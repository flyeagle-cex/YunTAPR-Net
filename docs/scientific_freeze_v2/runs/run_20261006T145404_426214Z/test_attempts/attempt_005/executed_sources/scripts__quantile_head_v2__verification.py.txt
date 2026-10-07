"""Disposable synthetic numerical evidence; no raw dataset or trained weights."""
import gc
import math
from pathlib import Path
import torch
from torch.nn import functional as F
from yuntapr.models.b0 import B0Model
from yuntapr.models.quantile_v2.legacy_path import LegacyLogDomainFixture
from yuntapr.models.quantile_v2.models import B0MatchedV2, B1V2
from yuntapr.models.quantile_v2.parameterization import CandidateNumerics, normalized_monotonic_quantiles
from yuntapr.models.quantile_v2.outputs import physical_risk
from yuntapr.losses.total_loss import b0_core_loss
from yuntapr.training.phase_a_protocol import (parameter_groups, seed_reproducibility,
    capture_rng, restore_rng, state_digest, lr_for_update)

RESULTS = {}
NUMERICS = CandidateNumerics(1e-4, 1e-4)  # User-approved engineering candidate ONLY.


def optimizer(model):
    groups, _ = parameter_groups(model, check_counts=False)
    return torch.optim.AdamW(groups, lr=1e-4, betas=(.9,.999), eps=1e-8,
                            foreach=False, fused=False, amsgrad=False, maximize=False,
                            capturable=False, differentiable=False)


def equivalence(device):
    seed_reproducibility()
    base = B0Model()
    initial = {k:v.clone() for k,v in base.state_dict().items()}
    del base
    rng = capture_rng()
    generator = torch.Generator().manual_seed(1801)
    batches = []
    for count in (2,1):
        x = torch.randn((count,1,501,501), generator=generator).to(device)
        valid = torch.ones_like(x, dtype=torch.bool)
        y = torch.full((count,1,100,100), 2., device=device)
        imerg = torch.ones_like(y, dtype=torch.bool)
        mask = torch.zeros_like(imerg); mask.flatten(1)[:,:3430] = True
        batches.append((x,valid,y,imerg,mask))
    records = []
    expected = None
    for decoupled in (False, True):
        model = (LegacyLogDomainFixture(test_fixture_only=True) if decoupled else B0Model()).to(device)
        model.load_state_dict(initial)
        opt = optimizer(model)
        restore_rng(rng)
        current = []
        for step, ((x,valid,y,imerg,mask), update) in enumerate(zip(batches,(1,5228))):
            opt.zero_grad(set_to_none=True)
            lr = lr_for_update(update, steps_per_epoch=5228)
            for group in opt.param_groups: group['lr'] = lr
            with torch.autocast(device.type, dtype=torch.bfloat16, enabled=device.type=='cuda'):
                output = model(x,valid)
                loss = b0_core_loss(output,y,imerg,mask,focal_alpha=.5,focal_gamma=2.,quantile_axis_reduction='mean')
            assert loss.valid_supervised_count == x.shape[0]*3430
            if not decoupled:
                assert torch.isfinite(output.conditional_quantiles_physical).all()
            else:
                assert not hasattr(output,'conditional_quantiles_physical')
                assert torch.equal(output.conditional_quantiles_log.detach().cpu(),expected[step]['qlog'])
                assert torch.equal(loss.total.detach().cpu(),expected[step]['loss_tensor'])
            loss.total.backward()
            grad_pre = {n:p.grad for n,p in model.named_parameters()}
            assert all(p.grad is not None and torch.isfinite(p.grad).all() for p in model.parameters())
            grad_before = state_digest(grad_pre)
            pre = torch.nn.utils.clip_grad_norm_(model.parameters(),5.,error_if_nonfinite=True)
            grad_after = state_digest({n:p.grad for n,p in model.named_parameters()})
            opt.step()
            row = {'batch':x.shape[0], 'update':update, 'LR':lr,
                   'qlog':output.conditional_quantiles_log.detach().cpu().clone(),
                   'loss_tensor':loss.total.detach().cpu().clone(),
                   'denominator':loss.valid_supervised_count,
                   'qlog_sha256':state_digest(output.conditional_quantiles_log),
                   'loss_sha256':state_digest(loss.total),
                   'gradients_before_clip_sha256':grad_before,
                   'gradients_after_clip_sha256':grad_after,
                   'pre_clip_norm':float(pre),
                   'optimizer_state_sha256':state_digest(opt.state_dict()),
                   'model_state_after_update_sha256':state_digest(model.state_dict()),
                   'RNG_state_sha256':state_digest(capture_rng())}
            if decoupled:
                for key,value in row.items():
                    if key not in ('qlog','loss_tensor'): assert value == expected[step][key], key
            current.append(row)
            del output,loss,grad_pre
        if not decoupled: expected = current
        records.append([{k:v for k,v in row.items() if k not in ('qlog','loss_tensor')} for row in current])
        del opt,model,current
        gc.collect()
        if device.type == 'cuda': torch.cuda.empty_cache()
    del batches,initial,expected
    result = {'description':'exact equivalence（精确等价性）：正常 synthetic fixture（合成测试夹具）中仅移除未参与核心损失的物理生成。',
              'device':str(device),'autocast':'BF16' if device.type=='cuda' else 'DISABLED_FP32',
              'TEST_FIXTURE_ONLY':True,
              'qlog_loss_gradients_optimizer_model_RNG_exact':True,
              'comparison_tolerance':0,'paths':records,'engineering_optimizer_steps':4,
              'formal_optimizer_steps_added':0,'historical_checkpoint_loaded':False,
              'temporary_models_optimizers_destroyed':True}
    RESULTS['a_path_equivalence_'+device.type] = result
    return result


def extreme_stress():
    levels = (-1e4,-1e3,-100.,-50.,0.,50.,100.,1e3,1e4)
    report = []
    for dtype in (torch.float32,torch.float64):
        generator = torch.Generator().manual_seed(26006)
        # 50,000 independently mixed scene-pixels plus all 81 constant combinations.
        n = 50000
        values = torch.tensor(levels,dtype=dtype)
        a = values[torch.randint(0,len(levels),(1,32,1,n),generator=generator)].requires_grad_()
        s = values[torch.randint(0,len(levels),(1,1,1,n),generator=generator)].requires_grad_()
        q = normalized_monotonic_quantiles(a,s,numerics=NUMERICS)
        q.mean().backward()
        assert torch.isfinite(a.grad).all() and torch.isfinite(s.grad).all()
        # Parenthesization must match the formula used in q32 exactly.
        assert torch.equal(q[:,-1:],math.log1p(.1)+(F.softplus(s.double())+NUMERICS.epsilon_span))
        risk = physical_risk(q)
        for allocation in levels:
            for span in levels:
                aa=torch.full((1,32,1,1),allocation,dtype=dtype,requires_grad=True)
                ss=torch.full((1,1,1,1),span,dtype=dtype,requires_grad=True)
                qq=normalized_monotonic_quantiles(aa,ss,numerics=NUMERICS)
                qq.sum().backward()
                assert torch.isfinite(aa.grad).all() and torch.isfinite(ss.grad).all()
        report.append({'raw_dtype':str(dtype),'transform_dtype':str(q.dtype),'mixed_scene_pixels':n,
                       'raw_allocation_values':32*n,'constant_cases':81,'all_requested_cases_pass':True,
                       'gradient_finite':True, **risk})
    RESULTS['v2_extreme_stress'] = {'levels':list(levels),'cases':report,'all_required_cases_pass':True}
    return RESULTS['v2_extreme_stress']


def model_identity():
    rows = {}
    models = {}
    for label,factory in (('B0_MATCHED_V2',B0MatchedV2),('B1_V2',B1V2)):
        seed_reproducibility(); model=factory(numerics=NUMERICS)
        groups,evidence=parameter_groups(model,check_counts=False)
        seed_reproducibility(); repeated=factory(numerics=NUMERICS)
        assert state_digest(model.state_dict()) == state_digest(repeated.state_dict())
        rows[label]={'parameters':evidence['counts'],'head_parameters':sum(p.numel() for p in model.heads.parameters()),
                     'initial_state_sha256':state_digest(model.state_dict()),'fresh_replay_exact':True}
        del repeated,groups
        models[label]=model
    a,b=models['B0_MATCHED_V2'],models['B1_V2']
    assert type(a.heads) is type(b.heads)
    aa,bb=a.state_dict(),b.state_dict()
    different={k for k in aa if aa[k].shape != bb[k].shape}
    assert different == {'backbone.enc0.conv1.weight','backbone.enc0.skip.weight'}
    native_head_equal=all(torch.equal(a.heads.state_dict()[k],b.heads.state_dict()[k]) for k in a.heads.state_dict())
    input_before={k:state_digest(bb[k]) for k in different}
    # Study the v1 SAME-NAME/SAME-SHAPE fresh pairing policy in a disposable
    # fixture only. No trained weights, optimizer state or formal initializer.
    with torch.no_grad():
        for key in aa:
            if key not in different: bb[key].copy_(aa[key])
    assert all(torch.equal(aa[k],bb[k]) for k in aa if k not in different)
    assert input_before=={k:state_digest(bb[k]) for k in different}
    result={'description':'fresh initialization（全新初始化）与 paired comparison（配对比较）工程身份；seed（随机种子）2026 仅是未冻结候选。',
            'models':rows,'same_head_family':True,'native_unpaired_head_parameters_bit_identical':native_head_equal,
            'head_parameters_bit_identical_in_disposable_paired_fixture':True,
            'pairing_policy':'CANDIDATE_V1_FRESH_SAME_NAME_SAME_SHAPE_COPY_TEST_FIXTURE_ONLY',
            'B1_native_input_kernels_unchanged':True,
            'only_shape_differences':sorted(different),'parameter_count_difference':2400,
            'seed_candidate':2026,'seed_scientifically_approved':False,
            'historical_checkpoint_loaded':False,'formal_initializer_created':False}
    RESULTS['model_identity']=result
    del models,a,b,aa,bb
    gc.collect()
    return result


def full_chain(count):
    """Actual CUDA native-frame -> SP04 -> v2 -> unchanged loss -> gradients."""
    from unittest.mock import patch
    rows=[]
    for label,cls,frames in (('B0_MATCHED_V2',B0MatchedV2,1),('B1_V2',B1V2,6)):
        seed_reproducibility();model=cls(numerics=NUMERICS).cuda()
        generator=torch.Generator().manual_seed(6326)
        x=torch.randn(count,frames,501,501,generator=generator).cuda()
        native_valid=torch.ones_like(x,dtype=torch.bool)
        y=torch.full((count,1,100,100),2.,device='cuda');valid=torch.ones_like(y,dtype=torch.bool)
        mask=torch.zeros_like(valid);mask.flatten(1)[:,:3430]=True
        with patch.object(torch,'expm1',side_effect=AssertionError('No implicit physical transform')):
            with torch.autocast('cuda',dtype=torch.bfloat16):
                output=model(x,native_valid)
                loss=b0_core_loss(output,y,valid,mask,focal_alpha=.5,focal_gamma=2.,quantile_axis_reduction='mean')
            assert loss.valid_supervised_count==count*3430 and torch.isfinite(loss.total)
            loss.total.backward()
        assert all(p.grad is not None and torch.isfinite(p.grad).all() for p in model.parameters())
        assert (model.heads.quantile.weight.grad[:32]!=0).any()
        assert (model.heads.quantile.weight.grad[32:]!=0).any()
        assert (model.backbone.enc0.conv1.weight.grad!=0).any()
        pre=torch.nn.utils.clip_grad_norm_(model.parameters(),5.,error_if_nonfinite=True)
        rows.append({'model':label,'batch':count,'actual_denominator':loss.valid_supervised_count,
                     'loss':float(loss.total.detach()),'pre_clip_norm':float(pre),
                     'all_parameter_gradients_finite':True,'backbone_allocation_span_nonzero_gradients':True,
                     'optimizer_steps':0,'checkpoint_loaded':False,'TEST_FIXTURE_ONLY':True,
                     'physical_risk':physical_risk(output.conditional_quantiles_log)})
        del model,x,native_valid,y,valid,mask,output,loss
        gc.collect();torch.cuda.empty_cache()
    RESULTS['v2_full_chain_batch_'+str(count)]=rows
    return rows
