"""Actual existing/new fixture tests, isolated from the formal checkpoint."""
from pathlib import Path
import sys
ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "scripts"), str(ROOT / "src"), str(ROOT)]
from mask_partitioned_replay_v1 import common as c
import argparse
import io
import json
import unittest


def main():
    parser = argparse.ArgumentParser(); parser.add_argument("--run", type=Path, required=True); args = parser.parse_args()
    suite = unittest.TestSuite(); counts = {}
    for label, folder in (("existing_autopsy", "quantile_overflow_autopsy"), ("mask_partitioned", "mask_partitioned_replay")):
        selected = unittest.TestLoader().discover(str(ROOT / "tests" / folder), pattern="test_*.py")
        counts[label] = selected.countTestCases(); suite.addTests(selected)
    console = io.StringIO(); result = unittest.TextTestRunner(stream=console, verbosity=2).run(suite)
    ok = result.wasSuccessful() and not result.skipped
    output = {"utc": c.now(), "status": "PASS" if ok else "FAIL", "TEST_FIXTURE_ONLY": True,
        "suite_counts": counts, "counts": {"passed": result.testsRun - len(result.failures) - len(result.errors) - len(result.skipped),
            "failed": len(result.failures), "errors": len(result.errors), "skipped": len(result.skipped)},
        "FORMAL_OPTIMIZER_STEPS_ADDED": 0, "2025_RAW_ACCESS": 0, "temporary_checkpoints_created": 0,
        "fixture_models_optimizer_artifacts": "In-memory isolated fixtures, released/GC; no formal checkpoint opened by tests.",
        "cuda_equivalence": "Frozen execute_update output/loss/gradient/model/optimizer/RNG exact identity",
        "diagnostic_source_hashes": {p.relative_to(ROOT).as_posix(): c.digest(p) for p in
                                    sorted(Path(__file__).parent.glob("*.py"))},
        "test_source_hashes": {p.relative_to(ROOT).as_posix(): c.digest(p) for p in
                              sorted((ROOT / "tests/mask_partitioned_replay").glob("*.py"))},
        "immutable_history": c.verify_snapshot(args.run), "console": console.getvalue()}
    c.write(args.run / "observer_test_result.json", output)
    print(json.dumps({"status": output["status"], "suite_counts": counts, "counts": output["counts"]}), flush=True)
    if not ok: print(console.getvalue()); raise SystemExit(1)


if __name__ == "__main__":
    main()
