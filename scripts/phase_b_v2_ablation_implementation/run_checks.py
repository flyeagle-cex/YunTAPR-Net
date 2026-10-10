"""Bounded pytest runner for synthetic loss fixtures, not a training launcher."""
from __future__ import annotations
from pathlib import Path
import argparse
import json
import os
import re
import subprocess
import sys
import time
import xml.etree.ElementTree as ET

REPO = Path(__file__).resolve().parents[2]
OUT = REPO / "docs/phase_b_v2_ablation_implementation/v1"


def redact(text: str) -> str:
    text = text.replace(str(REPO), "<WORKSPACE>").replace(REPO.as_posix(), "<WORKSPACE>")
    # Imported dependency tracebacks can contain a user profile outside REPO.
    return re.sub(r"[A-Za-z]:[/\\]+Users[/\\]+[^/\\\s\"'<>]+", "<USER_PROFILE>", text)


def main(attempt: int, cuda: bool) -> None:
    if type(attempt) is not int or attempt < 1: raise ValueError("Positive append-only attempt required")
    label = f"{'cuda' if cuda else 'synthetic'}_attempt_{attempt:03d}"
    public = OUT / "tests"; private = OUT / ".local"
    public.mkdir(parents=True, exist_ok=True); private.mkdir(parents=True, exist_ok=True)
    record_path = public / (label + ".json")
    if record_path.exists(): raise FileExistsError("Never overwrite an earlier test record")
    xml = private / (label + ".xml")
    args = [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", "--junitxml=" + str(xml)]
    suite = "tests/phase_b_v2_ablation_implementation"
    args += [suite + "/test_cuda.py"] if cuda else [suite, "--ignore=" + suite + "/test_cuda.py"]
    env = dict(os.environ, PYTHONUTF8="1", YUNTAPR_SYNTHETIC_CUDA="1" if cuda else "0")
    start = time.monotonic()
    try:
        result = subprocess.run(args, cwd=REPO, env=env, capture_output=True, timeout=60)
        raw = result.stdout + result.stderr; code = result.returncode; timeout = False
    except subprocess.TimeoutExpired as exc:
        raw = (exc.stdout or b"") + (exc.stderr or b""); code = None; timeout = True
    (private / (label + ".full.log")).write_bytes(raw)
    output = redact(raw.decode("utf-8", errors="replace"))
    (public / (label + ".log")).write_text(output, encoding="utf-8", newline="\n")
    counts = {"tests": 0, "failures": 0, "errors": 0, "skipped": 0}
    if xml.exists():
        tree = ET.parse(xml)
        for node in tree.iter():
            if "hostname" in node.attrib: node.attrib["hostname"] = "REDACTED_HOST"
        for node in tree.getroot().iter("testsuite"):
            for key in counts: counts[key] += int(node.get(key, 0))
        public_xml = redact(ET.tostring(tree.getroot(), encoding="unicode"))
        (public / (label + ".xml")).write_text(public_xml, encoding="utf-8", newline="\n")
    counts["passed"] = counts["tests"] - counts["failures"] - counts["errors"] - counts["skipped"]
    record = {"scope": "CUDA_SYNTHETIC_LOSS_ONLY" if cuda else "CPU_SYNTHETIC_LOSS_AND_METADATA_ONLY",
              "status": "TIMEOUT" if timeout else "PASS" if code == 0 and counts["passed"] > 0 else "FAIL_OR_UNAVAILABLE",
              "exit_code": code, "timeout": timeout, "timeout_seconds": 60, "counts": counts,
              "wall_seconds": round(time.monotonic()-start, 3), "command": ["python", *args[1:3], *args[3:-2], *args[-2:]],
              "optimizer_steps": 0, "model_forward": 0, "raw_data_reads": 0}
    record["command"] = [redact(a) for a in record["command"]]
    with record_path.open("x", encoding="utf-8") as stream: json.dump(record, stream, indent=2)
    print(json.dumps(record, ensure_ascii=False))
    # Timeouts/unavailable tests must also give a failing shell exit status.
    if record["status"] != "PASS": sys.exit(code if code and code > 0 else 1)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(); parser.add_argument("--attempt", type=int, required=True); parser.add_argument("--cuda", action="store_true")
    opt = parser.parse_args(); main(opt.attempt, opt.cuda)
