"""Check public proposal artifacts without reading observations or model state.

This closes an unpublished evidence package, never issues an authorization.
Inputs are repository source, published metadata, reports and test records only.
"""
from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
import ast
import csv
import hashlib
import json
import re
import shutil
import subprocess
import sys
import traceback
import xml.etree.ElementTree as ET

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "scripts/phase_b_v2_candidates"))
from scripts.phase_b_v2_preregistration.review import load_json, review_protocol, static_identity_inputs
from scripts.phase_b_v2_preregistration.budgets import run_rows, summary
from scripts.phase_b_v2_candidates.build_delivery import markdown_tex
from pypdf import PdfReader

OUT = REPO / "docs/phase_b_v2_ablation_preregistration/v1"
BASELINE = "8fbc06ba341aeee43136c18f20ebd6acd3463efd"
DOCS = ["SCIENTIFIC_OBJECTIVES.md", "FROZEN_EXPERIMENT_MATRIX_CANDIDATE.md",
        "CONTROLLED_VARIABLE_MATRIX.md", "LOSS_MATHEMATICS_AND_RESEARCHER_EXERCISE.md",
        "METRICS_AND_GUARDRAILS.md", "STATISTICAL_ANALYSIS_PLAN.md", "COMPUTE_AND_STORAGE_BUDGET.md",
        "RESEARCHER_APPROVAL_CHECKLIST.md", "SAFE_IMPLEMENTATION_HANDOFF.md", "TEST_PLAN.md",
        "RESEARCHER_DECISION_REQUIRED.md", "STATIC_CODE_REVIEW.md"]
PROTECTED = ["src", "config", "docs/v2_scientific_acceptance", "docs/phase_a_evidence_hardening",
             "docs/phase_b_v2_protocol_candidates", "docs/b1_scientific_freeze"]


def git(*args: str) -> str:
    return subprocess.check_output(["git", *args], cwd=REPO).decode("utf-8").strip()


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_record(path: Path, value: object) -> None:
    """Append records only; do not replace an earlier delivery attempt."""
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        stream.write(json.dumps(value, ensure_ascii=False, indent=2) + "\n")


def public_files() -> list[Path]:
    """Narrow file allowlist; no recursive inclusion of .local or other work."""
    return sorted([p for p in OUT.iterdir() if p.is_file() and p.name not in
                   {"manifest.json", "publication_receipt.json"}]
                  + [p for p in (OUT / "tests").iterdir() if p.is_file()]
                  + list((REPO / "scripts/phase_b_v2_preregistration").glob("*.py"))
                  + list((REPO / "tests/phase_b_v2_preregistration").glob("*.py")))


def main() -> None:
    checks = []

    def check(name: str, success: bool, detail: object = None) -> None:
        checks.append({"name": name, "status": "PASS" if success else "FAIL", "detail": detail})
        if not success:
            raise ValueError("Delivery check failed: " + name)

    check("baseline_head", git("rev-parse", "HEAD") == BASELINE)
    check("tracked_work_and_index_clean_before_staging",
          not git("diff", "--name-only") and not git("diff", "--cached", "--name-only"))
    check("protected_history_unmodified", not git("diff", BASELINE, "--name-only", "--", *PROTECTED))
    check("required_documents_present", all((OUT / p).is_file() for p in DOCS + ["README.md"]))

    identity, observed = static_identity_inputs()
    check("source_41_byte_identities", len(observed) == 41 and
          all(observed[r["path"]] == r["sha256"] for r in identity["repository_files"]))
    locations = []
    for ref in identity["repository_files"]:
        if ref["path"].startswith("src/") and ref["path"].endswith(".py"):
            tree = ast.parse((REPO / ref["path"]).read_text(encoding="utf-8"))
            for node in tree.body:
                if isinstance(node, (ast.FunctionDef, ast.ClassDef)):
                    locations.append({"path": ref["path"], "symbol": node.name,
                                      "line": node.lineno, "end_line": node.end_lineno})
    check("source_function_locations", locations == identity["code_locations"])
    check("external_mask_declared_not_reopened", identity["external_pins"][0]["status"] ==
          "DECLARED_PIN_NOT_REOPENED" and identity["raw_files_opened"] ==
          identity["checkpoint_files_opened"] == identity["sample_manifest_rows_parsed"] == 0)
    proposal, schema = load_json(OUT / "protocol_proposed.json"), load_json(OUT / "protocol_schema.json")
    result = review_protocol(proposal, schema, identity_sha=sha(OUT / "source_identity.json"),
                             expected_refs=identity["repository_files"], observed_hashes=observed)
    check("closed_schema_and_static_review", result.candidate_valid and not result.errors)
    check("training_launch_always_blocked", not result.can_launch_formal_training and
          not result.runner_implemented and len(result.blockers) == 6)
    check("no_generated_approvals", all(v is None for v in proposal["approvals"].values()) and
          all(s["execution_authorization"] is None for s in proposal["stages"]))
    flags = proposal["governance"]
    check("governance_boundary", flags == {"RESEARCHER_SCIENTIFIC_APPROVAL_REQUIRED": True,
          "V2_PHASE_B_AUTHORIZED": False, "2025_RAW_ACCESS": 0, "2025_PIXELS_READ": 0,
          "HISTORICAL_RECOVERY_RATIFICATION": "NOT_GRANTED", "can_launch_formal_training": False})
    check("unestablished_fields_remain_null", all(d == {"status": "NOT_YET_ESTABLISHED", "value": None}
                                                for d in proposal["decision_fields"].values()))
    controls = proposal["controls"]
    frozen = load_json(REPO / "config/science_v2/phase_a_protocol_frozen_v1.json")
    check("frozen_optimizer_gradient_precision_loader_scheduler", all(controls[key] == frozen[key]
          for key in ("optimizer", "gradient", "precision", "loader", "scheduler")))
    check("frozen_scaler_no_refit", controls["normalizer"]["sha256"] == frozen["normalization_sha256"]
          and not controls["normalizer"]["refit"])
    check("frozen_v2_shape_threshold_tau_eps", controls["head"]["quantile_raw_channels"] == 33 and
          controls["head"]["quantiles"] == 32 and controls["head"]["tau32"] == .984375 and
          controls["head"]["epsilon_w"] == controls["head"]["epsilon_span"] == 1e-4 and
          controls["target"]["rain_label"] == "float32_y>float32(0.1)_BEFORE_PROMOTION")
    check("only_two_single_factors", proposal["arms"] == [
          {"id": "E0", "alpha": .5, "gamma": 2, "lambda_q": 1},
          {"id": "E1", "alpha": .5, "gamma": 0, "lambda_q": 1},
          {"id": "E2", "alpha": .5, "gamma": 2, "lambda_q": 2}])
    expected_rows = run_rows()
    check("matrix_18_unique_runs", proposal["runs"] == [{k: r[k] for k in
          ("run_id", "arm", "model", "seed", "stage")} for r in expected_rows] and
          len({r["run_id"] for r in expected_rows}) == 18)
    with (OUT / "run_budget.csv").open(encoding="utf-8", newline="") as stream:
        csv_rows = list(csv.DictReader(stream))
    check("budget_csv_exact_integer_rows", csv_rows == [{k: str(v) for k, v in r.items()} for r in expected_rows])
    totals = summary()
    check("budget_json_exact_recalculation", totals == load_json(OUT / "budget_summary.json"))
    check("fixed_epoch_9_every_epoch_validation", totals["total_train_updates"] == 846936 and
          totals["total_validation_batches"] == 212706 and
          controls["validation_cadence"] == "EVERY_COMPLETED_TRAIN_EPOCH" and
          controls["endpoint_epoch"] == 9 and not controls["training"]["performance_early_stop"])

    new_sources = list((REPO / "scripts/phase_b_v2_preregistration").glob("*.py")) + \
                  list((REPO / "tests/phase_b_v2_preregistration").glob("*.py"))
    imports, prohibited_calls = [], []
    for path in new_sources:
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imports.extend(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                imports.append(node.module or "")
            elif isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                if node.func.attr in {"forward", "backward", "step", "load_state_dict"}:
                    prohibited_calls.append(node.func.attr)
    check("new_sources_ast_no_model_import_or_execution", not prohibited_calls and
          not any(m.startswith(("torch", "yuntapr", "netCDF4", "xarray", "h5py")) for m in imports),
          {"python_files": len(new_sources), "inspection": "AST only; not an execution trace"})

    for attempt in (1, 2):
        path = OUT / f"tests/synthetic_attempt_{attempt:03d}.xml"
        backup = OUT / f".local/synthetic_attempt_{attempt:03d}.unredacted.xml"
        if backup.exists():
            raise FileExistsError("Prior privacy preparation already exists")
        shutil.copyfile(path, backup)
        tree = ET.parse(path)
        for node in tree.iter():
            if "hostname" in node.attrib:
                node.attrib["hostname"] = "REDACTED_HOST"
        tree.write(path, encoding="utf-8", xml_declaration=True)
    suites = list(ET.parse(OUT / "tests/synthetic_attempt_002.xml").getroot().iter("testsuite"))
    check("current_synthetic_tests_actual_64_pass", len(suites) == 1 and suites[0].get("tests") == "64"
          and all(suites[0].get(k) == "0" for k in ("errors", "failures", "skipped")))
    check("first_failure_and_fix_preserved", load_json(OUT / "tests/static_review_attempt_001.json")["status"] ==
          "FAIL_CLOSED" and (OUT / "tests/static_review_failure_attempt_001.log").stat().st_size > 100)

    compiled = load_json(OUT / "tests/compiler_attempt_003.json")
    exported = load_json(OUT / "tests/export_attempt_003.json")
    check("final_latex_compilation_and_export", json.loads(compiled["content"][0]["text"])["kind"] == "success"
          and exported["status"] == "PASS" and all(p["returncode"] == 0 for p in exported["passes"])
          and not any(exported["warnings"].values()))
    pdf = OUT / "PHASE_B_V2_ABLATION_REVIEW.pdf"
    reader = PdfReader(pdf)
    page_texts = [p.extract_text() for p in reader.pages]
    check("pdf_22_pages_rendered_with_text", len(reader.pages) == exported["pages_rendered"] == 22
          and all(len(t) > 100 for t in page_texts)
          and len(list((OUT / ".local/render_003").glob("page-*.png"))) == 22)
    tex = OUT / "PHASE_B_V2_ABLATION_REVIEW.tex"
    body = "\n".join(markdown_tex((OUT / p).read_text(encoding="utf-8")) for p in DOCS)
    check("editable_report_binds_final_markdown", body in tex.read_text(encoding="utf-8"))
    private_identity_pattern = re.compile(r"(?:[A-Za-z]:[/\\]Users[/\\][^/\\\s]+|LAPTOP-[A-Z0-9]{8})", re.I)
    check("pdf_metadata_has_no_local_identity", private_identity_pattern.search(str(reader.metadata)) is None)
    pending_links = {OUT / p for p in ("manifest.json", "final_status.json", "publication_receipt.json")}
    missing = []
    for path in [OUT / "README.md"] + [OUT / p for p in DOCS] + [OUT / "tests/README.md"]:
        for target in re.findall(r"\[[^\]]+\]\(([^)]+)\)", path.read_text(encoding="utf-8")):
            if target.startswith(("http:", "https:", "#")):
                continue
            linked = (path.parent / target.split("#")[0]).resolve()
            if not linked.exists() and linked not in pending_links:
                missing.append({"document": path.relative_to(REPO).as_posix(), "target": target})
    check("document_local_links_except_declared_closeout", not missing)
    allowed_extensions = {".md", ".tex", ".pdf", ".json", ".csv", ".xml", ".log", ".py"}
    check("public_allowlist_excludes_private_artifacts", all(p.suffix in allowed_extensions and
          ".local" not in p.parts and p.stat().st_size < 2000000 for p in public_files()))
    privacy = []
    for path in public_files():
        if path.suffix != ".pdf":
            text = path.read_text(encoding="utf-8")
            if private_identity_pattern.search(text):
                privacy.append(path.relative_to(REPO).as_posix())
    check("public_text_paths_and_hostnames_redacted", not privacy)

    write_record(OUT / "tests/static_review_attempt_002.json", {**asdict(result),
          "source_files_verified": len(observed), "current_synthetic_passed": 64, "current_synthetic_failed": 0,
          "scope": "STATIC_SOURCE_METADATA_AND_PROPOSAL_REVIEW_ONLY"})
    write_record(OUT / "tests/visual_review.json", {"status": "PASS", "final_export_attempt": 3,
          "pages_reviewed": list(range(1, 23)), "method": "Manual inspection of final rendered page PNGs",
          "unresolved_layout_defects": 0, "new_scientific_figures_created": 0,
          "initial_defects_and_repairs": ["report_format_repair.json", "report_toc_repair.json"]})
    write_record(OUT / "report_source_binding_final.json", {"source_markdown": [
          {"path": p, "sha256": sha(OUT / p)} for p in DOCS], "tex_sha256": sha(tex),
          "pdf_sha256": sha(pdf), "pdf_pages": 22, "final_export_attempt": 3, "self_contained": True,
          "initial_binding_role": "report_source_binding.json preserves pre-formatting authoring identity"})
    check("current_final_binding_and_review_records_exist", all((OUT / p).is_file() for p in
          ("tests/static_review_attempt_002.json", "tests/visual_review.json", "report_source_binding_final.json")))
    check("no_formal_runner_artifact", not proposal["runner_implemented"] and
          all(p.name not in {"runner.py", "train.py", "launch.py"} for p in new_sources))
    verification = {"status": "PASS", "checks_passed": len(checks), "checks_failed": 0, "checks": checks,
          "scope": "NEW_DELIVERY_ONLY_NOT_REEXECUTION_OF_PRIOR_87_CHECKS",
          "source_baseline": BASELINE, "can_launch_formal_training": False}
    write_record(OUT / "tests/delivery_verification.json", verification)
    status = {"delivery_status": "COMPLETE_WITHIN_AUTHORIZED_ENGINEERING_SCOPE_AT_APPROVAL_BOUNDARY",
          "protocol_status": proposal["status"], "decision_status": "RESEARCHER_DECISION_REQUIRED",
          "formal_experiments": "NOT_EXECUTED", "baseline_commit": BASELINE,
          "publication_identity": "Appended publication_receipt.json after actual commit and remote verification",
          "governance": flags, "synthetic_tests": {"passed": 64, "failed": 0, "skipped": 0,
              "previous_attempt": {"passed": 62, "failed": 0}, "not_additive_unique_total": 64},
          "static_delivery_checks": {"passed": len(checks), "failed": 0},
          "retained_review_failure_attempts": 1,
          "retained_delivery_import_failure_attempts": 1,
          "delivery_import_repair": "Add the existing helper directory for its legacy absolute planning import; no historical code modified",
          "failure_repair": "Exact two published helper paths added to source allowlist; two tests added",
          "environment_probe_failures": "See tests/environment_preparation.json; not scientific test failures",
          "report": {"pages": 22, "final_compile_success": True, "final_layout_warnings": 0,
                     "all_pages_manually_reviewed": True, "pdf_sha256": sha(pdf), "tex_sha256": sha(tex)},
          "matrix": {"arms": 3, "models": 2, "seeds": [2026, 2027, 2028], "runs": 18,
                     "updates_per_run": 47052, "updates_total": 846936, "validation_batches_total": 212706},
          "source_files_verified": 41, "previous_87_checks_reexecuted": 0,
          "activity_counters": {"formal_training_runs": 0, "model_forward": 0, "backward": 0,
              "optimizer_steps": 0, "new_validation_inference": 0, "raw_preflight": 0,
              "raw_files_opened": 0, "checkpoint_files_opened": 0, "sealed_2025_raw_access": 0,
              "sealed_2025_pixels_read": 0, "new_approval_records": 0},
          "protected_files_modified": [], "not_executed": [
              {"item": "Researcher minimal PyTorch loss implementation and code review",
               "reason": "Researcher-led learning and independent implementation required"},
              {"item": "Loss numerical, gradient, model and restore fixture tests",
               "reason": "Require researcher implementation, review and explicit integration/test scope permission"},
              {"item": "Real 2023/2024 data preflight, initial states, GPU time and checkpoint measurements",
               "reason": "Require new approved engineering/execution scope, data permissions and compute resources"},
              {"item": "Phase-B/FinalFit training and fresh inference",
               "reason": "Independent science approval and separately bound execution authorization absent"},
              {"item": "Scientific pass/fail or power claim",
               "reason": "Effect bounds, tolerances, multiplicity and effective sample size not established"},
              {"item": "Phase-A acceptance or historical B1 recovery ratification",
               "reason": "Independent researcher decision remains pending"}],
          "safe_next_step": "Review protocol and unresolved fields; researcher independently implements minimal losses; do not launch training"}
    write_record(OUT / "final_status.json", status)
    files = public_files()
    manifest = {"version": "PHASE_B_V2_ABLATION_PREREGISTRATION_DELIVERY_v1",
          "recorded_utc": datetime.now(timezone.utc).isoformat(), "baseline_commit": BASELINE,
          "status": "PROPOSED_FOR_RESEARCHER_APPROVAL", "authorization_scope": "DOCUMENT_AND_STATIC_SYNTHETIC_REVIEW_ONLY",
          "manifest_self_hash": "Recorded in appended publication_receipt.json; no self-referential hash",
          "excluded": [".local", "__pycache__", "raw data", "model state", "publication_receipt.json"],
          "files": [{"path": p.relative_to(REPO).as_posix(), "bytes": p.stat().st_size,
                     "sha256": sha(p)} for p in files]}
    write_record(OUT / "manifest.json", manifest)
    print(json.dumps({"status": status["delivery_status"], "synthetic_passed": 64,
          "delivery_checks_passed": len(checks), "manifest_files": len(files), "can_launch_formal_training": False}))


if __name__ == "__main__":
    try:
        main()
    except Exception:
        error = traceback.format_exc().replace(str(REPO), "<WORKSPACE>").replace(REPO.as_posix(), "<WORKSPACE>")
        path = OUT / "tests/delivery_failure_attempt_001.log"
        if not path.exists():
            with path.open("x", encoding="utf-8") as stream:
                stream.write(error)
        raise
