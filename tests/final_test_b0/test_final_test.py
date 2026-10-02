from copy import deepcopy
from datetime import timedelta
import json
import math
import os
from pathlib import Path
import tempfile
import shutil
import uuid
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import numpy as np
import torch

from yuntapr.contracts.loader import REPO_ROOT,sha256
from yuntapr.evaluation import final_test_b0 as f
from yuntapr.spatial.sp04_mapping import load_sp04
from yuntapr.training.phase_a_validation import grouped_occurrence_metrics
from yuntapr.training.scientific_review import diagnostic_rules


def row(start=f.START):
    nominal=start+timedelta(minutes=20)
    return {'sample_id':start.isoformat(),'window_start':start.isoformat(),
        'analysis_time':(start+timedelta(minutes=30)).isoformat(),'expected_nominal':nominal.isoformat(),
        'selected_nominal':nominal.isoformat(),'obs_start':nominal.isoformat(),
        'obs_end':(start+timedelta(minutes=29)).isoformat(),'date_created':'',
        'b13_relative_path':nominal.strftime('%Y%m\\%d\\NC_H09_%Y%m%d_%H%M_R21_FLDK.06001_06001.nc'),
        'imerg_day_path':str(f.IROOT/'2025'/('imerg_'+start.strftime('%Y%m%d')+'.nc')),
        'expected_latest_available':'True','b13_readable':'True','b13_finite':'True','b13_metadata_valid':'True',
        'used_older_causal_frame':'False','full_valid_native_pixels':'251001',
        'imerg_product':'IMERG','imerg_version':'V07','imerg_run_type':'Final','imerg_time_grid_provenance_pass':'True',
        'imerg_valid_yunnan_count':'2','imerg_rain_yunnan_count':'1','imerg_index':str(start.hour*2+start.minute//30),
        'b13_sha256':'a'*64,'imerg_sha256':'b'*64,'b13_bytes':'123','imerg_bytes':'456',
        'eligible':'True','rejection_reason':''}


def fixture(rates=((0.,.1,1.,20.),(2.,50.)),starts=None):
    starts=starts or [f.START+timedelta(minutes=30*i) for i in range(len(rates))]
    b=len(rates);shape=(b,1,100,100)
    y=torch.full(shape,float('nan'),dtype=torch.float32);valid=torch.zeros(shape,dtype=torch.bool)
    p=torch.empty(shape,dtype=torch.float64)
    for i,values in enumerate(rates):
        y[i,0,0,:len(values)]=torch.tensor(values,dtype=torch.float32)
        valid[i,0,0,:len(values)]=True;p[i]=.25+.25*i
    physical=(torch.arange(2,34,dtype=torch.float64)/10)[None,:,None,None].expand(b,32,100,100).clone()
    q=torch.log1p(physical)
    output=SimpleNamespace(rain_prob=p,rain_logit=torch.logit(p),conditional_quantiles_log=q,conditional_quantiles_physical=physical)
    batch=SimpleNamespace(y_imerg=y,imerg_valid_mask=valid,yunnan_eval_mask=torch.ones_like(valid))
    samples=[SimpleNamespace(sample_id=t.isoformat(),imerg_window_start=t,analysis_time=t+timedelta(minutes=30)) for t in starts]
    return output,batch,samples


def subset(output,batch,samples,index):
    out=SimpleNamespace(**{k:v[index:index+1] for k,v in vars(output).items()})
    bat=SimpleNamespace(**{k:v[index:index+1] for k,v in vars(batch).items()})
    return out,bat,samples[index:index+1]


def accumulator(samples):
    return f.FinalAccumulator(load_sp04().axes,[s.sample_id for s in samples])


class ProtocolTests(unittest.TestCase):
    def test_fixed_final_and_normalization_and_false_authority(self):
        p=f.load_protocol()
        self.assertEqual(p['FINAL']['sha256'],f.FINAL_SHA)
        self.assertEqual(p['FINAL']['epoch'],11)
        self.assertEqual((p['normalization']['mean_K'],p['normalization']['std_K']),(f.MU,f.SIGMA))
        self.assertFalse(p['FINAL_TEST_2025_AUTHORIZED']);self.assertFalse(p['FINAL_TEST_2025_EXECUTED'])

    def test_existing_diagnostics_inherited_verbatim(self):
        p=f.load_protocol();self.assertEqual(p['inherited_diagnostics'],diagnostic_rules())
        old=f.read(REPO_ROOT/p['identity']['inherited_diagnostic_rules']['path'])
        self.assertEqual(old,p['inherited_diagnostics'])
        self.assertEqual(old['spatial_conditional_pinball_min_rain_count'],30)
        self.assertEqual(old['top_N_each'],10)

    def test_no_post_test_threshold_metric_or_population_tuning(self):
        p=f.load_protocol()
        self.assertEqual(p['primary_metrics'],f.PRIMARY)
        self.assertIsNone(p['metric_definitions']['probability_threshold'])
        self.assertEqual(p['metric_definitions']['POD_FAR_CSI'],'THRESHOLD_NOT_FROZEN')
        self.assertTrue(p['metric_definitions']['no_post_2025_metric_selection'])
        self.assertEqual(p['population']['eligible_population_count'],'NOT_INSPECTED_IN_THIS_ZERO_2025_READ_PREFLIGHT')

    def test_protocol_tamper_fails_before_historical_or_raw_io(self):
        parent=(REPO_ROOT.parent/'tmp/final_test_b0_units').resolve()
        parent.mkdir(parents=True,exist_ok=True)
        root=(parent/('unit_'+uuid.uuid4().hex)).resolve()
        self.assertEqual(root.parent,parent)
        root.mkdir() # inherit the workspace ACL; Windows tempfile mode 0700 is incompatible with the restricted token
        try:
            target=root/f.PROTOCOL_PATH;target.parent.mkdir(parents=True)
            target.write_bytes((REPO_ROOT/f.PROTOCOL_PATH).read_bytes()+b'\n# tampered\n')
            with self.assertRaisesRegex(ValueError,'protocol SHA'): f.load_protocol(root)
        finally:
            if root.resolve().parent!=parent:raise ValueError('Unsafe fixture cleanup target')
            shutil.rmtree(root)

    def test_partial_imerg_validity_remains_eligible(self):
        item=row();item['imerg_valid_yunnan_count']='1'
        self.assertEqual(f.eligibility(item),[])
        item['imerg_valid_yunnan_count']='0'
        self.assertEqual(f.eligibility(item),['NO_VALID_YUNNAN_SUPERVISION'])

    def test_full_b13_required_and_no_older_fallback(self):
        item=row();item['full_valid_native_pixels']='251000';item['used_older_causal_frame']='True'
        self.assertEqual(f.eligibility(item),['B13_FULL_SCENE_REQUIRED','OLDER_FALLBACK_PROHIBITED'])

    def test_causality_and_imerg_product_eligibility_are_fixed(self):
        item=row();item['obs_end']=(f.START+timedelta(minutes=31)).isoformat();item['imerg_run_type']='Early'
        self.assertEqual(f.eligibility(item),['LATEST_CAUSAL_TIME_FAILED','IMERG_V07_FINAL_REQUIRED'])

    def test_missing_latest_has_no_substitution(self):
        item=row();item['expected_latest_available']='False'
        self.assertEqual(f.eligibility(item),['EXPECTED_LATEST_B13_MISSING_NO_FORMAL_FALLBACK'])

    def test_sep30_final_window_and_nominal_source_are_allowed(self):
        item=row(f.END-timedelta(minutes=30))
        self.assertEqual(f.eligibility(item),[])
        self.assertEqual(item['analysis_time'],f.END.isoformat())
        self.assertIn('_20250930_2350_',item['b13_relative_path'])

    def test_all_scheduled_candidates_required_with_fixed_rejection_reasons(self):
        candidates=[row(f.START+timedelta(minutes=30*i)) for i in range(10272)]
        eligible=f.validate_population(candidates)
        self.assertEqual(len(eligible),10272)
        for bad in (candidates[:-1],[candidates[1],candidates[0],*candidates[2:]]):
            with self.assertRaises(ValueError): f.validate_population(bad)
        candidates[0]['eligible']='False'
        with self.assertRaisesRegex(ValueError,'eligibility'): f.validate_population(candidates)

    def test_historical_normalization_matches_exact_frozen_arithmetic(self):
        normal=f.FinalTestNormalizer.load(f.load_protocol(),fixture=True)
        raw=np.full((501,501),280.,dtype=np.float32);valid=np.ones_like(raw,dtype=bool)
        result=normal.transform(raw,valid,f.utc('2024-07-01T00:00:00+00:00'))
        np.testing.assert_array_equal(result,((raw.astype(np.float64)-f.MU)/f.SIGMA).astype(np.float32))
        with self.assertRaises(ValueError):normal.transform(raw,valid,f.START)

    def test_final_normalizer_accepts_only_approved_final_period(self):
        normal=f.FinalTestNormalizer.load(f.load_protocol())
        raw=np.full((501,501),270.,dtype=np.float32);valid=np.ones_like(raw,dtype=bool)
        result=normal.transform(raw,valid,f.START)
        self.assertEqual(result.dtype,np.float32)
        with self.assertRaises(ValueError):normal.transform(raw,valid,f.END)

    def test_final_provenance_rejected_before_checkpoint_load_or_model_apply(self):
        p=f.load_protocol();original=f.read
        def changed(path):
            value=original(path)
            if str(path).endswith('final_checkpoint_identity.json'):value={**value,'sha256':'0'*64}
            return value
        with patch.object(f,'read',side_effect=changed),patch.object(f.inherited_finalfit,'load_verified_checkpoint') as load:
            with self.assertRaisesRegex(ValueError,'FINAL identity'):f.verify_final(p)
            load.assert_not_called()

    def test_checkpoint_SHA_failure_precedes_deserialization(self):
        p=f.load_protocol()
        identity=f.read(REPO_ROOT/p['identity']['final_checkpoint_identity']['path'])
        expected=f.read(REPO_ROOT/p['identity']['finalfit_run_manifest']['path'])['checkpoint_expected']
        with patch.object(f.inherited_finalfit,'sha256',return_value='0'*64),patch.object(torch,'load') as load:
            with self.assertRaisesRegex(ValueError,'file identity'):f.inherited_finalfit.load_verified_checkpoint(identity,expected)
            load.assert_not_called()


class GuardTests(unittest.TestCase):
    def test_october_rejected_before_path_fields_or_io(self):
        for t in ('2025-10-01T00:00:00+00:00','2025-10-31T23:30:00+00:00'):
            with self.assertRaisesRegex(ValueError,'October'):f.guard_source_paths({'window_start':t})

    def test_wrong_year_and_halfhour_cadence_rejected(self):
        for t in ('2024-07-01T00:00:00+00:00','2025-02-28T23:30:00+00:00','2025-07-01T00:10:00+00:00'):
            with self.assertRaises(ValueError):f.guard_time(t)

    def test_path_traversal_alternate_root_and_cross_month_identity_rejected(self):
        variants=[('b13_relative_path',r'..\202503\01\evil.nc'),
            ('imerg_day_path',r'G:\IMERG\2025\imerg_20250301.nc'),
            ('imerg_day_path',r'F:\云南极端降水数据\raw\IMERG\2025\imerg_20251001.nc'),
            ('b13_relative_path',r'202510\01\NC_H09_20251001_0020_R21_FLDK.06001_06001.nc')]
        for key,value in variants:
            item=row();item[key]=value
            with self.assertRaises(ValueError):f.guard_source_paths(item)

    def test_preflight_raw_python_open_is_blocked_before_file_system_access(self):
        paths=[r'H:\葵花202303_202510\202503\01\sample.nc',
            r'F:\云南极端降水数据\raw\IMERG\2025\imerg_20250301.nc',
            r'H:\葵花202303_202510\202407\01\sample.nc']
        with f.RawSourceGuard(preflight=True):
            for path in paths:
                with self.assertRaises(PermissionError):
                    with open(path,'rb'):pass

    def test_direct_netcdf_october_backend_never_called(self):
        import netCDF4
        with patch.object(netCDF4,'Dataset') as backend:
            with f.RawSourceGuard(preflight=True):
                with self.assertRaises(PermissionError):netCDF4.Dataset(r'H:\葵花202303_202510\202510\01\sample.nc')
            backend.assert_not_called()

    def test_future_guard_still_rejects_october_and_source_writes(self):
        with f.RawSourceGuard(preflight=False) as guard:
            for path,mode in ((r'F:\云南极端降水数据\raw\IMERG\2025\imerg_20251001.nc','r'),
                (r'H:\葵花202303_202510\202503\01\sample.nc','w')):
                with self.assertRaises(PermissionError):guard.check(path,mode)

    def test_formal_checkpoint_writes_are_blocked(self):
        with f.RawSourceGuard(preflight=True) as guard:
            with self.assertRaises(PermissionError):guard.check(f.FINAL_PATH,'wb')

    def test_phase_a_or_other_epoch_checkpoint_reads_are_blocked(self):
        with f.RawSourceGuard(preflight=True) as guard:
            for path in (f.FINAL_PATH.with_name('epoch_010.pt'),
                    r'F:\pytorch\Research\outputs\formal_training\b0_phase_a\epoch_011.pt'):
                with self.assertRaises(PermissionError):guard.check(path,'rb')

    def test_misfiled_october_himawari_name_is_rejected_even_in_march_folder(self):
        with f.RawSourceGuard(preflight=False) as guard:
            with self.assertRaises(PermissionError):
                guard.check(r'H:\葵花202303_202510\202503\01\NC_H09_20251001_0020_R21_FLDK.06001_06001.nc','r')

    def test_formal_cli_gate_rejects_before_inference_or_source_catalogue(self):
        import test_b0_2025_final_v1 as runner
        args=SimpleNamespace(authorization=None,authorization_sha256=None,population=None)
        with patch.object(f,'verify_final') as verify:
            with self.assertRaises(PermissionError):runner.formal(args)
            verify.assert_not_called()

    def test_no_authorization_fails_before_population_or_raw_io(self):
        with patch.object(f,'implementation_hashes') as implementation:
            with self.assertRaisesRegex(PermissionError,'AUTHORIZED=false'):f.FinalAuthorization.load(None,None,None)
            implementation.assert_not_called()

    def test_optimizer_backward_and_training_mode_rejections_execute_no_operations(self):
        with f.FinalInferenceGuard() as guard:
            with self.assertRaises(RuntimeError):torch.optim.AdamW.__init__(None)
            with self.assertRaises(RuntimeError):torch.optim.AdamW.step(None)
            with self.assertRaises(RuntimeError):torch.autograd.backward(None)
            with self.assertRaises(RuntimeError):torch.nn.Linear(1,1).train(True)
        self.assertEqual(guard.attempts,{'optimizer_creation':1,'optimizer_step':1,'backward':1,'training_mode':1})


class AccumulatorTests(unittest.TestCase):
    def test_full_population_raw_sums_unequal_batch_partitions(self):
        output,batch,samples=fixture();whole=accumulator(samples);split=accumulator(samples)
        whole.add(output,batch,samples,[{'index':0},{'index':1}])
        for index in range(2):
            o,b,s=subset(output,batch,samples,index);split.add(o,b,s,[{'index':index}])
        a,b=whole.primary_report(),split.primary_report()
        self.assertEqual(a['N_valid'],6);self.assertEqual(a['N_rain'],4)
        for key in ('global_core_loss','occurrence_loss','quantile_loss','Brier','AUROC','Average_Precision','conditional_mean_pinball'):
            self.assertAlmostEqual(a[key],b[key],places=12)
        self.assertEqual(a['32_tau_conditional_coverage'],b['32_tau_conditional_coverage'])
        self.assertEqual(a['global_core_loss'],(a['S_occ']+a['S_qr'])/6)

    def test_conditional_pinball_uses_rain_count_not_valid_count(self):
        o,b,s=fixture();a=accumulator(s);a.add(o,b,s,[{'index':0},{'index':1}]);r=a.primary_report()
        self.assertEqual(r['conditional_mean_pinball'],r['S_qr']/4)
        self.assertEqual(r['quantile_loss'],r['S_qr']/6)

    def test_float32_point_one_remains_negative(self):
        o,b,s=fixture(((0.,.1,1.),));a=accumulator(s);a.add(o,b,s,[{'index':0}])
        self.assertEqual(a.primary_report()['N_rain'],1)

    def test_masked_missing_targets_remain_nan_and_do_not_count_as_zero(self):
        o,b,s=fixture(((0.,1.),));a=accumulator(s);a.add(o,b,s,[{'index':0}])
        self.assertTrue(torch.isnan(b.y_imerg[~b.imerg_valid_mask]).all())
        self.assertEqual(a.primary_report()['N_valid'],2)

    def test_target_nonfinite_inside_valid_mask_stops(self):
        o,b,s=fixture(((0.,1.),));b.y_imerg[0,0,0,0]=float('nan');a=accumulator(s)
        with self.assertRaises(FloatingPointError):a.add(o,b,s,[{'index':0}])

    def test_no_rain_conditional_and_coverage_errors_are_null(self):
        o,b,s=fixture(((0.,.1),));a=accumulator(s);a.add(o,b,s,[{'index':0}]);r=a.primary_report()
        self.assertIsNone(r['conditional_mean_pinball']);self.assertIsNone(r['Average_Precision']);self.assertIsNone(r['AUROC'])
        self.assertEqual(r['coverage_error'],[None]*32);self.assertIsNone(r['mean_absolute_coverage_error'])
        diagnostics=a.diagnostics(b.yunnan_eval_mask[0,0].numpy())
        self.assertTrue(all(bin['pixel_count']==0 for bin in diagnostics['rainrate']))
        self.assertIsNone(diagnostics['probability_distributions']['rainy_truth'])

    def test_single_positive_class_AUC_null_AP_one(self):
        o,b,s=fixture(((1.,2.),));a=accumulator(s);a.add(o,b,s,[{'index':0}]);r=a.primary_report()
        self.assertIsNone(r['AUROC']);self.assertEqual(r['Average_Precision'],1.)

    def test_exact_tied_scores_AP_AUC_match_inherited_convention(self):
        metrics=grouped_occurrence_metrics([.9,.9,.5,.5,.1],[True,False,True,False,False])
        self.assertAlmostEqual(metrics['AUROC'],2/3)
        self.assertEqual(metrics['Average_Precision'],.5)

    def test_coverage_counts_and_signed_absolute_errors(self):
        o,b,s=fixture(((1.,2.),));a=accumulator(s);a.add(o,b,s,[{'index':0}]);r=a.primary_report()
        expected=(np.array([1.,2.])[:,None]<=o.conditional_quantiles_physical[0,:,0,0].numpy()).mean(0)
        np.testing.assert_array_equal(r['32_tau_conditional_coverage'],expected)
        np.testing.assert_array_equal(r['coverage_error'],expected-f.TAU)
        np.testing.assert_array_equal(r['absolute_coverage_error'],np.abs(expected-f.TAU))

    def test_crossing_in_cell_outside_evaluation_mask_stops(self):
        o,b,s=fixture(((1.,),));o.conditional_quantiles_log[0,5,99,99]=o.conditional_quantiles_log[0,4,99,99]
        with self.assertRaises(FloatingPointError):accumulator(s).add(o,b,s,[{'index':0}])

    def test_nonfinite_occurrence_outside_mask_stops(self):
        o,b,s=fixture(((1.,),));o.rain_prob[0,0,99,99]=float('nan')
        with self.assertRaises(FloatingPointError):accumulator(s).add(o,b,s,[{'index':0}])

    def test_log_and_physical_support_violations_stop(self):
        for name,value in (('conditional_quantiles_log',math.log1p(.1)),('conditional_quantiles_physical',.1)):
            o,b,s=fixture(((1.,),));getattr(o,name)[0,0,99,99]=value
            with self.assertRaises(FloatingPointError):accumulator(s).add(o,b,s,[{'index':0}])

    def test_quantile_float32_policy_violation_stops(self):
        o,b,s=fixture(((1.,),));o.conditional_quantiles_log=o.conditional_quantiles_log.float()
        with self.assertRaises(ValueError):accumulator(s).add(o,b,s,[{'index':0}])

    def test_reordered_duplicate_and_incomplete_population_rejected(self):
        o,b,s=fixture();a=accumulator(s)
        with self.assertRaises(ValueError):a.add(o,b,s[::-1],[{'index':0},{'index':1}])
        x,y,z=subset(o,b,s,0);a.add(x,y,z,[{'index':0}])
        with self.assertRaises(ValueError):a.add(x,y,z,[{'index':1}])
        with self.assertRaises(ValueError):a.primary_report()

    def test_monthly_spatial_reliability_and_rate_reconcile(self):
        o,b,s=fixture(starts=[f.utc('2025-03-31T23:30:00+00:00'),f.utc('2025-04-01T00:00:00+00:00')])
        a=accumulator(s);a.add(o,b,s,[{'index':0},{'index':1}]);d=a.diagnostics(b.yunnan_eval_mask[0,0].numpy())
        self.assertEqual(sum(m['scene_count'] for m in d['monthly']),2)
        self.assertEqual([m['month'] for m in d['monthly']],[f'2025-{m:02d}' for m in range(3,10)])
        self.assertEqual(sum(r['count'] for r in d['reliability']),6)
        self.assertEqual(sum(r['pixel_count'] for r in d['rainrate']),4)
        self.assertTrue(np.isnan(d['spatial']['conditional_pinball']).all())
        self.assertEqual(a.global_acc.n_rain,4)

    def test_reliability_edges_and_descriptive_rate_boundaries_unchanged(self):
        rates=(.1,1.,5.,10.,20.,30.,50.,100.)
        o,b,s=fixture((rates,));o.rain_prob[0,0,0,:8]=torch.tensor([0.,.1,.2,.3,.4,.5,.9,1.],dtype=torch.float64)
        o.rain_logit=torch.zeros_like(o.rain_prob) # independent finite fixture logits for the edge-bin test
        a=accumulator(s);a.add(o,b,s,[{'index':0}])
        self.assertEqual(a.rate[:,0].tolist(),[1.,1.,1.,1.,1.,1.,1.])
        self.assertEqual(a.bins[:,0].tolist(),[1.,1.,1.,1.,1.,1.,0.,0.,0.,2.])

    def test_proxy_is_not_exact_expectation_and_threshold_metrics_remain_unfrozen(self):
        o,b,s=fixture(((0.,1.),));a=accumulator(s);a.add(o,b,s,[{'index':0}]);r=a.primary_report()
        proxy=(o.rain_prob*o.conditional_quantiles_physical.mean(1,keepdim=True))[b.imerg_valid_mask]
        y=b.y_imerg[b.imerg_valid_mask].double()
        self.assertEqual(r['DIAGNOSTIC_PROXY_METRIC']['MAE'],float((proxy-y).abs().mean()))
        self.assertFalse(r['DIAGNOSTIC_PROXY_METRIC']['is_exact_expected_precipitation'])
        for name in ('POD','FAR','CSI'):self.assertEqual(r[name],'THRESHOLD_NOT_FROZEN')
        self.assertNotIn('checkpoint_metric',r)

    def test_case_ties_use_declared_scene_then_row_major_order(self):
        o,b,s=fixture(((1.,1.),(1.,1.)));a=accumulator(s);a.add(o,b,s,[{'index':0},{'index':1}])
        cases=a.diagnostics(b.yunnan_eval_mask[0,0].numpy())['cases']
        high=[c for c in cases if c['rule']=='HIGHEST_TRUE_RAIN_RATE']
        self.assertEqual([(c['scene_index'],c['target_col']) for c in high],[(0,0),(0,1),(1,0),(1,1)])


class PreflightArtifactTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.out=Path(os.environ['YUNTAPR_FINAL_TEST_PREFLIGHT_EVIDENCE'])
        cls.manifest=f.read(cls.out/'preflight_manifest.json')
        cls.smoke=f.read(cls.out/'synthetic_FINAL_forward_smoke.json')

    def test_exact_protocol_and_new_runner_code_pinned(self):
        self.assertEqual(self.manifest['protocol_sha256'],f.PROTOCOL_SHA)
        self.assertEqual(self.manifest['implementation_sha256'],f.implementation_hashes())

    def test_all_historical_files_byte_identical(self):
        for name,digest in self.manifest['baseline_files_sha256'].items():self.assertEqual(sha256(REPO_ROOT/name),digest,name)

    def test_final_sha_provenance_verified_read_only(self):
        identity=f.read(self.out/'final_identity_verification.json')
        self.assertEqual(identity['sha256'],f.FINAL_SHA)
        self.assertTrue(identity['provenance_before_state_application'])
        self.assertFalse(identity['optimizer_state_applied']);self.assertFalse(identity['RNG_state_applied'])

    def test_FINAL_model_parameters_unchanged_by_synthetic_forward(self):
        self.assertEqual(self.smoke['model_state_sha256_before'],self.smoke['model_state_sha256_after'])
        self.assertFalse(self.smoke['MODEL_PARAMETERS_UPDATED']);self.assertEqual(self.smoke['OPTIMIZER_STEPS'],0)
        self.assertEqual(self.smoke['BACKWARD_CALLS'],0)

    def test_forward_precision_and_fixture_metrics_are_explicit(self):
        self.assertEqual(self.smoke['raw_quantile_dtype'],'torch.float32')
        self.assertEqual(self.smoke['qlog_dtype'],'torch.float64')
        self.assertEqual(self.smoke['qphysical_dtype'],'torch.float64')
        self.assertEqual(self.smoke['synthetic_metrics']['N_valid'],4)
        self.assertEqual(self.smoke['synthetic_metrics']['N_rain'],2)
        self.assertTrue(self.smoke['not_a_Final_Test_result'])

    def test_zero_2025_reads_and_no_formal_test_authority_or_execution(self):
        self.assertFalse(self.manifest['FINAL_TEST_2025_AUTHORIZED']);self.assertFalse(self.manifest['FINAL_TEST_2025_EXECUTED'])
        self.assertEqual(self.manifest['2025_PIXELS_READ'],0);self.assertEqual(self.smoke['2025_PIXELS_READ'],0)


if __name__=='__main__':unittest.main()
