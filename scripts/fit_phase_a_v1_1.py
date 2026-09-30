"""Exact final-eligible 2023 native-pixel fit, with immutable prior-index verification."""
import argparse
from collections import Counter
import csv
from dataclasses import asdict
from datetime import timedelta
import json
from pathlib import Path
import subprocess
import time
import netCDF4
import numpy as np

from yuntapr.contracts.loader import REPO_ROOT, load_contract, sha256
from yuntapr.data.formal_policy import indexed_reject_reason, require_phase_a_fit_time, require_full_valid, MISSING_LATEST
from yuntapr.data.himawari_b13 import read_b13_local
from yuntapr.data.imerg_v07 import decode_imerg, validate_final_provenance
from yuntapr.data.masks import read_frozen_yunnan_mask
from yuntapr.data.sample_schema import utc
from yuntapr.data.staging import BoundedEnglishStaging
from yuntapr.spatial.sp04_mapping import load_sp04

HROOT = Path(r"H:\葵花202303_202510")
RAW = Path(r"F:\云南极端降水数据")
MASK = Path(r"F:\pytorch\Research\outputs\stage0_spatial_decision_update\run_20260928T102636_513428Z\FROZEN\MASK\yunnan_evaluation_mask_center_gadm41_imerg_v1.nc")
PRIOR = REPO_ROOT / "docs/development_qc/runs/run_20260930T075627Z"


def dump(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def table(path, rows):
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]), lineterminator="\n")
        w.writeheader(); w.writerows(rows)


def evidence(name, manifest):
    info = manifest["local_evidence"][name]
    path = Path(info["local_path"])
    if sha256(path) != info["sha256"]:
        raise ValueError(f"Historical evidence changed: {name}")
    with path.open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def recheck_imerg(pairs, stage, mapping, yunnan):
    completion_path = RAW / "manifests/imerg_manifest.jsonl"
    completions = {}
    for line in completion_path.read_text(encoding="utf-8").splitlines():
        row = json.loads(line)
        if row.get("status") == "complete" and row.get("granules") == 48:
            completions[str(row.get("path", "")).casefold()] = row
    result, verified = {}, []
    for name in sorted({p["imerg_day_path"] for p in pairs}):
        path = Path(name)
        with stage.local(path) as local:
            with netCDF4.Dataset(str(local)) as ds:
                ds.set_auto_maskandscale(False)
                validate_final_provenance({k: str(ds.getncattr(k)) for k in ds.ncattrs()}, completions[str(path).casefold()], path.stat().st_size)
                var = ds["precipitation"]
                if var.dimensions != ("time", "lat", "lon") or var.shape != (48, 130, 140) or var.units != "mm hr-1":
                    raise ValueError("IMERG time/grid/unit mismatch")
                mapping.assert_axes(mapping.axes["native_lat"], mapping.axes["native_lon"], ds["lat"][10:110], ds["lon"][20:120])
                y, valid = decode_imerg(np.asarray(var[:, 10:110, 20:120]), {k: var.getncattr(k) for k in var.ncattrs()})
                t = ds["time"]
                times = [utc(v.isoformat() + "Z") for v in netCDF4.num2date(t[:], t.units, calendar=getattr(t, "calendar", "standard"), only_use_cftime_datetimes=False)]
                day = times[0]
                if day.hour or day.minute or day.year not in (2023, 2024):
                    raise ValueError("IMERG development day mismatch")
                for i, converted in enumerate(times):
                    if converted != day + timedelta(minutes=30 * i):
                        raise ValueError("IMERG window sequence mismatch")
                    count = int((valid[i] & yunnan).sum())
                    result[converted.isoformat()] = {"status": "VALID_TARGET_SLOT" if count else "INVALID", "valid_yunnan_count": count}
        verified.append({"day_path": str(path), "sha256": stage.records[-1].source_sha256, "slots": 48})
    return result, verified, sha256(completion_path)


def run(out):
    start = time.perf_counter()
    if (out / "normalization_phaseA_2023_final_eligible.json").exists():
        raise FileExistsError("Completed normalization cannot be overwritten")
    science, cfg = load_contract()
    manifest = json.loads((PRIOR / "manifest.json").read_text(encoding="utf-8"))
    frames = evidence("b13_per_frame.csv", manifest)
    pairs = evidence("causal_pairing_per_slot.csv", manifest)
    old_imerg = evidence("imerg_per_slot.csv", manifest)
    frames_by_time = {r["nominal"]: r for r in frames}
    assert len(pairs) == 23520 and all(utc(p["window_start"]).year in (2023, 2024) for p in pairs)
    mapping = load_sp04()
    yunnan = read_frozen_yunnan_mask(MASK, mapping)
    stage = BoundedEnglishStaging(Path(r"F:\pytorch\Research\stage0_himawari\cache\staging"), cfg["staging"]["max_temporary_bytes"], True, True)
    # Size-only inventory includes 2025. No 2025 pixels are read or used in fitting.
    largest = (0, "")
    for f in frames:
        if f["status"] in ("FULL_VALID", "PARTIAL", "ALL_FILL"):
            source = HROOT / f["relative_path"]
            size = source.stat().st_size
            if size > largest[0]:
                largest = size, str(source)
    if largest[0] + 32 * 1024**2 > stage.max_bytes:
        raise ValueError(f"STAGING_CAP_REQUIRES_EXPLICIT_FIXED_MARGIN_UPDATE: {largest}")
    dump(out / "staging_inventory_v3.json", {"MAX_VALID_B13_FILE_BYTES": largest[0], "path": largest[1], "cap_bytes": stage.max_bytes, "actual_margin_bytes": stage.max_bytes-largest[0], "minimum_fixed_safety_margin_bytes": 32*1024**2, "scope": "All historical readable inventory, size-only including 2025; no 2025 pixel reads"})
    print("Inventory cap verified; revalidating 490 development IMERG days", flush=True)
    imerg, verified_days, completion_hash = recheck_imerg(pairs, stage, mapping, yunnan)
    dump(out / "imerg_development_revalidation.json", {"completion_manifest_sha256": completion_hash, "days": verified_days, "year_scope": [2023, 2024]})
    old_by_time = {r["window_start"]: r for r in old_imerg}
    decisions, counts, selected = [], [], []
    for year in (2023, 2024):
        c = Counter(year=year)
        for p in pairs:
            if utc(p["window_start"]).year != year:
                continue
            c["imerg_windows_total"] += 1
            c["expected_latest_available"] += p["pair_status"] == "EXPECTED_LATEST_SLOT_AVAILABLE"
            frame = frames_by_time.get(p["expected_nominal"])
            iv = imerg[p["window_start"]]
            if int(iv["valid_yunnan_count"]) != int(old_by_time[p["window_start"]]["valid_yunnan_count"]):
                raise ValueError("IMERG valid population changed since audit")
            reason = indexed_reject_reason(p, frame, iv)
            if p["pair_status"] == "EXPECTED_LATEST_SLOT_MISSING_BUT_OLDER_CAUSAL_EXISTS":
                c["older_fallback_rejected"] += 1
            reason_keys = {MISSING_LATEST: "missing_latest_rejected", "B13_PARTIAL_FORMAL_SUPERVISION_REJECTED": "partial_rejected", "B13_ALL_FILL_REJECT_SAMPLE": "all_fill_rejected", "B13_UNREADABLE": "unreadable_rejected", "TIME_METADATA_ERROR": "metadata_rejected", "NO_CAUSAL_FRAME": "no_causal_rejected", "IMERG_INVALID_OR_NO_VALID_YUNNAN": "imerg_rejected"}
            if reason:
                c[reason_keys.get(reason, "other_rejected")] += 1
            else:
                c["final_supervised_eligible_scenes"] += 1
                c["final_supervised_yunnan_pixel_observations"] += int(iv["valid_yunnan_count"])
                if year == 2023:
                    selected.append((p, frame))
            decisions.append({**p, "formal_supervised_eligible": not bool(reason), "formal_reject_reason": reason, "b13_full_valid": bool(frame and frame["status"] == "FULL_VALID")})
        keys = ["year", "imerg_windows_total", "expected_latest_available", "older_fallback_rejected", "missing_latest_rejected", "partial_rejected", "all_fill_rejected", "unreadable_rejected", "metadata_rejected", "no_causal_rejected", "imerg_rejected", "other_rejected", "final_supervised_eligible_scenes", "final_supervised_yunnan_pixel_observations"]
        counts.append({k: c[k] for k in keys})
    table(out / "formal_sample_counts_2023_2024.csv", counts)
    table(out / "formal_sample_eligibility_2023_2024.csv", decisions)
    print(json.dumps({"counts": counts, "fit_scenes": len(selected)}), flush=True)
    # Exact histogram of actual packed int16 code points, no centikelvin rebinning.
    hist = np.zeros(65536, dtype=np.int64)
    population, running_mean, m2 = 0, 0.0, 0.0
    sample_rows = []
    for number, (p, f) in enumerate(selected, 1):
        require_phase_a_fit_time(p["window_start"])
        source = HROOT / f["relative_path"]
        with stage.local(source) as local:
            x, valid, meta = read_b13_local(local, mapping, p["expected_nominal"])
            require_full_valid(x, valid)
            if meta.obs_start != utc(f["obs_start"]) or meta.obs_end != utc(f["obs_end"]) or meta.obs_end > utc(p["analysis_time"]) or meta.date_created != utc(f["date_created"]):
                raise ValueError("B13 temporal metadata changed")
            with netCDF4.Dataset(str(local)) as ds:
                ds.set_auto_maskandscale(False)
                v = ds["tbb_13"]
                raw = np.asarray(v[:])
                if raw.dtype != np.int16 or np.float32(v.scale_factor) != np.float32(.01) or np.float32(v.add_offset) != np.float32(273.15):
                    raise ValueError("Exact packed-code histogram requires audited encoding")
                hist += np.bincount(raw.astype(np.int32).ravel() + 32768, minlength=65536)
            vals = x.astype(np.float64).ravel()
            n, avg = vals.size, float(vals.mean())
            local_m2 = float(np.square(vals - avg).sum(dtype=np.float64))
            delta = avg - running_mean
            m2 += local_m2 + delta * delta * population * n / (population + n)
            running_mean += delta * n / (population + n)
            population += n
        rec = stage.records[-1]
        sample_rows.append({"sample_id": p["window_start"], "year": 2023, "window_start": p["window_start"], "analysis_time": p["analysis_time"], "expected_latest_slot": p["expected_nominal"], "b13_relative_path": f["relative_path"], "source_sha256": rec.source_sha256, "source_bytes": rec.temporary_bytes, "valid_pixel_count": n, "imerg_day_path": p["imerg_day_path"], "imerg_index": p["imerg_index"], "formal_supervised_qc_pass": True, "used_older_causal_frame": False})
        if number % 250 == 0:
            print(json.dumps({"fit_completed": number, "fit_total": len(selected), "elapsed_seconds": round(time.perf_counter()-start, 1)}), flush=True)
    table(out / "normalization_phaseA_sample_manifest.csv", sample_rows)
    sample_hash = sha256(out / "normalization_phaseA_sample_manifest.csv")
    (out / "normalization_phaseA_sample_manifest_sha256.txt").write_text(sample_hash + "\n", encoding="ascii")
    values = (np.arange(-32768, 32768, dtype=np.float32) * np.float32(.01) + np.float32(273.15)).astype(np.float64)
    mean = float(np.dot(hist.astype(np.float64), values) / population)
    std = float(np.sqrt(np.dot(hist.astype(np.float64), (values-mean)**2) / population))
    if population != int(hist.sum()) or population != len(selected)*251001 or abs(mean-running_mean) > 1e-9 or abs(std-np.sqrt(m2/population)) > 1e-9:
        raise ValueError("Independent exact-histogram and streaming moments disagree")
    cumulative = hist.cumsum()
    def percentile(p):
        rank = p * (population - 1)
        low, high = int(np.floor(rank)), int(np.ceil(rank))
        a, b = values[np.searchsorted(cumulative, low+1)], values[np.searchsorted(cumulative, high+1)]
        return float(a+(b-a)*(rank-low))
    qs = {name: percentile(p) for name, p in [("min_K", 0), ("p1_K", .01), ("q1_K", .25), ("median_K", .5), ("q3_K", .75), ("p99_K", .99), ("max_K", 1)]}
    qs["IQR_K"] = qs["q3_K"]-qs["q1_K"]
    code_paths = [Path(__file__), REPO_ROOT / "src/yuntapr/data/formal_policy.py", REPO_ROOT / "src/yuntapr/data/himawari_b13.py", REPO_ROOT / "src/yuntapr/data/staging.py"]
    result = {"normalization_version": "PHASE_A_2023_FINAL_ELIGIBLE_v1.1", "status": "DEVELOPMENT_DERIVED_PARAMETER", "ready": True, "fit_years": [2023], "fit_months": list(range(3, 11)), "ddof": 0, "eligible_scene_count": len(selected), "excluded_missing_latest_count": counts[0]["missing_latest_rejected"], "excluded_partial_count": counts[0]["partial_rejected"], "excluded_all_fill_count": counts[0]["all_fill_rejected"], "excluded_unreadable_count": counts[0]["unreadable_rejected"], "valid_pixel_count": population, "mean_K": mean, "std_K": std, **qs, "sample_manifest_sha256": sample_hash, "source_root": str(HROOT), "scientific_contract_sha256": sha256(REPO_ROOT / "config/science_contract_v1.1.yaml"), "prior_evidence_manifest_sha256": sha256(PRIOR / "manifest.json"), "statistics_method": "All eligible native pixels decoded identically to runtime float32, promoted to float64; exact packed-int16 code histogram (no rounding/rebinning), independently cross-checked against merged per-frame float64 central moments; quantiles exact linear rank interpolation", "streaming_mean_K": running_mean, "streaming_std_K": float(np.sqrt(m2/population)), "code_baseline_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=REPO_ROOT, text=True).strip(), "code_sha256": {str(p.relative_to(REPO_ROOT)).replace(chr(92), "/"): sha256(p) for p in code_paths}, "2024_role": "eligibility audit only; reuse 2023 statistics", "2025_pixels_read": False, "phase_b_statistics_ready": False, "formal_training_started": False}
    np.save(out / "normalization_phaseA_exact_packed_code_histogram.npy", hist)
    table(out / "staging_operations.csv", [asdict(r) for r in stage.records])
    dump(out / "normalization_phaseA_2023_final_eligible.json", result)
    dump(out / "fit_execution.json", {"elapsed_seconds": time.perf_counter()-start, "staging_operations": len(stage.records), "all_cleanup_success": all(r.cleanup_success for r in stage.records), "temporary_peak_bytes": max(r.temporary_bytes for r in stage.records), "copy_seconds": sum(r.copy_seconds or 0 for r in stage.records), "read_seconds": sum(r.read_seconds or 0 for r in stage.records)})
    print(json.dumps(result), flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-dir", type=Path, required=True)
    args = parser.parse_args()
    run(args.run_dir)
