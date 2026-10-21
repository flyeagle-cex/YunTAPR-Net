"""Recovery delta only: artificial SQL/OS-task mocks, no tensor or optimizer."""
from pathlib import Path
from contextlib import contextmanager,nullcontext,closing
from unittest.mock import patch
import ast,hashlib,json,os,sqlite3,sys,unittest,uuid
ROOT=Path(__file__).absolute().parents[2];sys.path.insert(0,str(ROOT/'src'))
from yuntapr.training.phase_b_v2_seed2027_b1_epoch7_recovery_v2 import protocol as p,quota as q,ancestor as a,accounting as acc,task_owner as task
from yuntapr.training.phase_b_v2_seed2027_b1_epoch7_recovery_v2.authority import execution_instruction,require_execution_authority
from yuntapr.training.phase_b_v2_seed2027_b1_epoch7_recovery_v1 import protocol as old
NEW=ROOT/'src/yuntapr/training/phase_b_v2_seed2027_b1_epoch7_recovery_v2'
OLD=NEW.with_name('phase_b_v2_seed2027_b1_epoch7_recovery_v1')

def method(path,name,cls=None):
    body=ast.parse(path.read_bytes()).body
    if cls:body=next(x.body for x in body if isinstance(x,ast.ClassDef) and x.name==cls)
    return next(x for x in body if getattr(x,'name',None)==name)

@contextmanager
def fixture():
    folder=p.LOCAL/('artificial_'+uuid.uuid4().hex);folder.mkdir()
    with closing(sqlite3.connect(folder/'old.sqlite')) as c:
        c.executescript('CREATE TABLE campaign(id,status,reason);CREATE TABLE attempts(status);CREATE TABLE runs(id,ordinal,status,epoch,updates,last_sha);CREATE TABLE epochs(run,epoch,phase,train,validation,last_receipt);CREATE TABLE sessions(n,status);')
        c.execute('INSERT INTO campaign VALUES(?,?,NULL)',(a.SOURCE_CAMPAIGN,'ACTIVE'))
        c.executemany('INSERT INTO attempts VALUES(?)',[('RETURNED_VERIFIED',)]*548)
        for i,(m,arm) in enumerate(p.ORDER):
            c.execute('INSERT INTO runs VALUES(?,?,?,?,?,?)',(p.run_id(m,arm),i,'COMPLETE' if i==0 else ('RUNNING' if i==1 else 'PENDING'),9 if i==0 else (7 if i==1 else 0),47052 if i==0 else (37144 if i==1 else 0),a.COMPLETE_SHA if i==0 else (p.LAST_SHA if i==1 else None)))
        for run,limit in ((a.COMPLETE_RUN,9),(a.RUN,8)):
            for e in range(1,limit+1):c.execute('INSERT INTO epochs VALUES(?,?,?,?,?,?)',(run,e,'TRAINING' if run==a.RUN and e==8 else 'LAST_COMMITTED','t'+str(e),'v'+str(e),'r'+str(e)))
        c.execute("INSERT INTO sessions VALUES(1,'ACTIVE')");c.commit()
    release={'failed_ancestor_sha256':'a'*64}
    with patch.object(q,'ROOT',folder),patch.object(q,'DB',folder/'new.sqlite'),patch.object(p,'verify_release',return_value=release),patch.object(a,'SOURCE_DB','old.sqlite'),patch.object(a,'Guard',return_value=nullcontext()):yield folder,release

class Tests(unittest.TestCase):
    def test_01_exact_nonrefundable_arithmetic(self):
        self.assertEqual((p.OLD_RESERVED,p.OLD_VERIFIED,p.TOTAL,p.MAX_NEW,p.ABANDONED),(165383,165382,364047,198664,81735))
        self.assertEqual(p.TOTAL-old.TOTAL,548);self.assertEqual(282312+81735,p.TOTAL)
        self.assertEqual(acc.fields(198664,198664)['reserved'],364047)
        with self.assertRaises(ValueError):acc.validate(acc.fields(1,0),complete_transaction=True)
    def test_02_exact_failed_predecessor(self):
        with fixture() as (folder,_):
            with closing(sqlite3.connect(folder/'old.sqlite')) as c:
                a.verify_source(c);c.execute("INSERT INTO attempts VALUES('RESERVED_BEFORE_CALL')")
                with self.assertRaises(ValueError):a.verify_source(c)
    def test_03_complete_b0_adopt_seven_no_refund_or_duplicate(self):
        with fixture() as (folder,release):
            before=hashlib.sha256((folder/'old.sqlite').read_bytes()).hexdigest();ledger=q.Ledger.initialize(release)
            try:
                self.assertEqual(ledger.run_row(a.COMPLETE_RUN)['status'],'COMPLETE')
                self.assertEqual(ledger.run_row(a.RUN)['updates'],36596)
                self.assertEqual(ledger.con.execute('SELECT count(*) FROM epochs').fetchone(),(16,))
                n,nonce=ledger.claim_session();ledger.activate_session(n,nonce);ledger.start_run(a.RUN);ledger.begin_epoch(a.RUN,8)
                ledger.reserve(a.RUN,36597)
                with self.assertRaises(sqlite3.IntegrityError):ledger.reserve(a.RUN,36597)
                ledger.returned(a.RUN,36597);self.assertEqual(ledger.snapshot()['reserved'],165384)
                with self.assertRaises(PermissionError):ledger.claim_session()
            finally:ledger.close()
            self.assertEqual(before,hashlib.sha256((folder/'old.sqlite').read_bytes()).hexdigest())
    def test_04_fixed_human_decision_and_science(self):
        row=execution_instruction();self.assertEqual(row['additional_attempts'],548);self.assertEqual(row['maximum_attempts'],364047)
        self.assertEqual(row['answer'],'授权修复集成、恢复及额外548次额度')
        self.assertEqual(p.LIMITS,old.LIMITS);self.assertEqual(p.ORDER,old.ORDER)
        self.assertEqual((p.OUT/'config.json').read_bytes(),(old.OUT/'config.json').read_bytes())
        p.validate_plan(json.loads((p.OUT/'config.json').read_bytes()))
        for x in (True,2026,2028):
            with self.assertRaises(PermissionError):require_execution_authority(x)
    def test_05_train_validate_rng_unchanged(self):
        for file,name,cls in [('engine.py','train','Engine'),('engine.py','validate','Engine'),('recovery.py','apply_validated_state',None),('supervisor.py','FormalJob',None)]:
            self.assertEqual(ast.dump(method(OLD/file,name,cls)),ast.dump(method(NEW/file,name,cls)))
        text=(NEW/'recovery.py').read_text();self.assertIn('RECOVERY_PREFIX as PREFIX',text)
        self.assertIn('phase_b_v2_seed2027_epoch2_recovery_v2.checkpoint',text)
        self.assertIn("COMPLETE_PREFIX+ident+'.json'",(NEW/'engine.py').read_text())
    def test_06_task_scope_rejects_before_os_access(self):
        for n,nonce in [(0,'a'*32),(True,'a'*32),(1,'bad'),(1000,'a'*32)]:
            with self.assertRaises(PermissionError):task.task_name(n,nonce)
        self.assertNotIn('Popen(',ast.unparse(method(NEW/'control.py','start')))
    def test_07_fixed_registration_and_no_retries(self):
        folder=p.LOCAL/('artificial_task_'+uuid.uuid4().hex);folder.mkdir();entry=ROOT/'scripts/phase_b_v2_seed2027_b1_epoch7_recovery_v2/Task-Owner.ps1'
        release={'source_sha256':'b'*64,'source_pins':{entry.relative_to(ROOT).as_posix():hashlib.sha256(entry.read_bytes()).hexdigest()}}
        with patch.object(task,'owned_json',return_value={'python':sys.executable}),patch.object(task,'session_root',return_value=folder),patch.object(task,'ps',return_value='{"registered":true}') as invoke:
            task.start_owner(1,'c'*32,release);script=invoke.call_args.args[0]
            for fragment in ('-RunLevel Limited','-MultipleInstances IgnoreNew','RestartCount -ne 0','Start-ScheduledTask','No existing task overwrite or retry'):
                self.assertIn(fragment,script)
            with self.assertRaises(PermissionError):task.start_owner(1,'c'*32,release)
            self.assertEqual(invoke.call_count,1)
    def test_08_bootstrap_seed_set_before_interpreter(self):
        text=(ROOT/'scripts/phase_b_v2_seed2027_b1_epoch7_recovery_v2/Task-Owner.ps1').read_text(encoding='ascii')
        self.assertLess(text.index("$env:PYTHONHASHSEED='2026'"),text.index('& $taskPython'))
        self.assertIn('HASH_SEED_MUST_BE_SET_BEFORE_PYTHON_START',(NEW/'task_entry.py').read_text())
        self.assertIn('TASK_OWNER_NATIVE_PID_CREATION_IMAGE_MISMATCH',(NEW/'supervisor.py').read_text())
    def test_09_wrong_owner_claim_is_rejected(self):
        class Fake:
            def execute(self,*args):return self
            def fetchone(self):return ('ACTIVE','d'*32)
            def close(self):pass
        spec={'synthetic':True}
        with patch.object(task,'verify_release',return_value={}),patch.object(task,'owned_json',return_value=spec),patch.object(task,'fixed_spec',return_value=spec),patch.object(q,'ro',return_value=Fake()):
            with self.assertRaises(PermissionError):task.validate_owner_request(1,'d'*32)
    def test_10_no_real_training_imports(self):
        self.assertNotIn('torch',sys.modules);self.assertFalse(p.DB.exists());self.assertFalse(p.DB.with_suffix('.once').exists())

if __name__=='__main__':unittest.main(verbosity=2)
