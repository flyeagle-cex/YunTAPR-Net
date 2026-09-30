"""Validate and document completed Development QC run without scientific freeze."""
from __future__ import annotations

import argparse
from collections import Counter
import csv
import json
from pathlib import Path
import sys

from yuntapr.contracts.loader import REPO_ROOT, load_contract, sha256


def rows(path):
    with path.open(newline="", encoding="utf-8-sig") as stream:
        return list(csv.DictReader(stream))


def number(row, name):
    return int(row[name] or 0)


def summary(run, local):
    required = ("himawari_b13_monthly_coverage.csv", "b13_valid_fraction_summary.json",
                "b13_partial_spatial_summary.json", "sp04_support_distribution.csv",
                "qc_candidate_impact.csv", "imerg_v07_coverage.csv",
                "causal_pairing_summary.csv", "normalization_2023_train_only.json",
                "DECISION_8_NORMALIZATION_EVIDENCE.md", "quantile_numerical_stress.json",
                "real_multisample_smoke.json", "test_results.txt")
    missing_outputs = [name for name in required if not (run / name).is_file()]
    if missing_outputs:
        raise FileNotFoundError(f"Required audit outputs absent: {missing_outputs}")
    tests = (run / "test_results.txt").read_text(encoding="utf-8")
    if not all(marker in tests for marker in ("SCIENTIFIC_FREEZE PASS", "B0_SKELETON PASS",
                                              "DEVELOPMENT_QC PASS")):
        raise ValueError("Required test suites did not all pass")
    science, engineering = load_contract()
    if science["execution_status"]["B0_FORMAL_SCIENTIFIC_CONTRACT"] != "FROZEN" or science[
            "execution_status"]["B0_FORMAL_TRAINING_STARTED"] or engineering["formal_training_started"]:
        raise ValueError("Frozen contract/formal training status mismatch")
    h = rows(run / "himawari_b13_monthly_coverage.csv")
    i = rows(run / "imerg_v07_coverage.csv")
    p = rows(run / "causal_pairing_summary.csv")
    pair_rows = rows(local / "causal_pairing_per_slot.csv")
    fallback_reasons = Counter(r["expected_status"] for r in pair_rows if r[
        "pair_status"] == "EXPECTED_LATEST_SLOT_MISSING_BUT_OLDER_CAUSAL_EXISTS")
    q = rows(run / "qc_candidate_impact.csv")
    s = json.loads((run / "b13_partial_spatial_summary.json").read_text(encoding="utf-8"))
    n = json.loads((run / "normalization_2023_train_only.json").read_text(encoding="utf-8"))
    stress = json.loads((run / "quantile_numerical_stress.json").read_text(encoding="utf-8"))
    smoke = json.loads((run / "real_multisample_smoke.json").read_text(encoding="utf-8"))
    h_internal = json.loads((local / "h_scan_internal.json").read_text(encoding="utf-8"))
    i_internal = json.loads((local / "imerg_scan_internal.json").read_text(encoding="utf-8"))
    if len(h) != 16 or len(i) != 23 or len([r for r in p if r["month"] != "ALL_DEVELOPMENT"]) != 16:
        raise ValueError("Required monthly H/IMERG/pairing audit coverage incomplete")
    if sum(number(x, "expected_nominal_slots") for x in h) != 144 * sum(
            31 if x["month"][4:] in ("03", "05", "07", "08", "10") else 30 for x in h):
        raise ValueError("Expected ten-minute slot arithmetic mismatch")
    expected = sum(number(x, "expected_nominal_slots") for x in h)
    available = sum(number(x, "available_b13") for x in h)
    missing = sum(number(x, "missing") for x in h)
    if expected != available + missing:
        raise ValueError("B13 expected/available/missing inventory mismatch")
    readable = sum(number(x, "readable_b13") for x in h)
    if readable + sum(number(x, "corrupt_or_unreadable") for x in h) + sum(
            number(x, "duplicate_nominal") for x in h) != available:
        raise ValueError("B13 readable/corrupt/duplicate inventory mismatch")
    if any(number(x, "expected_30min_slots") != 48 * number(x, "expected_days") for x in i):
        raise ValueError("IMERG expected day/slot mismatch")
    imerg_expected_days = sum(number(x, "expected_days") for x in i)
    imerg_complete_days = sum(number(x, "48_slot_complete_days") for x in i)
    imerg_expected_slots = sum(number(x, "expected_30min_slots") for x in i)
    imerg_valid_slots = sum(number(x, "valid_target_slots") for x in i)
    pair_total = number(next(x for x in p if x["month"] == "ALL_DEVELOPMENT"),
                        "total_valid_imerg_windows")
    if pair_total != sum(number(x, "valid_target_slots") for x in i if x["month"][:4] in ("2023", "2024")):
        raise ValueError("Every valid Development IMERG slot must be paired or explicitly classified")
    if h_internal["stage_cleanup_failures"] or i_internal["stage_cleanup_failures"] or h_internal["stage_sha_failures"]:
        raise ValueError("Source staging integrity was not clean")
    if not smoke["selected_sample_count"] or not all(x["finite_forward_loss_backward"] for x in smoke["samples"]):
        raise ValueError("Real multi-sample backward smoke missing or nonfinite")
    if smoke["formal_training_started"] or smoke["optimizer_step_performed"]:
        raise ValueError("Formal training occurred in engineering audit")
    coverage = "COMPLETE" if missing == 0 and available == readable and imerg_complete_days == imerg_expected_days else (
        "PARTIAL" if all(number(x, "readable_b13") > 0 for x in h) and imerg_valid_slots > 0 else "INSUFFICIENT")
    status = {"B0_FORMAL_SCIENTIFIC_CONTRACT": "FROZEN", "B0_FORMAL_SKELETON_IMPLEMENTED": True,
              "B0_FORMAL_TRAINING_STARTED": False, "DEVELOPMENT_DATA_COVERAGE": coverage,
              "B13_PARTIAL_QC_EVIDENCE_READY": True,
              "MASK_AWARE_INPUT_DECISION_REQUIRED": s["mapped_native_invalid_total_in_partial_frames"] > 0,
              "NORMALIZATION_EVIDENCE_READY": n["2023_train_candidate"]["valid_pixel_count"] > 0,
              "QUANTILE_NUMERICAL_STABILITY_DECISION_REQUIRED": stress[
                  "QUANTILE_NUMERICAL_STABILITY_DECISION_REQUIRED"],
              "FORMAL_TRAINING_AUTHORIZED": False}
    return locals()


def report(run, info):
    h, i, p, q, s, n, stress, smoke = [info[x] for x in ("h", "i", "p", "q", "s", "n", "stress", "smoke")]
    status = info["status"]
    pair = next(x for x in p if x["month"] == "ALL_DEVELOPMENT")
    impacts = [x for x in q if x["month"] == "ALL_DEVELOPMENT"]
    lines = ["# Development Data/QC Closure Audit v1", "",
        "This independent run uses the frozen science contract at baseline `c5a7a6bb3746275c16cfd66c2a305cbae016aaff`. "
        "It is real-data engineering evidence, not a formal experiment or training authorization.", "",
        "## Required status", ""]
    lines += [f"- `{key} = {str(value).lower() if isinstance(value, bool) else value}`"
              for key, value in status.items()]
    lines += ["", "## Source coverage", "",
        f"Himawari B13 Development covers 16 months (2023/2024 March–October): "
        f"{info['expected']:,} expected nominal 10-minute slots, {info['available']:,} files, "
        f"{info['readable']:,} readable, {info['missing']:,} missing. "
        f"Among readable files, {sum(number(x, 'fully_valid') for x in h):,} are fully valid, "
        f"{sum(number(x, 'partial') for x in h):,} partial and "
        f"{sum(number(x, 'all_fill') for x in h):,} all-fill; "
        f"{sum(number(x, 'corrupt_or_unreadable') for x in h):,} file is unreadable. "
        "The ten-minute schedule is supported by the previous Stage-0 H09 index and verified source filenames. "
        "Per-month all-fill, partial, full-valid, metadata-invalid and causal-usable counts are in "
        "`himawari_b13_monthly_coverage.csv`. No other Himawari band is an eligibility gate for B0.", "",
        f"IMERG V07 Final: {info['imerg_complete_days']:,}/{info['imerg_expected_days']:,} expected days "
        f"have 48-slot files; {info['imerg_valid_slots']:,}/{info['imerg_expected_slots']:,} half-hour "
        "slots have valid Yunnan target pixels. 2025 March–September is coverage inventory only and was "
        "excluded from normalization and QC threshold fitting. 2025 October remains observation/inference only, "
        "not a supervised blocker.", "",
        "## Causal pairing and latest-slot fallback", "",
        f"All {info['pair_total']:,} valid Development IMERG windows were classified. "
        f"Expected latest available: {number(pair, 'EXPECTED_LATEST_SLOT_AVAILABLE'):,}; "
        f"latest missing/invalid but older causal exists: {number(pair, 'EXPECTED_LATEST_SLOT_MISSING_BUT_OLDER_CAUSAL_EXISTS'):,}; "
        f"no causal frame: {number(pair, 'NO_CAUSAL_FRAME'):,}; "
        f"time metadata error: {number(pair, 'TIME_METADATA_ERROR'):,}. "
        f"Fallback expected-slot reasons: {dict(info['fallback_reasons'])}. "
        "`causal_pairing_summary.csv` separately records duplicated observation ends, equal-end ties, "
        "inverted intervals and metadata inconsistencies. An older frame is logged as fallback evidence; "
        "this run does not approve it as a formal sample.", "",
        "## Partial B13, SP04 support, candidate impacts", "",
        f"Partial-frame invalid native pixels falling inside the frozen mapped weather domain: "
        f"{s['mapped_native_invalid_total_in_partial_frames']:,}; distinct mapped centers affected: "
        f"{s['partial_invalid_centers_ever_inside_mapped_domain']:,}. "
        "The aggregated 501×501 frequency map remains in local evidence with SHA256 in the public JSON. "
        "Disjoint north/south/west/east/interior zones use a descriptive 25-native-pixel band. "
        "This geometry is an audit convention, not a scientific QC threshold. "
        "The existing frozen SP04 CSV was read and hash-verified; no mapping was regenerated. "
        "`sp04_support_distribution.csv` reports 25/25 through 0/25 for all 10,000 target cells and "
        "3,430 Yunnan cells.", "",
        "Candidate A requires whole-scene 100% validity; B/C/D are target-cell support 25/25, "
        "≥24/25 and ≥23/25; E retains partial scenes and reports target-cell validity separately. "
        "The comparison grain is an exact-latest B13 frame paired to a valid IMERG half-hour window. "
        "The 46 older-frame fallback windows are excluded pending researcher approval. "
        "All are counterfactual comparisons only. No candidate is selected. "
        "Percentages and monthly rainy/dry/heavy-rate-proxy counts are in `qc_candidate_impact.csv`. "
        "A rate ≥20 mm/h is only an engineering intensity bin; IMERG intensity alone does not establish convection.", ""]
    for r in impacts:
        lines.append(f"- {r['candidate']}: {number(r, 'retained_scenes'):,}/{number(r, 'baseline_usable_scenes'):,} "
                     f"scenes; {number(r, 'retained_yunnan_pixels'):,}/{number(r, 'possible_yunnan_pixels'):,} "
                     "Yunnan cell-observations retained.")
    lines += ["", "The monthly table provides the season comparison. For each candidate, the "
              "following Development-wide scene-retention rates are descriptive only:", ""]
    for r in impacts:
        rates = []
        for label in ("DRY", "RAINY", "HEAVY_RATE_PROXY_GE20"):
            denominator = number(r, f"{label}_scenes")
            rates.append(f"{label}={100 * number(r, f'{label}_retained_scenes') / denominator:.2f}%"
                         if denominator else f"{label}=no observed cases")
        lines.append(f"- {r['candidate']}: " + ", ".join(rates) + ".")
    lines += ["", "A seasonal or convective bias cannot be settled from these counts alone: "
              "the missing Himawari slots themselves have no B13 scene, and IMERG rain rate is "
              "not a convective classification. The month-by-month counts expose any differential "
              "attrition for researcher review."]
    lines += ["", "## Input and quantile decisions still required", "",
        "The current B0 backbone receives 0.0 K as a placeholder at invalid B13 positions while its validity mask "
        "stays outside the backbone. The mask-aware input status above follows from observed mapped-domain partial "
        "invalid pixels; it does not add a channel, fill data or alter the science contract.", "",
        f"Decision 8 evidence uses {n['2023_train_candidate']['valid_pixel_count']:,} valid 2023 native pixels: "
        f"mean {n['2023_train_candidate']['mean_K']:.6f} K, population std "
        f"{n['2023_train_candidate']['std_K']:.6f} K. Robust statistics and 2024 transformed observations "
        "are in the normalization JSON and decision note. No normalization rule is frozen.", "",
        "The float32 quantile stress test includes raw values from −80 to 80, finite gradients and strict "
        "monotonicity checks. Very negative raw values produced adjacent equal outputs at float32 precision. "
        "The current v2 initialization only addresses the initial forward pass; future parameter updates can "
        "recreate equality. Engineering options are documented in `quantile_numerical_stress.json`; no "
        "sort, clamp or reparameterization was applied.", "",
        "## Real integration and reproducibility", "",
        f"{smoke['selected_sample_count']} real Development samples crossed "
        "Dataset → B0 → frozen SP04 → probability heads → masked loss → backward with finite results. "
        "Focal α=0.25 and γ=2.0 were `ENGINEERING_TEST_ONLY`; no optimizer step or checkpoint was produced. "
        "The large per-frame tables, exact centikelvin histograms and invalid-frequency array remain outside GitHub. "
        "Their paths, schemas, row counts and SHA256 are in `manifest.json`. Raw Himawari/IMERG fields and "
        "the private mask payload are not in this repository.", "",
        "One exceptional 607 MiB H09 file exceeded the standard 16 MiB B0 staging cap. A separate "
        "single-file, 700 MiB bounded, SHA-verified and cleaned audit read confirmed it was fully valid. "
        "Its original cap rejection, corrected classification and before/after aggregate hashes are recorded "
        "in `b13_oversize_reconciliation.json`; the B0 production staging setting remains 16 MiB.", "",
        "The first QC candidate table used every B13 frame as its denominator. Its table, report and manifest "
        "were preserved in local revision history; `qc_impact_grain_reconciliation.json` records their hashes "
        "and the corrected supervised-window denominator.", "",
        "Researcher decisions remain required for partial QC thresholds, fallback acceptability, mask-aware input "
        "handling, Decision 8 normalization and quantile numerical strategy. Formal training remains unauthorized.", ""]
    (run / "DEVELOPMENT_DATA_QC_REPORT.md").write_text("\n".join(lines), encoding="utf-8", newline="\n")


def manifest(run, local, status):
    local_files = ("b13_per_frame.csv", "b13_partial_invalid_frequency.npy",
                   "b13_2023_centikelvin_hist.npy", "b13_2024_centikelvin_hist.npy",
                   "imerg_per_slot.csv", "causal_pairing_per_slot.csv", "h_scan_internal.json",
                   "imerg_scan_internal.json", "oversize_reconciliation.json")
    entries = {}
    for name in local_files:
        path = local / name
        entries[name] = {"local_path": str(path), "bytes": path.stat().st_size, "sha256": sha256(path),
                         "schema": (list(rows(path)[0]) if name.endswith(".csv") else
                                    "uint32[501,501]" if "frequency.npy" in name else
                                    "int64[65536]" if "hist.npy" in name else "JSON summary")}
        if name.endswith(".csv"):
            with path.open(encoding="utf-8-sig") as stream:
                entries[name]["row_count"] = sum(1 for _ in stream) - 1
    public = {str(p.relative_to(run)): sha256(p) for p in run.iterdir() if p.is_file() and p.name != "manifest.json"}
    cadence_index = REPO_ROOT / ("stage0-b0-evidence/evidence/himawari_stage0_outputs/202407/"
        "resume_20260927T104625_772423Z/index/himawari_master_index_202407.csv")
    script_names = ("audit_development_qc.py", "audit_imerg_coverage.py",
                    "finalize_development_qc.py", "real_multisample_qc_smoke.py",
                    "package_development_qc.py", "reconcile_b13_oversize.py",
                    "revise_qc_candidate_impact.py",
                    "verify_b0_real_sample.py")
    revision_dir = local / "pre_supervised_grain_revision"
    revision_history = ({name: {"local_path": str(revision_dir / name),
                                "sha256": sha256(revision_dir / name)}
                         for name in ("qc_candidate_impact.csv", "DEVELOPMENT_DATA_QC_REPORT.md",
                                      "manifest.json", "test_results.txt")}
                        if revision_dir.is_dir() else {})
    data = {"run_id": run.name, "baseline_commit": "c5a7a6bb3746275c16cfd66c2a305cbae016aaff",
            "science_contract_sha256": sha256(REPO_ROOT / "config/science_contract_v1.yaml"),
            "ten_minute_cadence_evidence": {"path": str(cadence_index),
                                           "sha256": sha256(cadence_index)},
            "status": status, "python": sys.executable,
            "public_files_sha256": public, "local_evidence": entries,
            "local_revision_history": revision_history,
            "source_payload_committed": False, "private_mask_payload_committed": False,
            "published_scripts_sha256": {name: sha256(REPO_ROOT / "scripts" / name) for name in script_names},
            "scan_execution_note": "The source scans started before presentation-only explicit-zero CSV formatting edits to the two scan scripts. Computation and source-read rules did not change; current published script hashes identify the reviewed versions. The current-run monthly CSVs were normalized to show zero counts explicitly before packaging."}
    with (run / "manifest.json").open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(data, stream, ensure_ascii=False, indent=2)
        stream.write("\n")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--local-dir", type=Path, required=True)
    args = parser.parse_args()
    run, local = args.run_dir, args.local_dir
    if run.parent.resolve() != (REPO_ROOT / "docs/development_qc/runs").resolve():
        raise ValueError("Unexpected run directory")
    info = summary(run, local)
    report(run, info)
    manifest(run, local, info["status"])
    print(json.dumps(info["status"], ensure_ascii=False))


if __name__ == "__main__":
    main()
