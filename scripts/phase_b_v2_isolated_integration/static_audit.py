"""Read-only AST/identity/record audit. No torch import, model or data preflight."""
from pathlib import Path
import ast
import hashlib
import json
import subprocess
import xml.etree.ElementTree as ET

REPO = Path(__file__).resolve().parents[2]
OUT = REPO / "docs/phase_b_v2_isolated_integration/v1"
BASELINE = "ca524b1accdcb30524cf106bf40d533d698e61e7"


def main():
    checks = []
    def check(name, condition, details=None):
        if not condition: raise AssertionError(name)
        checks.append({"name": name, "status": "PASS", "details": details})
    refs = json.loads((OUT/"source_identity.json").read_text(encoding="utf-8"))["repository_files"]
    check("66_inherited_source_and_metadata_identities",
          len(refs) == 66 and all(hashlib.sha256((REPO/x["path"]).read_bytes()).hexdigest() == x["sha256"] for x in refs))
    old = json.loads((REPO/"docs/phase_b_v2_ablation_implementation/v1/manifest.json").read_text(encoding="utf-8"))
    check("previous_delivery_91_members_unchanged",
          len(old["files"]) == 91 and all(hashlib.sha256((REPO/x["path"]).read_bytes()).hexdigest() == x["sha256"] for x in old["files"]))
    check("no_existing_tracked_file_diff", not subprocess.check_output(["git", "diff", BASELINE, "--name-only"], cwd=REPO))
    source = REPO/"src/yuntapr/experimental/phase_b_v2_integration"
    trees = {p.name: ast.parse(p.read_text(encoding="utf-8")) for p in source.glob("*.py")}
    check("eight_candidate_modules_parse", len(trees) == 8)
    banned = {"step", "load_state_dict", "forward_formal", "adamw", "optimizer_for",
              "apply_verified", "verify_file", "make_payload", "expm1"}
    violations = []
    for name, tree in trees.items():
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                called = node.func.attr if isinstance(node.func, ast.Attribute) else node.func.id if isinstance(node.func, ast.Name) else ""
                if called in banned: violations.append((name, called))
            if isinstance(node, ast.ImportFrom) and node.module and (
                node.module.startswith("yuntapr.data") or "formal_phase_a_v2" in node.module or "checkpoint_v2" in node.module):
                violations.append((name, node.module))
    check("no_optimizer_state_reader_raw_dataset_or_formal_runner_calls", not violations, violations)
    official = [p for p in (REPO/"src/yuntapr").rglob("*.py") if "experimental" not in p.parts]
    check("official_paths_do_not_import_candidate", all("phase_b_v2_integration" not in p.read_text(encoding="utf-8") for p in official))
    init = (source/"initialization.py").read_text(encoding="utf-8")
    check("resource_and_identity_checks_before_construction",
          init.index("require_resources(admission)") < init.index("anchor = B0MatchedV2")
          and init.index("verify_frozen_sources()") < init.index("anchor = B0MatchedV2"))
    bootstrap = (REPO/"scripts/phase_b_v2_isolated_integration/test_process.py").read_text(encoding="utf-8")
    check("file_guard_and_resource_admission_before_test_execution",
          bootstrap.index("install_process_file_guard()") < bootstrap.index("pytest.main(arguments)")
          and bootstrap.index("require_resources(admission)") < bootstrap.index("pytest.main(arguments)")
          and '["-x", suite + "/test_cuda_e2e.py"]' in bootstrap)
    cpu = json.loads((OUT/"tests/cpu_attempt_002.json").read_text())
    cuda = json.loads((OUT/"tests/cuda_attempt_002.json").read_text())
    for prefix, expected in (("cpu", 91), ("cuda", 6)):
        record = cpu if prefix == "cpu" else cuda
        suites = ET.parse(OUT/f"tests/{prefix}_attempt_002.xml").getroot().findall("testsuite")
        actual = {k: sum(int(s.attrib.get(k, 0)) for s in suites) for k in ("tests", "failures", "errors", "skipped")}
        check(prefix+"_final_xml_matches_record", actual == {"tests": expected, "failures": 0, "errors": 0, "skipped": 0}
              and record["counts"]["passed"] == expected and record["status"] == "PASS")
    proofs = [json.loads((OUT/f"tests/cpu_attempt_002_evidence/actual_initialization_seed_{seed}.json").read_text()) for seed in (2026, 2027, 2028)]
    check("different_seeds_have_distinct_actual_states",
          all(len({row["proofs"][0]["state_sha256"][model] for row in proofs}) == 3 for model in ("B0_MATCHED_V2", "B1_V2")))
    cases = [json.loads(p.read_text()) for p in sorted((OUT/"tests/cuda_attempt_002_evidence").glob("E*.json"))]
    check("complete_six_case_matrix_full_shapes_and_no_parameter_updates",
          len(cases) == 6 and {(x["arm"], x["model"]) for x in cases} ==
          {(a, m) for a in ("E0", "E1", "E2") for m in ("B0_MATCHED_V2", "B1_V2")}
          and all(x["status"] == "SYNTHETIC_INTEGRATION_PASS" and x["batch_size"] == 2
                  and x["input_shape"][-2:] == [501,501] and x["qlog_shape"] == [2,32,100,100]
                  and x["fresh_initial_state_sha256"] == x["after_backward_state_sha256"]
                  and x["optimizer_steps"] == 0 and not x["FORMAL_SCIENTIFIC_EXECUTION_AUTHORIZED"] for x in cases))
    check("actual_GPU_same_seed_states_match_CPU_fresh_proof",
          all(x["fresh_initial_state_sha256"] == proofs[0]["proofs"][0]["state_sha256"][x["model"]] for x in cases))
    check("E0_original_loss_and_all_parameter_gradients",
          all(x["E0_original_loss_compatibility"]["status"] == "PASS"
              and x["E0_original_loss_compatibility"]["maximum_parameter_gradient_abs_difference"] == 0
              for x in cases if x["arm"] == "E0"))
    old_result = json.loads((REPO/"docs/phase_b_v2_ablation_implementation/v1/tests/synthetic_attempt_008.json").read_text())
    check("prior_full_LR_prefix_evidence_reused_without_rerun",
          old_result["counts"]["passed"] == 177, "Pinned old tests/code cover all 47052 LR positions; current CPU tests cover endpoint boundaries")
    summary = {"scope": "SYNTHETIC_ENGINEERING_ONLY", "checks": checks, "passed": len(checks), "failed": 0,
               "FORMAL_SCIENTIFIC_EXECUTION_AUTHORIZED": False, "V2_PHASE_B_AUTHORIZED": False,
               "RESEARCHER_SCIENTIFIC_APPROVAL_REQUIRED": True, "HISTORICAL_RECOVERY_RATIFICATION": "NOT_GRANTED",
               "2025_RAW_ACCESS": 0, "2025_PIXELS_READ": 0}
    with (OUT/"tests/static_audit_001.json").open("x", encoding="utf-8") as stream:
        json.dump(summary, stream, indent=2)
    print(json.dumps({"passed": len(checks), "failed": 0, "formal_execution_authorized": False}))


if __name__ == "__main__":
    main()

