"""Only the new numeric control, offline decomposition and block resampling."""
import copy
import importlib.util
import inspect
from pathlib import Path
import unittest
import numpy as np
import torch
from yuntapr.contracts.loader import REPO_ROOT
from yuntapr.experimental.core_innovation.grid import GridSpec
from yuntapr.experimental.core_innovation.stage2.fusion import paired_fusion_candidates
from yuntapr.experimental.research_readiness.dynamic_terrain import PhysicalDote
from yuntapr.experimental.research_readiness.dynamic_training import run_task
from yuntapr.experimental.research_readiness.dote_numeric_control import ZeroNumericDote
from yuntapr.experimental.research_readiness.scientific_diagnostics import binned_brier,paired_week_bootstrap


class AttributionTests(unittest.TestCase):
    def test_zero_values_preserve_every_real_validity_bit_and_input(self):
        x=np.ones((8,100,100),np.float32);m=np.ones_like(x,bool);m[0,3,4]=False;x[0,3,4]=np.nan
        control=object.__new__(ZeroNumericDote);control.physical=lambda frame:(x,m)
        y,v=control(None)
        self.assertTrue(np.isnan(x[0,3,4]));self.assertFalse(y.any());np.testing.assert_array_equal(v,m)
        v[1,3,4]=False;self.assertTrue(m[1,3,4])
    def test_default_dynamic_path_is_still_the_frozen_physical_transform(self):
        self.assertIs(inspect.signature(run_task).parameters['dynamic_transform_factory'].default,PhysicalDote)
    def fusion(self):
        a,_=paired_fusion_candidates(feature_channels=[48],gfs_channels=[26],terrain_channels=[28],projection_width=16,modulation_limit=.1)
        grid=GridSpec([25.,25.1,25.2],[101.,101.1,101.2]);mask=[torch.ones(1,1,3,3,dtype=torch.bool)]
        f=torch.randn(1,48,3,3);g=torch.randn(1,26,3,3);t=torch.randn(1,28,3,3)
        def call(t):return a([f],[g],[t],mask,mask,mask,feature_grids=[grid],gfs_grids=[grid],terrain_grids=[grid]).values[0]
        return a,f,t,call
    def test_initial_identity_holds_for_real_and_zero_numeric_condition(self):
        a,f,t,call=self.fusion();zero=t.clone();zero[:,12:20]=0
        self.assertTrue(torch.equal(call(t),f));self.assertTrue(torch.equal(call(zero),f))
    def test_128_weights_have_zero_loss_gradient_not_equal_effective_capacity(self):
        a,f,t,call=self.fusion();t[:,12:20]=0
        with torch.no_grad():a.fuse[0].weight.fill_(.001)
        call(t).square().sum().backward();grad=a.terrain[0].weight.grad
        self.assertEqual(grad[:,12:20].numel(),128);self.assertEqual(torch.count_nonzero(grad[:,12:20]).item(),0)
        self.assertGreater(torch.count_nonzero(grad[:,:12]).item(),0);self.assertGreater(torch.count_nonzero(grad[:,20:]).item(),0)
    def test_binned_murphy_is_not_mislabelled_exact_original_score_calibration(self):
        p=np.array([.11,.19,.61,.69]);y=np.array([0,1,0,1]);bins=[]
        for i in range(10):
            m=(p>=i/10)&(p<(i+1)/10);bins.append(dict(n=int(m.sum()),rain=int(y[m].sum()),probability_sum=float(p[m].sum())))
        r=binned_brier(4,2,float(np.mean((p-y)**2)),bins)
        self.assertAlmostEqual(r['binned_mean_forecast_brier'],r['binned_reliability']-r['binned_resolution']+r['uncertainty'])
        self.assertNotEqual(r['binning_residual'],0);self.assertIn('NOT_AVAILABLE',r['exact_original_score_reliability'])
    def test_block_resampling_keeps_all_seeds_paired_and_rank_pooling_exact(self):
        b=dict(n_valid=2,n_rain=1,brier_sum=.08,s_qr=.2,covered=[1]*32)
        a=dict(blocks=[copy.deepcopy(b) for _ in range(35)],pos=np.tile([1,0],(35,1)),neg=np.tile([0,1],(35,1)))
        arms={str(s):dict(B7=copy.deepcopy(a),B8=copy.deepcopy(a)) for s in (2029,2030,2031)}
        r=paired_week_bootstrap(arms,repetitions=25)
        self.assertEqual(r['blocks'],35)
        for v in r['metrics'].values():self.assertEqual(v['point_estimate'],0);self.assertEqual(v['percentile_interval_95'],[0,0])
    def test_no_new_grant_or_wrong_task_is_rejected_before_execution(self):
        file=REPO_ROOT/'tools/research_readiness/start_dote_numeric_control.py';spec=importlib.util.spec_from_file_location('control_launch',file)
        m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
        p=dict(execution_code_commit='c'*40,tasks=[dict(model='B7_ZERO_DOTE',seed=2029)],scientific_choices={},budget={})
        p['proposal_sha256']=m.digest(p);private={'output_root':'SYNTHETIC_ONLY'}
        grant=dict(approved_by_researcher=True,decision_id='SYNTHETIC',code_commit='c'*40,proposal_sha256=p['proposal_sha256'],
                   tasks=p['tasks'],scientific_choices={},budget={},output_root=private['output_root'])
        m.validate(grant,p,private,'c'*40)
        for changed in [dict(approved_by_researcher=False),dict(code_commit='d'*40),dict(tasks=[dict(model='B7',seed=2029)]),dict(budget={'replay':1})]:
            with self.assertRaises(PermissionError):m.validate(dict(grant,**changed),p,private,'c'*40)


if __name__=='__main__':unittest.main()
