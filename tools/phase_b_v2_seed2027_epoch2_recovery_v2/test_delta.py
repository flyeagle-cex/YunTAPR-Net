"""Epoch2 recovery delta: integer accounting and artificial SQLite only."""
from pathlib import Path
from contextlib import contextmanager,nullcontext
from unittest.mock import patch
from types import SimpleNamespace
import ast,copy,json,re,sqlite3,sys,unittest,uuid
ROOT=Path(__file__).absolute().parents[2];sys.path.insert(0,str(ROOT/'src'))
from yuntapr.training.phase_b_v2_seed2027_epoch2_recovery_v2 import protocol as p,accounting as a,quota as q,ancestor as anc
from yuntapr.training.phase_b_v2_seed2027_epoch2_recovery_v2.recovery import validate_history_metrics
from yuntapr.training.phase_b_v2_seed2027_epoch2_recovery_v2.authority import execution_instruction,require_execution_authority
OLD=ROOT/'src/yuntapr/training/phase_b_v2_seed2027_epoch2_recovery_v1';NEW=OLD.with_name('phase_b_v2_seed2027_epoch2_recovery_v2')

def node(path,name,cls=None):
    rows=ast.parse(path.read_bytes()).body
    if cls:rows=next(x.body for x in rows if isinstance(x,ast.ClassDef) and x.name==cls)
    return next(x for x in rows if getattr(x,'name',None)==name)

@contextmanager
def fixture():
    folder=p.LOCAL/('synthetic_sqlite_'+uuid.uuid4().hex);folder.mkdir()
    old=folder/'old.sqlite';con=sqlite3.connect(old)
    con.executescript('CREATE TABLE campaign(id,status,reason);CREATE TABLE attempts(status);CREATE TABLE runs(id,ordinal,status,epoch,updates,last_sha);CREATE TABLE epochs(run,epoch,phase,train,validation,last_receipt);CREATE TABLE sessions(n,status);')
    con.execute('INSERT INTO campaign VALUES(?,?,NULL)',(anc.SOURCE_CAMPAIGN,'ACTIVE'))
    con.executemany('INSERT INTO attempts VALUES(?)',[('RETURNED_VERIFIED',)]*10456)
    for i,(m,arm) in enumerate(p.ORDER):
        con.execute('INSERT INTO runs VALUES(?,?,?,?,?,?)',(p.run_id(m,arm),i,'RUNNING' if i==0 else 'PENDING',2 if i==0 else 0,15684 if i==0 else 0,p.LAST_SHA if i==0 else None))
    for e in (1,2,3):con.execute('INSERT INTO epochs VALUES(?,?,?,?,?,?)',(anc.RUN,e,'LAST_COMMITTED' if e<3 else 'WAIT_VALIDATION','train'+str(e),'validation'+str(e),'receipt'+str(e)))
    con.execute("INSERT INTO sessions VALUES(1,'ACTIVE')");con.commit();con.close()
    release={'failed_ancestor_sha256':'a'*64}
    with patch.object(q,'ROOT',folder),patch.object(q,'DB',folder/'new.sqlite'),patch.object(p,'verify_release',return_value=release),patch.object(anc,'SOURCE_DB','old.sqlite'),patch.object(anc,'Guard',return_value=nullcontext()):
        yield folder,release

class Tests(unittest.TestCase):
    def test_01_accounting_and_scope(self):
        r=a.fields(0,0);self.assertEqual((r['reserved'],r['returned_verified'],r['adopted_prior_updates'],r['abandoned_old_updates']),(86415,86414,10456,75959))
        self.assertEqual(p.TOTAL,p.OLD_RESERVED+p.MAX_NEW);self.assertEqual(p.MAX_NEW,282312-p.SOURCE_UPDATE)
        self.assertEqual(a.fields(p.MAX_NEW,p.MAX_NEW)['reserved'],358271)
        for n,v in ((271857,271857),(True,0),(1,2)):
            with self.assertRaises(ValueError):a.fields(n,v)
    def test_02_no_refund_or_uncertain_promotion(self):
        r=a.fields(1,1);r['returned_verified']+=1
        with self.assertRaises(ValueError):a.validate(r,complete_transaction=True)
        with self.assertRaises(ValueError):a.validate(a.fields(1,0),complete_transaction=True)
    def test_03_source_fixture_and_reject_modified_counts(self):
        with fixture() as (folder,release):
            with sqlite3.connect(folder/'old.sqlite') as con:
                anc.verify_source(con);con.execute("INSERT INTO attempts VALUES('RESERVED_BEFORE_CALL')")
                with self.assertRaises(ValueError):anc.verify_source(con)
    def test_04_inherit_two_boundaries_not_unvalidated_third(self):
        with fixture() as (folder,release):
            import hashlib
            before=hashlib.sha256((folder/'old.sqlite').read_bytes()).hexdigest()
            ledger=q.Ledger.initialize(release)
            self.assertEqual(ledger.run_row(anc.RUN)['updates'],10456)
            self.assertEqual(ledger.con.execute('SELECT epoch,phase FROM epochs ORDER BY epoch').fetchall(),[(1,'LAST_COMMITTED'),(2,'LAST_COMMITTED')])
            n,nonce=ledger.claim_session();ledger.activate_session(n,nonce);ledger.start_run(anc.RUN)
            with self.assertRaises(ValueError):ledger.begin_epoch(anc.RUN,2)
            ledger.begin_epoch(anc.RUN,3)
            with self.assertRaises(PermissionError):ledger.reserve(anc.RUN,5229)
            self.assertEqual(ledger.reserve(anc.RUN,10457),1)
            with self.assertRaises(sqlite3.IntegrityError):ledger.reserve(anc.RUN,10457)
            ledger.returned(anc.RUN,10457)
            self.assertEqual(ledger.snapshot()['reserved'],86416)
            with self.assertRaises(ValueError):ledger.pause_boundary(n,nonce,{})
            with self.assertRaises(PermissionError):ledger.start_run(p.run_id(*p.ORDER[1]))
            ledger.close();self.assertEqual(before,hashlib.sha256((folder/'old.sqlite').read_bytes()).hexdigest())
    def test_05_pause_before_replay_preserves_epoch2_boundary(self):
        with fixture() as (folder,release):
            ledger=q.Ledger.initialize(release);n,nonce=ledger.claim_session();ledger.activate_session(n,nonce);ledger.request_pause()
            with self.assertRaises(q.PauseAtBoundary):ledger.start_run(anc.RUN)
            r=ledger.pause_boundary(n,nonce,{});self.assertEqual(r['quota']['reserved'],86415);ledger.close()
    def test_06_frozen_science_and_actual_human_reply(self):
        raw=(p.OUT/'config.json').read_bytes();self.assertEqual(raw,(ROOT/'docs/phase_b_v2_formal_execution/seed2027_epoch1_recovery_v2/config.json').read_bytes());p.validate_plan(json.loads(raw))
        auth=execution_instruction();self.assertEqual(auth['answer'],'授权修复集成、恢复及额外632次额度')
        self.assertEqual((auth['additional_attempts'],auth['maximum_attempts'],auth['source_epoch']),(632,358271,2))
        for seed in (2028,2026,True):
            with self.assertRaises(PermissionError):require_execution_authority(seed)
    def test_07_unchanged_training_math_and_watchdog(self):
        for file,cls,names in [('engine.py','Engine',('train','validate')),('checkpoint.py',None,('Store',)),('supervisor.py',None,('main',)),('recovery.py',None,('apply_validated_state',))]:
            for name in names:
                before=ast.dump(node(OLD/file,name,cls),include_attributes=False).replace('phase_b_v2_seed2027_epoch2_recovery_v1','phase_b_v2_seed2027_epoch2_recovery_v2')
                self.assertEqual(before,ast.dump(node(NEW/file,name,cls),include_attributes=False))
    def test_08_canonical_history_rejects_changed_values(self):
        payload=dict(train=dict(scenes=10455),validation=dict(scene_blocks=[('artificial',0)],summary=dict(brier=.2)))
        hist=json.loads(json.dumps(dict(train=payload['train'],development=payload['validation'])))
        validate_history_metrics(hist,payload);hist['development']['summary']['brier']=.201
        with self.assertRaises(ValueError):validate_history_metrics(hist,payload)
    def test_09_checkpoint_metadata_carries_new_nonrefundable_quota(self):
        fn=copy.deepcopy(node(NEW/'checkpoint.py','validate','Contract'))
        cut=next(i for i,n in enumerate(fn.body) if isinstance(n,ast.Assign) and isinstance(n.targets[0],ast.Name) and n.targets[0].id=='m');fn.body=fn.body[:cut]
        ns=dict(__package__='yuntapr.training.phase_b_v2_seed2027_epoch2_recovery_v2',re=re,SCHEMA='ARTIFICIAL',STEPS=p.STEPS,TRAIN_N=p.TRAIN_N,DEV_N=p.DEV_N,CAMPAIGN=p.CAMPAIGN,TOTAL=p.TOTAL,digest=p.digest,epoch_order=lambda ids,epoch:ids)
        exec(compile(ast.Module(body=[fn],type_ignores=[]),'metadata-only','exec'),ns)
        identity=dict(run_id=anc.RUN,code=dict(failed_ancestor_sha256='a'*64));obj=SimpleNamespace(identity=identity,initial='initial',key='source',train_ids=('artificial-train',),dev_ids=('artificial-dev',))
        report=dict(complete=True,source_sha='source',ids_sha=p.digest(obj.dev_ids),summary=dict(scenes=p.DEV_N,n_valid=p.DEV_N*3430));report['receipt_sha']=p.digest(report)
        quota=dict(campaign=p.CAMPAIGN,**a.fields(5228,5228),old_ancestor_receipt_sha256='a'*64,runs=[dict(id=anc.RUN,updates=15684)])
        payload=dict(schema='ARTIFICIAL',identity=identity,model=None,optimizer=None,scheduler=None,rng=None,initial_sha='initial',epoch=3,update=15684,parent_last_sha=p.LAST_SHA,train=dict(scenes=p.TRAIN_N,batches=p.STEPS,ids_sha=p.digest(obj.train_ids),n_valid=p.TRAIN_N*3430),validation=report,quota=quota)
        ns['validate'](obj,payload);payload['quota']['abandoned_old_updates']-=5228
        with self.assertRaises(ValueError):ns['validate'](obj,payload)
    def test_10_no_actual_session_or_heavy_import(self):
        self.assertFalse(p.DB.exists());self.assertFalse(p.DB.with_suffix('.once').exists());self.assertFalse((p.LOCAL/'sessions').exists());self.assertNotIn('torch',sys.modules)

if __name__=='__main__':unittest.main(verbosity=2)
