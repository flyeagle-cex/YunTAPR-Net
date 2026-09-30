# YunTAPR-Net

The authoritative [Scientific Freeze v1](docs/scientific_freeze/YUNTAPR_SCIENTIFIC_FREEZE_v1.md) and [machine-readable contract](config/science_contract_v1.yaml) record the researcher's approved time, data-role, SP04 spatial, split, missing/QC, probability, and formal B0 backbone rules. The versioned [SP04 coordinate/index artifacts](config/spatial/sp04_coordinate_manifest_v1.json) implement the approved target-cell membership. **B0_FORMAL_SCIENTIFIC_CONTRACT=FROZEN; B0_FORMAL_TRAINING_STARTED=false.** The next phase is `FORMAL_B0_SKELETON_IMPLEMENTATION`.

The Stage-0, engineering smoke, and formal-readiness reports below remain immutable historical evidence. Their `NOT_YET_FROZEN` or `RESEARCHER_DECISION_REQUIRED` statements about a rule now explicitly frozen in Scientific Freeze v1 are superseded by that later researcher approval. Earlier observations and unresolved data-availability findings remain historical facts. Do not use 2025 Test results to revise the frozen protocol.

The [Stage-0 and B0 engineering evidence snapshot](stage0-b0-evidence/README.md) contains source code, audit reports, test records, and SHA256 manifests from the current research workflow.

The historical [formal-readiness report](stage0-b0-evidence/evidence/outputs/stage1_b0_formal_readiness_resolution/run_20260928T124313_169375Z/FINAL_B0_FORMAL_READINESS_REPORT.md) recorded **B0_FORMAL_NOT_READY** at that run: the engineering smoke passed, 30 formal-readiness checks passed, and 12 formal-entry items still required resolution. Its data-gap evidence remains relevant; the later Scientific Freeze v1 resolves the listed scientific choices without rewriting that report. No formal B0 training was started.

The new [B0 spatial and probability contract resolution](stage0-b0-evidence/evidence/outputs/b0_spatial_probability_contract_resolution/run_20260928T144303_935304Z/FINAL_B0_SPATIAL_PROBABILITY_CONTRACT_REPORT.md) records actual-coordinate SP04 geometry, five spatial-alignment candidates, probability-output and loss candidates, 40 passing focused tests, and the remaining researcher decisions. It does not start formal training or freeze a projection, τ grid, or loss hyperparameter.

This public repository excludes source satellite/precipitation values, storage benchmark arrays, and restricted boundary/mask payloads. Scientific Freeze v1 adds only coordinate-axis metadata and an explicit index map required to execute the frozen spatial rule. The snapshot README and manifests identify other included files and local artifacts excluded from public distribution.
