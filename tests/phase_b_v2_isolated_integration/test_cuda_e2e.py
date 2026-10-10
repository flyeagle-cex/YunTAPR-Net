"""Six complete model cases, synthetic batch=2 only; never an optimizer step."""
import gc
import time
import pytest
import torch
from yuntapr.losses.total_loss import b0_core_loss
from yuntapr.training.phase_a_protocol import state_digest
from yuntapr.experimental.phase_b_v2_integration.adapter import forward_synthetic, loss_from_output
from yuntapr.experimental.phase_b_v2_integration.initialization import fresh_paired_models, seeded_environment
from yuntapr.experimental.phase_b_v2_integration.resources import resource_snapshot, require_resources
from yuntapr.experimental.phase_b_v2_integration import SCOPE


def gradient_evidence(model):
    named = list(model.named_parameters())
    assert all(p.grad is not None and p.grad.shape == p.shape and p.grad.dtype == torch.float32
               and bool(torch.isfinite(p.grad).all()) for _, p in named)
    norms = {name: float(torch.linalg.vector_norm(p.grad.detach().double()).cpu()) for name, p in named}
    return {"parameter_tensors": len(named), "missing_gradients": 0, "nonfinite_gradients": 0,
            "all_shapes_and_dtypes_match": True, "norms": norms,
            "zero_gradient_tensors": [name for name, value in norms.items() if value == 0]}


@pytest.mark.parametrize("kind", ["B0_MATCHED_V2", "B1_V2"])
@pytest.mark.parametrize("arm", ["E0", "E1", "E2"])
def test_full_frozen_model_synthetic_forward_backward(pair, record, kind, arm):
    admission = resource_snapshot(full_backward=True)
    require_resources(admission)  # before either full model constructor
    with seeded_environment(2026):
        models, proof = fresh_paired_models(2026)
        model = models.pop(kind)
        del models  # only the selected architecture is moved to GPU
        model = model.to("cuda:0").train()
        batch = pair[kind].to("cuda:0")
        initial_sha = state_digest(model.state_dict())
        assert initial_sha == proof["state_sha256"][kind]
        raw_head = {}
        def inspect_raw(module, inputs, output):
            raw_head.update(shape=list(output.shape), dtype=str(output.dtype))
        hook = model.heads.quantile.register_forward_hook(inspect_raw)
        torch.cuda.synchronize()
        torch.cuda.reset_peak_memory_stats()
        started = time.perf_counter()
        output, loss = forward_synthetic(model, batch, kind, arm)
        torch.cuda.synchronize()
        forward_loss_seconds = time.perf_counter() - started
        hook.remove()
        assert raw_head == {"shape": [2, 33, 100, 100], "dtype": "torch.float32"}

        # Controlled arm checks use these same outputs, no extra model inference.
        alternatives = {candidate: loss_from_output(output, batch, kind, candidate) for candidate in ("E0", "E1", "E2")}
        assert all(torch.equal(value.s_qr, alternatives["E0"].s_qr) for value in alternatives.values())
        assert all(torch.equal(value.scientific_conditional_pinball, alternatives["E0"].scientific_conditional_pinball)
                   for value in alternatives.values())
        adjoints = {candidate: torch.autograd.grad(value.training_objective,
                    (output.rain_logit, output.conditional_quantiles_log), retain_graph=True)
                    for candidate, value in alternatives.items()}
        torch.testing.assert_close(adjoints["E2"][0], adjoints["E0"][0], rtol=0, atol=0)
        torch.testing.assert_close(adjoints["E2"][1], 2 * adjoints["E0"][1], rtol=0, atol=0)
        torch.testing.assert_close(adjoints["E1"][1], adjoints["E0"][1], rtol=0, atol=0)
        adjoint_record = {candidate: {"occurrence_norm": float(g[0].double().norm()),
                                     "quantile_norm": float(g[1].norm())} for candidate, g in adjoints.items()}
        del adjoints, alternatives
        torch.cuda.synchronize()
        started = time.perf_counter()
        loss.training_objective.backward(retain_graph=arm == "E0")
        torch.cuda.synchronize()
        backward_seconds = time.perf_counter() - started
        gradients = gradient_evidence(model)
        primary_peak_allocated = torch.cuda.max_memory_allocated()
        primary_peak_reserved = torch.cuda.max_memory_reserved()
        compatibility = {"performed": False, "reason": "Full original-loss comparison is assigned to E0 only"}

        if arm == "E0":
            candidate_gradients = {name: p.grad.detach().cpu().clone() for name, p in model.named_parameters()}
            model.zero_grad(set_to_none=True)
            with torch.autocast("cuda", dtype=torch.bfloat16):
                reference = b0_core_loss(output, batch.rate, batch.reference_valid, batch.region_mask,
                                         focal_alpha=.5, focal_gamma=2., quantile_axis_reduction="mean")
            torch.testing.assert_close(loss.training_objective, reference.total, rtol=8e-7, atol=1e-8)
            torch.testing.assert_close(loss.s_occ / loss.n_valid, reference.occurrence, rtol=8e-7, atol=1e-8)
            torch.testing.assert_close(loss.s_qr / loss.n_valid, reference.conditional_quantile, rtol=1e-12, atol=1e-14)
            torch.cuda.synchronize()
            started_reference = time.perf_counter()
            reference.total.backward()
            torch.cuda.synchronize()
            reference_backward_seconds = time.perf_counter() - started_reference
            differences = {}
            for name, p in model.named_parameters():
                actual = p.grad.detach().cpu()
                torch.testing.assert_close(actual, candidate_gradients[name], rtol=8e-7, atol=1e-8)
                differences[name] = float((actual - candidate_gradients[name]).abs().max())
            compatibility = {"performed": True, "status": "PASS", "loss_abs_difference":
                float((reference.total.detach() - loss.training_objective.detach()).abs()),
                "maximum_parameter_gradient_abs_difference": max(differences.values()),
                "parameter_gradient_rtol": 8e-7, "parameter_gradient_atol": 1e-8,
                "reference_backward_seconds": reference_backward_seconds,
                "scope": "Same actual output graph, original loss under frozen BF16 autocast; no optimizer"}
            del candidate_gradients, reference

        final_sha = state_digest(model.state_dict())
        assert final_sha == initial_sha
        assert not loss.execution_authorization
        record(f"{arm}_{kind}", {"scope": SCOPE, "status": "SYNTHETIC_INTEGRATION_PASS",
            "model": kind, "arm": arm, "seed": 2026, "batch_size": 2,
            "input_shape": list(batch.x.shape), "target_shape": list(batch.rate.shape),
            "qlog_shape": list(output.conditional_quantiles_log.shape), "raw_quantile_head": raw_head,
            "precision": {"parameters": "float32", "occurrence": str(output.rain_logit.dtype),
                          "qlog_and_pinball": str(output.conditional_quantiles_log.dtype), "TF32": False},
            "synthetic_arithmetic_not_performance": {"S_occ": float(loss.s_occ.detach()),
                "S_qr_unweighted": float(loss.s_qr.detach()), "weighted_objective": float(loss.training_objective.detach()),
                "N_valid": loss.n_valid, "N_rain": loss.n_rain,
                "unweighted_conditional_mean": float(loss.scientific_conditional_pinball.detach())},
            "same_output_arm_adjoint_norms": adjoint_record, "gradients": gradients,
            "E0_original_loss_compatibility": compatibility,
            "resource_admission": admission, "synthetic_measurement": {
                "forward_and_loss_seconds": forward_loss_seconds, "selected_loss_backward_seconds": backward_seconds,
                "primary_peak_allocated_bytes": primary_peak_allocated, "primary_peak_reserved_bytes": primary_peak_reserved,
                "complete_case_peak_allocated_bytes": torch.cuda.max_memory_allocated(),
                "complete_case_peak_reserved_bytes": torch.cuda.max_memory_reserved(),
                "includes_same_output_adjoint_checks": True, "cold_one_batch_not_training_throughput": True},
            "fresh_initial_state_sha256": initial_sha, "after_backward_state_sha256": final_sha,
            "parameters_unchanged_after_backward": True, "full_model_forward_calls": 1,
            "full_model_backward_calls": 2 if arm == "E0" else 1,
            "optimizer_steps": 0, "checkpoint_reads_or_writes": 0, "actual_data_reads": 0,
            "FORMAL_SCIENTIFIC_EXECUTION_AUTHORIZED": False})
        del model, batch, output, loss
        gc.collect()
        torch.cuda.empty_cache()
