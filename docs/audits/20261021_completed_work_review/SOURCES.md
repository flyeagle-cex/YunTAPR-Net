# 审查来源索引

SHA和可用Git历史中的最后修改commit见机器索引；来源中的旧状态只适用于其原始时刻。

## RUNTIME

- [runtime_snapshot.json](../../../docs/audits/20261021_completed_work_review/evidence/runtime_snapshot.json)
- [v7_code_identity.json](../../../docs/audits/20261021_completed_work_review/evidence/v7_code_identity.json)
- [seed2027_completed_e0.json](../../../docs/audits/20261021_completed_work_review/evidence/seed2027_completed_e0.json)
- [FINAL_LIVE_OBSERVATION.json](../../../docs/audits/20261021_completed_work_review/evidence/FINAL_LIVE_OBSERVATION.json)
- [RUN_STATE_CHANGE.md](../../../docs/audits/20261021_completed_work_review/RUN_STATE_CHANGE.md)

## V7

- [release.json](../../../docs/phase_b_v2_formal_execution/seed2027_b1_epoch7_recovery_v7/release.json)
- [FAILED_ANCESTOR.json](../../../docs/phase_b_v2_formal_execution/seed2027_b1_epoch7_recovery_v7/FAILED_ANCESTOR.json)
- [config.json](../../../docs/phase_b_v2_formal_execution/seed2027_b1_epoch7_recovery_v7/config.json)
- [authority.py](../../../src/yuntapr/training/phase_b_v2_seed2027_b1_epoch7_recovery_v7/authority.py)
- [accounting.py](../../../src/yuntapr/training/phase_b_v2_seed2027_b1_epoch7_recovery_v7/accounting.py)
- [quota.py](../../../src/yuntapr/training/phase_b_v2_seed2027_b1_epoch7_recovery_v7/quota.py)
- [engine.py](../../../src/yuntapr/training/phase_b_v2_seed2027_b1_epoch7_recovery_v7/engine.py)
- [recovery.py](../../../src/yuntapr/training/phase_b_v2_seed2027_b1_epoch7_recovery_v7/recovery.py)

## FREEZE

- [scientific_freeze_v2_registry_v1.json](../../../config/science_v2/scientific_freeze_v2_registry_v1.json)
- [phase_a_protocol_frozen_v1.json](../../../config/science_v2/phase_a_protocol_frozen_v1.json)
- [quantile_head_v2_frozen_v1.json](../../../config/science_v2/quantile_head_v2_frozen_v1.json)
- [researcher_approval.txt](../../../docs/scientific_freeze_v2/approval_runs/run_20261007T012725Z/researcher_approval.txt)

## DATA

- [sample_set_freeze.json](../../../docs/b1_scientific_freeze/runs/run_20261003T045139_110133Z/sample_set_freeze.json)
- [normalization_b1_2023_shared_v1.json](../../../docs/b1_scientific_freeze/runs/run_20261003T045139_110133Z/normalization_b1_2023_shared_v1.json)
- [b1_2023_formal_manifest.csv](../../../docs/b1_scientific_freeze/runs/run_20261003T045139_110133Z/b1_2023_formal_manifest.csv)
- [b1_2024_formal_manifest.csv](../../../docs/b1_scientific_freeze/runs/run_20261003T045139_110133Z/b1_2024_formal_manifest.csv)
- [b0_matched_control_2023_formal_manifest.csv](../../../docs/b1_scientific_freeze/runs/run_20261003T045139_110133Z/b0_matched_control_2023_formal_manifest.csv)
- [b0_matched_control_2024_formal_manifest.csv](../../../docs/b1_scientific_freeze/runs/run_20261003T045139_110133Z/b0_matched_control_2024_formal_manifest.csv)
- [dataset_b1.py](../../../src/yuntapr/data/dataset_b1.py)
- [himawari_b13.py](../../../src/yuntapr/data/himawari_b13.py)
- [imerg_v07.py](../../../src/yuntapr/data/imerg_v07.py)
- [formal_policy.py](../../../src/yuntapr/data/formal_policy.py)

## SPATIAL

- [sp04_coordinate_manifest_v1.json](../../../config/spatial/sp04_coordinate_manifest_v1.json)
- [sp04_target_cell_membership_v1.csv](../../../config/spatial/sp04_target_cell_membership_v1.csv)
- [sp04_mapping.py](../../../src/yuntapr/spatial/sp04_mapping.py)
- [projection.py](../../../src/yuntapr/spatial/projection.py)

## GFS

- [GFS_TIME_SEMANTICS_SUMMARY.md](../../../stage0-b0-evidence/evidence/outputs/stage0_continuous_engineering/run_20260928T041855_828904Z/GFS/GFS_TIME_SEMANTICS_SUMMARY.md)
- [gfs_thermo_inventory_summary.md](../../../stage0-b0-evidence/evidence/outputs/stage0_gfs_thermo_compatibility/run_20260928T084334_575397Z/THERMO/gfs_thermo_inventory_summary.md)
- [AUXILIARY_TIME_CONFLICT_REPORT.md](../../../stage0-b0-evidence/evidence/outputs/stage0_gfs_thermo_compatibility/run_20260928T084334_575397Z/TIME_LINEAGE/AUXILIARY_TIME_CONFLICT_REPORT.md)
- [compat_rules.py](../../../stage0-b0-evidence/evidence/outputs/stage0_gfs_thermo_compatibility/run_20260928T084334_575397Z/src/compat_rules.py)
- [unit_pressure_audit.py](../../../stage0-b0-evidence/evidence/outputs/stage0_gfs_thermo_compatibility/run_20260928T084334_575397Z/src/unit_pressure_audit.py)
- [FINAL_GFS_PROVENANCE_VINTAGE_REPORT.md](../../../stage0-b0-evidence/evidence/outputs/stage0_gfs_provenance_vintage_resolution/run_20260928T092552_449937Z/FINAL_GFS_PROVENANCE_VINTAGE_REPORT.md)
- [STAGE0_MASTER_STATUS.md](../../../stage0-b0-evidence/evidence/outputs/stage0_final_gate_package/run_20260928T113745_449683Z/STAGE0_MASTER_STATUS.md)

## DEM

- [dem_audit_summary.json](../../../stage0-b0-evidence/evidence/outputs/stage0_spatial_static_closeout/run_20260928T095818_821492Z/DEM/dem_audit_summary.json)
- [terrain_smoke_result.json](../../../stage0-b0-evidence/evidence/outputs/stage0_spatial_static_closeout/run_20260928T095818_821492Z/DEM/terrain_smoke_result.json)
- [audit_dem.py](../../../stage0-b0-evidence/evidence/outputs/stage0_spatial_static_closeout/run_20260928T095818_821492Z/src/audit_dem.py)
- [spatial_rules.py](../../../stage0-b0-evidence/evidence/outputs/stage0_spatial_static_closeout/run_20260928T095818_821492Z/src/spatial_rules.py)
- [TERRAIN_STRATIFICATION_CANDIDATES.md](../../../docs/phase_a_evidence_hardening/TERRAIN_STRATIFICATION_CANDIDATES.md)

## TEST2025

- [b0_2025_catalogue_only_authorization_v1.1.json](../../../config/evaluation/b0_2025_catalogue_only_authorization_v1.1.json)
- [final_status.json](../../../docs/final_test_b0/catalogue_gate_v1_1/catalogue_only_runs/run_20261003T015507_526850Z/final_status.json)

## OLDTRAIN

- [B0_PHASE_A_FORMAL_TRAINING_REPORT.md](../../../docs/formal_training/b0_phase_a/runs/run_20261001T035003_243409Z/B0_PHASE_A_FORMAL_TRAINING_REPORT.md)
- [final_status.json](../../../docs/formal_training/b0_phase_b_finalfit/runs/run_20261002T035929_487644Z/final_status.json)
- [final_status.json](../../../docs/formal_training/b0_matched_phase_a/runs/run_20261003T093519_542831Z/final_status.json)
- [final_status.json](../../../docs/formal_training/b1_phase_a/runs/run_20261003T093522_417735Z/final_status.json)

## OLDFAIL

- [b0_matched_phase_b_execution_result.json](../../../docs/paired_extended_pipeline/runs/run_20261005T043214_165890Z/b0_matched_phase_b_execution_result.json)
- [phase_b_orchestration_failure_20261005T141344_810928Z.json](../../../docs/paired_extended_pipeline/runs/run_20261005T043214_165890Z/phase_b_orchestration_failure_20261005T141344_810928Z.json)

## PHASEA

- [V2_PAIRED_PHASE_A_REVIEW.md](../../../docs/v2_phase_a_review/paired_packets/run_20261009T072307_459014Z/V2_PAIRED_PHASE_A_REVIEW.md)
- [final_review.json](../../../docs/v2_paired_phase_a_review/runs/run_20261009T072307_459014Z/B0_MATCHED_V2/final_review.json)
- [final_review.json](../../../docs/v2_paired_phase_a_review/runs/run_20261009T072307_459014Z/B1_V2/final_review.json)
- [SCIENTIFIC_EVIDENCE_AUDIT.md](../../../docs/phase_a_evidence_hardening/SCIENTIFIC_EVIDENCE_AUDIT.md)
- [final_status.json](../../../docs/phase_a_evidence_hardening/final_status.json)

## MODEL

- [parameterization.py](../../../src/yuntapr/models/quantile_v2/parameterization.py)
- [outputs.py](../../../src/yuntapr/models/quantile_v2/outputs.py)
- [probability_heads.py](../../../src/yuntapr/models/probability_heads.py)

## METRICS

- [metrics.py](../../../src/yuntapr/experimental/phase_b_v2_formal_integration_candidate/metrics.py)
- [metrics.py](../../../src/yuntapr/experimental/phase_b_v2_ablations/metrics.py)
- [validation.py](../../../src/yuntapr/experimental/phase_b_v2_ablations/validation.py)
- [evaluation.py](../../../src/yuntapr/training/phase_b_v2_seed2027_b1_epoch7_recovery_v7/evaluation.py)

## SEED2026

- [execution_status.json](../../../docs/phase_b_v2_formal_execution/seed2026_operator_v3/execution_status.json)
- [RECOMPUTATION_AUDIT.json](../../../docs/phase_b_v2_seed2026_scientific_analysis/v1/RECOMPUTATION_AUDIT.json)

## BACKUP

- [CHECKPOINT_PAYLOAD_AUDIT.json](../../../docs/phase_b_v2_seed2026_scientific_analysis/v1/CHECKPOINT_PAYLOAD_AUDIT.json)
- [BACKUP_VERIFICATION.json](../../../docs/phase_b_v2_multiseed_preparation/v1/BACKUP_VERIFICATION.json)
- [README.md](../../../docs/phase_b_v2_multiseed_preparation/v1/README.md)

## RECOVERY

- [DELTA_TESTS_attempt1.log](../../../docs/phase_b_v2_formal_execution/seed2027_b1_epoch7_recovery_v4/DELTA_TESTS_attempt1.log)
- [FAILED_ANCESTOR.json](../../../docs/phase_b_v2_formal_execution/seed2027_b1_epoch7_recovery_v5/FAILED_ANCESTOR.json)
- [failure_sanitized.txt](../../../docs/phase_b_v2_formal_execution/seed2027_b1_epoch7_recovery_v5/postmortem_20261021/failure_sanitized.txt)
- [final_status.json](../../../docs/phase_b_v2_formal_execution/seed2027_b1_epoch7_recovery_v5/postmortem_20261021/final_status.json)
- [FAILED_ANCESTOR.json](../../../docs/phase_b_v2_formal_execution/seed2027_b1_epoch7_recovery_v6/FAILED_ANCESTOR.json)
- [FAILED_ANCESTOR.json](../../../docs/phase_b_v2_formal_execution/seed2027_b1_epoch7_recovery_v7/FAILED_ANCESTOR.json)

## GOVERNANCE

- [RECOVERY_GOVERNANCE_GAP_REVIEW.md](../../../docs/phase_a_evidence_hardening/RECOVERY_GOVERNANCE_GAP_REVIEW.md)
- [recovery_best_chronology_note.json](../../../docs/v2_scientific_acceptance/runs/run_20261009T112710_013267Z/delivery_v2/recovery_best_chronology_note.json)
- [RECOVERY_GOVERNANCE_DEVIATION.md](../../../docs/v2_scientific_acceptance/runs/run_20261009T112710_013267Z/delivery_v2/RECOVERY_GOVERNANCE_DEVIATION.md)

## ANALYSIS

- [SCIENTIFIC_RESULTS.md](../../../docs/phase_b_v2_seed2026_scientific_analysis/v1/SCIENTIFIC_RESULTS.md)
- [FAILURES_AND_LIMITATIONS.md](../../../docs/phase_b_v2_seed2026_scientific_analysis/v1/FAILURES_AND_LIMITATIONS.md)
- [manifest.json](../../../docs/phase_b_v2_seed2026_scientific_analysis/v1/manifest.json)
- [final_metrics.csv](../../../docs/phase_b_v2_seed2026_scientific_analysis/v1/tables/final_metrics.csv)
- [rain_strata.csv](../../../docs/phase_b_v2_seed2026_scientific_analysis/v1/tables/rain_strata.csv)
- [TEST_RESULTS.json](../../../docs/phase_b_v2_seed2026_scientific_analysis/v1/TEST_RESULTS.json)

## MAINLINE

- [freeze_registry.json](../../../stage0-b0-evidence/evidence/outputs/stage0_spatial_decision_update/run_20260928T102636_513428Z/freeze_registry.json)
- [science_contract_v1.1.yaml](../../../config/science_contract_v1.1.yaml)
- [candidates.py](../../../src/yuntapr/diagnostics/candidates.py)
- [TERRAIN_STRATIFICATION_CANDIDATES.md](../../../docs/phase_a_evidence_hardening/TERRAIN_STRATIFICATION_CANDIDATES.md)

## FIX

- [protocol.py](../../../src/yuntapr/experimental/phase_b_v2_multiseed_candidate/protocol.py)
- [authority.py](../../../src/yuntapr/experimental/phase_b_v2_multiseed_candidate/authority.py)
- [test_predecessor_interface.py](../../../tests/completed_work_review/test_predecessor_interface.py)
- [P1_001_before.txt](../../../docs/audits/20261021_completed_work_review/evidence/P1_001_before.txt)
- [P1_001_after.txt](../../../docs/audits/20261021_completed_work_review/evidence/P1_001_after.txt)
