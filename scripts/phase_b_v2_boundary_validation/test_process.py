"""Disposable process restricted to new artificial boundary tests."""
from pathlib import Path
import json
import os
import sys
from yuntapr.experimental.phase_b_v2_integration.safety import install_process_file_guard, synthetic_operation_guards
from yuntapr.experimental.phase_b_v2_integration.resources import resource_snapshot, require_resources
from yuntapr.experimental.phase_b_v2_boundaries.boundary import verify_inherited_identity


def main():
    phase,xml=sys.argv[1:]
    if phase not in ("cpu","cuda"):
        raise ValueError("No formal selection")
    install_process_file_guard()
    verified=verify_inherited_identity()
    snapshot=resource_snapshot(full_backward=phase=="cuda")
    with (Path(os.environ["YUNTAPR_SYNTHETIC_EVIDENCE"])/"resource_before_model_construction.json").open("x",encoding="utf-8") as f:
        json.dump({"scope":"SYNTHETIC_ENGINEERING_ONLY","inherited_hashes_verified":verified,
                   "resource":snapshot},f,indent=2)
    require_resources(snapshot)
    import pytest
    test="test_cuda_boundaries.py" if phase=="cuda" else "test_cpu_boundaries.py"
    arguments=["-q","-p","no:cacheprovider","--junitxml="+xml,
               "tests/phase_b_v2_boundary_validation/"+test]
    if phase=="cuda":
        arguments.insert(0,"-x")  # stop first failed/resource case, never retry or reduce the batch
    with synthetic_operation_guards():
        code=pytest.main(arguments)
    raise SystemExit(code)


if __name__=="__main__":
    main()
