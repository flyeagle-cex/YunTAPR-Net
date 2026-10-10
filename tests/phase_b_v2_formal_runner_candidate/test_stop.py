"""Actual architecture failure injection before any optimizer update."""
from dataclasses import replace
import copy
import json
import pytest
import torch
from yuntapr.experimental.phase_b_v2_ablations.config import RunSpec
from yuntapr.experimental.phase_b_v2_integration.initialization import seeded_environment
from yuntapr.experimental.phase_b_v2_formal_runner_candidate import engine as module
from yuntapr.experimental.phase_b_v2_formal_runner_candidate.engine import EpochEngine
from yuntapr.experimental.phase_b_v2_formal_runner_candidate.data import artificial_registry
from yuntapr.experimental.phase_b_v2_formal_runner_candidate.safety import Ledger
from yuntapr.experimental.phase_b_v2_formal_runner_candidate.protocol import OUT


@pytest.mark.parametrize("model", ["B0_MATCHED_V2", "B1_V2"])
def test_nan_reference_poison_no_step_no_last(model, monkeypatch):
    if not torch.cuda.is_available():pytest.skip("CUDA unavailable")
    ledger = Ledger(); before = copy.deepcopy(ledger.read())
    original = module.forward
    def invalid_reference(actual_model, batch, kind, arm):
        bad = replace(batch, rate=torch.full_like(batch.rate, float("nan")))
        return original(actual_model, bad, kind, arm)
    with seeded_environment(2026):
        torch.cuda.empty_cache()
        engine = EpochEngine(RunSpec("E0", model, 2026), artificial_registry(), ledger)
        monkeypatch.setattr(module, "forward", invalid_reference)
        with pytest.raises((ValueError, FloatingPointError)):
            engine.train_epoch()
        assert engine.poisoned and engine.completed_epoch == 0 and engine.schedule.completed == 0
        assert engine.last_reference is None and ledger.read() == before
        with pytest.raises(RuntimeError, match="Poisoned"):
            engine.validate_and_commit()
        with pytest.raises(RuntimeError, match="Poisoned"):
            engine.train_epoch()
        record = {"scope":"SYNTHETIC_ENGINEERING_ONLY","model":model,"nan_reference_rejected":True,
                  "poisoned":True,"LAST_created":False,"SYNTHETIC_OPTIMIZER_STEPS":0,"FORMAL_OPTIMIZER_STEPS":0}
        with (OUT/"tests"/(model+"_abnormal_stop.json")).open("x",encoding="utf-8") as f:json.dump(record,f,indent=2)
    del engine
    torch.cuda.empty_cache()

