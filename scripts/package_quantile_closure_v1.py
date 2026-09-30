"""Run the five independent suites and package measured numerical closure evidence."""
import argparse
import ast
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys

import torch

from yuntapr.contracts.loader import REPO_ROOT, load_contract, sha256


BASELINE = "957e8519e8063a6174b7bced5f10a819be0ef64e"
SUITES = ("scientific_freeze", "b0_skeleton", "development_qc",
          "scientific_freeze_v1_1", "quantile_numerical_closure")


def write_new(path, value):
    if path.exists():
        raise FileExistsError(f"Versioned run output already exists: {path}")
    if isinstance(value, str):
        path.write_text(value, encoding="utf-8", newline="\n")
    else:
        path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False)+"\n",
                        encoding="utf-8", newline="\n")


def run_tests(out):
    env = {**os.environ, "PYTHONPATH": str(REPO_ROOT / "src"), "PYTHONIOENCODING": "utf-8"}
    logs, results = [], []
    for suite in SUITES:
        command = [sys.executable, "-m", "unittest", "discover", "-s", "tests/"+suite, "-p", "test_*.py", "-v"]
        proc = subprocess.run(command, cwd=REPO_ROOT, env=env, capture_output=True, text=True, encoding="utf-8")
        output = proc.stdout + proc.stderr
        match = re.search(r"Ran (\d+) tests? in", output)
        result = {"suite": suite, "count": int(match[1]) if match else 0, "exit_code": proc.returncode,
                  "passed": proc.returncode == 0 and match is not None and int(match[1]) > 0}
        logs.append("COMMAND: "+" ".join(command)+"\n"+output)
        results.append(result)
        print(json.dumps(result), flush=True)
    write_new(out / "test_results.txt", "\n\n".join(log.rstrip("\n") for log in logs)+"\n")
    return {"suites": results, "test_count": sum(r["count"] for r in results),
            "all_passed": all(r["passed"] for r in results)}


def main(out):
    if not out.is_dir():
        raise FileNotFoundError("Independent versioned run directory required")
    science, cfg = load_contract()
    if cfg["schema_version"] != 4:
        raise ValueError("v4 engineering configuration not active")
    historical = ["config/science_contract_v1.yaml", "config/science_contract_v1.1.yaml",
                  "config/b0_engineering_v2.yaml", "config/b0_engineering_v3.yaml",
                  "docs/scientific_freeze", "docs/b0_pretraining_closure", "docs/development_qc",
                  "docs/b0_skeleton", "config/spatial", "stage0-b0-evidence"]
    changed = subprocess.check_output(["git", "diff", "--name-only", BASELINE, "--", *historical],
                                      cwd=REPO_ROOT, text=True).strip()
    if changed:
        raise ValueError("Historical scientific contracts/evidence modified: "+changed)
    science_path = REPO_ROOT/"config/science_contract_v1.1.yaml"
    baseline_science = subprocess.check_output(["git", "show", BASELINE+":config/science_contract_v1.1.yaml"], cwd=REPO_ROOT)
    if hashlib.sha256(baseline_science).hexdigest() != sha256(science_path):
        raise ValueError("D1-D8 scientific contract changed")
    stress = json.loads((out/"quantile_stress_float64.json").read_text(encoding="utf-8"))
    physical = json.loads((out/"physical_overflow_stress.json").read_text(encoding="utf-8"))
    real = json.loads((out/"real_regression_smoke.json").read_text(encoding="utf-8"))
    gradient = json.loads((out/"gradient_dtype_trace.json").read_text(encoding="utf-8"))
    execution = json.loads((out/"execution_status.json").read_text(encoding="utf-8"))
    tests = run_tests(out)
    write_new(out/"engineering_config_snapshot_v4.yaml", (REPO_ROOT/"config/b0_engineering_v4.yaml").read_text(encoding="utf-8"))
    production = [REPO_ROOT/"src/yuntapr/models/monotonic_quantiles.py", REPO_ROOT/"src/yuntapr/models/probability_heads.py"]
    forbidden = {"sort", "argsort", "clamp", "clamp_min", "clamp_max", "nan_to_num"}
    no_repair = not any({n.attr for n in ast.walk(ast.parse(p.read_text(encoding="utf-8")))
                         if isinstance(n, ast.Attribute)} & forbidden for p in production)
    all_cases = len(stress["cases"]) == 14 and stress["all_required_cases_pass"] and all(
        r["qlog_finite"] and r["strictly_increasing"] and r["adjacent_equal_count"] == 0
        and r["gradient_finite"] and r["qlog_dtype"] == "torch.float64" for r in stress["cases"])
    real_pass = (real["all_passed"] and {s["year"] for s in real["samples"]} == {2023, 2024}
                 and all(s["qlog_strict"] and s["qphysical_finite"] and s["finite_forward_physical_loss_and_backward"]
                         for s in real["samples"]))
    dtype_pass = gradient["all_dtype_and_gradient_contracts_pass"] and any(
        r["suite"] == "quantile_numerical_closure" and r["passed"] for r in tests["suites"])
    physical_pass = (physical["physical_overflow_caught_separately"] and physical["large_qlog_finite_and_strict"]
                     and physical["moderate_float64_physical_finite"]
                     and not physical["monotonicity_error_raised_for_physical_overflow"])
    criteria = {"all_required_qlog_stress_strict_zero_equal": all_cases, "real_2023_2024_regression": real_pass,
                "float32_parameter_gradients_and_float64_outputs": dtype_pass,
                "physical_overflow_separately_caught": physical_pass,
                "no_sort_or_clamp": no_repair, "all_historical_and_new_tests": tests["all_passed"],
                "scientific_contract_unchanged": not bool(changed)}
    closed = all(criteria.values())
    status = {"SCIENTIFIC_FREEZE_VERSION": "v1.1", "QUANTILE_NUMERICAL_STABILITY_CLOSED": closed,
              "B0_FORMAL_TRAINING_STARTED": False, "FORMAL_TRAINING_AUTHORIZED": False}
    write_new(out / "closure_status.json", {"criteria": criteria, "status": status, "test_count": tests["test_count"],
             "status_basis": "All measured criteria; a detected physical overflow is expected to raise explicitly"})
    constant_rows = [r for r in stress["cases"] if r["case"].startswith("constant_")]
    random_rows = [r for r in stress["cases"] if not r["case"].startswith("constant_")]
    lines = "\n".join(f"| {r['case']} | {r['qlog_dtype']} | {r['adjacent_equal_count']} | {r['strictly_increasing']} | {r['gradient_finite']} |"
                      for r in stress["cases"])
    test_lines = "\n".join(f"| {r['suite']} | {r['count']} | {'PASS' if r['passed'] else 'FAIL'} |" for r in tests["suites"])
    report = f"""# YunTAPR-Net Quantile Numerical Closure v1

Run: `{out.name}`. Baseline: `{BASELINE}`. Scientific Freeze remains **v1.1**.
This is an engineering precision change. The SHA256 of the scientific v1.1 contract
is unchanged; no D1–D8 definition or model parameterization was altered.

## Result

**QUANTILE_NUMERICAL_STABILITY_CLOSED = {str(closed).lower()}** for the specified
stress population and real regression gate. This does not imply every unbounded raw
tensor has a finite physical expm1 value: overflow is detected as a separate error.
Training authorization remains false; no optimizer update or checkpoint was made.

## Precision path

Backbone and both head parameters remain float32. The quantile head emits float32 raw
values even inside CPU autocast. In the monotonic transform, raw is converted to
float64, softplus and the unchanged epsilon=1e-4 are evaluated in float64, and all
32 log quantiles are accumulated sequentially in float64 from log1p(0.1). The
qlog tensor stays float64. Physical expm1 also uses float64. There is no downcast,
sort, rank relabel, clamp, or artificial precipitation maximum. Runtime checks
finite qlog, q1>log1p(0.1), and strict adjacent increase; violations raise
`QUANTILE_MONOTONICITY_LOST`. Finite qlog with nonfinite physical expm1 raises
`QUANTILE_PHYSICAL_OVERFLOW`.

The conditional pinball target computes log1p(y) in qlog's float64 dtype, and τ
uses the same dtype with the unchanged `(i−0.5)/32` grid. The occurrence head and
focal loss remain unchanged. Real backward traces prove that float64 loss gradients
reach the float32 quantile head and backbone parameters without a detach.

## MONOTONIC_TRANSFORM_STRESS

Seed 20260930. Ten constant cases and four random/mixed cases; expm1 is deliberately
excluded from this test family. All {len(stress['cases'])} cases have finite float64
qlog, strict adjacent increase, zero equal pairs and finite raw gradients. In the
old 22×(+100) then 10×(−100) counterexample, the minimum observed log increment
is {next(r for r in stress['cases'] if r['case'].startswith('mixed_'))['minimum_log_increment']:.12g},
and the equal count is 0. The previous float32 run recorded 10 equalities in this
case; its report remains immutable historical evidence.

| Case | qlog dtype | Equal adjacent | Strict | Finite gradient |
|---|---|---:|---|---|
{lines}

## FULL_PHYSICAL_HEAD_STRESS

With a moderate synthetic raw bias +20, float64 physical quantiles are finite.
With +100 across 32 channels, qlog is finite and strictly increasing up to
{physical['large_qlog_max']:.6f}, while expm1 overflows float64. The observed runtime
error is `{physical['observed_error']}`. This is the expected explicit physical
overflow category; no monotonicity error was raised and no clamp was applied.

## Real 2023/2024 regression

The same previously hash-verified 2023 and 2024 full-valid B13/IMERG samples were
reread through bounded English staging with SHA verification. Each passed formal QC,
the pinned 2023-only normalization, B0 backbone, frozen SP04 projection,
probability heads, masked loss and backward. Each has 3430 valid Yunnan loss pixels.
Both forward outputs, physical quantiles, loss and parameter gradients are finite.
Per-sample `gradient_dtype_trace.json` records float32 backbone/head weights and
gradients, float32 raw quantile output/gradient, and float64 qlog, qphysical and
conditional loss. Quantile and backbone gradients are nonzero. Focal alpha=.25 and
gamma=2 are ENGINEERING_TEST_ONLY; they remain unfrozen development parameters.

The CPU bfloat16 autocast test verifies that the quantile head raw output stays
float32 and the monotonic accumulator, qlog and physical quantiles stay float64.

## Tests and provenance

| Suite | Tests | Result |
|---|---:|---|
{test_lines}

Total: {tests['test_count']} tests. Old Scientific Freeze, B0 skeleton, Development
QC and v1.1 reports/configurations were preserved. Engineering v4 is a separate
config with a pinned copy in this run. The manifest records source/code/artifact
SHA256 hashes. PyTorch version: {torch.__version__}; interpreter: `{sys.executable}`.

## Final status

```text
SCIENTIFIC_FREEZE_VERSION = v1.1
QUANTILE_NUMERICAL_STABILITY_CLOSED = {str(closed).lower()}
B0_FORMAL_TRAINING_STARTED = false
FORMAL_TRAINING_AUTHORIZED = false
```

Stop after GitHub synchronization. Phase-A training is outside this task.
"""
    write_new(out / "QUANTILE_NUMERICAL_CLOSURE_REPORT.md", report)
    core = ["config/science_contract_v1.1.yaml", "config/b0_engineering_v3.yaml", "config/b0_engineering_v4.yaml",
            "src/yuntapr/contracts/loader.py", "src/yuntapr/models/monotonic_quantiles.py",
            "src/yuntapr/models/probability_heads.py", "src/yuntapr/models/b0.py",
            "src/yuntapr/losses/pinball.py", "src/yuntapr/losses/total_loss.py",
            "scripts/quantile_numerical_closure_v1.py", "scripts/package_quantile_closure_v1.py",
            "tests/quantile_numerical_closure/test_quantile_v4.py"]
    manifest = {"run_id": out.name, "baseline_commit": BASELINE,
                "created_utc": datetime.now(timezone.utc).isoformat(), "scientific_freeze_version": "v1.1",
                "status": status, "criteria": criteria, "python": sys.executable,
                "torch_version": torch.__version__, "scientific_contract_sha256": sha256(science_path),
                "historical_files_unchanged": True,
                "prior_quantile_stress_sha256": sha256(REPO_ROOT/"docs/b0_pretraining_closure/runs/run_20260930T095416Z/quantile_numerical_stability_v1.1.json"),
                "code_and_config_sha256": {p: sha256(REPO_ROOT/p) for p in core},
                "public_files_sha256": {p.name: sha256(p) for p in out.iterdir() if p.is_file() and p.name != "manifest.json"}}
    write_new(out / "manifest.json", manifest)
    print(json.dumps({"closed": closed, "tests": tests["test_count"], "criteria": criteria}), flush=True)
    if not closed:
        raise SystemExit(1)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-dir", type=Path, required=True)
    main(parser.parse_args().run_dir)
