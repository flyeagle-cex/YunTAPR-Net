"""Version delta only: fake SQLite, source AST and mocked task API; no model."""
from pathlib import Path
from contextlib import contextmanager,nullcontext,closing
from unittest.mock import patch
import ast,hashlib,json,sqlite3,sys,unittest,uuid
ROOT=Path(__file__).absolute().parents[2];sys.path.insert(0,str(ROOT/'src'))
from yuntapr.training.phase_b_v2_seed2027_b1_epoch7_recovery_v4 import protocol as p,quota as q,ancestor as a,accounting as acc,task_owner as task,console
from yuntapr.training.phase_b_v2_seed2027_b1_epoch7_recovery_v4.authority import execution_instruction,require_execution_authority
from yuntapr.training.phase_b_v2_seed2027_b1_epoch7_recovery_v3 import protocol as old
NEW=ROOT/'src/yuntapr/training/phase_b_v2_seed2027_b1_epoch7_recovery_v4';OLD=NEW.with_name('phase_b_v2_seed2027_b1_epoch7_recovery_v3')

def method(path,name,cls=None):
    body=ast.parse(path.read_bytes()).body
    if cls:body=next(x.body for x in body if isinstance(x,ast.ClassDef) and x.name==cls)
    return next(x for x in body if getattr(x,'name',None)==name)

@contextmanager
def fixture():
    folder=p.LOCAL/('artificial_'+uuid.uuid4().hex);folder.mkdir()
    with closing(sqlite3.connect(folder/'old.sqlite')) as c:
        c.executescript('CREATE TABLE campaign(id,status,reason);CREATE TABLE attempts(n,run,update_no,status);CREATE TABLE runs(id,ordinal,status,epoch,updates,last_sha);CREATE TABLE epochs(run,epoch,phase,train,validation,last_receipt);CREATE TABLE sessions(n,status);')
        c.execute('INSERT INTO campaign VALUES(?,?,NULL)',(a.SOURCE_CAMPAIGN,'ACTIVE'))
        c.executemany('INSERT INTO attempts VALUES(?,?,?,?)',[(i,a.RUN,36596+i,'RETURNED_VERIFIED') for i in range(1,923)])
        for i,(m,arm) in enumerate(p.ORDER):
            c.execute('INSERT INTO runs VALUES(?,?,?,?,?,?)',(p.run_id(m,arm),i,'COMPLETE' if i==0 else ('RUNNING' if i==1 else 'PENDING'),9 if i==0 else (7 if i==1 else 0),47052 if i==0 else (37518 if i==1 else 0),a.COMPLETE_SHA if i==0 else (p.LAST_SHA if i==1 else None)))
        for run,limit in ((a.COMPLETE_RUN,9),(a.RUN,8)):
            for e in range(1,limit+1):c.execute('INSERT INTO epochs VALUES(?,?,?,?,?,?)',(run,e,'TRAINING' if run==a.RUN and e==8 else 'LAST_COMMITTED','t'+str(e),'v'+str(e),'r'+str(e)))
        c.execute("INSERT INTO sessions VALUES(1,'ACTIVE')");c.commit()
    release={'failed_ancestor_sha256':'a'*64}
    with patch.object(q,'ROOT',folder),patch.object(q,'DB',folder/'new.sqlite'),patch.object(p,'verify_release',return_value=release),patch.object(a,'SOURCE_DB','old.sqlite'),patch.object(a,'Guard',return_value=nullcontext()):yield folder,release

class Tests(unittest.TestCase):
    def test_01_exact_nonrefundable_922(self):
        self.assertEqual((p.OLD_RESERVED,p.OLD_VERIFIED,p.TOTAL,p.MAX_NEW,p.ABANDONED),(166305,166304,364969,198664,82657))
        self.assertEqual(p.TOTAL-old.TOTAL,922);self.assertEqual(282312+82657,p.TOTAL)
        self.assertEqual(acc.fields(198664,198664)['reserved'],364969)
        self.assertEqual(166305+198664,p.TOTAL)
        with self.assertRaises(ValueError):acc.validate(acc.fields(1,0),complete_transaction=True)
    def test_02_exact_old_attempts_and_source(self):
        with fixture() as (folder,_):
            with closing(sqlite3.connect(folder/'old.sqlite')) as c:
                a.verify_source(c);c.execute("UPDATE attempts SET status='RESERVED_BEFORE_CALL' WHERE n=922")
                with self.assertRaises(ValueError):a.verify_source(c)
    def test_03_adopt_only_complete_epochs_new_quota_no_refund(self):
        with fixture() as (folder,release):
            before=hashlib.sha256((folder/'old.sqlite').read_bytes()).hexdigest();ledger=q.Ledger.initialize(release)
            try:
                self.assertEqual(ledger.run_row(a.COMPLETE_RUN)['status'],'COMPLETE')
                self.assertEqual(ledger.run_row(a.RUN)['updates'],36596)
                self.assertEqual(ledger.con.execute('SELECT count(*) FROM epochs').fetchone(),(16,))
                n,nonce=ledger.claim_session();ledger.activate_session(n,nonce);ledger.start_run(a.RUN);ledger.begin_epoch(a.RUN,8)
                ledger.reserve(a.RUN,36597)
                with self.assertRaises(sqlite3.IntegrityError):ledger.reserve(a.RUN,36597)
                ledger.returned(a.RUN,36597);self.assertEqual(ledger.snapshot()['reserved'],166306)
                with self.assertRaises(PermissionError):ledger.claim_session()
            finally:ledger.close()
            self.assertEqual(before,hashlib.sha256((folder/'old.sqlite').read_bytes()).hexdigest())
    def test_04_direct_human_scope_science_unchanged(self):
        row=execution_instruction();self.assertEqual(row['additional_attempts'],922);self.assertEqual(row['maximum_attempts'],364969)
        self.assertEqual(row['message'],'授权修复集成、恢复及额外922次额度')
        self.assertEqual(row['last_sha256'],p.LAST_SHA)
        self.assertEqual(p.LIMITS,old.LIMITS);self.assertEqual(p.ORDER,old.ORDER)
        self.assertEqual((p.OUT/'config.json').read_bytes(),(old.OUT/'config.json').read_bytes())
        p.validate_plan(json.loads((p.OUT/'config.json').read_bytes()))
        for x in (True,2026,2028):
            with self.assertRaises(PermissionError):require_execution_authority(x)
    def test_05_numerical_paths_reader_and_rng_unchanged(self):
        for file,name,cls in [('engine.py','train','Engine'),('engine.py','validate','Engine'),('recovery.py','apply_validated_state',None),('supervisor.py','FormalJob',None),('checkpoint.py','read','Store')]:
            self.assertEqual(ast.dump(method(OLD/file,name,cls)),ast.dump(method(NEW/file,name,cls)))
        text=(NEW/'checkpoint.py').read_text();self.assertIn("q['old_campaign_reserved']!=OLD_RESERVED",text)
    def test_06_bad_task_scope_denied_before_os(self):
        for n,nonce in [(0,'a'*32),(True,'a'*32),(1,'bad'),(1000,'a'*32)]:
            with self.assertRaises(PermissionError):task.task_name(n,nonce)
        self.assertNotIn('Popen(',ast.unparse(method(NEW/'control.py','start')))
    def test_07_fixed_gui_task_no_retry(self):
        folder=p.LOCAL/('artificial_task_'+uuid.uuid4().hex);folder.mkdir();entry=NEW/'gui_owner.py'
        release={'source_sha256':'b'*64,'gui_runtime_sha256':'c'*64,'source_pins':{entry.relative_to(ROOT).as_posix():hashlib.sha256(entry.read_bytes()).hexdigest()}}
        gui={'wrapper_path':str(Path(sys.executable).with_name('pythonw.exe')),'native_path':str(Path(sys.executable).with_name('pythonw.exe'))}
        with patch.object(task,'owned_json',return_value={'python':sys.executable}),patch.object(task,'gui_runtime',return_value=gui),patch.object(task,'session_root',return_value=folder),patch.object(task,'ps',return_value='{"registered":true}') as invoke:
            task.start_owner(1,'d'*32,release);script=invoke.call_args.args[0]
            for fragment in ('-RunLevel Limited','-MultipleInstances IgnoreNew','RestartCount -ne 0','Start-ScheduledTask','No existing task overwrite or retry','pythonw.exe'):
                self.assertIn(fragment,script)
            self.assertNotIn('Task-Owner.ps1',script)
            with self.assertRaises(PermissionError):task.start_owner(1,'d'*32,release)
            self.assertEqual(invoke.call_count,1)
    def test_08_console_errors_fail_closed(self):
        receipt=dict(before={},detached=False,after=dict(hwnd=0,process_count=0,process_ids=[],winerror=5))
        with patch.object(console,'detach_current_console',return_value=receipt):
            with self.assertRaises(PermissionError):console.isolate()
        receipt['after']['winerror']=6
        with patch.object(console,'detach_current_console',return_value=receipt):self.assertEqual(console.isolate(),receipt)
    def test_09_bootstrap_environment_and_isolation_order(self):
        gui=(NEW/'gui_owner.py').read_text(encoding='utf-8');worker=(NEW/'worker.py').read_text(encoding='utf-8')
        self.assertLess(gui.index("PYTHONHASHSEED='2026'"),gui.index('job.spawn('))
        self.assertLess(worker.index('isolation=isolate()'),worker.index('from .engine import Engine'))
        self.assertIn('validate_gui_parent(n,nonce)',(NEW/'task_entry.py').read_text())
        self.assertIn('OWNER_OUTSIDE_GUI_OWNED_JOB',(NEW/'task_owner.py').read_text())
    def test_10_pause_requires_outer_gui_completion(self):
        text=(NEW/'quota.py').read_text(encoding='utf-8')
        self.assertIn("owned_json(path/'gui_termination.json')",text)
        self.assertIn("gui['supervisor_exit_code']!=0",text)
    def test_11_no_training_or_live_ledger(self):
        self.assertNotIn('torch',sys.modules);self.assertFalse(p.DB.exists());self.assertFalse(p.DB.with_suffix('.once').exists())

if __name__=='__main__':unittest.main(verbosity=2)
