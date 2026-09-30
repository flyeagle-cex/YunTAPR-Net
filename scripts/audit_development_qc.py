"""Read-only source audit for 2023/2024 development; never trains or freezes QC.

Run with the fixed project interpreter and a bounded English staging directory.
Large per-frame evidence remains at --local-dir; only aggregate evidence is public.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import csv
from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
import sys
import time

import netCDF4
import numpy as np

from yuntapr.contracts.loader import REPO_ROOT, sha256
from yuntapr.data.development_audit import (centikelvin_bins, expected_month_slots,
                                             nominal_from_name, support_counts, zone_masks)
from yuntapr.data.himawari_b13 import read_b13_local
from yuntapr.data.masks import read_frozen_yunnan_mask
from yuntapr.data.staging import BoundedEnglishStaging
from yuntapr.spatial.sp04_mapping import load_sp04


FRAME_FIELDS = ("month", "nominal", "relative_path", "status", "valid_count", "valid_fraction",
                "obs_start", "obs_end", "date_created", "yunnan_25", "yunnan_24",
                "yunnan_23", "yunnan_positive", "invalid_mapped", "error")


def write_json(path: Path, payload):
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(payload, stream, ensure_ascii=False, indent=2, default=str)
        stream.write("\n")


def write_csv(path: Path, fields, rows):
    with path.open("x", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def month_keys(years=(2023, 2024)):
    return [(year, month) for year in years for month in range(3, 11)]


def scan_h(args):
    run = args.run_dir
    local = args.local_dir
    if run.exists() or local.exists():
        raise FileExistsError("New audit run and local evidence directories required")
    run.mkdir(parents=True)
    local.mkdir(parents=True)
    mapping = load_sp04()
    yunnan = read_frozen_yunnan_mask(args.mask, mapping).ravel()
    if int(yunnan.sum()) != 3430:
        raise ValueError("Frozen Yunnan mask cell count mismatch")
    indices = mapping.indices.numpy()
    mapped_native = np.zeros((501, 501), dtype=bool)
    mapped_native.ravel()[indices.ravel()] = True
    zones = zone_masks()
    stage = BoundedEnglishStaging(args.staging_root, 16777216, True)
    frame_rows = []
    months = []
    fractions = []
    invalid_frequency = np.zeros((501, 501), dtype=np.uint32)
    hist_all = np.zeros(26, dtype=np.int64)
    hist_yunnan = np.zeros(26, dtype=np.int64)
    hist_2023_ck = np.zeros(65536, dtype=np.int64)
    hist_2024_ck = np.zeros(65536, dtype=np.int64)
    zone_invalid = Counter()
    zone_possible = Counter()
    season_counts = Counter()
    total_source_bytes = 0
    scan_start = time.perf_counter()
    for year, month in month_keys():
        key = f"{year}{month:02d}"
        source_dir = args.himawari_root / key
        if not source_dir.is_dir():
            raise FileNotFoundError(source_dir)
        expected = expected_month_slots(year, month)
        expected_set = set(expected)
        paths = {}
        unexpected = []
        for path in source_dir.rglob("*.nc"):
            try:
                nominal = nominal_from_name(path)
                if nominal not in expected_set or path.parent.name != f"{nominal.day:02d}":
                    raise ValueError("outside expected month/day placement")
                paths.setdefault(nominal, []).append(path)
            except ValueError:
                unexpected.append(str(path))
        counts = Counter()
        month_fractions = []
        for nominal in expected:
            candidates = paths.get(nominal, [])
            base = dict.fromkeys(FRAME_FIELDS, "")
            base.update(month=key, nominal=nominal.isoformat())
            counts["expected_nominal_slots"] += 1
            if not candidates:
                base["status"] = "MISSING"
                counts["missing"] += 1
                frame_rows.append(base)
                continue
            counts["available_b13"] += 1
            if len(candidates) != 1:
                base["status"] = "DUPLICATE_NOMINAL"
                base["error"] = str(len(candidates))
                counts["duplicate_nominal"] += 1
                frame_rows.append(base)
                continue
            path = candidates[0]
            base["relative_path"] = str(path.relative_to(args.himawari_root))
            size = path.stat().st_size
            total_source_bytes += size
            try:
                with stage.local(path) as english:
                    x, valid, observed = read_b13_local(english, mapping, nominal)
                count = int(valid.sum())
                base.update(valid_count=count, valid_fraction=count / valid.size,
                            obs_start=observed.obs_start.isoformat(),
                            obs_end=observed.obs_end.isoformat(),
                            date_created=observed.date_created.isoformat() if observed.date_created else "")
                counts["readable_b13"] += 1
                fraction = count / valid.size
                fractions.append(fraction)
                month_fractions.append(fraction)
                if observed.obs_start > observed.obs_end or observed.obs_end < nominal:
                    base["status"] = "METADATA_INVALID"
                    counts["metadata_time_invalid"] += 1
                elif count == 0:
                    base["status"] = "ALL_FILL"
                    counts["all_fill"] += 1
                elif count < valid.size:
                    base["status"] = "PARTIAL"
                    counts["partial"] += 1
                else:
                    base["status"] = "FULL_VALID"
                    counts["fully_valid"] += 1
                if base["status"] in ("PARTIAL", "FULL_VALID"):
                    analysis = nominal.replace(minute=0, second=0, microsecond=0) + timedelta(
                        minutes=30 if nominal.minute < 30 else 60)
                    if observed.obs_end <= analysis:
                        counts["causal_usable_at_containing_window_end"] += 1
                if count == valid.size:
                    hist_all[25] += 10000
                    hist_yunnan[25] += 3430
                    base.update(yunnan_25=3430, yunnan_24=3430, yunnan_23=3430,
                                yunnan_positive=3430, invalid_mapped=0)
                else:
                    support = support_counts(valid, indices)
                    hist_all += np.bincount(support, minlength=26)
                    hist_yunnan += np.bincount(support[yunnan], minlength=26)
                    ys = support[yunnan]
                    base.update(yunnan_25=int((ys == 25).sum()), yunnan_24=int((ys >= 24).sum()),
                                yunnan_23=int((ys >= 23).sum()), yunnan_positive=int((ys > 0).sum()),
                                invalid_mapped=int((~valid & mapped_native).sum()))
                    if count and base["status"] == "PARTIAL":
                        bad = ~valid
                        invalid_frequency += bad
                        for zone_name, zone in zones.items():
                            zone_invalid[zone_name] += int((bad & zone).sum())
                            zone_possible[zone_name] += int(zone.sum())
                if count and year in (2023, 2024):
                    bins = centikelvin_bins(x[valid])
                    target = hist_2023_ck if year == 2023 else hist_2024_ck
                    target += np.bincount(bins, minlength=65536)
            except Exception as error:
                base["status"] = "CORRUPT_OR_UNREADABLE"
                base["error"] = repr(error)[:500]
                counts["corrupt_or_unreadable"] += 1
            frame_rows.append(base)
        count_fields = ("expected_nominal_slots", "available_b13", "readable_b13", "missing",
                        "corrupt_or_unreadable", "all_fill", "partial", "fully_valid",
                        "metadata_time_invalid", "causal_usable_at_containing_window_end",
                        "duplicate_nominal")
        month_record = {"month": key, **{field: counts[field] for field in count_fields},
                        "unexpected_filename_count": len(unexpected),
                        "duplicate_files_count": sum(max(0, len(v) - 1) for v in paths.values()),
                        "source_file_count": sum(len(v) for v in paths.values()) + len(unexpected),
                        "valid_fraction_min": min(month_fractions) if month_fractions else "",
                        "valid_fraction_max": max(month_fractions) if month_fractions else ""}
        months.append(month_record)
        season_counts[key] = dict(counts)
        print(json.dumps({"month_done": key, "elapsed_seconds": round(time.perf_counter() - scan_start, 1),
                          "expected": len(expected), "available": counts["available_b13"],
                          "partial": counts["partial"], "unreadable": counts["corrupt_or_unreadable"]}), flush=True)
    write_csv(local / "b13_per_frame.csv", FRAME_FIELDS, frame_rows)
    fields = ("month", "expected_nominal_slots", "available_b13", "readable_b13", "missing",
              "corrupt_or_unreadable", "all_fill", "partial", "fully_valid", "metadata_time_invalid",
              "causal_usable_at_containing_window_end", "duplicate_nominal", "duplicate_files_count",
              "unexpected_filename_count", "source_file_count", "valid_fraction_min", "valid_fraction_max")
    write_csv(run / "himawari_b13_monthly_coverage.csv", fields, months)
    q = np.percentile(fractions, [0, .1, 1, 5, 50, 95, 99, 99.9, 100]) if fractions else [None] * 9
    write_json(run / "b13_valid_fraction_summary.json", {
        "scope": "2023_2024_MARCH_OCTOBER_DEVELOPMENT_ONLY", "readable_frame_count": len(fractions),
        "quantiles": dict(zip(("min", "p0_1", "p1", "p5", "p50", "p95", "p99", "p99_9", "max"), map(float, q))),
        "invalid_count_total": int(sum(501 * 501 - round(f * 501 * 501) for f in fractions)),
        "all_fill_count": sum(x.get("all_fill", 0) for x in months),
        "partial_frame_count": sum(x.get("partial", 0) for x in months),
        "full_valid_frame_count": sum(x.get("fully_valid", 0) for x in months),
        "per_frame_evidence_path": str(local / "b13_per_frame.csv"),
        "per_frame_rows": len(frame_rows), "per_frame_sha256": sha256(local / "b13_per_frame.csv")})
    np.save(local / "b13_partial_invalid_frequency.npy", invalid_frequency, allow_pickle=False)
    np.save(local / "b13_2023_centikelvin_hist.npy", hist_2023_ck, allow_pickle=False)
    np.save(local / "b13_2024_centikelvin_hist.npy", hist_2024_ck, allow_pickle=False)
    write_json(run / "b13_partial_spatial_summary.json", {
        "partial_frame_count": sum(x.get("partial", 0) for x in months),
        "invalid_frequency_map_shape": [501, 501],
        "invalid_frequency_map_path": str(local / "b13_partial_invalid_frequency.npy"),
        "invalid_frequency_map_sha256": sha256(local / "b13_partial_invalid_frequency.npy"),
        "edge_width_native_pixels_descriptive_only": 25,
        "zone_invalid_counts": dict(zone_invalid), "zone_possible_counts": dict(zone_possible),
        "mapped_native_invalid_total_in_partial_frames": int(invalid_frequency[mapped_native].sum()),
        "mapped_native_centers": int(mapped_native.sum()),
        "partial_invalid_centers_ever_inside_mapped_domain": int(np.count_nonzero(invalid_frequency & mapped_native)),
        "partial_invalid_centers_ever_outside_mapped_domain": int(np.count_nonzero(invalid_frequency & ~mapped_native))})
    write_json(local / "h_scan_internal.json", {
        "hist_all": hist_all.tolist(), "hist_yunnan": hist_yunnan.tolist(),
        "2023_hist_sha256": sha256(local / "b13_2023_centikelvin_hist.npy"),
        "2024_hist_sha256": sha256(local / "b13_2024_centikelvin_hist.npy"),
        "source_bytes_read_at_least": total_source_bytes,
        "stage_copies": len(stage.records), "stage_copy_seconds": sum(r.copy_seconds or 0 for r in stage.records),
        "stage_read_seconds": sum(r.read_seconds or 0 for r in stage.records),
        "stage_cleanup_failures": sum(not r.cleanup_success for r in stage.records),
        "stage_sha_failures": sum(r.sha256_match is False for r in stage.records),
        "scan_seconds": time.perf_counter() - scan_start,
        "mapping_sha256": mapping.manifest["mapping_csv_sha256"],
        "frozen_mask_sha256": sha256(args.mask), "python": sys.executable})
    print(json.dumps({"h_scan_complete": True, "frames": len(frame_rows),
                      "public_run": str(run), "local_evidence": str(local)}), flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("phase", choices=("scan-h",))
    for name in ("run-dir", "local-dir", "himawari-root", "mask", "staging-root"):
        parser.add_argument("--" + name, type=Path, required=True)
    args = parser.parse_args()
    if args.run_dir.parent.resolve() != (REPO_ROOT / "docs/development_qc/runs").resolve():
        raise ValueError("Public run directory must be under docs/development_qc/runs")
    if args.phase == "scan-h":
        scan_h(args)


if __name__ == "__main__":
    main()
