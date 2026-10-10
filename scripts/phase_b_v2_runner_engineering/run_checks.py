"""Bounded subprocess checks with exclusive, retained logs; no dataset access."""
from __future__ import annotations
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "docs/phase_b_v2_runner_engineering/v1/tests"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("suite", choices=("cpu", "cuda", "hardening", "final_static", "final_cuda_state"))
    parser.add_argument("attempt", type=int)
    args = parser.parse_args()
    if args.attempt < 1:
        parser.error("Positive attempt required")
    OUT.mkdir(parents=True, exist_ok=True)
    stem = f"{args.suite}_attempt_{args.attempt:03d}"
    env = dict(os.environ, PYTHONUTF8="1", PYTHONHASHSEED="2026", CUBLAS_WORKSPACE_CONFIG=":4096:8")
    env["PYTHONPATH"] = os.pathsep.join((str(ROOT / "src"), str(ROOT / "docs/phase_b_v2_ablation_implementation/v1/.local/test_dependencies")))
    test_file = "hardening" if args.suite == "final_cuda_state" else args.suite
    command = [sys.executable, "-m", "pytest", "-q", "--tb=short", "-x",
               f"tests/phase_b_v2_runner_candidate/test_{test_file}.py",
               "--junitxml=" + str(OUT / (stem + ".xml"))]
    if args.suite == "final_cuda_state":
        command.extend(["-k", "final_source_identity_and_restore_fail_closed_no_updates"])
    start = time.perf_counter()
    with (OUT / (stem + ".log")).open("x", encoding="utf-8") as stream:
        result = subprocess.run(command, cwd=ROOT, env=env, stdout=stream, stderr=subprocess.STDOUT, timeout=600)
    record = {"scope": "SYNTHETIC_ENGINEERING_ONLY", "suite": args.suite, "attempt": args.attempt,
              "exit_code": result.returncode, "elapsed_seconds": time.perf_counter() - start,
              "FORMAL_OPTIMIZER_STEPS": 0, "prior_suites_reexecuted": False}
    with (OUT / (stem + ".json")).open("x", encoding="utf-8") as stream:
        json.dump(record, stream, indent=2)
    print(json.dumps(record))
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
