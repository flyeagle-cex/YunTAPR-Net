"""Read published aggregate evidence only; append a separately named audit.

No torch, model, raw pixel loader, checkpoint deserializer or training import.
Run with --output a NEW directory. Failing checks are retained and exit nonzero.
"""
from __future__ import annotations
import argparse
import ast
import csv
import hashlib
import importlib.util
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable
import numpy as np

REPO = Path(__file__).resolve().parents[2]
RUN = REPO / "docs/v2_scientific_acceptance/runs/run_20261009T112710_013267Z"
DELIVERY = RUN / "delivery_v2"
MODELS = ("B0_MATCHED_V2", "B1_V2")
NAMES = ("Core_loss", "Brier", "AUROC", "AP", "conditional_pinball")


def read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def digest(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def rows(name: str) -> list[dict[str, str]]:
    with (DELIVERY / name).open(encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def close(a: object, b: object) -> None:
    np.testing.assert_allclose(a, b, rtol=1e-11, atol=1e-12, equal_nan=True)


def number(s: str) -> float:
    return float(s) if s else float("nan")


def load_stats_module():
    path = REPO / "docs/v2_scientific_acceptance/analysis_v1/sufficient_stats.py"
    spec = importlib.util.spec_from_file_location("published_sufficient_stats", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def run_audit(output: Path) -> dict:
    output.mkdir(parents=True, exist_ok=False)
    checks = []
    stats = load_stats_module()
    published = read(RUN / "paired_best_metrics.json")
    historical = read(REPO / "docs/v2_paired_phase_a_review/runs/run_20261009T072307_459014Z/paired_best_metrics.json")
    uncertainty = read(DELIVERY / "paired_uncertainty.json")
    data = {m: dict(np.load(RUN / m / "sufficient_statistics.npz", allow_pickle=False)) for m in MODELS}
    weights = np.load(RUN / "paired_bootstrap_block_multiplicities.npy", allow_pickle=False)
    stratified = rows("PAIRED_STRATIFIED_ANALYSIS.csv")
    comparisons = rows("PAIRED_STRATIFIED_COMPARISONS.csv")
    reliability = rows("reliability_fixed_bins.csv")
    coverage = rows("conditional_quantile_calibration.csv")
    rng = np.random.default_rng(2026)
    expected_weights = np.array([np.bincount(rng.integers(0, 35, 35), minlength=35) for _ in range(2000)])

    def check(name: str, callback: Callable[[], object]) -> None:
        try:
            detail = callback()
            checks.append({"name": name, "status": "PASS", "detail": detail})
        except Exception as exc:
            import traceback
            checks.append({"name": name, "status": "FAIL", "error": repr(exc), "traceback": traceback.format_exc()})

    def require(condition: bool, detail: str) -> str:
        if not condition:
            raise AssertionError(detail)
        return detail

    def manifest_identity():
        manifest = read(DELIVERY / "acceptance_manifest.json")
        for ref in manifest["artifacts"]:
            p = (REPO / ref["repository_path"]).resolve()
            if not p.is_relative_to(REPO) or p.stat().st_size != ref["bytes"] or digest(p) != ref["sha256"]:
                raise AssertionError(ref["repository_path"])
        return {"verified_files": len(manifest["artifacts"]), "manifest_sha256": digest(DELIVERY / "acceptance_manifest.json")}

    check("historical_acceptance_manifest_bytes", manifest_identity)
    check("published_global_json_exact", lambda: require(all(published["models"][m]["metrics"] == historical["models"][m]["metrics"] for m in MODELS), "Both models match published original metrics exactly"))
    ids = [published["models"][m]["supplemental_statistics"]["scene_ids"] for m in MODELS]
    check("paired_validation_identities", lambda: require(ids[0] == ids[1] and len(set(ids[0])) == len(ids[0]) == 10501 and all(s.startswith("2024-") and 3 <= int(s[5:7]) <= 10 for s in ids[0]), "10501 identical unique 2024 March-October scenes"))

    def frozen_identity():
        protocol = read(REPO / "config/science_v2/phase_a_protocol_frozen_v1.json")
        verified, deferred = [], []
        for name, ref in protocol["identity"].items():
            if name == "yunnan_mask":
                deferred.append({"name": name, "reason": "External static mask; published SHA only, not reopened"})
                continue
            p = REPO / ref["path"]
            require(digest(p) == ref["sha256"], name)
            verified.append(name)
        return {"verified": verified, "deferred": deferred}

    check("frozen_protocol_input_sha", frozen_identity)
    check("bootstrap_seed_exact_matrix", lambda: require(np.array_equal(weights, expected_weights) and weights.shape == (2000, 35) and (weights.sum(1) == 35).all(), "Entire stored matrix reproduced from seed=2026; 35 draws each"))
    check("bootstrap_declaration", lambda: require((uncertainty["seed"], uncertainty["replicates"], uncertainty["week_blocks"]) == (2026, 2000, 35) and not uncertainty["block_length_changed_from_results"] and uncertainty["BEST_selection_optimism_not_corrected"], "Pointwise exploratory intervals; no independent-pixel assumption"))

    aggregate = {}
    for model in MODELS:
        d = data[model]
        sums = d["daily"][:, 0].sum(0)
        blocks = d["daily"][:, 0].reshape(35, 7, -1).sum(1)
        pooled = weights @ blocks
        aggregate[model] = pooled
        old = published["models"][model]
        check(model + ":exposure_and_score_counts", lambda d=d, sums=sums: require(sums[0] == 36018430 and sums[1] == 4496600 and d["scores"][:, 0].sum() == sums[0] and d["scores"][:, 0, :, 1].sum() == sums[1], "Global denominators and exact-score class counts agree"))

        def point_metrics(d=d, sums=sums, old=old):
            computed = stats.metrics(sums, d["scores"][:, 0].sum(0))
            m = old["metrics"]
            close(computed, [m[k] for k in ("global_val_core_loss", "Brier_Score", "AUROC", "Average_Precision", "conditional_mean_pinball")])
            close(sums[2:4], [m["S_occ"], m["S_qr"]])
            close(sums[3] / sums[0], m["global_core_L_qr"])
            return {"metrics": dict(zip(NAMES, computed.tolist())), "S_qr_over_Nvalid": sums[3] / sums[0]}

        check(model + ":global_metric_reconstruction", point_metrics)

        def strata_check(model=model, d=d):
            selected = {r["group"]: r for r in stratified if r["model"] == model}
            require(len(selected) == len(stats.GROUPS), "22 unique groups")
            for i, group in enumerate(stats.GROUPS):
                s = d["daily"][:, i].sum(0)
                close([number(selected[group][n]) for n in NAMES], stats.metrics(s, d["scores"][:, i].sum(0)))
                require(int(selected[group]["N_valid"]) == s[0] and int(selected[group]["N_rain"]) == s[1], group)
            for groups in (stats.GROUPS[1:9], stats.GROUPS[9:12], stats.GROUPS[12:14], stats.GROUPS[14:]):
                require(sum(int(selected[g]["N_valid"]) for g in groups) == 36018430, "Partition valid counts")
                require(sum(int(selected[g]["N_rain"]) for g in groups) == 4496600, "Partition rain counts")
            return "All 22 strata recomputed; all four partitions conserve counts"

        check(model + ":stratified_points_and_partitions", strata_check)

        def reliability_check(model=model, sums=sums, pooled=pooled):
            out = []
            rr = [r for r in reliability if r["model"] == model]
            require(len(rr) == 10 and [int(r["bin_index"]) for r in rr] == list(range(10)), "Fixed bins")
            for i, r in enumerate(rr):
                n = sums[73+i]
                require(int(r["count"]) == n, "Bin count")
                if n == 0:
                    require(all(r[f] == "" for f in ("mean_probability", "observed_frequency", "observed_ci_lower", "observed_ci_upper")), "Empty bin remains missing")
                    out.append({"bin": i, "count": 0, "status": "EMPTY"})
                    continue
                close([number(r["mean_probability"]), number(r["observed_frequency"])], [sums[83+i]/n, sums[93+i]/n])
                good = pooled[:, 73+i] > 0
                require(int(r["bootstrap_valid_replicates"]) == int(good.sum()), "Effective replicate count")
                for numerator, low, high in ((83+i, "predicted_ci_lower", "predicted_ci_upper"), (93+i, "observed_ci_lower", "observed_ci_upper")):
                    close(np.quantile(pooled[good, numerator] / pooled[good, 73+i], [.025, .975]), [number(r[low]), number(r[high])])
                out.append({"bin": i, "count": int(n), "predicted_minus_observed": (sums[83+i]-sums[93+i])/n, "effective_replicates": int(good.sum())})
            close(sum(sums[93:103]), 4496600)
            return out

        check(model + ":all_probability_bins_and_intervals", reliability_check)

        def coverage_check(model=model, sums=sums, pooled=pooled, old=old):
            cc = [r for r in coverage if r["model"] == model]
            require(len(cc) == 32, "All 32 quantiles")
            close([number(r["tau"]) for r in cc], stats.TAU)
            close([number(r["coverage"]) for r in cc], sums[9:41] / sums[1])
            close([number(r["coverage_error"]) for r in cc], sums[9:41] / sums[1] - stats.TAU)
            close([number(r["conditional_pinball"]) for r in cc], sums[41:73] / sums[1])
            close(sums[41:73] / sums[1], old["metrics"]["per_tau_pinball"])
            close(np.quantile(pooled[:, 9:41] / pooled[:, 1:2], [.025, .975], axis=0), [[number(r[k]) for r in cc] for k in ("coverage_ci_lower", "coverage_ci_upper")])
            require(np.all(np.diff(sums[9:41]) >= 0), "Coverage monotonicity")
            return {"q32": sums[40]/sums[1], "target": float(stats.TAU[-1]), "mean_absolute_coverage_error": float(np.abs(sums[9:41]/sums[1]-stats.TAU).mean())}

        check(model + ":32_quantile_points_and_intervals", coverage_check)
        check(model + ":checkpoint_and_unchanged_state_metadata", lambda old=old: require(old["BEST"]["epoch"] == 9 and old["BEST"]["global_update"] == 47052 and old["model_state_sha256_before"] == old["model_state_sha256_after"] and all(old[k] == 0 for k in ("BACKWARD_CALLS", "OPTIMIZER_STEPS", "2025_RAW_ACCESS", "2025_PIXELS_READ")), "Published checkpoint receipt and read-only counters; private bytes not reopened"))

    def paired_tables():
        require(len(comparisons) == 22 * 5, "110 rows")
        for r in comparisons:
            v = uncertainty["comparisons"][r["group"]][r["metric"]]
            for key in ("B0", "B1", "B1_minus_B0", "relative_percent_of_B0"):
                close(number(r[key]), np.nan if v[key] is None else v[key])
            for prefix, key in (("delta", "paired_difference_95_percentile_interval"), ("relative", "paired_relative_difference_95_percentile_interval")):
                q = v[key]
                close([number(r[prefix+"_lower"]), number(r[prefix+"_upper"])], [np.nan if q[x] is None else q[x] for x in ("lower", "upper")])
                require(int(r[prefix+"_valid_replicates"]) == q["valid_replicates"], "CI effective counts")
            if v["B0"] is not None and v["B1"] is not None:
                close(v["B1_minus_B0"], v["B1"] - v["B0"])
        return "CSV/JSON point and interval fields agree for all 110 comparisons"

    check("all_comparison_csv_json_fields", paired_tables)

    def loss_bootstrap():
        # Independently reconstruct pooled denominator ratios, not average daily losses.
        for group in range(22):
            boot = {}
            for model in MODELS:
                b = data[model]["daily"][:, group].reshape(35, 7, -1).sum(1)
                s = weights @ b
                with np.errstate(divide="ignore", invalid="ignore"):
                    boot[model] = np.c_[(s[:, 2] + s[:, 3])/s[:, 0], s[:, 4]/s[:, 0], s[:, 3]/s[:, 1]]
            for j, name in enumerate(("Core_loss", "Brier", "conditional_pinball")):
                delta = boot[MODELS[1]][:, j] - boot[MODELS[0]][:, j]
                good = np.isfinite(delta)
                ci = uncertainty["comparisons"][stats.GROUPS[group]][name]["paired_difference_95_percentile_interval"]
                require(int(good.sum()) == ci["valid_replicates"], name)
                if good.any():
                    close(np.quantile(delta[good], [.025, .975]), [ci["lower"], ci["upper"]])
        return "66 paired pooled-loss difference intervals independently reconstructed"

    check("all_strata_loss_bootstrap_intervals", loss_bootstrap)

    def ranking_replicates():
        # Five fixed replicate indices selected by engineering design, not outcomes.
        for model in MODELS:
            scores = data[model]["scores"][:, 0]
            for i in (0, 1, 499, 999, 1999):
                computed = stats.ranking(np.tensordot(weights[i], scores, axes=(0, 0)))
                require(np.isfinite(computed).all(), "Both classes present")
            require((scores[:, :, 0].sum(1) > 0).all() and (scores[:, :, 1].sum(1) > 0).all(), "Every week has both classes")
        return "Exact-score pooled ranking executable on 5 preselected paired draws; full historical ranking CI not rerun"

    check("pooled_ranking_replicate_smoke", ranking_replicates)

    def tail_exposures():
        rr = rows("upper_tail_exposure_units.csv")
        require(len(rr) == 20, "All model/region/threshold combinations")
        for r in rr:
            v = published["models"][r["model"]]["upper_tail_diagnostics"][r["region"]]["threshold_exceedances"][r["threshold_mm_h"]]
            for key in ("scene_pixel_tau_exposure", "scene_pixel_any_tau_exposure"):
                require(int(r[key]) == v[key], key)
        with (DELIVERY / "figures/inside_q32_gt50_observations.csv").open(encoding="utf-8", newline="") as stream:
            all_rows = list(csv.DictReader(stream))
        selected = [r for r in all_rows if r["model"] == "B1_V2" and float(r["q32_log"]) > np.log1p(100)]
        require((len(selected), len({(r["row"], r["column"]) for r in selected}), len({r["sample_id"] for r in selected})) == (58, 44, 28), "Exposures / unique cells / scenes")
        rainy = [r for r in selected if np.float32(float(r["truth_mm_h"])) > np.float32(.1)]
        require(len(rainy) == 30, "30 rainy exposures")
        # Report text rounds the frozen float32 reference to 20.24. Compare in
        # its source representation, without weakening aggregate tolerances.
        require(max(float(r["truth_mm_h"]) for r in selected) == float(np.float32(20.24)), "Frozen float32 maximum equals displayed 20.24")
        return {"exposures": 58, "unique_cells": 44, "scenes": 28, "rainy_exposures": 30, "p_range": [min(float(r["p_rain"]) for r in selected), max(float(r["p_rain"]) for r in selected)], "independent_events": None}

    check("tail_units_and_joint_probability_reference", tail_exposures)

    def governance():
        audit = read(DELIVERY / "recovery_governance_source_audit.json")
        for ref in audit["sources"]:
            p = REPO / ref["path"]
            require(digest(p) == ref["sha256"] and p.stat().st_size == ref["bytes"], ref["path"])
        chronology = read(DELIVERY / "recovery_best_chronology_note.json")
        require(chronology["BEST_epoch"] < chronology["resume_LAST_epoch"] < chronology["interrupted_epoch"], "Logical chronology")
        require(audit["independent_human_LAST_bound_resume_approval"] == "NOT_EVIDENCED_IN_REGISTERED_RESUME_RECORDS", "No inferred human approval")
        return "9 governance source identities preserved; approval still not evidenced"

    check("historical_recovery_governance_sources", governance)
    check("scientific_limits_still_in_force", lambda: require(read(DELIVERY/"final_status.json")["V2_PHASE_B_AUTHORIZED"] is False and read(DELIVERY/"final_status.json")["RESEARCHER_SCIENTIFIC_APPROVAL_REQUIRED"] is True, "No new stage authority"))

    def source_paths():
        paths = ["src/yuntapr/losses/total_loss.py", "src/yuntapr/losses/pinball.py", "src/yuntapr/training/checkpoint_v2.py", "src/yuntapr/training/formal_phase_a_v2.py", "src/yuntapr/models/quantile_v2/parameterization.py", "src/yuntapr/models/quantile_v2/outputs.py"]
        for p in paths:
            ast.parse((REPO / p).read_text(encoding="utf-8"))
        t = (REPO / paths[0]).read_text(encoding="utf-8")
        require(" / nvalid" in t and "pinball_sum(" in t, "Training denominator source")
        return {p: digest(REPO / p) for p in paths}

    check("actual_source_static_identity_and_syntax", source_paths)
    source_refs = [RUN / "paired_best_metrics.json", DELIVERY / "acceptance_manifest.json", RUN / "paired_bootstrap_block_multiplicities.npy", DELIVERY / "paired_uncertainty.json", *[RUN/m/"sufficient_statistics.npz" for m in MODELS]]
    result = {"status": "PASS" if all(c["status"] == "PASS" for c in checks) else "FAIL",
              "created_utc": datetime.now(timezone.utc).isoformat(), "baseline_HEAD": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=REPO, text=True).strip(),
              "checks_passed": sum(c["status"] == "PASS" for c in checks), "checks_failed": sum(c["status"] == "FAIL" for c in checks), "checks": checks,
              "source_sha256": {str(p.relative_to(REPO)).replace("\\", "/"): digest(p) for p in source_refs},
              "MODEL_FORWARDS_ADDED": 0, "BACKWARD_CALLS": 0, "FORMAL_OPTIMIZER_STEPS_ADDED": 0,
              "2025_RAW_ACCESS": 0, "2025_PIXELS_READ": 0, "V2_PHASE_B_AUTHORIZED": False,
              "not_executed": ["Raw satellite/IMERG reads", "Private checkpoint reopen/deserialization", "New model inference", "Full 2000-draw ranking CI reanalysis", "Independent gauge/radar validation", "Formal event/terrain evaluation"]}
    with (output / "audit_results.json").open("x", encoding="utf-8") as stream:
        json.dump(result, stream, ensure_ascii=False, indent=2, allow_nan=False)
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = run_audit(args.output)
    print(json.dumps({k: result[k] for k in ("status", "checks_passed", "checks_failed")}, ensure_ascii=False))
    raise SystemExit(0 if result["status"] == "PASS" else 1)
