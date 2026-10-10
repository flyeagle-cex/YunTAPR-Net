"""Allowlisted staging/byte audit; does not push or overwrite old Git evidence."""
from __future__ import annotations
import hashlib
import json
from pathlib import Path
import subprocess
from datetime import datetime, timezone

REPO = Path(__file__).resolve().parents[2]
OUT = REPO/"docs/phase_a_evidence_hardening"
ROOTS = ("src/yuntapr/diagnostics/", "tests/phase_a_evidence_hardening/", "scripts/phase_a_evidence_hardening/", "docs/phase_a_evidence_hardening/")


def sha(path: Path) -> str:
    with path.open("rb") as stream: return hashlib.file_digest(stream,"sha256").hexdigest()


def git(*args: str) -> bytes:
    return subprocess.check_output(["git","-c","core.longpaths=true",*args],cwd=REPO)


def main(*, resume_staging: bool = False) -> None:
    # The original source/manifest was generated before this final checklist note.
    # Regenerate only this task's manifest, preserving all historical evidence.
    import importlib.util
    spec = importlib.util.spec_from_file_location("delivery_closeout",Path(__file__).with_name("closeout.py"))
    closeout = importlib.util.module_from_spec(spec); spec.loader.exec_module(closeout)
    existing = git("diff","--cached","--name-status").decode("utf-8").splitlines()
    if existing and not resume_staging:
        raise RuntimeError("Index already contains work; leave it untouched")
    if any(not line.startswith("A\t") or not line.split("\t",1)[1].startswith(ROOTS) for line in existing):
        raise RuntimeError("Foreign staged work found; do not touch the index")
    status_path = OUT/"final_status.json"
    status = json.loads(status_path.read_text(encoding="utf-8"))
    status["prior_delivery_errors_preserved"] = 1
    status["prior_pdf_compile_failure_records"] = "First error in conversation plus preserved source; second complete log preserved"
    status_path.write_text(json.dumps(status,ensure_ascii=False,indent=2)+"\n",encoding="utf-8",newline="\n")
    # Newly retained failure log from the first verification contains local roots.
    closeout.redact_public_records()
    files = closeout.public_files()
    manifest_path = OUT/"manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["artifacts"] = [{"repository_path":closeout.rel(p),"bytes":p.stat().st_size,"sha256":sha(p)} for p in files]
    manifest_path.write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+"\n",encoding="utf-8",newline="\n")
    names = [closeout.rel(p) for p in files]+[closeout.rel(manifest_path)]
    allowlist = OUT/"publication_allowlist.paths"
    allowlist.write_text("\n".join(names)+"\n",encoding="utf-8",newline="\n")
    for name in names:
        if not name.startswith(ROOTS) or git("ls-tree","--name-only","HEAD","--",name).strip():
            raise RuntimeError("Publication must contain only new allowlisted files: "+name)
    git("-c","core.autocrlf=false","add","--pathspec-from-file="+str(allowlist))
    # Preserve original whitespace in diagnostic logs. Check authored code,
    # documents and metadata with Windows CRLF recognized as line endings.
    git("-c","core.whitespace=cr-at-eol","diff","--cached","--check","--",".", ":(exclude)docs/phase_a_evidence_hardening/**/*.log")
    staged = git("diff","--cached","--name-status").decode("utf-8").splitlines()
    if set(staged) != {"A\t"+name for name in names}:
        raise RuntimeError("Unexpected staged paths/status; do not commit")
    for name in names:
        blob = git("show",":"+name)
        if hashlib.sha256(blob).hexdigest() != sha(REPO/name):
            raise RuntimeError("Staged byte conversion/mismatch: "+name)
    receipt = {"status":"ALLOWLIST_STAGED_BYTES_PASS", "created_utc":datetime.now(timezone.utc).isoformat(), "baseline_HEAD":git("rev-parse","HEAD").decode().strip(), "new_files":len(names), "historical_files_changed":0, "all_staged_bytes_match_working_files":True, "manifest_sha256":sha(manifest_path), "private_raw_checkpoint_or_device_records_published":False, "2025_RAW_ACCESS":0, "FORMAL_OPTIMIZER_STEPS_ADDED":0, "whitespace_check":"Authored files/metadata checked with cr-at-eol; diagnostic logs excluded to preserve complete original log whitespace", "receipt_self_binding":"Own blob bound by evidence commit tree"}
    receipt_path = OUT/"publication_staged_audit.json"
    with receipt_path.open("x",encoding="utf-8",newline="\n") as stream: json.dump(receipt,stream,ensure_ascii=False,indent=2)
    git("-c","core.autocrlf=false","add","--",closeout.rel(receipt_path))
    if git("diff","--cached","--name-only").decode("utf-8").splitlines() != sorted(names+[closeout.rel(receipt_path)]):
        raise RuntimeError("Index changed concurrently")
    print(json.dumps({"status":"PASS", "staged_new_files":len(names)+1, "historical_files_changed":0}))


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--resume-staging", action="store_true")
    main(resume_staging=parser.parse_args().resume_staging)
