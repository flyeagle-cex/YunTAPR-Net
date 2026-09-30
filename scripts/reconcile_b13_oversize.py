"""Reconcile one SHA-verified oversize B13 file rejected only by 16 MiB staging cap.

This is an auditable single-file exception, not a change to B0 production staging.
It updates the still-open Development audit run before aggregate pairing/finalization.
"""
from __future__ import annotations

import argparse
import csv
from datetime import datetime, timezone
import json
from pathlib import Path

import numpy as np

from yuntapr.contracts.loader import REPO_ROOT, sha256
from yuntapr.data.development_audit import centikelvin_bins
from yuntapr.data.himawari_b13 import read_b13_local
from yuntapr.data.staging import BoundedEnglishStaging
from yuntapr.spatial.sp04_mapping import load_sp04


NOMINAL = datetime(2024, 3, 2, 0, 10, tzinfo=timezone.utc)
RELATIVE = Path("202403/02/NC_H09_20240302_0010_R21_FLDK.06001_06001.nc")


def table(path):
    with path.open(newline="", encoding="utf-8-sig") as stream:
        reader = csv.DictReader(stream)
        return reader.fieldnames, list(reader)


def replace_csv(path, fields, rows):
    with path.open("w", newline="", encoding="utf-8-sig") as stream:
        writer = csv.DictWriter(stream, fields)
        writer.writeheader()
        writer.writerows(rows)


def replace_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")


def reconcile(args):
    if args.run_dir.parent.resolve() != (REPO_ROOT / "docs/development_qc/runs").resolve():
        raise ValueError("Unexpected audit run")
    if (args.local_dir / "oversize_reconciliation.json").exists():
        raise FileExistsError("Outlier already reconciled")
    source = args.himawari_root / RELATIVE
    if source.stat().st_size <= 16 * 1024 * 1024:
        raise ValueError("Source no longer exceeds standard staging cap")
    local_csv = args.local_dir / "b13_per_frame.csv"
    coverage_csv = args.run_dir / "himawari_b13_monthly_coverage.csv"
    frame_fields, frames = table(local_csv)
    month_fields, months = table(coverage_csv)
    matches = [r for r in frames if r["nominal"] == NOMINAL.isoformat()]
    if len(matches) != 1 or matches[0]["status"] != "CORRUPT_OR_UNREADABLE" or "byte cap" not in matches[0]["error"]:
        raise ValueError("Expected exactly one staging-cap rejection to reconcile")
    row = matches[0]
    if Path(row["relative_path"]) != RELATIVE:
        raise ValueError("Outlier path mismatch")
    mapping = load_sp04()
    source_hash_before = sha256(source)
    stage = BoundedEnglishStaging(args.staging_root, 700 * 1024 * 1024, True)
    with stage.local(source) as english:
        x, valid, frame = read_b13_local(english, mapping, NOMINAL)
    if not (len(stage.records) == 1 and stage.records[0].cleanup_success and stage.records[0].sha256_match):
        raise RuntimeError("Outlier staging integrity failure")
    if sha256(source) != source_hash_before:
        raise RuntimeError("Outlier source changed during bounded audit")
    if not (valid.shape == (501, 501) and valid.all() and frame.obs_start <= frame.obs_end):
        raise ValueError("Oversize B13 is not a full-valid legal frame; manual review needed")
    before = {"per_frame_sha256": sha256(local_csv), "monthly_sha256": sha256(coverage_csv),
              "hist_2024_sha256": sha256(args.local_dir / "b13_2024_centikelvin_hist.npy")}
    row.update(status="FULL_VALID", valid_count="251001", valid_fraction="1.0",
               obs_start=frame.obs_start.isoformat(), obs_end=frame.obs_end.isoformat(),
               date_created=frame.date_created.isoformat() if frame.date_created else "",
               yunnan_25="3430", yunnan_24="3430", yunnan_23="3430",
               yunnan_positive="3430", invalid_mapped="0", error="")
    month_row = next(r for r in months if r["month"] == "202403")
    for field, delta in (("readable_b13", 1), ("corrupt_or_unreadable", -1),
                         ("fully_valid", 1), ("causal_usable_at_containing_window_end", 1)):
        month_row[field] = str(int(month_row[field]) + delta)
    hist_path = args.local_dir / "b13_2024_centikelvin_hist.npy"
    hist24 = np.load(hist_path, allow_pickle=False)
    hist24 += np.bincount(centikelvin_bins(x[valid]), minlength=65536)
    h_internal_path = args.local_dir / "h_scan_internal.json"
    internal = json.loads(h_internal_path.read_text(encoding="utf-8"))
    internal["hist_all"][25] += 10000
    internal["hist_yunnan"][25] += 3430
    internal["stage_copies"] += 1
    internal["stage_copy_seconds"] += stage.records[0].copy_seconds or 0
    internal["stage_read_seconds"] += stage.records[0].read_seconds or 0
    valid_summary_path = args.run_dir / "b13_valid_fraction_summary.json"
    valid_summary = json.loads(valid_summary_path.read_text(encoding="utf-8"))
    fractions = np.asarray([float(r["valid_fraction"]) for r in frames if r["valid_fraction"] != ""],
                           dtype=np.float64)
    quantiles = np.percentile(fractions, [0, .1, 1, 5, 50, 95, 99, 99.9, 100])
    valid_summary["readable_frame_count"] = len(fractions)
    valid_summary["full_valid_frame_count"] += 1
    valid_summary["quantiles"] = dict(zip(("min", "p0_1", "p1", "p5", "p50", "p95", "p99", "p99_9", "max"),
                                           map(float, quantiles)))
    replace_csv(local_csv, frame_fields, frames)
    replace_csv(coverage_csv, month_fields, months)
    np.save(hist_path, hist24, allow_pickle=False)
    valid_summary["per_frame_sha256"] = sha256(local_csv)
    replace_json(valid_summary_path, valid_summary)
    internal["2024_hist_sha256"] = sha256(hist_path)
    internal["oversize_single_file_reconciled"] = str(RELATIVE)
    replace_json(h_internal_path, internal)
    evidence = {"reason": "Standard 16 MiB B0 staging cap rejected a valid exceptional 607 MiB H09 file; "
                          "a one-time 700 MiB single-file audit cap was used without changing B0 production config.",
                "nominal": NOMINAL.isoformat(), "source_path": str(source), "source_bytes": source.stat().st_size,
                "source_sha256": source_hash_before, "valid_count": int(valid.sum()),
                "classification_before": "CORRUPT_OR_UNREADABLE_STAGING_CAP",
                "classification_after": "FULL_VALID", "before_hashes": before,
                "after_hashes": {"per_frame_sha256": sha256(local_csv),
                                 "monthly_sha256": sha256(coverage_csv),
                                 "hist_2024_sha256": sha256(hist_path)},
                "staging_copy_seconds": stage.records[0].copy_seconds,
                "staging_read_seconds": stage.records[0].read_seconds,
                "staging_temporary_bytes": stage.records[0].temporary_bytes,
                "staging_sha256_match": True, "staging_cleanup_success": True,
                "source_modified": False}
    replace_json(args.local_dir / "oversize_reconciliation.json", evidence)
    public = {k: v for k, v in evidence.items() if k not in ("source_path",)}
    replace_json(args.run_dir / "b13_oversize_reconciliation.json", public)
    print(json.dumps({"oversize_reconciled": True, "monthly_202403_readable": month_row["readable_b13"],
                      "sha256_match": True, "cleanup_success": True}))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("run-dir", "local-dir", "himawari-root", "staging-root"):
        parser.add_argument("--" + name, type=Path, required=True)
    reconcile(parser.parse_args())


if __name__ == "__main__":
    main()
