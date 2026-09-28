# Data gaps and evidence limits

已确认缺口共 7 项；工程缺口不等同原始文件错误。bbox/context 等未冻结选择不列为 data gap。

| id | classification | item | status | detail | evidence |
| --- | --- | --- | --- | --- | --- |
| G01 | HARD_DATA_GAP | IMERG 2025-10 | MISSING | 候选 2025-03~10 final test 缺 31 日；不可自动缩短到 September。 | [OCTOBER](F:/pytorch/Research/outputs/stage0_continuous_engineering/run_20260928T041855_828904Z/CROSS_SOURCE/imerg_202510_targeted_presence.json); [RUN_p0](F:/pytorch/Research/outputs/stage0_p0_audit/run_20260927T161311_417313Z/audit_final_status.json) |
| G02 | DATA_COVERAGE_GAP | GFS main 研究期六层 T/RH | MAIN_ROOT_MISSING_COMPANION_CANDIDATE_COMPLETE | 主库缺所需 T/RH；thermo 有 8820/8820 structural complete 对。缺口限主来源，未批准 integration。 | [REPORT_continuous](F:/pytorch/Research/outputs/stage0_continuous_engineering/run_20260928T041855_828904Z/FINAL_CONTINUOUS_ENGINEERING_REPORT.md); [THERMO_RESEARCH](F:/pytorch/Research/outputs/stage0_gfs_thermo_compatibility/run_20260928T084334_575397Z/COMPATIBILITY/research_period_thermo_coverage.csv) |
| G03 | DATA_COVERAGE_GAP | Himawari 2024-07 nominal slots | PARTIAL | 4390/4464，74 个名义时次未覆盖；六帧候选 4020 complete /444 incomplete。B0 单帧不可直接用六帧完整性剔除。 | [RUN_himawari](F:/pytorch/Research/stage0_himawari/outputs/202407/resume_20260927T104625_772423Z/reports/final_dry_run_status_202407_v2.json); [RESEARCH_MATRIX](F:/pytorch/Research/outputs/stage0_continuous_engineering/run_20260928T041855_828904Z/CROSS_SOURCE/research_period_data_matrix.csv) |
| G04 | METADATA_EVIDENCE_GAP | IMERG native exact half-hour window | PROVISIONAL | converted CF time 已验证；native 窗口起止及 analysis_time 绑定仍未完全建立。 | [SCHEMA](F:/pytorch/Research/outputs/stage0_continuous_engineering/run_20260928T041855_828904Z/schemas/sample_index_schema.md); [CONVENTIONS](F:/pytorch/Research/outputs/stage0_continuous_engineering/run_20260928T041855_828904Z/docs/DECISION_LOG_STAGE0.md) |
| G05 | METADATA_EVIDENCE_GAP | GFS operational release / historical vintage | NOT_ESTABLISHED | 2026 retrospective acquisition 仅 PARTIALLY_ESTABLISHED，不能证明 2023–2025 contemporaneous availability。 | [RUN_provenance](F:/pytorch/Research/outputs/stage0_gfs_provenance_vintage_resolution/run_20260928T092552_449937Z/audit_final_status.json) |
| G06 | SOURCE_PROVENANCE_GAP | GFS main/thermo acquisition-conversion-content chain | SUPPORTED_WITH_CAVEATS | 原始内容/转换过程证据链未闭合；不能把 token/grid/time 一致升级成全部来源认证。 | [RUN_provenance](F:/pytorch/Research/outputs/stage0_gfs_provenance_vintage_resolution/run_20260928T092552_449937Z/audit_final_status.json); [REPORT_provenance](F:/pytorch/Research/outputs/stage0_gfs_provenance_vintage_resolution/run_20260928T092552_449937Z/FINAL_GFS_PROVENANCE_VINTAGE_REPORT.md) |
| G07 | METADATA_EVIDENCE_GAP | Himawari operational availability | NOT_ESTABLISHED | date_created 是 product/file creation timestamp；不是已验证 operational availability。 | [RUN_p0](F:/pytorch/Research/outputs/stage0_p0_audit/run_20260927T161311_417313Z/audit_final_status.json); [REPORT_himawari](F:/pytorch/Research/stage0_himawari/outputs/202407/resume_20260927T104625_772423Z/reports/README_HIMAWARI_PREPROCESS_202407_v2.md) |

## 未审计范围：不计入已确认缺口数

| id | classification | item | status | detail | evidence |
| --- | --- | --- | --- | --- | --- |
| U01 | DATA_COVERAGE_GAP | 独立外部验证 | NOT_AUDITED | 这是准备状态未知，不是已证明数据缺失。既有材料未建立可用独立验证集，不扫描/下载来补齐。 | [RESEARCH_MATRIX](F:/pytorch/Research/outputs/stage0_continuous_engineering/run_20260928T041855_828904Z/CROSS_SOURCE/research_period_data_matrix.csv); [CONVENTIONS](F:/pytorch/Research/outputs/stage0_continuous_engineering/run_20260928T041855_828904Z/docs/DECISION_LOG_STAGE0.md) |
| U02 | DATA_COVERAGE_GAP | Himawari 其余 23 个研究月份 | NOT_AUDITED | 只有目录证据；未证明缺文件，也未证明 READY。未来正式样本生产前需完成其选定范围工程验证。 | [RESEARCH_MATRIX](F:/pytorch/Research/outputs/stage0_continuous_engineering/run_20260928T041855_828904Z/CROSS_SOURCE/research_period_data_matrix.csv) |

DATA_COVERAGE_GAP 为待核验的缺口类别，U01/U02 的实际缺失未知。独立验证 NOT_AUDITED 不能写成不存在或 READY。
