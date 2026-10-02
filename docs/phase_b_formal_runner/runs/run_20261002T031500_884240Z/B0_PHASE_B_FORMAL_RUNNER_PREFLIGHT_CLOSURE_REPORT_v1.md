# B0 Phase-B FinalFit runner implementation and preflight closure v1

Baseline: `08ebd685b7628489bdd5d1b1d20966c64702ffd4`. Independent audit run: `run_20261002T031500_884240Z`.

The formal entrypoint is `scripts/train_b0_phase_b_finalfit_v1.py`; production code is
`src/yuntapr/training/formal_phase_b.py`. This release implements a future authorized
eleven-epoch FinalFit and executes engineering preflight only. No formal fit was started.

## Locked scientific and engineering conventions

Fresh seed 2026; 23,447 pinned 2023/2024 identities; physical batch 2; no drop,
duplication, padding, replacement or accumulation. Each complete epoch has 11,724
updates and one singleton. Eleven epochs total 128,964 updates. Stateless scheduler
W=11,724 and U=586,200 preserve the 50-epoch horizon; warmup is unclamped.
Normalization SHA256: `c7042beac2412594ca9fc264d7df10981755b393158c539cb48c9b56cd314327`.
Manifest SHA256: `00e6bd018eae6aeb05be0740b55a92b7a5cc9a44b9ab2b80affbad3e3282ccff`. Architecture, focal alpha=0.5/gamma=2,
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
`F:\pytorch\Research\outputs\formal_training\b0_phase_b_finalfit`. This engineering path is provisional pending researcher
confirmation; it grants no training authorization. No formal directory/checkpoint was
created or changed. Git stores identities, registry, hashes and history only; binary
payloads remain excluded by existing ignore rules.

## Actual ENGINEERING_ONLY preflight

Two independent fresh model/optimizer fixtures used the first full batch and actual
last singleton in the seed-2026 epoch-one permutation. Both executed real CUDA
forward, loss, backward, norm clipping and one optimizer step, then released all states.

| Real batch | Stateless scheduler u | LR | Actual supervised denominator |
|---|---:|---:|---:|
| batch2 | 1 | 8.5295121119071997e-09 | 6860 |
| singleton batch1 | 11,724 | 0.0001 | 3430 |

Singleton LR equals Python float `1e-4` exactly, including its hexadecimal value.
No preceding 11,723 updates ran; each fixture's AdamW counter is exactly one.
Independent FP64 occurrence/quantile reduction references passed for both batches.
Raw sources were read-only through bounded English staging with source/copy SHA,
size checks and successful cleanup. All copy/read times and memory measurements
are in `engineering_preflight.json`. No formal checkpoint was generated and no
checkpoint state was loaded.

## Verification and limits

All current 210 regression tests plus 32 new
runner/artifact tests passed: 242 total, zero failures/errors/skips.
Fixture tests use tiny temporary models and synthetic completed-epoch schemas to
test eleven boundaries and exact next-update resume; they do not claim real full
FinalFit epochs were executed. Test binaries/optimizer artifacts were cleaned.
Real preflight validates three actual frozen source identities and two update paths.
The full formal eleven-epoch loop has not run; future authorized startup will verify
all 23,447 original B13 SHA identities and unique IMERG day identities, and verifies
source SHA/QC again during every runtime sample read. No 2025 pixels were read.
All 1621 baseline files and the formal Phase-A BEST SHA remain unchanged.

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
{
  "state": "PHASE_B_FORMAL_RUNNER_IMPLEMENTATION_PREFLIGHT_CLOSURE_COMPLETED",
  "run_id": "run_20261002T031500_884240Z",
  "PHASE_B_FORMAL_RUNNER_READY": true,
  "FORMAL_TRAINING_ENTRYPOINT_PROVIDED": true,
  "SINGLETON_ACTUAL_TAIL_LR_SMOKE_PASS": true,
  "PHASE_B_AUTHORIZED": false,
  "PHASE_B_FORMAL_TRAINING_STARTED": false,
  "FORMAL_OPTIMIZER_STEPS": 0,
  "2025_PIXELS_READ": 0,
  "ENGINEERING_OPTIMIZER_STEPS": 2,
  "TOTAL_REGRESSION_TESTS_EXECUTED": 242,
  "TEST_FAILURES": 0,
  "TEST_ERRORS": 0,
  "TEST_SKIPS": 0,
  "temporary_fixture_cleanup_success": true,
  "preservation": {
    "all_baseline_files_unchanged": true,
    "files_checked": 1621,
    "formal_BEST_sha256": "3f517f31394a4efa54ea0abed7757c7d59eb048416cfa98f02ab91ba60c24fe3",
    "phase_b_formal_checkpoint_root_unchanged": true
  },
  "completed_utc": "2026-10-02T03:22:42.767559+00:00"
}
```

STOP after publication. This result does not authorize Phase-B training or a next stage.
