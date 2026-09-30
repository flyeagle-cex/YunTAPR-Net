# B0 pretraining closure v1.1

Current evidence: [run_20260930T095416Z](runs/run_20260930T095416Z/B0_PRETRAINING_CLOSURE_REPORT.md).
Scientific authority: [v1.1](../scientific_freeze/YUNTAPR_SCIENTIFIC_FREEZE_v1.1.md).
Historical v1 documents, configurations and all previous evidence runs remain immutable.

## Runtime

Use the existing `F:\pytorch\Research\.venv\Scripts\python.exe`; no packages were upgraded.
Set `PYTHONPATH=src`. The default contract loader selects science v1.1 / engineering v3;
`load_contract(version="v1")` remains available for historical checks.

Load `PhaseANormalizer.from_pinned()`, which validates the statistics artifact and
sample-list SHA256. Construct `B0Dataset(..., formal_supervised=True,
normalizer=normalizer, frozen_mask_path=...)` with source-verified readers and
provenance. `x_b13` remains raw Kelvin; `x_b13_normalized` is a separate field.
`B0Batch.from_formal_samples(...)` and `model.forward_formal(batch)` require complete
native validity, causal expected-latest eligibility, supervised labels, and verified
normalized tensors before entering the backbone. The helper
`formal_rules_engineering_forward_step` supports forward/loss/backward only.
Its focal values in this run are ENGINEERING_TEST_ONLY, never frozen hyperparameters.

The legacy `model(x, valid_mask)` observation route is ENGINEERING_ONLY. Its
nonphysical placeholder with a validity sidecar remains available for fixtures and
partial observation use. It must not be used to bypass the formal sample contract.
The `older_causal_available` field describes the supplied indexed frame context;
production record builders must provide that context explicitly. The final real
smoke supplies the expected slot and preceding five ten-minute slots.

## Reproduction and safeguards

Run these four suites independently from the repository root:

```powershell
$env:PYTHONPATH='src'
& 'F:\pytorch\Research\.venv\Scripts\python.exe' -m unittest discover -s tests/scientific_freeze -p 'test_*.py' -v
& 'F:\pytorch\Research\.venv\Scripts\python.exe' -m unittest discover -s tests/b0_skeleton -p 'test_*.py' -v
& 'F:\pytorch\Research\.venv\Scripts\python.exe' -m unittest discover -s tests/development_qc -p 'test_*.py' -v
& 'F:\pytorch\Research\.venv\Scripts\python.exe' -m unittest discover -s tests/scientific_freeze_v1_1 -p 'test_*.py' -v
```

The generation scripts are `freeze_v1_1_build_contracts.py`,
`fit_phase_a_v1_1.py`, `pin_normalization_v1_1.py`,
`quantile_stress_v1_1.py`, `real_normalized_smoke_v1_1.py`,
`run_all_tests_v1_1.py` and `package_closure_v1_1.py` under `scripts/`.
The initial builder refuses existing v1.1 destinations. For a new audit, use a new
run directory and preserve this run; do not silently repin completed artifacts.
The fit uses hash-verified local Development indexes and the fixed H:/F: data roots.
The repository contains counts, manifests, hashes and aggregate statistics only,
not satellite fields, precipitation fields or restricted mask/boundary payloads.

Staging is ASCII, one file per sequential reader, size and SHA256 verified,
with a 734003200-byte cap. This workflow uses one staging instance at a time;
parallel readers must not share the staging root. Only the instance's owned UUID
copies are removed; raw sources and earlier backend diagnostic caches are retained.
Cleanup failure is logged, raises on the v3 route, and blocks additional copies.
The cap exceeds the largest verified file (636106619 bytes) by 97896581 bytes.
The normalization run made 12210 copies (490 IMERG days + 11720 B13 frames), taking
160.420 seconds of copying and 244.737 seconds of read/QC/statistics time, with
517.878 seconds wall time including inventory, hashing and bookkeeping. Copy timing
does not include the two SHA256 reads. These costs are the Unicode-path workaround.
The large-file smoke separately exercised the full 636106619-byte temporary copy.

## Interpretation

The 23520 Development windows are the candidate denominator. Seventy-three fail
the final formal-B0 rule (46 missing latest, 27 partial), leaving 23447 scenes.
Formal normalization uses only the 11720 eligible 2023 scenes; no 2024/2025 fitting.
FinalFit 2023+2024 statistics remain uncomputed until the Phase-A protocol is fixed.
2025 Test must use FinalFit statistics; the Phase-A runtime rejects that use now.

Specified constant quantile stresses pass, but some random/mixed extreme tensors
still lose strict float32 ordering. The runtime guard passes by refusing those
tensors; this is distinct from claiming numerical closure. The report records
`QUANTILE_NUMERICAL_STABILITY_CLOSED=false` and requires researcher review.
No optimizer update, checkpoint, Phase-A training or next-stage execution occurred.
