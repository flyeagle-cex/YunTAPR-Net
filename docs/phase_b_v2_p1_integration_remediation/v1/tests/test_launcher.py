"""Only new integrated artificial launch routes; no PyTorch import."""
import json
from pathlib import Path
import sqlite3
import sys
import unittest
from unittest.mock import patch
from yuntapr.experimental.phase_b_v2_p1_integration_candidate import launcher as L

RESULTS=[]


class LauncherTests(unittest.TestCase):
    def case(self,name,violation):
        row=L.run(name);RESULTS.append(row)
        self.assertTrue(row['job_empty_and_handles_signaled'])
        self.assertLess(row['elapsed_seconds'],15)
        self.assertEqual(row['violation'],violation)
        self.assertEqual(row['restarts'],0);self.assertEqual(row['refunds'],0)
        self.assertTrue(row['source_sha'])
        self.assertNotIn('torch',sys.modules)
        return row

    def test_normal(self):
        row=self.case('normal',None)
        self.assertNotEqual(row['root_pid'],row['worker_identity']['pid']) # real venv stub
    def test_wrapper_early_exit(self):
        row=self.case('wrapper_exit',None)
        self.assertTrue(row['root_exited_during_monitor'])
    def test_before_identity_exit(self): self.case('exit_before','EXIT_BEFORE_IDENTITY')
    def test_unexpected_exit(self): self.case('unexpected_exit','WORKER_UNEXPECTED_EXIT')
    def test_memory_limit(self):
        row=self.case('memory','MEMORY_LIMIT')
        self.assertGreater(row['peak_process_working_set_bytes'],24*1024**2)
    def test_cpu_limit(self): self.case('cpu','CPU_TIME_LIMIT')
    def test_tree_timeout(self):
        row=self.case('timeout_tree','ELAPSED_LIMIT')
        self.assertGreaterEqual(len(row['observed_native_identities']),3)
    def test_foreign_monitor_pid_is_not_terminated(self):
        self.case('foreign_pid','IDENTITY_OR_MONITOR_FAILURE')
        self.assertGreater(L.os.getpid(),0) # this external monitor remains alive
    def test_creation_mismatch(self): self.case('wrong_creation','IDENTITY_OR_MONITOR_FAILURE')
    def test_executable_mismatch(self): self.case('wrong_image','IDENTITY_OR_MONITOR_FAILURE')
    def test_nonce_mismatch(self): self.case('wrong_nonce','IDENTITY_OR_MONITOR_FAILURE')
    def test_missing_pid(self): self.case('missing_pid','IDENTITY_OR_MONITOR_FAILURE')
    def test_invalid_handle(self): self.case('invalid_handle','IDENTITY_OR_MONITOR_FAILURE')
    def test_monitor_abrupt_exit_kills_inner_job(self):
        row=self.case('monitor_exit','WORKER_UNEXPECTED_EXIT')
        self.assertIs(row['inner_cleanup_before_outer_stop'],True)
    def test_reject_arbitrary_argv_and_approval_without_spawn(self):
        with patch.object(L.Job,'spawn',side_effect=AssertionError('No spawn')):
            for value in ('APPROVED','train','--approved',{'APPROVED':True},['python','train.py']):
                with self.assertRaises(ValueError):L.run(value)


if __name__=='__main__':
    suite=unittest.defaultTestLoader.loadTestsFromTestCase(LauncherTests)
    result=unittest.TextTestRunner(verbosity=2).run(suite)
    out=L.ROOT/'docs/phase_b_v2_p1_integration_remediation/v1/tests'
    # Exclusive, versioned results preserve first failure; no retries inside cases.
    tag='initial' if not (out/'job_initial.json').exists() else 'repair'
    rows=dict(tests=result.testsRun,failures=len(result.failures),errors=len(result.errors),results=RESULTS)
    L.persist(out/('job_'+tag+'.json'),rows)
    with sqlite3.connect((L.LOCAL/'launch_campaign.sqlite').as_uri()+'?mode=ro',uri=True) as con:
        print('Nonrefundable launch reservations:',con.execute('SELECT COUNT(*) FROM attempts').fetchone()[0])
    raise SystemExit(not result.wasSuccessful())
