"""Phase-A protocol evidence only: no optimizer, model fitting, or checkpoints."""
from __future__ import annotations
import argparse
from collections import Counter, defaultdict
from contextlib import nullcontext
import csv
from dataclasses import asdict
from datetime import datetime, timedelta, timezone
import hashlib
import inspect
import io
import json
import math
import os
from pathlib import Path
import subprocess
import sys
import time
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT/"src"), str(ROOT/"scripts")]
import netCDF4
import numpy as np
import torch
from yuntapr.contracts.loader import load_contract, sha256
from yuntapr.data.imerg_v07 import decode_imerg, validate_final_provenance
from yuntapr.data.masks import read_frozen_yunnan_mask
from yuntapr.data.sample_schema import utc, HimawariFrame
from yuntapr.data.dataset_b0 import B0Record
from yuntapr.data.staging import BoundedEnglishStaging
from yuntapr.losses.focal import focal_bce_sum
from yuntapr.losses.total_loss import b0_core_loss
from yuntapr.models.b0 import B0Model
from yuntapr.spatial.sp04_mapping import load_sp04
from yuntapr.training.batch_contract import B0Batch
from benchmark_b0_gpu_feasibility import dataset_new, to_cuda, parameter_hash
from fit_phase_a_v1_1 import HROOT, RAW, MASK, PRIOR as DEVELOPMENT

BASELINE = "bc287755cfade53dd5a52a32c99c7326e2c2dfe8"
PRIOR = ROOT/"docs/b0_pretraining_closure/runs/run_20260930T095416Z"
GPU = ROOT/"docs/gpu_training_feasibility/runs/run_20260930T154142Z"
STAGING = Path(r"F:\pytorch\Research\stage0_himawari\cache\staging")


def save(path, value):
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2, allow_nan=False, default=str)
        stream.write("\n")


def text_file(path, value):
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        stream.write(value.rstrip()+"\n")


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def read_csv(path):
    with path.open(encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def table(path, rows, keys=None):
    keys = keys or list(dict.fromkeys(k for row in rows for k in row))
    with path.open("x", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=keys, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def population():
    prior = read_json(PRIOR/"manifest.json")
    for name in ("normalization_phaseA_sample_manifest.csv", "formal_sample_eligibility_2023_2024.csv",
                 "normalization_phaseA_2023_final_eligible.json", "imerg_development_revalidation.json",
                 "formal_sample_counts_2023_2024.csv"):
        if sha256(PRIOR/name) != prior["public_files_sha256"][name]:
            raise ValueError("Pinned evidence changed: "+name)
    rows = read_csv(PRIOR/"formal_sample_eligibility_2023_2024.csv")
    eligible = {year: [r for r in rows if utc(r["window_start"]).year == year and r["formal_supervised_eligible"] == "True"] for year in (2023, 2024)}
    train = read_csv(PRIOR/"normalization_phaseA_sample_manifest.csv")
    if (len(eligible[2023]), len(eligible[2024]), len(train)) != (11720, 11727, 11720):
        raise ValueError("Eligible population count changed")
    if {r["window_start"] for r in train} != {r["window_start"] for r in eligible[2023]}:
        raise ValueError("Train normalization and target eligibility populations differ")
    for year, selected in eligible.items():
        if len({r["window_start"] for r in selected}) != len(selected):
            raise ValueError("Duplicate scene")
        if any(utc(r["window_start"]).month not in range(3, 11) or r["b13_full_valid"] != "True" for r in selected):
            raise ValueError("Invalid eligibility row")
    days = {r["day_path"]: r["sha256"] for r in read_json(PRIOR/"imerg_development_revalidation.json")["days"]}
    return eligible, train, days


def reproducibility_snapshot():
    return {"torch": torch.__version__, "python": sys.executable, "CUDA_runtime": torch.version.cuda,
            "deterministic_algorithms": torch.are_deterministic_algorithms_enabled(),
            "deterministic_warn_only": torch.is_deterministic_algorithms_warn_only_enabled(),
            "cudnn_deterministic": torch.backends.cudnn.deterministic,
            "cudnn_benchmark": torch.backends.cudnn.benchmark,
            "cuda_matmul_allow_tf32": torch.backends.cuda.matmul.allow_tf32,
            "cudnn_allow_tf32": torch.backends.cudnn.allow_tf32,
            "float32_matmul_precision": torch.get_float32_matmul_precision(),
            "torch_initial_seed_process_observation": torch.initial_seed(),
            "torch_CPU_rng_state_sha256": hashlib.sha256(torch.get_rng_state().numpy().tobytes()).hexdigest(),
            "PYTHONHASHSEED": os.environ.get("PYTHONHASHSEED"),
            "CUBLAS_WORKSPACE_CONFIG": os.environ.get("CUBLAS_WORKSPACE_CONFIG"),
            "torch_num_threads": torch.get_num_threads(), "settings_modified_by_snapshot": False,
            "scope": "PROCESS_OBSERVATION_NOT_SEED_POLICY",
            "notes": "No deterministic, TF32 or cuDNN setting changed. Seed policy is undecided; this process seed is not a scientific recommendation."}


def parameter_audit(model):
    params = dict(model.named_parameters())
    groupnorm, biases, convweights, headweights = set(), set(), set(), set()
    for module_name, module in model.named_modules():
        for name, p in module.named_parameters(recurse=False):
            full = f"{module_name}.{name}" if module_name else name
            if isinstance(module, torch.nn.GroupNorm):
                groupnorm.add(full)
            if name == "bias":
                biases.add(full)
            if isinstance(module, torch.nn.Conv2d) and name == "weight":
                convweights.add(full)
            if module_name.startswith("heads.") and name == "weight":
                headweights.add(full)
    count = lambda names: sum(params[n].numel() for n in names)
    excluded = biases | groupnorm
    trainable = {n for n, p in params.items() if p.requires_grad}
    groups = {"A_all_trainable_decay": sorted(trainable),
              "B_decay": sorted(trainable-excluded), "B_no_decay": sorted(trainable & excluded)}
    assert set(groups["B_decay"]).isdisjoint(groups["B_no_decay"])
    assert set(groups["B_decay"]) | set(groups["B_no_decay"]) == trainable
    return {"total_trainable_params": count(trainable), "trainable_tensors": len(trainable),
            "bias_params_including_GroupNorm_beta": count(biases), "GroupNorm_affine_params": count(groupnorm),
            "bias_GroupNorm_overlap_params": count(biases & groupnorm),
            "Conv_weight_params_including_heads": count(convweights), "head_weight_params_subset_of_Conv": count(headweights),
            "A_decayed_params": count(trainable), "B_decayed_params": count(trainable-excluded),
            "B_no_decay_params": count(trainable & excluded), "named_groups": groups,
            "categories_overlap_as_labeled": True, "optimizer_created": False,
            "AdamW_default_signature_observed": str(inspect.signature(torch.optim.AdamW)),
            "candidate_default_reference": {"betas": [.9, .999], "eps": 1e-8, "status": "DEFAULT_REFERENCE"}}


def lock(out):
    actual = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    if actual != BASELINE:
        raise ValueError("Expected baseline differs")
    science, cfg = load_contract()
    eligible, train, _ = population()
    mapping = load_sp04()
    yunnan = read_frozen_yunnan_mask(MASK, mapping)
    # Validation has no separate historical file: materialize a view, preserving source rows.
    keys = ("window_start", "analysis_time", "expected_nominal", "selected_b13_relative_path", "imerg_day_path", "imerg_index")
    validation_view = [{k: r[k] for k in keys} for r in sorted(eligible[2024], key=lambda r: r["window_start"])]
    table(out/"eligible_validation_manifest.csv", validation_view, keys)
    refs = {"scientific_contract_v1.1": ROOT/"config/science_contract_v1.1.yaml",
            "scientific_freeze_v1.1_document": ROOT/science["authoritative_document"],
            "engineering_v4": ROOT/"config/b0_engineering_v4.yaml",
            "phase_a_normalization_artifact": ROOT/science["normalization"]["phase_a"]["artifact"],
            "eligible_train_manifest": PRIOR/"normalization_phaseA_sample_manifest.csv",
            "eligible_validation_manifest": out/"eligible_validation_manifest.csv",
            "combined_eligibility_source": PRIOR/"formal_sample_eligibility_2023_2024.csv",
            "SP04_mapping": ROOT/"config/spatial/sp04_membership_v1.csv",
            "SP04_manifest": ROOT/"config/spatial/sp04_coordinate_manifest_v1.json",
            "yunnan_mask": MASK, "prior_gpu_manifest": GPU/"manifest.json"}
    # Resolve actual membership filename from the checked manifest directory.
    if not refs["SP04_mapping"].is_file():
        matches = list((ROOT/"config/spatial").glob("*.csv"))
        refs["SP04_mapping"] = next(p for p in matches if sha256(p) == mapping.manifest["mapping_csv_sha256"])
    gpu_manifest = read_json(GPU/"manifest.json")
    for name, info in gpu_manifest["public_files"].items():
        if sha256(GPU/name) != info["sha256"]:
            raise ValueError("GPU audit evidence changed: "+name)
    save(out/"baseline_lock.json", {"git_commit": actual, "scientific_freeze": "v1.1", "engineering_config": 4,
         "references": {k: {"path": str(p), "sha256": sha256(p)} for k, p in refs.items()},
         "train_scenes": len(eligible[2023]), "validation_scenes": len(eligible[2024]), "yunnan_target_cells": int(yunnan.sum()),
         "validation_manifest_note": "Deterministic identity view derived from SHA-verified historical combined eligibility. No eligibility changes; rows sorted by window_start; exact LF CSV bytes hashed.",
         "2025_pixels_read": False, "formal_training_started": False, "formal_training_authorized": False})
    repro = reproducibility_snapshot()
    save(out/"reproducibility_settings.json", repro)
    with torch.random.fork_rng(devices=[]):
        torch.manual_seed(20261001)
        model = B0Model()
    heads = {}
    for name in ("occurrence", "quantile"):
        module = getattr(model.heads, name)
        if not isinstance(module, torch.nn.Conv2d):
            raise ValueError("Head differs from direct Conv implementation")
        heads[name] = {"module": type(module).__name__, "input_channels": module.in_channels,
                       "output_channels": module.out_channels, "kernel_size": list(module.kernel_size),
                       "hidden_layers": 0, "bias": module.bias is not None,
                       "parameter_count": sum(p.numel() for p in module.parameters()),
                       "raw_activation": "none", "semantic_transform": "sigmoid" if name == "occurrence" else "softplus positive increments + epsilon; sequential float64 qlog; expm1 physical"}
    save(out/"head_architecture_audit.json", {"heads": heads, "total_head_params": sum(h["parameter_count"] for h in heads.values()),
         "HEAD_IMPLEMENTATION_DETAIL_REQUIRES_PROTOCOL_PIN": True,
         "reason": "v1.1 specifies occurrence/32-quantile semantics and shared heads, but not exact hidden depth or direct 1x1 layer shape in the scientific protocol.",
         "source_sha256": sha256(ROOT/"src/yuntapr/models/probability_heads.py"), "architecture_modified": False})
    save(out/"model_parameter_groups.json", parameter_audit(model))
    focal_source = inspect.getsource(focal_bce_sum)
    save(out/"focal_implementation_audit.json", {"input": "logit", "target": "rainy bool cast to logit dtype, y in {0,1}",
         "FOCAL_ALPHA_SEMANTICS": "ALPHA_IS_POSITIVE_CLASS_WEIGHT", "alpha_t": "alpha*y+(1-alpha)*(1-y)",
         "bce": "softplus(z)-y*z", "p_t": "exp(-bce)=y*sigmoid(z)+(1-y)*(1-sigmoid(z))",
         "gamma_factor": "(1-p_t)**gamma", "pixel_loss": "alpha_t*(1-p_t)**gamma*bce",
         "mask": "imerg_valid_mask AND yunnan_eval_mask", "focal_function_reduction": "sum masked pixel losses",
         "occurrence_core_reduction": "sum masked pixel losses / N_valid_supervised_Yunnan",
         "source": focal_source, "source_sha256": sha256(ROOT/"src/yuntapr/losses/focal.py"),
         "parameter_domain": "0<=alpha<=1, gamma>=0; None rejects, no scientific numeric default",
         "threshold_runtime_precision": "Production comparison uses float32 decoded targets and representable float32 0.1. Exact float32 0.1 is negative; no tolerance/rebinning.",
         "total_loss_source_sha256": sha256(ROOT/"src/yuntapr/losses/total_loss.py"), "status": "EVIDENCE_READY"})
    print("BASELINE_CONTRACT_POPULATION_HEAD_LOCK_PASS", flush=True)


def classify(values, valid):
    selected = values[valid]
    if not np.isfinite(selected).all() or np.any(selected < 0):
        raise ValueError("Valid precipitation must be finite nonnegative")
    rainy = selected > np.float32(.1)
    return selected, rainy


def merge_moments(a, b):
    na, ma, m2a = a
    nb, mb, m2b = b
    if not na:
        return b
    if not nb:
        return a
    delta = mb-ma
    return na+nb, ma+delta*nb/(na+nb), m2a+m2b+delta*delta*na*nb/(na+nb)


def exact_percentile(sorted_values, fraction):
    rank = fraction*(len(sorted_values)-1)
    low, high = math.floor(rank), math.ceil(rank)
    a, b = float(sorted_values[low]), float(sorted_values[high])
    return a+(b-a)*(rank-low)


def prevalence(out):
    eligible, _, day_hash = population()
    _, cfg = load_contract()
    mapping = load_sp04()
    yunnan = read_frozen_yunnan_mask(MASK, mapping)
    grouped = defaultdict(list)
    for row in eligible[2023]:
        grouped[row["imerg_day_path"]].append(row)
    manifest_path = RAW/"manifests/imerg_manifest.jsonl"
    completions = {r["path"].casefold(): r for r in (json.loads(line) for line in manifest_path.read_text(encoding="utf-8").splitlines())
                   if r.get("status") == "complete" and r.get("granules") == 48}
    stage = BoundedEnglishStaging(STAGING/f"prefreeze_{out.name}"/"prevalence", cfg["staging"]["max_temporary_bytes"], True, True)
    monthly = defaultdict(Counter)
    rainy_chunks, day_rows, scene_rows = [], [], []
    moments = (0, 0., 0.)
    thresholds = Counter()
    sums, squares = [], []
    equality = 0
    start = time.perf_counter()
    for number, (name, rows) in enumerate(sorted(grouped.items()), 1):
        source = Path(name)
        with stage.local(source) as english:
            with netCDF4.Dataset(str(english), "r") as ds:
                ds.set_auto_maskandscale(False)
                validate_final_provenance({k: str(ds.getncattr(k)) for k in ds.ncattrs()}, completions[str(source).casefold()], source.stat().st_size)
                var = ds["precipitation"]
                if var.dimensions != ("time", "lat", "lon") or var.shape != (48, 130, 140) or var.units != "mm hr-1":
                    raise ValueError("IMERG shape/units mismatch")
                mapping.assert_axes(mapping.axes["native_lat"], mapping.axes["native_lon"], ds["lat"][10:110], ds["lon"][20:120])
                indices = [int(r["imerg_index"]) for r in rows]
                if len(indices) != len(set(indices)):
                    raise ValueError("Duplicate day indices")
                t = ds["time"]
                times = netCDF4.num2date(t[indices], t.units, calendar=getattr(t, "calendar", "standard"), only_use_cftime_datetimes=False)
                for row, converted in zip(rows, times):
                    if utc(converted.isoformat()+"Z") != utc(row["window_start"]):
                        raise ValueError("IMERG selected CF coordinate changed")
                y, valid = decode_imerg(np.asarray(var[indices, 10:110, 20:120]), {k: var.getncattr(k) for k in var.ncattrs()})
                for row, target, validity in zip(rows, y, valid):
                    values, positive = classify(target, validity & yunnan)
                    count, pos = len(values), int(positive.sum())
                    if count != int(row["imerg_valid_yunnan_count"]) or pos != int(row["imerg_rain_yunnan_count"]):
                        raise ValueError("Target count differs from pinned eligibility evidence")
                    month = row["month"]
                    monthly[month].update(scenes=1, valid_pixels=count, positive_pixels=pos, negative_pixels=count-pos)
                    equality += int((values == np.float32(.1)).sum())
                    rain = values[positive].copy()
                    rainy_chunks.append(rain)
                    r64 = rain.astype(np.float64)
                    if len(r64):
                        local_mean = float(r64.mean())
                        moments = merge_moments(moments, (len(r64), local_mean, float(np.square(r64-local_mean).sum())))
                        sums.append(float(r64.sum()))
                        squares.append(float(np.square(r64).sum()))
                    for threshold in (1, 5, 10, 20, 30, 50):
                        thresholds[threshold] += int((rain > threshold).sum())
                    scene_rows.append({"sample_id": row["window_start"], "month": month, "valid_pixels": count,
                                       "positive_pixels": pos, "negative_pixels": count-pos})
        rec = stage.records[-1]
        if rec.source_sha256 != day_hash[name] or not rec.sha256_match or not rec.cleanup_success or stage._owned:
            raise ValueError("Pinned raw hash/staging cleanup failed")
        day_rows.append({"path": name, "eligible_scenes": len(rows), **asdict(rec)})
        if number % 25 == 0:
            print(json.dumps({"days_read": number, "days_total": len(grouped), "scenes_counted": len(scene_rows), "elapsed_seconds": round(time.perf_counter()-start, 2)}), flush=True)
    monthly_rows = [{"month": month, **dict(monthly[month]),
                     "rain_fraction": monthly[month]["positive_pixels"]/monthly[month]["valid_pixels"],
                     "dry_fraction": monthly[month]["negative_pixels"]/monthly[month]["valid_pixels"]}
                    for month in sorted(monthly)]
    nvalid = sum(r["valid_pixels"] for r in monthly_rows)
    npos = sum(r["positive_pixels"] for r in monthly_rows)
    nneg = nvalid-npos
    if len(scene_rows) != 11720 or nvalid != 40199600 or moments[0] != npos:
        raise ValueError("Full-population accounting incomplete")
    result = {"scenes": len(scene_rows), "N_valid": nvalid, "N_positive": npos, "N_negative": nneg,
              "positive_fraction": npos/nvalid, "negative_fraction": nneg/nvalid,
              "negative_to_positive_ratio": nneg/npos, "occurrence": "R > 0.1 mm/h, production float32 comparison",
              "count_at_float32_0_1_negative": equality, "years": [2023], "months": list(range(3, 11)),
              "full_population": True, "yunnan_cells": 3430, "IMERG": "V07 Final", "2025_pixels_read": False,
              "train_manifest_sha256": sha256(PRIOR/"normalization_phaseA_sample_manifest.csv"),
              "eligible_source_sha256": sha256(PRIOR/"formal_sample_eligibility_2023_2024.csv"),
              "completion_manifest_sha256": sha256(manifest_path),
              "elapsed_seconds": time.perf_counter()-start, "staging_operations": len(stage.records),
              "all_source_hashes_match_pinned": True, "all_cleanup_success": True,
              "temporary_peak_file_bytes": max(r.temporary_bytes for r in stage.records)}
    save(out/"train_occurrence_prevalence.json", result)
    table(out/"train_occurrence_monthly.csv", monthly_rows)
    table(out/"train_occurrence_per_scene.csv", scene_rows)
    table(out/"train_imerg_read_evidence.csv", day_rows)
    rain = np.concatenate(rainy_chunks)
    del rainy_chunks
    rain.sort()
    direct_mean = math.fsum(sums)/npos
    direct_variance = math.fsum(squares)/npos-direct_mean**2
    std = math.sqrt(moments[2]/npos)
    if abs(direct_mean-moments[1]) > 1e-10 or abs(direct_variance-std**2) > 1e-9:
        raise ValueError("Independent rainy moments disagree")
    distribution = {"count": npos, "mean": moments[1], "std": std, "ddof": 0, "units": "mm/h",
                    **{name: exact_percentile(rain, p) for name, p in (("p1", .01), ("p5", .05), ("p10", .10), ("p25", .25),
                            ("median", .5), ("p75", .75), ("p90", .90), ("p95", .95), ("p99", .99))},
                    "strict_exceedance": {str(t): {"count": thresholds[t], "rainy_fraction": thresholds[t]/npos} for t in (1, 5, 10, 20, 30, 50)},
                    "percentile_method": "Exact linear rank interpolation, r=p*(N-1); decoded runtime float32 values sorted without rebinning, endpoints promoted to float64 for interpolation.",
                    "moments_method": "Merged float64 central moments, independently checked against float64 sums/squares.",
                    "in_memory_rain_array_bytes": rain.nbytes, "intermediate_disk_cache_created": False,
                    "threshold_scope": "DESCRIPTIVE_ONLY_NOT_EXTREME_THRESHOLD_FREEZE", "source_years": [2023]}
    save(out/"train_rainrate_distribution.json", distribution)
    print(json.dumps(result), flush=True)


def alpha_candidates(npos, nneg):
    p = npos/(npos+nneg)
    return {"semantics": "ALPHA_IS_POSITIVE_CLASS_WEIGHT", "N_positive": npos, "N_negative": nneg,
            "candidates": [{"name": "A", "alpha": .25, "negative_weight": .75, "status": "CANONICAL_REFERENCE_ONLY"},
                           {"name": "B", "alpha": .5, "negative_weight": .5, "status": "NO_CLASS_REWEIGHTING_REFERENCE"},
                           {"name": "C", "alpha": 1-p, "negative_weight": p, "status": "TRAIN_BALANCED_CANDIDATE_ONLY"}],
            "balanced_formula": "alpha_balanced=N_negative/(N_positive+N_negative); 1-alpha_balanced=N_positive/N_valid",
            "D_inverse_frequency": {"positive_weight_unit_expected_mean": 1/(2*p), "negative_weight_unit_expected_mean": 1/(2*(1-p)),
                 "positive_to_negative_ratio": (1-p)/p,
                 "weights_normalized_to_sum_one": [1-p, p],
                 "equivalence": "Sum-one inverse-frequency weights exactly equal candidate C. Unit-expected-mean weights have the same class ratio but multiply L_occ by 1/[2*p*(1-p)], changing scale relative to L_qr."},
            "gamma_zero_equal_difficulty_balance_check": {"positive_mass": (1-p)*p, "negative_mass": p*(1-p)},
            "recommended_alpha": None, "selection_status": "RESEARCHER_DECISION_REQUIRED"}


def global_core_metric(rows):
    denominator = sum(r["valid_Yunnan_denominator"] for r in rows)
    if denominator <= 0:
        return {"status": "UNDEFINED_NO_VALID_PIXELS", "valid_count": denominator}
    occ = math.fsum(r["occ_numerator"] for r in rows)/denominator
    qr = math.fsum(r["qr_numerator"] for r in rows)/denominator
    return {"status": "DEFINED", "valid_count": denominator,
            "val_occurrence_loss": occ, "val_quantile_loss": qr, "val_core_loss": occ+qr}


def math_tables(out):
    p = read_json(out/"train_occurrence_prevalence.json")
    alpha = alpha_candidates(p["N_positive"], p["N_negative"])
    save(out/"focal_alpha_candidates.json", alpha)
    table(out/"focal_gamma_weight_table.csv", [{"p_t": pt, "gamma": gamma, "weight": (1-pt)**gamma}
          for pt in (.01, .05, .1, .25, .5, .75, .9, .95, .99) for gamma in (0, 1, 2, 3)])
    logits = (-4., -2., -1., 0., 1., 2., 4.)
    shaping = []
    for candidate in alpha["candidates"]:
        a = candidate["alpha"]
        for gamma in (0, 1, 2, 3):
            for scenario in ("same_raw_logit_both_classes", "equal_true_class_confidence"):
                for z in logits:
                    zp, zn = z, (z if scenario == "same_raw_logit_both_classes" else -z)
                    zt = torch.tensor([zp, zn], dtype=torch.float64)
                    posloss = float(focal_bce_sum(zt, torch.tensor([True, False]), torch.tensor([True, False]), a, gamma))
                    negloss = float(focal_bce_sum(zt, torch.tensor([True, False]), torch.tensor([False, True]), a, gamma))
                    pos = p["positive_fraction"]*posloss
                    neg = p["negative_fraction"]*negloss
                    # Relative to alpha=.5,gamma=0 at the same logits, not an optimizer/performance proxy.
                    basepos = float(focal_bce_sum(zt, torch.tensor([True, False]), torch.tensor([True, False]), .5, 0))
                    baseneg = float(focal_bce_sum(zt, torch.tensor([True, False]), torch.tensor([False, True]), .5, 0))
                    reference = p["positive_fraction"]*basepos+p["negative_fraction"]*baseneg
                    shaping.append({"alpha_candidate": candidate["name"], "alpha": a, "gamma": gamma, "scenario": scenario,
                                    "positive_logit": zp, "negative_logit": zn, "positive_pixel_loss": posloss, "negative_pixel_loss": negloss,
                                    "positive_loss_contribution": pos, "negative_loss_contribution": neg, "total_loss": pos+neg,
                                    "positive_share": pos/(pos+neg), "total_relative_to_alpha05_gamma0": (pos+neg)/reference,
                                    "scope": "SYNTHETIC_MATH_DIAGNOSTIC_ONLY"})
    table(out/"focal_loss_shaping.csv", shaping)
    lr = []
    for base_lr in (5e-5, 1e-4, 2e-4, 3e-4):
        for accum in (1, 2, 4):
            effective = 2*accum
            lr.append({"physical_batch": 2, "accumulation_steps": accum, "effective_batch": effective,
                       "base_lr_at_effective2": base_lr, "linear_scaled_lr_reference": base_lr*effective/2,
                       "physical_steps_per_epoch": 5860, "optimizer_updates_per_epoch_if_flush_tail": math.ceil(5860/accum),
                       "status": "CANDIDATE_ONLY_NOT_SELECTED", "linear_scaling_adopted": False})
    table(out/"lr_effective_batch_candidates.csv", lr)
    print("FOCAL_ALPHA_GAMMA_AND_UPDATE_ARITHMETIC_PASS", flush=True)


def loss_scale(out):
    eligible, train, day_hash = population()
    train_sha = {r["b13_relative_path"]: r["source_sha256"] for r in train}
    manifest = read_json(DEVELOPMENT/"manifest.json")
    pinned = read_json(PRIOR/"manifest.json")
    if sha256(DEVELOPMENT/"manifest.json") != pinned["prior_development_manifest_sha256"]:
        raise ValueError("Prior frame evidence changed")
    frame_info = manifest["local_evidence"]["b13_per_frame.csv"]
    frame_path = Path(frame_info["local_path"])
    if sha256(frame_path) != frame_info["sha256"]:
        raise ValueError("Per-frame evidence changed")
    wanted = []
    for year in (2023, 2024):
        rows = sorted(eligible[year], key=lambda r: r["window_start"])
        wanted.extend(rows[int(i)] for i in np.linspace(0, len(rows)-1, 4, dtype=np.int64))
    selected_rel = {r["selected_b13_relative_path"] for r in wanted}
    frames = {r["relative_path"]: r for r in read_csv(frame_path) if r["relative_path"] in selected_rel}
    records, hashes = [], []
    for row in wanted:
        f = frames[row["selected_b13_relative_path"]]
        frame = HimawariFrame(HROOT/f["relative_path"], utc(f["nominal"]), utc(f["obs_start"]), utc(f["obs_end"]), utc(f["date_created"]))
        records.append(B0Record(row["window_start"], utc(row["window_start"]), (frame,), Path(row["imerg_day_path"]), int(row["imerg_index"]), "IMERG", "V07", "Final", True))
        # Historical frame metadata has no SHA column. Train hashes are pinned in
        # normalization manifest; new Validation frame SHA is recorded before read.
        b13_hash = train_sha.get(f["relative_path"])
        if b13_hash is None:
            b13_hash = sha256(frame.path)
        hashes.append({"b13": b13_hash, "imerg": day_hash[row["imerg_day_path"]]})
    # Declare fixed identities before reading/forward; no outcome-based sample selection.
    save(out/"loss_scale_selected_samples.json", [{"sample_id": r.sample_id, "year": r.imerg_window_start.year,
         "H_path": str(r.frames[0].path), "IMERG_path": str(r.imerg_path),
         "b13_hash_scope": "HISTORICALLY_PINNED_TRAIN" if r.imerg_window_start.year == 2023 else "PRE_READ_IDENTITY_RECORDED_THIS_RUN",
         **h} for r, h in zip(records, hashes)])
    dataset = dataset_new(records, hashes, out, "protocol_loss_scale")
    _, cfg = load_contract()
    repro_before = reproducibility_snapshot()
    old_threads = torch.get_num_threads()
    torch.set_num_threads(2)  # process-only audit CPU validation cost, restored below
    rows = []
    with torch.random.fork_rng(devices=[0]):
        torch.manual_seed(20261001)
        model = B0Model().cuda().eval()
        before = parameter_hash(model)
        with torch.no_grad():
            for i, record in enumerate(records):
                sample, read_evidence = dataset[i]
                batch = to_cuda(B0Batch.from_formal_samples([sample]))
                batch.validate_formal()
                with torch.autocast("cuda", dtype=torch.bfloat16):
                    output = model.forward_formal(batch)
                    loss = b0_core_loss(output, batch.y_imerg, batch.imerg_valid_mask, batch.yunnan_eval_mask,
                        focal_alpha=.25, focal_gamma=2., quantile_axis_reduction=cfg["loss"]["quantile_axis_reduction"])
                finite = all(bool(torch.isfinite(t).all()) for t in (output.rain_logit, output.rain_prob, output.conditional_quantiles_log,
                             output.conditional_quantiles_physical, loss.total, loss.occurrence, loss.conditional_quantile))
                strict = bool((output.conditional_quantiles_log[:, 1:] > output.conditional_quantiles_log[:, :-1]).all())
                rows.append({"sample_id": record.sample_id, "year": record.imerg_window_start.year,
                     "L_occ": float(loss.occurrence), "L_qr": float(loss.conditional_quantile), "L_total": float(loss.total),
                     "occ_numerator": float(loss.occurrence)*loss.valid_supervised_count,
                     "qr_numerator": float(loss.conditional_quantile)*loss.valid_supervised_count,
                     "valid_Yunnan_denominator": loss.valid_supervised_count, "rainy_count": loss.rainy_valid_count,
                     "qr_to_occ_ratio": float(loss.conditional_quantile/loss.occurrence),
                     "qlog_dtype": str(output.conditional_quantiles_log.dtype), "pinball_dtype": str(loss.conditional_quantile.dtype),
                     "finite": finite, "qlog_strict": strict, "formal_QC_pass": sample.formal_supervised_qc_pass,
                     "read_evidence": read_evidence})
                if not finite or not strict or loss.valid_supervised_count != 3430:
                    raise RuntimeError("Loss-scale numerical/QC failure")
                del sample, batch, output, loss
        unchanged = before == parameter_hash(model)
        grads_absent = all(p.grad is None for p in model.parameters())
        del model
    torch.set_num_threads(old_threads)
    repro_after = reproducibility_snapshot()
    settings_unchanged = all(repro_before[k] == repro_after[k] for k in ("deterministic_algorithms", "cudnn_deterministic", "cudnn_benchmark",
         "cuda_matmul_allow_tf32", "cudnn_allow_tf32", "float32_matmul_precision", "torch_num_threads", "torch_CPU_rng_state_sha256"))
    save(out/"loss_scale_smoke.json", {"status": "PASS" if unchanged and grads_absent and settings_unchanged else "FAIL", "samples": rows,
         "initialization_seed": 20261001, "initialization_seed_scope": "ISOLATED_FIXED_AUDIT_SEED_NOT_PROTOCOL_SELECTION",
         "model": "Untrained baseline B0 exact architecture", "mode": "BF16", "focal_alpha": .25, "focal_gamma": 2.,
         "focal_parameter_scope": "PREVIOUS_ENGINEERING_REFERENCE_ONLY_NOT_CHOSEN", "parameters_unchanged": unchanged,
         "parameter_sha256": before, "no_backward": grads_absent, "optimizer_created": False, "checkpoint_created": False,
         "RNG_and_runtime_settings_restored": settings_unchanged,
         "global_metric_examples": {str(year): global_core_metric([r for r in rows if r["year"] == year]) for year in (2023, 2024)},
         "numerator_example_precision_note": "Smoke reconstructs numerator from existing per-sample loss times denominator; formal proposed accumulator should collect raw numerator directly in float64 to avoid per-batch division rounding.",
         "scale_conclusion": "Shared valid denominator does not make occurrence and log1p conditional pinball scales naturally equal. Rain prevalence, logits and quantile errors affect them; these 8 untrained forwards cannot select alpha/gamma or loss weights."})
    print("REAL_LOSS_SCALE_FORWARD_ONLY_PASS", flush=True)


def run_tests(out):
    suites = ("scientific_freeze", "b0_skeleton", "development_qc", "scientific_freeze_v1_1", "quantile_numerical_closure",
              "training_environment_audit", "gpu_training_feasibility", "phase_a_protocol_prefreeze")
    results = []
    with (out/"test_results.txt").open("x", encoding="utf-8", newline="\n") as stream:
        for directory in suites:
            stream.write("\nSUITE "+directory+"\n")
            suite = unittest.TestLoader().discover(str(ROOT/"tests"/directory))
            result = unittest.TextTestRunner(stream=stream, verbosity=2).run(suite)
            row = {"suite": directory, "tests": result.testsRun, "errors": len(result.errors), "failures": len(result.failures),
                   "skipped": len(result.skipped), "pass": result.wasSuccessful() and not result.skipped}
            results.append(row)
            stream.flush()
            print(json.dumps(row), flush=True)
            if not row["pass"]:
                break
    save(out/"test_summary.json", results)
    if len(results) != 8 or not all(r["pass"] for r in results) or sum(r["tests"] for r in results[:7]) != 126:
        raise RuntimeError("Required test gate failed")


def main():
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument("phase", choices=("lock", "prevalence", "math_tables", "loss_scale", "run_tests", "package"))
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    if Path(sys.executable).resolve() != Path(r"F:\pytorch\Research\.venv-cuda\Scripts\python.exe").resolve():
        raise RuntimeError("Verified CUDA interpreter required")
    args.out.mkdir(parents=True, exist_ok=True)
    save(args.out/(args.phase+"_invocation.json"), {"utc": datetime.now(timezone.utc).isoformat(),
         "python": sys.executable, "script_sha256": sha256(Path(__file__)), "argv": sys.argv})
    if args.phase == "package":
        from phase_a_prefreeze_candidates import package
        package(args.out)
    else:
        globals()[args.phase](args.out)


if __name__ == "__main__":
    main()
