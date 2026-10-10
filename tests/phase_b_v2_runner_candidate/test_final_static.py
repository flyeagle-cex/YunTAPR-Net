"""Incremental optimizer-state faults and safety review; zero actual updates."""
import copy
import pytest
import torch
from yuntapr.experimental.phase_b_v2_ablations.config import learning_rate_prefix
from yuntapr.experimental.phase_b_v2_runner_candidate.checkpoint import validate_payload
from yuntapr.experimental.phase_b_v2_runner_candidate.optimizer import new_adamw
from yuntapr.experimental.phase_b_v2_runner_candidate.safety import install_guard
from test_cpu import fixture_payload

install_guard()


def updated_metadata_fixture():
    p, model, template = fixture_payload()
    p["progress"].update(synthetic_updates=1, train_complete=True, validation_complete=True)
    p["scheduler"]["completed"] = 1
    p["optimizer"]["param_groups"][0]["lr"] = learning_rate_prefix(1)
    p["optimizer"]["state"] = {0: {"step": torch.tensor(1.), "exp_avg": torch.ones(2), "exp_avg_sq": torch.ones(2)}}
    return p, model, template


def test_adamw_state_metadata_valid():
    p, model, template = updated_metadata_fixture()
    validate_payload(p, p["identity"], model, template)


@pytest.mark.parametrize("fault", ["missing_param", "missing_moment", "wrong_shape", "wrong_dtype",
                                  "nonfinite", "negative_second", "counter", "counter_dtype", "wrong_lr"])
def test_adamw_state_metadata_faults(fault):
    p, model, template = updated_metadata_fixture()
    if fault == "missing_param":
        p["optimizer"]["state"] = {}
    elif fault == "wrong_lr":
        p["optimizer"]["param_groups"][0]["lr"] = 1e-4
    else:
        state = p["optimizer"]["state"][0]
        if fault == "missing_moment": state.pop("exp_avg")
        elif fault == "wrong_shape": state["exp_avg"] = torch.ones(3)
        elif fault == "wrong_dtype": state["exp_avg"] = torch.ones(2, dtype=torch.float64)
        elif fault == "nonfinite": state["exp_avg"][0] = float("inf")
        elif fault == "negative_second": state["exp_avg_sq"][0] = -1
        elif fault == "counter": state["step"] = torch.tensor(2.)
        elif fault == "counter_dtype": state["step"] = torch.tensor(1., dtype=torch.float64)
    with pytest.raises((ValueError, FloatingPointError)):
        validate_payload(p, p["identity"], model, template)


def test_frozen_adamw_groups_and_flags_no_step():
    model = torch.nn.Sequential(torch.nn.Conv2d(1, 2, 1), torch.nn.GroupNorm(1, 2))
    opt, evidence = new_adamw(model)
    assert [g["weight_decay"] for g in opt.param_groups] == [1e-4, 0.]
    assert evidence["complete_union"] and evidence["disjoint"]
    assert not opt.state
    for g in opt.param_groups:
        assert g["betas"] == (.9, .999) and g["eps"] == 1e-8
        assert all(g[name] is False for name in ("amsgrad", "maximize", "capturable", "differentiable", "foreach", "fused"))


@pytest.mark.parametrize("cls", [torch.optim.AdamW, torch.optim.Adam, torch.optim.SGD])
def test_unregistered_optimizer_classes_blocked(cls):
    opt = cls([torch.nn.Parameter(torch.ones(1))], lr=1e-4)
    with pytest.raises(PermissionError):
        opt.step()


def test_registered_adamw_guard_dispatch_spy_no_actual_step(monkeypatch):
    from yuntapr.experimental.phase_b_v2_runner_candidate import safety
    opt = torch.optim.AdamW([torch.nn.Parameter(torch.ones(1))])
    seen = []
    monkeypatch.setattr(safety, "_original_step", lambda instance, *a, **kw: seen.append(instance))
    token = safety._step.set(opt)
    try:
        opt.step()  # mocked dispatch only; original AdamW is NEVER invoked
    finally:
        safety._step.reset(token)
    assert seen == [opt]


def test_final_ledger_fsync_and_quota_no_updates():
    from yuntapr.experimental.phase_b_v2_runner_candidate.safety import StepLedger
    from yuntapr.experimental.phase_b_v2_runner_candidate.checkpoint import SyntheticStore
    ledger = StepLedger(SyntheticStore().root / "metadata_only_final.json")
    key = "B0_MATCHED_V2__E0"
    ledger._mutate(key)
    ledger._mutate(key)
    assert StepLedger(ledger.path).read()["reserved"][key] == 2
    assert not ledger.read()["completed"]
    with pytest.raises(PermissionError):
        ledger._mutate(key)
