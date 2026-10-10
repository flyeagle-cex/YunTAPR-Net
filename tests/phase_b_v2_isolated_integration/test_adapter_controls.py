from dataclasses import replace
import math
import pytest
import torch
from yuntapr.models.quantile_v2.outputs import LogDomainOutput
from yuntapr.experimental.phase_b_v2_ablations.config import RunSpec, learning_rate_prefix
from yuntapr.experimental.phase_b_v2_ablations.readiness import FormalExecutionBlocked
from yuntapr.experimental.phase_b_v2_integration.adapter import loss_from_output, forward_synthetic
from yuntapr.experimental.phase_b_v2_integration.controls import (
    candidate_plan, audit_plan, isolated_run_id, synthetic_epoch_order, endpoint_boundary,
    reject_resume, reject_formal_start)
from yuntapr.experimental.phase_b_v2_integration.resources import require_resources, ResourceLimit
from yuntapr.experimental.phase_b_v2_integration.safety import reject_restricted_path


def output_fixture():
    logit = torch.zeros(2, 1, 100, 100, requires_grad=True)
    q = (math.log1p(.1) + torch.arange(1, 33, dtype=torch.float64).reshape(1, 32, 1, 1) / 32)
    return LogDomainOutput(logit, logit.sigmoid(), q.expand(2, 32, 100, 100).clone().requires_grad_())


@pytest.mark.parametrize("kind", ["B0_MATCHED_V2", "B1_V2"])
@pytest.mark.parametrize("arm", ["E0", "E1", "E2"])
def test_full_target_adapter_tensor_only(pair, kind, arm):
    out = output_fixture()
    loss = loss_from_output(out, pair[kind], kind, arm)
    assert loss.n_valid == 6860 and 0 < loss.n_rain < loss.n_valid
    assert loss.s_qr.dtype == torch.float64
    loss.training_objective.backward()
    assert out.rain_logit.grad is not None and torch.isfinite(out.rain_logit.grad).all()
    assert out.conditional_quantiles_log.grad is not None
    assert not loss.execution_authorization


def test_latest_frame_and_distinct_causal_slots(pair):
    a, b = pair["B0_MATCHED_V2"], pair["B1_V2"]
    assert torch.equal(a.x, b.x[:, -1:]) and a.sample_ids == b.sample_ids
    assert not torch.equal(b.x[:, 0], b.x[:, -1])
    assert torch.equal(a.rate, b.rate) and torch.equal(a.region_mask, b.region_mask)
    assert int((a.rate == torch.tensor(.1, dtype=torch.float32)).sum()) > 0


@pytest.mark.parametrize("defect", ["scope", "year", "ids", "duplicate", "slot_order", "batch", "native_shape",
                                   "reference_shape", "rate_dtype", "mask_dtype", "native_missing",
                                   "region_count", "reference_missing", "nan_input", "nan_rate", "device"])
def test_batch_rejects_before_forward(pair, defect):
    batch = pair["B1_V2"]
    if defect == "scope": batch = replace(batch, scope="FORMAL")
    elif defect == "year": batch = replace(batch, data_years=(2025,))
    elif defect == "ids": batch = replace(batch, sample_ids=("2023/real", "2024/real"))
    elif defect == "duplicate": batch = replace(batch, sample_ids=(batch.sample_ids[0],) * 2)
    elif defect == "slot_order": batch = replace(batch, slot_offsets=tuple(reversed(batch.slot_offsets)))
    elif defect == "batch": batch = replace(batch, x=batch.x[:1])
    elif defect == "native_shape": batch = replace(batch, x=batch.x[:, :, :500])
    elif defect == "reference_shape": batch = replace(batch, rate=batch.rate[:, :, :99])
    elif defect == "rate_dtype": batch = replace(batch, rate=batch.rate.double())
    elif defect == "mask_dtype": batch = replace(batch, reference_valid=batch.reference_valid.float())
    elif defect == "native_missing":
        mask = batch.native_valid.clone(); mask[0, 0, 0, 0] = False
        batch = replace(batch, native_valid=mask)
    elif defect == "region_count":
        mask = batch.region_mask.clone(); mask[0, 0, 0, 0] = False
        batch = replace(batch, region_mask=mask)
    elif defect == "reference_missing":
        mask = batch.reference_valid.clone(); mask[0, 0, 0, 0] = False
        batch = replace(batch, reference_valid=mask)
    elif defect == "nan_input":
        x = batch.x.clone(); x[0, 0, 0, 0] = float("nan"); batch = replace(batch, x=x)
    elif defect == "nan_rate":
        y = batch.rate.clone(); y[0, 0, 0, 0] = float("nan"); batch = replace(batch, rate=y)
    elif defect == "device": batch = replace(batch, rate=torch.empty_like(batch.rate, device="meta"))
    with pytest.raises(ValueError):
        forward_synthetic(None, batch, "B1_V2", "E0")


@pytest.mark.parametrize("defect", ["q_channels", "q_grid", "q_dtype", "occ_grid", "prob_support", "prob_relation", "output_type", "unknown_arm"])
def test_output_interface_rejections(pair, defect):
    out = output_fixture()
    if defect == "q_channels": out.conditional_quantiles_log = out.conditional_quantiles_log[:, :31]
    elif defect == "q_grid": out.conditional_quantiles_log = out.conditional_quantiles_log[:, :, :99]
    elif defect == "q_dtype": out.conditional_quantiles_log = out.conditional_quantiles_log.float()
    elif defect == "occ_grid": out.rain_logit = out.rain_logit[:, :, :99]
    elif defect == "prob_support": out.rain_prob = torch.full_like(out.rain_prob, 2.)
    elif defect == "prob_relation": out.rain_prob = torch.full_like(out.rain_prob, .3)
    elif defect == "output_type": out = {}
    with pytest.raises((ValueError, FloatingPointError)):
        loss_from_output(out, pair["B0_MATCHED_V2"], "B0_MATCHED_V2", "E9" if defect == "unknown_arm" else "E0")


@pytest.mark.parametrize("arm", ["E0", "E1", "E2"])
def test_plan_good_is_never_authorized(arm):
    run = RunSpec(arm, "B1_V2", 2026)
    result = audit_plan(candidate_plan(run))
    assert result["candidate_metadata_consistent"]
    assert result["run_id"].startswith("SYNTHETIC_ENGINEERING_ONLY__")
    assert not result["FORMAL_SCIENTIFIC_EXECUTION_AUTHORIZED"]


@pytest.mark.parametrize("field,value", [
    ("gamma", 9.), ("lambda_q", 2.), ("alpha", 1.), ("data_years", (2023, 2025)),
    ("epochs", 10), ("physical_batch", 1), ("accumulation", 2), ("drop_last", True),
    ("train_scenes", 10454), ("validation_scenes", 10500), ("qualification", "RELAXED"),
    ("normalization", "REFIT"), ("endpoint", "BEST"), ("scheduler_horizon", 9),
    ("scientific_approval", True), ("execution_authorization", {"approved": True})])
def test_candidate_plan_rejects_scope_changes(field, value):
    plan = candidate_plan(RunSpec("E0", "B0_MATCHED_V2", 2026))
    plan[field] = value
    with pytest.raises(ValueError): audit_plan(plan)


@pytest.mark.parametrize("claimed", [None, True, "APPROVED", "AUTHORIZED_TO_EXECUTE", {"approved": True, "researcher": "self"}])
def test_no_self_report_can_start_formal_execution(claimed):
    with pytest.raises(FormalExecutionBlocked): reject_formal_start(approval=claimed, execute=True)


@pytest.mark.parametrize("epoch", [0, 1, 8, 9])
def test_fixed_endpoint_boundary(epoch):
    value = endpoint_boundary(epoch)
    assert value["remaining_budget"] == (9 - epoch) * 5228
    assert value["next_epoch"] == (epoch + 1 if epoch < 9 else None)
    assert value["next_lr"] == (learning_rate_prefix(epoch * 5228 + 1) if epoch < 9 else None)
    assert value["formal_updates_executed"] == 0


@pytest.mark.parametrize("bad", [-1, 10, True, 9.0])
def test_outside_endpoint_rejected(bad):
    with pytest.raises(ValueError): endpoint_boundary(bad)


@pytest.mark.parametrize("seed", [2026, 2027, 2028])
def test_synthetic_order_deterministic_paired_and_complete(seed):
    ids = tuple(f"SYNTHETIC_ENGINEERING_ONLY/order_{i:05d}" for i in range(10455))
    results = [synthetic_epoch_order(ids, seed, epoch) for epoch in range(9)]
    for epoch, order in enumerate(results):
        assert order == synthetic_epoch_order(ids, seed, epoch)
        assert len(order) == len(set(order)) == 10455 and set(order) == set(ids)
    assert results[0] != results[1]


@pytest.mark.parametrize("defect", ["seed", "epoch", "duplicate", "real_ids"])
def test_order_rejects_bad_identity(defect):
    ids = tuple(f"SYNTHETIC_ENGINEERING_ONLY/order_{i:05d}" for i in range(3))
    if defect == "duplicate": ids = (ids[0],) * 2
    if defect == "real_ids": ids = ("2025/observation",)
    with pytest.raises(ValueError): synthetic_epoch_order(ids, 2030 if defect == "seed" else 2026, 9 if defect == "epoch" else 0)


def metadata_fixture():
    run = RunSpec("E0", "B0_MATCHED_V2", 2026).run_id
    meta = {k: "a" * 64 for k in ("last_sha256", "model_sha256", "optimizer_sha256", "rng_sha256",
                                 "scheduler_sha256", "code_sha256", "protocol_sha256", "data_sha256", "init_sha256")}
    meta.update(run_id=run, completed_epoch=1, retained_updates=5228,
                boundary="COMPLETED_TRAIN_AND_VALIDATION_EPOCH_ONLY", original_execution_reference="SYNTHETIC_REFERENCE_NOT_APPROVAL")
    expected = {k: meta[k] for k in ("run_id", "last_sha256", "code_sha256", "protocol_sha256", "data_sha256", "init_sha256")}
    return meta, expected


@pytest.mark.parametrize("defect", ["missing_approval", "self_reference", "sha", "partial", "updates", "run", "best", "unknown_epoch"])
def test_resume_has_no_state_application(defect):
    meta, expected = metadata_fixture()
    if defect == "sha": meta["last_sha256"] = "b" * 64
    if defect == "partial": meta["boundary"] = "TRAIN_ONLY"
    if defect == "updates": meta["retained_updates"] = 5227
    if defect == "run": meta["run_id"] = "HISTORICAL_B1"
    if defect == "unknown_epoch": meta["completed_epoch"] = None
    with pytest.raises((ValueError, FormalExecutionBlocked)):
        reject_resume(meta, expected, checkpoint_kind="BEST" if defect == "best" else "LAST",
                      resume_approval_reference="SYNTHETIC_FAKE_APPROVAL" if defect == "self_reference" else None)


@pytest.mark.parametrize("path", ["synthetic.nc", "synthetic.pt", "fictional/2025/metadata.json", "fictional.csv", "tensor.npy"])
def test_restricted_files_rejected_without_open(path):
    with pytest.raises(PermissionError): reject_restricted_path(path)


@pytest.mark.parametrize("resource", ["host_available_bytes", "workspace_free_bytes", "cuda_free_bytes"])
def test_resource_shortfall_rejects_no_fallback(resource):
    value = {"host_available_bytes": 20, "minimum_host_bytes": 10, "workspace_free_bytes": 20,
             "minimum_workspace_bytes": 10, "cuda_free_bytes": 20, "minimum_cuda_free_bytes": 10, "full_backward": True}
    value[resource] = 0
    with pytest.raises(ResourceLimit): require_resources(value)

