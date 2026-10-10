"""Retained bounded new-suite logs. No --approved or real-data options."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "docs/phase_b_v2_formal_runner_candidate/v1/tests"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("suite", choices=("cpu", "cuda", "checkpoint", "cpu_repair", "stop"))
    parser.add_argument("attempt", type=int)
    args = parser.parse_args()
    if args.attempt < 1: parser.error("Positive attempt required")
    stem = f"{args.suite}_attempt_{args.attempt:03d}"
    env = dict(os.environ, PYTHONUTF8="1", PYTHONHASHSEED="2026", CUBLAS_WORKSPACE_CONFIG=":4096:8")
    env["PYTHONPATH"] = os.pathsep.join((str(ROOT/"src"),str(ROOT/"docs/phase_b_v2_ablation_implementation/v1/.local/test_dependencies")))
    suite = "cpu" if args.suite == "cpu_repair" else args.suite
    command = [sys.executable,"-m","pytest","-q","-x","--tb=short",
               f"tests/phase_b_v2_formal_runner_candidate/test_{suite}.py","--junitxml="+str(OUT/(stem+".xml"))]
    if args.suite == "cpu_repair":command.extend(["-k","streaming"])
    start = time.perf_counter()
    with (OUT/(stem+".log")).open("x",encoding="utf-8") as stream:
        result = subprocess.run(command,cwd=ROOT,env=env,stdout=stream,stderr=subprocess.STDOUT,timeout=600)
    with (OUT/(stem+".json")).open("x",encoding="utf-8") as stream:
        json.dump({"scope":"SYNTHETIC_ENGINEERING_ONLY","suite":args.suite,"attempt":args.attempt,
                   "exit_code":result.returncode,"seconds":time.perf_counter()-start,
                   "FORMAL_OPTIMIZER_STEPS":0,"prior_suites_reexecuted":False},stream,indent=2)
    print(json.dumps({"suite":args.suite,"attempt":args.attempt,"exit_code":result.returncode}))
    return result.returncode


if __name__ == "__main__": raise SystemExit(main())
