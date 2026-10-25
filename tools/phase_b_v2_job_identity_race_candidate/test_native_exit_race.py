"""Small artificial processes and injected identity faults; zero training."""
from pathlib import Path
from unittest.mock import patch
import ctypes as C
from ctypes import wintypes as W
import json,sys,time,unittest
ROOT=Path(__file__).absolute().parents[2];sys.path.insert(0,str(ROOT/'src'))
from yuntapr.experimental.phase_b_v2_job_identity_race_candidate import job as candidate
from yuntapr.experimental.phase_b_v2_execution_watchdog_candidate.winjob import (
    K,bind,checked,exited,close_handle,native_identity)

terminate=bind(K,'TerminateProcess',[W.HANDLE,W.UINT],W.BOOL)
RECORDS=[]

def wait_exit(handle):
    end=time.monotonic()+3
    while not exited(handle):
        if time.monotonic()>=end:raise TimeoutError('BOUNDED_ARTIFICIAL_PROCESS_EXIT')
        time.sleep(.01)

class Tests(unittest.TestCase):
    def setUp(self):
        self.job=candidate.IdentitySafeJob()
        self.pid=self.job.spawn([sys.executable,'-c','import time;time.sleep(8)'],ROOT)
        self.held=self.job.handles.pop(self.pid)
        self.identity=self.job.identities.pop(self.pid)
    def tearDown(self):
        self.job.stop();wait_exit(self.held)
        self.job.close();close_handle(self.held)
    def test_01_live_owned_access_denied_stays_fatal(self):
        with patch.object(candidate,'native_identity',side_effect=C.WinError(5)):
            with self.assertRaises(PermissionError) as error:self.job.bind(self.pid)
        self.assertFalse(exited(self.held));self.assertEqual(error.exception.identity_exit_status,'NATIVE_HANDLE_NOT_SIGNALED')
        self.assertEqual(self.job.identity_exit_receipts,[])
    def test_02_same_handle_exit_after_membership_has_precise_receipt(self):
        def exited_image_query(handle):
            checked(terminate(self.held,99));wait_exit(self.held)
            try:native_identity(handle);actual='IMAGE_STILL_AVAILABLE'
            except OSError as exc:actual='WINERROR_'+str(exc.winerror)
            RECORDS.append(dict(actual_post_exit_native_image_result=actual))
            raise C.WinError(5)
        with patch.object(candidate,'native_identity',side_effect=exited_image_query):
            with self.assertRaises(candidate.ExitedOwnedMember) as found:self.job.bind(self.pid)
        self.assertTrue(found.exception.receipt['retained_handle_signaled'])
        self.assertTrue(found.exception.receipt['owned_job_membership_verified'])
        self.assertEqual(len(self.job.identity_exit_receipts),1)
    def test_03_snapshot_tolerates_only_proven_exited_still_listed_member(self):
        def exited_image_query(handle):
            checked(terminate(self.held,99));wait_exit(self.held);raise C.WinError(5)
        with patch.object(self.job,'pids',return_value=[self.pid]),patch.object(candidate,'native_identity',side_effect=exited_image_query):
            self.assertEqual(self.job.snapshot(),[self.pid])
        self.assertEqual(len(self.job.identity_exit_receipts),1)
    def test_04_unknown_wait_status_is_not_ignored(self):
        with patch.object(candidate,'native_identity',side_effect=C.WinError(5)),patch.object(candidate,'exited',side_effect=C.WinError(6)):
            with self.assertRaises(OSError):self.job.bind(self.pid)
        self.assertEqual(self.job.identity_exit_receipts,[])
    def test_05_foreign_owned_test_process_is_never_bound_or_killed(self):
        other=candidate.IdentitySafeJob();pid=other.spawn([sys.executable,'-c','import time;time.sleep(8)'],ROOT)
        try:
            with self.assertRaises(PermissionError):self.job.bind(pid)
            self.assertFalse(exited(other.root));self.assertEqual(other.identity_exit_receipts,[])
        finally:other.stop();wait_exit(other.root);other.close()
    def test_06_normal_identity_stays_exact(self):
        handle=self.job.bind(self.pid)
        self.assertEqual(native_identity(handle),self.identity)
        self.assertEqual(self.job.identity_exit_receipts,[])

class EnumerationTests(unittest.TestCase):
    def setUp(self):
        self.job=candidate.IdentitySafeJob()
    def tearDown(self):self.job.close()
    @staticmethod
    def query(rows):
        rows=iter(rows)
        def fake(handle,kind,buffer,size,returned):
            assigned,count,ids,ok,error=next(rows)
            row=C.cast(buffer,C.POINTER(candidate.W.DWORD))
            row[0]=assigned;row[1]=count
            values=C.cast(C.addressof(buffer._obj)+8,C.POINTER(candidate.SIZE))
            for i,pid in enumerate(ids):values[i]=pid
            C.set_last_error(error);return ok
        return fake
    def test_07_partial_is_requeried_not_returned(self):
        with patch.object(candidate,'query_job',side_effect=self.query([(2,1,[10],1,0),(2,2,[10,11],1,0)])):
            self.assertEqual(self.job.pids(),[10,11])
        self.assertEqual(len(self.job.enumeration_resize_receipts),1)
    def test_08_partial_never_becomes_false_empty(self):
        with patch.object(candidate,'query_job',side_effect=self.query([(1,0,[],1,0)]*3)) as call:
            with self.assertRaisesRegex(RuntimeError,'THREE_BOUNDED'):self.job.pids()
        self.assertEqual(call.call_count,3)
    def test_09_active_count_limit_stays_fatal(self):
        with patch.object(candidate,'query_job',side_effect=self.query([(17,17,list(range(1,18)),1,0)])):
            with self.assertRaisesRegex(RuntimeError,'INVALID_JOB_COUNTS'):self.job.pids()
    def test_10_access_denied_is_not_retried(self):
        with patch.object(candidate,'query_job',side_effect=self.query([(0,0,[],0,5)])) as call:
            with self.assertRaises(PermissionError):self.job.pids()
        self.assertEqual(call.call_count,1)
    def test_11_duplicate_pid_is_fatal(self):
        with patch.object(candidate,'query_job',side_effect=self.query([(2,2,[11,11],1,0)])):
            with self.assertRaisesRegex(RuntimeError,'INVALID_NATIVE_JOB_PID_LIST'):self.job.pids()
    def test_12_documented_insufficient_buffer_grows_within_bound(self):
        with patch.object(candidate,'query_job',side_effect=self.query([(4,1,[11],0,234),(1,1,[11],1,0)])):
            self.assertEqual(self.job.pids(),[11])
        self.assertEqual(self.job.enumeration_resize_receipts[0]['capacity'],32)

if __name__=='__main__':
    suite=unittest.TestSuite([unittest.defaultTestLoader.loadTestsFromTestCase(cls) for cls in (Tests,EnumerationTests)])
    result=unittest.TextTestRunner(verbosity=2).run(suite)
    print(json.dumps(dict(tests_run=result.testsRun,failures=len(result.failures),errors=len(result.errors),records=RECORDS,
        synthetic_only=True,new_optimizer_steps=0,real_raw_data_reads=0,torch_imported='torch' in sys.modules)))
    raise SystemExit(not result.wasSuccessful())
