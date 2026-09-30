"""Measure v4 float64 monotonicity, separate physical overflow, and real gradients."""
import argparse
import csv
from datetime import datetime
import json
from pathlib import Path
import sys

import numpy as np
import torch

from yuntapr.contracts.loader import REPO_ROOT, load_contract, sha256
from yuntapr.data.dataset_b0 import B0Dataset, B0Record
from yuntapr.data.masks import read_frozen_yunnan_mask
from yuntapr.data.normalization import PhaseANormalizer
from yuntapr.data.sample_schema import HimawariFrame, utc
from yuntapr.data.staging import BoundedEnglishStaging, StagedB13Reader, StagedIMERGReader
from yuntapr.models.b0 import B0Model
from yuntapr.models.monotonic_quantiles import monotonic_quantiles
from yuntapr.models.probability_heads import ProbabilityHeads
from yuntapr.spatial.sp04_mapping import load_sp04
from yuntapr.training.batch_contract import B0Batch
from yuntapr.training.forward_step import formal_rules_engineering_forward_step
from fit_phase_a_v1_1 import HROOT, MASK


PRIOR = REPO_ROOT / "docs/b0_pretraining_closure/runs/run_20260930T095416Z"


def save(path, value):
    if path.exists():
        raise FileExistsError(f"Versioned evidence must not be overwritten: {path}")
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8", newline="\n")


def monotonic_stress(out, epsilon):
    gen = torch.Generator().manual_seed(20260930)
    cases = [(f"constant_{value}", torch.full((1, 32, 4, 4), float(value)))
             for value in (-100, -80, -40, -20, -10, 0, 10, 40, 80, 100)]
    cases += [
        ("random_uniform_minus100_plus100", torch.rand((8, 32, 32, 32), generator=gen) * 200 - 100),
        ("random_normal_sigma100", torch.randn((8, 32, 32, 32), generator=gen) * 100),
        ("random_signed_100", torch.randint(0, 2, (8, 32, 32, 32), generator=gen).float() * 200 - 100),
    ]
    mixed = torch.full((1, 32, 1, 1), -100.)
    mixed[:, :22] = 100.
    cases.append(("mixed_22_positive100_then_10_negative100", mixed))
    rows = []
    for name, value in cases:
        raw = value.requires_grad_(True)
        qlog = monotonic_quantiles(raw, .1, epsilon_mono=epsilon, accumulation_dtype=torch.float64)
        qlog.mean().backward()
        adjacent = qlog[:, 1:] - qlog[:, :-1]
        row = {"case": name, "shape": list(raw.shape), "raw_dtype": str(raw.dtype),
               "qlog_dtype": str(qlog.dtype), "qlog_finite": bool(torch.isfinite(qlog).all()),
               "strictly_increasing": bool((adjacent > 0).all()),
               "adjacent_equal_count": int((adjacent == 0).sum()),
               "above_threshold": bool((qlog[:, :1] > np.log1p(.1)).all()),
               "minimum_log_increment": float(adjacent.min()), "maximum_qlog": float(qlog.max()),
               "raw_gradient_dtype": str(raw.grad.dtype), "gradient_finite": bool(torch.isfinite(raw.grad).all())}
        rows.append(row)
        print(json.dumps({"monotonic_case": name, "pass": row["strictly_increasing"] and row["gradient_finite"]}), flush=True)
    passed = all(r["qlog_finite"] and r["qlog_dtype"] == "torch.float64"
                 and r["strictly_increasing"] and r["adjacent_equal_count"] == 0
                 and r["above_threshold"] and r["gradient_finite"] for r in rows)
    result = {"test_family": "MONOTONIC_TRANSFORM_STRESS", "epsilon_mono": epsilon,
              "domain": "log1p(mm h^-1)", "random_seed": 20260930,
              "physical_expm1_invoked": False, "all_required_cases_pass": passed, "cases": rows}
    save(out / "quantile_stress_float64.json", result)
    return result


def physical_stress(out, epsilon):
    head = ProbabilityHeads(48, .1, epsilon_mono=epsilon, accumulation_dtype=torch.float64)
    features = torch.zeros((1, 48, 100, 100), dtype=torch.float32)
    with torch.no_grad():
        head.quantile.weight.zero_()
        head.quantile.bias.fill_(20.)
    moderate = head(features)
    moderate_ok = moderate[2].dtype == torch.float64 and moderate[3].dtype == torch.float64 and bool(torch.isfinite(moderate[3]).all())
    with torch.no_grad():
        head.quantile.bias.fill_(100.)
    raw = head.quantile(features)
    qlog = monotonic_quantiles(raw, .1, epsilon_mono=epsilon, accumulation_dtype=torch.float64)
    log_ok = bool(torch.isfinite(qlog).all() and (qlog[:, 1:] > qlog[:, :-1]).all())
    error = None
    try:
        head(features)
    except FloatingPointError as exc:
        error = str(exc)
    overflow_caught = bool(error and error.startswith("QUANTILE_PHYSICAL_OVERFLOW") and log_ok)
    result = {"test_family": "FULL_PHYSICAL_HEAD_STRESS", "moderate_float64_physical_finite": moderate_ok,
              "synthetic_positive_raw": 100., "large_qlog_finite_and_strict": log_ok,
              "large_qlog_max": float(qlog.max()), "expected_runtime_outcome": "FAIL_LOUDLY_QUANTILE_PHYSICAL_OVERFLOW",
              "observed_error": error, "physical_overflow_caught_separately": overflow_caught,
              "monotonicity_error_raised_for_physical_overflow": bool(error and "QUANTILE_MONOTONICITY_LOST" in error),
              "clamp_or_sort_applied": False}
    save(out / "physical_overflow_stress.json", result)
    return result


def real_regression(out, config):
    old = json.loads((PRIOR / "real_normalized_forward_smoke.json").read_text(encoding="utf-8"))
    chosen = [r for r in old["samples"] if r["category"] in ("FULL_VALID_2023", "FULL_VALID_2024")]
    if len(chosen) != 2:
        raise ValueError("Prior real sample identities incomplete")
    with (PRIOR / "formal_sample_eligibility_2023_2024.csv").open(encoding="utf-8", newline="") as stream:
        index = {r["window_start"]: r for r in csv.DictReader(stream)
                 if r["window_start"] in {s["window_start"] for s in chosen}}
    mapping = load_sp04()
    yunnan = read_frozen_yunnan_mask(MASK, mapping)
    normalizer = PhaseANormalizer.from_pinned()
    stage = BoundedEnglishStaging(Path(r"F:\pytorch\Research\stage0_himawari\cache\staging"),
                                  config["staging"]["max_temporary_bytes"], True, True)
    b13, imerg = StagedB13Reader(stage, mapping), StagedIMERGReader(stage, mapping)
    torch.manual_seed(20260930)
    model = B0Model().eval()
    raw_outputs = []
    def capture_raw(_module, _inputs, output):
        output.retain_grad()
        raw_outputs.append(output)
    hook = model.heads.quantile.register_forward_hook(capture_raw)
    samples, traces = [], []
    try:
        for prior in chosen:
            row = index[prior["window_start"]]
            source, target = HROOT / row["selected_b13_relative_path"], Path(row["imerg_day_path"])
            if sha256(source) != prior["source_sha256"] or sha256(target) != prior["target_sha256"]:
                raise ValueError("Real source hash changed since frozen v1.1 smoke")
            frame = HimawariFrame(source, utc(prior["selected_nominal"]), utc(prior["obs_start"]),
                                  utc(prior["obs_end"]), utc(prior["date_created"]))
            record = B0Record(prior["category"], utc(prior["window_start"]), (frame,), target,
                              int(row["imerg_index"]), "IMERG", "V07", "Final", True)
            sample = B0Dataset([record], mapping, yunnan, b13, imerg, frozen_mask_path=MASK,
                               formal_supervised=True, normalizer=normalizer)[0]
            batch = B0Batch.from_formal_samples([sample])
            model.zero_grad(set_to_none=True)
            output, loss = formal_rules_engineering_forward_step(model, batch, focal_alpha=.25, focal_gamma=2.,
                quantile_axis_reduction=config["loss"]["quantile_axis_reduction"])
            loss.total.backward()
            quantile_grad = model.heads.quantile.weight.grad
            backbone_grad = model.backbone.enc0.skip.weight.grad
            raw_grad = raw_outputs[-1].grad
            valid = (torch.isfinite(output.rain_logit).all() and torch.isfinite(output.conditional_quantiles_log).all()
                     and torch.isfinite(output.conditional_quantiles_physical).all() and torch.isfinite(loss.total)
                     and quantile_grad is not None and torch.isfinite(quantile_grad).all()
                     and backbone_grad is not None and torch.isfinite(backbone_grad).all()
                     and raw_grad is not None and torch.isfinite(raw_grad).all())
            trace = {"year": sample.imerg_window_start.year, "backbone_parameter_dtype": str(model.backbone.enc0.skip.weight.dtype),
                     "backbone_gradient_dtype": str(backbone_grad.dtype), "quantile_head_parameter_dtype": str(model.heads.quantile.weight.dtype),
                     "quantile_head_gradient_dtype": str(quantile_grad.dtype), "quantile_raw_dtype": str(raw_outputs[-1].dtype),
                     "quantile_raw_gradient_dtype": str(raw_grad.dtype), "qlog_dtype": str(output.conditional_quantiles_log.dtype),
                     "qphysical_dtype": str(output.conditional_quantiles_physical.dtype),
                     "conditional_pinball_dtype": str(loss.conditional_quantile.dtype), "total_loss_dtype": str(loss.total.dtype),
                     "all_parameter_gradients_finite": all(p.grad is not None and bool(torch.isfinite(p.grad).all()) for p in model.parameters()),
                     "nonzero_quantile_gradient": bool((quantile_grad != 0).any()),
                     "nonzero_backbone_gradient": bool((backbone_grad != 0).any())}
            traces.append(trace)
            item = {"year": sample.imerg_window_start.year, "window_start": prior["window_start"],
                    "b13_relative_path": row["selected_b13_relative_path"], "source_sha256": prior["source_sha256"],
                    "imerg_sha256": prior["target_sha256"], "normalization_version": sample.normalization_version,
                    "normalization_sha256": sample.normalization_artifact_sha256, "formal_supervised_qc_pass": sample.formal_supervised_qc_pass,
                    "expected_latest_available": sample.expected_latest_available, "used_older_causal_frame": sample.used_older_causal_frame,
                    "native_shape": output.native_feature_shape, "target_shape": output.target_feature_shape,
                    "yunnan_loss_pixels": loss.valid_supervised_count, "finite_forward_physical_loss_and_backward": bool(valid),
                    "qlog_strict": bool((output.conditional_quantiles_log[:, 1:] > output.conditional_quantiles_log[:, :-1]).all()),
                    "qlog_finite": bool(torch.isfinite(output.conditional_quantiles_log).all()),
                    "qphysical_finite": bool(torch.isfinite(output.conditional_quantiles_physical).all()),
                    "loss": float(loss.total), "focal_alpha_gamma_scope": "ENGINEERING_TEST_ONLY"}
            samples.append(item)
            print(json.dumps({"real_sample_year": item["year"], "pass": bool(valid)}), flush=True)
    finally:
        hook.remove()
    if stage._owned or not all(r.cleanup_success and r.sha256_match for r in stage.records):
        raise ValueError("Bounded staging integrity failure")
    trace_ok = all(t["backbone_parameter_dtype"] == t["quantile_head_parameter_dtype"] == "torch.float32"
                   and t["backbone_gradient_dtype"] == t["quantile_head_gradient_dtype"] == t["quantile_raw_gradient_dtype"] == "torch.float32"
                   and t["qlog_dtype"] == t["qphysical_dtype"] == t["conditional_pinball_dtype"] == t["total_loss_dtype"] == "torch.float64"
                   and t["all_parameter_gradients_finite"] and t["nonzero_quantile_gradient"] and t["nonzero_backbone_gradient"]
                   for t in traces)
    regression_ok = all(s["finite_forward_physical_loss_and_backward"] and s["qlog_strict"] and s["yunnan_loss_pixels"] == 3430 for s in samples)
    save(out / "real_regression_smoke.json", {"execution_scope": "ENGINEERING_ONLY", "python": sys.executable,
        "prior_v1_1_smoke_sha256": sha256(PRIOR / "real_normalized_forward_smoke.json"), "samples": samples,
        "all_passed": regression_ok, "staging_copy_count": len(stage.records), "all_staging_cleanup_success": True,
        "formal_training_started": False, "optimizer_step_performed": False, "checkpoint_generated": False})
    save(out / "gradient_dtype_trace.json", {"samples": traces, "all_dtype_and_gradient_contracts_pass": trace_ok,
        "gradient_crosses_float64_quantile_to_float32_parameters": trace_ok, "quantile_target_and_tau_dtype": "torch.float64",
        "detach_in_loss_path": False})
    return regression_ok, trace_ok


def main(out):
    science, config = load_contract()
    if config["schema_version"] != 4 or science["execution_status"]["B0_FORMAL_TRAINING_STARTED"] is not False:
        raise ValueError("Wrong active numerical contract or training state")
    epsilon = config["quantile_numerics"]["epsilon_mono"]
    torch.set_num_threads(2)
    a = monotonic_stress(out, epsilon)
    b = physical_stress(out, epsilon)
    real_ok, dtype_ok = real_regression(out, config)
    result = {"monotonic_stress": a["all_required_cases_pass"], "physical_overflow_caught": b["physical_overflow_caught_separately"],
              "real_regression": real_ok, "gradient_dtypes": dtype_ok}
    save(out / "execution_status.json", result)
    if not all(result.values()):
        raise RuntimeError("Quantile numerical closure checks incomplete")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-dir", type=Path, required=True)
    main(parser.parse_args().run_dir)
