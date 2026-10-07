"""TEST_FIXTURE_ONLY. New head, unchanged objectives; no real data or old weights."""
import ast
import gc
import inspect
import math
import unittest
from unittest.mock import patch
import torch
from yuntapr.models.b0 import B0Model
from yuntapr.models.quantile_v2 import parameterization as parameterization_module
from yuntapr.models.quantile_v2.parameterization import CandidateNumerics, normalized_monotonic_quantiles
from yuntapr.models.quantile_v2.heads import ProbabilityHeadsV2
from yuntapr.models.quantile_v2.models import B0MatchedV2, B1V2
from yuntapr.models.quantile_v2.outputs import (LogDomainOutput, materialize_physical,
    physical_risk, validate_log_quantiles)
from yuntapr.models.quantile_v2.legacy_path import LegacyLogDomainFixture
from yuntapr.losses.total_loss import b0_core_loss
from yuntapr.losses.pinball import frozen_taus
from quantile_head_v2 import verification as v
from quantile_head_v2.governance import check_raw_path


class ParameterizationTests(unittest.TestCase):
    def logits(self,dtype=torch.float32):
        return torch.zeros(2,32,2,3,dtype=dtype,requires_grad=True), torch.zeros(2,1,2,3,dtype=dtype,requires_grad=True)

    def test_shape_and_fp64_output(self):
        a,s=self.logits();q=normalized_monotonic_quantiles(a,s,numerics=v.NUMERICS)
        self.assertEqual(q.shape,(2,32,2,3));self.assertEqual(q.dtype,torch.float64)

    def test_tau_grid_bit_exact(self):
        self.assertTrue(torch.equal(frozen_taus(dtype=torch.float64),torch.tensor([(i-.5)/32 for i in range(1,33)],dtype=torch.float64)))

    def test_strict_support_and_order(self):
        a,s=self.logits();q=normalized_monotonic_quantiles(a,s,numerics=v.NUMERICS)
        self.assertTrue((q[:,:1]>math.log1p(.1)).all());self.assertTrue((q[:,1:]>q[:,:-1]).all())

    def test_endpoint_is_independent_of_allocation(self):
        a,s=self.logits();q=normalized_monotonic_quantiles(a,s,numerics=v.NUMERICS)
        changed=a.detach().clone();changed[:,::2]=1e4;changed[:,1::2]=-1e4
        other=normalized_monotonic_quantiles(changed,s,numerics=v.NUMERICS)
        self.assertTrue(torch.equal(q[:,-1:],other[:,-1:]))
        self.assertFalse(torch.equal(q[:,:-1],other[:,:-1]))

    def test_exact_q32_formula(self):
        a,s=self.logits();q=normalized_monotonic_quantiles(a,s,numerics=v.NUMERICS)
        expected=math.log1p(.1)+(torch.nn.functional.softplus(s.double())+v.NUMERICS.epsilon_span)
        self.assertTrue(torch.equal(q[:,-1:],expected))

    def test_both_allocation_and_span_have_finite_gradients(self):
        a,s=self.logits();q=normalized_monotonic_quantiles(a,s,numerics=v.NUMERICS)
        tau=frozen_taus(dtype=torch.float64).reshape(1,32,1,1)
        error=math.log1p(2.)-q
        torch.maximum(tau*error,(tau-1)*error).mean().backward()
        self.assertTrue(torch.isfinite(a.grad).all() and torch.isfinite(s.grad).all())
        self.assertTrue((a.grad!=0).any() and (s.grad!=0).any())

    def test_wrong_shapes_rejected(self):
        a,s=self.logits()
        with self.assertRaises(ValueError):normalized_monotonic_quantiles(a[:,:31],s,numerics=v.NUMERICS)
        with self.assertRaises(ValueError):normalized_monotonic_quantiles(a,s[:,:,:1],numerics=v.NUMERICS)

    def test_nonfinite_allocation_rejected(self):
        a,s=self.logits();a=a.detach();a[:,0]=float('inf')
        with self.assertRaisesRegex(FloatingPointError,'RAW_NONFINITE'):normalized_monotonic_quantiles(a,s,numerics=v.NUMERICS)

    def test_nonfinite_span_rejected(self):
        a,s=self.logits();s=s.detach();s[:]=float('nan')
        with self.assertRaisesRegex(FloatingPointError,'RAW_NONFINITE'):normalized_monotonic_quantiles(a,s,numerics=v.NUMERICS)

    def test_epsilons_have_no_defaults(self):
        with self.assertRaises(TypeError):CandidateNumerics()
        for invalid in (0,-1,float('inf'),float('nan'),True):
            with self.assertRaises(ValueError):CandidateNumerics(invalid,1e-4)
            with self.assertRaises(ValueError):CandidateNumerics(1e-4,invalid)

    def test_inputs_not_mutated(self):
        a,s=self.logits();aa,ss=a.clone(),s.clone()
        normalized_monotonic_quantiles(a,s,numerics=v.NUMERICS)
        self.assertTrue(torch.equal(a,aa) and torch.equal(s,ss))

    def test_finite_raw_precision_counterexample_is_rejected(self):
        a=torch.full((1,32,1,1),-1e4,dtype=torch.float64);a[:,0]=1e20
        s=torch.full((1,1,1,1),-1e4,dtype=torch.float64)
        with self.assertRaisesRegex(FloatingPointError,'STRICT_ORDER_LOST'):normalized_monotonic_quantiles(a,s,numerics=v.NUMERICS)
        v.RESULTS['fp64_finite_raw_counterexample']={'finite_raw':True,'largest_raw':1e20,'epsilon_w':1e-4,'epsilon_span':1e-4,'guard_rejects':True,'repair_applied':False}

    def test_finite_raw_sum_overflow_is_rejected(self):
        a=torch.full((1,32,1,1),torch.finfo(torch.float64).max,dtype=torch.float64)
        s=torch.zeros(1,1,1,1,dtype=torch.float64)
        with self.assertRaisesRegex(FloatingPointError,'ALLOCATION_TOTAL_NONFINITE'):normalized_monotonic_quantiles(a,s,numerics=v.NUMERICS)

    def test_native_fp32_counterexample_is_disclosed(self):
        a=torch.full((1,32,1,1),-1e4,dtype=torch.float32);a[:,0]=1e4
        s=torch.full((1,1,1,1),-1e4,dtype=torch.float32)
        w=torch.nn.functional.softplus(a)+1e-4;prefix=torch.cumsum(w,1)
        q=math.log1p(.1)+(torch.nn.functional.softplus(s)+1e-4)*(prefix/prefix[:,-1:])
        ties=int((q[:,1:]==q[:,:-1]).sum())
        self.assertEqual(ties,31)
        v.RESULTS['native_fp32_counterexample']={'finite_raw':True,'largest_raw':1e4,'adjacent_equal_count':ties,'production_transform_dtype':'float64','native_fp32_approved':False}

    def test_no_clamp_sort_nan_repair(self):
        tree=ast.parse(inspect.getsource(parameterization_module))
        attrs={n.attr for n in ast.walk(tree) if isinstance(n,ast.Attribute)}
        self.assertFalse(attrs & {'clamp','clamp_min','clamp_max','sort','argsort','nan_to_num','nextafter'})

    def test_extreme_raw_float32_float64_large_random_stress(self):
        result=v.extreme_stress();self.assertTrue(result['all_required_cases_pass'])


class OutputPathTests(unittest.TestCase):
    def output(self,span=0.):
        a=torch.zeros(1,32,100,100,requires_grad=True)
        s=torch.full((1,1,100,100),span,requires_grad=True)
        q=normalized_monotonic_quantiles(a,s,numerics=v.NUMERICS)
        logit=torch.zeros(1,1,100,100,requires_grad=True)
        return LogDomainOutput(logit,torch.sigmoid(logit),q),a,s

    def test_log_api_has_no_physical_products(self):
        out,_,_=self.output()
        self.assertFalse(hasattr(out,'conditional_quantiles_physical'))
        self.assertFalse(hasattr(out,'threshold_censored_mean'))

    def test_head_training_forward_cannot_call_expm1(self):
        head=ProbabilityHeadsV2(numerics=v.NUMERICS)
        with patch.object(torch,'expm1',side_effect=AssertionError('Implicit physical product forbidden')):
            out=head(torch.zeros(2,48,100,100))
        self.assertEqual(out.conditional_quantiles_log.shape,(2,32,100,100))

    def test_explicit_physical_conversion_and_proxy(self):
        out,_,_=self.output();p=materialize_physical(out)
        self.assertTrue(torch.equal(p.conditional_quantiles_physical,torch.expm1(out.conditional_quantiles_log)))
        self.assertTrue(torch.equal(p.threshold_censored_mean,out.rain_prob*p.conditional_quantiles_physical.mean(1,keepdim=True)))

    def test_physical_overflow_raises_without_repair(self):
        out,_,_=self.output(1000.)
        self.assertTrue(torch.isfinite(out.conditional_quantiles_log).all())
        with self.assertRaisesRegex(FloatingPointError,'PHYSICAL_OVERFLOW'):materialize_physical(out)

    def test_physical_risk_does_not_stop_log_loss_or_backward(self):
        out,a,s=self.output(1000.)
        report=physical_risk(out.conditional_quantiles_log)
        self.assertTrue(report['FP64_PHYSICAL_OVERFLOW_RISK'] and report['FP32_PHYSICAL_OVERFLOW_RISK'])
        y=torch.full_like(out.rain_logit,2.);mask=torch.ones_like(y,dtype=torch.bool)
        with patch.object(torch,'expm1',side_effect=AssertionError('No physical conversion in loss')):
            result=b0_core_loss(out,y,mask,mask,focal_alpha=.5,focal_gamma=2.,quantile_axis_reduction='mean')
            result.total.backward()
        self.assertTrue(torch.isfinite(result.total) and torch.isfinite(a.grad).all() and torch.isfinite(s.grad).all())

    def test_risk_has_no_gradient_RNG_or_mutation_effect(self):
        from yuntapr.training.phase_a_protocol import state_digest,capture_rng
        out,a,s=self.output();before=out.conditional_quantiles_log.clone()
        rng=state_digest(capture_rng())
        with patch.object(torch,'expm1',side_effect=AssertionError('Risk never materializes physical')):
            report=physical_risk(out.conditional_quantiles_log)
        self.assertEqual(len(report['per_tau_qlog_range']),32)
        self.assertTrue(torch.equal(before,out.conditional_quantiles_log));self.assertIsNone(a.grad)
        self.assertEqual(rng,state_digest(capture_rng()))

    def test_risk_boundary_is_strictly_greater(self):
        boundary=math.log1p(torch.finfo(torch.float64).max)
        q=torch.linspace(.2,boundary,32,dtype=torch.float64).reshape(1,32,1,1)
        self.assertFalse(physical_risk(q)['FP64_PHYSICAL_OVERFLOW_RISK'])
        q[:,-1]=boundary+1e-10
        self.assertTrue(physical_risk(q)['FP64_PHYSICAL_OVERFLOW_RISK'])

    def test_diagnostics_do_not_change_gradients(self):
        gradients=[]
        for observe in (False,True):
            out,a,s=self.output(1000.)
            if observe:physical_risk(out.conditional_quantiles_log)
            out.conditional_quantiles_log.mean().backward();gradients.append((a.grad,s.grad))
        self.assertTrue(all(torch.equal(a,b) for a,b in zip(*gradients)))


class ModelAndEquivalenceTests(unittest.TestCase):
    def test_v2_full_native_CUDA_batch2_loss_backward(self):
        self.assertTrue(all(row['all_parameter_gradients_finite'] for row in v.full_chain(2)))

    def test_v2_full_native_CUDA_singleton_loss_backward(self):
        self.assertTrue(all(row['actual_denominator']==3430 for row in v.full_chain(1)))

    def test_A_cpu_two_batches_bit_exact(self):
        self.assertTrue(v.equivalence(torch.device('cpu'))['qlog_loss_gradients_optimizer_model_RNG_exact'])

    def test_A_cuda_two_batches_bit_exact(self):
        self.assertTrue(torch.cuda.is_available(),'Actual CUDA test is mandatory, not skipped')
        self.assertTrue(v.equivalence(torch.device('cuda'))['qlog_loss_gradients_optimizer_model_RNG_exact'])

    def test_true_parameter_counts_and_fresh_deterministic_head_identity(self):
        r=v.model_identity()
        self.assertEqual(r['models']['B0_MATCHED_V2']['parameters']['total'],4329410)
        self.assertEqual(r['models']['B1_V2']['parameters']['total'],4331810)
        self.assertTrue(r['same_head_family'] and r['head_parameters_bit_identical_in_disposable_paired_fixture'])

    def test_B0_B1_full_native_forward_shapes_and_no_physical(self):
        for cls,frames in ((B0MatchedV2,1),(B1V2,6)):
            model=cls(numerics=v.NUMERICS).eval();x=torch.zeros(1,frames,501,501)
            with torch.no_grad(),torch.autocast('cpu',dtype=torch.bfloat16),patch.object(torch,'expm1',side_effect=AssertionError('Physical forbidden')):
                out=model(x,torch.ones_like(x,dtype=torch.bool))
            self.assertEqual(out.native_feature_shape,(1,48,501,501))
            self.assertEqual(out.target_feature_shape,(1,48,100,100))
            self.assertEqual(out.conditional_quantiles_log.shape,(1,32,100,100))
            del model,x,out
            gc.collect()

    def test_full_models_reject_missing_without_placeholder(self):
        model=B1V2(numerics=v.NUMERICS);x=torch.zeros(1,6,501,501);mask=torch.ones_like(x,dtype=torch.bool);mask.flatten()[0]=False
        with self.assertRaisesRegex(ValueError,'full-valid'):model(x,mask)

    def test_old_checkpoint_shape_is_incompatible_without_loading_checkpoint(self):
        old=B0Model();new=B0MatchedV2(numerics=v.NUMERICS)
        with self.assertRaises(RuntimeError):new.load_state_dict(old.state_dict())

    def test_legacy_adapter_requires_fixture_scope(self):
        with self.assertRaises(PermissionError):LegacyLogDomainFixture(test_fixture_only=False)

    def test_cpu_autocast_forward_and_fp64_quantile_backward(self):
        self.autocast(torch.device('cpu'))

    def test_cuda_autocast_raw_fp32_transform_fp64_and_gradients(self):
        self.assertTrue(torch.cuda.is_available());self.autocast(torch.device('cuda'))

    def autocast(self,device):
        head=ProbabilityHeadsV2(numerics=v.NUMERICS).to(device)
        seen=[];hook=head.quantile.register_forward_hook(lambda m,i,o:seen.append(o.dtype))
        try:
            with torch.autocast(device.type,dtype=torch.bfloat16):
                out=head(torch.zeros(1,48,100,100,device=device))
                loss=out.conditional_quantiles_log.mean()
                if device.type=='cuda':loss=loss+out.rain_logit.mean()
            loss.backward()
        finally:hook.remove()
        self.assertEqual(seen,[torch.float32]);self.assertEqual(out.conditional_quantiles_log.dtype,torch.float64)
        parameters=head.parameters() if device.type=='cuda' else head.quantile.parameters()
        self.assertTrue(all(p.grad is not None and torch.isfinite(p.grad).all() for p in parameters))
        del head,out,loss
        if device.type=='cuda':torch.cuda.empty_cache()


class GovernanceTests(unittest.TestCase):
    def test_2025_himawari_blocked_before_open(self):
        with self.assertRaises(PermissionError):check_raw_path(r'H:\葵花202303_202510\202503\frame.nc')

    def test_2025_imerg_blocked_before_open(self):
        with self.assertRaises(PermissionError):check_raw_path(r'F:\云南极端降水数据\raw\IMERG\IMERG_20250701.nc')

    def test_2023_2024_raw_also_not_needed(self):
        for year in (2023,2024):
            with self.assertRaises(PermissionError):check_raw_path(f'H:/葵花202303_202510/{year}03/frame.nc')

    def test_v2_candidate_cannot_authorize_formal_training(self):
        from quantile_head_v2 import common as c
        config=c.read(c.ROOT/'config/science_v2/quantile_head_v2_candidate.json')
        for key in ('FORMAL_TRAINING_AUTHORIZED','V2_SCIENTIFIC_FREEZE_APPROVED','V2_PHASE_A_AUTHORIZED','V2_PHASE_B_AUTHORIZED'):
            self.assertIs(config['authorization'][key],False)


if __name__=='__main__':unittest.main()
