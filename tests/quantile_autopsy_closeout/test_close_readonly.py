"""Pure saved-evidence fixtures; zero model/optimizer/raw/checkpoint operations."""
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'scripts'))
import copy
import math
import subprocess
import unittest
from unittest.mock import patch
from quantile_autopsy_v1 import close_readonly as close
from quantile_autopsy_v1 import common as c

def terminal():
    return {'status':'REPRODUCTION_FAILURE','error_type':'PermissionError','error':close.GUARD_ERROR,
        'traceback':"'immutable_history':c.verify_snapshot(run)",
        'counts':{'ENGINEERING_OPTIMIZER_STEPS':8625,'ENGINEERING_BACKWARD_CALLS':8625,
            'ENGINEERING_FORWARD_CALLS':8626,'FORMAL_OPTIMIZER_STEPS_ADDED':0,'FORMAL_OPTIMIZER_STEPS':50537,
            '2025_RAW_ACCESS':0,'2025_PIXELS_READ':0,'B1_PHASE_B_STARTED':False},
        'exact_matches':{k:8625 for k in close.KEYS}}

def failure_fixture():
    q=[math.log1p(.1)+23*(i+1) for i in range(32)]
    values={k:list(q) for k in ('qlog_per_tau_max','qlog_per_tau_median','increments_per_tau_max','increments_per_tau_mean','raw_per_tau_max')}
    fail={'captured_before_expm1':True,'update':41914,'qlog_dtype':'torch.float64',
        'qlog_all_finite':True,'raw_all_finite':True,'qphysical_nonfinite_count':1,'qlog_max':q[-1],
        'sample_identities':[{'sample_id':'c'},{'sample_id':'d'}],'qlog_32_at_pixel':q,
        'increments_32_at_pixel':[23.]*32,'raw_32_at_pixel':[23.]*32,'target_feature_48_at_pixel':[1.]*48,
        'observation':values}
    row={'status':'EXPECTED_FORWARD_OVERFLOW','update':41914,'sample_ids':['c','d'],
         'qphysical_nonfinite_count':1,'qlog':{'max':q[-1]},**values}
    return fail,row

class ReadOnlyClosureTests(unittest.TestCase):
    def test_known_closeout_is_separate_from_numerical_failure(self):
        before=terminal();saved=copy.deepcopy(before)
        self.assertEqual(close.check_terminal(before)['ENGINEERING_OPTIMIZER_STEPS'],8625)
        self.assertEqual(before,saved)
    def test_numeric_mismatch_cannot_be_relabelled(self):
        t=terminal();t['error_type']='ValueError';t['error']='REPRODUCTION_FAILURE: loss mismatch'
        with self.assertRaises(ValueError):close.check_terminal(t)
    def test_incomplete_trajectory_rejected(self):
        t=terminal();t['counts']['ENGINEERING_OPTIMIZER_STEPS']=8624
        with self.assertRaises(ValueError):close.check_terminal(t)
    def test_missing_match_count_rejected(self):
        t=terminal();del t['exact_matches']['loss']
        with self.assertRaises(ValueError):close.check_terminal(t)
    def test_formal_step_increment_rejected(self):
        t=terminal();t['counts']['FORMAL_OPTIMIZER_STEPS_ADDED']=1
        with self.assertRaises(ValueError):close.check_terminal(t)
    def test_valid_observed_overflow(self):
        f,r=failure_fixture()
        with patch.object(c,'FAIL_BATCH',2):self.assertTrue(close.check_failure(f,r))
    def test_no_physical_overflow_rejected(self):
        f,r=failure_fixture();f['qphysical_nonfinite_count']=0
        with patch.object(c,'FAIL_BATCH',2),self.assertRaises(ValueError):close.check_failure(f,r)
    def test_log_nonfinite_rejected(self):
        f,r=failure_fixture();f['qlog_all_finite']=False
        with patch.object(c,'FAIL_BATCH',2),self.assertRaises(ValueError):close.check_failure(f,r)
    def test_local_vector_loss_rejected(self):
        f,r=failure_fixture();f['qlog_32_at_pixel'].pop()
        with patch.object(c,'FAIL_BATCH',2),self.assertRaises(ValueError):close.check_failure(f,r)
    def test_extra_update_rejected(self):
        f,r=failure_fixture()
        good={'status':'SUCCESS_EXACT_MATCH','sample_ids':['a','b'],'update':41913,'LR':1e-4,'loss':.1,
              'actual_denominator':6860,'pre_clip_norm':.2,'post_clip_norm':.2,'clipped':False}
        with patch.object(c,'SUCCESS',1),patch.object(c,'FAIL_BATCH',2),self.assertRaises(ValueError):
            close.replay_rows([good,r,good],[good],f)
    def test_no_torch_imported(self):
        # A full regression suite may already have imported torch elsewhere.
        # Verify this read-only module in its own clean process instead.
        program="import sys;sys.path.insert(0,"+repr(str(ROOT/'scripts'))+");from quantile_autopsy_v1 import close_readonly;assert 'torch' not in sys.modules"
        result=subprocess.run([sys.executable,'-c',program],capture_output=True,text=True,timeout=10)
        self.assertEqual(result.returncode,0,result.stderr)

if __name__=='__main__':unittest.main()
