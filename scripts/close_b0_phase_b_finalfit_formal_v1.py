"""Read-only FINAL verification, current full regression and formal evidence closure."""
import argparse
import csv
from datetime import datetime, timezone
import gc
import json
import math
import os
from pathlib import Path
import shutil
import sys
import tempfile
import traceback
import unittest
import uuid

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT/"src"), str(ROOT/"scripts")]
import torch
from yuntapr.contracts.loader import sha256
from yuntapr.training import formal_phase_b as b
import execute_b0_phase_b_finalfit_formal_v1 as execution
import train_b0_phase_a_formal_v1 as inherited


def read(path): return execution.read(path)
def save(path, value): execution.save(path, value)


def verify_training(out):
    manifest = read(out/"run_manifest.json")
    registry = read(out/"checkpoint_registry.json")
    if (registry.get("FINAL") != registry.get("LAST") or not registry.get("FINAL")
            or registry["FINAL"]["epoch"] != 11 or "BEST" in registry):
        raise ValueError("FINAL/LAST identity incomplete or invalid")
    expected = manifest["checkpoint_expected"]
    payload = b.load_verified_checkpoint(registry["FINAL"], expected)
    if payload["global_update"] != 128964 or payload["completed_epoch"] != 11:
        raise ValueError("Frozen epoch/update budget incomplete")
    del payload; gc.collect()
    contract = b.RunnerContract.load()
    ids = contract.rows
    private_log = Path(manifest["formal_checkpoint_root"])/"updates.jsonl"
    count = 0
    order = []
    seen = set()
    epoch_count = 0
    actual_epochs = []
    with private_log.open(encoding="utf-8") as stream:
        for line in stream:
            row = json.loads(line)
            u = count+1
            epoch, position = (u-1)//11724+1, (u-1)%11724
            if position == 0:
                permutation, _ = b.batch_plan(epoch-1)
                order = permutation.tolist(); seen = set(); epoch_count = 0
                actual = {"S_occ": 0., "S_qr": 0., "N_rain": 0, "N_valid": 0,
                    "norm_sum": 0., "norm_min": math.inf, "norm_max": -math.inf, "clip_count": 0}
            expected_indices = order[2*position:2*position+2]
            if (row["global_update"] != u or row["scheduler_u"] != u or row["epoch"] != epoch
                    or row["finalfit_indices"] != expected_indices
                    or row["sample_ids"] != [ids[i]["sample_id"] for i in expected_indices]
                    or row["scope"] != b.SCOPE or row["LR"] != b.finalfit_lr(u)
                    or row["batch_size"] != len(expected_indices)
                    or row["valid_denominator"] != len(expected_indices)*3430):
                raise ValueError("Actual formal update log identity/order/LR/denominator failure")
            if not all(row.get(key) is True for key in (
                    "forward_pass", "loss_pass", "backward_pass", "clip_pass", "optimizer_step_pass")):
                raise ValueError("Actual update numerical gate did not pass")
            if (row["raw_quantile_dtype"] != "torch.float32" or row["qlog_dtype"] != "torch.float64"
                    or row["pinball_dtype"] != "torch.float64"
                    or not all(math.isfinite(row[key]) for key in ("S_occ", "S_qr", "loss", "pre_clip_norm", "post_clip_norm"))):
                raise ValueError("Actual update precision/finiteness failure")
            norm = row["pre_clip_norm"]
            actual["S_occ"] += row["S_occ"]; actual["S_qr"] += row["S_qr"]
            actual["N_rain"] += row["rainy_count"]; actual["N_valid"] += row["valid_denominator"]
            actual["norm_sum"] += norm
            actual["norm_min"] = min(actual["norm_min"], norm); actual["norm_max"] = max(actual["norm_max"], norm)
            actual["clip_count"] += int(5./(norm+1e-6) < 1.)
            if seen.intersection(expected_indices): raise ValueError("Duplicate frozen identity within epoch")
            seen.update(expected_indices); epoch_count += len(expected_indices); count += 1
            if position == 11723 and (len(seen) != 23447 or epoch_count != 23447):
                raise ValueError("Actual epoch identity coverage incomplete")
            if position == 11723:
                actual_epochs.append({"epoch": epoch, "N_rain": actual["N_rain"], "N_valid": actual["N_valid"],
                    "global_train_occurrence_loss": actual["S_occ"]/actual["N_valid"],
                    "global_train_quantile_loss": actual["S_qr"]/actual["N_valid"],
                    "global_train_core_loss": (actual["S_occ"]+actual["S_qr"])/actual["N_valid"],
                    "gradient_norm_min": actual["norm_min"], "gradient_norm_max": actual["norm_max"],
                    "gradient_norm_mean": actual["norm_sum"]/11724,
                    "clip_count": actual["clip_count"], "clip_fraction": actual["clip_count"]/11724,
                    "LR_start": b.finalfit_lr((epoch-1)*11724+1), "LR_end": row["LR"],
                    "singleton_LR": row["LR"], "singleton_actual_denominator": row["valid_denominator"],
                    "singleton_sample_id": row["sample_ids"][0]})
    if count != 128964: raise ValueError("Actual formal log update count incomplete")
    summaries = [read(p) for p in sorted(out.glob("epoch_*_summary.json"))]
    if [r["epoch"] for r in summaries] != list(range(1, 12)):
        raise ValueError("Eleven complete actual epoch summaries required")
    for summary, actual in zip(summaries, actual_epochs):
        if summary["samples"] != 23447 or summary["updates"] != 11724 or summary["N_valid"] != 80423210:
            raise ValueError("Completed epoch sample/update/denominator mismatch")
        if any(summary[key] != value for key, value in actual.items()):
            raise ValueError("Epoch telemetry disagrees with independently reread actual update log")
    with (out/"training_history.csv").open(encoding="utf-8", newline="") as stream:
        history = list(csv.DictReader(stream))
    if len(history) != 11 or any({k: str(v) for k, v in row.items()} != history[i]
            for i, row in enumerate(summaries)):
        raise ValueError("CSV history disagrees with actual completed epoch summaries")
    boundary_identities = []
    for summary in summaries:
        epoch = summary["epoch"]
        entry = read(out/f"epoch_{epoch:03d}_history.json")
        identity = entry["checkpoint"]
        if (entry["epoch"] != epoch or entry["validation_executed"] is not False
                or identity["epoch"] != epoch or identity["global_update"] != epoch*11724
                or entry["training_metrics"]["formal_epoch_telemetry"] != summary):
            raise ValueError("Completed boundary history/identity mismatch")
        boundary = b.load_verified_checkpoint(identity, expected)
        if boundary["completed_epoch"] != epoch or boundary["global_update"] != epoch*11724:
            raise ValueError("Retained boundary payload epoch/update mismatch")
        del boundary
        boundary_identities.append(identity)
    final = registry["FINAL"]
    rich = {**final, "manifest_sha256": expected["finalfit_manifest_sha256"],
        "normalization_sha256": expected["normalization_artifact_sha256"],
        "runner_config_sha256": expected["runner_config_sha256"],
        "formal_phase_b_sha256": expected["implementation_sha256"]["src/yuntapr/training/formal_phase_b.py"],
        "formal_entrypoint_sha256": expected["implementation_sha256"]["scripts/train_b0_phase_b_finalfit_v1.py"],
        "environment": expected["environment"], "provenance": expected,
        "FINAL_BINARY_READ_ONLY_VERIFIED": True}
    b.atomic_json(out/"checkpoint_registry.json", {**registry, "LAST": rich, "FINAL": rich})
    b.atomic_json(out/"last_checkpoint_identity.json", rich)
    b.atomic_json(out/"final_checkpoint_identity.json", rich)
    save(out/"formal_training_verification.json", {"status": "PASS", "actual_logged_optimizer_updates": count,
        "actual_optimizer_update_log_identity": {"absolute_local_path": str(private_log),
            "bytes": private_log.stat().st_size, "sha256": sha256(private_log), "uploaded_to_Git": False},
        "eleven_epochs_23447_identities_exactly_once": True, "epoch_one_tail_LR_exact_1e_minus4": summaries[0]["singleton_LR"] == 1e-4,
        "global_loss_gradient_clip_tail_history_independently_recomputed": True,
        "all_eleven_boundary_payloads_readable_SHA_provenance_PASS": True,
        "retained_completed_epoch_checkpoint_identities": boundary_identities,
        "FINAL_readable_SHA_provenance_PASS": True, "FINAL": final, "verified_utc": execution.runner.now()})
    return rich


def regression(out, final):
    before = sha256(Path(final["absolute_local_path"]))
    pins_before = execution.baseline_inventory()
    parent = Path(r"F:\pytorch\Research\outputs\formal_execution\b0_phase_b_finalfit")
    fixture = (parent/("post_tests_"+uuid.uuid4().hex)).resolve()
    if fixture.parent != parent.resolve(): raise ValueError("Unsafe post-test fixture root")
    fixture.mkdir(parents=True, exist_ok=False)
    os.environ.update(TEST_FIXTURE_ONLY="true", TEMP=str(fixture), TMP=str(fixture),
        TORCHINDUCTOR_CACHE_DIR=str(fixture/"torchinductor"),
        YUNTAPR_PROTOCOL_DRYRUN_EVIDENCE=str(inherited.DRYRUN),
        YUNTAPR_SCIENTIFIC_REVIEW_EVIDENCE=str(execution.REVIEW),
        YUNTAPR_PHASE_B_PREPARATION_EVIDENCE=str(execution.PREPARATION),
        YUNTAPR_PHASE_B_RUNNER_EVIDENCE=str(execution.PREFLIGHT), YUNTAPR_PHASE_B_FORMAL_EVIDENCE=str(out))
    tempfile.tempdir = str(fixture); torch.set_num_threads(2)
    best = Path(read(execution.REVIEW/"review_manifest.json")["formal_best"]["absolute_local_path"]).resolve()
    rawroots = [b.HROOT.resolve(), b.IROOT.resolve()]
    formalroot = Path(r"F:\pytorch\Research\outputs\formal_training").resolve()
    active = {"enabled": True}; artifact = {"enabled": False}; violations = []
    def audit(event, args):
        if event != "open" or not isinstance(args[0], (str, bytes, os.PathLike)): return
        path = Path(os.fsdecode(args[0])).resolve(); mode = args[1] or ""; flags = args[2] if len(args)>2 else 0
        writing = any(c in str(mode) for c in "wax+") or bool(flags & (os.O_WRONLY|os.O_RDWR|os.O_CREAT|os.O_TRUNC))
        bad = any(path.is_relative_to(root) for root in rawroots)
        bad |= path.is_relative_to(formalroot) and not (artifact["enabled"] and path == best and not writing)
        bad |= writing and not path.is_relative_to(fixture) and not path.is_relative_to(out)
        if bad:
            violations.append(str(path)); raise PermissionError("Isolated post-training tests cannot access/modify formal states or raw data: "+str(path))
    sys.addaudithook(lambda e, a: audit(e, a) if active["enabled"] else None)
    results = []; success = False; cleanup = False
    try:
        groups = [(name, str(ROOT/"tests"/name), "test*.py", "TEST_FIXTURE_ONLY", None)
                  for name in (*inherited.SUITES, "formal_phase_a")]
        groups += [("scientific_review_units", str(ROOT/"tests/scientific_review"), "test_review_units.py", "TEST_FIXTURE_ONLY", None),
            ("scientific_review_full_artifacts", str(ROOT/"tests/scientific_review"), "test_review_full_artifacts.py", "READ_ONLY_ARTIFACT_VERIFICATION", None),
            ("phase_b_preparation_units", None, None, "TEST_FIXTURE_ONLY", "tests.phase_b_preparation.test_preparation.PreparationUnitTests"),
            ("phase_b_preparation_artifacts", None, None, "READ_ONLY_ARTIFACT_VERIFICATION", "tests.phase_b_preparation.test_preparation.PreparationArtifactTests"),
            ("formal_phase_b_units", None, None, "TEST_FIXTURE_ONLY", "tests.formal_phase_b.test_finalfit.FinalFitRunnerTests"),
            ("formal_phase_b_artifacts", None, None, "READ_ONLY_ARTIFACT_VERIFICATION", "tests.formal_phase_b.test_finalfit.FinalFitArtifactTests"),
            ("formal_execution_telemetry_units", None, None, "TEST_FIXTURE_ONLY", "tests.formal_phase_b_execution.test_execution.TelemetryUnitTests"),
            ("formal_execution_artifacts", None, None, "READ_ONLY_ARTIFACT_VERIFICATION", "tests.formal_phase_b_execution.test_execution.FormalExecutionArtifactTests")]
        with (out/"post_training_test_results.txt").open("x", encoding="utf-8", newline="\n") as stream:
            for name, location, pattern, scope, classname in groups:
                artifact["enabled"] = scope == "READ_ONLY_ARTIFACT_VERIFICATION"
                suite = unittest.defaultTestLoader.loadTestsFromName(classname) if classname else unittest.TestLoader().discover(location, pattern=pattern)
                stream.write("\nSUITE "+name+" SCOPE "+scope+"\n")
                result = unittest.TextTestRunner(stream=stream, verbosity=2).run(suite)
                item = {"suite": name, "scope": scope, "executed": result.testsRun,
                    "failures": len(result.failures), "errors": len(result.errors), "skipped": len(result.skipped),
                    "pass": result.wasSuccessful() and not result.skipped}
                results.append(item); stream.flush(); print("POST_TRAIN_TEST "+json.dumps(item), flush=True)
                if not item["pass"]: raise RuntimeError("STOP: post-training regression failed: "+name)
            success = True
    finally:
        active["enabled"] = False; gc.collect(); torch.cuda.empty_cache()
        if fixture.parent == parent.resolve() and fixture.name.startswith("post_tests_"):
            shutil.rmtree(fixture); cleanup = not fixture.exists()
        after = sha256(Path(final["absolute_local_path"]))
        unchanged = before == after == final["sha256"]
        summary = {"status": "PASS" if success and cleanup and unchanged and not violations else "FAIL",
            "suites": results, "total_tests_executed": sum(r["executed"] for r in results),
            "current_242_tests_executed": sum(r["executed"] for r in results if not r["suite"].startswith("formal_execution")),
            "new_formal_run_tests_executed": sum(r["executed"] for r in results if r["suite"].startswith("formal_execution")),
            "FINAL_SHA256_before": before, "FINAL_SHA256_after": after, "FINAL_unchanged": unchanged,
            "TEST_FIXTURE_ONLY": True, "FINAL_not_applied_to_test_models": True, "fixture_cleanup_success": cleanup,
            "prohibited_accesses": violations, "baseline_unchanged": pins_before == execution.baseline_inventory(),
            "2025_PIXELS_READ": 0, "finished_utc": execution.runner.now()}
        save(out/"post_training_test_summary.json", summary)
    if summary["status"] != "PASS": raise RuntimeError("Full regression/FINAL preservation/fixture cleanup failed")
    return summary


def finalize(out, final, tests):
    verification = read(out/"formal_training_verification.json")
    if verification["status"] != "PASS" or tests["status"] != "PASS" or tests["current_242_tests_executed"] != 242:
        raise ValueError("All actual training, FINAL and current regression gates required")
    if not (out/"training_runner_completion.json").exists():
        save(out/"training_runner_completion.json", read(out/"final_status.json"))
    runtime = read(out/"runtime_summary.json")
    summaries = [read(p) for p in sorted(out.glob("epoch_*_summary.json"))]
    formal_manifest = read(out/"formal_run_manifest.json")
    execution_manifest_path = ROOT/formal_manifest["execution_manifest"]/"execution_manifest.json"
    execution_manifest = read(execution_manifest_path)
    source_preflight = read(execution_manifest_path.parent/"source_identity_preflight.json")
    if (source_preflight["b13_files_verified"] != 23447 or source_preflight["imerg_days_verified"] != 490
            or source_preflight["2025_PIXELS_READ"] != 0):
        raise ValueError("Complete frozen original-source preflight evidence required")
    execution_wall = (datetime.fromisoformat(runtime["finished_utc"])
        - datetime.fromisoformat(execution_manifest["created_utc"])).total_seconds()
    status = {"state": "B0_PHASE_B_FINALFIT_FORMAL_TRAINING_COMPLETED_POST_TEST_CLOSURE_PASS",
        "run_id": out.name, "PHASE_B_AUTHORIZED": True, "PHASE_B_FORMAL_TRAINING_STARTED": True,
        "PHASE_B_FINALFIT_COMPLETED": True, "TOTAL_COMPLETED_EPOCHS": 11, "FORMAL_OPTIMIZER_STEPS": 128964,
        "EXPECTED_FORMAL_OPTIMIZER_STEPS": 128964, "FINAL_EPOCH": 11,
        "FINAL_CHECKPOINT_SHA256": final["sha256"], "FINAL_CHECKPOINT_LOCAL_PATH": final["absolute_local_path"],
        "FINAL_CHECKPOINT_READABLE_SHA_PROVENANCE_PASS": True,
        "2025_PIXELS_READ": 0, "B1_STARTED": False, "B1_TO_B8_AUTHORIZED": False,
        "FINAL_TEST_2025_AUTHORIZED": False, "FINAL_TEST_2025_EXECUTED": False,
        "TOTAL_POST_TRAINING_TESTS_EXECUTED": tests["total_tests_executed"],
        "TEST_FAILURES": 0, "TEST_ERRORS": 0, "TEST_SKIPS": 0,
        "FINAL_SHA_UNCHANGED_BY_TESTS": True, "CHECKPOINT_BINARY_NOT_COMMITTED_TO_GIT": True,
        "baseline_commit": execution.BASELINE, "completed_utc": execution.runner.now()}
    b.atomic_json(out/"runtime_summary.json", {**runtime, "post_training_closure_pending": False,
        "post_training_tests_PASS": True, "train_wall_seconds_sum": sum(r["wall_seconds"] for r in summaries),
        "source_SHA_preflight_seconds": source_preflight["wall_seconds"],
        "execution_manifest_to_training_completion_wall_seconds": execution_wall,
        "execution_wall_time_basis": "UTC_TIMESTAMP_DELTA_INCLUDES_PREFLIGHT_CHECKPOINT_AND_RUN_OVERHEAD_EXCLUDES_POST_TESTS",
        "IO_copy_seconds_sum": sum(r["IO_copy_seconds"] for r in summaries),
        "IO_read_seconds_sum": sum(r["IO_read_seconds"] for r in summaries),
        "GPU_peak_allocated_bytes_max": max(r["GPU_peak_allocated_bytes"] for r in summaries),
        "GPU_peak_reserved_bytes_max": max(r["GPU_peak_reserved_bytes"] for r in summaries),
        "b13_original_files_SHA_verified": source_preflight["b13_files_verified"],
        "imerg_original_days_SHA_verified": source_preflight["imerg_days_verified"],
        "tests": tests, "PHASE_B_FINALFIT_COMPLETED": True})
    b.atomic_json(out/"final_status.json", status)
    b.atomic_json(out/"run_status.json", {"state": status["state"], "PHASE_B_AUTHORIZED": True,
        "PHASE_B_FORMAL_TRAINING_STARTED": True, "PHASE_B_FINALFIT_COMPLETED": True,
        "completed_epoch": 11, "FORMAL_OPTIMIZER_STEPS": 128964,
        "2025_PIXELS_READ": 0, "updated_utc": status["completed_utc"]})
    metadata_note = ("A report-only execution-manifest path error occurred after all 254 tests passed. "
        "Its failure record is preserved, along with the timestamped metadata correction. "
        "The correction rechecked FINAL SHA/provenance and added zero formal optimizer updates.\n"
        if list(out.glob("post_training_metadata_correction_*.json")) else "")
    report = f"""# B0 Phase-B FinalFit formal training v1

Baseline `{execution.BASELINE}`; independent formal run `{out.name}`.
Researcher scope B0_PHASE_B_FINALFIT_ONLY. Fresh seed2026 model identity matches
`57a4d103a31aa7be1a52af079cdf7fb81bc73c51ba3e0e97d395513d21d9023d`.
No Phase-A model/optimizer/scheduler state was used. Historical false authorization
fields, all baseline files and the SHA-pinned runner/module/config remain unchanged.

All 11 fixed-budget epochs completed: each of the 23,447 identities appeared
exactly once per epoch. Physical batch size was 2, with one final singleton batch.
There was no skip, drop, duplication, padding or replacement. Each epoch contained
11,724 updates, giving 128,964 in total. Actual private update-log identities,
order, LR and denominators were
independently rechecked after training. All original source SHA preflight and runtime
staged source/QC/causality checks passed. No source/numerical failure was bypassed.

Normalization mean 270.5900486586461 K / std 20.368583874067266 K, SHA
`{b.NORMALIZATION_SHA}`, reused unchanged. Manifest SHA `{b.MANIFEST_SHA}`.
Architecture/loss/AdamW/BF16/FP32 parameters/raw quantiles/FP64 quantile/pinball and
global norm clip 5 inherit the unchanged protocol. W=11,724/U=586,200 retain the
50-epoch scheduler horizon. Epoch-one actual singleton LR is exactly 1e-4;
every singleton actual denominator is 3430, each full batch 6860.

No independent 2024 validation, early stopping, BEST selection, epoch reselection,
training-loss budget adjustment, 2025 access or next-stage execution occurred.
Global loss uses accumulated raw numerators divided by total actual valid pixels;
it is not a mean of batch losses. Requested LR/gradient/clip/GPU/I/O/tail metrics
are in `training_history.csv` and eleven `epoch_*_summary.json` files.

LAST and FINAL both identify epoch 11. Checkpoints use temporary writes, fsync,
round-trip/SHA checks and atomic rename. All eleven boundary payloads remain at
the researcher-approved F: root. Binary payloads are excluded from Git. FINAL
readability/SHA/provenance passed; post-training tests never applied FINAL state.

All current 242 tests plus {tests['new_formal_run_tests_executed']} legal new tests were
executed after training: total {tests['total_tests_executed']}, zero failures/errors/skips.
Isolated fixture artifacts were cleaned; FINAL SHA before/after tests is unchanged.
The Phase-B result describes fixed-budget FinalFit completion; it makes no 2025
Final Test or B1-B8 performance claim.

{metadata_note}
```json
{json.dumps(status, indent=2)}
```

STOP after publication. Final Test 2025 and B1-B8 remain unauthorized.
"""
    with (out/"B0_PHASE_B_FINALFIT_FORMAL_TRAINING_REPORT_v1.md").open("x", encoding="utf-8", newline="\n") as stream:
        stream.write(report)
    hashes = {p.name: {"sha256": sha256(p), "bytes": p.stat().st_size} for p in sorted(out.iterdir()) if p.is_file()}
    save(out/"artifact_sha256.json", hashes)
    print("FORMAL_CLOSURE "+json.dumps(status), flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__); parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--finalize-verified-evidence", action="store_true",
        help="Complete metadata only after an already recorded successful verification and full regression execution")
    args = parser.parse_args(); out = args.run_dir.resolve()
    root = (ROOT/"docs/formal_training/b0_phase_b_finalfit/runs").resolve()
    if out.parent != root or not out.name.startswith("run_"): raise SystemExit("Invalid formal run directory")
    try:
        if args.finalize_verified_evidence:
            verification = read(out/"formal_training_verification.json")
            tests = read(out/"post_training_test_summary.json")
            registry = read(out/"checkpoint_registry.json"); final = registry["FINAL"]
            if (verification["status"] != "PASS" or tests["status"] != "PASS"
                    or registry["LAST"] != final or final["epoch"] != 11 or final["global_update"] != 128964
                    or tests["current_242_tests_executed"] != 242 or not tests["fixture_cleanup_success"]
                    or not tests["baseline_unchanged"] or tests["prohibited_accesses"]
                    or any(r["failures"] or r["errors"] or r["skipped"] for r in tests["suites"])
                    or sha256(Path(final["absolute_local_path"])) != final["sha256"]
                    or tests["FINAL_SHA256_before"] != final["sha256"]
                    or tests["FINAL_SHA256_after"] != final["sha256"]):
                raise ValueError("Cannot complete metadata from incomplete or altered actual verification/test evidence")
            execution.baseline_inventory()
            payload = b.load_verified_checkpoint(final, read(out/"run_manifest.json")["checkpoint_expected"])
            del payload
            stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S_%fZ")
            save(out/f"post_training_metadata_correction_{stamp}.json", {
                "scope": "REPORT_METADATA_ONLY", "correction": "Resolve execution_manifest directory to execution_manifest.json",
                "preserved_failure_records": [{"filename": p.name, "sha256": sha256(p)}
                    for p in sorted(out.glob("post_training_closure_failure_*.json"))],
                "actual_training_verification_sha256": sha256(out/"formal_training_verification.json"),
                "actual_post_training_test_summary_sha256": sha256(out/"post_training_test_summary.json"),
                "correction_script_sha256": sha256(Path(__file__)), "FORMAL_OPTIMIZER_STEPS_ADDED": 0,
                "FINAL_SHA256_rechecked": final["sha256"], "corrected_utc": execution.runner.now()})
        else:
            final = verify_training(out)
            tests = regression(out, final)
        finalize(out, final, tests)
    except Exception as error:
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S_%fZ")
        registry = read(out/"checkpoint_registry.json") if (out/"checkpoint_registry.json").exists() else {}
        last = registry.get("LAST") or {}
        failure = {"state": "POST_TRAINING_CLOSURE_FAILED_STOP_REQUIRED", "error": repr(error),
            "traceback": traceback.format_exc(), "PHASE_B_AUTHORIZED": True,
            "PHASE_B_FORMAL_TRAINING_STARTED": True, "PHASE_B_FINALFIT_COMPLETED": False,
            "TOTAL_COMPLETED_EPOCHS": last.get("epoch", 0), "FORMAL_OPTIMIZER_STEPS": last.get("global_update", 0),
            "EXPECTED_FORMAL_OPTIMIZER_STEPS": 128964, "FINAL": registry.get("FINAL"),
            "2025_PIXELS_READ": 0, "B1_STARTED": False, "B1_TO_B8_AUTHORIZED": False,
            "FINAL_TEST_2025_AUTHORIZED": False, "FINAL_TEST_2025_EXECUTED": False,
            "failed_utc": execution.runner.now()}
        save(out/f"post_training_closure_failure_{stamp}.json", failure)
        if (out/"final_status.json").exists():
            save(out/f"training_runner_completion_before_failed_closure_{stamp}.json", read(out/"final_status.json"))
        b.atomic_json(out/"final_status.json", failure)
        b.atomic_json(out/"run_status.json", failure)
        raise
