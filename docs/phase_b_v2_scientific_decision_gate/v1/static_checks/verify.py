"""Static candidate review only. No project imports, datasets or execution gate.

Reads this document package and an explicit public-source whitelist. It cannot
verify human approvals or enable training. --check-only performs no writes.
"""
from __future__ import annotations

import argparse
import ast
import copy
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[4]
PACKAGE = Path(__file__).resolve().parents[1]
BASELINE = "090ad2e3a912e214976b4236f90f99f41df7cd2e"
DOCS = ("README.md", "SCIENCE_PROTOCOL_CANDIDATE.md", "OPERATIONAL_LATENCY_POSITION.md",
        "EFFECT_THRESHOLDS_AND_MULTIPLICITY_OPTIONS.md", "DATA_INTEGRITY_COMPLETION_OPTIONS.md",
        "FORMAL_INTEGRATION_DIFF.md", "RESEARCHER_DECISIONS_TO_SIGN.md")
FLAGS = {
    "V2_PHASE_B_AUTHORIZED": False, "FORMAL_SCIENTIFIC_EXECUTION_AUTHORIZED": False,
    "RESEARCHER_SCIENTIFIC_APPROVAL_REQUIRED": True,
    "HISTORICAL_RECOVERY_RATIFICATION": "NOT_GRANTED", "FORMAL_OPTIMIZER_STEPS": 0,
    "2025_PIXELS_READ": 0, "2025_RAW_ACCESS": 0, "can_launch_formal_training": False,
}
ARMS = {"E0": {"alpha": .5, "gamma": 2, "lambda_q": 1},
        "E1": {"alpha": .5, "gamma": 0, "lambda_q": 1},
        "E2": {"alpha": .5, "gamma": 2, "lambda_q": 2}}
MODELS, SEEDS = ["B0_MATCHED_V2", "B1_V2"], [2026, 2027, 2028]
UNITS = {
    "minimum_brier_improvement": "ABSOLUTE_DIMENSIONLESS",
    "minimum_abs_q32_error_reduction": "COVERAGE_PROPORTION",
    "maximum_cpb_degradation": "LOG1P_DOMAIN_PINBALL",
    "maximum_strong_rain_cpb_degradation_by_bin": "LOG1P_DOMAIN_PINBALL_BY_FROZEN_BIN",
    "maximum_brier_degradation_HQ": "ABSOLUTE_DIMENSIONLESS",
    "maximum_auroc_drop": "ABSOLUTE_DIMENSIONLESS",
    "maximum_ap_drop": "ABSOLUTE_DIMENSIONLESS",
    "tail_distribution_acceptance_rule": "EXPOSURE_FRACTION_AND_LOG_SPAN_RULE",
    "seed_guardrail_aggregation_rule": "LOGICAL_RULE", "minimum_eligible_blocks": "BLOCK_COUNT",
    "minimum_available_replicate_fraction": "FRACTION",
}


def read_json(path: Path) -> dict:
    """Reject non-standard NaN/Infinity JSON, without importing project modules."""
    def invalid(value):
        raise ValueError("Nonfinite JSON constant: " + value)
    return json.loads(path.read_text(encoding="utf-8"), parse_constant=invalid)


def require(ok: bool, reason: str) -> None:
    if not ok:
        raise ValueError(reason)


def same(actual, expected, reason: str) -> None:
    # Serialize to distinguish false/0 and true/1; Python equality conflates them.
    require(json.dumps(actual, sort_keys=True, allow_nan=False) ==
            json.dumps(expected, sort_keys=True, allow_nan=False), reason)


def validate_candidate(c: dict) -> None:
    """Consistency of an unsigned proposal, NEVER authentication/authorization."""
    require(set(c) == {"schema", "baseline_commit", "status", "decision_status", "execution_status",
                      "scope", "governance", "protocol", "runs", "budget", "metrics", "statistics",
                      "positioning", "integrity", "approval_events", "decision_groups", "thresholds"},
            "Unknown/missing candidate field")
    same(c["schema"], "PHASE_B_V2_SCIENTIFIC_DECISION_CANDIDATE_v1", "schema")
    same(c["baseline_commit"], BASELINE, "baseline")
    same(c["status"], "PROPOSED_FOR_RESEARCHER_APPROVAL", "status cannot upgrade")
    same(c["decision_status"], "RESEARCHER_DECISION_REQUIRED", "decision status")
    same(c["execution_status"], "NOT_AUTHORIZED", "execution status")
    same(c["scope"], "PUBLIC_EVIDENCE_AND_STATIC_DOCUMENTS_ONLY", "scope")
    same(c["governance"], FLAGS, "All scientific boundaries must remain closed")
    p = c["protocol"]
    expected_protocol = {
        "route": "D1", "qualification": "Q1_M1_PAIRED_FROZEN", "normalization": "N0_FROZEN_2023_SHARED",
        "initialization": "I3_PAIRED_FRESH", "train_year": 2023, "development_year": 2024,
        "sealed_years": [2025], "months": [3,4,5,6,7,8,9,10], "train_scenes": 10455,
        "development_scenes": 10501, "seeds": SEEDS, "models": MODELS, "arms": ARMS, "epochs": 9,
        "budget": "B9", "scheduler": "S0_ORIGINAL_50_EPOCH_PREFIX", "scheduler_horizon": 50,
        "selection": "V0_FIXED_EPOCH9", "train_batch": 2, "validation_batch": 8,
        "accumulation": 1, "drop_last": False, "warm_start": False, "quantiles": 32, "tau32": .984375,
        "rain_label": "FLOAT32_Y_GT_FLOAT32_0.1_BEFORE_PROMOTION", "quantile_dtype": "FP64",
        "common_evaluation_dtype": "FP64", "yunnan_cells": 3430, "target_shape": [100,100],
    }
    same(p, expected_protocol, "Frozen matrix/data/numerics changed")
    runs = [{"run_id": f"{arm}__{model}__s{seed}", "arm": arm, "model": model, "seed": seed,
             "status": "NOT_EXECUTED"} for seed in SEEDS for arm in ARMS for model in MODELS]
    same(c["runs"], runs, "18-run closed candidate identity/order")
    ntrain, nval, epochs = (10455+1)//2, (10501+7)//8, 9
    same(c["budget"], {
        "runs": 18, "formal_runs_executed": 0, "updates_per_epoch": ntrain,
        "updates_per_run": epochs*ntrain, "updates_total": 18*epochs*ntrain,
        "validation_batches_per_epoch": nval, "validation_batches_per_run": epochs*nval,
        "validation_batches_total": 18*epochs*nval, "stage1_runs": 6,
        "stage1_updates": 6*epochs*ntrain, "stage1_validation_passes": 6*epochs,
        "stage1_validation_batches": 6*epochs*nval, "stage2_runs": 12,
        "stage2_updates": 12*epochs*ntrain, "stage2_validation_batches": 12*epochs*nval,
    }, "Integer budget")
    same(c["metrics"], {
        "primary_HO": "BRIER_E1_MINUS_E0_BY_MODEL_SEED",
        "primary_HQ": "ABS_Q32_COVERAGE_ERROR_E2_MINUS_E0_BY_MODEL_SEED",
        "training": "(S_occ_gamma_arm+lambda_q*S_qr)/N_valid",
        "common_core": "(S_occ_gamma2_FP64+S_qr_unweighted_FP64)/N_valid",
        "conditional_pinball": "S_qr_unweighted_FP64/N_rain",
        "quantile_coverage": "RAIN_VALID_LOG1P_Y_LE_Q_FP64",
        "rain_strata_mm_h": ["(0.1,1]","(1,5]","(5,10]","(10,20]","(20,30]","(30,50]","(50,inf)"],
        "tail_thresholds_mm_h": [10,50,100,500,1000], "probability_bins": 10,
        "empty_metric": "NA_WITH_REASON_NO_REDRAW", "report_all_32": True,
    }, "Training/common evaluation denominators or diagnostic family changed")
    same(c["statistics"], {
        "recommended_method": "M-C_FULL_EFFECTS_POINTWISE_EXPLORATORY_INTERVALS",
        "recommendation_status": "NOT_APPROVED", "confirmatory_significance_claim": False,
        "fwer_control_claim": False, "bootstrap": {"status": "PROPOSED_NOT_EXECUTED",
            "utc_start": "2024-03-01", "utc_end": "2024-10-31", "blocks": 35, "block_days": 7,
            "replicates": 2000, "seed": 2026, "paired_all_runs": True,
            "ratio_after_pool": True, "percentiles": [2.5,97.5]},
        "primary_comparisons": 4, "seed_summary": "PER_SEED_EFFECT_THEN_EQUAL_MEAN_RANGE_DESCRIPTIVE_SD",
        "threshold_policy": "DESCRIPTIVE_NO_AUTOMATIC_SUCCESS_OR_ADOPTION",
        "statistical_power": "NOT_YET_ESTABLISHED", "independent_event_count": "NOT_YET_ESTABLISHED",
        "raw_p_construction": "NOT_YET_ESTABLISHED",
    }, "Exploratory statistical scope")
    same(c["positioning"], {
        "recommended": "A_RETROSPECTIVE_CAUSAL_IR_WITH_DEPLOYMENT_POTENTIAL",
        "recommendation_status": "NOT_APPROVED", "strict_operational_B": "NOT_ESTABLISHED",
        "latency_deadline_seconds": None,
    }, "No operational claim or invented latency deadline")
    same(c["integrity"], {
        "prior_preflight_overall": "NOT_VERIFIED", "frozen_scenes": 20956,
        "referenced_unique_files": 67006, "payload_sha_unique_files": 294,
        "payload_sha_not_verified_files": 66712, "decoded_scenes": 48,
        "late_created_scene_slot_references": 27880,
        "initial_2025_path_attribute_queries": "NOT_INSTRUMENTED",
        "historical_2025_payload_binary_reads": 0, "historical_2025_pixels_read": 0,
        "kernel_wide_zero_access_claim": False, "real_preflight_rerun_after_guard_fix": False,
        "recommended_completion": "I-C_APPROVED_SWEEP_AND_SAME_BYTES_OR_IMMUTABLE_CONSUMPTION",
        "recommendation_status": "NOT_APPROVED",
    }, "Readiness or historical access claim changed")
    same(c["thresholds"], {k: {"status": "NOT_YET_ESTABLISHED", "value": None, "unit": v}
                           for k,v in UNITS.items()}, "Unsupported effect/tolerance values")
    same(c["approval_events"], [], "No generated approval event")
    same(c["decision_groups"], [{
        "id": group, "status": "NOT_APPROVED", "researcher_event_reference": None
    } for group in ("DG1_SCIENTIFIC_SCOPE_AND_INDEPENDENT_HISTORY_DISPOSITION",
                    "DG2_PROTOCOL_STATISTICS_THRESHOLDS", "DG3_INTEGRITY_AND_FUTURE_READONLY_SCOPE",
                    "DG4_FORMAL_INTEGRATION_AUTHORITY_RESOURCES", "DG5_SEPARATE_STAGE1_EXECUTION")],
        "Unsigned decisions")


def public_source(path: str) -> Path:
    """Only registry-listed, tracked public documentation/source; no raw roots."""
    relative = PurePosixPath(path)
    require(not relative.is_absolute() and ".." not in relative.parts and "\\" not in path,
            "Noncanonical public reference")
    allowed = (
        path.startswith("docs/phase_b_v2_") or path.startswith("docs/phase_a_evidence_hardening/")
        or path.startswith("docs/v2_scientific_acceptance/") or
        (path.startswith(("src/yuntapr/", "scripts/phase_b_v2_real_data_preflight/",
                          "tests/phase_b_v2_real_data_preflight/")) and path.endswith(".py"))
        or path in ("config/science_v2/phase_a_protocol_frozen_v1.json", "config/science_contract_v1.1.yaml")
    )
    require(allowed and ".local" not in relative.parts, "Outside public-source whitelist")
    subprocess.run(["git", "ls-files", "--error-unmatch", "--", path], cwd=ROOT,
                   check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
    return ROOT.joinpath(*relative.parts)


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run_checks() -> dict:
    cases = []
    def case(name, fn):
        try:
            detail = fn()
            cases.append({"name": name, "status": "PASS", "detail": detail})
        except Exception as exc:
            cases.append({"name": name, "status": "FAIL", "reason": str(exc)})

    c = read_json(PACKAGE/"decision_candidate.json")
    case("closed_unsigned_candidate", lambda: validate_candidate(c))
    old = read_json(ROOT/"docs/phase_b_v2_ablation_preregistration/v1/protocol_proposed.json")
    def matrix_against_published():
        same(c["protocol"]["arms"], {v["id"]: {k:v[k] for k in ("alpha","gamma","lambda_q")}
                                    for v in old["arms"]}, "Published arms")
        same(c["protocol"]["models"], old["models"], "Published models")
        same(c["protocol"]["seeds"], old["controls"]["seeds"], "Published seeds")
        same([v["run_id"] for v in c["runs"]], [v["run_id"] for v in old["runs"]], "Published IDs")
        require(len(c["runs"]) == 18 and len({v["run_id"] for v in c["runs"]}) == 18, "Unique 18 IDs")
    case("published_matrix_identity", matrix_against_published)

    # Negative controls mutate only this unsigned JSON; no synthetic tensors.
    changes = [
        ("self_approved", ("status",), "APPROVED"),
        ("authorization_boolean", ("governance","V2_PHASE_B_AUTHORIZED"), True),
        ("boolean_count", ("governance","FORMAL_OPTIMIZER_STEPS"), False),
        ("fake_approval_event", ("approval_events",), [{"status":"APPROVED"}]),
        ("wrong_gamma", ("protocol","arms","E1","gamma"), 2),
        ("wrong_lambda", ("protocol","arms","E2","lambda_q"), 1),
        ("unknown_seed", ("protocol","seeds"), [2026,2027,2029]),
        ("sealed_train_year", ("protocol","train_year"), 2025),
        ("best_selection", ("protocol","selection"), "BEST"),
        ("warm_start", ("protocol","warm_start"), True),
        ("rescheduled_cosine", ("protocol","scheduler_horizon"), 9),
        ("budget_extension", ("budget","stage1_updates"), 282313),
        ("weighted_scientific_pinball", ("metrics","conditional_pinball"), "lambda_q*S_qr/N_rain"),
        ("invented_effect", ("thresholds","minimum_brier_improvement","value"), .001),
        ("confirmed_significance", ("statistics","confirmatory_significance_claim"), True),
        ("operational_claim", ("positioning","strict_operational_B"), "ESTABLISHED"),
        ("preflight_upgrade", ("integrity","prior_preflight_overall"), "PASS"),
        ("kernel_zero_claim", ("integrity","kernel_wide_zero_access_claim"), True),
        ("erase_historical_gap", ("integrity","initial_2025_path_attribute_queries"), 0),
        ("fake_real_rerun", ("integrity","real_preflight_rerun_after_guard_fix"), True),
    ]
    for name, path, value in changes:
        def reject(path=path, value=value):
            mutated = copy.deepcopy(c)
            target = mutated
            for key in path[:-1]:
                target = target[key]
            target[path[-1]] = value
            try:
                validate_candidate(mutated)
            except ValueError:
                return "Rejected as required; no execution capability"
            raise ValueError("Invalid candidate accepted")
        case("negative_"+name, reject)

    registry = read_json(PACKAGE/"source_registry.json")
    def sources():
        require(registry["baseline_commit"] == BASELINE, "Registry baseline")
        paths = [e["path"] for e in registry["files"]]
        require(len(paths) == len(set(paths)), "Duplicate source reference")
        for item in registry["files"]:
            path = public_source(item["path"])
            require(digest(path) == item["sha256"], "Source SHA changed: "+item["path"])
            blob = subprocess.check_output(["git","show",BASELINE+":"+item["path"]], cwd=ROOT)
            require(hashlib.sha256(blob).hexdigest() == item["sha256"], "Baseline blob SHA mismatch")
        return {"public_files_sha_verified": len(paths), "raw_artifacts_read": 0}
    case("public_source_sha_and_baseline", sources)

    def evidence():
        previous = read_json(ROOT/"docs/phase_b_v2_real_data_preflight/v1/final_status.json")
        summary = read_json(ROOT/"docs/phase_b_v2_real_data_preflight/v1/PACKAGE_VERIFICATION.json")
        require(previous["overall_status"] == "NOT_VERIFIED", "Prior readiness")
        identities = previous["checks"]["frozen_sample_identity"]
        require(identities["train_scenes"]+identities["development_scenes"] == 20956, "Scene total")
        total = previous["checks"]["source_reference_inventory"]["unique_files"]
        require(total-summary["raw_data_unique_files"] == 66712, "SHA remainder")
        require(previous["checks"]["temporal_metadata"]["file_created_after_analysis_scene_slot_exposures"]
                == 27880, "Late-created references")
        require(summary["selected_scenes"] == 48, "Limited decode")
        require(previous["code_provenance"]["initial_negative_test_path_attribute_queries"]
                == "NOT_INSTRUMENTED", "Unknown attributes preserved")
        require(previous["code_provenance"]["real_raw_data_reads_after_hardening"] == 0, "No rerun")
        return "Public aggregates only; no real file probing"
    case("preflight_limit_reconciliation", evidence)

    def docs():
        link_count = 0
        for name in DOCS:
            text = (PACKAGE/name).read_text(encoding="utf-8")
            require(len(text)>400 and text.startswith("# "), "Empty/invalid document "+name)
            require(not re.search(r"(?<![A-Za-z0-9])[A-Za-z]:[\\/]|/Users/|/home/|\\\\[A-Za-z]", text), "Private path "+name)
            require(text.count("$$")%2 == 0, "Unclosed display equation "+name)
            for target in re.findall(r"\[[^\]]+\]\(([^)]+)\)", text):
                if target.startswith(("https://", "http://")):
                    continue  # referenced URLs, not fetched by this checker
                dest = (PACKAGE/target.split("#")[0]).resolve()
                require(dest.is_relative_to(ROOT) and dest.is_file(), "Broken/outside local link "+target)
                link_count += 1
        return {"documents": len(DOCS), "local_links": link_count}
    case("documents_links_privacy_equations", docs)

    def blocked_source():
        source = ROOT/"src/yuntapr/experimental/phase_b_v2_formal_runner_candidate/authorization.py"
        tree = ast.parse(source.read_text(encoding="utf-8"))
        for name in ("start_formal", "open_real_data"):
            fn = next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name==name)
            require(len(fn.body)==1 and isinstance(fn.body[0],ast.Raise), "Formal entry not always blocked")
        return "AST only, not imported/called"
    case("formal_entry_static_always_raise", blocked_source)

    def frozen_git():
        names = subprocess.check_output(["git","diff",BASELINE,"--name-only"],cwd=ROOT,text=True).splitlines()
        require(all(n.startswith("docs/phase_b_v2_scientific_decision_gate/v1/") for n in names),
                "Existing protected tracked files modified")
        return {"existing_tracked_files_modified":0}
    case("protected_git_diff", frozen_git)

    def status():
        s = read_json(PACKAGE/"final_status.json")
        for key, value in FLAGS.items():
            same(s[key], value, "Status boundary "+key)
        same(s["prior_real_preflight_status"], "NOT_VERIFIED", "Status readiness")
        same(s["historical_2025_path_attributes"], "NOT_INSTRUMENTED", "Status unknown attributes")
        same(s["new_real_payload_reads"], 0, "No newly authorized payload access")
    case("final_status_boundaries", status)
    manifest = PACKAGE/"manifest.json"
    if manifest.is_file():
        def delivery():
            m = read_json(manifest)
            for item in m["files"]:
                rel = PurePosixPath(item["path"])
                require(not rel.is_absolute() and ".." not in rel.parts, "Bad package member")
                path = PACKAGE.joinpath(*rel.parts)
                require(digest(path) == item["sha256"] and path.stat().st_size==item["bytes"],
                        "Package member identity: "+item["path"])
            return {"manifest_members": len(m["files"])}
        case("delivery_manifest", delivery)
    return {
        "scope":"STATIC_DOCUMENT_AND_CONFIG_ONLY", "checked_at_utc":datetime.now(timezone.utc).isoformat(),
        "baseline_commit": BASELINE, "checks": cases, "pass":sum(v["status"]=="PASS" for v in cases),
        "fail":sum(v["status"]=="FAIL" for v in cases), "negative_config_cases": len(changes),
        "project_imports":0, "model_forwards":0, "optimizer_steps":0, "real_payload_reads":0,
        "confers_execution_authority":False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check-only", action="store_true")
    parser.add_argument("--attempt", default="001")
    args = parser.parse_args()
    if not re.fullmatch("[0-9]{3}", args.attempt):
        parser.error("Attempt must be three digits")
    if args.check_only:
        require((PACKAGE/"manifest.json").is_file(), "Final verification requires the delivery manifest")
    report = run_checks()
    if not args.check_only:
        folder = PACKAGE/"checks"
        folder.mkdir(exist_ok=True)
        path = folder/("static_attempt_"+args.attempt+".json")
        if path.exists():
            raise FileExistsError("Preserve prior attempt; use a new attempt ID")
        path.write_bytes((json.dumps(report,ensure_ascii=False,indent=2)+"\n").encode("utf-8"))
    print(json.dumps(report,ensure_ascii=False))
    return 1 if report["fail"] else 0


if __name__ == "__main__":
    sys.exit(main())
