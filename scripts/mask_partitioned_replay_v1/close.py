"""Independent saved-evidence closeout after the disposable replay exits.

No torch import/deserialization/forward/update; raw journals are metadata only.
Historical checkpoints may be stream-hashed, never loaded as state here.
"""
from pathlib import Path
import sys
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
from mask_partitioned_replay_v1 import common as c
from mask_partitioned_replay_v1.summary import validate_row, cohort, csv_records, CSV_FIELDS
from quantile_autopsy_v1.close_readonly import source_journals
import argparse
import csv
import json


def close(run):
    run = run.resolve()
    if run.parent != c.RUN_ROOT.resolve(): raise ValueError("Exact diagnostic run required")
    if (run / "mask_partitioned_postprocessing_audit.json").exists():
        raise FileExistsError("Never overwrite an existing audit")
    rec = c.read(run / "mask_partitioned_replay_reconciliation.json")
    if rec["status"] != "EXACT_FAILURE_REPRODUCED": raise ValueError("Replay did not complete exactly; preserve failure")
    expected_counts = {"ENGINEERING_OPTIMIZER_STEPS": c.SUCCESS, "ENGINEERING_BACKWARD_CALLS": c.SUCCESS,
        "ENGINEERING_FORWARD_CALLS": c.FAIL_BATCH, "FORMAL_OPTIMIZER_STEPS_ADDED": 0,
        "FORMAL_OPTIMIZER_STEPS": c.FORMAL_STEPS, "2025_RAW_ACCESS": 0, "2025_PIXELS_READ": 0, "B1_PHASE_B_STARTED": False}
    if rec["counts"] != expected_counts or rec["partition_union_matches_prior_autopsy"] != c.FAIL_BATCH:
        raise ValueError("Execution/reconciliation counters mismatch")
    checks = ["exact_replay_counters"]
    gate = c.read(run / "replay_identity_preflight.json")
    c.preflight_matches_prior(gate); c.verify(gate["frozen_mask_identity"])
    if any(p["expected"] != p["actual"] for p in gate["state_hashes"].values()):
        raise ValueError("Restored state mismatch")
    checks.append("initial_model_optimizer_RNG_scheduler_permutation_matches_prior")
    tests = c.read(run / "observer_test_result.json")
    if tests["status"] != "PASS" or any(tests["counts"][k] for k in ("failed", "errors", "skipped")):
        raise ValueError("Fixture gate did not pass")
    for path, wanted in {**tests["diagnostic_source_hashes"], **tests["test_source_hashes"]}.items():
        if c.digest(ROOT / path) != wanted: raise ValueError("Executed source changed: " + path)
    checks.append("fixture_gate_and_executed_source_identities")
    rows = []
    with (run / "mask_partitioned_forward_observations.jsonl").open(encoding="utf8") as handle:
        for line in handle:
            value = json.loads(line); validate_row(value); rows.append(value)
    if len(rows) != c.FAIL_BATCH: raise ValueError("Incomplete forward journal")
    refs = list(c.historical_updates(5))
    for expected, actual in zip(refs, rows[:-1]): c.exact_reconcile(expected, actual)
    if len(refs) != c.SUCCESS: raise ValueError("Formal history length changed")
    checks.append("all_8625_updates_formal_history_zero_tolerance")
    with (c.PRIOR / "replay_observations.jsonl").open(encoding="utf8") as handle:
        prior = [json.loads(line) for line in handle]
    if len(prior) != len(rows): raise ValueError("Prior replay coverage changed")
    for expected, actual in zip(prior, rows): c.check_partition_union(expected, actual)
    checks.append("all_8626_partition_unions_match_prior_autopsy")
    failed = rows[-1]; failure = c.read(run / "mask_partitioned_failure_forward.json")
    old_failure = c.read(c.PRIOR / "failing_tensor_diagnostics.json")
    if (failed["status"] != "EXPECTED_FORWARD_OVERFLOW" or failed["update"] != 50538
            or failure["qphysical_nonfinite_count"] != old_failure["qphysical_nonfinite_count"]
            or failure["qlog_max"] != old_failure["qlog_max"] or rec["exception"] != c.ERROR):
        raise ValueError("Original unmasked physical overflow not reproduced")
    for field in ("batch_index", "tau_index_zero_based", "tau_ordinal", "tau", "row", "column"):
        if failure["outside_max_location"][field] != old_failure["location"][field]:
            raise ValueError("Original outside extreme location mismatch")
    checks.append("original_failed_forward_physical_transform_and_outside_identity")
    summary = c.read(run / "mask_partitioned_quantile_extremes.json")
    expected_cohorts = {"SUCCESSFUL_UPDATES_ONLY": cohort(rows[:-1]),
                       "SUCCESSFUL_UPDATES_PLUS_FAILING_FORWARD": cohort(rows)}
    if summary["cohorts"] != expected_cohorts: raise ValueError("Cohort statistics do not reconcile")
    checks.append("both_cohorts_region_distributions_and_exposure_totals")
    with (run / "mask_partitioned_quantile_extremes.csv").open(encoding="utf8", newline="") as handle:
        actual = list(csv.DictReader(handle))
    if actual != [{k: str(row[k]) for k in CSV_FIELDS} for row in csv_records(rows)]:
        raise ValueError("CSV differs from aggregate journal")
    checks.append("all_17252_region_CSV_rows_match_journal")
    manifest = c.read(c.FAILED / "run_manifest.json")["manifest"]
    records = c.csv_rows(c.verify(manifest))
    source_audit = source_journals(run, [sid for row in rows for sid in row["sample_ids"]], records)
    if source_audit != rec["source_journal_audit"]: raise ValueError("Source journal totals mismatch")
    checks.append("all_sources_copy_SHA_cleanup_and_2025_firewall_journals")
    immutable = c.verify_snapshot(run)
    checks.append("all_192_or_actual_count_historical_files_byte_identical")
    for ref in rec["mask_partitioned_summary"]["output_identities"].values(): c.verify(ref)
    if "torch" in sys.modules: raise ValueError("Closeout must not import torch")
    output = {"utc": c.now(), "status": "PASS", "scope": c.SCOPE, "checks_run": len(checks),
        "checks_passed": checks, "tests": tests["counts"], "immutable_history": immutable,
        "source_journal_audit": source_audit, "replay_counters": expected_counts,
        "POSTPROCESSING_FORWARD_CALLS": 0, "POSTPROCESSING_BACKWARD_CALLS": 0, "POSTPROCESSING_OPTIMIZER_STEPS": 0,
        "POSTPROCESSING_RAW_SOURCE_OPENS": 0, "POSTPROCESSING_CHECKPOINT_DESERIALIZATIONS": 0,
        "FORMAL_RESUME_AUTHORIZED": False, "RESEARCHER_DECISION_REQUIRED": True,
        "formal_reconciliation_identity": c.pin(run / "mask_partitioned_replay_reconciliation.json")}
    c.write(run / "mask_partitioned_postprocessing_audit.json", output)
    paths = sorted(p for p in run.rglob("*") if p.is_file())
    paths += sorted(p for p in Path(__file__).parent.iterdir() if p.is_file() and p.suffix in (".py", ".html", ".txt"))
    paths += sorted((ROOT / "tests/mask_partitioned_replay").glob("*.py"))
    if any(p.suffix.lower() in (".pt", ".pth", ".ckpt") for p in paths): raise ValueError("No binary model publication")
    files = [{"relative_path": p.relative_to(ROOT).as_posix(), "bytes": p.stat().st_size, "sha256": c.digest(p)} for p in paths]
    if any(p["bytes"] >= 100 * 1024 * 1024 for p in files): raise ValueError("Artifact exceeds GitHub single-file size")
    c.write(run / "publication_manifest.json", {"utc": c.now(), "baseline": c.BASELINE, "scope": c.SCOPE,
        "status": "READY_FOR_PUBLICATION", "FORMAL_OPTIMIZER_STEPS": c.FORMAL_STEPS,
        "FORMAL_OPTIMIZER_STEPS_ADDED": 0, "B1_PHASE_B_STARTED": False, "2025_RAW_ACCESS": 0,
        "FORMAL_RESUME_AUTHORIZED": False, "RESEARCHER_DECISION_REQUIRED": True,
        "files": files, "file_count": len(files), "total_bytes": sum(p["bytes"] for p in files)})
    print(json.dumps({"status": "READY_FOR_PUBLICATION", "checks": len(checks), "files": len(files)}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(); parser.add_argument("--run", type=Path, required=True)
    close(parser.parse_args().run)
