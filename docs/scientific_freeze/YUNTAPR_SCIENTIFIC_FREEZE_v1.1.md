# YunTAPR-Net Scientific Freeze v1.1

Authority: researcher explicit approval in SCIENTIFIC FREEZE v1.1 + B0 QC CLOSURE + DECISION 8 NORMALIZATION.
Baseline: 890f5cecaa0a8f75f920e66e6d30381ae5c0ff04.

## Scope and inheritance

Scientific Freeze v1.1 supersedes v1 only for explicitly approved formal B0 QC,
input normalization, quantile numerical implementation, and engineering staging
rules. The v1 document, YAML, and every prior evidence run remain immutable.
The time, temporal product, spatial/SP04, split, probability/loss and backbone
definitions in D1–D7 are inherited without reinterpretation. The machine-readable
`formal_b0_supervision` section is a scoped override of the inherited general D5
partial/support rules for formal B0 supervision only. The inherited D1 general
latest-completed-observation definition is unchanged.

## Formal B0 QC closure

B0_FORMAL_SUPERVISED_B13_POLICY = FULL_SCENE_REQUIRED.
B13_PARTIAL_FORMAL_SUPERVISION_ALLOWED = false.
MASK_AWARE_INPUT_REQUIRED_FOR_B0_CORE = false.

A supervised candidate must have readable, metadata-valid B13 with all 251001
native pixels valid. PARTIAL remains preserved for observation, inference and
future robustness research; it cannot enter formal supervised B0. ALL_FILL,
corrupt and unreadable inputs are rejected. There is no interpolation, neighbor
fill, mask channel, backbone change or interpretation of 0 K as an observation.

For each IMERG window [T,T+30min), analysis_time=T+30min. The expected latest
nominal H09 slot is analysis_time−10min, from the audited ten-minute product
schedule; the actual observation must also satisfy obs_end<=analysis_time and
the unchanged D1 latest-completed rule. Nominal time alone does not prove causality.
OLDER_CAUSAL_FALLBACK_ALLOWED_FOR_FORMAL_SUPERVISION = false.
When the expected latest file is absent, reject formal supervision with
EXPECTED_LATEST_B13_MISSING_NO_FORMAL_FALLBACK, even if an older causal frame
exists. NO_CAUSAL_FRAME and TIME_METADATA_ERROR also reject formal supervision.

Phase A Train uses 2023 March–October, Validation uses 2024 March–October, both
with identical QC, expected-latest, causal, IMERG V07 Final time/grid/provenance
and nonempty valid Yunnan supervision requirements. Data eligibility is not
authorization to train. Partial/fallback records remain available as evidence.

## D8 — Input Normalization

Status: FROZEN. Policy: TRAIN_ONLY_Z_SCORE.
x_norm=(T_K−mu_train)/sigma_train; population standard deviation has ddof=0.
Phase A fits only final eligible 2023 Train sample native B13 pixels. 2024
Validation reuses these values without refitting; 2025 never fits normalization.
The numeric constants are DEVELOPMENT_DERIVED_PARAMETER, computed from exact
eligible raw pixels with a hash-identified sample manifest. The broader earlier
Development mean/std are not the final constants.

After architecture, hyperparameters, loss and epoch budget have been frozen in
Phase A, Phase B FinalFit recomputes statistics on eligible 2023+2024 samples.
2025 March–September Final Test must use those FinalFit statistics. FinalFit
statistics are not computed or authorized by this engineering task.

Runtime order is raw Kelvin → QC → eligibility → normalization → backbone.
The formal supervised route requires an entirely valid frame and verified
normalization metadata. Placeholder handling is confined to an explicitly
ENGINEERING_ONLY observation/fixture route. Cin remains 1.

## Quantile numerical implementation

The frozen softplus-positive-increment construction remains. Engineering v3
sets epsilon_mono=1e-4 in log1p(mm h^-1): delta_i=softplus(raw_i)+epsilon_mono,
q1=log1p(0.1)+delta_1 and q_i=q_(i-1)+delta_i. The runtime checks finite outputs,
q1>log1p(0.1), and strict adjacent increase. Any lost ordering at float32
precision must raise; no sort, rank relabel, clamp, or unapproved precision
change is allowed. Closure depends on measured stress results, not the presence
of epsilon alone. Physical-domain overflow also remains an explicit error.

## Bounded staging engineering v3

max_temporary_bytes=734003200 (700 MiB), one_file_at_a_time=true,
verify_sha256=true, cleanup_required=true, ASCII_staging_root_required=true.
The known 636106619-byte valid H09 file fits this explicit bound. A size-only
inventory verifies the maximum observed/verified valid file. A larger valid file
must be reported and an explicit larger fixed-margin cap documented. Sources
remain read-only and only owned UUID staging copies may be removed.

## Execution status

SCIENTIFIC_FREEZE_VERSION = v1.1
B0_FORMAL_SCIENTIFIC_CONTRACT = FROZEN
DECISION_8_NORMALIZATION = FROZEN
B0_FORMAL_SKELETON_IMPLEMENTED = true
B0_PARTIAL_B13_FORMAL_SUPERVISION_ALLOWED = false
B0_OLDER_CAUSAL_FALLBACK_ALLOWED = false
B0_MASK_AWARE_INPUT_REQUIRED = false
B0_FORMAL_TRAINING_STARTED = false
FORMAL_TRAINING_AUTHORIZED = false

Measured normalization, eligibility and numerical-stability readiness are recorded
in the new versioned reports; this contract does not claim those checks have passed.
