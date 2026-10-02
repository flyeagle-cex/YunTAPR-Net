"""Independent implementation/preflight closure; never calls the formal fit action."""
import argparse
from datetime import datetime, timezone
import gc
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
import uuid

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT/"src"), str(ROOT/"scripts")]
import torch
from yuntapr.contracts.loader import sha256
from yuntapr.training import formal_phase_b as b
import train_b0_phase_a_formal_v1 as inherited
import train_b0_phase_b_finalfit_v1 as runner

BASELINE = "08ebd685b7628489bdd5d1b1d20966c64702ffd4"
PUBLIC = ROOT/"docs/phase_b_formal_runner/runs"
PRIVATE = Path(r"F:\pytorch\Research\outputs\phase_b_formal_runner")
PREP = ROOT/"docs/phase_b_finalfit_preparation/runs/run_20261002T014649_144967Z"
REVIEW = ROOT/"docs/scientific_review/b0_phase_a/runs/run_20261002T005448_798068Z"


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def save(path, value):
    runner.exclusive_json(path, value)


def preserve(out):
    pins = read(out/"historical_preservation.json")
    for name, expected in pins["baseline_files_sha256"].items():
        if sha256(ROOT/name) != expected:
            raise ValueError("Historical artifact changed: "+name)
    best = pins["formal_best"]
    path = Path(best["absolute_local_path"])
    if path.stat().st_size != best["bytes"] or sha256(path) != best["sha256"]:
        raise ValueError("Formal Phase-A BEST identity changed")
    if b.CHECKPOINT_ROOT.exists():
        current = sorted(str(p.relative_to(b.CHECKPOINT_ROOT)) for p in b.CHECKPOINT_ROOT.rglob("*"))
    else:
        current = []
    if current != pins["phase_b_formal_root_contents"]:
        raise ValueError("Formal Phase-B artifacts created during implementation/preflight")
    return {"all_baseline_files_unchanged": True, "files_checked": len(pins["baseline_files_sha256"]),
        "formal_BEST_sha256": best["sha256"], "phase_b_formal_checkpoint_root_unchanged": True}


def initialize():
    if subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip() != BASELINE:
        raise ValueError("Unexpected Git baseline")
    contract = b.RunnerContract.load()
    entries = subprocess.check_output(["git", "ls-tree", "-r", "-z", BASELINE], cwd=ROOT).decode().rstrip("\0").split("\0")
    pins = {}
    for entry in entries:
        meta, name = entry.split("\t", 1)
        data = (ROOT/name).read_bytes()
        if hashlib.sha1(b"blob "+str(len(data)).encode()+b"\0"+data).hexdigest() != meta.split()[2]:
            raise ValueError("Baseline file changed: "+name)
        pins[name] = hashlib.sha256(data).hexdigest()
    best = read(REVIEW/"review_manifest.json")["formal_best"]
    if sha256(Path(best["absolute_local_path"])) != best["sha256"]:
        raise ValueError("Phase-A BEST identity mismatch")
    run_id = "run_"+datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S_%fZ")
    out = PUBLIC/run_id
    private = PRIVATE/run_id
    out.mkdir(parents=True, exist_ok=False)
    private.mkdir(parents=True, exist_ok=False)
    contents = sorted(str(p.relative_to(b.CHECKPOINT_ROOT)) for p in b.CHECKPOINT_ROOT.rglob("*")) if b.CHECKPOINT_ROOT.exists() else []
    save(out/"historical_preservation.json", {"baseline_commit": BASELINE, "baseline_files_sha256": pins,
        "formal_best": best, "phase_b_formal_root_contents": contents})
    save(out/"runner_manifest.json", {"run_id": run_id, "baseline_commit": BASELINE,
        "scope": "RUNNER_IMPLEMENTATION_AND_ENGINEERING_PREFLIGHT_ONLY", "created_utc": runner.now(),
        "private_directory": str(private), "checkpoint_root_provisional_engineering_path": str(b.CHECKPOINT_ROOT),
        "runner_config_sha256": contract.config_sha256, "normalization_sha256": b.NORMALIZATION_SHA,
        "finalfit_manifest_sha256": b.MANIFEST_SHA, "inherited_protocol_sha256": b.PROTOCOL_SHA,
        "implementation_sha256": b.implementation_hashes(), "PHASE_B_AUTHORIZED": False,
        "PHASE_B_FORMAL_TRAINING_STARTED": False, "FORMAL_OPTIMIZER_STEPS": 0, "2025_PIXELS_READ": 0})
    print("RUN_DIRECTORY "+str(out), flush=True)


def preflight(out):
    before = preserve(out)
    private = Path(read(out/"runner_manifest.json")["private_directory"]).resolve()
    cache = (private/("preflight_tmp_"+uuid.uuid4().hex)).resolve()
    if cache.parent != private: raise ValueError("Unsafe preflight temporary directory")
    cache.mkdir(exist_ok=False)
    os.environ.update(TEMP=str(cache), TMP=str(cache), TORCHINDUCTOR_CACHE_DIR=str(cache/"torchinductor"))
    tempfile.tempdir = str(cache)
    violations = []
    active = {"enabled": True}
    stage = (b.STAGING/("phase_b_runner_"+out.name)).resolve()
    def audit(event, args):
        if event != "open" or not isinstance(args[0], (str, bytes, os.PathLike)): return
        path = Path(os.fsdecode(args[0])).resolve()
        mode = args[1] or ""
        flags = args[2] if len(args) > 2 else 0
        writing = any(c in str(mode) for c in "wax+") or bool(flags & (os.O_WRONLY|os.O_RDWR|os.O_CREAT|os.O_TRUNC))
        bad = False
        for root in (b.HROOT.resolve(), b.IROOT.resolve()):
            if path.is_relative_to(root):
                relative = path.relative_to(root)
                bad |= writing or not relative.parts or relative.parts[0][:4] not in ("2023", "2024")
        bad |= path.is_relative_to(Path(r"F:\pytorch\Research\outputs\formal_training").resolve())
        bad |= writing and not path.is_relative_to(out) and not path.is_relative_to(stage) and not path.is_relative_to(cache)
        if bad:
            violations.append(str(path)); raise PermissionError("Preflight isolated path restriction: "+str(path))
    sys.addaudithook(lambda e, a: audit(e, a) if active["enabled"] else None)
    try:
        runner.preflight(out)
    finally:
        active["enabled"] = False
        gc.collect(); torch.cuda.empty_cache()
        if cache.parent == private and cache.name.startswith("preflight_tmp_"):
            shutil.rmtree(cache)
        save(out/("preflight_isolation_"+datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S_%fZ")+".json"),
            {"prohibited_accesses": violations, "raw_sources_read_only": True,
             "formal_binary_reads_and_writes_blocked": True, "2025_paths_blocked_before_open": True,
             "owned_temporary_cache_root": str(cache), "owned_temporary_cache_cleanup_success": not cache.exists(),
             "owned_staging_files_remaining": len(list(stage.rglob("*.nc"))) if stage.exists() else 0,
             "preservation_before_after_equal": before == preserve(out)})
    if violations: raise ValueError("Preflight isolation violation")


def tests(out, units_only=False):
    before = preserve(out)
    if not units_only and read(out/"engineering_preflight.json")["status"] != "PASS":
        raise ValueError("Real preflight must pass before complete artifact tests")
    parent = Path(read(out/"runner_manifest.json")["private_directory"]).resolve()
    fixture = (parent/("test_fixtures_"+uuid.uuid4().hex)).resolve()
    if fixture.parent != parent: raise ValueError("Unsafe fixture root")
    fixture.mkdir(exist_ok=False)
    os.environ.update(TEST_FIXTURE_ONLY="true", TEMP=str(fixture), TMP=str(fixture),
        YUNTAPR_PROTOCOL_DRYRUN_EVIDENCE=str(inherited.DRYRUN), YUNTAPR_SCIENTIFIC_REVIEW_EVIDENCE=str(REVIEW),
        YUNTAPR_PHASE_B_PREPARATION_EVIDENCE=str(PREP), YUNTAPR_PHASE_B_RUNNER_EVIDENCE=str(out))
    tempfile.tempdir = str(fixture)
    torch.set_num_threads(2)
    rawroots = [b.HROOT.resolve(), b.IROOT.resolve()]
    formalroot = Path(r"F:\pytorch\Research\outputs\formal_training").resolve()
    best = Path(read(out/"historical_preservation.json")["formal_best"]["absolute_local_path"]).resolve()
    artifact = {"enabled": False}
    active = {"enabled": True}
    violations = []
    def audit(event, args):
        if event != "open" or not isinstance(args[0], (str, bytes, os.PathLike)): return
        path = Path(os.fsdecode(args[0])).resolve()
        mode = args[1] or ""
        flags = args[2] if len(args) > 2 else 0
        writing = any(c in str(mode) for c in "wax+") or bool(flags & (os.O_WRONLY|os.O_RDWR|os.O_CREAT|os.O_TRUNC))
        bad = any(path.is_relative_to(root) for root in rawroots)
        bad |= path.is_relative_to(formalroot) and not (artifact["enabled"] and path == best and not writing)
        bad |= writing and not path.is_relative_to(fixture) and not path.is_relative_to(out)
        if bad:
            violations.append(str(path)); raise PermissionError("TEST_FIXTURE_ONLY isolation: "+str(path))
    sys.addaudithook(lambda e, a: audit(e, a) if active["enabled"] else None)
    prefix = "unit_gate" if units_only else "all_regression"
    success = False
    results = []
    cleanup = False
    try:
        groups = []
        if not units_only:
            groups = [(name, str(ROOT/"tests"/name), "test*.py", "TEST_FIXTURE_ONLY", None)
                      for name in (*inherited.SUITES, "formal_phase_a")]
            groups += [("scientific_review_units", str(ROOT/"tests/scientific_review"), "test_review_units.py", "TEST_FIXTURE_ONLY", None),
                ("scientific_review_full_artifacts", str(ROOT/"tests/scientific_review"), "test_review_full_artifacts.py", "READ_ONLY_ARTIFACT_VERIFICATION", None),
                ("phase_b_preparation_units", None, None, "TEST_FIXTURE_ONLY", "tests.phase_b_preparation.test_preparation.PreparationUnitTests"),
                ("phase_b_preparation_artifacts", None, None, "READ_ONLY_ARTIFACT_VERIFICATION", "tests.phase_b_preparation.test_preparation.PreparationArtifactTests")]
        groups.append(("formal_phase_b_units", None, None, "TEST_FIXTURE_ONLY", "tests.formal_phase_b.test_finalfit.FinalFitRunnerTests"))
        if not units_only:
            groups.append(("formal_phase_b_artifacts", None, None, "READ_ONLY_ARTIFACT_VERIFICATION", "tests.formal_phase_b.test_finalfit.FinalFitArtifactTests"))
        with (out/(prefix+"_results.txt")).open("x", encoding="utf-8", newline="\n") as stream:
            for name, location, pattern, scope, testname in groups:
                artifact["enabled"] = scope == "READ_ONLY_ARTIFACT_VERIFICATION"
                suite = unittest.defaultTestLoader.loadTestsFromName(testname) if testname else unittest.TestLoader().discover(location, pattern=pattern)
                stream.write("\nSUITE "+name+" SCOPE "+scope+"\n")
                result = unittest.TextTestRunner(stream=stream, verbosity=2).run(suite)
                item = {"suite": name, "scope": scope, "executed": result.testsRun, "failures": len(result.failures),
                    "errors": len(result.errors), "skipped": len(result.skipped), "pass": result.wasSuccessful() and not result.skipped}
                results.append(item); stream.flush(); print("TEST "+json.dumps(item), flush=True)
                if not item["pass"]: raise RuntimeError("STOP test failure: "+name)
            success = True
    finally:
        active["enabled"] = False
        gc.collect(); torch.cuda.empty_cache()
        if fixture.parent == parent and fixture.name.startswith("test_fixtures_"):
            shutil.rmtree(fixture); cleanup = not fixture.exists()
        summary = {"status": "PASS" if success and cleanup and not violations else "FAIL", "suites": results,
            "total_tests_executed": sum(r["executed"] for r in results),
            "current_regression_tests_executed": sum(r["executed"] for r in results if not r["suite"].startswith("formal_phase_b")),
            "new_formal_phase_b_tests_executed": sum(r["executed"] for r in results if r["suite"].startswith("formal_phase_b")),
            "TEST_FIXTURE_ONLY": True, "synthetic_completed_epoch_checkpoint_fixtures_only": True,
            "fixture_cleanup_success": cleanup, "fixture_root": str(fixture), "prohibited_accesses": violations,
            "all_baseline_and_BEST_unchanged": before == preserve(out), "FORMAL_OPTIMIZER_STEPS": 0,
            "2025_PIXELS_READ": 0, "PHASE_B_AUTHORIZED": False, "PHASE_B_FORMAL_TRAINING_STARTED": False,
            "completed_utc": runner.now()}
        save(out/(prefix+"_summary.json"), summary)
    if not success or not cleanup or violations: raise RuntimeError("Tests/fixture cleanup failed")


def report(out):
    manifest = read(out/"runner_manifest.json")
    smoke = read(out/"engineering_preflight.json")
    tests = read(out/"all_regression_summary.json")
    if smoke["status"] != "PASS" or tests["status"] != "PASS" or tests["current_regression_tests_executed"] != 210:
        raise ValueError("All required real execution and regression gates must pass")
    isolation_files = list(out.glob("preflight_isolation_*.json"))
    if len(isolation_files) != 1:
        raise ValueError("Exactly one completed isolation audit required")
    isolation = read(isolation_files[0])
    if (isolation["prohibited_accesses"] or not isolation["owned_temporary_cache_cleanup_success"]
            or isolation["owned_staging_files_remaining"] != 0 or not isolation["preservation_before_after_equal"]):
        raise ValueError("Preflight isolation/cleanup/preservation gate failed")
    preservation = preserve(out)
    if manifest["implementation_sha256"] != b.implementation_hashes():
        raise ValueError("Implementation changed since run initialization")
    status = {"state": "PHASE_B_FORMAL_RUNNER_IMPLEMENTATION_PREFLIGHT_CLOSURE_COMPLETED", "run_id": out.name,
        "PHASE_B_FORMAL_RUNNER_READY": True, "FORMAL_TRAINING_ENTRYPOINT_PROVIDED": True,
        "SINGLETON_ACTUAL_TAIL_LR_SMOKE_PASS": smoke["SINGLETON_ACTUAL_TAIL_LR_SMOKE_PASS"],
        "PHASE_B_AUTHORIZED": False, "PHASE_B_FORMAL_TRAINING_STARTED": False,
        "FORMAL_OPTIMIZER_STEPS": 0, "2025_PIXELS_READ": 0, "ENGINEERING_OPTIMIZER_STEPS": 2,
        "TOTAL_REGRESSION_TESTS_EXECUTED": tests["total_tests_executed"], "TEST_FAILURES": 0, "TEST_ERRORS": 0,
        "TEST_SKIPS": 0, "temporary_fixture_cleanup_success": tests["fixture_cleanup_success"],
        "preservation": preservation, "completed_utc": runner.now()}
    save(out/"final_status.json", status)
    a, tail = smoke["batches"]
    content = f"""# B0 Phase-B FinalFit runner implementation and preflight closure v1

Baseline: `{BASELINE}`. Independent audit run: `{out.name}`.

The formal entrypoint is `scripts/train_b0_phase_b_finalfit_v1.py`; production code is
`src/yuntapr/training/formal_phase_b.py`. This release implements a future authorized
eleven-epoch FinalFit and executes engineering preflight only. No formal fit was started.

## Locked scientific and engineering conventions

Fresh seed 2026; 23,447 pinned 2023/2024 identities; physical batch 2; no drop,
duplication, padding, replacement or accumulation. Each complete epoch has 11,724
updates and one singleton. Eleven epochs total 128,964 updates. Stateless scheduler
W=11,724 and U=586,200 preserve the 50-epoch horizon; warmup is unclamped.
Normalization SHA256: `{b.NORMALIZATION_SHA}`.
Manifest SHA256: `{b.MANIFEST_SHA}`. Architecture, focal alpha=0.5/gamma=2,
AdamW groups/config, BF16, FP32 raw quantiles, FP64 quantiles/pinball and clip norm 5
inherit the SHA-pinned protocol. No Phase-A model/optimizer/scheduler state is used.

## Checkpoint and resume semantics

Only completed-epoch boundaries can be saved. Coverage must prove 23,447 identities
exactly once, 11,724 updates and 80,423,210 supervised pixels per epoch. Checkpoints
keep LAST and final epoch-11 FINAL identities, never BEST. Older completed payloads
are retained locally; no selection uses training metrics or 2024 validation.
Resume verifies file size/SHA, run identity, all scientific/data/code/environment
provenance, boundary counters, coverage, finite tensor checksums, model shapes/dtypes,
AdamW groups/moments/step counters and RNG compatibility before applying states.
An interrupted partial epoch is discarded; resume begins the next complete epoch
from verified LAST. A completed FINAL cannot be reselected or retrained.

Local checkpoint root configured for future researcher authorization:
`{b.CHECKPOINT_ROOT}`. This engineering path is provisional pending researcher
confirmation; it grants no training authorization. No formal directory/checkpoint was
created or changed. Git stores identities, registry, hashes and history only; binary
payloads remain excluded by existing ignore rules.

## Actual ENGINEERING_ONLY preflight

Two independent fresh model/optimizer fixtures used the first full batch and actual
last singleton in the seed-2026 epoch-one permutation. Both executed real CUDA
forward, loss, backward, norm clipping and one optimizer step, then released all states.

| Real batch | Stateless scheduler u | LR | Actual supervised denominator |
|---|---:|---:|---:|
| batch2 | 1 | {a['LR']:.17g} | {a['valid_denominator']} |
| singleton batch1 | 11,724 | {tail['LR']:.17g} | {tail['valid_denominator']} |

Singleton LR equals Python float `1e-4` exactly, including its hexadecimal value.
No preceding 11,723 updates ran; each fixture's AdamW counter is exactly one.
Independent FP64 occurrence/quantile reduction references passed for both batches.
Raw sources were read-only through bounded English staging with source/copy SHA,
size checks and successful cleanup. All copy/read times and memory measurements
are in `engineering_preflight.json`. No formal checkpoint was generated and no
checkpoint state was loaded.

## Verification and limits

All current 210 regression tests plus {tests['new_formal_phase_b_tests_executed']} new
runner/artifact tests passed: {tests['total_tests_executed']} total, zero failures/errors/skips.
Fixture tests use tiny temporary models and synthetic completed-epoch schemas to
test eleven boundaries and exact next-update resume; they do not claim real full
FinalFit epochs were executed. Test binaries/optimizer artifacts were cleaned.
Real preflight validates three actual frozen source identities and two update paths.
The full formal eleven-epoch loop has not run; future authorized startup will verify
all 23,447 original B13 SHA identities and unique IMERG day identities, and verifies
source SHA/QC again during every runtime sample read. No 2025 pixels were read.
All {preservation['files_checked']} baseline files and the formal Phase-A BEST SHA remain unchanged.

## Future invocation and authorization

Set `PYTHONHASHSEED=2026`, `CUBLAS_WORKSPACE_CONFIG=:4096:8`,
`PYTHONUTF8=1`, `PYTHONDONTWRITEBYTECODE=1`; use the verified CUDA interpreter.
Engineering audit: `python -B scripts/train_b0_phase_b_finalfit_v1.py preflight --run-dir <new-audit-run>`.
Formal `train` and `resume --run-id <formal-run>` require a separate researcher-approved
`--authorization <file> --authorization-sha256 <sha>` and reject absent authorization
before raw I/O/model creation. The authorization must bind scope B0_PHASE_B_FINALFIT_ONLY,
fresh initialization, epoch budget, normalization, manifest, runner config, checkpoint
root and every implementation SHA. No such authorization was created this round.
There are no epoch/LR/batch/init-checkpoint/early-stop override flags.

## Final status

```json
{json.dumps(status, indent=2, ensure_ascii=False)}
```

STOP after publication. This result does not authorize Phase-B training or a next stage.
"""
    (out/"B0_PHASE_B_FORMAL_RUNNER_PREFLIGHT_CLOSURE_REPORT_v1.md").write_text(content, encoding="utf-8", newline="\n")
    artifacts = {p.name: {"sha256": sha256(p), "bytes": p.stat().st_size} for p in sorted(out.iterdir()) if p.is_file()}
    save(out/"artifact_sha256.json", artifacts)
    print(json.dumps(status), flush=True)


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("action", choices=["init", "units", "preflight", "tests", "report"])
    p.add_argument("--run-dir", type=Path)
    args = p.parse_args()
    if args.action == "init":
        if args.run_dir: raise SystemExit("init creates a new independent run")
        initialize()
    else:
        out = args.run_dir.resolve()
        if out.parent != PUBLIC.resolve() or not out.is_dir(): raise SystemExit("Invalid independent audit run")
        try:
            {"units": lambda: tests(out, True), "preflight": lambda: preflight(out),
             "tests": lambda: tests(out), "report": lambda: report(out)}[args.action]()
        except Exception as error:
            import traceback
            save(out/("failure_"+datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S_%fZ")+".json"),
                {"action": args.action, "error": repr(error), "traceback": traceback.format_exc(),
                 "PHASE_B_AUTHORIZED": False, "PHASE_B_FORMAL_TRAINING_STARTED": False, "FORMAL_OPTIMIZER_STEPS": 0})
            raise
