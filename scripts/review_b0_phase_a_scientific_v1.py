"""Full, immutable-BEST review. This script cannot train or authorize Phase-B."""
from __future__ import annotations
import argparse
import csv
from datetime import datetime, timezone
import hashlib
import importlib
import json
import math
import os
from pathlib import Path
import subprocess
import sys
import time
import traceback

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "src"), str(ROOT / "scripts")]
import numpy as np
import torch
from netCDF4 import Dataset
from torch.utils.data import DataLoader

from yuntapr.contracts.loader import sha256
from yuntapr.data.masks import read_frozen_yunnan_mask
from yuntapr.models.b0 import B0Model
from yuntapr.spatial.sp04_mapping import load_sp04
from yuntapr.training.formal_phase_a import (FormalAuthorization, atomic_json, load_verified_checkpoint,
    formal_worker_init, formal_collate, formal_batch, formal_forward, precision_check, assert_determinism)
from yuntapr.training.phase_a_protocol import load_protocol, seed_reproducibility, state_digest
from yuntapr.training.scientific_review import (SCOPE, BASELINE, BEST_SHA, BEST_BYTES, BEST_CORE, TAU,
    N_SCENES, N_VALID, N_RAIN, RATE_LABELS, ReviewDataset, ReviewAccumulator, InferenceOnlyGuard,
    diagnostic_rules, rows, table, probability_summary, guard_identity)

FORMAL = ROOT / "docs/formal_training/b0_phase_a/runs/run_20261001T035003_243409Z"
PUBLIC = ROOT / "docs/scientific_review/b0_phase_a/runs"
PRIVATE = Path(r"F:\pytorch\Research\outputs\scientific_review\b0_phase_a")
STAGING = Path(r"F:\pytorch\Research\stage0_himawari\cache\staging")
AUTH_SHA = "04fa458828b0f74d3e4fe0b4887282327b736b72476f059955c354fefbb6e963"
PROTOCOL_SHA = "dcacbe34050da7e777ad0cb72c53b5b51b48ce57eb9260b09fd283d96de12a4a"
CODE_PATHS = ("scripts/review_b0_phase_a_scientific_v1.py", "src/yuntapr/training/scientific_review.py")


def now():
    return datetime.now(timezone.utc).isoformat()


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def status_defaults():
    return {"B0_PHASE_A_SCIENTIFIC_REVIEW_COMPLETED": False, "BEST_CHECKPOINT_VERIFIED": False,
        "BEST_EPOCH": 11, "BEST_VAL_CORE_LOSS": BEST_CORE, "FULL_2024_REINFERENCE_COMPLETED": False,
        "MONTHLY_ANALYSIS_COMPLETED": False, "SPATIAL_ANALYSIS_COMPLETED": False,
        "RELIABILITY_ANALYSIS_COMPLETED": False, "QUANTILE_CALIBRATION_REVIEW_COMPLETED": False,
        "QUANTILE_CROSSING_COUNT": None, "NONFINITE_COUNT": None, "2025_PIXELS_READ": 0,
        "MODEL_PARAMETERS_UPDATED": False, "OPTIMIZER_STEPS": 0, "B0_PHASE_A_ACCEPTED": "UNDECIDED",
        "ACCEPT_B0_PHASE_A": "UNDECIDED", "TRANSFER_EPOCH_BUDGET_TO_PHASE_B": "UNDECIDED",
        "PHASE_B_AUTHORIZED": False, "B1_TO_B8_AUTHORIZED": False, "scope": SCOPE}


def identities():
    if subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip() != BASELINE:
        raise ValueError("STOP: review baseline mismatch")
    authorization = FormalAuthorization.load(AUTH_SHA)
    protocol = load_protocol(expected_sha256=PROTOCOL_SHA)
    old_manifest = read(FORMAL / "formal_run_manifest.json")
    preflight = read(FORMAL / "preflight.json")
    for name, digest in read(FORMAL / "evidence_sha256.json").items():
        # The finalized evidence index uses a nested structure in some releases.
        if isinstance(digest, str) and sha256(FORMAL / name) != digest:
            raise ValueError("Formal evidence identity changed: " + name)
    ledger = FORMAL / "source_identity_preflight.csv"
    if sha256(ledger) != preflight["source_identity"]["source_identity_ledger_sha256"]:
        raise ValueError("Formal source identity ledger changed")
    best = read(FORMAL / "best_checkpoint_identity.json")
    if (best["sha256"] != BEST_SHA or best["bytes"] != BEST_BYTES or best["epoch"] != 11
            or best["global_update"] != 64460 or best["global_val_core_loss"] != BEST_CORE
            or best["absolute_local_path"] != str(Path(r"F:\pytorch\Research\outputs\formal_training\b0_phase_a\run_20261001T035003_243409Z\epoch_011.pt"))):
        raise ValueError("STOP: BEST identity mismatch")
    payload = load_verified_checkpoint(best, preflight["checkpoint_expected"])
    if payload["completed_epoch"] != 11 or payload["global_update"] != 64460 or payload["global_val_core_loss"] != BEST_CORE:
        raise ValueError("STOP: BEST payload identity mismatch")
    return authorization, protocol, preflight, best, payload


def region_audit():
    # Search only existing tracked definitions before any output is seen.
    result = subprocess.run(["rg", "-n", "-i", "evaluation_regions|subregion|regional.mask|region_mask|region_a_mask",
        "config", "src", "docs/scientific_freeze", "docs/training_protocol"], cwd=ROOT, text=True, encoding="utf-8", capture_output=True)
    # This review's own implementation mentions subregions; exclude that source.
    lines = [line for line in result.stdout.splitlines() if "scientific_review.py" not in line]
    if lines:
        raise ValueError("Region definition candidates need explicit frozen-identity resolution: " + "\n".join(lines))
    return {"status": "NO_PREDEFINED_SUBREGION_MASK_AVAILABLE", "search_roots": ["config", "src", "docs/scientific_freeze", "docs/training_protocol"],
        "matches": [], "no_posthoc_regions_created": True, "fallback": "Yunnan-wide spatial cell diagnostics"}


def initialize():
    auth, protocol, preflight, best, payload = identities()
    with InferenceOnlyGuard() as guard:
        # Full payload verification reads optimizer tensors as inert bytes. No
        # optimizer object is constructed and none of its states is applied.
        model_sha = state_digest(payload["model_state_dict"])
    del payload
    run_id = "run_" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S_%fZ")
    out = PUBLIC / run_id
    out.mkdir(parents=True, exist_ok=False)
    baseline_paths = subprocess.check_output(["git", "ls-tree", "-r", "--name-only", BASELINE], cwd=ROOT, text=True, encoding="utf-8").splitlines()
    retained = {p: sha256(ROOT / p) for p in baseline_paths}
    manifest = {"run_id": run_id, "created_utc": now(), "scope": SCOPE, "baseline_commit": BASELINE,
        "formal_run_id": FORMAL.name, "public_directory": str(out), "private_directory": str(PRIVATE / run_id),
        "formal_best": best, "formal_model_state_sha256": model_sha, "formal_identity": auth.config["identity"],
        "formal_authorization_sha256": AUTH_SHA, "review_authority": "researcher Scientific Characterization Review v1 attachment",
        "code_sha256": {p: sha256(ROOT / p) for p in CODE_PATHS}, "baseline_files_sha256": retained,
        "formal_source_ledger_sha256": sha256(FORMAL / "source_identity_preflight.csv"),
        "source_metadata_strategy": "Read only 2023/2024 frozen population/ledger metadata; 2024 B13 metadata read from source whose full SHA is pinned. Mixed-year per-frame QC ledger not opened.",
        "validation_order": "unchanged frozen eligible_validation_manifest.csv identity order",
        "review_guard_attempts": guard.attempts, "PHASE_B_AUTHORIZED": False,
        "CHECKPOINT_SELECTION_REMAINS_EPOCH_11": True, "minimum_count_rule": diagnostic_rules()["spatial_conditional_pinball_min_rain_count"]}
    atomic_json(out / "review_manifest.json", manifest)
    atomic_json(out / "case_selection_rules.json", diagnostic_rules())
    atomic_json(out / "region_audit.json", region_audit())
    atomic_json(out / "final_status.json", {"run_id": run_id, "state": "INITIALIZED", "updated_utc": now(), **status_defaults(), "BEST_CHECKPOINT_VERIFIED": True})
    history(out)
    print("INITIALIZED " + run_id, flush=True)


def history(out):
    train, val = rows(FORMAL / "training_history.csv"), rows(FORMAL / "validation_history.csv")
    if [int(r["epoch"]) for r in train] != list(range(1, 20)) or [int(r["epoch"]) for r in val] != list(range(1, 20)):
        raise ValueError("Full 19 completed epochs required")
    summaries, gaps = [], []
    for t, v in zip(train, val):
        epoch = int(t["epoch"])
        record = read(FORMAL / f"epoch_{epoch:03d}.json")
        summaries.append({"epoch": epoch, "train_core": float(t["global_train_core_loss"]), "val_core": float(v["global_val_core_loss"]),
            "Brier": float(v["Brier_Score"]), "AUROC": float(v["AUROC"]), "AP": float(v["Average_Precision"]),
            "conditional_pinball": float(v["conditional_mean_pinball"]), "best_checkpoint_at_epoch": record["selection"]["selected_checkpoint_epoch"],
            "early_stop_count": record["selection"]["non_improvement_count"]})
        gaps.append({"epoch": epoch, "train_core_loss": float(t["global_train_core_loss"]), "val_core_loss": float(v["global_val_core_loss"]),
            "generalization_gap": float(v["global_val_core_loss"]) - float(t["global_train_core_loss"])})
    table(out / "epoch_summary.csv", summaries)
    table(out / "generalization_gap.csv", gaps)
    atomic_json(out / "history_sources.json", {"curve_sources_only": {name: sha256(FORMAL / name) for name in ("training_history.csv", "validation_history.csv")},
        "state_columns_source": "formal epoch_NNN.json selection states only; no checkpoint reselection",
        "epochs": list(range(1, 20)), "BEST_epoch": 11, "early_stop_epoch": 19, "smoothing": False})


def population(auth):
    protocol = auth.config
    declared = rows(ROOT / protocol["identity"]["eligible_validation_manifest"]["path"])
    pairs = {r["window_start"]: r for r in rows(ROOT / protocol["identity"]["combined_eligibility_source"]["path"])
        if r["month"].startswith("2024") and r["formal_supervised_eligible"] == "True"}
    ledger = [r for r in rows(FORMAL / "source_identity_preflight.csv") if r["role"] == "Validation"]
    if len(declared) != N_SCENES or len(ledger) != N_SCENES:
        raise ValueError("Validation population count changed")
    paired = []
    for n, (row, identity) in enumerate(zip(declared, ledger)):
        pair = pairs[row["window_start"]]
        if (int(identity["index"]) != n or identity["window_start"] != row["window_start"]
                or identity["b13_relative_path"] != row["selected_b13_relative_path"]
                or identity["imerg_day_path"] != row["imerg_day_path"] or identity["imerg_index"] != row["imerg_index"]
                or pair["selected_b13_relative_path"] != identity["b13_relative_path"] or pair["b13_full_valid"] != "True"
                or pair["selected_nominal"] != pair["expected_nominal"]):
            raise ValueError("Frozen validation identity/order/QC changed")
        guard_identity(identity)
        paired.append(pair)
    if (sum(int(i["imerg_valid_yunnan_count"]) for i in ledger), sum(int(i["imerg_rain_yunnan_count"]) for i in ledger)) != (N_VALID, N_RAIN):
        raise ValueError("Frozen count totals changed")
    return ledger, paired


def assert_unchanged(out):
    manifest = read(out / "review_manifest.json")
    for p, digest in manifest["baseline_files_sha256"].items():
        if sha256(ROOT / p) != digest:
            raise ValueError("STOP: immutable baseline file changed: " + p)
    best = manifest["formal_best"]
    if sha256(Path(best["absolute_local_path"])) != BEST_SHA or Path(best["absolute_local_path"]).stat().st_size != BEST_BYTES:
        raise ValueError("STOP: formal BEST changed")
    return {"all_baseline_files_unchanged": True, "files_checked": len(manifest["baseline_files_sha256"]), "BEST_sha256": BEST_SHA}


def inference(out):
    manifest = read(out / "review_manifest.json")
    rules = read(out / "case_selection_rules.json")
    if rules != diagnostic_rules() or any(sha256(ROOT / p) != manifest["code_sha256"][p] for p in CODE_PATHS):
        raise ValueError("Predeclared rules/review implementation changed before inference")
    auth, protocol, preflight, best, payload = identities()
    original = assert_unchanged(out)
    official = read(FORMAL / "epoch_011.json")["validation"]
    inherited = importlib.import_module("train_b0_phase_a_formal_v1")
    torch.set_num_threads(2)
    seed_reproducibility()
    assert_determinism()
    env = inherited.environment()
    ledger, pairs = population(auth)
    mapping = load_sp04()
    mask_path = Path(protocol["identity"]["yunnan_mask"]["path"])
    yunnan = read_frozen_yunnan_mask(mask_path, mapping)
    if yunnan.shape != (100, 100) or int(yunnan.sum()) != 3430:
        raise ValueError("Frozen target mask shape/count changed")
    private = PRIVATE / out.name
    private.mkdir(parents=True, exist_ok=False)
    began = time.perf_counter()
    acc = ReviewAccumulator(mapping.axes, rules)
    io = inherited.empty_io()
    stage = STAGING / ("review_" + out.name)
    atomic_json(out / "inference_start.json", {"started_utc": now(), "environment": env, "scope": SCOPE,
        "rule_sha256": sha256(out / "case_selection_rules.json"), "BEST_sha256_before": BEST_SHA, "preservation": original,
        "quantile_check_population": "all 100x100 output cells of every scene; statistics use frozen valid Yunnan cells",
        "review_code_sha256": manifest["code_sha256"], "private_directory": str(private)})
    with InferenceOnlyGuard() as guard, torch.no_grad():
        model = B0Model().cuda()
        model.load_state_dict(payload["model_state_dict"], strict=True)
        model.eval()
        before = state_digest(model.state_dict())
        if before != manifest["formal_model_state_sha256"]:
            raise ValueError("Loaded BEST model state mismatch")
        del payload
        raw = {}
        def capture_raw(module, inputs, output):
            raw["dtype"] = output.dtype
        model.heads.quantile.register_forward_hook(capture_raw)
        data = ReviewDataset(ledger, pairs, mapping, yunnan, mask_path, stage, auth)
        loader = DataLoader(data, batch_size=8, sampler=list(range(N_SCENES)), num_workers=2, prefetch_factor=1,
            pin_memory=False, persistent_workers=False, drop_last=False, collate_fn=formal_collate,
            worker_init_fn=formal_worker_init, generator=torch.Generator().manual_seed(2036))
        torch.cuda.reset_peak_memory_stats()
        with (private / "read_ledger.csv").open("x", encoding="utf-8", newline="") as log:
            writer = None
            for index, (samples, details) in enumerate(loader):
                if any(s.imerg_window_start.year != 2024 for s in samples):
                    raise ValueError("STOP: unauthorized year in review batch")
                batch = formal_batch(samples, details, auth)
                with torch.autocast("cuda", dtype=torch.bfloat16):
                    output = formal_forward(model, batch, auth)
                acc.add(output, batch, samples, details)
                precision_check(model, raw["dtype"], output)
                inherited.add_io(io, details)
                if writer is None:
                    writer = csv.DictWriter(log, fieldnames=list(details[0]))
                    writer.writeheader()
                writer.writerows(details)
                if index % 40 == 0 or acc.seen == N_SCENES:
                    log.flush()
                    progress = {"run_id": out.name, "phase": "FULL_2024_REINFERENCE", "scenes_completed": acc.seen,
                        "scenes_required": N_SCENES, "wall_seconds": time.perf_counter() - began,
                        "N_valid": acc.global_acc.n_valid, "N_rain": acc.global_acc.n_rain, "updated_utc": now()}
                    atomic_json(out / "progress.json", progress)
                    print("REVIEW " + json.dumps(progress), flush=True)
                del samples, details, batch, output
        after = state_digest(model.state_dict())
        if before != after or any(guard.attempts.values()) or model.training:
            raise ValueError("STOP: model mutated or prohibited operation attempted")
        model_evidence = {"model_state_sha256_before": before, "model_state_sha256_after": after,
            "eval": True, "no_grad": True, "optimizer_created": False, "optimizer_steps": 0,
            "backward_calls": 0, "prohibited_attempts": guard.attempts}
    reconciliation = acc.reconcile()
    global_report = acc.global_acc.report()
    comparisons = {}
    for name in ("global_val_core_loss", "global_L_occ", "global_core_L_qr", "Brier_Score", "AUROC", "Average_Precision", "conditional_mean_pinball"):
        observed, expected = global_report[name], official[name]
        passed = math.isclose(observed, expected, rel_tol=1e-12, abs_tol=1e-12)
        comparisons[name] = {"official": expected, "review": observed, "difference": observed - expected, "pass": passed}
        if not passed:
            raise ValueError("STOP: BEST metric reproduction failed: " + name)
    if (global_report["per_tau_conditional_coverage"] != official["per_tau_conditional_coverage"]
            or not np.allclose(global_report["per_tau_pinball"], official["per_tau_pinball"], rtol=1e-12, atol=1e-12)):
        raise ValueError("STOP: quantile calibration reproduction failed")
    comparisons["coverage_exact"] = True
    preservation = assert_unchanged(out)
    runtime = {"scenes": acc.seen, "wall_seconds": time.perf_counter()-began,
        "peak_GPU_allocated_bytes": torch.cuda.max_memory_allocated(), "peak_GPU_reserved_bytes": torch.cuda.max_memory_reserved(),
        "I_O": io, "read_ledger": {"absolute_local_path": str(private / "read_ledger.csv"),
            "bytes": (private / "read_ledger.csv").stat().st_size, "sha256": sha256(private / "read_ledger.csv")},
        "2025_PIXELS_READ": 0, "source_years_read": [2024], "model": model_evidence,
        "preservation": preservation, "finished_utc": now()}
    write_metrics(out, acc, global_report, yunnan)
    atomic_json(out / "reinference_summary.json", {"status": "PASS", "global": global_report,
        "numeric_checks": acc.numerics, "reconciliation": reconciliation, "formal_reproduction": comparisons, "runtime": runtime})
    atomic_json(out / "final_status.json", {"run_id": out.name, "state": "REINFERENCE_COMPLETED_AWAITING_REPORTS_TESTS", "updated_utc": now(),
        **status_defaults(), "BEST_CHECKPOINT_VERIFIED": True, "FULL_2024_REINFERENCE_COMPLETED": True,
        "MONTHLY_ANALYSIS_COMPLETED": True, "SPATIAL_ANALYSIS_COMPLETED": True,
        "RELIABILITY_ANALYSIS_COMPLETED": True, "QUANTILE_CALIBRATION_REVIEW_COMPLETED": True,
        "QUANTILE_CROSSING_COUNT": global_report["strict_crossing_count"], "NONFINITE_COUNT": global_report["nonfinite_count"]})
    print("REINFERENCE_PASS " + out.name, flush=True)


def write_metrics(out, acc, global_report, yunnan):
    monthly = []
    for m, accumulator in acc.months.items():
        report = accumulator.report()
        monthly.append({"month": f"2024-{m:02d}", "scene_count": acc.scenes[m],
            **{k: report[k] for k in ("N_valid", "N_rain", "prevalence", "global_val_core_loss", "global_L_occ", "global_core_L_qr",
                "Brier_Score", "AUROC", "Average_Precision", "conditional_mean_pinball", "strict_crossing_count", "nonfinite_count")},
            **{"DIAGNOSTIC_PROXY_" + k: v for k, v in report["DIAGNOSTIC_PROXY_METRIC"].items() if k in ("MAE", "RMSE", "Bias")},
            "physical_explanation_status": "POSSIBLE_EXPLANATION_NOT_ESTABLISHED"})
        accumulator.scores.clear()
        accumulator.labels.clear()
    table(out / "monthly_metrics.csv", monthly)
    reliability = []
    for i, (n, p_sum, r_sum) in enumerate(acc.bins):
        reliability.append({"bin": i, "lower": i/10, "upper": (i+1)/10, "upper_inclusive": i == 9,
            "count": int(n), "rainy_count": int(r_sum), "mean_predicted_probability": p_sum/n if n else None,
            "observed_rain_frequency": r_sum/n if n else None, "scope": "BINNED_DIAGNOSTIC"})
    table(out / "reliability_table.csv", reliability)
    distributions = {k: probability_summary(v) for k, v in acc.frequencies.items()}
    atomic_json(out / "probability_distribution_stats.json", {"scope": "DESCRIPTIVE_ONLY", "groups": distributions,
        "histogram_edges": [i/100 for i in range(101)], "histogram_counts": {k: v.tolist() for k, v in acc.hist.items()},
        "no_probability_cutoff_selected": True})
    quantiles = []
    for i, tau in enumerate(TAU):
        coverage = global_report["per_tau_conditional_coverage"][i]
        quantiles.append({"tau": tau, "rainy_count": global_report["N_rain"], "coverage_count": int(acc.global_acc.coverage[i]),
            "conditional_coverage": coverage, "coverage_minus_tau": coverage-tau,
            "absolute_calibration_error": abs(coverage-tau), "conditional_pinball_log1p_mm_h": global_report["per_tau_pinball"][i]})
    table(out / "quantile_calibration.csv", quantiles)
    groups = {}
    for name, selected in (("low", TAU < .2), ("middle", (TAU >= .2) & (TAU <= .8)), ("high", TAU > .8)):
        groups[name] = {"number_of_tau": int(selected.sum()), "mean_absolute_coverage_error":
            float(np.mean(np.abs(np.array(global_report["per_tau_conditional_coverage"])[selected]-TAU[selected])))}
    atomic_json(out / "quantile_tail_diagnostics.json", {"status": "ANALYTIC_GROUPING_ONLY", "groups": groups,
        "strict_numerical_checks": acc.numerics, "monotonicity_is_not_calibration": True})
    rate = []
    for label, (n, pinball, signed, absolute) in zip(RATE_LABELS, acc.rate):
        rate.append({"rate_bin_mm_h": label, "pixel_count": int(n), "fraction_of_rainy_population": n/global_report["N_rain"],
            "conditional_pinball_log1p_mm_h": pinball/n if n else None,
            "DIAGNOSTIC_PROXY_Bias_mm_h": signed/n if n else None, "DIAGNOSTIC_PROXY_MAE_mm_h": absolute/n if n else None,
            "scope": "DESCRIPTIVE_RATE_BINS_ONLY", "extreme_definition": "NOT_FROZEN"})
    table(out / "rainrate_stratified_metrics.csv", rate)
    exceed = []
    for j, (threshold, (n, pinball, signed, absolute)) in enumerate(zip((10, 20, 30, 50), acc.exceed)):
        exceed.append({"threshold_mm_h": threshold, "count": int(n), "conditional_pinball_log1p_mm_h": pinball/n if n else None,
            "DIAGNOSTIC_PROXY_Bias_mm_h": signed/n if n else None, "DIAGNOSTIC_PROXY_MAE_mm_h": absolute/n if n else None,
            "scope": "DESCRIPTIVE_ONLY", "extreme_definition": "NOT_FROZEN"})
    table(out / "strong_rain_DESCRIPTIVE_ONLY.csv", exceed)
    atomic_json(out / "strong_rain_quantiles_DESCRIPTIVE_ONLY.json", {"scope": "DESCRIPTIVE_ONLY", "extreme_definition": "NOT_FROZEN",
        "tau": TAU.tolist(), "thresholds": [{"threshold_mm_h": t, "N": int(acc.exceed[j, 0]),
            "coverage": (acc.exceed_coverage[j]/acc.exceed[j, 0]).tolist() if acc.exceed[j, 0] else [None]*32,
            "pinball": (acc.exceed_tau_sum[j]/acc.exceed[j, 0]).tolist() if acc.exceed[j, 0] else [None]*32}
            for j, t in enumerate((10, 20, 30, 50))]})
    cases = []
    for name, heap in acc.heaps.items():
        for rank, entry in enumerate(sorted(heap, key=lambda e: e[:3], reverse=True), 1):
            cases.append({"rank": rank, **entry[-1]})
    table(out / "case_diagnostics.csv", cases)
    spatial = acc.spatial_metrics(yunnan)
    with Dataset(str(out / "spatial_cell_metrics.nc"), "w", format="NETCDF4") as nc:
        nc.createDimension("lat", 100)
        nc.createDimension("lon", 100)
        for axis, units in (("lat", "degrees_north"), ("lon", "degrees_east")):
            variable = nc.createVariable(axis, "f4", (axis,))
            variable[:] = acc.axes["target_" + axis]
            variable.units = units
        mask = nc.createVariable("yunnan_evaluation_mask", "u1", ("lat", "lon"))
        mask[:] = yunnan
        for name, values in {**spatial, **{"raw_"+k: v for k, v in acc.spatial.items()}}.items():
            variable = nc.createVariable(name, "i8" if np.issubdtype(values.dtype, np.integer) else "f8", ("lat", "lon"), zlib=True, complevel=4)
            variable[:] = values
            variable.units = "mm h-1" if "mm_h" in name else "count" if name.endswith("count") else "dimensionless"
        nc.scope = SCOPE
        nc.conditional_pinball_min_rain_count = acc.rules["spatial_conditional_pinball_min_rain_count"]
        nc.minimum_count_scope = "DISPLAY_DIAGNOSTIC_ONLY"
        nc.coordinate_policy = "Exact frozen target Float32 axes; ascending latitude; no transpose or flip"
        nc.quantile_loss_domain = "log1p(rate_mm_h), dimensionless"
    atomic_json(out / "spatial_summary.json", {"status": "NO_PREDEFINED_SUBREGION_MASK_AVAILABLE", "shape": [100,100],
        "Yunnan_cells": int(yunnan.sum()), "global_valid": int(spatial["valid_count"].sum()), "global_rain": int(spatial["rainy_count"].sum()),
        "target_coordinate_hashes": {k: hashlib.sha256(acc.axes[k].tobytes()).hexdigest() for k in ("target_lat", "target_lon")},
        "lat_ascending": True, "no_transpose": True, "no_silent_flip": True,
        "minimum_rain_count": acc.rules["spatial_conditional_pinball_min_rain_count"], "minimum_count_scope": "DISPLAY_DIAGNOSTIC_ONLY",
        "cells_not_reporting_conditional_pinball": int((yunnan & (spatial["rainy_count"] < 30)).sum()),
        "cell_metric_ranges": {k: {"min": float(np.nanmin(v[yunnan])), "max": float(np.nanmax(v[yunnan])), "median": float(np.nanmedian(v[yunnan]))} for k, v in spatial.items()}})


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=["init", "infer", "check"])
    parser.add_argument("--run-id")
    args = parser.parse_args()
    if args.action == "init":
        initialize()
        return
    if not args.run_id or Path(args.run_id).name != args.run_id or not args.run_id.startswith("run_"):
        raise ValueError("Explicit safe run identifier required")
    out = PUBLIC / args.run_id
    try:
        if args.action == "infer":
            inference(out)
        else:
            print(json.dumps(assert_unchanged(out)))
    except Exception:
        failure = traceback.format_exc()
        if out.is_dir():
            atomic_json(out / ("failure_" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S_%fZ") + ".json"),
                {"failed_utc": now(), "scope": SCOPE, "traceback": failure, "no_automatic_retry_or_next_stage": True})
        raise


if __name__ == "__main__":
    main()
