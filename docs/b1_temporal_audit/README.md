# B1 temporal audit v1

Completed run: `run_20261003T035724_142784Z`. Read [full audit report](runs/run_20261003T035724_142784Z/B1_TEMPORAL_DATA_AUDIT_REPORT_v1.md) and [researcher decision packet](../b1_scientific_design/B1_SCIENTIFIC_DESIGN_DECISION_PACKET_v1.md).

Raw B13 QC actually completed in `run_20261003T024550_523841Z`; its final registry failed on a CLI str/Path mismatch. That failure run remains immutable. The current run is an independent metadata-only closure with the full predecessor hash snapshot and original code copies. It copies QC/identity CSVs, reconciles them and executes artifact tests with zero raw-source opens. The corrected CLI supplies a pathlib.Path. The predecessor audit-hook terminal counter was not captured; its instrumented staging read counters were saved and independently reconciled.

Approved offsets before A=T+30min: `[60,50,40,30,20,10]` minutes; oldest-to-latest `[B,6,501,501]` B13 only. Real CF `obs_start <= obs_end <= A` is required for the complete-causal candidate classification. Expected scan bucket is diagnostic only.

Scope: 2023/2024 March–October only. February context is OUTSIDE_AUDIT_SCOPE, never silently missing. All 2025 raw/IMERG/checkpoints/model operations are blocked. No normalization fitting, B1 training or B0 reevaluation.

The published audit is reproducible as an additions-only evidence run: original execution baseline `4286f8151fea2185c99b3cea0c8e532e8cd90070`, approval/definition/code SHA recorded before source access. Its reader refuses execution from a different HEAD and refuses reuse of a started/completed/failed run. Do not bypass these guards to rerun it. A future approved run needs its own execution identity binding and independent output directory; the frozen slot definition remains fixed unless the researcher explicitly revises it.

Original command (record only):

```powershell
& 'F:\pytorch\Research\.venv-cuda\Scripts\python.exe' scripts/audit_b1_temporal_v1.py `
  --definition config/b1/b1_six_slot_audit_definition_v1.json `
  --definition-sha256 b6887a59900aa2f736cec4ab0d8727511e59eb9fc4e0418ebcb7d71778cd66d4 `
  --run-directory docs/b1_temporal_audit/runs/run_20261003T024550_523841Z `
  --staging-root 'F:\pytorch\Research\stage0_himawari\cache\staging\b1_temporal_run_20261003T024550_523841Z'
```

Only one caller-owned English staging file is active. Copy size and raw/staged SHA are checked before netCDF4 reads. Source-copy read and temporary-write bytes, source-hash read bytes, copy/read seconds and cleanup are accounted separately; staged-hash reads and filesystem overhead remain in elapsed time. No permanent bulk raw duplicate. Staging root and five historical backend diagnostic caches are preserved; only owned temporary files are cleaned.

Input/output fields are QC/identity metadata. B13 validity checks read B13 pixels but do not fit or summarize their distribution; raw IMERG is not opened. Target validity uses pinned 2023/2024 historical evidence only. All six-slot candidate and intersection CSVs explicitly remain non-formal until researcher decisions.

Tests: `python -m unittest tests.b1_temporal_audit.test_b1_temporal_audit tests.b1_temporal_audit.test_full_audit_artifacts` with `src` and repo on PYTHONPATH; full artifact tests intentionally fail without completed actual run. Closure additionally executed 10 relevant existing data/spatial tests. Synthetic NetCDF fixtures are English-path, caller-owned and removed after use. Initial failed tests and cleanup records are kept; NOT_RUN is never a PASS.

`B1_DESIGN_FROZEN=false`. Pending: missing policy, normalization, primary fairness population. 2025 outcomes remain sealed. STOP; no next-stage authorization.
