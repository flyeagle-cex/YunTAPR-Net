"""One real B0 sample ENGINEERING_ONLY verification; no fit, optimizer, or checkpoint.

The only source-file writes are bounded UUID staging copies under --staging-root.
The output is metadata/diagnostics JSON, never raw data or model predictions.
"""
from __future__ import annotations

import argparse
import csv
from dataclasses import asdict
from datetime import timedelta
import json
import os
from pathlib import Path
import sys

import netCDF4
import numpy as np
import torch

from yuntapr.contracts.loader import REPO_ROOT, load_contract, sha256
from yuntapr.data.dataset_b0 import B0Dataset, B0Record
from yuntapr.data.imerg_v07 import validate_final_provenance
from yuntapr.data.masks import read_frozen_yunnan_mask
from yuntapr.data.sample_schema import HimawariFrame, select_latest_causal_frame, utc
from yuntapr.data.staging import BoundedEnglishStaging, StagedB13Reader, StagedIMERGReader
from yuntapr.models.b0 import B0Model
from yuntapr.spatial.sp04_mapping import load_sp04
from yuntapr.training.batch_contract import B0Batch
from yuntapr.training.forward_step import engineering_forward_step


def _args():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("himawari-root", "master-index", "imerg-file", "imerg-manifest", "frozen-mask", "staging-root", "output"):
        parser.add_argument("--" + name, type=Path, required=True)
    parser.add_argument("--imerg-window-start", required=True)
    parser.add_argument("--imerg-index", type=int, required=True)
    parser.add_argument("--engineering-focal-alpha", type=float, required=True)
    parser.add_argument("--engineering-focal-gamma", type=float, required=True)
    parser.add_argument("--engineering-seed", type=int, required=True)
    parser.add_argument("--engineering-threads", type=int, required=True)
    return parser.parse_args()


def _frame_from_row(root: Path, row: dict) -> HimawariFrame:
    return HimawariFrame(
        root / row["relative_path"], utc(row["timestamp_filename_utc"]),
        utc(row["start_time"]), utc(row["end_time"]),
        utc(row["date_created"]) if row["date_created"] else None,
    )


def b0_candidate_rows(rows: list[dict], root: Path, start, analysis) -> list[dict]:
    """B0 eligibility starts with the B13 file, independent of other bands.

    Packed B13 readability, metadata and causality are verified below by the
    B13 reader and frame selector. Seven-band Stage-0 flags are not B0 gates.
    """
    return [row for row in rows
            if start <= utc(row["timestamp_filename_utc"]) <= analysis
            and (root / row["relative_path"]).is_file()]


def _load_manifest_row(path: Path, imerg_path: Path, date: str) -> dict:
    matches = []
    with path.open(encoding="utf-8") as stream:
        for line in stream:
            row = json.loads(line)
            if row.get("date") == date and str(Path(row.get("path", "")).resolve()).casefold() == str(imerg_path.resolve()).casefold():
                matches.append(row)
    if len(matches) != 1:
        raise ValueError(f"Expected one IMERG completion row; found {len(matches)}")
    return matches[0]


def verify(args) -> dict:
    science, engineering = load_contract()
    mapping = load_sp04()
    start = utc(args.imerg_window_start)
    analysis = start + timedelta(minutes=30)
    if args.engineering_threads < 1 or args.engineering_seed < 0:
        raise ValueError("Engineering threads/seed invalid")
    if args.staging_root.resolve() != Path(os.environ[engineering["staging"]["staging_root_env_var"]]).resolve():
        raise ValueError("Explicit staging root differs from configured environment variable")
    staging = BoundedEnglishStaging(args.staging_root, engineering["staging"]["max_temporary_bytes"], engineering["staging"]["verify_sha256"])
    b13_reader = StagedB13Reader(staging, mapping)
    imerg_reader = StagedIMERGReader(staging, mapping)
    with args.master_index.open(newline="", encoding="utf-8-sig") as stream:
        rows = list(csv.DictReader(stream))
    if not rows:
        raise ValueError("Empty Himawari master index")
    near_rows = b0_candidate_rows(rows, args.himawari_root, start, analysis)
    if not near_rows:
        raise ValueError("No available B13 candidate in the audited window")
    source_paths = [_frame_from_row(args.himawari_root, row).path for row in near_rows] + [args.imerg_file]
    if any(not path.is_file() for path in source_paths):
        raise FileNotFoundError("Required real source missing")
    before = {str(path): {"size_bytes": path.stat().st_size, "sha256": sha256(path)} for path in source_paths}
    candidate_audit = []
    frames = []
    for row in near_rows:
        path = args.himawari_root / row["relative_path"]
        nominal = utc(row["timestamp_filename_utc"])
        x, valid, observed = b13_reader(path, nominal)
        if all(row.get(k) for k in ("start_time", "end_time")) and (
            observed.obs_start != utc(row["start_time"]) or observed.obs_end != utc(row["end_time"])
        ):
            raise ValueError("Himawari master index disagrees with real source metadata")
        if row.get("date_created") and observed.date_created != utc(row["date_created"]):
            raise ValueError("Himawari date_created disagrees with real source metadata")
        if x.shape != (501, 501) or valid.shape != x.shape:
            raise ValueError("Real B13 native shape mismatch")
        if valid.any() and observed.obs_start <= observed.obs_end and observed.obs_end <= analysis:
            frames.append(observed)
        candidate_audit.append({
            "path": str(path), "nominal_time": nominal.isoformat(),
            "obs_start": observed.obs_start.isoformat(), "obs_end": observed.obs_end.isoformat(),
            "date_created": observed.date_created.isoformat() if observed.date_created else None,
            "causality_pass": observed.obs_end <= analysis,
            "b13_eligible": bool(valid.any() and observed.obs_start <= observed.obs_end and observed.obs_end <= analysis),
            "quality_class_from_stage0_index": row.get("quality_class"),
            "b13_valid_count": int(valid.sum()), "b13_invalid_count": int((~valid).sum()),
        })
    selected = select_latest_causal_frame(frames, analysis)
    manifest_row = _load_manifest_row(args.imerg_manifest, args.imerg_file, start.date().isoformat())
    with staging.local(args.imerg_file) as local:
        with netCDF4.Dataset(str(local)) as ds:
            converted_attrs = {name: str(ds.getncattr(name)) for name in ds.ncattrs()}
            imerg_time_slots = len(ds.dimensions["time"])
    validate_final_provenance(converted_attrs, manifest_row, args.imerg_file.stat().st_size)
    if imerg_time_slots != 48:
        raise ValueError("IMERG day must have 48 converted half-hour slots")
    yunnan = read_frozen_yunnan_mask(args.frozen_mask, mapping)
    record = B0Record(
        sample_id="real_engineering_" + start.strftime("%Y%m%dT%H%M%SZ"),
        imerg_window_start=start, frames=tuple(frames), imerg_path=args.imerg_file,
        imerg_index=args.imerg_index, imerg_product="IMERG", imerg_version="V07",
        imerg_run_type="Final", imerg_provenance_verified=True,
    )
    sample = B0Dataset([record], mapping, yunnan, b13_reader, imerg_reader, frozen_mask_path=args.frozen_mask)[0]
    if sample.himawari_path != selected.path or sample.himawari_obs_end > sample.analysis_time:
        raise ValueError("Real sample failed latest-frame/causality contract")
    if sample.imerg_window_start != start or sample.imerg_window_end != analysis:
        raise ValueError("IMERG converted time/window contract mismatch")
    torch.set_num_threads(args.engineering_threads)
    torch.manual_seed(args.engineering_seed)
    model = B0Model().eval()
    batch = B0Batch(
        torch.from_numpy(sample.x_b13[None, None].copy()),
        torch.from_numpy(sample.b13_valid_mask[None, None].copy()),
        torch.from_numpy(sample.y_imerg[None, None].copy()),
        torch.from_numpy(sample.imerg_valid_mask[None, None].copy()),
        torch.from_numpy(sample.yunnan_eval_mask[None, None].copy()),
    )
    with torch.no_grad():
        output, losses = engineering_forward_step(
            model, batch, focal_alpha=args.engineering_focal_alpha,
            focal_gamma=args.engineering_focal_gamma,
            quantile_axis_reduction=engineering["loss"]["quantile_axis_reduction"],
        )
    if not all(bool(torch.isfinite(t).all()) for t in (output.rain_logit, output.rain_prob, output.conditional_quantiles_log,
                                                       output.conditional_quantiles_physical, output.threshold_censored_mean, losses.total)):
        raise FloatingPointError("Real engineering forward/loss nonfinite")
    if not bool((output.conditional_quantiles_log[:, 1:] > output.conditional_quantiles_log[:, :-1]).all()):
        raise FloatingPointError("Real engineering quantile crossing")
    after = {str(path): {"size_bytes": path.stat().st_size, "sha256": sha256(path)} for path in source_paths}
    if before != after or staging._owned or any(not row.cleanup_success for row in staging.records):
        raise RuntimeError("Source integrity or bounded staging cleanup failed")
    return {
        "scope": "ENGINEERING_ONLY_REAL_SAMPLE_VERIFICATION",
        "formal_training_started": False,
        "science_contract_status": science["execution_status"]["B0_FORMAL_SCIENTIFIC_CONTRACT"],
        "fixed_python": sys.executable,
        "torch_version": torch.__version__, "numpy_version": np.__version__, "netcdf4_version": netCDF4.__version__,
        "master_index_path": str(args.master_index), "master_index_sha256": sha256(args.master_index),
        "master_index_rows": len(rows), "b13_candidate_rows": len(near_rows),
        "candidate_audit": candidate_audit,
        "sample_id": sample.sample_id,
        "analysis_time": analysis.isoformat(), "imerg_window_start": start.isoformat(), "imerg_window_end": analysis.isoformat(),
        "selected_himawari_path": str(sample.himawari_path), "selected_nominal_time": sample.himawari_nominal_time.isoformat(),
        "selected_obs_start": sample.himawari_obs_start.isoformat(), "selected_obs_end": sample.himawari_obs_end.isoformat(),
        "selected_date_created": sample.himawari_date_created.isoformat() if sample.himawari_date_created else None,
        "causality_pass": True, "historical_operational_availability_claimed": False,
        "imerg_file": str(args.imerg_file), "imerg_manifest_path": str(args.imerg_manifest),
        "imerg_manifest_sha256": sha256(args.imerg_manifest), "imerg_manifest_row": manifest_row,
        "imerg_global_attrs": converted_attrs, "imerg_time_slots": imerg_time_slots,
        "imerg_v07_final_provenance_verified": True,
        "frozen_mask_path": str(args.frozen_mask), "frozen_mask_sha256": sha256(args.frozen_mask),
        "frozen_mask_true_cells_target": int(yunnan.sum()),
        "sample_roles": {"observation_eligible": sample.observation_eligible, "supervised_eligible": sample.supervised_eligible,
                         "inference_eligible": sample.inference_eligible, "internal_test_eligible": sample.internal_test_eligible,
                         "external_validation_eligible": sample.external_validation_eligible, "qc_status": sample.qc_status},
        "b13_valid_count": int(sample.b13_valid_mask.sum()), "b13_invalid_count": sample.b13_invalid_count,
        "b13_valid_fraction": sample.b13_valid_fraction, "target_support_fraction_min": float(sample.target_support_fraction.min()),
        "target_support_fraction_max": float(sample.target_support_fraction.max()),
        "imerg_valid_count_target": int(sample.imerg_valid_mask.sum()),
        "imerg_valid_zero_count_target": int(((sample.y_imerg == 0) & sample.imerg_valid_mask).sum()),
        "loss_valid_supervised_yunnan_count": losses.valid_supervised_count,
        "loss_rainy_valid_yunnan_count": losses.rainy_valid_count,
        "loss_finite": True, "loss_value_omitted_as_non_scientific": True,
        "engineering_test_only_focal_alpha": args.engineering_focal_alpha,
        "engineering_test_only_focal_gamma": args.engineering_focal_gamma,
        "development_focal_parameters_frozen": False,
        "engineering_seed": args.engineering_seed, "engineering_threads": args.engineering_threads,
        "native_feature_shape": output.native_feature_shape, "target_feature_shape": output.target_feature_shape,
        "rain_logit_shape": list(output.rain_logit.shape), "quantile_shape": list(output.conditional_quantiles_log.shape),
        "quantiles_strictly_monotonic": True, "extreme_exceedance_status": output.exceedance_probability(100.0)["status"],
        "source_integrity_before": before, "source_integrity_after_equal": True,
        "staging_records": [asdict(row) for row in staging.records],
        "staging_peak_temporary_bytes": max(row.temporary_bytes for row in staging.records),
        "staging_cleanup_all_success": True,
    }


def main():
    args = _args()
    output_root = (REPO_ROOT / "docs/b0_real_sample_verification/runs").resolve()
    out = args.output.resolve()
    if not out.is_relative_to(output_root) or out.name != "evidence.json" or out.parent.exists():
        raise ValueError("Output must be new versioned run/evidence.json under docs/b0_real_sample_verification/runs")
    result = verify(args)
    out.parent.mkdir(parents=True, exist_ok=False)
    with out.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(result, stream, ensure_ascii=False, indent=2, default=str)
        stream.write("\n")
    print(json.dumps({"output": str(out), "sample_id": result["sample_id"], "selected_obs_end": result["selected_obs_end"],
                      "loss_finite": result["loss_finite"], "staging_cleanup_all_success": result["staging_cleanup_all_success"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
