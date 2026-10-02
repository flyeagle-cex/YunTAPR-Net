# B0 2025 Final Test protocol / preflight v1

Current status: protocol frozen, runner preflight passed, **2025 Final Test is not authorized or executed**. No 2025 raw source was opened. The latest complete evidence is `preflight/run_20261002T152029_621524Z/` (60 tests, zero failures/errors/skips). The earlier 57-test run and both engineering probe failure records remain as history.

Read `B0_2025_FINAL_TEST_PROTOCOL_FREEZE_PREFLIGHT_REPORT_v1.md` for the complete Chinese report; the matching `.tex` is editable and `.pdf` is a compiled, visually checked copy. `B0_2025_FINAL_TEST_PROTOCOL_v1.md` describes the frozen machine protocol. The YAML is at `config/evaluation/b0_2025_final_test_protocol_v1.yaml`, SHA256 `6d08def2602dda3d931937c68cadeae86b5c16b60f9f7132c9e134b962cdbe3b`.

## Terminology

Population means the complete set of eligible evaluation scenes. Pixel metrics accumulate raw numerators and valid-pixel-observation denominators across that set; the same grid cell at different times is counted separately. Conditional metrics use valid rainy pixel observations. Denominators are observation counts, not scene counts or geographically deduplicated cell counts. The Chinese terms are 评价样本全集 and 全样本评价. This documentation correction changes no metric, data, code, test or authorization.

## Entrypoint

From the repository root, the authorized action is:

```powershell
& 'F:\pytorch\Research\.venv-cuda\Scripts\python.exe' scripts/test_b0_2025_final_v1.py preflight
```

It creates a new independent UTC evidence directory, checks all baseline identities, runs synthetic/schema and inference-only regressions, verifies frozen FINAL read-only, and forwards synthetic input only. It never discovers or opens 2025 raw files. The report compiler uses existing XeLaTeX with `--disable-installer`; no environment packages were changed.

The separate `run` action is implemented for a future authorization. **It must not be used under this release.** It requires `--authorization`, its SHA256 and `--population`; the researcher authorization must bind the immutable protocol, runner/module, sole FINAL, normalization, and all 10,272 scheduled candidate windows. Missing authority is rejected before population/source/FINAL I/O. No authorization artifact or real 2025 population catalogue is created here.

## Frozen semantics

March-September 2025 UTC window starts only; October source files rejected. Full-scene latest-causal B13 with no older fallback, V07 Final IMERG with masked partial-valid Yunnan supervision, fixed order and exactly-once coverage. Full-population raw-sum metric accumulation, exact tied AUROC/AP and inherited 2024 diagnostics. POD/FAR/CSI remain THRESHOLD_NOT_FROZEN. Model and normalization are immutable; no optimizer, backward, training, selection or calibration.

## Actual test scope

44 new unit/schema/guard/accumulator tests + 6 new artifact tests + 10 existing inference-only regressions = 60. The historical 254 training/resume tests were not rerun because they contain operations prohibited in this task. Their historical evidence is unchanged. Current fixture tests have zero actual optimizer creations/steps and zero backward calls. Guard rejection probes are not training operations.

`artifact_sha256.json` in the latest preflight evidence directory identifies every original evidence file. The original `delivery_artifact_sha256.json` and `report_render_verification.json` are immutable records for commit `299d3f1080840b24db3ba6fe39684a1e6bca530a`. The current terminology-only document revision, rendering verification and current document hashes are recorded separately under `documentation_corrections/run_20261002T155531_123259Z/`; the historical preflight was not rerun. No checkpoint/model/optimizer binary, source data, staging cache or environment is published. Stop after publishing this preflight release.
