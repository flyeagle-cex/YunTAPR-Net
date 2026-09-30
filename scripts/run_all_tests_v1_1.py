"""Run historical and v1.1 suites independently; retain every test attempt."""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import subprocess
import sys
from yuntapr.contracts.loader import REPO_ROOT


def main(out):
    suites = ["scientific_freeze", "b0_skeleton", "development_qc", "scientific_freeze_v1_1"]
    env = {**os.environ, "PYTHONPATH": str(REPO_ROOT/"src"), "PYTHONIOENCODING": "utf-8"}
    logs, results = [], []
    for suite in suites:
        command = [sys.executable, "-m", "unittest", "discover", "-s", "tests/"+suite, "-p", "test_*.py", "-v"]
        p = subprocess.run(command, cwd=REPO_ROOT, env=env, capture_output=True, text=True, encoding="utf-8")
        log = p.stdout+p.stderr
        logs.append("COMMAND: "+" ".join(command)+"\n"+log)
        match = re.search(r"Ran (\d+) tests? in", log)
        result = {"suite": suite, "tests_run": int(match[1]) if match else 0, "exit_code": p.returncode,
                  "passed": p.returncode == 0 and match is not None and int(match[1]) > 0}
        results.append(result)
        print(json.dumps(result), flush=True)
    text = "\n\n".join(logs)
    attempt = out/("test_attempt_"+datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")+".txt")
    attempt.write_text(text, encoding="utf-8", newline="\n")
    (out/"test_results.txt").write_text(text, encoding="utf-8", newline="\n")
    (out/"test_summary.json").write_text(json.dumps({"suites": results, "all_passed": all(r["passed"] for r in results), "tests_run": sum(r["tests_run"] for r in results)}, indent=2)+"\n", encoding="utf-8")
    if not all(r["passed"] for r in results):
        raise SystemExit(1)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-dir", type=Path, required=True)
    main(parser.parse_args().run_dir)
