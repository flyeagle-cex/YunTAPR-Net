"""Close candidate delivery using source bytes and existing tests, never data/model calls.

The visual-review record must come from an actual human/assistant page inspection;
this script validates it, but cannot create visual approval or scientific approval.
All new records are exclusive-create, preserving previous attempts.
"""
from __future__ import annotations
from datetime import datetime, timezone
from pathlib import Path
import ast
import hashlib
import importlib.util
import json
import os
import re
import subprocess
import sys
import xml.etree.ElementTree as ET

REPO = Path(__file__).resolve().parents[2]
OUT = REPO / "docs/phase_b_v2_ablation_implementation/v1"
BASELINE = "c6d938f4afc7780b29caf3ae84cfc2ef8ff70ed9"
FLAGS = {"V2_PHASE_B_AUTHORIZED": False, "RESEARCHER_SCIENTIFIC_APPROVAL_REQUIRED": True,
         "HISTORICAL_RECOVERY_RATIFICATION": "NOT_GRANTED", "2025_RAW_ACCESS": 0, "2025_PIXELS_READ": 0}


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path: str) -> dict:
    return json.loads((OUT / path).read_text(encoding="utf-8"))


def new_json(name: str, value: dict) -> None:
    with (OUT / name).open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2)
        stream.write("\n")


def git(*arguments: str) -> str:
    return subprocess.check_output(["git", *arguments], cwd=REPO).decode("utf-8").strip()


def public_paths() -> list[Path]:
    paths = [p for p in OUT.iterdir() if p.is_file() and p.suffix in {".md", ".json", ".tex", ".pdf"}
             and p.name not in {"manifest.json", "publication_receipt.json"}]
    paths += [p for p in (OUT / "tests").iterdir() if p.is_file() and p.suffix in {".md", ".json", ".log", ".xml"}]
    for directory in ("src/yuntapr/experimental", "tests/phase_b_v2_ablation_implementation",
                      "scripts/phase_b_v2_ablation_implementation"):
        paths += list((REPO / directory).rglob("*.py"))
    return sorted(paths, key=lambda p: p.relative_to(REPO).as_posix())


def verify_xml(name: str, expected: int) -> None:
    record = read("tests/" + name + ".json")
    suites = ET.parse(OUT / "tests" / (name + ".xml")).getroot().findall("testsuite")
    actual = {k: sum(int(s.attrib.get(k, "0")) for s in suites)
              for k in ("tests", "failures", "errors", "skipped")}
    assert actual == {"tests": expected, "failures": 0, "errors": 0, "skipped": 0}, actual
    assert record["status"] == "PASS" and record["counts"]["passed"] == expected
    assert all(record["counts"][k] == actual[k] for k in actual)
    assert record["optimizer_steps"] == record["model_forward"] == record["raw_data_reads"] == 0


def main() -> None:
    from pypdf import PdfReader  # document text only, not observational data
    checks = []

    def checked(name: str, details: object) -> None:
        checks.append({"name": name, "status": "PASS", "details": details})

    assert git("rev-parse", "HEAD") == BASELINE
    assert not git("diff", "--name-only") and not git("diff", "--cached", "--name-only")
    checked("unchanged_tracked_worktree_and_index_at_closure", BASELINE)

    if "--retry-unpublished" in sys.argv:
        assert not (OUT / "manifest.json").exists(), "Published/closed package cannot be retried in place"
        attempt = 1
        while (OUT / f".local/closure_failed_attempt_{attempt:03d}").exists():
            attempt += 1
        backup = OUT / f".local/closure_failed_attempt_{attempt:03d}"
        backup.mkdir(exist_ok=False)
        for name in ("report_source_binding_final.json", "final_status.json"):
            current, target = OUT / name, backup / name
            assert current.resolve().is_relative_to(OUT.resolve())
            assert target.resolve().is_relative_to((OUT / ".local").resolve())
            current.replace(target)  # only our own two verified incomplete closure records

    helper_spec = importlib.util.spec_from_file_location("synthetic_checks", REPO / "scripts/phase_b_v2_ablation_implementation/run_checks.py")
    helper = importlib.util.module_from_spec(helper_spec)
    helper_spec.loader.exec_module(helper)
    for separator in ("/", "\\"):
        fake_path = separator.join(("D:", "Users", "SyntheticResearcher", "dependency.py"))
        assert helper.redact(fake_path) == "<USER_PROFILE>" + separator + "dependency.py"
    assert helper.redact(str(REPO)) == "<WORKSPACE>"
    checked("public_traceback_redaction_regression", "Both path separators and repository path; no tensor/data call")

    identity = read("source_identity.json")
    for item in identity["repository_files"]:
        path = REPO / item["path"]
        assert sha(path) == item["sha256"] and path.stat().st_size == item["bytes"], item["path"]
    for item in identity["frozen_code_locations"]:
        tree = ast.parse((REPO / item["path"]).read_text(encoding="utf-8"))
        assert any(getattr(n, "name", None) == item["symbol"] and n.lineno == item["line"]
                   and n.end_lineno == item["end_line"] for n in ast.walk(tree))
    checked("published_sources_and_frozen_code_locations", {"files": len(identity["repository_files"]),
            "symbols": len(identity["frozen_code_locations"]), "external_mask": "DECLARED_NOT_REOPENED"})

    verify_xml("synthetic_attempt_008", 177)
    verify_xml("cuda_attempt_004", 3)
    static = read("tests/static_attempt_002.json")
    assert static["passed"] == 11 and static["failed"] == 0 and not static["can_launch_formal_training"]
    checked("actual_final_xml_json_and_static_results", {"cpu": 177, "cuda": 3, "static": 11})

    previous = ET.parse(OUT / "tests/synthetic_attempt_007.xml").getroot()
    assert sum(int(s.attrib["failures"]) for s in previous.findall("testsuite")) == 1
    assert read("tests/cuda_attempt_001.json")["status"] == "TIMEOUT"
    assert read("tests/scalar_device_repair.json")["tolerances_changed"] is False
    checked("retained_failures_and_fixed_device_check", "No tolerance or formula change")

    guide = (OUT / "RESEARCHER_CODE_STUDY_GUIDE.md").read_text(encoding="utf-8")
    blocks = re.findall(r"\x60\x60\x60python\n(.*?)\x60\x60\x60", guide, re.S)
    source = REPO / "src/yuntapr/experimental/phase_b_v2_ablations"
    names = ("__init__.py", "config.py", "validation.py", "focal.py", "pinball.py", "total.py", "metrics.py", "readiness.py")
    assert len(blocks) == len(names) == 8
    for name, block in zip(names, blocks):
        assert block == (source / name).read_text(encoding="utf-8"), name
        assert sha(source / name) in guide
    functions = read("candidate_function_index.json")["functions"]
    for item in functions:
        tree = ast.parse((REPO / item["path"]).read_text(encoding="utf-8"))
        assert any(isinstance(n, ast.FunctionDef) and n.name == item["symbol"]
                   and n.lineno == item["line"] and n.end_lineno == item["end_line"] for n in ast.walk(tree))
    checked("exact_eight_source_copies_and_candidate_function_lines", len(functions))

    spec = importlib.util.spec_from_file_location("delivery_author", REPO / "scripts/phase_b_v2_ablation_implementation/author_delivery.py")
    author = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(author)
    tex = OUT / "PHASE_B_V2_IMPLEMENTATION_STUDY.tex"
    text = tex.read_text(encoding="utf-8")
    body = "\n".join(author.with_code_blocks((OUT / name).read_text(encoding="utf-8")) for name in author.DOCS)
    assert text[text.index(r"\clearpage\section{"):text.index(r"\clearpage\section{关键数学")] == body
    checked("current_markdown_tex_body_exact_binding", len(author.DOCS))

    compiler = read("tests/compiler_attempt_004.json")
    assert json.loads(compiler["content"][0]["text"])["kind"] == "success"
    export = read("tests/export_attempt_004.json")
    assert export["status"] == "PASS" and export["pages_rendered"] == 26 and not any(export["warnings"].values())
    pdf = OUT / "PHASE_B_V2_IMPLEMENTATION_STUDY.pdf"
    pages = PdfReader(pdf).pages
    assert len(pages) == 26 and all(len(page.extract_text()) > 30 for page in pages)
    visual = read("tests/visual_review.json")
    assert visual["pdf_sha256"] == sha(pdf) and visual["pages_reviewed"] == list(range(1, 27))
    assert visual["status"] == "PASS" and visual["scientific_approval"] == "NOT_GRANTED"
    checked("compiled_exported_extracted_and_visually_reviewed_pdf", 26)

    for path in public_paths():
        if path.suffix == ".py":
            ast.parse(path.read_text(encoding="utf-8"), filename=path.relative_to(REPO).as_posix())
    checked("new_python_syntax", len([p for p in public_paths() if p.suffix == ".py"]))

    binding = {"role": "FINAL_CURRENT_SOURCE_BINDING",
        "earlier_binding_record_role": "report_source_binding.json preserves initial pre-reflow authoring identities",
        "source_markdown": [{"path": name, "sha256": sha(OUT / name)} for name in author.DOCS],
        "tex": {"path": tex.name, "sha256": sha(tex)}, "pdf": {"path": pdf.name, "sha256": sha(pdf)},
        "candidate_source": [{"path": (source/name).relative_to(REPO).as_posix(), "sha256": sha(source/name)} for name in names]}
    new_json("report_source_binding_final.json", binding)
    status = {"status": "COMPLETE_WITHIN_AUTHORIZED_CANDIDATE_DEVELOPMENT_AND_SYNTHETIC_SCOPE",
        "recorded_utc": datetime.now(timezone.utc).isoformat(), "baseline_commit": BASELINE,
        "scientific_status": "PROPOSED_FOR_RESEARCHER_APPROVAL", "researcher_decision": "RESEARCHER_DECISION_REQUIRED",
        **FLAGS, "current_tests": {"cpu_passed": 177, "cuda_passed": 3, "unique_pytest_instances": 180,
                "failed": 0, "errors": 0, "skipped": 0, "static_passed": 11},
        "historical_attempts_retained": {"assertion_failures": 1, "collection_errors": 1,
                "pytest_dependency_start_failures": 2, "cuda_timeouts": 1},
        "historical_failure_records": ["tests/failure_and_repair_history.json", "tests/scalar_device_repair.json"],
        "historical_history_role": "First history JSON preserves pre-final-refinement 176-test state, not final count",
        "e0_math_and_two_head_gradient_compatibility": "PASS_WITH_DECLARED_TOLERANCES",
        "synthetic_gradcheck_gradgradcheck_analytic_and_finite_difference": "PASS",
        "synthetic_loss_forward_and_autograd": "EXECUTED_NOT_EXACTLY_COUNTED",
        "formal_model_forward": 0, "optimizer_steps": 0, "formal_parameters_updated": 0,
        "raw_2023_2024_files_opened": 0, "private_checkpoint_files_opened": 0,
        "formal_or_historical_tracked_files_modified": 0, "runner_can_launch_formal_training": False,
        "budget_candidate_only": {"runs": 18, "epochs": 9, "updates_per_epoch": 5228,
             "updates_per_run": 47052, "updates_total": 846936, "validation_batches_per_epoch": 1313,
             "validation_batches_total": 212706, "stage1_updates": 282312, "stage2_updates": 564624},
        "learning_order": ["config", "validation", "focal", "pinball", "total", "metrics", "gradient_tests", "readiness"],
        "formal_integration_not_performed": True,
        "remaining_decisions": ["Independent researcher review of candidate loss and controls",
             "Scientific protocol, effect limits, side-effect tolerances and multiplicity approval",
             "Phase-A evidence acceptance scope and separate historical recovery disposition",
             "New independent v2 runner integration approval",
             "Data/compute permission and separately authorized real preflight",
             "Actual fresh tensor/RNG/order identity evidence, not declared SHA metadata",
             "Separate stage-bound execution authorization; LAST-bound independent approval for any recovery"],
        "publication": "Actual evidence commit will be recorded in append-only publication_receipt.json; receipt commit identity is in Git history"}
    new_json("final_status.json", status)

    username, hostname = os.environ.get("USERNAME", ""), os.environ.get("COMPUTERNAME", "")
    for path in public_paths():
        assert path.stat().st_size < 2_000_000, path.name
        assert ".local" not in path.relative_to(OUT if path.is_relative_to(OUT) else REPO).parts
        if path.suffix != ".pdf":
            public = path.read_text(encoding="utf-8")
            assert not re.search(r"[A-Za-z]:[/\\]+Users[/\\]", public), path.relative_to(REPO)
            for private in (username, hostname):
                assert not private or private.lower() not in public.lower(), path.relative_to(REPO)
    extracted = "\n".join(page.extract_text() for page in pages)
    assert not re.search(r"[A-Za-z]:[/\\]+Users[/\\]", extracted)
    for private in (username, hostname):
        assert not private or private.lower() not in extracted.lower()
    checked("narrow_public_file_privacy_and_size_checks", "No user profile, hostname, raw files, private logs or dependencies")
    for path in OUT.glob("*.md"):
        for link in re.findall(r"\]\(([^)]+)\)", path.read_text(encoding="utf-8")):
            if not re.match(r"[A-Za-z][A-Za-z0-9+.-]*:", link) and not link.startswith("#"):
                target = path.parent / link.split("#")[0]
                # The manifest is created only after this final verification.
                assert target.exists() or target.resolve() == (OUT / "manifest.json").resolve(), (path.name, link)
    checked("document_navigation_targets", "All targets exist except this transaction's manifest, which is written and verified below")

    new_json("tests/delivery_verification.json", {"scope": "DOCUMENT_SOURCE_BYTE_AND_RECORD_CLOSURE_ONLY",
        "checks": checks, "passed": len(checks), "failed": 0, **FLAGS,
        "can_launch_formal_training": False})
    paths = public_paths()
    manifest = {"scope": "PUBLIC_CANDIDATE_CODE_SYNTHETIC_EVIDENCE_AND_EDITABLE_TEACHING_DOCUMENTS",
        "baseline_commit": BASELINE, **FLAGS, "manifest_self_excluded": True,
        "later_publication_receipt_excluded_by_design": True,
        "files": [{"path": p.relative_to(REPO).as_posix(), "sha256": sha(p), "bytes": p.stat().st_size} for p in paths]}
    new_json("manifest.json", manifest)
    assert all(sha(REPO / item["path"]) == item["sha256"] for item in manifest["files"])
    print(json.dumps({"closure_checks_passed": len(checks), "public_files": len(paths),
        "manifest_sha256": sha(OUT/"manifest.json"), "formal_training": False}))


if __name__ == "__main__":
    main()
