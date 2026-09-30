# Development B13 / IMERG QC audit

This is a read-only source audit for YunTAPR-Net B0. The frozen authority remains
`config/science_contract_v1.yaml` and
`docs/scientific_freeze/YUNTAPR_SCIENTIFIC_FREEZE_v1.md`. This audit compares
possible QC rules, but does not select a threshold, normalize model inputs,
train, run an optimizer step, write a checkpoint, or change the science contract.

The 2023 and 2024 March–October data are Development. The 2025 March–September
IMERG V07 Final data are checked for coverage only. October 2025 is an
unlabeled observation/inference period, not a V07 supervised blocker.

Use `F:\pytorch\Research\.venv\Scripts\python.exe` with `PYTHONPATH=src;.`.
Run `scripts/audit_development_qc.py scan-h` first with a *new* public
`docs/development_qc/runs/run_<UTC>` and matching local
`F:\pytorch\Research\outputs\development_qc\run_<UTC>` directory, the H09
source root, the frozen private mask path and the bounded English staging path.
Next run `scripts/audit_imerg_coverage.py` on the same directories with the
converted IMERG root and completion manifest. If the known 2024-03-02 00:10
H09 file is rejected only because it exceeds the standard 16 MiB single-file
cap, run `scripts/reconcile_b13_oversize.py` once; it verifies that one file
with a temporary 700 MiB cap and records the original and corrected audit
classification without changing B0 production staging. Then run
`scripts/finalize_development_qc.py`,
`scripts/real_multisample_qc_smoke.py`, the tests and
`scripts/package_development_qc.py` in that order. Each script requires
explicit paths and refuses to replace a completed run artifact.

The B13 reader stages one source file at a time to an ASCII path, verifies
copy size and SHA256, and cleans up only its own UUID temporary copy. The
original H: and F: source files are opened read-only. No month-wide copy is
retained. The per-frame B13 table, per-slot IMERG/pairing tables, exact
centikelvin histograms, and the 501×501 partial invalid-frequency map remain
in the local F: run. The public `manifest.json` records their paths, schemas,
row counts and SHA256. The repository contains only aggregate statistics and
hashes, never raw satellite/precipitation values or the private mask payload.

`EXPECTED_LATEST_SLOT_MISSING_BUT_OLDER_CAUSAL_EXISTS` is an explicit audit
state, not approval to use that older frame in formal samples. QC candidates
A–E are compared at exact-latest B13 / valid IMERG supervised-window grain;
fallback windows are excluded pending researcher decision. The first draft
candidate table used all B13 frames as its denominator. It was preserved in
local revision history and corrected with
`scripts/revise_qc_candidate_impact.py` before final packaging. The 20 mm/h
heavy-rate proxy and the 25-pixel spatial edge zone are
engineering comparisons, not frozen scientific thresholds. A valid IMERG
zero remains a valid no-rain target; missing is never interpreted as zero.

The report's statuses are evidence gates only. Formal training remains
unauthorized until the researcher decides the remaining QC, fallback, input
normalization and quantile stability questions in a separate decision update.
