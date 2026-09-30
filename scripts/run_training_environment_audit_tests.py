"""Run every existing YunTAPR suite plus this audit's evidence checks."""
import argparse
from pathlib import Path
import subprocess
import sys

from yuntapr.contracts.loader import REPO_ROOT


SUITES = ("scientific_freeze", "b0_skeleton", "development_qc",
          "scientific_freeze_v1_1", "quantile_numerical_closure",
          "training_environment_audit")


def main(run):
    if run.parent.resolve() != (REPO_ROOT / "docs/training_environment_audit/runs").resolve():
        raise ValueError("Versioned run directory required")
    result_path = run / "test_results.txt"
    if result_path.exists():
        raise FileExistsError("Existing test result is immutable")
    outcomes = []
    with result_path.open("x", encoding="utf-8", newline="\n") as output:
        for suite in SUITES:
            command = [sys.executable, "-m", "unittest", "discover", "-s",
                       str(REPO_ROOT / "tests" / suite), "-p", "test_*.py", "-v"]
            process = subprocess.run(command, cwd=REPO_ROOT, capture_output=True, text=True,
                                     encoding="utf-8", errors="replace")
            output.write(f"COMMAND: {' '.join(command)}\n")
            output.write(process.stdout)
            output.write(process.stderr)
            output.write(f"SUITE_EXIT_CODE: {process.returncode}\n\n")
            output.flush()
            print(f"{suite}: {'PASS' if process.returncode == 0 else 'FAIL'}", flush=True)
            outcomes.append(process.returncode)
        output.write("FINAL_TEST_STATUS: " + ("PASS" if all(code == 0 for code in outcomes) else "FAIL") + "\n")
    return 0 if all(code == 0 for code in outcomes) else 1


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-dir", type=Path, required=True)
    sys.exit(main(parser.parse_args().run_dir.resolve()))
