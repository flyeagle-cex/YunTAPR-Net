"""Restart delta only: pure integers, artificial SQLite, AST, no model/GPU/data."""
from pathlib import Path
from types import SimpleNamespace
import ast,copy,hashlib,json,sqlite3,sys,unittest
ROOT=Path(__file__).absolute().parents[2];sys.path.insert(0,str(ROOT/'src'))
from yuntapr.training.phase_b_v2_seed2027_restart_v3 import accounting as a,protocol as p
from yuntapr.training.phase_b_v2_seed2027_restart_v3.quota import Ledger
from yuntapr.training.phase_b_v2_seed2027_restart_v3.authority import require_execution_authority,execution_instruction
from yuntapr.training.phase_b_v2_seed2027_restart_v3.ancestor import evidence_path,verify_old_rows,STOPPED_CAMPAIGN,accounted_bytes,require_stopped
OLD=ROOT/'src/yuntapr/training/phase_b_v2_seed2027_restart_v2';NEW=ROOT/'src/yuntapr/training/phase_b_v2_seed2027_restart_v3'

def node(path,name,cls=None):
    nodes=ast.parse(path.read_bytes()).body
    if cls:nodes=next(n.body for n in nodes if isinstance(n,ast.ClassDef) and n.name==cls)
    return next(n for n in nodes if getattr(n,'name',None)==name)

def mock_ledger(q):
    sql=[]
    class Con:
        def execute(self,query,args=()):
            sql.append(query)
            if 'count(*) FROM epochs' in query:return SimpleNamespace(fetchone=lambda:(0,))
            if 'SELECT status,nonce' in query:return SimpleNamespace(fetchone=lambda:('ACTIVE','n'*32))
            return None
    ledger=object.__new__(Ledger);ledger.con=Con();ledger.snapshot=lambda:q;ledger._atomic=lambda fn:fn()
    return ledger,sql

class RestartTests(unittest.TestCase):
    def test_01_truthful_empty_new_campaign(self):
        q=a.fields(0,0);self.assertEqual((q['reserved'],q['returned_verified']),(2087,2086))
        a.validate(q,complete_transaction=True)
    def test_02_unknown_old_attempt_cannot_be_promoted(self):
        q=a.fields(10,10);q['returned_verified']+=1
        with self.assertRaises(ValueError):a.validate(q,complete_transaction=True)
    def test_03_new_unverified_attempt_prevents_checkpoint_pause(self):
        q=a.fields(5228,5227)
        with self.assertRaises(ValueError):a.validate(q,complete_transaction=True)
        a.validate(q,complete_transaction=False)
    def test_04_cap_and_bad_types(self):
        for n,v in ((282313,282313),(1,2),(-1,0),(True,0),(0,None)):
            with self.assertRaises(ValueError):a.fields(n,v)
    def test_05_full_new_scope_with_historical_unknown_can_complete(self):
        q=a.fields(282312,282312);q['runs']=[dict(status='COMPLETE') for _ in p.ORDER]
        ledger,sql=mock_ledger(q);ledger.complete()
        self.assertEqual((q['reserved'],q['returned_verified']),(284399,284398))
        self.assertTrue(any("status='COMPLETE'" in s for s in sql))
    def test_06_incomplete_new_scope_cannot_complete(self):
        q=a.fields(282311,282311);q['runs']=[dict(status='COMPLETE') for _ in p.ORDER]
        with self.assertRaises(ValueError):mock_ledger(q)[0].complete()
    def test_07_safe_pause_counts_only_verified_new_transactions(self):
        q=a.fields(5228,5228);ledger,sql=mock_ledger(q)
        receipt=ledger.pause_boundary(1,'n'*32,dict(content_bytes=1,elapsed_seconds=1))
        self.assertEqual(receipt['status'],'PAUSED_VERIFIED')
        self.assertEqual(receipt['quota']['old_unverified_attempts'],1)
    def test_08_unverified_new_transaction_cannot_pause(self):
        with self.assertRaises(ValueError):mock_ledger(a.fields(5228,5227))[0].pause_boundary(1,'n'*32,{})
    def test_09_config_is_byte_identical(self):
        raw=(p.OUT/'config.json').read_bytes()
        self.assertEqual(raw,(ROOT/'docs/phase_b_v2_formal_execution/seed2027_execution_v1/config.json').read_bytes())
        p.validate_plan(json.loads(raw));self.assertEqual(p.TOTAL,p.MAX_NEW+p.OLD_RESERVED)
    def test_10_new_human_scope(self):
        self.assertEqual(execution_instruction()['answer'],'授权重新启动及额外 2,087 次额度，累计上限 284,399；仅已执行桌面 GPU 常驻应用清理')
        require_execution_authority(2027)
        for seed in (2026,2028,True,'2027'):
            with self.assertRaises(PermissionError):require_execution_authority(seed)
    def test_11_numeric_and_monitor_methods_unchanged(self):
        for file,cls,methods in [('engine.py','Engine',('train','validate')),('supervisor.py',None,('main',)),
            ('control.py',None,('start','pause','open_owned_job','emergency_stop'))]:
            for method in methods:
                # Module path changes route the same algorithm to the new namespace.
                old=ast.dump(node(OLD/file,method,cls),include_attributes=False).replace('yuntapr.training.phase_b_v2_seed2027_restart_v2.','yuntapr.training.phase_b_v2_seed2027_restart_v3.')
                self.assertEqual(old,ast.dump(node(NEW/file,method,cls),include_attributes=False))
        self.assertEqual((OLD/'resources.py').read_bytes(),(NEW/'resources.py').read_bytes())
        self.assertEqual(ast.dump(node(OLD/'checkpoint.py','Store'),include_attributes=False),ast.dump(node(NEW/'checkpoint.py','Store'),include_attributes=False))
    def test_12_prior_scope_forbids_weights_escape_and_2025(self):
        for rel in ('../x.json','C:/x.json','docs/phase_b_v2_formal_execution/seed2027_execution_v1/x.pt',
                    'docs/phase_b_v2_formal_execution/seed2027_execution_v1/2025/x.json','src/x.json'):
            with self.assertRaises(PermissionError):evidence_path(rel)
    def test_13_prior_sqlite_fixture_and_mismatch(self):
        with sqlite3.connect(':memory:') as con:
            con.executescript('CREATE TABLE campaign(id,status,reason); CREATE TABLE attempts(status); CREATE TABLE runs(id,ordinal,status,epoch,updates,last_sha); CREATE TABLE epochs(run,epoch,phase); CREATE TABLE sessions(n,status);')
            con.execute('INSERT INTO campaign VALUES(?,?,?)',(STOPPED_CAMPAIGN,'ACTIVE',None))
            con.executemany('INSERT INTO attempts VALUES(?)',[('RETURNED_VERIFIED',)]*960)
            for i,(m,arm) in enumerate(p.ORDER):con.execute('INSERT INTO runs VALUES(?,?,?,?,?,?)',(p.run_id(m,arm),i,'RUNNING' if i==0 else 'PENDING',0,960 if i==0 else 0,None))
            con.execute('INSERT INTO epochs VALUES(?,?,?)',(p.run_id(*p.ORDER[0]),1,'TRAINING'))
            con.execute("INSERT INTO sessions VALUES(1,'ACTIVE')")
            verify_old_rows(con)
            con.execute("INSERT INTO attempts VALUES('RESERVED_BEFORE_CALL')")
            with self.assertRaises(ValueError):verify_old_rows(con)
    def test_14_new_checkpoint_quota_contract_with_old_unknown(self):
        # Execute only the real metadata/coverage/quota prefix, before tensor checks.
        fn=copy.deepcopy(node(NEW/'checkpoint.py','validate','Contract'))
        cut=next(i for i,n in enumerate(fn.body) if isinstance(n,ast.Assign) and isinstance(n.targets[0],ast.Name) and n.targets[0].id=='m')
        fn.body=fn.body[:cut]
        ns=dict(__package__='yuntapr.training.phase_b_v2_seed2027_restart_v3',SCHEMA='TEST_ONLY',STEPS=p.STEPS,
            TRAIN_N=p.TRAIN_N,DEV_N=p.DEV_N,CAMPAIGN=p.CAMPAIGN,TOTAL=p.TOTAL,digest=p.digest,epoch_order=lambda ids,epoch:ids)
        exec(compile(ast.Module(body=[fn],type_ignores=[]),'checkpoint-metadata-prefix','exec'),ns)
        identity=dict(run_id=p.run_id(*p.ORDER[0]),code=dict(failed_ancestor_sha256='a'*64))
        obj=SimpleNamespace(identity=identity,initial='initial',key='source',train_ids=('artificial-train',),dev_ids=('artificial-dev',))
        report=dict(complete=True,source_sha='source',ids_sha=p.digest(obj.dev_ids),summary=dict(scenes=p.DEV_N,n_valid=p.DEV_N*3430))
        report['receipt_sha']=p.digest(report)
        quota=dict(campaign=p.CAMPAIGN,**a.fields(p.STEPS,p.STEPS),old_ancestor_receipt_sha256='a'*64,runs=[dict(id=identity['run_id'],updates=p.STEPS)])
        payload=dict(schema='TEST_ONLY',identity=identity,initial_sha='initial',epoch=1,update=p.STEPS,parent_last_sha=None,
            model=None,optimizer=None,scheduler=None,rng=None,train=dict(scenes=p.TRAIN_N,batches=p.STEPS,ids_sha=p.digest(obj.train_ids),n_valid=p.TRAIN_N*3430),validation=report,quota=quota)
        ns['validate'](obj,payload)
        bad=copy.deepcopy(payload);bad['quota']['returned_verified']+=1
        with self.assertRaises(ValueError):ns['validate'](obj,bad)
    def test_15_no_real_campaign_or_heavy_import(self):
        self.assertFalse(p.DB.exists());self.assertFalse(p.DB.with_suffix('.once').exists())
        self.assertFalse((p.LOCAL/'sessions').exists());self.assertNotIn('torch',sys.modules)
    def test_16_byte_carry_includes_public_metadata_without_double_count(self):
        events=[dict(event='READ_FINISHED',bytes=100),dict(event='PUBLIC_METADATA_READ',bytes=20),
            dict(event='READ_RESERVED',bytes=100),dict(event='READ_CHUNK',bytes=100)]
        self.assertEqual(a.prior_content_bytes(events,110),120)
        with self.assertRaises(ValueError):a.prior_content_bytes(events,121)
    def test_17_exact_new_release_and_tamper_rejection(self):
        raw=(p.OUT/'config.json').read_bytes();actual=dict(sha256='a'*64,pins={'fake.py':'b'*64})
        from yuntapr.training.phase_b_v2_seed2027_restart_v3.authority import EXECUTION_SCOPE
        record=dict(schema='SEED2027_HUMAN_AUTHORIZED_FRESH_RESTART_v3',campaign=p.CAMPAIGN,seed=2027,
            human_instruction=execution_instruction(),human_instruction_sha256=p.digest(execution_instruction()),
            execution_scope=EXECUTION_SCOPE,launch_authorized=True,planned_attempt_cap=p.TOTAL,
            new_attempt_cap=p.MAX_NEW,prior_reserved=2087,prior_returned_verified=2086,original_execution_commit=p.BASELINE,
            failed_ancestor_sha256='c'*64,held_publication_commit='ed45c6c817b9c5ab47b1e3f30ce30e99ddb9e38c',
            dependency_manifest_sha256='2d02c5757f9da5fc1fef8b82168ffd689b96c07056d1cc13acf354a3fd88e780',
            original_resource_limits=p.LIMITS,source_sha256=actual['sha256'],source_pins=actual['pins'],
            config_sha256=hashlib.sha256(raw).hexdigest())
        p.validate_record(record,actual,raw)
        for k,v in [('new_attempt_cap',282313),('prior_returned_verified',2087),('planned_attempt_cap',284400),
            ('seed',2028),('human_instruction',{'APPROVED':True}),('failed_ancestor_sha256',None)]:
            with self.subTest(field=k):
                with self.assertRaises(ValueError):p.validate_record(dict(record,**{k:v}),actual,raw)
    def test_18_closed_reads_carried_bytes_and_trailing_abandon(self):
        events=[dict(event='PUBLIC_METADATA_READ',bytes=3),dict(event='READ_RESERVED',file_key='a',opened_utc='t'),dict(event='READ_FINISHED',file_key='a',opened_utc='t',status='SHA_PASS',expected_sha256='a',actual_sha256='a',bytes=7)]
        total,abandoned=accounted_bytes(events,10,19,allow_trailing_abandon=True)
        self.assertEqual((total,abandoned),(20,None))
        events2=events+[dict(event='READ_RESERVED',file_key='b',opened_utc='u')]
        total,abandoned=accounted_bytes(events2,10,19,allow_trailing_abandon=True)
        self.assertEqual((total,abandoned),(20,('b','u')))
        with self.assertRaises(ValueError):accounted_bytes(events2,10,19)
        with self.assertRaises(ValueError):accounted_bytes(events2,10,21,allow_trailing_abandon=True)
        with self.assertRaises(ValueError):accounted_bytes([dict(event='READ_RESERVED',file_key='x',opened_utc='t'),dict(event='READ_RESERVED',file_key='y',opened_utc='t2')],10,10,allow_trailing_abandon=True)
    def test_19_native_stopped_proof_is_mandatory(self):
        fixture=dict(campaign=STOPPED_CAMPAIGN,observation=dict(effective_state='STOPPED_UNCLEAN_NO_LAST',observed_process_tree_empty=True),quota=dict(reserved=2087,returned_verified=2086),native_probes=dict(job=dict(status='ABSENT')))
        require_stopped(fixture)
        for state in ('LIVE','NOT_VERIFIED_NATIVE_PROBE','PAUSED'):
            bad=copy.deepcopy(fixture);bad['observation']['effective_state']=state
            with self.assertRaises(PermissionError):require_stopped(bad)
        bad=copy.deepcopy(fixture);bad['native_probes']['job']['status']='PRESENT'
        with self.assertRaises(PermissionError):require_stopped(bad)

if __name__=='__main__':
    result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(RestartTests))
    out=p.LOCAL/'restart_delta_tests.json'
    number=2
    while out.exists():
        out=p.LOCAL/f'restart_delta_tests_{number:02d}.json';number+=1
    with out.open('x',encoding='utf-8',newline='\n') as f:
        json.dump(dict(tests=result.testsRun,passed=result.testsRun-len(result.failures)-len(result.errors),
            failures=[(str(t),trace) for t,trace in result.failures],errors=[(str(t),trace) for t,trace in result.errors]),f,indent=2)
    raise SystemExit(not result.wasSuccessful())
