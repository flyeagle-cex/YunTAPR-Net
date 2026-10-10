"""Closed configuration and metadata fixtures, never actual model states."""
from dataclasses import FrozenInstanceError, replace
import ast
import hashlib
import math
from pathlib import Path
import pytest
from yuntapr.experimental.phase_b_v2_ablations.config import AblationConfig, RunSpec, get_config, learning_rate_prefix, proposed_runs, workload
from yuntapr.experimental.phase_b_v2_ablations.readiness import (BlockedRunner, FormalExecutionBlocked,
    FreshRecord, TensorIdentity, audit_fresh_metadata, review_checkpoint_binding, state_metadata_digest)


def original_lr_function():
    """Execute just the unchanged pure arithmetic function, no module I/O imports."""
    path = Path(__file__).resolve().parents[2] / "src/yuntapr/training/phase_a_protocol.py"
    tree = ast.parse(path.read_text(encoding="utf-8"))
    node = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "lr_for_update")
    isolated = ast.Module(body=[node], type_ignores=[])
    namespace = {"math": math}
    exec(compile(isolated, path.as_posix(), "exec"), namespace)
    return namespace["lr_for_update"]


def h(text): return hashlib.sha256(text.encode()).hexdigest()


def fresh_fixture():
    result = []
    for run in proposed_runs():
        frames = 1 if run.model == "B0_MATCHED_V2" else 6
        tensors = {"shared.weight": TensorIdentity((2, 2), "float32", h(f"shared{run.seed}"))}
        for name in ("backbone.enc0.conv1.weight", "backbone.enc0.skip.weight"):
            tensors[name] = TensorIdentity((2, frames, 1, 1), "float32", h(f"{name}{run.seed}{run.model}"))
        result.append(FreshRecord(run, tensors, state_metadata_digest(tensors), h(f"rng{run.seed}"),
                                  h(f"order{run.seed}"), h("synthetic_initializer")))
    return result


@pytest.mark.parametrize("arm,params", [("E0", (.5, 2., 1.)), ("E1", (.5, 0., 1.)), ("E2", (.5, 2., 2.))])
def test_closed_three_conditions(arm, params):
    c = get_config(arm); assert (c.alpha, c.gamma, c.lambda_q) == params
    with pytest.raises(FrozenInstanceError): c.gamma = 5


@pytest.mark.parametrize("identity", ["E3", "E4", "e0", "FinalFit", "", None, True, {}])
def test_unknown_conditions_reject(identity):
    with pytest.raises(ValueError): get_config(identity)


@pytest.mark.parametrize("params", [("E0", .5, 0., 1.), ("E1", .5, 0., 2.), ("E2", .5, 2., 1.),
    ("E0", True, 2., 1.), ("E0", .5, float("nan"), 1.), ("E0", .5, 2., float("inf"))])
def test_condition_tampering_reject(params):
    with pytest.raises(ValueError): AblationConfig(*params)


@pytest.mark.parametrize("model,seed", [("B0", 2026), ("FINALFIT", 2026), ("B1_V2", True),
    ("B1_V2", 2025), ("B1_V2", 2026.0)])
def test_run_identity_invalid(model, seed):
    with pytest.raises(ValueError): RunSpec("E0", model, seed)


def test_matrix_budget_and_stage_split():
    runs = proposed_runs()
    assert len(runs) == len({r.run_id for r in runs}) == 18
    assert sum(r.stage == 1 for r in runs) == 6
    b = workload()
    assert b["updates_per_run"] == 47052 and b["updates_total"] == 846936
    assert b["validation_batches_total"] == 212706
    assert b["stage1_updates"] == 282312 and b["stage2_updates"] == 564624


def test_entire_9_epoch_LR_prefix_exact_original_function():
    lr_for_update = original_lr_function()
    assert all(learning_rate_prefix(u) == lr_for_update(u, steps_per_epoch=5228) for u in range(1, 47053))
    assert learning_rate_prefix(1) < 1e-6
    assert learning_rate_prefix(47052) > 1e-6  # not a compressed nine-epoch cosine


@pytest.mark.parametrize("update", [0, -1, 47053, True, 1.5])
def test_LR_budget_rejects_outside_prefix(update):
    with pytest.raises(ValueError): learning_rate_prefix(update)


def test_fresh_metadata_valid_but_no_actual_proof_or_authority():
    result = audit_fresh_metadata(fresh_fixture())
    assert result["metadata_consistent"] and not result["can_launch_formal_training"]
    assert not result["actual_initialization_proven"] and not result["actual_model_instantiated"]


@pytest.mark.parametrize("mutation", ["missing", "duplicate", "historical", "bad_digest", "different_arm_state",
    "different_rng", "different_order", "different_code", "shared_mismatch", "unapproved_shape"])
def test_fresh_metadata_fail_closed(mutation):
    records = fresh_fixture()
    if mutation == "missing": records.pop()
    elif mutation == "duplicate": records[-1] = records[0]
    elif mutation == "historical": records[0] = replace(records[0], historical_checkpoint_loaded=True)
    elif mutation == "bad_digest": records[0] = replace(records[0], state_sha256=h("wrong"))
    elif mutation == "different_rng": records[0] = replace(records[0], post_pair_rng_sha256=h("changed"))
    elif mutation == "different_order": records[0] = replace(records[0], epoch_order_sha256=h("changed"))
    elif mutation == "different_code": records[0] = replace(records[0], initializer_code_sha256=h("changed"))
    else:
        index = 2 if mutation == "different_arm_state" else 1
        old = records[index]; tensors = dict(old.tensors)
        key = "shared.weight"
        tensors[key] = TensorIdentity((3, 2) if mutation == "unapproved_shape" else (2, 2), "float32", h("changed"))
        records[index] = replace(old, tensors=tensors, state_sha256=state_metadata_digest(tensors))
    with pytest.raises(ValueError): audit_fresh_metadata(records)


def checkpoint_fixture(epoch=2):
    record = {"run_id": proposed_runs()[0].run_id, "completed_epoch": epoch, "retained_updates": epoch * 5228,
              "boundary": "COMPLETED_TRAIN_AND_VALIDATION_EPOCH_ONLY", "original_execution_reference": "SYNTHETIC_EVENT_REFERENCE_NOT_APPROVAL"}
    for key in ("last", "model", "optimizer", "rng", "scheduler", "code", "protocol", "data", "init"):
        record[key + "_sha256"] = h("synthetic_" + key)
    expected = {k: record[k] for k in ("run_id", "last_sha256", "code_sha256", "protocol_sha256", "data_sha256", "init_sha256")}
    return record, expected


@pytest.mark.parametrize("reference", [None, "SYNTHETIC_REFERENCE_NOT_APPROVAL"])
def test_checkpoint_review_cannot_authorize_or_apply(reference):
    result = review_checkpoint_binding(*checkpoint_fixture(), resume_approval_reference=reference)
    assert result["metadata_consistent"] and result["next_epoch"] == 3
    assert not result["can_apply_checkpoint_state"] and not result["approval_authenticity_verified"]


def test_endpoint_checkpoint_has_no_remaining_training():
    result = review_checkpoint_binding(*checkpoint_fixture(epoch=9))
    assert result["remaining_retained_updates"] == 0 and result["next_epoch"] is None


@pytest.mark.parametrize("field,value", [("completed_epoch", 10), ("completed_epoch", True),
    ("retained_updates", 1), ("boundary", "HALF_EPOCH"), ("original_execution_reference", ""),
    ("last_sha256", "bad"), ("run_id", "v1_FINALFIT")])
def test_checkpoint_metadata_rejected(field, value):
    metadata, expected = checkpoint_fixture(); metadata[field] = value
    with pytest.raises(ValueError): review_checkpoint_binding(metadata, expected)


@pytest.mark.parametrize("field", ["last_sha256", "code_sha256", "protocol_sha256", "data_sha256", "init_sha256"])
def test_resume_expected_identity_mismatch(field):
    metadata, expected = checkpoint_fixture(); expected[field] = h("changed")
    with pytest.raises(ValueError): review_checkpoint_binding(metadata, expected)


@pytest.mark.parametrize("claimed", [False, True, "APPROVED", "AUTHORIZED_TO_EXECUTE"])
def test_skeleton_always_blocks_even_self_reported_approval(claimed):
    runner = BlockedRunner(); assert not runner.describe()["can_launch_formal_training"]
    with pytest.raises(FormalExecutionBlocked): runner.run(approved=claimed, optimizer=object())
