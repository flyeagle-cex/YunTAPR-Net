"""Twelve artificial model cases; train1 backward, validation8/5 inference only."""
import gc
import json
import time
import pytest
import torch
from yuntapr.training.phase_a_protocol import state_digest
from yuntapr.losses.total_loss import b0_core_loss
from yuntapr.experimental.phase_b_v2_integration.initialization import fresh_paired_models, seeded_environment
from yuntapr.experimental.phase_b_v2_integration.resources import resource_snapshot, require_resources
from yuntapr.experimental.phase_b_v2_boundaries.boundary import (
    REPO, make_boundary_pair, forward_boundary, evaluation_components, aggregate_evaluation, verify_inherited_identity)
from yuntapr.experimental.phase_b_v2_boundaries.gradients import checked_gradients


@pytest.mark.parametrize("kind",["B0_MATCHED_V2","B1_V2"])
@pytest.mark.parametrize("size",[1,8,5])
@pytest.mark.parametrize("rain",["MIXED","EMPTY_RAIN"])
def test_frozen_boundary(kind,size,rain,record):
    name=f"B{size}_{rain}_{kind}"
    # Conservative existing GPU admission also applies to no-gradient validation.
    admission=resource_snapshot(full_backward=True)
    record(name+"_admission",{"planned_batch":size,"phase":"TRAIN" if size==1 else "VALIDATION",
                              "resource":admission,"threshold_role":"Engineering admission, not estimated memory need"})
    require_resources(admission)  # before full model construction; no fallback
    assert verify_inherited_identity()==226
    with seeded_environment(2026):
        models,proof=fresh_paired_models(2026)
        model=models.pop(kind); del models
        model=model.to("cuda:0").train(size==1)
        batch=make_boundary_pair(size,rain)[kind].to("cuda:0")
        before=state_digest(model.state_dict())
        old=json.loads((REPO/"docs/phase_b_v2_isolated_integration/v1/tests/cpu_attempt_002_evidence/actual_initialization_seed_2026.json").read_text())
        assert before==old["proofs"][0]["state_sha256"][kind]
        raw={}
        def capture(module,args,result): raw.update(shape=list(result.shape),dtype=str(result.dtype))
        hook=model.heads.quantile.register_forward_hook(capture)
        torch.cuda.synchronize(); torch.cuda.reset_peak_memory_stats()
        started=time.perf_counter()
        output,results=forward_boundary(model,batch,kind)
        torch.cuda.synchronize()
        forward_seconds=time.perf_counter()-started
        hook.remove()
        assert raw=={"shape":[size,33,100,100],"dtype":"torch.float32"}
        assert output.conditional_quantiles_log.shape==(size,32,100,100)
        assert all(loss.n_valid==size*3430 for loss in results.values())
        assert all(loss.n_rain==0 for loss in results.values()) if rain=="EMPTY_RAIN" else all(loss.n_rain>0 for loss in results.values())
        # Common frozen core uses gamma2 and unweighted sums regardless of candidate training condition.
        components=evaluation_components(results,output=output,batch=batch)
        common=aggregate_evaluation([components])
        with torch.inference_mode(mode=size!=1),torch.autocast("cuda",dtype=torch.bfloat16):
            original=b0_core_loss(output,batch.rate,batch.reference_valid,batch.region_mask,
                                  focal_alpha=.5,focal_gamma=2.,quantile_axis_reduction="mean")
        torch.testing.assert_close(results["E0"].training_objective,original.total,rtol=8e-7,atol=1e-8)
        compatibility_abs=float((results["E0"].training_objective.detach()-original.total.detach()).abs())
        del original
        evidence={}
        backward_calls=0
        for index,arm in enumerate(("E0","E1","E2")):
            loss=results[arm]
            expected=(loss.s_occ+({"E0":1,"E1":1,"E2":2}[arm])*loss.s_qr)/loss.n_valid
            torch.testing.assert_close(loss.training_objective,expected,rtol=0,atol=0)
            if size==1:
                model.zero_grad(set_to_none=True)
                torch.cuda.synchronize(); started=time.perf_counter()
                loss.training_objective.backward(retain_graph=index<2)
                torch.cuda.synchronize()
                backward_seconds=time.perf_counter()-started
                gradients=checked_gradients(model,empty_rain=rain=="EMPTY_RAIN")
                backward_calls+=1
            else:
                assert not loss.training_objective.requires_grad and not output.rain_logit.requires_grad
                assert all(p.grad is None for p in model.parameters())
                backward_seconds=None
                gradients={"not_executed":"Frozen validation inference_mode","all_parameter_grads_absent":True}
            evidence[arm]={"S_occ_training_unweighted":float(loss.s_occ.detach()),
                "S_qr_unweighted":float(loss.s_qr.detach()),"synthetic_weighted_training_objective":float(loss.training_objective.detach()),
                "N_valid":loss.n_valid,"N_rain":loss.n_rain,
                "synthetic_conditional_pinball_unweighted":float(loss.scientific_conditional_pinball.detach()) if loss.n_rain else None,
                "backward_seconds":backward_seconds,"gradients":gradients}
        if rain=="EMPTY_RAIN":
            assert results["E0"].s_qr==0 and results["E2"].training_objective==results["E0"].training_objective
        else:
            assert all(torch.equal(loss.scientific_conditional_pinball,results["E0"].scientific_conditional_pinball) for loss in results.values())
        after=state_digest(model.state_dict()); assert before==after
        record(name,{"scope":"SYNTHETIC_ENGINEERING_ONLY","status":"SYNTHETIC_BOUNDARY_PASS",
            "scientific_performance_evidence":False,"model":kind,"batch_size":size,"rain_case":rain,
            "phase":"TRAIN_TAIL" if size==1 else "VALIDATION_INFERENCE",
            "input_shape":list(batch.x.shape),"target_shape":list(batch.rate.shape),"qlog_shape":list(output.conditional_quantiles_log.shape),
            "raw_quantile_head":raw,"precision":{"parameters":"float32","occurrence":"bfloat16","raw_quantile":"float32","qlog":"float64","TF32":False},
            "N_valid":size*3430,"mask_role":batch.mask_role,"arms":evidence,"common_fixed_evaluation":common,
            "common_evaluation_components":components,"common_evaluation_numerator_dtype":"float64",
            "E0_original_loss_abs_difference":compatibility_abs,"E0_tolerance":{"rtol":8e-7,"atol":1e-8},
            "fresh_state_sha256":before,"after_state_sha256":after,"prior_seed2026_identity_matches":True,
            "nonpersistent_buffers_sha256":proof["buffers_sha256"][kind],
            "measurement":{"forward_and_three_losses_seconds":forward_seconds,
                "peak_allocated_bytes":torch.cuda.max_memory_allocated(),"peak_reserved_bytes":torch.cuda.max_memory_reserved(),
                "one_batch_cold_cache_and_extra_checks_not_training_throughput":True,
                "optimizer_or_checkpoint_memory_included":False},
            "full_model_forwards":1,"full_model_backwards":backward_calls,
            "optimizer_steps":0,"raw_data_reads":0,"checkpoint_reads_or_writes":0,
            "FORMAL_SCIENTIFIC_EXECUTION_AUTHORIZED":False})
        del model,batch,output,results,loss,expected
        gc.collect(); torch.cuda.empty_cache()
