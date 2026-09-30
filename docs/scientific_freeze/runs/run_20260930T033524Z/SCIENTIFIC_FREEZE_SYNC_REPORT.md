# Scientific Freeze Synchronization Report

**Run:** `run_20260930T033524Z`  
**Authority:** explicit researcher decisions D1–D7, 2026-09-30  
**Result:** `B0_FORMAL_SCIENTIFIC_CONTRACT=FROZEN`; `B0_FORMAL_TRAINING_STARTED=false`  
**Next phase:** `FORMAL_B0_SKELETON_IMPLEMENTATION`

The approved rules are now [human-readable](../../YUNTAPR_SCIENTIFIC_FREEZE_v1.md) and [machine-readable](../../../../config/science_contract_v1.yaml) in GitHub source. Earlier Stage-0, smoke, readiness and candidate reports were not modified. Their unresolved D1–D7 candidate labels are superseded by the later researcher decision; their measurements and data-gap evidence remain historical records.

| ID | Decision | Status | Remaining numerical/configuration item |
|---|---|---|---|
| D1 | Time Contract | FROZEN | none |
| D2 | Temporal Data Role and IMERG Product | FROZEN | none |
| D3 | Spatial Contract | FROZEN | feature_reduction_operator_ENGINEERING_CONFIG |
| D4 | Split Contract | FROZEN | phase_a_estimated_epoch_budget |
| D5 | Missing and QC Principles | FROZEN_PRINCIPLES | partial_support_thresholds_DEVELOPMENT_ESTIMATED_PARAMETER |
| D6 | Probability Core | FROZEN | focal_alpha_focal_gamma_DEVELOPMENT_ESTIMATED_PARAMETER |
| D7 | Formal B0 Backbone | FROZEN | groupnorm_groups_ENGINEERING_CONFIG |

The SP04 axes were copied from SHA-verified actual float32 coordinate evidence, not regenerated from nominal increments. The v1 map contains 10,000 unique target cells and 25 native centers per cell under explicitly float32-rounded center-derived edges and `[south,north) × [west,east)` ownership. It matches the prior candidate map row-for-row. Native input retains all 501×501 centers; direct feature aggregation excludes native north row 0 and east column 500. The frozen Yunnan evaluation mask remains 3430 cells with SHA256 `9d921def661fc3e58cd1ed783fcf87abbf493da6ae5e5fea79c28043f73495ef` and is not redistributed.

The frozen mask file's ancillary bounds yield 4/5/6 raw float64 center counts along either axis (11/78/11 cells); they are not this feature-membership rule. This difference is disclosed in v1 and does not alter the mask. The mapping CSV SHA256 is `3f4dea000efa0146cec292578bca07c370f897328c933e804346097f8ab9d3fd`; the axis CSV SHA256 is `994705240ef12b2fbd6438a678f18c6e8f7687fe238ee45e7af16299eeeef0c5`. `config/spatial/sp04_coordinate_manifest_v1.json` records source and axis hashes.

**Checks:** 42 repository-self-contained unit tests PASS; 17 local Markdown links resolve; historical `stage0-b0-evidence` files show no tracked modifications. No data split, train statistics, model initialization/training, 2025 Test tuning, original-file mutation, or GADM geometry/mask publication occurred. Parameters still marked `DEVELOPMENT_ESTIMATED_PARAMETER` or `ENGINEERING_CONFIG` have no scientific numeric default and must be recorded before formal training.
