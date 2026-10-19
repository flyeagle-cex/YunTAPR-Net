"""Delta-only CPU metadata tests: no model, CUDA, optimizer or raw-data access."""
from pathlib import Path
from contextlib import nullcontext,contextmanager
import uuid
from unittest.mock import patch
import ast,hashlib,io,json,sqlite3,sys,tempfile,tracemalloc,unittest
ROOT=Path(__file__).absolute().parents[2];sys.path.insert(0,str(ROOT/'src'))
from yuntapr.training.phase_b_v2_seed2027_epoch1_recovery_v1 import accounting as a,protocol as p,quota as q,ancestor as an
from yuntapr.training.phase_b_v2_seed2027_epoch1_recovery_v1.evidence import scan,CHUNK,MAX_LINE
from yuntapr.training.phase_b_v2_seed2027_epoch1_recovery_v1.authority import require_execution_authority
NEW=ROOT/'src/yuntapr/training/phase_b_v2_seed2027_epoch1_recovery_v1'
OLD=ROOT/'src/yuntapr/training/phase_b_v2_seed2027_restart_v4'

def node(path,name,cls=None):
    nodes=ast.parse(path.read_bytes()).body
    if cls:nodes=next(n.body for n in nodes if isinstance(n,ast.ClassDef) and n.name==cls)
    return next(n for n in nodes if getattr(n,'name',None)==name)

@contextmanager
def fixture_dir():
    path=p.LOCAL/('synthetic_sqlite_'+uuid.uuid4().hex);path.mkdir()
    yield path # Preserve bounded artificial fixtures and failures for audit.

def fixture_old(path):
    c=sqlite3.connect(path)
    c.executescript('CREATE TABLE campaign(id,status,reason);CREATE TABLE attempts(status);CREATE TABLE runs(id,ordinal,status,epoch,updates,last_sha);CREATE TABLE epochs(run,epoch,phase,train,validation,last_receipt);')
    c.execute('INSERT INTO campaign VALUES(?,?,?)',('YUNTAPR_PHASE_B_V2_SEED2027_FRESH_RESTART_V4','FAILED_NO_RETRY','MemoryError'))
    c.executemany('INSERT INTO attempts VALUES(?)',[('RETURNED_VERIFIED',)]*5228)
    for i,(m,arm) in enumerate(p.ORDER):
        c.execute('INSERT INTO runs VALUES(?,?,?,?,?,?)',(p.run_id(m,arm),i,'RUNNING' if i==0 else 'PENDING',1 if i==0 else 0,5228 if i==0 else 0,p.LAST_SHA if i==0 else None))
    c.execute('INSERT INTO epochs VALUES(?,?,?,?,?,?)',(an.RUN,1,'LAST_COMMITTED','train','validation','receipt'))
    c.commit();c.close()

class Tests(unittest.TestCase):
    def test_01_preserve_all_prior_charges(self):
        r=a.fields(0,0);a.validate(r,complete_transaction=True)
        self.assertEqual((r['reserved'],r['returned_verified'],r['adopted_prior_updates'],r['abandoned_old_updates']),(75327,75326,5228,70099))
        self.assertEqual(a.fields(277084,277084)['reserved'],352411)
    def test_02_no_extra_or_unknown_refund(self):
        for n,v in ((277085,277085),(True,0),(-1,0),(1,2)):
            with self.assertRaises(ValueError):a.fields(n,v)
        r=a.fields(1,0)
        with self.assertRaises(ValueError):a.validate(r,complete_transaction=True)
        r=a.fields(1,1);r['returned_verified']+=1
        with self.assertRaises(ValueError):a.validate(r,complete_transaction=True)
    def test_03_immutable_science(self):
        raw=(p.OUT/'config.json').read_bytes();p.validate_plan(json.loads(raw))
        self.assertEqual(raw,(ROOT/'docs/phase_b_v2_formal_execution/seed2027_restart_v4/config.json').read_bytes())
        self.assertEqual(p.MAX_NEW+p.OLD_RESERVED,p.TOTAL)
    def test_04_stream_hash_and_pairing(self):
        rows=[dict(event='READ_RESERVED',file_key='x',opened_utc='t'),dict(event='READ_FINISHED',file_key='x',opened_utc='t',bytes=17),dict(event='PUBLIC_METADATA_READ',bytes=3)]
        raw=b''.join(json.dumps(r).encode()+b'\n' for r in rows)
        summary,data=scan(io.BytesIO(raw),event_log=True)
        self.assertEqual(summary['sha256'],hashlib.sha256(raw).hexdigest());self.assertEqual(summary['content_bytes'],20)
        self.assertIsNone(data);self.assertIsNone(summary['trailing_read_reservation'])
    def test_05_unfinished_read_is_explicit(self):
        r,_=scan(io.BytesIO(b'{"event":"READ_RESERVED","file_key":"x","opened_utc":"t"}\n'),event_log=True)
        self.assertEqual(r['trailing_read_reservation'],['x','t'])
    def test_06_malformed_or_unbounded_logs_reject(self):
        for raw in (b'{"event":"X"}',b'\n',b'{}\n',b'x'*(MAX_LINE+1),b'{"event":"READ_FINISHED","file_key":"x","opened_utc":"t","bytes":0}\n'):
            with self.subTest(size=len(raw)):
                with self.assertRaises((ValueError,KeyError)):scan(io.BytesIO(raw),event_log=True)
    def test_07_stream_memory_not_proportional_to_log(self):
        block=(b'{"event":"TEST","padding":"'+b'x'*970+b'"}\n')*1024
        class Repeated:
            n=48;part=b''
            def readinto(self,buf):
                if not self.part:
                    if self.n==0:return 0
                    self.n-=1;self.part=block
                n=min(len(buf),len(self.part));buf[:n]=self.part[:n];self.part=self.part[n:];return n
        tracemalloc.start();s,_=scan(Repeated(),event_log=True);_,peak=tracemalloc.get_traced_memory();tracemalloc.stop()
        self.assertEqual(s['lines'],48*1024);self.assertLess(peak,12*1024**2)
    def test_08_exact_last_scope(self):
        an.lexical(an.CP+'LAST_epoch_01.pt')
        for name in ('../x.json','C:/private.pt',an.CP+'LAST_epoch_02.pt',an.PREFIX+'2025/x.json'):
            with self.assertRaises(PermissionError):an.lexical(name)
    def test_09_adopted_epoch_transaction_and_no_replay(self):
        with fixture_dir() as temp:
            root=Path(temp);old=root/'old.sqlite';new=root/'new.sqlite';fixture_old(old)
            before=hashlib.sha256(old.read_bytes()).hexdigest();release={'failed_ancestor_sha256':'a'*64}
            with patch.object(q,'ROOT',root),patch.object(q,'DB',new),patch.object(p,'verify_release',return_value=release),patch.object(an,'OLD_DB','old.sqlite'),patch.object(an,'Guard',return_value=nullcontext()):
                ledger=q.Ledger.initialize(release)
                self.assertEqual(ledger.run_row(an.RUN)['updates'],5228)
                n,nonce=ledger.claim_session();ledger.activate_session(n,nonce);ledger.start_run(an.RUN)
                with self.assertRaises(ValueError):ledger.begin_epoch(an.RUN,1)
                ledger.begin_epoch(an.RUN,2)
                with self.assertRaises(PermissionError):ledger.reserve(an.RUN,1)
                self.assertEqual(ledger.reserve(an.RUN,5229),1)
                with self.assertRaises(sqlite3.IntegrityError):ledger.reserve(an.RUN,5229)
                with self.assertRaises(ValueError):ledger.pause_boundary(n,nonce,{})
                ledger.returned(an.RUN,5229)
                self.assertEqual(ledger.snapshot()['reserved'],75328)
                with self.assertRaises(ValueError):ledger.pause_boundary(n,nonce,{})
                with self.assertRaises(PermissionError):ledger.start_run(p.run_id(*p.ORDER[1]))
                ledger.close()
            self.assertEqual(before,hashlib.sha256(old.read_bytes()).hexdigest())
    def test_10_complete_boundary_pause_before_first_update(self):
        with fixture_dir() as temp:
            root=Path(temp);fixture_old(root/'old.sqlite');release={'failed_ancestor_sha256':'a'*64}
            with patch.object(q,'ROOT',root),patch.object(q,'DB',root/'new.sqlite'),patch.object(p,'verify_release',return_value=release),patch.object(an,'OLD_DB','old.sqlite'),patch.object(an,'Guard',return_value=nullcontext()):
                ledger=q.Ledger.initialize(release);n,nonce=ledger.claim_session();ledger.activate_session(n,nonce)
                ledger.request_pause()
                with self.assertRaises(q.PauseAtBoundary):ledger.start_run(an.RUN)
                r=ledger.pause_boundary(n,nonce,{});self.assertEqual(r['quota']['reserved'],75327);ledger.close()
    def test_11_training_checkpoint_job_algorithms_unchanged(self):
        for file,cls,methods in [('engine.py','Engine',('train','validate')),('checkpoint.py',None,('Store',)),('supervisor.py',None,('main',)),('control.py',None,('start','pause','emergency_stop'))]:
            for name in methods:
                old=ast.dump(node(OLD/file,name,cls),include_attributes=False).replace('phase_b_v2_seed2027_restart_v4','phase_b_v2_seed2027_epoch1_recovery_v1')
                self.assertEqual(old,ast.dump(node(NEW/file,name,cls),include_attributes=False))
        for file in ('resources.py','evaluation.py'):
            self.assertEqual((OLD/file).read_bytes(),(NEW/file).read_bytes())
    def test_12_scope_and_no_heavy_execution(self):
        require_execution_authority(2027)
        for seed in (2028,2026,True,'2027'):
            with self.assertRaises(PermissionError):require_execution_authority(seed)
        self.assertNotIn('torch',sys.modules)
    def test_13_restore_order_is_validate_before_mutation(self):
        fn=node(NEW/'engine.py','run_one','Engine');source=ast.unparse(fn)
        self.assertLess(source.index('load_authorized_epoch1(identity'),source.index('apply_validated_state(model'))
        self.assertIn('first_epoch = 2',source)
        self.assertEqual((NEW/'recovery.py').read_text().count('optimizer.step('),0)

if __name__=='__main__':unittest.main(verbosity=2)
