"""Six full-architecture transactions; two synthetic steps per model/arm TOTAL.

This campaign is not repeatable automatically: the durable task quota survives
new pytest sessions. Never delete/reset the ledger to rerun successful steps.
"""
from __future__ import annotations
import gc
import json
import time
import pytest
import torch
from yuntapr.experimental.phase_b_v2_ablations.config import RunSpec
from yuntapr.experimental.phase_b_v2_integration.initialization import seeded_environment
from yuntapr.experimental.phase_b_v2_runner_candidate.runner import SyntheticRunner
from yuntapr.experimental.phase_b_v2_runner_candidate.safety import StepLedger, TEMP_ROOT
from yuntapr.experimental.phase_b_v2_runner_candidate.identity import DELIVERY


@pytest.mark.parametrize("arm", ["E0", "E1", "E2"])
@pytest.mark.parametrize("model", ["B0_MATCHED_V2", "B1_V2"])
def test_synthetic_update_replay_restore(model, arm):
    if not torch.cuda.is_available():
        pytest.skip("CUDA unavailable; no precision/batch fallback")
    ledger = StepLedger(TEMP_ROOT / "task_step_ledger.json")
    results_dir = DELIVERY / "tests"
    record_path = results_dir / (model + "__" + arm + "_synthetic.json")
    if record_path.exists():
        pytest.fail("Completed campaign record exists; do not repeat optimizer steps")
    result = {"scope": "SYNTHETIC_ENGINEERING_ONLY", "model": model, "arm": arm, "seed": 2026,
              "status": "STARTED", "FORMAL_OPTIMIZER_STEPS": 0}
    t0 = time.perf_counter()
    runner = None
    try:
        with seeded_environment(2026):
            torch.cuda.empty_cache()
            torch.cuda.reset_peak_memory_stats()
            runner = SyntheticRunner(RunSpec(arm, model, 2026), ledger)
            result["resource_admission"] = runner.admission
            result["initial_sha"] = runner.initial_sha
            result["protected_source_count"] = runner.source_count
            fresh = runner.save("FRESH_SYNTHETIC_UPDATE0")
            initial = runner.state_identity()
            result["empty_rain"] = runner.empty_rain_gradient_check()
            # No RNG-consuming layer exists, but explicitly restore the fresh RNG
            # before the first update instead of assuming this forever.
            runner.restore(fresh)
            torch.cuda.synchronize()
            start = time.perf_counter()
            first = runner.update_once()
            evaluation = runner.evaluate_synthetic()
            torch.cuda.synchronize()
            result["update_plus_evaluation_seconds"] = time.perf_counter() - start
            first_state = runner.state_identity()
            last = runner.save("LAST_SYNTHETIC_COMPLETED_MICROCYCLE1")
            assert runner.restore(fresh) == initial
            second = runner.update_once()
            second_eval = runner.evaluate_synthetic()
            second_state = runner.state_identity()
            assert first == second
            assert evaluation == second_eval
            assert first_state == second_state
            assert runner.restore(last) == first_state
            with pytest.raises(PermissionError):
                runner.start_formal(approved=True)
            result.update(status="PASS", first_update=first, common_evaluation_synthetic=evaluation,
                          exact_replay=True, restored_last_exact=True, state_identity=first_state,
                          SYNTHETIC_OPTIMIZER_STEPS=2, formal_start_blocked=True,
                          fresh_checkpoint_bytes=(runner.store.root / "FRESH_SYNTHETIC_UPDATE0.pt").stat().st_size,
                          last_checkpoint_bytes=(runner.store.root / "LAST_SYNTHETIC_COMPLETED_MICROCYCLE1.pt").stat().st_size)
            torch.cuda.synchronize()
            result["peak_cuda_allocated_bytes"] = torch.cuda.max_memory_allocated()
            result["peak_cuda_reserved_bytes"] = torch.cuda.max_memory_reserved()
    except BaseException as error:
        result.update(status="FAILED", error_type=type(error).__name__, error=str(error))
        raise
    finally:
        result["total_case_seconds"] = time.perf_counter() - t0
        state = ledger.read()
        result["task_reserved_steps"] = sum(state["reserved"].values())
        result["task_completed_steps"] = sum(state["completed"].values())
        with record_path.open("x", encoding="utf-8") as stream:
            json.dump(result, stream, ensure_ascii=False, indent=2)
        del runner
        gc.collect()
        torch.cuda.empty_cache()

