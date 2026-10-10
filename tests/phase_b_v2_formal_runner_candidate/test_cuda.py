"""Full epoch/validation/LAST and two-model continued-resume campaign, max30."""
import copy
import gc
import json
import time
import pytest
import torch
from yuntapr.experimental.phase_b_v2_ablations.config import RunSpec
from yuntapr.experimental.phase_b_v2_integration.initialization import seeded_environment
from yuntapr.experimental.phase_b_v2_formal_runner_candidate.engine import EpochEngine
from yuntapr.experimental.phase_b_v2_formal_runner_candidate.data import artificial_registry, ROLES
from yuntapr.experimental.phase_b_v2_formal_runner_candidate.safety import Ledger
from yuntapr.experimental.phase_b_v2_formal_runner_candidate.protocol import OUT


@pytest.mark.parametrize("arm", ["E0", "E1", "E2"])
@pytest.mark.parametrize("model", ["B0_MATCHED_V2", "B1_V2"])
def test_complete_epoch_and_bound_resume(model, arm):
    if not torch.cuda.is_available(): pytest.skip("CUDA unavailable, no precision/device fallback")
    path = OUT / "tests" / f"{model}__{arm}_epochs.json"
    if path.exists(): pytest.fail("Campaign result already exists; never repeat consumed updates")
    ledger = Ledger()
    result = {"scope": "SYNTHETIC_ENGINEERING_ONLY", "model": model, "arm": arm, "seed": 2026,
              "status": "STARTED", "FORMAL_OPTIMIZER_STEPS": 0, "formal_runs_executed": 0}
    start = time.perf_counter()
    engine = resumed = None
    try:
        with seeded_environment(2026):
            torch.cuda.empty_cache(); torch.cuda.reset_peak_memory_stats()
            registry = artificial_registry()
            engine = EpochEngine(RunSpec(arm, model, 2026), registry, ledger)
            result["source_pins_verified"] = engine.public_pins
            result["initial_sha"] = engine.initial_sha
            result["identity"] = engine.identity
            result["resource_admission"] = engine.resources
            result["source_code_sha"] = engine.identity["code_sha"]
            with pytest.raises(ValueError): engine.validate_and_commit()
            train = engine.train_epoch()
            assert engine.completed_epoch == 0 and engine.last_reference is None
            with pytest.raises(ValueError): engine.train_epoch()
            receipt1, last1 = engine.validate_and_commit()
            assert train["coverage"]["exactly_once"]
            assert [b["batch"] for b in train["batch_records"]] == [2,2,1]
            assert any(b["N_rain"] == 0 and b["empty_rain_connected_zero"] for b in train["batch_records"])
            assert receipt1["validation"]["coverage"]["exactly_once"]
            assert engine.selected_endpoint()["selected_synthetic_epoch"] is None
            result["epoch1"] = receipt1
            result["last1_bytes"] = (engine.store.root / json.loads(last1.read_text())["filename"]).stat().st_size
            if arm == "E0":
                engine.train_epoch(); baseline, last2 = engine.validate_and_commit()
                expected_state = engine.state_identity()
                assert engine.selected_endpoint()["selected_synthetic_epoch"] == 2
                with pytest.raises(ValueError): engine.train_epoch()
                # Fresh new engine simulates a new process restore: its mutable
                # model/optimizer/scheduler are new; the durable task quota is not.
                resumed = EpochEngine(RunSpec(arm, model, 2026), registry, Ledger())
                state_before = resumed.state_identity()
                source_sha = json.loads(last1.read_text())["sha256"]
                with pytest.raises(ValueError): resumed.restore_completed_last(engine.store, last1, "0"*64)
                assert resumed.state_identity() == state_before
                budget_before = copy.deepcopy(ledger.read())
                resumed.restore_completed_last(engine.store, last1, source_sha)
                assert ledger.read() == budget_before  # restoring did not refund steps
                resumed.train_epoch(); replay, replay_last = resumed.validate_and_commit()
                assert replay == baseline
                assert resumed.state_identity() == expected_state
                result["epoch2_baseline"] = baseline
                result["epoch2_replayed"] = replay
                result["resume_exact_state_sha"] = expected_state
                result["resume_exact"] = True
                result["resume_did_not_refund_quota"] = True
                with pytest.raises(ValueError): resumed.train_epoch()
            with pytest.raises(PermissionError): engine.start_formal(approved=True)
            torch.cuda.synchronize()
            result.update(status="PASS", SYNTHETIC_OPTIMIZER_STEPS=9 if arm == "E0" else 3,
                          peak_cuda_allocated_bytes=torch.cuda.max_memory_allocated(),
                          peak_cuda_reserved_bytes=torch.cuda.max_memory_reserved())
    except BaseException as error:
        result.update(status="FAILED", error_type=type(error).__name__, error=str(error))
        raise
    finally:
        result["elapsed_seconds"] = time.perf_counter()-start
        result["task_reserved_steps"] = sum(ledger.read()["reserved"].values())
        result["task_completed_steps"] = sum(ledger.read()["completed"].values())
        with path.open("x",encoding="utf-8") as stream: json.dump(result,stream,ensure_ascii=False,indent=2)
        del engine, resumed
        gc.collect(); torch.cuda.empty_cache()

