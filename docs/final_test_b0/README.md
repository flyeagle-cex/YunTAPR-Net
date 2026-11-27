# B0 2025 Final Test protocol / preflight / execution v1.1

Current status: protocol v1.1 frozen; 2025 catalogue QC executed and frozen on 2026-10-03; **the one-shot 2025 Final Test was executed once on 2026-11-27 under explicit researcher authorization**, with zero training, zero parameter updates, zero retries. No further 2025 run is authorized. The execution evidence is `formal_v1_1/run_20261127T050003.131968Z/`; the public receipt is `formal_v1_1/B0_2025_FINAL_TEST_RESULTS_v1_1.json`; the Chinese execution report is `B0_2025_FINAL_TEST_EXECUTION_REPORT_v1.{md,tex,pdf}` with `report_render_verification_final_v1.json`.

Protocol files: `config/evaluation/b0_2025_final_test_protocol_v1.1.yaml` (SHA256 `b1be82d5bc03293c35ddc793faa1187e97fa48c537039181c0eb68a689f15eb8`), `config/evaluation/b0_2025_final_test_authorization_v1.1.json` (SHA256 `ada75ca5de75c84c3515bca960a53d76de7796673d90dc1332b2b835765d9855`). `B0_2025_FINAL_TEST_PROTOCOL_v1.1.md` describes the frozen machine protocol; the earlier v1 preflight report (`B0_2025_FINAL_TEST_PROTOCOL_FREEZE_PREFLIGHT_REPORT_v1.*`, protocol v1 SHA256 `6d08def2…`) remains as history.

Frozen identity used by the executed test: FINAL `F:/pytorch/Research/outputs/formal_training/b0_phase_b_finalfit/run_20261002T035929_487644Z/epoch_011.pt` (SHA256 `05359d2e…`, 52,071,595 bytes, epoch 11, global update 128,964), normalization SHA256 `c7042bea…`, candidate catalogue `b1100610…` (10,272 windows), eligible population `53ce28a5…` (10,244 scenes, 28 rejected), catalogue freeze record `0fe49958…` (freeze_completed_utc `2026-10-03T02:19:33.679048+00:00`).

## Execution summary (2026-11-27)

| Item | Value |
|---|---:|
| eligible scenes | 10,244 |
| valid pixel observations | 35,136,920 |
| rainy pixel observations | 4,882,555 |
| global core loss | 0.05151132978268864 |
| occurrence loss | 0.033797817841140915 |
| quantile loss | 0.017713511941547723 |
| Brier | 0.09896918546879455 |
| AUROC | 0.8972174938962962 |
| Average Precision | 0.6059135116913023 |
| conditional mean pinball | 0.12747388447425723 |
| mean absolute coverage error | 0.013060728770592453 |
| crossing / nonfinite / support violation | 0 / 0 / 0 |
| POD / FAR / CSI | THRESHOLD_NOT_FROZEN |
| model parameters updated / optimizer steps / backward | false / 0 / 0 |

Source reads: B13 45,639,682,705 B + 214 IMERG day files 179,318,880 B = 45,819,001,585 B; `raw_source_open_events=51,434`; run elapsed 1,676.59 s wall; 5 artifact files with SHA256 recorded in the receipt; a local independent read-only audit passed 197 checks (`VERIFY_B0_FINAL_TEST_OK`).

Disclosure: the non-frozen diagnostic proxy `DIAGNOSTIC_PROXY_METRIC` shows numerical overflow in this run; it is not an exact expected precipitation, is not used for any selection, gate or claim, and the run was not altered or repeated because of it (see report §5).

Evidence boundary: one frozen FINAL model only; IMERG V07 Final is a reference, not truth; no POD/FAR/CSI thresholds; no event-level attribution; 2025 outcomes must not be used for tuning, selection or calibration; this release does not claim B1–B8, DOTE/DTFM physical attribution or innovation-chain final-test results.

## Terminology

Population means the complete set of eligible evaluation scenes. Pixel metrics accumulate raw numerators and valid-pixel-observation denominators across that set; the same grid cell at different times is counted separately. Conditional metrics use valid rainy pixel observations. Denominators are observation counts, not scene counts or geographically deduplicated cell counts. The Chinese terms are 评价样本全集 and 全样本评价. This documentation correction changes no metric, data, code, test or authorization.

## Entrypoint

From the repository root, the authorized one-shot action was:

```powershell
& 'F:\pytorch\Research\.venv-cuda\Scripts\python.exe' -B scripts\test_b0_2025_final_v1_1.py run `
  --authorization config\evaluation\b0_2025_final_test_authorization_v1.1.json `
  --authorization-sha256 ada75ca5de75c84c3515bca960a53d76de7796673d90dc1332b2b835765d9855 `
  --candidate-catalogue <frozen candidate catalogue CSV> `
  --eligible-population <frozen population manifest CSV> `
  --catalogue-freeze-record <frozen catalogue freeze record JSON>
```

The earlier v1 preflight action (`scripts/test_b0_2025_final_v1.py preflight`) remains documented in the historical preflight report. The legacy v1 `run` action has no authority. A future repeat of any final-test stage would require a new protocol/authorization cycle; this directory provides no such authorization.

## Frozen semantics

March-September 2025 UTC window starts only; October source files rejected. Full-scene latest-causal B13 with no older fallback, V07 Final IMERG with masked partial-valid Yunnan supervision, fixed order and exactly-once coverage. Full-population raw-sum metric accumulation, exact tied AUROC/AP and inherited 2024 diagnostics. POD/FAR/CSI remain THRESHOLD_NOT_FROZEN. Model and normalization are immutable; no optimizer, backward, training, selection or calibration.

## Evidence history

The v1 protocol freeze/preflight evidence (`preflight/run_20261002T152029_621524Z/`, 60 tests, zero failures) and its `delivery_artifact_sha256.json` / `report_render_verification.json` for commit `299d3f1080840b24db3ba6fe39684a1e6bca530a` remain immutable history. The 2025 catalogue QC run `catalogue_gate_v1_1/catalogue_only_runs/run_20261003T015507_526850Z/` preserves its own authorization binding and telemetry. This execution added only: the v1.1 authorization file, the `formal_v1_1/run_20261127T050003.131968Z/` artifacts, the public receipt, the execution report and its render verification. No checkpoint/model/optimizer binary, source data, staging cache or environment is published.
