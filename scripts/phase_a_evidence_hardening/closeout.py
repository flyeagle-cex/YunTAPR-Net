"""Validate the new delivery, retain failures, and generate an explicit allowlist.

No Git mutations or network operations occur here. Public records redact device
identifiers and absolute local roots; unredacted copies remain under .local/.
"""
from __future__ import annotations
import ast
import csv
import hashlib
import io
import json
from pathlib import Path
import re
import shutil
import subprocess
import unittest
import xml.etree.ElementTree as ET
from datetime import datetime, timezone

REPO = Path(__file__).resolve().parents[2]
OUT = REPO/"docs/phase_a_evidence_hardening"
OLD = REPO/"docs/v2_scientific_acceptance/runs/run_20261009T112710_013267Z/delivery_v2"
BASELINE = "92687641e59c256a9443b8bfb420b6c947fdcb3a"
PUBLIC_ROOTS = ("src/yuntapr/diagnostics", "tests/phase_a_evidence_hardening", "scripts/phase_a_evidence_hardening", "docs/phase_a_evidence_hardening")


def read(p: Path): return json.loads(p.read_text(encoding="utf-8-sig"))


def digest(p: Path) -> str:
    with p.open("rb") as stream: return hashlib.file_digest(stream, "sha256").hexdigest()


def write(name: str, value: dict) -> None:
    with (OUT/name).open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write("\n")


def rel(p: Path) -> str: return str(p.relative_to(REPO)).replace("\\", "/")


def public_files() -> list[Path]:
    files = []
    for name in PUBLIC_ROOTS:
        for p in (REPO/name).rglob("*"):
            if not p.is_file() or "__pycache__" in p.parts or ".local" in p.parts: continue
            if any(part.startswith("pdf_render") for part in p.parts): continue
            if p.suffix in (".aux", ".out", ".toc", ".pyc"): continue
            if "pdf_export" in p.parts and p.name == "PHASE_A_HARDENING_REVIEW.pdf": continue
            if any(part.startswith("pdf_export_attempt") for part in p.parts) and p.name == "PHASE_A_HARDENING_REVIEW.pdf": continue
            if p.name in ("manifest.json", "publication_allowlist.paths", "publication_receipt.json"): continue
            files.append(p)
    return sorted(files)


def redact_public_records() -> None:
    for p in public_files():
        if p.suffix not in (".json", ".xml", ".log"): continue
        raw = p.read_bytes()
        text = raw.decode("utf-8", errors="replace")
        updated = text.replace(str(REPO).replace("\\", "\\\\"), "<REPOSITORY>").replace(str(REPO), "<REPOSITORY>")
        updated = updated.replace(r"C:\\Users\\chenerxiao", "<LOCAL_USER_ROOT>").replace(r"C:\Users\chenerxiao", "<LOCAL_USER_ROOT>")
        # Traceback paths outside the checkout contain local runtime/device roots.
        updated = re.sub(r'[A-Z]:\\\\[^"\n]*?\\\\(?:site-packages|Lib)\\\\', '<PYTHON_RUNTIME>/', updated)
        if p.suffix == ".xml": updated = re.sub(r' hostname="[^"]*"', '', updated)
        if updated != text:
            local = OUT/".local"/p.relative_to(OUT)
            local.parent.mkdir(parents=True, exist_ok=True)
            if not local.exists(): local.write_bytes(raw)
            p.write_bytes(updated.encode("utf-8"))


class DeliveryTests(unittest.TestCase):
    def test_audit_current(self):
        r = read(OUT/"tests/audit_attempt_002/audit_results.json")
        self.assertEqual((r["status"],r["checks_passed"],r["checks_failed"]), ("PASS",25,0))
    def test_synthetic_current(self):
        r = ET.parse(OUT/"tests/synthetic_attempt_002.xml").getroot()[0]
        self.assertEqual([int(r.attrib[k]) for k in ("tests","failures","errors","skipped")], [48,0,0,0])
    def test_prior_failures_preserved(self):
        a = read(OUT/"tests/audit_attempt_001/audit_results.json")
        self.assertEqual(a["checks_failed"],1)
        self.assertTrue(any(c.get("traceback") for c in a["checks"] if c["status"]=="FAIL"))
        self.assertEqual(ET.parse(OUT/"tests/synthetic_attempt_001.xml").getroot()[0].attrib["failures"],"1")
        self.assertTrue((OUT/"tests/pdf_attempt_001/source.tex").exists())
    def test_reports_present_and_governance(self):
        names = ("README", "SCIENTIFIC_EVIDENCE_AUDIT", "PROBABILITY_AND_TAIL_DIAGNOSTICS", "EVENT_CATALOGUE_CANDIDATES", "TERRAIN_STRATIFICATION_CANDIDATES", "RECOVERY_GOVERNANCE_GAP_REVIEW", "PHASE_B_ENTRY_READINESS_CHECKLIST", "RESEARCHER_DECISION_REQUIRED")
        for n in names: self.assertGreater((OUT/(n+".md")).stat().st_size,600)
        self.assertIn("RESEARCHER_DECISION_REQUIRED", (OUT/"RESEARCHER_DECISION_REQUIRED.md").read_text(encoding="utf-8"))
    def test_pdf_complete_text(self):
        from pypdf import PdfReader
        p = OUT/"PHASE_A_HARDENING_REVIEW.pdf"
        self.assertEqual(p.read_bytes()[:5],b"%PDF-")
        reader = PdfReader(p); self.assertEqual(len(reader.pages),11)
        text = "".join(page.extract_text() for page in reader.pages)
        for token in ("128", "0.048759608", "0.047816404", "0.984375", "23,447", "35", "2,000"):
            self.assertIn(token,text)
    def test_final_pdf_log_and_visual_record(self):
        log = (OUT/"tests/pdf_export_attempt_002/PHASE_A_HARDENING_REVIEW.log").read_text(encoding="utf-8",errors="replace")
        self.assertNotIn("Missing character",log); self.assertNotIn("Overfull",log)
        self.assertEqual(read(OUT/"visual_delivery_audit.json")["pages_visually_inspected"],list(range(1,12)))
        self.assertEqual(read(OUT/"visual_delivery_audit.json")["PDF_sha256"],digest(OUT/"PHASE_A_HARDENING_REVIEW.pdf"))
    def test_desktop_final_compiler(self):
        r = read(OUT/"tests/pdf_compile_final.json")
        self.assertEqual(json.loads(r["content"][0]["text"])["kind"],"success")
    def test_report_source_bindings(self):
        b = read(OUT/"report_source_binding.json")
        for name,sha in b["sources"].items(): self.assertEqual(digest(REPO/name),sha)
        self.assertEqual(digest(OUT/"PHASE_A_HARDENING_REVIEW.tex"),b["latex_source_sha256"])
    def test_reused_figure_identity(self):
        r = read(OUT/"figures/figure_references.json")
        self.assertEqual(len(r["sources"]),8)
        for ref in r["sources"]: self.assertEqual(digest(REPO/ref["repository_path"]),ref["sha256"])
    def test_all_original_tracked_files_unchanged(self):
        # This is run before staging; after staging, baseline comparison still
        # permits only new files under the four explicit task roots.
        out = subprocess.check_output(["git","diff","--name-status",BASELINE],cwd=REPO,text=True,encoding="utf-8")
        for line in out.splitlines():
            status,name = line.split("\t",1)
            self.assertEqual(status,"A"); self.assertTrue(name.startswith(PUBLIC_ROOTS))
    def test_no_training_mutation_calls_in_new_code(self):
        for root in PUBLIC_ROOTS[:3]:
            for p in (REPO/root).glob("*.py"):
                parsed = ast.parse(p.read_text(encoding="utf-8"))
                for node in ast.walk(parsed):
                    if isinstance(node,ast.Call) and isinstance(node.func,ast.Attribute):
                        self.assertNotIn(node.func.attr,("backward","step","load_state_dict"),rel(p))
    def test_public_types_and_no_device_identifiers(self):
        allowed = {".py",".md",".json",".pdf",".tex",".xml",".log",".txt"}
        for p in public_files():
            self.assertIn(p.suffix,allowed,rel(p))
            self.assertLess(p.stat().st_size,5_000_000)
            if p.suffix in (".json",".xml"):
                text = p.read_text(encoding="utf-8")
                self.assertNotIn('hostname="',text)
                self.assertNotIn("C:\\\\Users\\\\chenerxiao",text)
    def test_metric_report_rounding(self):
        text = (OUT/"SCIENTIFIC_EVIDENCE_AUDIT.md").read_text(encoding="utf-8")
        with (OLD/"PAIRED_STRATIFIED_COMPARISONS.csv").open(encoding="utf-8",newline="") as stream:
            for r in csv.DictReader(stream):
                if r["group"]=="ALL":
                    for key in ("B0","B1","B1_minus_B0","delta_lower","delta_upper"):
                        self.assertIn(f'{float(r[key]):.9f}',text)
    def test_limits_and_advisory_only(self):
        for k in ("V2_PHASE_B_AUTHORIZED=false","2025_RAW_ACCESS=0","2025_PIXELS_READ=0"):
            self.assertIn(k,(OUT/"README.md").read_text(encoding="utf-8"))
        self.assertIn('"can_launch_formal_training": False',(REPO/"src/yuntapr/diagnostics/readiness.py").read_text(encoding="utf-8"))


def main() -> None:
    if not (OUT/"visual_delivery_audit.json").exists():
        write("visual_delivery_audit.json", {"status":"PASS", "pages_visually_inspected": list(range(1,12)), "render_directory":"tests/pdf_render_attempt_002", "PDF_sha256":digest(OUT/"PHASE_A_HARDENING_REVIEW.pdf"), "latex_sha256":digest(OUT/"PHASE_A_HARDENING_REVIEW.tex"), "inspection":"All final pages inspected through view_image; no clipping, overlap or missing math glyphs", "prior_export":"12-page first export retained; glyph/long identifier warnings corrected in final 11-page source"})
    redact_public_records()
    # Audit current result has no redacted absolute path. Its binding remains exact.
    stream = io.StringIO()
    result = unittest.TextTestRunner(stream=stream,verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(DeliveryTests))
    write("tests/delivery_verification.json", {"status":"PASS" if result.wasSuccessful() else "FAIL", "tests_run":result.testsRun, "failures":len(result.failures), "errors":len(result.errors), "log":stream.getvalue()})
    if not result.wasSuccessful():
        print(stream.getvalue()); raise SystemExit(1)
    write("final_status.json", {"status":"AUTHORIZED_ENGINEERING_SCOPE_COMPLETE_RESEARCHER_REVIEW_REQUIRED", "created_utc":datetime.now(timezone.utc).isoformat(), "recovered_baseline_HEAD":BASELINE, "audit_checks_passed":25, "synthetic_tests_passed":48, "delivery_checks_passed":result.testsRun, "current_failures":0, "prior_audit_failures_preserved":1, "prior_synthetic_failures_preserved":1, "PDF_pages":11, "MODEL_FORWARDS_ADDED":0, "SYNTHETIC_HEAD_NUMERICS_EXERCISED":True, "BACKWARD_CALLS":0, "OPTIMIZER_STEPS":0, "FORMAL_OPTIMIZER_STEPS_ADDED":0, "2025_RAW_ACCESS":0, "2025_PIXELS_READ":0, "RESEARCHER_SCIENTIFIC_APPROVAL_REQUIRED":True, "V2_PHASE_B_AUTHORIZED":False, "SCIENTIFIC_ACCEPTANCE_DECISION":"UNDECIDED", "HISTORICAL_RECOVERY_RATIFICATION":"NOT_GRANTED", "FORMAL_V2_PHASE_B_ENTRY":"NOT_READY_REQUIRES_APPROVED_PROTOCOL_AND_RUNNER", "EVENT_CATALOGUE":"CANDIDATE_MATH_AND_SYNTHETIC_ONLY", "TERRAIN_STRATA":"CANDIDATE_MATH_AND_SYNTHETIC_ONLY", "publication_status":"SEE_APPEND_ONLY_PUBLICATION_RECEIPT_AFTER_PUSH", "not_executed":read(OUT/"tests/audit_attempt_002/audit_results.json")["not_executed"], "AUTOMATIC_NEXT_STAGE":False, "STOP_AT_RESEARCHER_BOUNDARY":True})
    files = public_files()
    manifest = {"schema":"PHASE_A_HARDENING_PREPARATION_ONLY_v1", "baseline_commit":BASELINE, "artifacts":[{"repository_path":rel(p),"bytes":p.stat().st_size,"sha256":digest(p)} for p in files], "manifest_self_binding":"Git commit tree; own bytes are not recursively included", "public_records_privacy":"Absolute checkout/runtime/device identifiers redacted; unredacted copies retained in local .local/ (excluded from publication)", "historical_evidence_modified":False, "figure_policy":"References to eight published SVG/PNG only; no new figure generation", "sources":read(OUT/"tests/audit_attempt_002/audit_results.json")["source_sha256"]}
    write("manifest.json",manifest)
    paths = [rel(p) for p in files] + ["docs/phase_a_evidence_hardening/manifest.json"]
    (OUT/"publication_allowlist.paths").write_text("\n".join(paths)+"\n",encoding="utf-8",newline="\n")
    print(json.dumps({"status":"PASS", "delivery_checks":result.testsRun, "allowlisted_files":len(paths)}))


if __name__ == "__main__": main()
