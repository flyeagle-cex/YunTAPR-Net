"""Read-only monitor deltas, artificial metadata only."""
from pathlib import Path
from unittest.mock import patch
import importlib.util,json,sys,unittest,uuid
spec=importlib.util.spec_from_file_location('monitor',Path(__file__).with_name('server.py'))
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)

class Tests(unittest.TestCase):
    def test_01_active_ledger_with_dead_worker_is_not_running(self):
        probes=dict(owner=dict(status='ABSENT'),worker=dict(status='ABSENT'),job=dict(status='ABSENT',pids=[]))
        self.assertEqual(m.derive('ACTIVE',probes),'STOPPED_UNCLEAN')
    def test_02_exact_live_tree(self):
        probes=dict(owner=dict(status='LIVE_MATCH'),worker=dict(status='LIVE_MATCH'),job=dict(status='PRESENT',pids=[99]))
        self.assertEqual(m.derive('ACTIVE',probes),'RUNNING')
        probes['worker']['status']='PID_REUSED'
        self.assertNotEqual(m.derive('ACTIVE',probes),'RUNNING')
    def test_03_unknown_not_pass(self):
        probes=dict(owner=dict(status='UNKNOWN'),worker=dict(status='ABSENT'),job=dict(status='ABSENT',pids=[]))
        self.assertEqual(m.derive('ACTIVE',probes),'PROCESS_NOT_VERIFIED')
    def test_04_not_started_and_paused(self):
        self.assertEqual(m.derive('NOT_STARTED',None),'NOT_STARTED')
        self.assertEqual(m.derive('PAUSED',None),'PAUSED')
    def test_05_tail_drops_incomplete_last_line(self):
        root=m.LOCAL/('monitor_test_'+uuid.uuid4().hex);root.mkdir()
        path=root/'test.jsonl';path.write_bytes(b'{"event":"STEP_RETURNED","utc":"test","update":1}\n{"event":')
        self.assertEqual(m.tail_events(path),[dict(event='STEP_RETURNED',utc='test',update=1)])
    def test_06_read_bound_and_fixed_path(self):
        with self.assertRaises(PermissionError):m.read_json(m.ROOT/'2025'/'x.json')
        root=m.LOCAL/('monitor_test_'+uuid.uuid4().hex);root.mkdir();path=root/'test.json';path.write_text('{"value":100}')
        with self.assertRaises(ValueError):m.read_json(path,3)
    def test_07_readonly_no_torch_no_mutating_http(self):
        self.assertNotIn('torch',sys.modules)
        self.assertFalse(hasattr(m.Handler,'do_POST'));self.assertFalse(hasattr(m.Handler,'do_PUT'))
        self.assertEqual(m.APP_ID,'YUNTAPR_READONLY_LIVE_SEED2027_EPOCH1_V1')
if __name__=='__main__':unittest.main(verbosity=2)
