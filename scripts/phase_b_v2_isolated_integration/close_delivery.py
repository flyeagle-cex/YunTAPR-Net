"""Append-only document and provenance closure; no torch import or model execution.

Run before publication. Visual review is a separate, actually performed event;
this script verifies its binding, never produces scientific approval.
"""
from __future__ import annotations
import ast
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import subprocess
import xml.etree.ElementTree as ET

REPO = Path(__file__).resolve().parents[2]
OUT = REPO / "docs/phase_b_v2_isolated_integration/v1"
BASELINE = "ca524b1accdcb30524cf106bf40d533d698e61e7"
FLAGS = {"V2_PHASE_B_AUTHORIZED": False, "FORMAL_SCIENTIFIC_EXECUTION_AUTHORIZED": False,
         "RESEARCHER_SCIENTIFIC_APPROVAL_REQUIRED": True,
         "HISTORICAL_RECOVERY_RATIFICATION": "NOT_GRANTED", "2025_RAW_ACCESS": 0, "2025_PIXELS_READ": 0}
SOURCE_DIRS = ("src/yuntapr/experimental/phase_b_v2_integration",
               "tests/phase_b_v2_isolated_integration", "scripts/phase_b_v2_isolated_integration")


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(name: str) -> dict:
    return json.loads((OUT/name).read_text(encoding="utf-8"))


def new_json(name: str, value: dict) -> None:
    with (OUT/name).open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2)
        stream.write("\n")


def git(*args: str) -> str:
    return subprocess.check_output(["git", *args], cwd=REPO).decode("utf-8").strip()


def public_paths() -> list[Path]:
    paths = [p for p in OUT.iterdir() if p.is_file() and p.suffix in {".md", ".json", ".tex", ".pdf"}
             and p.name not in {"manifest.json", "publication_receipt.json"}]
    paths += [p for p in (OUT/"tests").iterdir() if p.is_file() and p.suffix in {".md", ".json", ".log", ".xml"}]
    paths += list((OUT/"tests").glob("*_evidence/*.json"))
    for directory in SOURCE_DIRS:
        paths += list((REPO/directory).glob("*.py"))
    return sorted(paths, key=lambda p: p.relative_to(REPO).as_posix())


def main() -> None:
    from pypdf import PdfReader
    checks = []
    def checked(name: str, condition: bool, details=None) -> None:
        if not condition:
            raise AssertionError(name)
        checks.append({"name": name, "status": "PASS", "details": details})
    checked("prepublication_baseline_and_clean_tracked_index",
            git("rev-parse", "HEAD") == BASELINE and not git("diff", "--name-only")
            and not git("diff", "--cached", "--name-only"))
    refs = read("source_identity.json")["repository_files"]
    checked("66_inherited_public_source_bytes_unchanged",
            len(refs) == 66 and all(sha(REPO/x["path"]) == x["sha256"] for x in refs))
    previous = json.loads((REPO/"docs/phase_b_v2_ablation_implementation/v1/manifest.json").read_text(encoding="utf-8"))
    checked("91_previous_delivery_members_unchanged",
            len(previous["files"]) == 91 and all(sha(REPO/x["path"]) == x["sha256"] for x in previous["files"]))
    pyfiles = [p for directory in SOURCE_DIRS for p in (REPO/directory).glob("*.py")]
    trees = {p: ast.parse(p.read_text(encoding="utf-8")) for p in pyfiles}
    checked("all_new_python_parses", len(trees) == 18, {"modules": 8, "test_files": 4, "scripts": 6})
    symbols = read("candidate_symbol_index.json")["symbols"]
    for item in symbols:
        path = REPO/item["path"]
        nodes = [n for n in ast.walk(trees[path]) if isinstance(n, (ast.FunctionDef, ast.ClassDef))
                 and n.name == item["symbol"] and n.lineno == item["line"] and n.end_lineno == item["end_line"]]
        assert nodes and sha(path) == item["sha256"], item
    checked("actual_symbol_lines_and_source_hashes", len(symbols) == 26)
    guide = (OUT/"MODULE_STUDY_GUIDE.md").read_text(encoding="utf-8")
    for file, function in (("adapter.py", "forward_synthetic"),
                           ("initialization.py", "fresh_paired_models"), ("controls.py", "reject_resume")):
        path = REPO/SOURCE_DIRS[0]/file
        node = next(n for n in ast.walk(trees[path]) if isinstance(n, ast.FunctionDef) and n.name == function)
        excerpt = "\n".join(path.read_text(encoding="utf-8").splitlines()[node.lineno-1:node.end_lineno])
        assert excerpt in guide
    checked("three_complete_code_excerpts_match_actual_source", True)
    binding = read("report_source_binding.json")
    checked("markdown_and_latex_binding",
            all(sha(OUT/x["path"]) == x["sha256"] for x in binding["source_markdown"])
            and sha(OUT/"ISOLATED_INTEGRATION_REVIEW.tex") == binding["tex_sha256"]
            and all(sha(REPO/x["path"]) == x["sha256"] for x in binding["candidate_modules"]))
    spec = importlib.util.spec_from_file_location("old_author", REPO/"scripts/phase_b_v2_ablation_implementation/author_delivery.py")
    author = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(author)
    body = "\n".join(author.with_code_blocks((OUT/x["path"]).read_text(encoding="utf-8"))
                     for x in binding["source_markdown"])
    checked("all_nine_markdown_bodies_embedded_in_editable_tex",
            body in (OUT/"ISOLATED_INTEGRATION_REVIEW.tex").read_text(encoding="utf-8"))
    for prefix, count in (("cpu", 91), ("cuda", 6)):
        record = read(f"tests/{prefix}_attempt_002.json")
        suites = ET.parse(OUT/f"tests/{prefix}_attempt_002.xml").getroot().findall("testsuite")
        actual = {k: sum(int(s.attrib.get(k, 0)) for s in suites) for k in ("tests", "failures", "errors", "skipped")}
        checked(prefix+"_final_records_match", actual == {"tests": count, "failures": 0, "errors": 0, "skipped": 0}
                and record["counts"]["passed"] == count and record["status"] == "PASS"
                and record["optimizer_steps"] == record["actual_observational_data_reads"] == record["private_checkpoint_reads"] == 0
                and "warnings summary" not in (OUT/f"tests/{prefix}_attempt_002.log").read_text(encoding="utf-8").lower())
    checked("failure_and_repair_records_retained",
            read("tests/cpu_attempt_001.json")["counts"]["failures"] == 4
            and read("tests/cuda_attempt_001.json")["counts"]["passed"] == 6
            and (OUT/"tests/repair_001.json").exists() and (OUT/"tests/repair_002.json").exists())
    for xml in (OUT/"tests").glob("*.xml"):
        ET.parse(xml)
    checked("all_new_xml_roundtrip_parse", True)
    checked("static_audit_15_pass", read("tests/static_audit_001.json")["passed"] == 15
            and read("tests/static_audit_001.json")["failed"] == 0)
    cases = [json.loads(p.read_text(encoding="utf-8")) for p in sorted((OUT/"tests/cuda_attempt_002_evidence").glob("E*.json"))]
    checked("collated_synthetic_results_equal_original_records", cases == read("SYNTHETIC_NUMERICAL_RESULTS.json")["cases"])
    checked("six_full_models_unchanged_after_backward", len(cases) == 6 and all(
        x["fresh_initial_state_sha256"] == x["after_backward_state_sha256"]
        and not x["FORMAL_SCIENTIFIC_EXECUTION_AUTHORIZED"] and x["optimizer_steps"] == 0 for x in cases))
    pdf = OUT/"ISOLATED_INTEGRATION_REVIEW.pdf"
    pages = PdfReader(pdf).pages
    review = read("tests/pdf_visual_review_001.json")
    export = read("tests/export_attempt_001.json")
    checked("compiled_pdf_text_and_actual_visual_review",
            len(pages) == 14 and all(len(p.extract_text().strip()) > 100 for p in pages)
            and review["pdf_sha256"] == sha(pdf) and review["pages_inspected"] == list(range(1, 15))
            and review["status"] == "PASS" and export["status"] == "PASS"
            and not any(export["warnings"].values()))
    pending = {(OUT/name).resolve() for name in ("final_status.json", "manifest.json")}
    for md in OUT.rglob("*.md"):
        if ".local" in md.parts:
            continue
        for link in re.findall(r"\[[^\]]*\]\(([^)]+)\)", md.read_text(encoding="utf-8")):
            if "://" not in link and not link.startswith("#"):
                target = (md.parent/link.split("#")[0]).resolve()
                assert target.exists() or target in pending, (md.name, link)
    checked("markdown_local_links_resolve_or_exact_pending_closure", True)
    # Look only at the explicit new publication scope; never scan unrelated raw data.
    for path in public_paths():
        content = "\n".join(p.extract_text() for p in pages) if path.suffix == ".pdf" else path.read_text(encoding="utf-8")
        assert not re.search(r"[A-Za-z]:[/\\]Users[/\\][^/\\\s]+", content, re.I), path
        assert Path.home().name.lower() not in content.lower(), path
    checked("public_scope_profile_path_scan", True)
    new_json("tests/closure_audit_001.json", {"scope": "SYNTHETIC_ENGINEERING_ONLY", "checks": checks,
             "passed": len(checks), "failed": 0, "pdf_sha256": sha(pdf), **FLAGS})
    new_json("final_status.json", {
        "status": "COMPLETE_WITHIN_ALLOWED_SYNTHETIC_SCOPE", "scope": "SYNTHETIC_ENGINEERING_ONLY",
        "integration_status": "SYNTHETIC_INTEGRATION_PASS", "baseline_commit": BASELINE,
        "current_tests": {"CPU": 91, "CUDA": 6, "unique_total": 97, "failures": 0, "errors": 0,
                          "skipped": 0, "warnings": 0, "static_checks": 15, "closure_checks": len(checks)},
        "retained_attempt_history": {"pytest_instances": 194, "initial_CPU_failures_fixed": 4,
                                    "initial_CUDA_logging_warning_fixed": 1, "previous_XML_not_modified": True},
        "full_model_execution": {"final_forwards": 6, "final_backwards": 8, "cumulative_forwards": 12,
                                "cumulative_backwards": 16, "batch_size": 2, "input_grid": [501,501],
                                "precision": ["BF16","FP32","FP64"], "OOM": False, "fallback": False},
        "initialization": {"CPU_seeds": [2026,2027,2028], "arms": ["E0","E1","E2"], "fresh_instances_total": 42},
        "E0_compatibility": {x["model"]: x["E0_original_loss_compatibility"] for x in cases if x["arm"] == "E0"},
        "optimizer_steps": 0, "actual_observational_data_reads": 0, "private_checkpoint_reads": 0,
        "source_integrity": {"inherited_pins": 66, "previous_manifest_members": 91, "historical_changes": 0},
        "not_executed": ["CPU full-backbone forward/backward (CUDA selected before admission)",
                         "true tail batch1 and validation batch8/tail5", "real mask/scaler/data preflight",
                         "optimizer or checkpoint transactions", "formal runner and scientific experiments"],
        "remaining_work_requires_independent_authorization": ["researcher source and scientific protocol review",
            "effect limits and multiplicity decisions", "new v2 runner integration",
            "real 2023/2024 data and resource preflight", "stage-specific execution and LAST-bound resume approval"],
        "publication_identity": "publication_receipt.json and Git history; no self-referential commit claim",
        "pdf_pages": 14, "pdf_sha256": sha(pdf), **FLAGS})
    files = public_paths()
    assert all(p.resolve().is_relative_to(REPO.resolve()) and ".local" not in p.parts for p in files)
    new_json("manifest.json", {"schema": "isolated-integration-publication-v1",
        "scope": "SYNTHETIC_ENGINEERING_ONLY", "baseline_commit": BASELINE,
        "files": [{"path": p.relative_to(REPO).as_posix(), "sha256": sha(p), "bytes": p.stat().st_size} for p in files],
        "excluded": ["manifest.json (self hash)", "publication_receipt.json (append-only post-publication)",
                     ".local private logs/renders/dependencies", "all historical untracked files"],
        "formal_authorization_granted": False})
    for name in ("final_status.json", "manifest.json"):
        assert (OUT/name).exists()
    print(json.dumps({"closure_passed": len(checks), "failed": 0, "manifest_members": len(files),
                      "public_bytes": sum(p.stat().st_size for p in files)}))


if __name__ == "__main__":
    main()
