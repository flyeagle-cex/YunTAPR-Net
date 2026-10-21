"""Fatal monitor permission faults: exact API phases, no OS/data/model calls."""
from pathlib import Path
from unittest.mock import patch
import ctypes,json,sys,unittest,uuid
ROOT=Path(__file__).absolute().parents[2];sys.path.insert(0,str(ROOT/'src'))
from yuntapr.training.phase_b_v2_seed2027_b1_epoch7_recovery_v4 import protocol as p,monitor as m
class FakeJob:
    def __init__(self):
        self.handles={111:2};self.identities={111:dict(pid=111,creation_filetime=222,image_path_key='a'*64)}
    def bind(self,pid):
        if pid!=111:raise PermissionError('FOREIGN_SYNTHETIC_PID')
        return 2
    def snapshot(self):return []

class Tests(unittest.TestCase):
    def setUp(self):
        self.folder=p.LOCAL/('artificial_monitor_'+uuid.uuid4().hex);self.folder.mkdir();self.job=FakeJob();self.nonce='b'*32
        (self.folder/'worker_identity.json').write_text(json.dumps(dict(**self.job.identities[111],nonce=self.nonce,campaign=p.CAMPAIGN)),encoding='utf-8')
        (self.folder/'paused.json').write_text('{}',encoding='utf-8')
    def run_monitor(self,watch):
        return m.monitor(self.job,self.folder,{'a'*64},self.nonce,1,m.time.monotonic(),m.time.monotonic(),watch)
    def test_snapshot_access_denied_is_fatal_and_named(self):
        watch={}
        with patch.object(self.job,'snapshot',side_effect=ctypes.WinError(5)):
            with self.assertRaises(PermissionError):self.run_monitor(watch)
        self.assertEqual(watch['phase'],'job.snapshot')
    def test_memory_access_denied_is_not_ignored(self):
        watch={}
        with patch.object(m,'exited',return_value=False),patch.object(m,'memory',side_effect=ctypes.WinError(5)):
            with self.assertRaises(PermissionError):self.run_monitor(watch)
        self.assertEqual(watch['phase'],'GetProcessMemoryInfo');self.assertEqual(watch['process_identity'],self.job.identities[111])
    def test_host_access_denied_still_stops(self):
        watch={}
        with patch.object(m,'exited',return_value=True),patch.object(m,'host_admission',side_effect=ctypes.WinError(5)):
            with self.assertRaises(PermissionError):self.run_monitor(watch)
        self.assertEqual(watch['phase'],'host_admission')
    def test_exit_code_access_denied_still_stops(self):
        watch={}
        with patch.object(m,'exited',return_value=True),patch.object(m,'host_admission',return_value={}),patch.object(m,'code',side_effect=ctypes.WinError(5)):
            with self.assertRaises(PermissionError):self.run_monitor(watch)
        self.assertEqual(watch['phase'],'GetExitCodeProcess')
    def test_valid_pause_returns_without_retry_or_torch(self):
        watch={};receipt=dict(nonce=self.nonce,campaign=p.CAMPAIGN,session=1,status='PAUSED_VERIFIED')
        with patch.object(m,'exited',return_value=True),patch.object(m,'host_admission',return_value={}),patch.object(m,'code',return_value=0),patch.object(m,'owned_json',return_value=receipt):
            self.run_monitor(watch)
        self.assertTrue(watch['paused']);self.assertFalse(watch['success']);self.assertNotIn('torch',sys.modules)
if __name__=='__main__':unittest.main(verbosity=2)
