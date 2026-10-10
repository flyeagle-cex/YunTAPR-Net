"""New full-target boundary arithmetic; prior 91/6 suites are never selected."""
from dataclasses import replace
import pytest
import torch
from yuntapr.models.quantile_v2.outputs import LogDomainOutput
from yuntapr.training.phase_a_validation_v2 import LogDomainValidation
from yuntapr.experimental.phase_b_v2_ablations.config import get_config
from yuntapr.experimental.phase_b_v2_ablations.total import candidate_loss
from yuntapr.experimental.phase_b_v2_ablations.validation import ZeroValidPixelsError
from yuntapr.experimental.phase_b_v2_boundaries.boundary import (
    make_boundary_pair, losses_from_output, evaluation_components, aggregate_evaluation, verify_inherited_identity)
from yuntapr.experimental.phase_b_v2_boundaries.gradients import checked_gradients


def synthetic_output(size):
    logits = torch.zeros(size,1,100,100,dtype=torch.bfloat16,requires_grad=True)
    qlog = (torch.arange(1,33,dtype=torch.float64).reshape(1,32,1,1)/32+.2).expand(size,32,100,100).clone().requires_grad_()
    return LogDomainOutput(logits,logits.sigmoid(),qlog)


@pytest.mark.parametrize("size",[1,8,5])
@pytest.mark.parametrize("rain",["MIXED","EMPTY_RAIN"])
@pytest.mark.parametrize("arm",["E0","E1","E2"])
def test_tail_denominators_and_unweighted_metric(size,rain,arm):
    batch=make_boundary_pair(size,rain)["B0_MATCHED_V2"]
    output=synthetic_output(size)
    results=losses_from_output(output,batch,"B0_MATCHED_V2")
    loss=results[arm]
    rainy=(batch.rate > torch.tensor(.1,dtype=torch.float32)) & batch.region_mask
    assert loss.n_valid==3430*size and loss.n_rain==int(rainy.sum())
    torch.testing.assert_close(loss.training_objective,(loss.s_occ+get_config(arm).lambda_q*loss.s_qr)/loss.n_valid,rtol=0,atol=0)
    assert torch.equal(loss.s_qr,results["E0"].s_qr)
    if rain=="EMPTY_RAIN":
        assert loss.n_rain==0 and loss.s_qr==0 and loss.scientific_conditional_pinball is None
    else:
        assert torch.equal(loss.scientific_conditional_pinball,results["E0"].scientific_conditional_pinball)
    # Only training tail=1 receives autograd here; validation arithmetic remains forward-only.
    if size==1:
        loss.training_objective.backward()
        assert output.rain_logit.grad is not None and torch.isfinite(output.rain_logit.grad).all()
        assert output.conditional_quantiles_log.grad is not None and torch.isfinite(output.conditional_quantiles_log.grad).all()
        assert bool((output.conditional_quantiles_log.grad==0).all()) == (rain=="EMPTY_RAIN")
    components=evaluation_components(results,output=output,batch=batch)
    report=aggregate_evaluation([components])
    reference=LogDomainValidation(); reference.add(output,batch.rate,batch.reference_valid,batch.region_mask)
    assert components["S_occ_gamma2_unweighted"]==reference.report()["S_occ"]
    assert components["S_qr_unweighted"]==reference.report()["S_qr"]
    assert report["N_valid"]==size*3430
    assert report["synthetic_conditional_pinball"] is None if rain=="EMPTY_RAIN" else report["synthetic_conditional_pinball"]>0


@pytest.mark.parametrize("size",[1,8,5])
def test_fp32_threshold_counts_and_mask_exclusion(size):
    batch=make_boundary_pair(size,"MIXED")["B0_MATCHED_V2"]
    out=synthetic_output(size)
    base=losses_from_output(out,batch,"B0_MATCHED_V2")["E0"]
    rate=batch.rate.clone()
    rate[~batch.region_mask]=float("nan")
    # Low-level mask edge only, not a Q1 qualified model batch. The candidate cleans unused reference.
    low=candidate_loss(out.rain_logit,out.conditional_quantiles_log,rate,batch.reference_valid,batch.region_mask,config=get_config("E0"))
    assert low.n_rain==base.n_rain and torch.equal(low.s_qr,base.s_qr)
    equal=torch.tensor(.1,dtype=torch.float32)
    assert not bool(equal>equal) and bool(equal.double()>.1)  # exposes the cast-first bug
    assert bool(torch.nextafter(equal,torch.tensor(float("inf")))>equal)


@pytest.mark.parametrize("problem",["missing_native","missing_reference","zero_region","shape","rate64","nan_input","inf_rate","year2025","duplicate_ids","mode","slots"])
def test_boundary_stops_on_invalid_fixture(problem):
    batch=make_boundary_pair(1,"MIXED")["B0_MATCHED_V2"]
    if problem=="missing_native":
        tensor=batch.native_valid.clone(); tensor.flatten()[0]=False; batch=replace(batch,native_valid=tensor)
    elif problem=="missing_reference":
        tensor=batch.reference_valid.clone(); tensor.flatten()[0]=False; batch=replace(batch,reference_valid=tensor)
    elif problem=="zero_region": batch=replace(batch,region_mask=torch.zeros_like(batch.region_mask))
    elif problem=="shape": batch=replace(batch,rate=batch.rate[:,:,:99])
    elif problem=="rate64": batch=replace(batch,rate=batch.rate.double())
    elif problem=="nan_input":
        tensor=batch.x.clone(); tensor.flatten()[0]=float("nan"); batch=replace(batch,x=tensor)
    elif problem=="inf_rate":
        tensor=batch.rate.clone(); tensor.flatten()[0]=float("inf"); batch=replace(batch,rate=tensor)
    elif problem=="year2025": batch=replace(batch,data_years=(2025,))
    elif problem=="duplicate_ids": batch=replace(batch,sample_ids=())
    elif problem=="mode": batch=replace(batch,mode="VALIDATION_TAIL")
    else: batch=replace(batch,slot_offsets=(0,))
    with pytest.raises((ValueError,FloatingPointError)):
        batch.validate("B0_MATCHED_V2")


@pytest.mark.parametrize("size",[1,8,5])
@pytest.mark.parametrize("problem",["zero_valid","nonfinite_q","nonfinite_logit","q32_dtype"])
def test_invalid_loss_boundary_never_silently_repairs(size,problem):
    batch=make_boundary_pair(size,"MIXED")["B0_MATCHED_V2"]
    out=synthetic_output(size)
    if problem=="zero_valid":
        with pytest.raises(ZeroValidPixelsError):
            candidate_loss(out.rain_logit,out.conditional_quantiles_log,batch.rate,
                           torch.zeros_like(batch.reference_valid),batch.region_mask,config=get_config("E0"))
    else:
        if problem=="nonfinite_q":
            out.conditional_quantiles_log=out.conditional_quantiles_log.detach().clone()
            out.conditional_quantiles_log.flatten()[0]=float("nan")
        elif problem=="nonfinite_logit":
            out.rain_logit=out.rain_logit.detach().clone(); out.rain_logit.flatten()[0]=float("inf")
        else: out.conditional_quantiles_log=out.conditional_quantiles_log.float()
        with pytest.raises((ValueError,FloatingPointError)):
            losses_from_output(out,batch,"B0_MATCHED_V2")


def test_unequal_batch_aggregation_uses_sums_not_batch_means():
    template={"scope":"SYNTHETIC_ENGINEERING_ONLY","scientific_performance_evidence":False,"occurrence_gamma_for_common_core":2}
    a=dict(template,S_occ_gamma2_unweighted=8.,S_qr_unweighted=16.,N_valid=8,N_rain=4)
    b=dict(template,S_occ_gamma2_unweighted=10.,S_qr_unweighted=5.,N_valid=5,N_rain=1)
    result=aggregate_evaluation([a,b])
    assert result["synthetic_common_core"]==39/13 and result["synthetic_conditional_pinball"]==21/5
    assert result["synthetic_conditional_pinball"]!=(16/4+5)/2
    with pytest.raises(ValueError): aggregate_evaluation([dict(a,weighted_objective=3.)])


@pytest.mark.parametrize("problem",["missing","nan","dtype"])
def test_gradient_stop_does_not_mutate_or_retry(problem):
    model=torch.nn.Linear(2,1,bias=False)
    parameter=next(model.parameters()); before=parameter.detach().clone()
    if problem=="missing": parameter.grad=None
    elif problem=="nan": parameter.grad=torch.full_like(parameter,float("nan"))
    else: parameter.data=parameter.data.double(); parameter.grad=torch.ones_like(parameter)
    with pytest.raises(FloatingPointError): checked_gradients(model,empty_rain=False)
    assert torch.equal(parameter.detach().float(),before)


def test_inherited_bytes_without_old_test_rerun():
    assert verify_inherited_identity()==226
