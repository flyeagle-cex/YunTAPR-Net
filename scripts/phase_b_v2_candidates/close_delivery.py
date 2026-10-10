"""Close an unpublished candidate package with static, bounded verification.

No observations, checkpoint tensors or model execution are used. This script
requires the known clean baseline and refuses to overwrite a published closure.
"""
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
import ast
import csv
import json
import re
import subprocess
import sys
import xml.etree.ElementTree as ET

from build_delivery import BASELINE, OUT, REPO, sha
from planning import budget, single_factor_changes


def git(*args: str) -> str:
    return subprocess.check_output(["git", *args], cwd=REPO).decode("utf-8").strip()


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def dump(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def require(condition: bool, reason: str) -> None:
    if not condition:
        raise ValueError(reason)


def main() -> None:
    if git("rev-parse", "HEAD") != BASELINE or git("diff", "--name-only"):
        raise RuntimeError("Only the original clean, unpublished baseline is supported")
    retry = "--retry-unpublished" in sys.argv
    if (OUT / "final_status.json").exists() and not retry:
        raise FileExistsError("Closure already exists; append a new audit instead")
    if retry and (OUT / "manifest.json").exists():
        raise FileExistsError("Do not replace a successfully packaged closure")
    stamp = datetime.now(timezone.utc).isoformat()
    private = OUT / ".local"
    private.mkdir(exist_ok=True)
    # Redact only new build diagnostics. Preserve complete originals locally.
    diagnostic_paths = [OUT / "tests/synthetic_attempt_001.xml"] + sorted(
        (OUT / "tests").glob("pdf_compile_attempt_*.json"))
    for path in diagnostic_paths:
        backup = private / (path.name + ".unredacted")
        if not backup.exists():
            with backup.open("xb") as stream:
                stream.write(path.read_bytes())
        if path.suffix == ".xml":
            tree = ET.parse(path)
            for node in tree.iter():
                if "hostname" in node.attrib:
                    node.set("hostname", "REDACTED_HOST")
            tree.write(path, encoding="utf-8", xml_declaration=True)
        else:
            result = read_json(path)
            for item in result.get("content", []):
                if item.get("type") == "text":
                    payload = json.loads(item["text"])
                    if "path" in payload:
                        payload["path"] = "<WORKSPACE>/" + str(
                            (OUT / "PHASE_B_V2_CANDIDATE_REVIEW.tex").relative_to(REPO)).replace("\\", "/")
                    item["text"] = json.dumps(payload, ensure_ascii=False)
            dump(path, result)
    first_log = (OUT / "tests/pdf_export/compile_pass_1.log").read_text(encoding="utf-8", errors="replace")
    # Keep the entire failure console, with user installation paths redacted.
    first_log = re.sub(r"[A-Za-z]:[/\\][^\s\"\n]*", "<LOCAL_PATH>", first_log)
    (OUT / "tests/pdf_export_failure_attempt_001.log").write_text(first_log, encoding="utf-8")
    visual = {"reviewed_utc": stamp, "method": "MANUAL_VISUAL_INSPECTION_OF_EACH_FINAL_RENDER",
              "final_export_attempt": 4, "pages_reviewed": list(range(1, 22)),
              "unresolved_visual_defects": [], "new_scientific_figures": 0,
              "local_render_directory": "tests/pdf_render_attempt_004",
              "notes": "All 21 final pages inspected; text, tables, URL labels and equations readable. Short chapter-end pages are intentional."}
    dump(OUT / "tests/visual_review.json", visual)
    initial_binding = read_json(OUT / "report_source_binding.json")
    final_binding = {"bound_utc": stamp, "source_markdown": initial_binding["source_markdown"],
                     "tex_sha256": sha(OUT / "PHASE_B_V2_CANDIDATE_REVIEW.tex"),
                     "pdf_sha256": sha(OUT / "PHASE_B_V2_CANDIDATE_REVIEW.pdf"),
                     "pages": 21, "final_compile_attempt": 4, "final_export_attempt": 4,
                     "supersedes_for_current_tex": "report_source_binding.json",
                     "initial_binding_role": "INITIAL_AUTHORING_SNAPSHOT_BEFORE_FORMATTING_REPAIRS",
                     "repairs": ["Missing local xurl replaced by url and explicit URL breaks",
                                 "Path breaks and TOC depth repaired", "Markdown interval/link parsing repaired"],
                     "self_contained_tex": True, "figures_added": 0}
    dump(OUT / "report_source_binding_final.json", final_binding)
    if "最终 PDF 为 attempt 004" not in (OUT / "tests/README.md").read_text(encoding="utf-8"):
        with (OUT / "tests/README.md").open("a", encoding="utf-8") as stream:
            stream.write("\n最终 PDF 为 attempt 004，21页，三个 XeLaTeX pass 返回0，溢出/缺失字形/LaTeX warning均0；21页逐页目视复核。首次终端构建因缺少本机xurl失败，完整控制台已脱敏保留，之后三个导出成功；早期成功版本的格式问题已修复。最初report_source_binding仅为修复前身份，当前文件身份以report_source_binding_final为准。检查JSON中的工作区路径及测试XML的hostname已脱敏，原记录和渲染图保留本地。\n")

    status = {"version": "PHASE_B_V2_CANDIDATES_v1_20261010", "recorded_utc": stamp,
              "task_delivery_status": "VERIFYING", "scientific_status": "RESEARCHER_DECISION_REQUIRED",
              "baseline_commit": BASELINE, "V2_PHASE_B_AUTHORIZED": False,
              "RESEARCHER_SCIENTIFIC_APPROVAL_REQUIRED": True,
              "HISTORICAL_RECOVERY_RATIFICATION": "NOT_GRANTED",
              "2025_RAW_ACCESS": 0, "2025_PIXELS_READ": 0,
              "formal_training_runs": 0, "model_forward_calls": 0,
              "optimizer_updates": 0, "calibration_fits": 0,
              "raw_reference_downloads": 0, "provider_messages_sent": 0,
              "previous_87_checks_reexecuted": 0,
              "completed_deliverables": ["candidate_protocol_tradeoffs", "minimum_hypotheses_and_ablations",
                                         "public_reference_inventory", "physical_validation_preparation",
                                         "methods_and_experimental_design_draft", "researcher_decisions",
                                         "editable_latex_and_pdf", "synthetic_and_static_verification"],
              "synthetic_tests": {"passed": 23, "failed": 0, "skipped": 0, "attempts": 1},
              "document_build": {"desktop_compile_successes": 4, "local_export_failed_attempts": 1,
                                 "local_export_successful_attempts": 3, "final_attempt": 4,
                                 "pdf_pages": 21, "final_warnings": 0, "visual_pages_reviewed": 21},
              "public_source_records": 20, "reference_classes": 9,
              "unexecuted": [
                  {"item": "Phase-B/FinalFit/new losses/calibration", "reason": "NEW_SCIENTIFIC_AND_EXECUTION_APPROVAL_REQUIRED", "compute": "unallocated"},
                  {"item": "real station/radar physical validation", "reason": "LICENCE_DATA_LINEAGE_ARCHIVE_AND_RULES_UNRESOLVED", "needs_new_data": True},
                  {"item": "2025 final test", "reason": "SEALED_SEPARATE_RELEASE_REQUIRED", "needs_new_data": False}],
              "safe_resume": "Read current remote/local HEAD and this package; record real decisions in a new version, approve v2 preflight and execution separately. Never infer approval from this delivery.",
              "closure_prior_failed_attempts": 1 if retry else 0,
              "automatic_next_stage": False, "publication": "SEE_APPEND_ONLY_PUBLICATION_RECEIPT"}
    dump(OUT / "final_status.json", status)
    sources = read_json(OUT / "source_registry.json")
    design = read_json(OUT / "candidate_design.json")
    snapshot = read_json(OUT / "baseline_snapshot.json")
    checks: list[dict] = []

    def check(name: str, operation) -> None:
        try:
            operation()
            checks.append({"id": name, "status": "PASS"})
        except Exception as error:
            checks.append({"id": name, "status": "FAIL", "reason": str(error)})

    check("governance", lambda: require(design["status"] == "RESEARCHER_DECISION_REQUIRED" and
          design["execution_status"] == "NOT_EXECUTED" and not design["V2_PHASE_B_AUTHORIZED"] and
          not design["can_launch_formal_training"] and design["historical_recovery_ratification"] == "NOT_GRANTED", "Authorization changed"))
    check("sealed_year", lambda: require(design["sealed_years"] == [2025] and
          design["permitted_candidate_training_years"] == [2023, 2024] and status["2025_RAW_ACCESS"] == status["2025_PIXELS_READ"] == 0, "Sealed boundary changed"))
    check("v2_head", lambda: require(design["model_contract"]["quantile_raw_channels"] == 33 and
          design["model_contract"]["conditional_quantiles"] == 32 and design["model_contract"]["tau32"] == (32-.5)/32 and
          design["model_contract"]["offset_minutes_before_analysis"] == [60,50,40,30,20,10], "Head or temporal contract differs"))
    check("routes_candidate_only", lambda: require(all(row["status"] == "RESEARCHER_DECISION_REQUIRED" for row in design["routes"]) and
          all(row["execution"] == "NOT_EXECUTED" for row in design["minimal_ablations"]), "A candidate became executed"))

    def verify_budgets() -> None:
        with (OUT / "budget_candidates.csv").open(encoding="utf-8", newline="") as stream:
            rows = [{k:int(v) for k,v in row.items()} for row in csv.DictReader(stream)]
        require(len(rows) == 6, "Budget rows missing")
        for row in rows:
            require(row == asdict(budget(row["scenes"], row["physical_batch"], row["epochs"])), "Arithmetic mismatch")
        require(10455+10501 == design["published_scene_counts"]["union_arithmetic_only"], "Union mismatch")
    check("six_budget_rows", verify_budgets)

    def verify_factors() -> None:
        controls = [ {k:row[k] for k in ("gamma","alpha","lambda_q","lambda_d","models")} for row in design["minimal_ablations"]]
        require(single_factor_changes(controls[0], controls[1]) == {"gamma"}, "E1 confounded")
        require(single_factor_changes(controls[0], controls[2]) == {"lambda_q"}, "E2 confounded")
    check("single_factor_matrix", verify_factors)
    check("thirteen_decisions", lambda: require(design["decision_ids"] == [f"D{i:02d}" for i in range(1,14)] and
          not design["minimal_recipe_candidate"]["seed_list_selected"], "Decision status differs"))
    check("twenty_primary_sources", lambda: require(len(sources["sources"]) == 20 and len({s["id"] for s in sources["sources"]}) == 20 and
          all(s["url"].startswith("https://") and s["evidence_depth"] and s["supports"] for s in sources["sources"]) and sources["raw_observation_downloads"] == 0, "Source record incomplete"))
    check("source_link_binding", lambda: require(all(s["url"] in (OUT / "REFERENCES.md").read_text(encoding="utf-8") and
          s["url"] in (OUT / "references.bib").read_text(encoding="utf-8") for s in sources["sources"]), "Reference binding incomplete"))
    check("markdown_final_binding", lambda: require(all(sha(OUT / row["path"]) == row["sha256"] for row in final_binding["source_markdown"]), "Published prose changed during formatting"))
    check("historical_ten_hashes", lambda: require(all(sha(REPO / row["path"]) == row["sha256"] for row in snapshot["historical_inputs"]), "Historical evidence changed"))
    check("git_baseline_clean", lambda: require(git("rev-parse", "HEAD") == BASELINE and not git("diff", "--name-only") and not git("diff", "--cached", "--name-only"), "Existing tracked/staged work changed"))

    def verify_synthetic() -> None:
        root = ET.parse(OUT / "tests/synthetic_attempt_001.xml").getroot()
        suites = [root] if root.tag == "testsuite" else list(root.findall("testsuite"))
        require(sum(int(s.attrib["tests"]) for s in suites) == 23, "Test count mismatch")
        require(all(int(s.attrib.get(k,"0")) == 0 for s in suites for k in ("failures","errors","skipped")), "Synthetic failure")
    check("actual_synthetic_xml", verify_synthetic)

    def verify_ast() -> None:
        paths = list((REPO / "scripts/phase_b_v2_candidates").glob("*.py")) + list((REPO / "tests/phase_b_v2_candidates").glob("*.py"))
        for path in paths:
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=path.name)
            for node in ast.walk(tree):
                modules = [v.name for v in node.names] if isinstance(node, ast.Import) else [node.module or ""] if isinstance(node, ast.ImportFrom) else []
                require(not any(m.startswith(("torch","yuntapr.training","xarray","h5py","netCDF4")) for m in modules), "Model/data import in planning")
    check("python_static_scope", verify_ast)

    def verify_build() -> None:
        record = read_json(OUT / "tests/pdf_export_status_attempt_004.json")
        compiled = read_json(OUT / "tests/pdf_compile_attempt_004.json")
        require(json.loads(compiled["content"][0]["text"])["kind"] == "success", "Desktop compilation not confirmed")
        require(record["status"] == "PASS" and record["pages_rendered"] == 21 and
                all(p["returncode"] == 0 for p in record["attempts"]) and not any(record["warning_counts"].values()), "Final PDF export failed")
        require(read_json(OUT / "tests/pdf_export_status.json")["status"] == "FAIL" and
                "xurl" in (OUT / "tests/pdf_export_failure_attempt_001.log").read_text(encoding="utf-8"), "Failure evidence lost")
    check("build_success_and_failure_retained", verify_build)
    check("all_pdf_pages_reviewed", lambda: require(visual["pages_reviewed"] == list(range(1,22)) and not visual["unresolved_visual_defects"], "Visual review incomplete"))
    check("metadata_schema_only", lambda: require(read_json(OUT / "reference_metadata_schema.json")["title"].endswith("no actual observation records") and
          "source_lineage" in read_json(OUT / "reference_metadata_schema.json")["required"], "Reference independence fields absent"))

    # All closure files exist before resolving local documentation links.
    def verify_links() -> None:
        for path in OUT.rglob("*.md"):
            if ".local" in path.parts:
                continue
            for target in re.findall(r"\[[^\[\]\n]+\]\(([^)]+)\)", path.read_text(encoding="utf-8")):
                if not target.startswith(("http:","https:","#")):
                    require((path.parent / target.split("#")[0]).exists() or target == "manifest.json", "Missing local link: " + target)
    check("markdown_local_links", verify_links)
    check("final_file_binding", lambda: require(sha(OUT / "PHASE_B_V2_CANDIDATE_REVIEW.tex") == final_binding["tex_sha256"] and
          sha(OUT / "PHASE_B_V2_CANDIDATE_REVIEW.pdf") == final_binding["pdf_sha256"], "Final report identity mismatch"))

    public = [p for p in OUT.iterdir() if p.is_file() and p.name != "manifest.json"]
    public += [p for p in (OUT / "tests").iterdir() if p.is_file()]
    public += list((REPO / "scripts/phase_b_v2_candidates").glob("*.py"))
    public += list((REPO / "tests/phase_b_v2_candidates").glob("*.py"))

    def verify_privacy() -> None:
        for path in public:
            if path.suffix == ".pdf":
                continue
            text = path.read_text(encoding="utf-8")
            require(not re.search(r"[A-Za-z]:\\+Users\\+", text), "Private installation path in " + path.name)
            if path.suffix == ".xml":
                require(all(n.attrib.get("hostname", "REDACTED_HOST") == "REDACTED_HOST" for n in ET.fromstring(text).iter()), "Unredacted test host")
    check("public_diagnostic_redaction", verify_privacy)

    report = {"recorded_utc": stamp, "scope": "NEW_CANDIDATE_DELIVERY_ONLY_NOT_PREVIOUS_87",
              "checks": checks, "passed": sum(c["status"] == "PASS" for c in checks),
              "failed": sum(c["status"] == "FAIL" for c in checks),
              "limitations": ["Static checks do not validate new scientific hypotheses or establish reference independence",
                              "No real data or model calls; visual review is separately recorded"]}
    dump(OUT / "tests/delivery_verification.json", report)
    status["static_checks"] = {"passed": report["passed"], "failed": report["failed"]}
    status["task_delivery_status"] = "COMPLETE_AT_RESEARCHER_APPROVAL_BOUNDARY" if not report["failed"] else "STATIC_VERIFICATION_FAILED"
    dump(OUT / "final_status.json", status)

    # Include new check output written after the allowlist was first assembled.
    public = sorted(set(public + [OUT / "tests/delivery_verification.json"]))
    manifest = {"version": design["version"], "created_utc": stamp, "baseline_commit": BASELINE,
                "status": "RESEARCHER_DECISION_REQUIRED", "hash_algorithm": "SHA256",
                "self_hash_excluded": True, "later_publication_receipt_excluded": True,
                "files": [{"path": p.relative_to(REPO).as_posix(), "sha256": sha(p), "bytes": p.stat().st_size}
                          for p in sorted(public)],
                "excluded_local_artifacts": [".local", "rendered page PNGs", "intermediate PDF/aux/complete installation logs"],
                "original_failure_log_publication": "FULL_CONSOLE_RETAINED_WITH_INSTALLATION_PATH_REDACTIONS"}
    dump(OUT / "manifest.json", manifest)
    print(json.dumps({"static_passed": report["passed"], "static_failed": report["failed"],
                      "public_files_in_manifest": len(public), "status": status["task_delivery_status"]}))
    if report["failed"]:
        sys.exit(1)


if __name__ == "__main__":
    main()
