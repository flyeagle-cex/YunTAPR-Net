"""Preserve first-grain audit and recompute candidate impact at supervised window grain."""
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
import shutil

from yuntapr.contracts.loader import REPO_ROOT, sha256
from scripts.finalize_development_qc import candidate_impact, read_csv


FIELDS = ("month", "candidate", "baseline_usable_scenes", "retained_scenes", "rejected_scenes",
          "retained_scenes_percent", "possible_yunnan_pixels", "retained_yunnan_pixels",
          "excluded_yunnan_pixels", "retained_yunnan_pixels_percent", "DRY_scenes",
          "DRY_retained_scenes", "RAINY_scenes", "RAINY_retained_scenes",
          "HEAVY_RATE_PROXY_GE20_scenes", "HEAVY_RATE_PROXY_GE20_retained_scenes",
          "UNKNOWN_scenes", "UNKNOWN_retained_scenes", "heavy_rate_proxy_is_engineering_only")


def revise(args):
    run, local = args.run_dir, args.local_dir
    if run.parent.resolve() != (REPO_ROOT / "docs/development_qc/runs").resolve():
        raise ValueError("Unexpected run directory")
    if (run / "qc_impact_grain_reconciliation.json").exists():
        raise FileExistsError("QC impact grain already revised")
    frame_rows = read_csv(local / "b13_per_frame.csv")
    pair_rows = read_csv(local / "causal_pairing_per_slot.csv")
    new = candidate_impact(frame_rows, pair_rows)
    exact = sum(r["pair_status"] == "EXPECTED_LATEST_SLOT_AVAILABLE" for r in pair_rows)
    fallback = sum(r["pair_status"] == "EXPECTED_LATEST_SLOT_MISSING_BUT_OLDER_CAUSAL_EXISTS"
                   for r in pair_rows)
    aggregate = [r for r in new if r["month"] == "ALL_DEVELOPMENT"]
    if exact <= 0 or any(r["baseline_usable_scenes"] != exact for r in aggregate):
        raise ValueError("Exact-latest supervised denominator mismatch")
    original = read_csv(run / "qc_candidate_impact.csv")
    old_aggregate = [r for r in original if r["month"] == "ALL_DEVELOPMENT"]
    if any(int(r["baseline_usable_scenes"]) <= exact for r in old_aggregate):
        raise ValueError("Expected erroneous all-frames denominator not found")
    backup = local / "pre_supervised_grain_revision"
    backup.mkdir(exist_ok=False)
    for name in ("qc_candidate_impact.csv", "DEVELOPMENT_DATA_QC_REPORT.md",
                 "manifest.json", "test_results.txt"):
        shutil.copy2(run / name, backup / name)
    impact_path = run / "qc_candidate_impact.csv"
    with impact_path.open("w", newline="", encoding="utf-8-sig") as stream:
        writer = csv.DictWriter(stream, FIELDS)
        writer.writeheader()
        writer.writerows(new)
    evidence = {"reason": "The initial candidate comparison counted every 10-minute B13 frame as a "
                          "supervised scene. The corrected grain is an exact-latest B13 / valid IMERG "
                          "half-hour window; fallback windows remain pending researcher approval.",
                "previous_all_frame_scene_denominator": int(old_aggregate[0]["baseline_usable_scenes"]),
                "correct_exact_latest_supervised_window_denominator": exact,
                "fallback_windows_excluded_pending_decision": fallback,
                "old_impact_sha256": sha256(backup / "qc_candidate_impact.csv"),
                "new_impact_sha256": sha256(impact_path),
                "previous_report_sha256": sha256(backup / "DEVELOPMENT_DATA_QC_REPORT.md"),
                "previous_manifest_sha256": sha256(backup / "manifest.json"),
                "local_previous_artifacts_directory": str(backup)}
    (run / "qc_impact_grain_reconciliation.json").write_text(
        json.dumps(evidence, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    # The preceding manifest is copied and hash-recorded. The package command
    # may now write a fresh manifest covering the revised public artifacts.
    (run / "manifest.json").unlink()
    print(json.dumps({"grain_revised": True, "exact_latest_windows": exact,
                      "fallback_excluded": fallback, "old_artifacts_preserved": str(backup)}))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--local-dir", type=Path, required=True)
    revise(parser.parse_args())


if __name__ == "__main__":
    main()
