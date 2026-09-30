"""Create researcher-approved additive v1.1 contracts; historical v1 is read-only."""
from datetime import datetime, timezone
import csv
import json
from pathlib import Path
import shutil

import yaml
from yuntapr.contracts.loader import REPO_ROOT, sha256


DOCUMENT = """# YunTAPR-Net Scientific Freeze v1.1

Authority: researcher explicit approval in SCIENTIFIC FREEZE v1.1 + B0 QC CLOSURE + DECISION 8 NORMALIZATION.
Baseline: 890f5cecaa0a8f75f920e66e6d30381ae5c0ff04.

## Scope and inheritance

Scientific Freeze v1.1 supersedes v1 only for explicitly approved formal B0 QC,
input normalization, quantile numerical implementation, and engineering staging
rules. The v1 document, YAML, and every prior evidence run remain immutable.
The time, temporal product, spatial/SP04, split, probability/loss and backbone
definitions in D1–D7 are inherited without reinterpretation. The machine-readable
`formal_b0_supervision` section is a scoped override of the inherited general D5
partial/support rules for formal B0 supervision only. The inherited D1 general
latest-completed-observation definition is unchanged.

## Formal B0 QC closure

B0_FORMAL_SUPERVISED_B13_POLICY = FULL_SCENE_REQUIRED.
B13_PARTIAL_FORMAL_SUPERVISION_ALLOWED = false.
MASK_AWARE_INPUT_REQUIRED_FOR_B0_CORE = false.

A supervised candidate must have readable, metadata-valid B13 with all 251001
native pixels valid. PARTIAL remains preserved for observation, inference and
future robustness research; it cannot enter formal supervised B0. ALL_FILL,
corrupt and unreadable inputs are rejected. There is no interpolation, neighbor
fill, mask channel, backbone change or interpretation of 0 K as an observation.

For each IMERG window [T,T+30min), analysis_time=T+30min. The expected latest
nominal H09 slot is analysis_time−10min, from the audited ten-minute product
schedule; the actual observation must also satisfy obs_end<=analysis_time and
the unchanged D1 latest-completed rule. Nominal time alone does not prove causality.
OLDER_CAUSAL_FALLBACK_ALLOWED_FOR_FORMAL_SUPERVISION = false.
When the expected latest file is absent, reject formal supervision with
EXPECTED_LATEST_B13_MISSING_NO_FORMAL_FALLBACK, even if an older causal frame
exists. NO_CAUSAL_FRAME and TIME_METADATA_ERROR also reject formal supervision.

Phase A Train uses 2023 March–October, Validation uses 2024 March–October, both
with identical QC, expected-latest, causal, IMERG V07 Final time/grid/provenance
and nonempty valid Yunnan supervision requirements. Data eligibility is not
authorization to train. Partial/fallback records remain available as evidence.

## D8 — Input Normalization

Status: FROZEN. Policy: TRAIN_ONLY_Z_SCORE.
x_norm=(T_K−mu_train)/sigma_train; population standard deviation has ddof=0.
Phase A fits only final eligible 2023 Train sample native B13 pixels. 2024
Validation reuses these values without refitting; 2025 never fits normalization.
The numeric constants are DEVELOPMENT_DERIVED_PARAMETER, computed from exact
eligible raw pixels with a hash-identified sample manifest. The broader earlier
Development mean/std are not the final constants.

After architecture, hyperparameters, loss and epoch budget have been frozen in
Phase A, Phase B FinalFit recomputes statistics on eligible 2023+2024 samples.
2025 March–September Final Test must use those FinalFit statistics. FinalFit
statistics are not computed or authorized by this engineering task.

Runtime order is raw Kelvin → QC → eligibility → normalization → backbone.
The formal supervised route requires an entirely valid frame and verified
normalization metadata. Placeholder handling is confined to an explicitly
ENGINEERING_ONLY observation/fixture route. Cin remains 1.

## Quantile numerical implementation

The frozen softplus-positive-increment construction remains. Engineering v3
sets epsilon_mono=1e-4 in log1p(mm h^-1): delta_i=softplus(raw_i)+epsilon_mono,
q1=log1p(0.1)+delta_1 and q_i=q_(i-1)+delta_i. The runtime checks finite outputs,
q1>log1p(0.1), and strict adjacent increase. Any lost ordering at float32
precision must raise; no sort, rank relabel, clamp, or unapproved precision
change is allowed. Closure depends on measured stress results, not the presence
of epsilon alone. Physical-domain overflow also remains an explicit error.

## Bounded staging engineering v3

max_temporary_bytes=734003200 (700 MiB), one_file_at_a_time=true,
verify_sha256=true, cleanup_required=true, ASCII_staging_root_required=true.
The known 636106619-byte valid H09 file fits this explicit bound. A size-only
inventory verifies the maximum observed/verified valid file. A larger valid file
must be reported and an explicit larger fixed-margin cap documented. Sources
remain read-only and only owned UUID staging copies may be removed.

## Execution status

SCIENTIFIC_FREEZE_VERSION = v1.1
B0_FORMAL_SCIENTIFIC_CONTRACT = FROZEN
DECISION_8_NORMALIZATION = FROZEN
B0_FORMAL_SKELETON_IMPLEMENTED = true
B0_PARTIAL_B13_FORMAL_SUPERVISION_ALLOWED = false
B0_OLDER_CAUSAL_FALLBACK_ALLOWED = false
B0_MASK_AWARE_INPUT_REQUIRED = false
B0_FORMAL_TRAINING_STARTED = false
FORMAL_TRAINING_AUTHORIZED = false

Measured normalization, eligibility and numerical-stability readiness are recorded
in the new versioned reports; this contract does not claim those checks have passed.
"""


def main():
    config = REPO_ROOT / "config"
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    closure = REPO_ROOT / "docs/b0_pretraining_closure/runs" / ("run_" + stamp)
    freeze = REPO_ROOT / "docs/scientific_freeze/runs" / ("run_" + stamp + "_v1_1")
    destinations = [config / "science_contract_v1.1.yaml", config / "b0_engineering_v3.yaml",
                    REPO_ROOT / "docs/scientific_freeze/YUNTAPR_SCIENTIFIC_FREEZE_v1.1.md"]
    if any(p.exists() for p in destinations):
        raise FileExistsError("v1.1 destinations already exist")
    closure.mkdir(parents=True, exist_ok=False)
    freeze.mkdir(parents=True, exist_ok=False)
    science = yaml.safe_load((config / "science_contract_v1.yaml").read_text(encoding="utf-8"))
    science.update(schema_version="1.1", contract_id="YUNTAPR_SCIENTIFIC_FREEZE_v1.1",
                   authoritative_document="docs/scientific_freeze/YUNTAPR_SCIENTIFIC_FREEZE_v1.1.md")
    science["precedence"] = {
        "inherits": "config/science_contract_v1.yaml", "inherits_sha256": sha256(config / "science_contract_v1.yaml"),
        "scope": "formal_B0_QC_normalization_quantile_numerics_engineering_staging_only",
        "rule": "Inherit D1-D7 unchanged except explicitly scoped formal_b0_supervision override of general D5 partial/support rules. D1 general causality remains unchanged. D8 added; historical artifacts immutable."}
    science["formal_b0_supervision"] = {
        "status": "FROZEN", "B0_FORMAL_SUPERVISED_B13_POLICY": "FULL_SCENE_REQUIRED",
        "B13_PARTIAL_FORMAL_SUPERVISION_ALLOWED": False,
        "MASK_AWARE_INPUT_REQUIRED_FOR_B0_CORE": False,
        "OLDER_CAUSAL_FALLBACK_ALLOWED_FOR_FORMAL_SUPERVISION": False,
        "formal_supervised_path_requires_full_valid_b13": True,
        "expected_latest_slot": "analysis_time_minus_10_minutes",
        "expected_latest_nominal_cadence_minutes": 10,
        "missing_latest_reject_reason": "EXPECTED_LATEST_B13_MISSING_NO_FORMAL_FALLBACK",
        "required": ["IMERG_V07_Final_valid", "expected_latest_exists", "latest_completed_causal",
                     "B13_readable", "B13_valid_fraction_equals_1", "B13_metadata_valid",
                     "IMERG_time_grid_provenance_pass", "valid_Yunnan_supervised_pixels_gt_0",
                     "no_older_fallback"],
        "partial_other_uses": ["observation", "inference", "future_robustness_research"],
        "partial_payload_deletion_allowed": False}
    science["normalization"] = {
        "decision_id": "D8", "status": "FROZEN", "policy": "TRAIN_ONLY_Z_SCORE",
        "formula": "(raw_B13_Kelvin-mu_train)/sigma_train", "ddof": 0,
        "numeric_values_status": "DEVELOPMENT_DERIVED_PARAMETER",
        "phase_a": {"fit_years": [2023], "fit_months": list(range(3, 11)),
                    "fit_population": "final_eligible_formal_B0_Train_samples_valid_native_pixels",
                    "validation_year": 2024, "validation_refit_allowed": False,
                    "artifact": str((closure / "normalization_phaseA_2023_final_eligible.json").relative_to(REPO_ROOT)).replace("\\", "/")},
        "phase_b": {"fit_years": [2023, 2024], "fit_months": list(range(3, 11)),
                    "starts_after": "Phase_A_architecture_hyperparameters_loss_epoch_budget_frozen",
                    "recompute_on_final_eligible_population": True, "statistics_ready": False},
        "final_test": {"year": 2025, "months": list(range(3, 10)), "statistics_source": "Phase_B_FinalFit", "refit_allowed": False},
        "forbidden_fit_years": [2024, 2025],
        "forbidden_fit_years_scope": "Phase_A_only; Phase_B_can_use_2024_after_protocol_freeze;_2025_always_forbidden",
        "partial_invalid_pixels_included": False, "older_fallback_samples_included": False,
        "runtime_order": ["raw_Kelvin", "QC", "eligibility", "normalization", "backbone"]}
    science["quantile_numerical_implementation"] = {
        "status": "ENGINEERING_CONFIG", "engineering_config": "config/b0_engineering_v3.yaml",
        "delta": "softplus(raw_i)+epsilon_mono", "recurrence": "q_i=q_(i-1)+delta_i",
        "epsilon_domain": "log1p(mm h^-1)", "scientific_parameterization_changed": False,
        "finite_precision_failure_action": "RAISE_FloatingPointError", "sort_or_clamp_allowed": False}
    science["decision_status"].append({"decision_id": "D8", "name": "Input Normalization", "status": "FROZEN",
        "supersedes": "broader_valid_pixel_evidence_not_formal_constants", "remaining_numeric_parameters": "DEVELOPMENT_DERIVED_PARAMETER",
        "evidence": "researcher_approval_and_final_eligible_2023_exact_pixel_fit"})
    science["execution_status"].update(B0_FORMAL_SKELETON_IMPLEMENTED=True, FORMAL_TRAINING_AUTHORIZED=False,
                                          next_phase="RESEARCHER_REVIEW_NO_AUTOMATIC_TRAINING")
    destinations[2].write_text(DOCUMENT, encoding="utf-8", newline="\n")
    destinations[0].write_text(yaml.safe_dump(science, sort_keys=False, allow_unicode=True), encoding="utf-8", newline="\n")
    engineering = yaml.safe_load((config / "b0_engineering_v2.yaml").read_text(encoding="utf-8"))
    engineering.update(schema_version=3, scientific_contract_sha256=sha256(destinations[0]),
                       scientific_freeze_document_sha256=sha256(destinations[2]))
    engineering["staging"].update(max_temporary_bytes=734003200, one_file_at_a_time=True,
                                  cleanup_required=True, ASCII_staging_root_required=True)
    engineering["quantile_numerics"] = {"status": "ENGINEERING_CONFIG", "epsilon_mono": 0.0001,
        "epsilon_domain": "log1p(mm h^-1)", "accumulation_dtype": "float32",
        "recurrence": "sequential", "finite_precision_failure_action": "RAISE_FloatingPointError"}
    engineering["missing"]["formal_supervised_path_requires_full_valid_b13"] = True
    engineering["missing"]["placeholder_allowed_scopes"] = ["ENGINEERING_ONLY", "inference", "fixture", "future_robustness"]
    destinations[1].write_text(yaml.safe_dump(engineering, sort_keys=False), encoding="utf-8", newline="\n")
    shutil.copyfile(destinations[1], closure / "engineering_config_snapshot_v3.yaml")
    with (freeze / "decision_status_v1_1.csv").open("x", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=science["decision_status"][0].keys(), lineterminator="\n")
        writer.writeheader(); writer.writerows(science["decision_status"])
    print(json.dumps({"closure_run": str(closure), "freeze_run": str(freeze)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
