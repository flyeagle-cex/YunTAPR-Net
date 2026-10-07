import copy
from dataclasses import asdict
import json
import math
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import numpy as np
import torch
from yuntapr.models.quantile_v2.outputs import LogDomainOutput, validate_log_quantiles
from yuntapr.training.phase_a_protocol import (ValidationSelection, lr_for_update, state_digest,
    capture_rng, seed_reproducibility)
from yuntapr.training import formal_phase_a_v2 as f
from yuntapr.training import checkpoint_v2 as ck
from yuntapr.training.phase_a_audit_v2 import Counters, SourceFirewall, atomic_json, identity
from yuntapr.training.upper_tail_v2 import UpperTailDiagnostics, BOUNDARY
from yuntapr.training.phase_a_validation_v2 import LogDomainValidation


def mask():
    m=torch.zeros((100,100),dtype=torch.bool);m.flatten()[:3430]=True;return m


def output(batch=1, base=1.):
    q=(torch.arange(32,dtype=torch.float64)/10+base).view(1,32,1,1).expand(batch,32,100,100).clone()
    logits=torch.zeros(batch,1,100,100)
    return LogDomainOutput(logits,torch.sigmoid(logits),q)


class DiagnosticTests(unittest.TestCase):
    def test_counts_both_units_and_regions(self):
        m=torch.tensor([[True,False]])
        q=torch.arange(32,dtype=torch.float64).reshape(1,32,1,1).expand(2,32,1,2).clone()
        d=UpperTailDiagnostics(m,'TEST_FIXTURE_ONLY');d.observe(q,['a','b']);r=d.report()
        for label in ('YUNNAN_INSIDE','YUNNAN_OUTSIDE'):
            for threshold in (10,50,100,500,1000):
                expected=sum(i>math.log1p(threshold) for i in range(32))*2
                self.assertEqual(r[label]['threshold_exceedances'][str(threshold)]['scene_pixel_tau_exposure'],expected)
                self.assertEqual(r[label]['threshold_exceedances'][str(threshold)]['scene_pixel_any_tau_exposure'],2)

    def test_percentile_exact_linear_forward_weighting(self):
        d=UpperTailDiagnostics(torch.tensor([[True,False]]),'TEST_FIXTURE_ONLY')
        for batch,value in ((2,1.),(1,11.)):
            d.observe(torch.full((batch,32,1,2),value,dtype=torch.float64),['x']*batch)
        self.assertEqual(d.report()['YUNNAN_INSIDE']['q32_per_forward_max_p99'],10.9)
        self.assertAlmostEqual(d.report()['YUNNAN_INSIDE']['q32_per_forward_max_p99_9'],10.99)

    def test_observer_does_not_modify_tensor_or_rng(self):
        q=output().conditional_quantiles_log.requires_grad_();before=q.clone();rng=state_digest(capture_rng())
        UpperTailDiagnostics(mask(),'TRAIN').observe(q,['a'])
        self.assertTrue(torch.equal(before,q));self.assertIsNone(q.grad)
        self.assertEqual(rng,state_digest(capture_rng()))

    def test_fp64_risk_does_not_materialize_or_stop(self):
        out=output(base=BOUNDARY+10)
        with patch.object(torch,'expm1',side_effect=AssertionError('forbidden')):
            validate_log_quantiles(out.conditional_quantiles_log)
            d=UpperTailDiagnostics(mask(),'TRAIN');d.observe(out.conditional_quantiles_log,['a'])
            self.assertTrue(d.report()['YUNNAN_INSIDE']['FP64_PHYSICAL_OVERFLOW_RISK'])

    def test_partition_argmax_identity(self):
        q=output(2).conditional_quantiles_log;q[1,31,99,99]=900
        d=UpperTailDiagnostics(mask(),'TRAIN');r=d.observe(q,['first','second'])
        self.assertEqual(r['YUNNAN_OUTSIDE']['max_location']['sample_id'],'second')
        self.assertEqual(r['YUNNAN_OUTSIDE']['max_location']['row'],99)

    def test_phase_separation_and_empty_rejection(self):
        a=UpperTailDiagnostics(mask(),'TRAIN');b=UpperTailDiagnostics(mask(),'VALIDATION')
        a.observe(output().conditional_quantiles_log,['a'])
        with self.assertRaises(ValueError): b.report()
        with self.assertRaises(ValueError): UpperTailDiagnostics(mask(),'BOTH')


class ValidationTests(unittest.TestCase):
    def add(self,acc,batch,rate):
        out=output(batch); y=torch.full((batch,1,100,100),rate,dtype=torch.float32)
        m=mask().expand(batch,1,100,100);acc.add(out,y,torch.ones_like(m),m)

    def test_global_accumulation_not_mean_of_batch_means(self):
        a=LogDomainValidation();b=LogDomainValidation();c=LogDomainValidation()
        self.add(a,2,0.);self.add(a,1,10.);self.add(b,2,0.);self.add(c,1,10.)
        expected=(b.s_occ+b.s_qr+c.s_occ+c.s_qr)/(3*3430)
        self.assertEqual(a.report()['global_val_core_loss'],expected)

    def test_no_physical_attribute_or_expm1_required(self):
        with patch.object(torch,'expm1',side_effect=AssertionError()):
            a=LogDomainValidation();self.add(a,1,1.);self.assertEqual(a.report()['N_valid'],3430)

    def test_occurrence_threshold_float32_boundary(self):
        a=LogDomainValidation();self.add(a,1,.1);self.assertEqual(a.n_rain,0)

    def test_zero_rain_no_skip(self):
        a=LogDomainValidation();self.add(a,1,0.);self.assertEqual(a.s_qr,0.);self.assertGreater(a.report()['global_val_core_loss'],0)

    def test_bad_denominator(self):
        out=output();valid=torch.zeros(1,1,100,100,dtype=torch.bool)
        with self.assertRaises(ValueError):LogDomainValidation().add(out,torch.ones(1,1,100,100),valid,valid)


class ProtocolTests(unittest.TestCase):
    def test_storage_budget_scales_by_measured_exposures(self):
        from paired_phase_a_v2.preflight import log_budget_from_smoke
        with tempfile.TemporaryDirectory() as temp:
            rows=[]
            for kind,frames in (('B0_MATCHED_V2',1),('B1_V2',6)):
                folder=Path(temp)/'smoke'/kind;folder.mkdir(parents=True)
                exposures=sum((2,1,8,5))*(frames+1)
                (folder/'raw_access_parent.jsonl').write_bytes(b'x'*(10*exposures))
                for i,batch in enumerate((2,1,8,5)):
                    (folder/f'{i}_diagnostics.jsonl').write_bytes(b'x'*100)
                    rows.append({'model':kind,'sample_ids':['fixture']*batch})
            budgets=log_budget_from_smoke(temp,rows)
            self.assertEqual(budgets['B1_V2']['predicted_io_bytes_per_epoch'],10*(10455+10501)*7)
            self.assertEqual(budgets['B0_MATCHED_V2']['predicted_diagnostic_bytes_per_epoch'],100*6541)

    def test_best_and_early_stop_separate(self):
        s=ValidationSelection();s.update(1,1.);d=s.update(2,.99999)
        self.assertTrue(d['checkpoint_selected']);self.assertFalse(d['early_stop_improvement']);self.assertEqual(s.non_improvement_count,1)

    def test_tie_preserves_earliest_and_eight_stops(self):
        s=ValidationSelection();s.update(1,1.)
        for ep in range(2,10):d=s.update(ep,1.)
        self.assertTrue(d['stop']);self.assertEqual(s.selected_checkpoint_epoch,1)

    def test_exact_min_delta_is_not_improvement(self):
        s=ValidationSelection();s.update(1,1.);self.assertFalse(s.update(2,1.-1e-4)['early_stop_improvement'])

    def test_lr_boundaries(self):
        self.assertEqual(lr_for_update(5228,steps_per_epoch=5228),1e-4)
        self.assertEqual(lr_for_update(261400,steps_per_epoch=5228),1e-6)
        self.assertLess(lr_for_update(1,steps_per_epoch=5228),1e-6)

    def test_numerical_guards(self):
        for mode in ('nan','equal','support'):
            q=output().conditional_quantiles_log
            if mode=='nan':q[0,2,0,0]=float('nan')
            elif mode=='equal':q[0,2,0,0]=q[0,1,0,0]
            else:q[0,0,0,0]=math.log1p(.1)
            with self.assertRaises(FloatingPointError):validate_log_quantiles(q)

    def test_counter_scopes(self):
        a=Counters('FORMAL');b=Counters('ENGINEERING_ONLY');b.OPTIMIZER_STEPS=4
        self.assertEqual(a.OPTIMIZER_STEPS,0)
        with self.assertRaises(ValueError):Counters('ANY')

    def test_2025_rejected_before_open(self):
        with tempfile.TemporaryDirectory() as temp:
            guard=SourceFirewall({},Path(temp)/'events.jsonl')
            with self.assertRaises(PermissionError):guard.check(r'F:\云南极端降水数据\raw\IMERG\2025\imerg_20250301.nc')
            self.assertEqual(guard.raw_opens,0)

    def test_raw_write_rejected(self):
        p=r'H:\葵花202303_202510\202303\test_20230301.nc'
        with tempfile.TemporaryDirectory() as temp:
            guard=SourceFirewall({p:{'year':2023,'month':3}},Path(temp)/'events.jsonl')
            self.assertTrue(guard.check(p,'rb'))
            with self.assertRaises(PermissionError):guard.check(p,'wb')

    def test_atomic_immutable_no_overwrite(self):
        with tempfile.TemporaryDirectory() as temp:
            p=Path(temp)/'evidence.json';atomic_json(p,{'a':1},immutable=True)
            with self.assertRaises(FileExistsError):atomic_json(p,{'a':2},immutable=True)
            self.assertEqual(json.loads(p.read_text())['a'],1)

    def test_no_implicit_train_cli(self):
        import run_paired_phase_a_v2 as entry
        with self.assertRaises(SystemExit):entry.main([])
        with self.assertRaises(SystemExit):entry.main(['train'])

    def test_scientific_approval_does_not_authorize_formal_runner(self):
        from types import SimpleNamespace
        from yuntapr.training.phase_a_audit_v2 import digest
        with tempfile.TemporaryDirectory() as temp:
            p=Path(temp)/'authorization.json';p.write_text(json.dumps({'V2_SCIENTIFIC_FREEZE_APPROVED':True,'FORMAL_TRAINING_AUTHORIZED':False}))
            contract=SimpleNamespace(root=Path(temp),code={})
            with self.assertRaises(PermissionError):f.authorize(p,digest(p),contract)


class CheckpointTests(unittest.TestCase):
    def fixture(self):
        seed_reproducibility()
        model=torch.nn.Linear(2,1);optimizer=torch.optim.AdamW(model.parameters(),lr=1e-4,foreach=False,fused=False)
        model(torch.ones(1,2)).sum().backward();optimizer.step();optimizer.zero_grad(set_to_none=True)
        selection=ValidationSelection();selection.update(1,1.)
        provenance={'scope':'TEST_FIXTURE_ONLY'}
        payload=ck.make_payload(model,optimizer,provenance,selection,
            {'scenes':10455,'steps':5228,'N_valid':10455*3430,'exactly_once':True},
            {'scenes':10501,'forwards':1313,'N_valid':10501*3430,'global_val_core_loss':1.},
            {},{'fixture':'simulated complete epoch metadata; not a formal run'})
        return model,optimizer,payload,provenance

    def test_roundtrip_and_provenance_before_application(self):
        with tempfile.TemporaryDirectory() as temp:
            model,opt,p,expected=self.fixture();store=ck.CheckpointStore(Path(temp)/'states',Path(temp)/'records','B0_MATCHED_V2','fixture',scope='TEST_FIXTURE_ONLY')
            store.save(p,expected,lambda *_:{'status':'PASS'},True);ref=store.last()
            before=state_digest(model.state_dict())
            with self.assertRaises(ValueError):ck.apply_verified(ref,{'wrong':True},model,opt)
            self.assertEqual(before,state_digest(model.state_dict()))
            ck.apply_verified(ref,expected,model,opt)

    def test_half_epoch_rejected(self):
        _,_,p,e=self.fixture();p['validation_completed']=False
        with self.assertRaises(ValueError):ck.validate_payload(p,e)

    def test_state_digest_tamper(self):
        _,_,p,e=self.fixture();p['model']['weight'][0,0]+=1
        with self.assertRaises(ValueError):ck.validate_payload(p,e)

    def test_permutation_tamper(self):
        _,_,p,e=self.fixture();p['next_permutation_sha256']='0'*64
        with self.assertRaises(ValueError):ck.validate_payload(p,e)

    def test_audit_failure_does_not_publish_last(self):
        with tempfile.TemporaryDirectory() as temp:
            _,_,p,e=self.fixture();store=ck.CheckpointStore(Path(temp)/'states',Path(temp)/'records','B0_MATCHED_V2','fixture',scope='TEST_FIXTURE_ONLY')
            with self.assertRaises(ValueError):store.save(p,e,lambda *_:{'status':'FAIL'},True)
            self.assertFalse((store.public/'checkpoint_registry.json').exists())
            self.assertTrue((store.root/'epoch_001.pt').exists())

    def test_retry_uses_new_attempt_without_overwriting_orphan(self):
        with tempfile.TemporaryDirectory() as temp:
            _,_,p,e=self.fixture();root=Path(temp)/'states';public=Path(temp)/'records'
            first=ck.CheckpointStore(root,public,'B0_MATCHED_V2','fixture',scope='TEST_FIXTURE_ONLY',attempt_id='run_20261007T000000_000001Z')
            with self.assertRaises(ValueError):first.save(p,e,lambda *_:{'status':'FAIL'},True)
            old=identity(first.write_root/'epoch_001.pt')
            second=ck.CheckpointStore(root,public,'B0_MATCHED_V2','fixture',scope='TEST_FIXTURE_ONLY',attempt_id='run_20261007T000000_000002Z')
            second.save(p,e,lambda *_:{'status':'PASS'},True)
            self.assertEqual(old,identity(first.write_root/'epoch_001.pt'))
            self.assertNotEqual(old['absolute_local_path'],second.last()['absolute_local_path'])

    def test_continuous_vs_resumed_exact_next_update(self):
        with tempfile.TemporaryDirectory() as temp:
            model,opt,p,e=self.fixture();store=ck.CheckpointStore(Path(temp)/'states',Path(temp)/'records','B0_MATCHED_V2','fixture',scope='TEST_FIXTURE_ONLY')
            store.save(p,e,lambda *_:{'status':'PASS'},True)
            def next_update():
                x=torch.randn(3,2);opt.zero_grad(set_to_none=True);lr=lr_for_update(5229,steps_per_epoch=5228)
                for g in opt.param_groups:g['lr']=lr
                loss=model(x).square().sum();loss.backward();grad=[v.grad.clone() for v in model.parameters()]
                norm=torch.nn.utils.clip_grad_norm_(model.parameters(),5.);opt.step()
                return state_digest((x,loss.detach(),grad,norm,model.state_dict(),opt.state_dict(),capture_rng()))
            a=next_update();ck.apply_verified(store.last(),e,model,opt);b=next_update();self.assertEqual(a,b)


class TinyQuantileModel(torch.nn.Module):
    def __init__(self):
        super().__init__();self.raw=torch.nn.Parameter(torch.zeros(33));self.logit=torch.nn.Parameter(torch.zeros(1))
    def forward(self,x,valid):
        from yuntapr.models.quantile_v2.parameterization import normalized_monotonic_quantiles,CandidateNumerics
        raw=self.raw.reshape(1,33,1,1).expand(len(x),33,100,100)
        q=normalized_monotonic_quantiles(raw[:,:32],raw[:,32:],numerics=CandidateNumerics(1e-4,1e-4))
        z=self.logit.reshape(1,1,1,1).expand(len(x),1,100,100)
        return LogDomainOutput(z,torch.sigmoid(z),q)


class UpdateIsolationTests(unittest.TestCase):
    def batch(self):
        from yuntapr.data.dataset_b1 import TemporalBatch
        return TemporalBatch(torch.ones(1,1,501,501),torch.ones(1,1,501,501,dtype=torch.bool),
            torch.ones(1,1,100,100),torch.ones(1,1,100,100,dtype=torch.bool),mask().reshape(1,1,100,100),['fixture'],[0])

    def test_observer_on_off_update_and_rng_bit_exact(self):
        result=[]
        for enabled in (False,True):
            seed_reproducibility();model=TinyQuantileModel();opt=torch.optim.AdamW(model.parameters(),foreach=False,fused=False)
            counter=Counters('TEST_FIXTURE_ONLY');observer=UpperTailDiagnostics(mask(),'TRAIN') if enabled else None
            with patch.object(torch,'expm1',side_effect=AssertionError('No physical conversion')):
                metrics,_=f.update(model,opt,self.batch(),1,counter,observer)
            result.append(state_digest((metrics,model.state_dict(),opt.state_dict(),capture_rng())))
        self.assertEqual(result[0],result[1])

    def test_nonfinite_gradient_never_steps(self):
        model=TinyQuantileModel();opt=torch.optim.AdamW(model.parameters(),foreach=False,fused=False)
        model.raw.register_hook(lambda grad:torch.full_like(grad,float('nan')))
        counter=Counters('TEST_FIXTURE_ONLY')
        with self.assertRaises(FloatingPointError):f.update(model,opt,self.batch(),1,counter)
        self.assertEqual(counter.OPTIMIZER_STEPS,0);self.assertEqual(counter.BACKWARD_CALLS,1)

    def test_singleton_actual_lr_and_denominator(self):
        model=TinyQuantileModel();opt=torch.optim.AdamW(model.parameters(),foreach=False,fused=False)
        counter=Counters('TEST_FIXTURE_ONLY');metrics,_=f.update(model,opt,self.batch(),5228,counter)
        self.assertEqual(metrics['LR'],1e-4);self.assertEqual(metrics['actual_denominator'],3430)

    def test_high_finite_qlog_risk_does_not_stop_update(self):
        model=TinyQuantileModel()
        with torch.no_grad():model.raw[-1]=800.
        opt=torch.optim.AdamW(model.parameters(),foreach=False,fused=False);counter=Counters('TEST_FIXTURE_ONLY')
        observer=UpperTailDiagnostics(mask(),'TRAIN')
        f.update(model,opt,self.batch(),1,counter,observer)
        self.assertEqual(counter.OPTIMIZER_STEPS,1);self.assertTrue(observer.report()['YUNNAN_INSIDE']['FP64_PHYSICAL_OVERFLOW_RISK'])


if __name__=='__main__':unittest.main()
