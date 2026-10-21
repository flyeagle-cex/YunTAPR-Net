"""Reproduce the legacy failure and reject artificial registry escapes."""
from pathlib import Path
from unittest.mock import patch
import json,os,secrets,sys,time,unittest
ROOT=Path(__file__).absolute().parents[2];sys.path.insert(0,str(ROOT/'src'));os.environ['PYTHONPATH']=str(ROOT/'src')
from yuntapr.experimental.phase_b_v2_owner_lifetime_candidate import task_bridge as bridge
from yuntapr.experimental.phase_b_v2_execution_watchdog_candidate.winjob import Job
from yuntapr.experimental.phase_b_v2_stability_review import native

class Tests(unittest.TestCase):
 def test_legacy_job_close_and_fixed_task_scope(self):
  nonce=secrets.token_hex(16)
  with patch.object(bridge,'ps',side_effect=AssertionError('Must reject before OS task access')):
   with self.assertRaises(PermissionError):bridge.start_artificial_owner('YunTAPR_ArtificialOwner_'+nonce,ROOT/'2025',nonce,sys.executable)
  folder=bridge.LOCAL/('artificial_legacy_final_'+nonce);folder.mkdir();job=Job()
  try:
   job.spawn([sys.executable,'-m','yuntapr.experimental.phase_b_v2_owner_lifetime_candidate.fixture','launcher',str(folder),nonce,'legacy'],ROOT)
   deadline=time.monotonic()+5
   while not (folder/'ready.json').exists():
    if time.monotonic()>deadline:raise TimeoutError('ARTIFICIAL_READY_DEADLINE')
    time.sleep(.01)
   owner=json.loads((folder/'owner.json').read_text(encoding='utf-8'));worker=json.loads((folder/'worker.json').read_text(encoding='utf-8'));job.close()
   while any(native.process(p)['status'] not in ('ABSENT','EXITED','PID_REUSED') for p in (owner,worker)):
    if time.monotonic()>deadline:raise TimeoutError('ARTIFICIAL_CLEANUP_DEADLINE')
    time.sleep(.01)
   self.assertFalse((folder/'termination.json').exists());self.assertNotIn('torch',sys.modules)
  finally:job.close()

if __name__=='__main__':unittest.main(verbosity=2)
