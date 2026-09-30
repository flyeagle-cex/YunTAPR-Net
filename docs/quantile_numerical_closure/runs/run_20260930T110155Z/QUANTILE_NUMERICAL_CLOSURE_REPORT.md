# YunTAPR-Net Quantile Numerical Closure v1

Run: `run_20260930T110155Z`. Baseline: `957e8519e8063a6174b7bced5f10a819be0ef64e`. Scientific Freeze remains **v1.1**.
This is an engineering precision change. The SHA256 of the scientific v1.1 contract
is unchanged; no D1–D8 definition or model parameterization was altered.

## Result

**QUANTILE_NUMERICAL_STABILITY_CLOSED = true** for the specified
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
excluded from this test family. All 14 cases have finite float64
qlog, strict adjacent increase, zero equal pairs and finite raw gradients. In the
old 22×(+100) then 10×(−100) counterexample, the minimum observed log increment
is 0.000100000000202,
and the equal count is 0. The previous float32 run recorded 10 equalities in this
case; its report remains immutable historical evidence.

| Case | qlog dtype | Equal adjacent | Strict | Finite gradient |
|---|---|---:|---|---|
| constant_-100 | torch.float64 | 0 | True | True |
| constant_-80 | torch.float64 | 0 | True | True |
| constant_-40 | torch.float64 | 0 | True | True |
| constant_-20 | torch.float64 | 0 | True | True |
| constant_-10 | torch.float64 | 0 | True | True |
| constant_0 | torch.float64 | 0 | True | True |
| constant_10 | torch.float64 | 0 | True | True |
| constant_40 | torch.float64 | 0 | True | True |
| constant_80 | torch.float64 | 0 | True | True |
| constant_100 | torch.float64 | 0 | True | True |
| random_uniform_minus100_plus100 | torch.float64 | 0 | True | True |
| random_normal_sigma100 | torch.float64 | 0 | True | True |
| random_signed_100 | torch.float64 | 0 | True | True |
| mixed_22_positive100_then_10_negative100 | torch.float64 | 0 | True | True |

## FULL_PHYSICAL_HEAD_STRESS

With a moderate synthetic raw bias +20, float64 physical quantiles are finite.
With +100 across 32 channels, qlog is finite and strictly increasing up to
3200.098510, while expm1 overflows float64. The observed runtime
error is `QUANTILE_PHYSICAL_OVERFLOW: expm1(qlog) nonfinite`. This is the expected explicit physical
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
| scientific_freeze | 42 | PASS |
| b0_skeleton | 20 | PASS |
| development_qc | 8 | PASS |
| scientific_freeze_v1_1 | 30 | PASS |
| quantile_numerical_closure | 14 | PASS |

Total: 114 tests. Old Scientific Freeze, B0 skeleton, Development
QC and v1.1 reports/configurations were preserved. Engineering v4 is a separate
config with a pinned copy in this run. The manifest records source/code/artifact
SHA256 hashes. PyTorch version: 2.14.0+cpu; interpreter: `F:\pytorch\Research\.venv\Scripts\python.exe`.

## Final status

```text
SCIENTIFIC_FREEZE_VERSION = v1.1
QUANTILE_NUMERICAL_STABILITY_CLOSED = true
B0_FORMAL_TRAINING_STARTED = false
FORMAL_TRAINING_AUTHORIZED = false
```

Stop after GitHub synchronization. Phase-A training is outside this task.
