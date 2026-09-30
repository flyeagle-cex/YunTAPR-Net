"""Assemble measured closure reports and byte-level provenance without altering history."""
import argparse
import csv
from datetime import datetime, timezone
import importlib.metadata
import json
from pathlib import Path
import platform
import subprocess
import sys

from yuntapr.contracts.loader import REPO_ROOT, load_contract, sha256
from fit_phase_a_v1_1 import dump, table, PRIOR

BASELINE = "890f5cecaa0a8f75f920e66e6d30381ae5c0ff04"


def main(out, freeze):
    def read(name):
        return json.loads((out/name).read_text(encoding="utf-8"))
    science, config = load_contract()
    norm, quant, smoke = read("normalization_phaseA_2023_final_eligible.json"), read("quantile_numerical_stability_v1.1.json"), read("real_normalized_forward_smoke.json")
    tests, fit, inventory = read("test_summary.json"), read("fit_execution.json"), read("staging_inventory_v3.json")
    with (out/"formal_sample_counts_2023_2024.csv").open(encoding="utf-8", newline="") as stream:
        counts = list(csv.DictReader(stream))
    if not tests["all_passed"] or not fit["all_cleanup_success"] or not smoke["all_cleanup_success"]:
        raise ValueError("Required engineering checks incomplete")
    if not all(s.get("finite_forward_loss_backward", s.get("formal_rejected", False)) for s in smoke["samples"]):
        raise ValueError("Real sample verification incomplete")
    protected = ["config/science_contract_v1.yaml", "config/b0_engineering_v1.yaml", "config/b0_engineering_v2.yaml",
                 "docs/scientific_freeze/YUNTAPR_SCIENTIFIC_FREEZE_v1.md", "docs/development_qc",
                 "docs/b0_skeleton", "docs/b0_real_sample_verification", "stage0-b0-evidence", "config/spatial"]
    # Include all already-tracked freeze runs, not the newly created untracked v1.1 run.
    tracked = subprocess.check_output(["git", "ls-files", "-z", "docs/scientific_freeze/runs"], cwd=REPO_ROOT).decode("utf-8").split("\0")
    protected += [p for p in tracked if p and "run_20260930T095416Z_v1_1/" not in p]
    changed = subprocess.check_output(["git", "diff", "--name-only", BASELINE, "--", *protected], cwd=REPO_ROOT, text=True).strip()
    if changed:
        raise ValueError("IMMUTABLE_HISTORY_CHANGED: "+changed)
    prior_manifest = json.loads((PRIOR/"manifest.json").read_text(encoding="utf-8"))
    for name, expected in prior_manifest["public_files_sha256"].items():
        if sha256(PRIOR/name) != expected:
            raise ValueError("Historical public evidence changed: "+name)
    for name, digest in norm["code_sha256"].items():
        if sha256(REPO_ROOT/name) != digest:
            raise ValueError("Exact-fit code changed since recorded execution: "+name)
    if sha256(out/"engineering_config_snapshot_v3.yaml") != sha256(REPO_ROOT/"config/b0_engineering_v3.yaml"):
        raise ValueError("Engineering snapshot mismatch")
    history = {"baseline": BASELINE, "protected_paths": protected, "git_diff_empty": True,
               "prior_development_public_hashes_verified": len(prior_manifest["public_files_sha256"]),
               "historical_v1_contract_sha256": sha256(REPO_ROOT/"config/science_contract_v1.yaml"),
               "historical_test_change": "One skeleton fixture explicitly loads version=v1; original v1 assertions retained. No historical evidence or configuration changed."}
    dump(out/"history_integrity.json", history)
    status = {"SCIENTIFIC_FREEZE_VERSION": "v1.1", "B0_FORMAL_SCIENTIFIC_CONTRACT": "FROZEN",
              "DECISION_8_NORMALIZATION": "FROZEN", "B0_FORMAL_SKELETON_IMPLEMENTED": True,
              "B0_PARTIAL_B13_FORMAL_SUPERVISION_ALLOWED": False, "B0_OLDER_CAUSAL_FALLBACK_ALLOWED": False,
              "B0_MASK_AWARE_INPUT_REQUIRED": False,
              "QUANTILE_NUMERICAL_STABILITY_CLOSED": quant["QUANTILE_NUMERICAL_STABILITY_CLOSED"],
              "PHASE_A_NORMALIZATION_READY": norm["ready"], "PHASE_A_SAMPLE_ELIGIBILITY_READY": True,
              "B0_FORMAL_TRAINING_STARTED": False, "FORMAL_TRAINING_AUTHORIZED": False}
    status_text = "\n".join(k+" = "+(str(v).lower() if isinstance(v,bool) else v) for k,v in status.items())
    rows = []
    for item in science["decision_status"]:
        row = dict(item)
        row["inherited_v1_status"] = item["status"] if item["decision_id"] != "D8" else "NOT_IN_V1"
        row["v1_1_scope_note"] = "Inherited without scientific change"
        if item["decision_id"] == "D1":
            row["v1_1_scope_note"] = "General causality unchanged; formal supervised eligibility additionally requires expected latest slot, no older fallback"
        if item["decision_id"] == "D5":
            row.update(status="FROZEN_FOR_FORMAL_B0_CORE", remaining_numeric_parameters="none_for_formal_B0_partial_policy",
                       v1_1_scope_note="FULL_SCENE_REQUIRED; inherited general partial/support field remains only outside formal B0 core")
        if item["decision_id"] == "D6":
            row["v1_1_scope_note"] = "Scientific probability unchanged; engineering epsilon 1e-4 approved; universal float32 numerical closure remains false"
        if item["decision_id"] == "D8":
            row["v1_1_scope_note"] = "FROZEN policy; exact 2023-only constants are DEVELOPMENT_DERIVED_PARAMETER"
        rows.append(row)
    table(freeze/"decision_status_v1_1.csv", rows)
    versions = {}
    for name in ("numpy", "torch", "netCDF4", "xarray", "zarr", "numcodecs", "pyarrow", "h5py", "h5netcdf", "PyYAML"):
        try:
            versions[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            versions[name] = "NOT_INSTALLED_OR_NO_DISTRIBUTION_METADATA; NOT_USED_IN_THIS_RUN"
    dump(out/"execution_log.json", {"packaged_utc": datetime.now(timezone.utc).isoformat(), "python": sys.executable,
         "python_version": platform.python_version(), "package_versions": versions, "packages_installed_or_upgraded": False,
         "execution_order": ["versioned_contract_creation_and_loader_check", "historical_hash_verification_and_size_inventory", "490_IMERG_day_time_grid_provenance_revalidation", "formal_eligibility_23520_windows", "exact_2023_native_pixel_fit_11720_scenes", "pin_derived_artifact", "constant_random_adversarial_float32_stress", "real_normalized_and_rejection_smoke", "all_four_regression_suites", "history_integrity_and_reports"],
         "first_smoke_retained": "real_normalized_forward_smoke_single_frame_context_attempt.json; successful, but older_causal_available only reflected singleton records. Final smoke rerun with six-slot indexed context to make availability evidence complete.",
         "packaging_attempt_1": "PackageNotFoundError for optional unused h5py distribution metadata. Version logging now records absent metadata explicitly; no package install/upgrade.",
         "no_2025_pixel_read": True, "raw_sources_read_only": True, "next_action_after_push": "STOP_NO_TRAINING"})
    summary_table = "| Quantity | 2023 Train | 2024 Validation |\n|---|---:|---:|\n"
    labels = [("IMERG windows total", "imerg_windows_total"), ("Expected latest available", "expected_latest_available"),
              ("Older-fallback windows rejected", "older_fallback_rejected"), ("Partial rejected", "partial_rejected"),
              ("All-fill rejected", "all_fill_rejected"), ("Unreadable rejected", "unreadable_rejected"),
              ("Metadata rejected", "metadata_rejected"), ("Final eligible scenes", "final_supervised_eligible_scenes"),
              ("Yunnan supervised pixel observations", "final_supervised_yunnan_pixel_observations")]
    for label, key in labels:
        summary_table += f"| {label} | {int(counts[0][key]):,} | {int(counts[1][key]):,} |\n"
    report = f"""# B0 PRETRAINING CLOSURE REPORT — v1.1

Run: {out.name}. Baseline: `{BASELINE}`. Scope: researcher-approved scientific
freeze synchronization, formal sample QC, exact train-only statistics and engineering
forward/backward verification. No model training is authorized or started.

**QC and Phase-A normalization are ready; quantile numerical stability is NOT CLOSED.**
Passing tests include verification that remaining precision failures raise loudly;
they do not establish that every extreme float32 tensor remains strictly ordered.

## FROZEN

Formal B0 requires the whole 501×501 B13 frame valid and the expected latest nominal
slot at analysis_time−10 minutes, with actual obs_end≤analysis_time and unchanged D1
latest-completed causality. Partial frames remain preserved for other research uses.
Missing latest slots cannot use an older causal replacement. Cin=1, backbone,
SP04 coordinates/membership, mask, IMERG product, split and scientific probability
definitions remain unchanged. D5's inherited generic unresolved partial/support
field is superseded for formal B0 by the explicit full-scene requirement.

Decision 8 is FROZEN: Train-only Z-score, population std (ddof=0). Its actual constants
are DEVELOPMENT_DERIVED_PARAMETER, not researcher-entered values. Phase A fits only
final-eligible March–October 2023 Train scenes; 2024 Validation reuses the result.

## Final sample population

{summary_table}
The 23,520 Development windows are the candidate denominator, not the final usable
population. Exactly 46 missing-latest and 27 partial windows are excluded, leaving
23,447 scenes. The all-fill/unreadable zeros above are at the expected-latest paired
supervised-window grain; they do not contradict defects elsewhere in the full native
ten-minute inventory. No source file was deleted or filled.

The old local B13, IMERG and pairing indexes were SHA256-verified against the immutable
Development manifest. This run reread all 490 Development IMERG days and verified
48-slot time order, actual SP04 target coordinates, V07 Final metadata plus completion
manifest, and valid Yunnan pixels. All 11,720 fit B13 frames were reread and rechecked
for exact native coordinates, packing, full validity, source times and causality.
The remaining 2024 population QC uses the prior verified per-frame audit snapshot;
this run also reread a 2024 normalized smoke frame and the oversized valid frame.
Every runtime read repeats source QC. No claim is made that all 2024 B13 were reread.

## Exact Phase-A normalization

- Eligible scenes: {norm['eligible_scene_count']:,}.
- Native valid pixels: {norm['valid_pixel_count']:,}.
- Mean: {norm['mean_K']:.15f} K.
- Population standard deviation: {norm['std_K']:.15f} K.
- Min / p1 / q1 / median / q3 / p99 / max: {norm['min_K']}, {norm['p1_K']}, {norm['q1_K']}, {norm['median_K']}, {norm['q3_K']}, {norm['p99_K']}, {norm['max_K']} K.
- IQR: {norm['IQR_K']} K.
- Sample manifest SHA256: `{norm['sample_manifest_sha256']}`.

The fit decodes each raw packed pixel exactly as the runtime float32 reader, then uses
float64 arithmetic. An exact histogram over all int16 code points, with no rounding
or rebinning, gives moments and exact rank-interpolated percentiles. Independent
per-frame merged central moments agree within 1e-9 K. The old broader normalization
histograms were not read for this fit. The new JSON pins fit-code hashes, baseline,
source root, science contract, exclusions and sample list; engineering v3 pins its hash.
No 2024 or 2025 pixel enters fitting. 2025 receives only size-only inventory checks.

Runtime keeps raw Kelvin and normalized inputs separate. The formal-rule dataset
enforces QC and eligibility before normalization. Batch validation rejects raw Kelvin,
missing metadata and partial masks before `forward_formal` calls the backbone directly,
without placeholder substitution. The legacy engineering observation path remains
explicitly scoped. Phase-A normalization refuses 2025 use.

## Quantile stability: RESEARCHER_DECISION_REQUIRED

The implementation reads epsilon_mono=1e-4 from engineering v3 and applies the exact
sequential recurrence in log1p(mm h^-1). All ten requested constants from −100 through
100 pass: finite, strict increase, zero adjacent equality and finite gradients. The
seeded uniform [−100,100] case also passes. Random normal and signed-extreme cases
have 112 and 305 adjacent equalities respectively; a reproducible tensor of 22 raw
+100 channels followed by 10 raw −100 channels has 10 equalities. Every such runtime
call raises FloatingPointError. At q≈2200, float32 spacing is 0.000244140625, so the
approved 0.0001 increment can be rounded away. No sorting, clamp, rank relabel,
precision change or epsilon adjustment was introduced. Gradients of the diagnostic
recurrence are finite, but that does not repair ordering.

`QUANTILE_NUMERICAL_STABILITY_CLOSED=false`. Researcher review of a precision strategy
or approved admissible raw domain is needed before a universal closure claim. Large
positive log quantiles also overflow physical expm1 independently; the head keeps its
explicit physical-finiteness error. This report does not silently change either rule.

## Real execution and staging

Real 2023-03-01 and 2024-03-01 00:00 UTC windows pass raw B13 → QC → formal eligibility
→ the same 2023 normalization → backbone → frozen SP04 → probability heads → masked
loss → backward. Each has 3430 valid Yunnan loss pixels and all 74 parameter-tensor
gradients finite. Execution and temporary focal alpha=0.25/gamma=2.0 are engineering
tests only; there was no optimizer update or checkpoint. Real partial and missing
latest/older-causal cases are rejected before the backbone. Source hashes are unchanged.
The first successful singleton-context smoke is preserved separately; the final smoke
uses indexed six-slot context so older-frame availability is accurately represented.

MAX_VALID_B13_FILE_BYTES={inventory['MAX_VALID_B13_FILE_BYTES']}.
Configured cap={inventory['cap_bytes']} bytes (700 MiB), margin={inventory['actual_margin_bytes']}
bytes, exceeding a fixed 32 MiB safety allowance. The real largest file was staged,
SHA256-verified, read as 251001 valid pixels, and cleaned successfully. Only owned UUID
temporary files under the ASCII staging root were removed; earlier diagnostic caches
and all raw data remain intact. Readers are sequential, one active staging instance.

Fit wall time: {fit['elapsed_seconds']:.3f} s. The {fit['staging_operations']:,} fit/revalidation
copies used {fit['copy_seconds']:.3f} s copy time and {fit['read_seconds']:.3f} s read/QC/statistics
time; per-source logs include bytes and cleanup. SHA verification adds two reads outside
copy_seconds. Fit temporary peak was {fit['temporary_peak_bytes']} bytes; the separate large-file
smoke peak was {inventory['MAX_VALID_B13_FILE_BYTES']} bytes. No package was installed/upgraded.

## Verification and remaining work

{tests['tests_run']} tests passed: historical scientific v1=42, skeleton=20, Development QC=8,
new v1.1=30. The skeleton fixture now explicitly selects historical v1 so its original
v2 assertions remain meaningful. All protected tracked historical evidence is unchanged
against the baseline, and prior public Development hashes were reverified.

NOT_YET_FROZEN / NOT_COMPUTED: focal alpha/gamma, Phase-A selected hyperparameters and
epoch budget, and Phase-B FinalFit normalization. Phase B must recompute on eligible
2023+2024 only after the Phase-A protocol is fixed; Final Test 2025 Mar–Sep must reuse
that FinalFit artifact. No next stage is started by this run.

## Final status

```text
{status_text}
```
"""
    (out/"B0_PRETRAINING_CLOSURE_REPORT.md").write_text(report, encoding="utf-8", newline="\n")
    freeze_report = f"""# SCIENTIFIC FREEZE V1.1 REPORT

Run: {freeze.name}. Baseline: `{BASELINE}`.
Authority: the researcher's explicit v1.1 / B0 QC / Decision 8 approval.

## Approved synchronization

New document: `docs/scientific_freeze/YUNTAPR_SCIENTIFIC_FREEZE_v1.1.md`.
New contract: `config/science_contract_v1.1.yaml`.
New engineering configuration: `config/b0_engineering_v3.yaml`.
Historical v1 documents, configurations and evidence are unchanged. D1–D7 dictionaries
remain exactly equal; scoped formal B0 QC overrides and D8 are explicit additions.
The active loader uses v1.1 and supports explicit historical v1 loading.

FROZEN: formal B0 whole-frame validity; expected-latest required with no older fallback;
Decision 8 Train-only Z-score; v3 epsilon recurrence and bounded staging engineering.
The original D1 general causality remains unchanged. Partial data are preserved and
no mask channel/backbone change was introduced. The decision CSV distinguishes inherited
v1 statuses from the current formal-B0 scope to avoid leaving the resolved partial policy
apparently open.

The exact 2023 eligible fit has {norm['eligible_scene_count']:,} scenes and
{norm['valid_pixel_count']:,} native pixels: μ={norm['mean_K']} K,
σ={norm['std_K']} K, ddof=0. These are derived parameters with a pinned sample manifest,
not manually frozen scientific numbers. 2024 Validation uses the identical artifact;
Phase B / 2025 Final Test rules are recorded without computing FinalFit statistics.

## Measured closure and limits

Formal sample counts are 11720 Train and 11727 Validation; 46 fallback windows and
27 partial windows are excluded from 23520 candidates. The real normalized 2023/2024
chain, real rejection examples, largest-file staging, and all {tests['tests_run']} tests executed.
No formal training, optimizer update, checkpoint or 2025 fitting occurred.

RESEARCHER_DECISION_REQUIRED: epsilon=1e-4 passes every requested constant stress but
does not guarantee strict order for mixed extreme float32 tensors. Random failures and
a deterministic counterexample raise explicitly. Numerical stability is **not closed**;
passing guard tests must not be presented as universal numerical success.

NOT_YET_FROZEN / NOT_COMPUTED: focal alpha/gamma and Phase-A model selection parameters;
FinalFit statistics await the required protocol freeze. Training is unauthorized.

Full results: `docs/b0_pretraining_closure/runs/{out.name}/B0_PRETRAINING_CLOSURE_REPORT.md`.
Integrity and artifact hashes are in the two run manifests. Stop after GitHub sync.

## Final status

```text
{status_text}
```
"""
    (freeze/"SCIENTIFIC_FREEZE_V1_1_REPORT.md").write_text(freeze_report, encoding="utf-8", newline="\n")
    (freeze/"test_results.txt").write_bytes((out/"test_results.txt").read_bytes())
    code = list((REPO_ROOT/"src/yuntapr").rglob("*.py")) + list((REPO_ROOT/"scripts").glob("*v1_1*.py"))
    code += list((REPO_ROOT/"tests/scientific_freeze_v1_1").glob("*.py"))
    code += [REPO_ROOT/"scripts/freeze_v1_1_build_contracts.py", REPO_ROOT/"config/science_contract_v1.1.yaml", REPO_ROOT/"config/b0_engineering_v3.yaml", REPO_ROOT/"README.md", REPO_ROOT/"docs/b0_pretraining_closure/README.md", REPO_ROOT/science["authoritative_document"]]
    common = {"baseline_commit": BASELINE, "status": status, "code_and_contract_sha256": {str(p.relative_to(REPO_ROOT)).replace("\\", "/"): sha256(p) for p in code},
              "historical_evidence_unchanged": True, "prior_development_manifest_sha256": sha256(PRIOR/"manifest.json"), "python": sys.executable,
              "commit_identity": "Containing Git commit; reported and checked against GitHub API after push to main"}
    dump(out/"manifest.json", {**common, "run_id": out.name,
         "public_files_sha256": {p.name: sha256(p) for p in out.iterdir() if p.is_file() and p.name != "manifest.json"}})
    dump(freeze/"manifest.json", {**common, "run_id": freeze.name, "closure_manifest_sha256": sha256(out/"manifest.json"),
         "public_files_sha256": {p.name: sha256(p) for p in freeze.iterdir() if p.is_file() and p.name != "manifest.json"}})
    print(json.dumps({"status": status, "tests": tests["tests_run"], "history_unchanged": True}), flush=True)


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--run-dir", type=Path, required=True)
    p.add_argument("--freeze-dir", type=Path, required=True)
    args = p.parse_args()
    main(args.run_dir, args.freeze_dir)
