"""Only artificial status files/processes; no torch, raw data or optimizer."""
from pathlib import Path
from unittest.mock import patch
import ast,importlib.util,json,os,subprocess,sys,time,unittest,uuid
ROOT=Path(__file__).absolute().parents[2];sys.path.insert(0,str(ROOT/'src'))
from yuntapr.training.phase_b_v2_seed2027_epoch2_recovery_v2 import protocol as p,control,ancestor as anc
from yuntapr.experimental.phase_b_v2_status_snapshot_io.reader import read_json_snapshot

def monitor():
    spec=importlib.util.spec_from_file_location('new_monitor',ROOT/'scripts/phase_b_v2_live_monitor_epoch2_v2/server.py')
    m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m

class Tests(unittest.TestCase):
    def setUp(self):
        self.folder=p.LOCAL/('synthetic_status_'+uuid.uuid4().hex);self.folder.mkdir()

    def test_mutable_writer_and_monitor_share_actual_mutex(self):
        m=monitor()
        for name in ('heartbeat.json','progress.json','execution_status.json'):
            path=self.folder/name;p.atomic_json(path,dict(n=0,artificial=True))
            self.assertEqual(m.read_json(path),dict(n=0,artificial=True))
            p.atomic_json(path,dict(n=1,artificial=True))
            self.assertEqual(read_json_snapshot(path,p.OUT)['n'],1)
            self.assertFalse(path.with_name(path.name+'.part').exists())

    def test_cross_process_actual_monitor_during_120_replacements(self):
        path=self.folder/'heartbeat.json';p.atomic_json(path,dict(n=0,artificial=True))
        code="""
import importlib.util,json,sys,time
from pathlib import Path
root=Path.cwd();sys.path.insert(0,str(root/'src'))
spec=importlib.util.spec_from_file_location('monitor',root/'scripts/phase_b_v2_live_monitor_epoch2_v2/server.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
path=Path(sys.argv[1]);last=-1
for _ in range(160):
 row=m.read_json(path)
 assert row['artificial'] is True and row['n']>=last
 last=row['n'];time.sleep(.003)
print(json.dumps(dict(reads=160,last=last)))
"""
        child=subprocess.Popen([sys.executable,'-c',code,str(path)],cwd=ROOT,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
        try:
            for n in range(1,121):p.atomic_json(path,dict(n=n,artificial=True));time.sleep(.002)
            stdout,stderr=child.communicate(timeout=10)
            self.assertEqual(child.returncode,0,stderr);self.assertEqual(json.loads(stdout)['reads'],160)
            self.assertEqual(read_json_snapshot(path,p.OUT)['n'],120)
        finally:
            if child.poll() is None:child.kill();child.wait(timeout=5)

    def test_control_status_routes_heartbeat_to_mutex(self):
        path=self.folder/'heartbeat.json';p.atomic_json(path,dict(artificial=True))
        class Con:
            def __enter__(self):return self
            def __exit__(self,*args):pass
            def execute(self,sql):
                if 'status,reason' in sql:self.rows=[('ACTIVE',None)]
                elif 'GROUP BY status' in sql:self.rows=[]
                elif 'n,status FROM sessions' in sql:self.rows=[(1,'ACTIVE')]
                elif 'pause_requested' in sql:self.rows=[(0,)]
                else:self.rows=[]
                return self
            def fetchone(self):return self.rows[0] if self.rows else None
            def __iter__(self):return iter(self.rows)
        class Existing:
            def exists(self):return True
        with patch.object(control,'DB',Existing()),patch.object(control,'ro',return_value=Con()),patch.object(control,'session_root',return_value=self.folder):
            row=control.status();self.assertEqual(row['heartbeat'],dict(artificial=True))

    def test_immutable_writer_still_exclusive_no_overwrite_of_part(self):
        path=self.folder/'receipt.json';p.atomic_json(path,dict(n=0))
        part=path.with_name(path.name+'.part');part.write_text('evidence',encoding='utf-8')
        with self.assertRaises(FileExistsError):p.atomic_json(path,dict(n=1))
        self.assertEqual(json.loads(path.read_text(encoding='utf-8')),dict(n=0));self.assertEqual(part.read_text(encoding='utf-8'),'evidence')

    def test_failed_part_is_registered_as_evidence_not_new_last(self):
        self.assertIn(anc.FAILED_PREFIX+'.local/sessions/session_0001/heartbeat.json.part',anc.REGISTERED)
        self.assertNotEqual(anc.FAILED_DB,anc.SOURCE_DB)
        self.assertIn('epoch1_recovery_v2',anc.SOURCE_DB)
        self.assertNotIn('torch',sys.modules)

    def test_static_immutable_science_and_no_retry_loop(self):
        old=ROOT/'src/yuntapr/training/phase_b_v2_seed2027_epoch2_recovery_v1'
        new=old.with_name('phase_b_v2_seed2027_epoch2_recovery_v2')
        for name in ('resources.py','evaluation.py','evidence.py'):
            self.assertEqual((old/name).read_bytes(),(new/name).read_bytes())
        atomic=next(x for x in ast.parse((new/'protocol.py').read_text(encoding='utf-8')).body if getattr(x,'name',None)=='atomic_json')
        self.assertFalse(any(isinstance(x,(ast.For,ast.While,ast.Try)) for x in ast.walk(atomic)))

if __name__=='__main__':unittest.main(verbosity=2)
