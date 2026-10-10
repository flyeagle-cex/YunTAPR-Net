"""NEW synthetic metadata/transaction tests; do not rerun inherited suites."""
from __future__ import annotations
import copy
from pathlib import Path
import random
import pytest
import torch
from yuntapr.experimental.phase_b_v2_ablations.config import RunSpec, learning_rate_prefix
from yuntapr.training.phase_a_protocol import lr_for_update, state_digest
from yuntapr.experimental.phase_b_v2_runner_candidate.identity import (
    candidate_plan, identity, verify_sources, reject_formal_execution, FLAGS)
from yuntapr.experimental.phase_b_v2_runner_candidate.safety import (
    install_guard, StepLedger, TEMP_ROOT)
from yuntapr.experimental.phase_b_v2_runner_candidate.optimizer import PrefixSchedule, clip_and_check, check_finite
from yuntapr.experimental.phase_b_v2_runner_candidate.checkpoint import SyntheticStore, SCHEMA, validate_payload
from yuntapr.experimental.phase_b_v2_runner_candidate import rng

install_guard()


def fixture_payload():
    model = {"synthetic_fixture": torch.tensor([1., 2.])}
    template = {"state": {}, "param_groups": [{"params": [0], "lr": 1e-4}], "_shapes": {0: (2,)}}
    return {"schema": SCHEMA, "identity": identity(RunSpec("E0", "B0_MATCHED_V2", 2026)),
            "model": model, "optimizer": {"state": {}, "param_groups": template["param_groups"]},
            "scheduler": PrefixSchedule().state_dict(), "rng": rng.capture(),
            "initial_sha": state_digest(model), "progress": {"formal_epoch": 0, "FORMAL_OPTIMIZER_STEPS": 0,
                "synthetic_updates": 0, "train_complete": False, "validation_complete": False}}, model, template


def test_sources_and_plan():
    assert verify_sources() == 333
    plan = candidate_plan()
    assert len(plan["runs"]) == len({r["synthetic_run_id"] for r in plan["runs"]}) == 18
    assert plan["formal_budget_not_executed"]["updates_total"] == 846936
    assert plan["formal_budget_not_executed"]["stage1_updates"] == 282312
    assert all(r["flags"] == FLAGS and r["warm_start"] is False for r in plan["runs"])


@pytest.mark.parametrize("claim", [True, "APPROVED", {"APPROVED": True}, {"approved": True}, None])
def test_formal_always_blocked(claim):
    with pytest.raises(PermissionError):
        reject_formal_execution(approved=claim)


@pytest.mark.parametrize("spec", [("E3", "B0_MATCHED_V2", 2026), ("E0", "B0_MATCHED_V2", 2025),
                                  ("E0", "B1_V2", True), ("E1", "FinalFit", 2026)])
def test_invalid_spec(spec):
    with pytest.raises(ValueError):
        identity(RunSpec(*spec))


@pytest.mark.parametrize("u", [1, 2, 5227, 5228, 5229, 10456, 47052])
def test_s0_assign_before_step(u):
    opt = torch.optim.AdamW([torch.nn.Parameter(torch.ones(1))], lr=1e-4)
    scheduler = PrefixSchedule()
    scheduler.completed = u - 1  # metadata test, NO actual optimizer update
    assert scheduler.prepare(opt) == learning_rate_prefix(u) == lr_for_update(u, steps_per_epoch=5228)
    assert opt.param_groups[0]["lr"] == learning_rate_prefix(u)
    assert scheduler.completed == u - 1
    scheduler.commit()
    assert scheduler.completed == u


def test_clip_analytic():
    model = torch.nn.Linear(2, 1, bias=False)
    model.weight.grad = torch.tensor([[6., 8.]])
    report = clip_and_check(model)
    assert report["pre_clip_norm"] == 10.
    assert report["post_clip_norm"] <= 5.
    torch.testing.assert_close(model.weight.grad, torch.tensor([[3., 4.]]) * (10. / (10. + 1e-6)))


@pytest.mark.parametrize("bad", [None, float("nan"), float("inf")])
def test_gradient_stop(bad):
    model = torch.nn.Linear(1, 1, bias=False)
    model.weight.grad = None if bad is None else torch.full_like(model.weight, bad)
    with pytest.raises(FloatingPointError):
        clip_and_check(model)


def test_unregistered_step_blocked():
    opt = torch.optim.AdamW([torch.nn.Parameter(torch.ones(1))])
    with pytest.raises(PermissionError):
        opt.step()


def test_ledger_reservations_cannot_reset():
    store = SyntheticStore()
    ledger = StepLedger(store.root / "metadata_only_ledger.json")
    ledger._mutate("B0_MATCHED_V2__E0")
    ledger._mutate("B0_MATCHED_V2__E0")
    with pytest.raises(PermissionError):
        StepLedger(ledger.path)._mutate("B0_MATCHED_V2__E0")
    assert sum(ledger.read()["completed"].values()) == 0  # no optimizer called


def test_ledger_failure_blocks_other_arms():
    store = SyntheticStore()
    ledger = StepLedger(store.root / "metadata_only_ledger.json")
    ledger._mutate("B0_MATCHED_V2__E0", failed=True)
    with pytest.raises(PermissionError):
        ledger._mutate("B1_V2__E1")


def test_rng_roundtrip():
    state = rng.capture()
    expected = (random.random(), torch.rand(3))
    rng.restore(state)
    actual = (random.random(), torch.rand(3))
    assert actual[0] == expected[0]
    assert torch.equal(actual[1], expected[1])


def test_atomic_roundtrip_weights_only():
    payload, model, opt = fixture_payload()
    store = SyntheticStore()
    ref = store.save("tiny_SYNTHETIC_FIXTURE", payload)
    loaded = store.read(ref)
    validate_payload(loaded, payload["identity"], model, opt)
    assert state_digest(loaded) == state_digest(payload)
    with pytest.raises(FileExistsError):
        store.save("tiny_SYNTHETIC_FIXTURE", payload)


@pytest.mark.parametrize("fault", ["after_serialization", "after_blob", "rename_locked"])
def test_save_fault_no_recoverable_commit(fault):
    payload, _, _ = fixture_payload()
    store = SyntheticStore()
    with pytest.raises(OSError):
        store.save("failure", payload, fault=fault)
    assert not (store.root / "failure.ref.json").exists()
    assert not (store.root / "failure.lock").exists()
    assert list(store.root.glob("*.part")) or (store.root / "failure.pt").exists()
    with pytest.raises(FileNotFoundError):
        store.read(store.root / "failure.ref.json")


def test_existing_lock_never_removed():
    payload, _, _ = fixture_payload()
    store = SyntheticStore()
    lock = store.root / "blocked.lock"
    lock.write_text("foreign owner", encoding="ascii")
    with pytest.raises(FileExistsError):
        store.save("blocked", payload)
    assert lock.read_text(encoding="ascii") == "foreign owner"


@pytest.mark.parametrize("mode", ["truncate", "mutate", "receipt_sha"])
def test_integrity_before_deserialization(mode):
    import json
    payload, _, _ = fixture_payload()
    store = SyntheticStore()
    ref = store.save("integrity", payload)
    record = json.loads(ref.read_text(encoding="utf-8"))
    if mode == "receipt_sha":
        record["sha256"] = "0" * 64
        ref.write_text(json.dumps(record), encoding="utf-8")
    else:
        with store.io():
            blob = store.root / record["filename"]
            data = bytearray(blob.read_bytes())
            if mode == "truncate":
                data = data[:100]
            else:
                data[100] ^= 1
            blob.write_bytes(data)
    with pytest.raises(ValueError, match="byte identity"):
        store.read(ref)


@pytest.mark.parametrize("fault", ["model_missing", "optimizer_missing", "seed", "arm", "epoch", "update", "boundary",
                                  "source", "protocol", "year2025", "model_shape", "model_nan", "rng_missing",
                                  "scheduler", "unknown_field", "optimizer_groups", "initial_sha"])
def test_invalid_payload(fault):
    original, model, opt = fixture_payload()
    p = copy.deepcopy(original)
    if fault.endswith("_missing"):
        p.pop(fault.removesuffix("_missing"))
    elif fault in {"seed", "arm"}:
        p["identity"][fault] = 2027 if fault == "seed" else "E2"
    elif fault in {"source", "protocol"}:
        p["identity"][fault + "_sha"] = "0" * 64
    elif fault == "year2025":
        p["identity"]["data_years"] = [2025]
    elif fault == "epoch":
        p["progress"]["formal_epoch"] = 9
    elif fault == "update":
        p["progress"]["synthetic_updates"] = 9
    elif fault == "boundary":
        p["progress"]["train_complete"] = True
    elif fault == "model_shape":
        p["model"]["synthetic_fixture"] = torch.ones(3)
    elif fault == "model_nan":
        p["model"]["synthetic_fixture"][0] = float("nan")
    elif fault == "scheduler":
        p["scheduler"]["original_horizon"] = 47052
    elif fault == "unknown_field":
        p["approved"] = True
    elif fault == "optimizer_groups":
        p["optimizer"]["param_groups"][0]["params"] = []
    elif fault == "initial_sha":
        p["initial_sha"] = "APPROVED"
    with pytest.raises((ValueError, FloatingPointError)):
        validate_payload(p, original["identity"], model, opt)
    assert state_digest(original["model"]) == state_digest(model)


@pytest.mark.parametrize("path", ["private_best.pt", "raw.nc", "sealed_2025.json", "unknown.csv"])
def test_forbidden_io_before_access(path):
    with pytest.raises(PermissionError):
        Path(path).open("rb")


def test_store_path_escape():
    store = SyntheticStore()
    with pytest.raises(PermissionError):
        store.read(Path("private_checkpoint.ref.json"))
    with pytest.raises(ValueError):
        store.save("../escape", {})


def test_schedule_rejects_unknown_resume():
    schedule = PrefixSchedule()
    with pytest.raises(ValueError):
        schedule.load_state_dict({"approved": True})

