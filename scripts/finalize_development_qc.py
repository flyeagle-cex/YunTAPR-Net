"""Aggregate completed source scans into review evidence; never select QC policy."""
from __future__ import annotations

import argparse
from bisect import bisect_right
from collections import Counter, defaultdict
import csv
from datetime import datetime, timedelta
import json
import math
from pathlib import Path

import numpy as np
import torch
from torch.nn import functional as F

from yuntapr.contracts.loader import REPO_ROOT, sha256
from yuntapr.data.development_audit import classify_pair, expected_latest_slot
from yuntapr.data.sample_schema import utc
from yuntapr.models.monotonic_quantiles import monotonic_quantiles


def read_csv(path):
    with path.open(newline="", encoding="utf-8-sig") as stream:
        return list(csv.DictReader(stream))


def write_csv(path, fields, rows):
    with path.open("x", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def write_json(path, payload):
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(payload, stream, ensure_ascii=False, indent=2, default=str)
        stream.write("\n")


def histogram_statistics(hist):
    hist = np.asarray(hist, dtype=np.int64)
    n = int(hist.sum())
    if n <= 0:
        raise ValueError("No valid B13 pixels for normalization evidence")
    values = np.arange(len(hist), dtype=np.float64) / 100.0
    mean = float(np.dot(hist.astype(np.float64), values) / n)
    variance = float(np.dot(hist.astype(np.float64), (values - mean) ** 2) / n)
    cumulative = np.cumsum(hist)
    def quantile(p):
        rank = p * (n - 1)
        low, high = math.floor(rank), math.ceil(rank)
        left = np.searchsorted(cumulative, low + 1, side="left") / 100.0
        right = np.searchsorted(cumulative, high + 1, side="left") / 100.0
        return float(left + (right - left) * (rank - low))
    return {"valid_pixel_count": n, "mean_K": mean, "std_K": math.sqrt(max(variance, 0)),
            "min_K": float(np.flatnonzero(hist)[0] / 100),
            "p1_K": quantile(.01), "median_K": quantile(.5),
            "q1_K": quantile(.25), "q3_K": quantile(.75),
            "IQR_K": quantile(.75) - quantile(.25), "p99_K": quantile(.99),
            "max_K": float(np.flatnonzero(hist)[-1] / 100)}


def pair_all(frame_rows, imerg_rows, root):
    by_nominal = {utc(r["nominal"]): r for r in frame_rows}
    usable = [r for r in frame_rows if r["status"] in ("FULL_VALID", "PARTIAL")
              and r["obs_end"] and r["relative_path"]]
    usable.sort(key=lambda r: (utc(r["obs_end"]), str(root / r["relative_path"])))
    ends = [utc(r["obs_end"]) for r in usable]
    end_count = Counter(ends)
    out = []
    for target in imerg_rows:
        if target["month"][:4] not in ("2023", "2024") or target["status"] != "VALID_TARGET_SLOT":
            continue
        analysis = utc(target["analysis_time"])
        nominal = expected_latest_slot(analysis)
        expected = by_nominal.get(nominal)
        pos = bisect_right(ends, analysis)
        selected = usable[pos - 1] if pos else None
        if selected is not None and utc(selected["nominal"]) > analysis:
            selected = None
        if selected is not None and end_count[utc(selected["obs_end"])] > 1:
            left = pos - end_count[utc(selected["obs_end"])]
            selected = min(usable[left:pos], key=lambda r: str(root / r["relative_path"]))
        expected_info = None
        if expected is not None:
            expected_info = {"status": ("READABLE" if expected["status"] in ("FULL_VALID", "PARTIAL")
                                        else expected["status"]),
                             "valid_count": int(expected["valid_count"] or 0),
                             "obs_start": expected["obs_start"], "obs_end": expected["obs_end"]}
        older = selected if selected is not None and selected is not expected else None
        label = classify_pair(expected_info, older, analysis)
        if label == "EXPECTED_LATEST_SLOT_AVAILABLE" and selected is not expected:
            label = "TIME_METADATA_ERROR"
        out.append({"month": target["month"], "window_start": target["window_start"],
                    "analysis_time": target["analysis_time"], "expected_nominal": nominal.isoformat(),
                    "expected_status": expected["status"] if expected else "MISSING",
                    "pair_status": label,
                    "selected_nominal": selected["nominal"] if selected else "",
                    "selected_obs_end": selected["obs_end"] if selected else "",
                    "selected_b13_relative_path": selected["relative_path"] if selected else "",
                    "equal_obs_end_tie": bool(selected and end_count[utc(selected["obs_end"])] > 1),
                    "imerg_day_path": target["day_path"], "imerg_index": target["index"],
                    "imerg_valid_yunnan_count": target["valid_yunnan_count"],
                    "imerg_zero_yunnan_count": target["zero_yunnan_count"],
                    "imerg_rain_yunnan_count": target["rain_yunnan_count"],
                    "imerg_max_yunnan_mmhr": target["max_yunnan_mmhr"]})
    diagnostic = {"usable_b13_frames": len(usable),
                  "duplicated_obs_end_values": sum(v > 1 for v in end_count.values()),
                  "frames_in_duplicated_obs_end_groups": sum(v for v in end_count.values() if v > 1),
                  "inverted_interval_frames": sum(bool(r["status"] == "METADATA_INVALID" and r["obs_start"] and
                                                  r["obs_end"] and utc(r["obs_start"]) > utc(r["obs_end"]))
                                                  for r in frame_rows),
                  "creation_before_observation_end_frames": sum(bool(r["date_created"] and r["obs_end"] and
                      utc(r["date_created"]) < utc(r["obs_end"])) for r in frame_rows)}
    diagnostic["metadata_inconsistency_frames"] = (
        diagnostic["inverted_interval_frames"] + diagnostic["creation_before_observation_end_frames"])
    return out, diagnostic


def candidate_impact(frame_rows, pair_rows):
    """Compare QC only at supervised-window grain with an exact latest B13.

    Older-frame fallback is a pending researcher decision, so it cannot silently
    enter this counterfactual comparison. This run's IMERG target is valid at
    all 3430 Yunnan cells; a future partial target needs per-cell intersection.
    """
    frames = {r["relative_path"]: r for r in frame_rows if r["relative_path"]}
    buckets = defaultdict(lambda: defaultdict(lambda: Counter()))
    for pair in pair_rows:
        if pair["pair_status"] != "EXPECTED_LATEST_SLOT_AVAILABLE":
            continue
        row = frames[pair["selected_b13_relative_path"]]
        if row["status"] not in ("FULL_VALID", "PARTIAL"):
            raise ValueError("Exact latest pair has no readable valid B13 frame")
        if int(pair["imerg_valid_yunnan_count"]) != 3430:
            raise ValueError("Partial IMERG target needs exact per-cell validity intersection")
        month = pair["month"]
        count = int(row["valid_count"])
        maximum = float(pair["imerg_max_yunnan_mmhr"] or 0)
        intensity = "HEAVY_RATE_PROXY_GE20" if maximum >= 20 else (
            "RAINY" if int(pair["imerg_rain_yunnan_count"] or 0) > 0 else "DRY")
        retained = {
            "A_SCENE_100_PERCENT": 3430 if count == 501 * 501 else 0,
            "B_CELL_25_OF_25": int(row["yunnan_25"]),
            "C_CELL_GE24_OF_25": int(row["yunnan_24"]),
            "D_CELL_GE23_OF_25": int(row["yunnan_23"]),
            "E_PARTIAL_RETAIN_CELL_VALIDITY_SEPARATE": int(row["yunnan_positive"]),
        }
        for candidate, pixels in retained.items():
            for key in (month, "ALL_DEVELOPMENT"):
                b = buckets[key][candidate]
                b["baseline_usable_scenes"] += 1
                b["possible_yunnan_pixels"] += 3430
                b["retained_yunnan_pixels"] += pixels
                b["excluded_yunnan_pixels"] += 3430 - pixels
                b["retained_scenes" if pixels else "rejected_scenes"] += 1
                b[f"{intensity}_scenes"] += 1
                if pixels:
                    b[f"{intensity}_retained_scenes"] += 1
    rows = []
    for month, candidates in sorted(buckets.items()):
        for name, b in candidates.items():
            b = dict(b)
            for field in ("retained_scenes", "rejected_scenes", "DRY_scenes", "DRY_retained_scenes",
                          "RAINY_scenes", "RAINY_retained_scenes", "HEAVY_RATE_PROXY_GE20_scenes",
                          "HEAVY_RATE_PROXY_GE20_retained_scenes", "UNKNOWN_scenes",
                          "UNKNOWN_retained_scenes"):
                b.setdefault(field, 0)
            possible = b["possible_yunnan_pixels"]
            rows.append({"month": month, "candidate": name, **b,
                         "retained_yunnan_pixels_percent": 100 * b["retained_yunnan_pixels"] / possible,
                         "retained_scenes_percent": 100 * b.get("retained_scenes", 0) / b["baseline_usable_scenes"],
                         "heavy_rate_proxy_is_engineering_only": True})
    return rows


def quantile_stress():
    torch.set_num_threads(2)
    cases = []
    for value in (-80., -40., -20., -10., 0., 10., 40., 80.):
        raw = torch.full((1, 32, 2, 2), value, dtype=torch.float32, requires_grad=True)
        increments = F.softplus(raw)
        first = math.log1p(.1) + increments[:, :1]
        q = torch.cat((first, first + torch.cumsum(increments[:, 1:], dim=1)), dim=1)
        equality = int((q[:, 1:] == q[:, :-1]).sum())
        finite = bool(torch.isfinite(q).all())
        q.sum().backward()
        gradient_finite = bool(torch.isfinite(raw.grad).all())
        try:
            monotonic_quantiles(raw.detach(), .1)
            official = "PASS"
        except FloatingPointError as error:
            official = type(error).__name__
        cases.append({"raw_constant": value, "finite": finite,
                      "strictly_increasing": bool((q[:, 1:] > q[:, :-1]).all()),
                      "float32_adjacent_equal_count": equality, "gradient_finite": gradient_finite,
                      "official_function": official})
    return {"dtype": "float32", "raw_range_tested": [-80, 80], "cases": cases,
            "QUANTILE_NUMERICAL_STABILITY_DECISION_REQUIRED": any(
                c["float32_adjacent_equal_count"] > 0 for c in cases),
            "not_auto_applied_options": [
                "accumulate positive increments in higher precision then cast with explicit contract impact review",
                "choose a positive minimum increment in the frozen log domain after Development-only analysis",
                "reparameterize a numerically stable monotonic head under a new researcher-approved version"],
            "forbidden_silent_fixes": ["posthoc_sort", "silent_clamp"]}


def finalize(args):
    run, local = args.run_dir, args.local_dir
    frames = read_csv(local / "b13_per_frame.csv")
    imerg = read_csv(local / "imerg_per_slot.csv")
    h_internal = json.loads((local / "h_scan_internal.json").read_text(encoding="utf-8"))
    if h_internal["stage_cleanup_failures"] or h_internal["stage_sha_failures"]:
        raise RuntimeError("Himawari staging integrity failure")
    i_internal = json.loads((local / "imerg_scan_internal.json").read_text(encoding="utf-8"))
    if i_internal["stage_cleanup_failures"]:
        raise RuntimeError("IMERG staging cleanup failure")
    pairs, diagnostic = pair_all(frames, imerg, args.himawari_root)
    pair_fields = ("month", "window_start", "analysis_time", "expected_nominal", "expected_status",
                   "pair_status", "selected_nominal", "selected_obs_end", "selected_b13_relative_path",
                   "equal_obs_end_tie", "imerg_day_path", "imerg_index", "imerg_valid_yunnan_count",
                   "imerg_zero_yunnan_count", "imerg_rain_yunnan_count", "imerg_max_yunnan_mmhr")
    write_csv(local / "causal_pairing_per_slot.csv", pair_fields, pairs)
    per_month = defaultdict(Counter)
    for row in pairs:
        for key in (row["month"], "ALL_DEVELOPMENT"):
            per_month[key]["total_valid_imerg_windows"] += 1
            per_month[key][row["pair_status"]] += 1
            per_month[key]["equal_obs_end_tie_cases"] += int(row["equal_obs_end_tie"])
    pair_summary = []
    for month, counts in sorted(per_month.items()):
        for field in ("EXPECTED_LATEST_SLOT_AVAILABLE", "EXPECTED_LATEST_SLOT_MISSING_BUT_OLDER_CAUSAL_EXISTS",
                      "NO_CAUSAL_FRAME", "TIME_METADATA_ERROR", "equal_obs_end_tie_cases"):
            counts[field] += 0
        pair_summary.append({"month": month, **counts,
                             "duplicated_obs_end_values_global": diagnostic["duplicated_obs_end_values"],
                             "inverted_interval_frames_global": diagnostic["inverted_interval_frames"],
                             "creation_before_observation_end_frames_global": diagnostic["creation_before_observation_end_frames"],
                             "metadata_inconsistency_frames_global": diagnostic["metadata_inconsistency_frames"]})
    write_csv(run / "causal_pairing_summary.csv", ("month", "total_valid_imerg_windows",
        "EXPECTED_LATEST_SLOT_AVAILABLE", "EXPECTED_LATEST_SLOT_MISSING_BUT_OLDER_CAUSAL_EXISTS",
        "NO_CAUSAL_FRAME", "TIME_METADATA_ERROR", "equal_obs_end_tie_cases",
        "duplicated_obs_end_values_global", "inverted_interval_frames_global",
        "creation_before_observation_end_frames_global", "metadata_inconsistency_frames_global"), pair_summary)
    hist_all = np.asarray(h_internal["hist_all"], dtype=np.int64)
    hist_yn = np.asarray(h_internal["hist_yunnan"], dtype=np.int64)
    support_rows = []
    for scope, hist in (("ALL_10000_TARGET_CELLS", hist_all), ("YUNNAN_3430_CELLS", hist_yn)):
        for count, frequency in enumerate(hist):
            support_rows.append({"scope": scope, "valid_native_centers": count, "total_native_centers": 25,
                                 "frequency": int(frequency), "fraction": float(frequency / hist.sum())})
    write_csv(run / "sp04_support_distribution.csv", ("scope", "valid_native_centers",
        "total_native_centers", "frequency", "fraction"), support_rows)
    impact = candidate_impact(frames, pairs)
    write_csv(run / "qc_candidate_impact.csv", ("month", "candidate", "baseline_usable_scenes",
        "retained_scenes", "rejected_scenes", "retained_scenes_percent", "possible_yunnan_pixels",
        "retained_yunnan_pixels", "excluded_yunnan_pixels", "retained_yunnan_pixels_percent",
        "DRY_scenes", "DRY_retained_scenes", "RAINY_scenes", "RAINY_retained_scenes",
        "HEAVY_RATE_PROXY_GE20_scenes", "HEAVY_RATE_PROXY_GE20_retained_scenes",
        "UNKNOWN_scenes", "UNKNOWN_retained_scenes", "heavy_rate_proxy_is_engineering_only"), impact)
    h23 = np.load(local / "b13_2023_centikelvin_hist.npy", allow_pickle=False)
    h24 = np.load(local / "b13_2024_centikelvin_hist.npy", allow_pickle=False)
    stats23 = histogram_statistics(h23)
    stats24 = histogram_statistics(h24)
    mean, std = stats23["mean_K"], stats23["std_K"]
    normalization = {"status": "EVIDENCE_ONLY_D8_NOT_FROZEN", "fit_year": 2023,
        "fit_months": list(range(3, 11)), "valid_native_pixels_only": True,
        "quantile_resolution_K": 0.01, "population_std_ddof": 0,
        "2023_train_candidate": stats23,
        "2024_observed_using_2023_fit": {"valid_pixel_count": stats24["valid_pixel_count"],
            "z_mean": (stats24["mean_K"] - mean) / std, "z_std": stats24["std_K"] / std,
            "z_p1": (stats24["p1_K"] - mean) / std, "z_median": (stats24["median_K"] - mean) / std,
            "z_p99": (stats24["p99_K"] - mean) / std},
        "2024_refitted": False, "2025_used": False,
        "2023_histogram_sha256": sha256(local / "b13_2023_centikelvin_hist.npy"),
        "2024_histogram_sha256": sha256(local / "b13_2024_centikelvin_hist.npy")}
    write_json(run / "normalization_2023_train_only.json", normalization)
    write_json(run / "quantile_numerical_stress.json", quantile_stress())
    decision_note = ("# Decision 8 — B13 normalization evidence (not frozen)\n\n"
        "Only valid native B13 pixels from 2023 March–October were used to fit the descriptive "
        "mean/std candidate. The 0.01 K centikelvin histogram also supplies median, IQR, p1, p99, "
        "minimum and maximum. 2024 is observed using the 2023 fit; 2025 is excluded.\n\n"
        f"2023 candidate mean = {mean:.6f} K; population std = {std:.6f} K; "
        f"median = {stats23['median_K']:.2f} K; IQR = {stats23['IQR_K']:.2f} K.\n\n"
        "Researcher decision required: normalization policy, treatment of partial frames and "
        "the time of fitting within a future formal protocol. This run does not alter the science contract.\n")
    (run / "DECISION_8_NORMALIZATION_EVIDENCE.md").write_text(decision_note, encoding="utf-8", newline="\n")
    print(json.dumps({"finalized_aggregates": True, "paired_valid_imerg_windows": len(pairs),
                      "normalization_2023_valid_pixels": stats23["valid_pixel_count"]}))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("run-dir", "local-dir", "himawari-root"):
        parser.add_argument("--" + name, type=Path, required=True)
    args = parser.parse_args()
    if args.run_dir.parent.resolve() != (REPO_ROOT / "docs/development_qc/runs").resolve():
        raise ValueError("Unexpected run directory")
    finalize(args)


if __name__ == "__main__":
    main()
