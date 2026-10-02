# B0 Phase-B FinalFit formal runner v1

Completed release evidence: [run_20261002T031500_884240Z report](runs/run_20261002T031500_884240Z/B0_PHASE_B_FORMAL_RUNNER_PREFLIGHT_CLOSURE_REPORT_v1.md).

Entrypoint: `scripts/train_b0_phase_b_finalfit_v1.py`.
Library: `src/yuntapr/training/formal_phase_b.py`.
Regression additions: `tests/formal_phase_b/`.
Audit driver: `scripts/audit_b0_phase_b_runner_v1.py`.

The runner is implemented and engineering preflight is complete. Phase-B formal
training remains unauthorized and unstarted. Missing a separately approved,
SHA-pinned Phase-B authorization stops `train`/`resume` before raw reads, model
construction and formal output creation. No formal authorization was generated.

The frozen 23,447-scene manifest and Phase-B normalization are reused unchanged.
Batch2 and singleton each use the actual supervised pixel denominator. Actual
singleton preflight at stateless u=11,724 has LR exactly 1e-4, with one independent
temporary update and no preceding updates or formal checkpoint.

Only completed epochs produce LAST; epoch eleven also produces FINAL. No BEST,
validation selection, early stopping, epoch reselection, Phase-A state initialization,
2025 data access, or hyperparameter override exists. Binaries are excluded from Git.
The future checkpoint root is an engineering path awaiting researcher confirmation:
`F:\pytorch\Research\outputs\formal_training\b0_phase_b_finalfit`.

Full regression: 210 existing + 32 new = 242 tests, no failures/errors/skips.
Test fixture optimizer updates and synthetic completed-epoch schemas are isolated
from formal states. Actual FinalFit training and full eleven-epoch performance
remain unexecuted; readiness covers implementation, regression, resume fixtures
and two real engineering update paths.

Preserved development history:

- `run_20261002T030213_576338Z`: first 23-unit gate passed; superseded after scope
  metadata and interrupted-FINAL metadata recovery were completed.
- `run_20261002T030804_630430Z`: preflight stopped before GPU updates because
  PyTorch's initial temp-directory probe was blocked by the audit wrapper. Failure
  and isolation records remain intact. The wrapper now uses a caller-owned private
  cache and cleans it after execution.
- `run_20261002T031111_873337Z`: real preflight passed; full regression stopped at
  the historical no-optimizer-step-in-src AST guard. Its failure and real smoke
  evidence remain intact. Actual `optimizer.step()` was moved to the entrypoint,
  matching Phase-A structure; no old test or frozen file was modified.
- `run_20261002T031500_884240Z`: final production code, real preflight and all
  242 tests passed. Each successful smoke run has two ENGINEERING_ONLY updates;
  the retained earlier smoke plus the final smoke account for four actual temporary
  GPU updates across this implementation task. All formal optimizer steps remain zero.

Stop after publishing this release. A later researcher decision is needed to
authorize formal FinalFit.
