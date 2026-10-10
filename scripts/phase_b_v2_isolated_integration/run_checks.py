"""Run one bounded synthetic suite; preserve every attempt and never retry automatically."""
from pathlib import Path
import argparse
import importlib.util
import json
import os
import subprocess
import sys
import time
import xml.etree.ElementTree as ET

REPO = Path(__file__).resolve().parents[2]
OUT = REPO / "docs/phase_b_v2_isolated_integration/v1"
spec = importlib.util.spec_from_file_location("prior_checks", REPO / "scripts/phase_b_v2_ablation_implementation/run_checks.py")
prior = importlib.util.module_from_spec(spec)
spec.loader.exec_module(prior)


def main(phase: str, attempt: int) -> None:
    if phase not in ("cpu", "cuda") or type(attempt) is not int or attempt < 1:
        raise ValueError("Closed suite and positive append-only attempt required")
    label = f"{phase}_attempt_{attempt:03d}"
    private = OUT / ".local" / label
    private.mkdir(exist_ok=False)
    evidence = OUT / "tests" / (label + "_evidence")
    evidence.mkdir(exist_ok=False)
    xml = private / "result.xml"
    args = [sys.executable, str(Path(__file__).with_name("test_process.py")), phase, str(xml)]
    env = dict(os.environ, PYTHONUTF8="1", PYTHONHASHSEED="2026", CUBLAS_WORKSPACE_CONFIG=":4096:8",
               YUNTAPR_SYNTHETIC_EVIDENCE=str(evidence))
    # Reuse the already installed task-private pytest; never modify project runtime.
    dependency = REPO / "docs/phase_b_v2_ablation_implementation/v1/.local/test_dependencies"
    env["PYTHONPATH"] = os.pathsep.join((str(REPO/"src"), str(dependency)))
    started = time.monotonic()
    timeout_seconds = 180 if phase == "cpu" else 240
    try:
        result = subprocess.run(args, cwd=REPO, env=env, capture_output=True, timeout=timeout_seconds)
        raw, exit_code, timed_out = result.stdout + result.stderr, result.returncode, False
    except subprocess.TimeoutExpired as exc:
        raw, exit_code, timed_out = (exc.stdout or b"") + (exc.stderr or b""), None, True
    (private / "console.full.log").write_bytes(raw)
    (OUT / "tests" / (label + ".log")).write_text(prior.redact(raw.decode("utf-8", errors="replace")), encoding="utf-8")
    counts = {"tests": 0, "failures": 0, "errors": 0, "skipped": 0}
    if xml.exists():
        tree = ET.parse(xml)
        for node in tree.iter():
            if node.tag == "testsuite":
                for key in counts: counts[key] += int(node.get(key, 0))
            for key, value in node.attrib.items():
                node.set(key, "REDACTED_HOST" if key == "hostname" else prior.redact(value))
            if node.text: node.text = prior.redact(node.text)
            if node.tail: node.tail = prior.redact(node.tail)
        # Redact parsed text, then serialize so angle-bracket placeholders stay XML-safe.
        target = OUT / "tests" / (label + ".xml")
        tree.write(target, encoding="utf-8", xml_declaration=True)
        ET.parse(target)
    counts["passed"] = counts["tests"] - counts["failures"] - counts["errors"] - counts["skipped"]
    status = "TIMEOUT" if timed_out else "PASS" if exit_code == 0 and counts["passed"] else "FAIL_OR_UNAVAILABLE"
    record = {"scope": "SYNTHETIC_ENGINEERING_ONLY", "phase": phase, "attempt": attempt, "status": status,
              "counts": counts, "exit_code": exit_code, "timeout": timed_out,
              "timeout_seconds": timeout_seconds, "wall_seconds": round(time.monotonic()-started, 3),
              "automatic_retry": False, "optimizer_steps": 0, "formal_execution_authorized": False,
              "actual_observational_data_reads": 0, "private_checkpoint_reads": 0,
              "test_source_sha_note": "Bound by delivery manifest after final code review"}
    with (OUT / "tests" / (label + ".json")).open("x", encoding="utf-8") as stream:
        json.dump(record, stream, indent=2)
    print(json.dumps(record))
    if status != "PASS": raise SystemExit(exit_code if exit_code and exit_code > 0 else 1)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--phase", choices=("cpu", "cuda"), required=True)
    parser.add_argument("--attempt", type=int, required=True)
    args = parser.parse_args()
    main(args.phase, args.attempt)

