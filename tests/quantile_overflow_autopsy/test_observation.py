"""TEST_FIXTURE_ONLY: disposable synthetic models, never the formal LAST."""
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[2]
sys.path[:0]=[str(ROOT/'scripts'),str(ROOT/'src'),str(ROOT)]
import gc
import math
import numpy as np
import unittest
import torch
from quantile_autopsy_v1 import common as c
from quantile_autopsy_v1.observer import stats,norm,overflow_boundaries,Observer
from quantile_autopsy_v1.replay import numpy_stats,ReplayDataset
from yuntapr.models.monotonic_quantiles import monotonic_quantiles
from yuntapr.models.probability_heads import ProbabilityHeads

def test_float64_overflow_can_have_finite_strict_monotonic_qlog():
    raw=torch.full((1,32,1,1),23.,dtype=torch.float32)
    q=monotonic_quantiles(raw,.1,epsilon_mono=6e-8,accumulation_dtype=torch.float64)
    assert torch.isfinite(q).all() and (q[:,1:]>q[:,:-1]).all()
    assert not torch.isfinite(torch.expm1(q)).all()
    assert overflow_boundaries(float(q.max()))['float64']['overflow_margin']>0

def test_nonfinite_raw_rejected_before_transform():
    raw=torch.full((1,32,1,1),float('nan'))
    with unittest.TestCase().assertRaisesRegex(FloatingPointError,'nonfinite raw'):
        monotonic_quantiles(raw,.1,accumulation_dtype=torch.float64)

def test_physical_guard_is_still_executed_in_fixture():
    heads=ProbabilityHeads(48,.1,epsilon_mono=6e-8,accumulation_dtype=torch.float64)
    with torch.no_grad():
        heads.quantile.weight.zero_();heads.quantile.bias.fill_(23.)
    with unittest.TestCase().assertRaisesRegex(FloatingPointError,'QUANTILE_PHYSICAL_OVERFLOW'):
        heads(torch.ones((1,48,100,100)))

def test_mathematical_limits():
    boundaries=overflow_boundaries(720.)
    assert boundaries['float64']['log1p_finfo_max']==math.log1p(np.finfo(np.float64).max)
    assert boundaries['float32']['log1p_finfo_max']==math.log1p(np.finfo(np.float32).max)

def test_observation_does_not_mutate_or_attach_gradient():
    x=torch.tensor([1.,-2.,3.],requires_grad=True);before=x.clone()
    result=stats(x);assert torch.equal(x,before) and x.grad is None
    assert math.isclose(result['std'],np.std([1.,-2.,3.]),rel_tol=1e-12)
    assert math.isclose(norm([x]),math.sqrt(14),rel_tol=1e-12)

def test_numpy_input_observation_no_mutation():
    x=np.array([230,270,310],dtype=np.float32);before=x.copy()
    assert numpy_stats(x)['mean']==270 and np.array_equal(x,before)

def test_reconciliation_stops_on_any_mismatch(field):
    ref={'sample_ids':['a','b'],'LR':1e-4,'loss':.25,'pre_clip_norm':2.,'post_clip_norm':2.,
         'actual_denominator':6860,'clipped':False,'update':41913}
    actual=ref.copy();actual[field]=['b','a'] if field=='sample_ids' else True if field=='clipped' else ref[field]+1e-12
    if field in ('actual_denominator','update'):actual[field]=ref[field]+1
    with unittest.TestCase().assertRaisesRegex(ValueError,'REPRODUCTION_FAILURE'):c.exact_reconcile(ref,actual)

def test_reconciliation_excludes_wall_time_only():
    ref={'sample_ids':['a','b'],'LR':1e-4,'loss':.25,'pre_clip_norm':2.,'post_clip_norm':2.,
         'actual_denominator':6860,'clipped':False,'update':41913,'wall_seconds':1.}
    assert len(c.exact_reconcile(ref,{**ref,'wall_seconds':9.}))==8

def test_2025_source_hard_reject_without_open(source,kind):
    from yuntapr.data.dataset_b1 import guard_source
    with unittest.TestCase().assertRaisesRegex(ValueError,'Forbidden raw date'):guard_source(source,kind)

def test_cuda_two_update_frozen_path_bit_exact_with_observer():
    import paired_extended_v1 as x
    from yuntapr.models.b0 import B0Model
    from yuntapr.data.dataset_b1 import TemporalBatch
    from yuntapr.training import paired_phase_a as frozen
    from yuntapr.training.phase_a_protocol import seed_reproducibility,state_digest,capture_rng,restore_rng
    assert torch.cuda.is_available(), 'Actual CUDA fixture gate is mandatory'
    seed_reproducibility();cpu_model=B0Model()
    initial={k:v.clone() for k,v in cpu_model.state_dict().items()};del cpu_model
    rng=capture_rng();generator=torch.Generator().manual_seed(12345)
    mask=torch.zeros((2,1,100,100),dtype=torch.bool);mask.flatten(1)[:,:3430]=True
    batch=TemporalBatch(torch.randn((2,1,501,501),generator=generator).cuda(),
        torch.ones((2,1,501,501),dtype=torch.bool,device='cuda'),
        torch.full((2,1,100,100),2.,device='cuda'),torch.ones((2,1,100,100),dtype=torch.bool,device='cuda'),
        mask.cuda(),['SYNTHETIC_ONLY_A','SYNTHETIC_ONLY_B'],[0,1])
    results=[]
    for observe in (False,True):
        model=B0Model().cuda();model.load_state_dict(initial);optimizer,_=frozen.optimizer_for(model,'B0_MATCHED')
        restore_rng(rng);model.train();observer=Observer(model);rows=[];outputs=[]
        from contextlib import nullcontext
        with observer.installed() if observe else nullcontext():
            for update in (41913,41914):
                if observe:observer.begin(batch,[],[],optimizer,update)
                metrics,out=x.execute_update(model,optimizer,batch,update)
                rows.append({**metrics,'sample_ids':batch.sample_ids})
                outputs.append(state_digest((out.rain_logit,out.rain_prob,out.conditional_quantiles_log,out.conditional_quantiles_physical,out.threshold_censored_mean)))
                if observe:
                    assert observer.current['qphysical_nonfinite_count']==0
                    assert 'gradients_pre_clip' in observer.current and 'gradients_post_clip' in observer.current
                    assert len(observer.current['qlog_per_tau_max'])==32
                observer.release();del out
        results.append({'rows':rows,'outputs':outputs,'model':state_digest(model.state_dict()),
            'optimizer':state_digest(optimizer.state_dict()),'rng':state_digest(capture_rng()),
            'grads':state_digest({k:p.grad for k,p in model.named_parameters()})})
        del observer,optimizer,model;gc.collect();torch.cuda.empty_cache()
    for expected,actual in zip(results[0]['rows'],results[1]['rows']):c.exact_reconcile(expected,actual)
    for key in ('outputs','model','optimizer','rng','grads'):assert results[0][key]==results[1][key]
    del batch,initial,results;gc.collect();torch.cuda.empty_cache()

def test_failure_capture_before_original_expm1_no_bypass():
    from types import SimpleNamespace
    from unittest.mock import patch
    class FixtureModel(torch.nn.Module):
        def __init__(self):
            super().__init__();self.projection=torch.nn.Identity()
            self.backbone=torch.nn.Module();self.backbone.dec0=torch.nn.Linear(1,1)
            self.heads=ProbabilityHeads(48,.1,epsilon_mono=6e-8,accumulation_dtype=torch.float64)
        def forward(self,x):return self.heads(self.projection(x))
    model=FixtureModel();optimizer=torch.optim.AdamW(model.parameters())
    with torch.no_grad():model.heads.quantile.weight.zero_();model.heads.quantile.bias.fill_(23.)
    y=torch.full((1,1,100,100),3.);valid=torch.ones_like(y,dtype=torch.bool)
    mask=torch.zeros_like(valid);mask.flatten()[-3430:]=True
    batch=SimpleNamespace(y_imerg=y,imerg_valid_mask=valid,yunnan_eval_mask=mask,sample_ids=['fixture'])
    record={'window_start':'2023-03-01T00:00:00+00:00','analysis_time':'2023-03-01T00:30:00+00:00',
            'imerg_day_path':'SYNTHETIC_ONLY','imerg_index':0}
    item={'index':0,'sample_id':'fixture','frames':[],'target_sha256':'SYNTHETIC',
          'normalization_sha256':'SYNTHETIC','engineering_input_observation':{'physical_K':{},'normalized':{}}}
    obs=Observer(model);obs.begin(batch,[item],[record],optimizer,50538)
    original=torch.expm1;observed=[]
    def delegate(value,*args,**kwargs):
        assert obs.failure is not None and obs.failure['captured_before_expm1']
        observed.append(True);return original(value,*args,**kwargs)
    with patch.object(torch,'expm1',delegate),obs.installed():
        with unittest.TestCase().assertRaisesRegex(FloatingPointError,'QUANTILE_PHYSICAL_OVERFLOW'):
            model(torch.ones((1,48,100,100)))
    assert observed==[True] and obs.failure['qlog_all_finite']
    assert obs.failure['read_only_log_objective_diagnostic']['all_finite']
    assert not obs.failure['Yunnan_mask'] and obs.failure['actual_denominator']==3430
    assert len(obs.failure['qlog_32_at_pixel'])==32 and len(obs.failure['target_feature_48_at_pixel'])==48
    assert obs.failure['qphysical_nonfinite_count']>0
    obs.release()


class ObservationTests(unittest.TestCase):
    """Each generated case is an independent named unittest, no external test package."""

for _name,_fn in list(globals().items()):
    if _name.startswith('test_') and _name not in ('test_reconciliation_stops_on_any_mismatch','test_2025_source_hard_reject_without_open'):
        setattr(ObservationTests,_name,lambda self,fn=_fn:fn())
for _field in ('sample_ids','LR','loss','pre_clip_norm','post_clip_norm','actual_denominator','clipped','update'):
    setattr(ObservationTests,'test_reconciliation_reject_'+_field,
        lambda self,field=_field:test_reconciliation_stops_on_any_mismatch(field))
for _kind,_source in [('B13',r'H:\葵花202303_202510\202503\bad.nc'),
    ('IMERG',r'F:\云南极端降水数据\raw\IMERG\IMERG_20250301.nc')]:
    setattr(ObservationTests,'test_2025_reject_'+_kind,
        lambda self,source=_source,kind=_kind:test_2025_source_hard_reject_without_open(source,kind))
del _name,_fn,_field,_kind,_source
