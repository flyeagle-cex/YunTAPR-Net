"""Windows artificial JSON only: no training, model, raw data or checkpoint."""
from pathlib import Path
from unittest.mock import patch
import json,os,subprocess,sys,threading,unittest,uuid
ROOT=Path(__file__).absolute().parents[2];sys.path.insert(0,str(ROOT/'src'))
from yuntapr.experimental.phase_b_v2_status_snapshot_io import reader as r
from yuntapr.training.phase_b_v2_seed2027_epoch2_recovery_v1.protocol import atomic_json

BASE=ROOT/'docs/phase_b_v2_status_snapshot_io_remediation/v1/.local'
BASE.mkdir(parents=True,exist_ok=True)

class Tests(unittest.TestCase):
    def setUp(self):
        self.root=BASE/uuid.uuid4().hex;self.root.mkdir();self.path=self.root/'heartbeat.json';atomic_json(self.path,dict(n=0,copy=0))
    def test_01_reproduce_builtin_reader_replace_denial(self):
        with self.path.open('rb') as old:
            with self.assertRaises(PermissionError):atomic_json(self.path,dict(n=1,copy=1))
            self.assertEqual(json.load(old)['n'],0)
    def test_02_writer_waits_until_snapshot_closes(self):
        started=threading.Event();done=threading.Event();errors=[]
        def writer():
            started.set()
            try:r.atomic_status_json(self.path,dict(n=1,copy=1),self.root)
            except BaseException as exc:errors.append(exc)
            finally:done.set()
        with r.open_snapshot(self.path,self.root) as (old,h,before):
            t=threading.Thread(target=writer);t.start();self.assertTrue(started.wait(1));self.assertFalse(done.wait(.03))
            self.assertEqual(json.loads(r.read_exact(old,before['size']))['n'],0)
        t.join(timeout=3);self.assertFalse(t.is_alive());self.assertFalse(errors)
        self.assertEqual(r.read_json_snapshot(self.path,self.root)['n'],1)
    def test_03_concurrent_replacement_coherent(self):
        errors=[]
        def writer():
            try:
                for n in range(1,81):r.atomic_status_json(self.path,dict(n=n,copy=n),self.root)
            except BaseException as exc:errors.append(exc)
        t=threading.Thread(target=writer);t.start()
        for _ in range(160):
            obj=r.read_json_snapshot(self.path,self.root);self.assertEqual(obj['n'],obj['copy'])
        t.join(timeout=5);self.assertFalse(t.is_alive());self.assertFalse(errors)
        self.assertEqual(r.read_json_snapshot(self.path,self.root)['n'],80)
    def test_04_lexical_before_native(self):
        with patch.object(r.K,'CreateFileW') as create:
            for path in (self.root/'2025.json',self.root/'..'/'x.json',self.root/'x.pt',self.root.parent/'x.json'):
                with self.assertRaises(PermissionError):r.read_json_snapshot(path,self.root)
            create.assert_not_called()
    def test_05_bound_and_bad_json(self):
        with self.assertRaises(ValueError):r.read_json_snapshot(self.path,self.root,2)
        self.path.write_bytes(b'{broken}')
        with self.assertRaises(ValueError):r.read_json_snapshot(self.path,self.root)
    def test_06_lock_timeout_has_no_partial_write(self):
        ready=threading.Event();release=threading.Event()
        def holder():
            with r.serialized_status(self.path,self.root):ready.set();release.wait(2)
        t=threading.Thread(target=holder);t.start();self.assertTrue(ready.wait(1))
        try:
            with self.assertRaises(TimeoutError):r.atomic_status_json(self.path,{'n':1},self.root,timeout_ms=20)
            self.assertFalse(self.path.with_name('heartbeat.json.part').exists())
        finally:release.set();t.join(timeout=3)
    def test_07_nonfinite_duplicate_rejected(self):
        for data in (b'{"n":NaN}',b'{"n":1e999}',b'{"n":1,"n":2}'):
            self.path.write_bytes(data)
            with self.assertRaises(ValueError):r.read_json_snapshot(self.path,self.root)
    def test_08_strict_data_handle_not_weakened(self):
        with r.ReadHandle(str(self.path),payload=True):
            with self.assertRaises(PermissionError):atomic_json(self.path,dict(n=1,copy=1))
        self.assertNotIn('torch',sys.modules)
    def test_09_cross_process_reader_and_writer(self):
        code="""import sys
from pathlib import Path
sys.path.insert(0,sys.argv[1])
from yuntapr.experimental.phase_b_v2_status_snapshot_io.reader import open_snapshot
with open_snapshot(Path(sys.argv[2]),Path(sys.argv[3])):
 print('READY',flush=True)
 sys.stdin.readline()
"""
        child=subprocess.Popen([sys.executable,'-c',code,str(ROOT/'src'),str(self.path),str(self.root)],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,creationflags=subprocess.CREATE_NO_WINDOW)
        done=threading.Event();errors=[]
        def writer():
            try:r.atomic_status_json(self.path,dict(n=9,copy=9),self.root)
            except BaseException as exc:errors.append(exc)
            finally:done.set()
        try:
            self.assertEqual(child.stdout.readline().strip(),'READY')
            t=threading.Thread(target=writer);t.start();self.assertFalse(done.wait(.03))
            _,err=child.communicate(input='release\n',timeout=5)
            t.join(timeout=3);self.assertFalse(t.is_alive());self.assertFalse(errors);self.assertEqual(child.returncode,0,err)
            self.assertEqual(r.read_json_snapshot(self.path,self.root)['n'],9)
        finally:
            if child.poll() is None:child.kill();child.communicate(timeout=3)

if __name__=='__main__':unittest.main(verbosity=2)
