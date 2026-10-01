# B0 Phase-A formal run authorization v1

Researcher authorization is limited to B0 Phase-A, seed 2026, Protocol v1.0. Train: 11720 frozen eligible 2023 March–October identities; Validation: 11727 frozen eligible 2024 March–October identities in pinned order. No 2025 sources, Phase-B, normalization fitting, B1–B8, search, or protocol edits are authorized.

The protocol's historical false authorization fields remain immutable. The separate run overlay records FORMAL_TRAINING_AUTHORIZED=true, B0_FORMAL_TRAINING_STARTED=false at authorization time; run status records the actual start only after all preflight gates pass. AUTHORIZED_BY=RESEARCHER; AUTHORIZED_SCOPE=B0_PHASE_A_ONLY; PHASE_B_AUTHORIZED=false; B1_TO_B8_AUTHORIZED=false.

Baseline: `aa65a5b4b33f04d7adddd1ca832963dcb21e4487`. Authorization YAML SHA256: `04fa458828b0f74d3e4fe0b4887282327b736b72476f059955c354fefbb6e963`.

FORMAL_CHECKPOINT_ROOT: `F:\pytorch\Research\outputs\formal_training\b0_phase_a`. BEST/LAST only; binaries and optimizer states are never committed. SHA, size, absolute paths, histories, reports and manifests are public evidence.

All inherited scientific, protocol, normalization, population, SP04 and mask identities, plus the corrected scheduler implementation, are pinned in the YAML identity map. Validation source hashes absent from the historical identity-only manifest are separately established at this run's preflight; no historical manifest or eligibility decision is replaced. All runtime reads must match that additional ledger and the frozen QC identities.

Epoch-boundary resume requires verified LAST and all provenance before applying model, optimizer and RNG states. Any scientific protocol, numerical, identity or QC failure stops this run. No automatic remediation or next-stage execution is authorized.
