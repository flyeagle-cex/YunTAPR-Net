"""Disposable guarded pytest process. It can only select the two synthetic suites."""
from pathlib import Path
import json
import os
import sys
from yuntapr.experimental.phase_b_v2_integration.safety import install_process_file_guard, synthetic_operation_guards
from yuntapr.experimental.phase_b_v2_integration.resources import resource_snapshot, require_resources


def main():
    phase, xml = sys.argv[1:]
    if phase not in ("cpu", "cuda"):
        raise ValueError("Unknown synthetic suite")
    install_process_file_guard()
    admission = resource_snapshot(full_backward=phase == "cuda")
    path = Path(os.environ["YUNTAPR_SYNTHETIC_EVIDENCE"]) / "resource_before_model_construction.json"
    with path.open("x", encoding="utf-8") as stream:
        json.dump(admission, stream, indent=2)
    require_resources(admission)
    import pytest
    suite = "tests/phase_b_v2_isolated_integration"
    arguments = ["-q", "-p", "no:cacheprovider", "--junitxml=" + xml]
    # A failed full-grid resource/gradient case ends this suite, without fallback.
    arguments += ["-x", suite + "/test_cuda_e2e.py"] if phase == "cuda" else [
        suite + "/test_adapter_controls.py", suite + "/test_initialization.py"]
    with synthetic_operation_guards():
        code = pytest.main(arguments)
    raise SystemExit(code)


if __name__ == "__main__":
    main()
