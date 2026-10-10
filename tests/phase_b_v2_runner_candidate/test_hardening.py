"""Incremental checks after the 12-step campaign; NO optimizer updates."""
import copy
import pytest
import torch
from yuntapr.training.phase_a_protocol import state_digest
from yuntapr.experimental.phase_b_v2_ablations.config import RunSpec
from yuntapr.experimental.phase_b_v2_runner_candidate.identity import identity
from yuntapr.experimental.phase_b_v2_runner_candidate.checkpoint import validate_payload, SyntheticStore
from yuntapr.experimental.phase_b_v2_runner_candidate.safety import StepLedger, TEMP_ROOT
from test_cpu import fixture_payload


def test_final_candidate_code_sha_bound():
    p, model, opt = fixture_payload()
    assert len(p["identity"]["candidate_code_sha"]) == 64
    p["identity"]["candidate_code_sha"] = "0" * 64
    with pytest.raises(ValueError):
        validate_payload(p, identity(RunSpec("E0", "B0_MATCHED_V2", 2026)), model, opt)


def test_formal_count_bool_rejected():
    p, model, opt = fixture_payload()
    expected = copy.deepcopy(p["identity"])
    p["progress"]["FORMAL_OPTIMIZER_STEPS"] = False
    with pytest.raises(ValueError):
        validate_payload(p, expected, model, opt)


def test_unknown_quota_arm_rejected():
    store = SyntheticStore()
    ledger = StepLedger(store.root / "metadata_only_ledger.json")
    with pytest.raises(ValueError):
        ledger._mutate("B0_MATCHED_V2__E3")


@pytest.mark.parametrize("model", ["B0_MATCHED_V2", "B1_V2"])
def test_final_source_identity_and_restore_fail_closed_no_updates(model, monkeypatch):
    from yuntapr.experimental.phase_b_v2_runner_candidate.runner import SyntheticRunner
    from yuntapr.experimental.phase_b_v2_integration.initialization import seeded_environment
    if not torch.cuda.is_available():
        pytest.skip("CUDA unavailable")
    ledger = StepLedger(TEMP_ROOT / "task_step_ledger.json")
    before_steps = copy.deepcopy(ledger.read())
    with seeded_environment(2026):
        torch.cuda.empty_cache()
        runner = SyntheticRunner(RunSpec("E0", model, 2026), ledger)
        fresh = runner.save("FINAL_CODE_FRESH0")
        state = runner.state_identity()
        assert runner.restore(fresh) == state
        payload = runner.store.read(fresh)
        for key in ("seed", "arm", "source_sha", "protocol_sha", "candidate_code_sha"):
            bad = copy.deepcopy(payload)
            bad["identity"][key] = "INVALID"
            reference = runner.store.save("BAD_" + key, bad)
            with pytest.raises(ValueError):
                runner.restore(reference)
            assert runner.state_identity() == state
        for key in ("model", "optimizer"):
            bad = copy.deepcopy(payload)
            bad.pop(key)
            reference = runner.store.save("MISSING_" + key, bad)
            with pytest.raises(ValueError):
                runner.restore(reference)
            assert runner.state_identity() == state
        def broken_apply(*args, **kwargs):
            raise RuntimeError("INJECTED_APPLY_FAILURE_NO_AUTOMATIC_CONTINUATION")
        monkeypatch.setattr(runner.model, "load_state_dict", broken_apply)
        with pytest.raises(RuntimeError, match="INJECTED_APPLY"):
            runner.restore(fresh)
        assert runner.poisoned
        with pytest.raises(RuntimeError, match="poisoned"):
            runner.update_once()
        assert ledger.read() == before_steps
    del runner
    torch.cuda.empty_cache()

