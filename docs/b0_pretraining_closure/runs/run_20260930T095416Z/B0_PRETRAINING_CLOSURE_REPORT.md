# B0 PRETRAINING CLOSURE REPORT — v1.1

Run: run_20260930T095416Z. Baseline: `890f5cecaa0a8f75f920e66e6d30381ae5c0ff04`. Scope: researcher-approved scientific
freeze synchronization, formal sample QC, exact train-only statistics and engineering
forward/backward verification. No model training is authorized or started.

**QC and Phase-A normalization are ready; quantile numerical stability is NOT CLOSED.**
Passing tests include verification that remaining precision failures raise loudly;
they do not establish that every extreme float32 tensor remains strictly ordered.

## FROZEN

Formal B0 requires the whole 501×501 B13 frame valid and the expected latest nominal
slot at analysis_time−10 minutes, with actual obs_end≤analysis_time and unchanged D1
latest-completed causality. Partial frames remain preserved for other research uses.
Missing latest slots cannot use an older causal replacement. Cin=1, backbone,
SP04 coordinates/membership, mask, IMERG product, split and scientific probability
definitions remain unchanged. D5's inherited generic unresolved partial/support
field is superseded for formal B0 by the explicit full-scene requirement.

Decision 8 is FROZEN: Train-only Z-score, population std (ddof=0). Its actual constants
are DEVELOPMENT_DERIVED_PARAMETER, not researcher-entered values. Phase A fits only
final-eligible March–October 2023 Train scenes; 2024 Validation reuses the result.

## Final sample population

| Quantity | 2023 Train | 2024 Validation |
|---|---:|---:|
| IMERG windows total | 11,760 | 11,760 |
| Expected latest available | 11,734 | 11,740 |
| Older-fallback windows rejected | 26 | 20 |
| Partial rejected | 14 | 13 |
| All-fill rejected | 0 | 0 |
| Unreadable rejected | 0 | 0 |
| Metadata rejected | 0 | 0 |
| Final eligible scenes | 11,720 | 11,727 |
| Yunnan supervised pixel observations | 40,199,600 | 40,223,610 |

The 23,520 Development windows are the candidate denominator, not the final usable
population. Exactly 46 missing-latest and 27 partial windows are excluded, leaving
23,447 scenes. The all-fill/unreadable zeros above are at the expected-latest paired
supervised-window grain; they do not contradict defects elsewhere in the full native
ten-minute inventory. No source file was deleted or filled.

The old local B13, IMERG and pairing indexes were SHA256-verified against the immutable
Development manifest. This run reread all 490 Development IMERG days and verified
48-slot time order, actual SP04 target coordinates, V07 Final metadata plus completion
manifest, and valid Yunnan pixels. All 11,720 fit B13 frames were reread and rechecked
for exact native coordinates, packing, full validity, source times and causality.
The remaining 2024 population QC uses the prior verified per-frame audit snapshot;
this run also reread a 2024 normalized smoke frame and the oversized valid frame.
Every runtime read repeats source QC. No claim is made that all 2024 B13 were reread.

## Exact Phase-A normalization

- Eligible scenes: 11,720.
- Native valid pixels: 2,941,731,720.
- Mean: 271.707819107373382 K.
- Population standard deviation: 19.896814653342556 K.
- Min / p1 / q1 / median / q3 / p99 / max: 177.1199951171875, 210.17999267578125, 262.3800048828125, 276.55999755859375, 286.30999755859375, 300.3699951171875, 324.510009765625 K.
- IQR: 23.92999267578125 K.
- Sample manifest SHA256: `dc0559f12f02817f8ec74916d03dd20e40ec0584ec58c59b34b5e02cc9a60e68`.

The fit decodes each raw packed pixel exactly as the runtime float32 reader, then uses
float64 arithmetic. An exact histogram over all int16 code points, with no rounding
or rebinning, gives moments and exact rank-interpolated percentiles. Independent
per-frame merged central moments agree within 1e-9 K. The old broader normalization
histograms were not read for this fit. The new JSON pins fit-code hashes, baseline,
source root, science contract, exclusions and sample list; engineering v3 pins its hash.
No 2024 or 2025 pixel enters fitting. 2025 receives only size-only inventory checks.

Runtime keeps raw Kelvin and normalized inputs separate. The formal-rule dataset
enforces QC and eligibility before normalization. Batch validation rejects raw Kelvin,
missing metadata and partial masks before `forward_formal` calls the backbone directly,
without placeholder substitution. The legacy engineering observation path remains
explicitly scoped. Phase-A normalization refuses 2025 use.

## Quantile stability: RESEARCHER_DECISION_REQUIRED

The implementation reads epsilon_mono=1e-4 from engineering v3 and applies the exact
sequential recurrence in log1p(mm h^-1). All ten requested constants from −100 through
100 pass: finite, strict increase, zero adjacent equality and finite gradients. The
seeded uniform [−100,100] case also passes. Random normal and signed-extreme cases
have 112 and 305 adjacent equalities respectively; a reproducible tensor of 22 raw
+100 channels followed by 10 raw −100 channels has 10 equalities. Every such runtime
call raises FloatingPointError. At q≈2200, float32 spacing is 0.000244140625, so the
approved 0.0001 increment can be rounded away. No sorting, clamp, rank relabel,
precision change or epsilon adjustment was introduced. Gradients of the diagnostic
recurrence are finite, but that does not repair ordering.

`QUANTILE_NUMERICAL_STABILITY_CLOSED=false`. Researcher review of a precision strategy
or approved admissible raw domain is needed before a universal closure claim. Large
positive log quantiles also overflow physical expm1 independently; the head keeps its
explicit physical-finiteness error. This report does not silently change either rule.

## Real execution and staging

Real 2023-03-01 and 2024-03-01 00:00 UTC windows pass raw B13 → QC → formal eligibility
→ the same 2023 normalization → backbone → frozen SP04 → probability heads → masked
loss → backward. Each has 3430 valid Yunnan loss pixels and all 74 parameter-tensor
gradients finite. Execution and temporary focal alpha=0.25/gamma=2.0 are engineering
tests only; there was no optimizer update or checkpoint. Real partial and missing
latest/older-causal cases are rejected before the backbone. Source hashes are unchanged.
The first successful singleton-context smoke is preserved separately; the final smoke
uses indexed six-slot context so older-frame availability is accurately represented.

MAX_VALID_B13_FILE_BYTES=636106619.
Configured cap=734003200 bytes (700 MiB), margin=97896581
bytes, exceeding a fixed 32 MiB safety allowance. The real largest file was staged,
SHA256-verified, read as 251001 valid pixels, and cleaned successfully. Only owned UUID
temporary files under the ASCII staging root were removed; earlier diagnostic caches
and all raw data remain intact. Readers are sequential, one active staging instance.

Fit wall time: 517.878 s. The 12,210 fit/revalidation
copies used 160.420 s copy time and 244.737 s read/QC/statistics
time; per-source logs include bytes and cleanup. SHA verification adds two reads outside
copy_seconds. Fit temporary peak was 6387344 bytes; the separate large-file
smoke peak was 636106619 bytes. No package was installed/upgraded.

## Verification and remaining work

100 tests passed: historical scientific v1=42, skeleton=20, Development QC=8,
new v1.1=30. The skeleton fixture now explicitly selects historical v1 so its original
v2 assertions remain meaningful. All protected tracked historical evidence is unchanged
against the baseline, and prior public Development hashes were reverified.

NOT_YET_FROZEN / NOT_COMPUTED: focal alpha/gamma, Phase-A selected hyperparameters and
epoch budget, and Phase-B FinalFit normalization. Phase B must recompute on eligible
2023+2024 only after the Phase-A protocol is fixed; Final Test 2025 Mar–Sep must reuse
that FinalFit artifact. No next stage is started by this run.

## Final status

```text
SCIENTIFIC_FREEZE_VERSION = v1.1
B0_FORMAL_SCIENTIFIC_CONTRACT = FROZEN
DECISION_8_NORMALIZATION = FROZEN
B0_FORMAL_SKELETON_IMPLEMENTED = true
B0_PARTIAL_B13_FORMAL_SUPERVISION_ALLOWED = false
B0_OLDER_CAUSAL_FALLBACK_ALLOWED = false
B0_MASK_AWARE_INPUT_REQUIRED = false
QUANTILE_NUMERICAL_STABILITY_CLOSED = false
PHASE_A_NORMALIZATION_READY = true
PHASE_A_SAMPLE_ELIGIBILITY_READY = true
B0_FORMAL_TRAINING_STARTED = false
FORMAL_TRAINING_AUTHORIZED = false
```
