# SCIENTIFIC FREEZE V1.1 REPORT

Run: run_20260930T095416Z_v1_1. Baseline: `890f5cecaa0a8f75f920e66e6d30381ae5c0ff04`.
Authority: the researcher's explicit v1.1 / B0 QC / Decision 8 approval.

## Approved synchronization

New document: `docs/scientific_freeze/YUNTAPR_SCIENTIFIC_FREEZE_v1.1.md`.
New contract: `config/science_contract_v1.1.yaml`.
New engineering configuration: `config/b0_engineering_v3.yaml`.
Historical v1 documents, configurations and evidence are unchanged. D1–D7 dictionaries
remain exactly equal; scoped formal B0 QC overrides and D8 are explicit additions.
The active loader uses v1.1 and supports explicit historical v1 loading.

FROZEN: formal B0 whole-frame validity; expected-latest required with no older fallback;
Decision 8 Train-only Z-score; v3 epsilon recurrence and bounded staging engineering.
The original D1 general causality remains unchanged. Partial data are preserved and
no mask channel/backbone change was introduced. The decision CSV distinguishes inherited
v1 statuses from the current formal-B0 scope to avoid leaving the resolved partial policy
apparently open.

The exact 2023 eligible fit has 11,720 scenes and
2,941,731,720 native pixels: μ=271.7078191073734 K,
σ=19.896814653342556 K, ddof=0. These are derived parameters with a pinned sample manifest,
not manually frozen scientific numbers. 2024 Validation uses the identical artifact;
Phase B / 2025 Final Test rules are recorded without computing FinalFit statistics.

## Measured closure and limits

Formal sample counts are 11720 Train and 11727 Validation; 46 fallback windows and
27 partial windows are excluded from 23520 candidates. The real normalized 2023/2024
chain, real rejection examples, largest-file staging, and all 100 tests executed.
No formal training, optimizer update, checkpoint or 2025 fitting occurred.

RESEARCHER_DECISION_REQUIRED: epsilon=1e-4 passes every requested constant stress but
does not guarantee strict order for mixed extreme float32 tensors. Random failures and
a deterministic counterexample raise explicitly. Numerical stability is **not closed**;
passing guard tests must not be presented as universal numerical success.

NOT_YET_FROZEN / NOT_COMPUTED: focal alpha/gamma and Phase-A model selection parameters;
FinalFit statistics await the required protocol freeze. Training is unauthorized.

Full results: `docs/b0_pretraining_closure/runs/run_20260930T095416Z/B0_PRETRAINING_CLOSURE_REPORT.md`.
Integrity and artifact hashes are in the two run manifests. Stop after GitHub sync.

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
