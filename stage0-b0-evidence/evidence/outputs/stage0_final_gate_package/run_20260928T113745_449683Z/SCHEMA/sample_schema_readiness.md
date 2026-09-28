# Formal sample schema readiness

状态：**NEEDS_UPDATE**。复用源：[SCHEMA](F:/pytorch/Research/outputs/stage0_continuous_engineering/run_20260928T041855_828904Z/schemas/sample_index_schema.md)。这是字段评估，不是新 schema 定版或正式样本库。

已有：源路径、UTC/null/evidence status、IMERG grid/units、时间窗口 provisional 状态、Himawari 六槽/七通道/obs_end/date_created/availability 分列、missing/QC flags、p99 marker、GFS init/lead/valid/release/vintage 与分库 provenance、surface pressure feasibility、bbox null 等。不能把这些字段都设为 B0 必填。

进入实现前需要描述并由对应任务补齐：

1. stage_profile / purpose：B0 单 B13 单时次；B1/B3 才有相应六槽输入；engineering_fixture 与 formal 实例显式区分。旧 fixed list[6]/list[7] 不能不加 profile 就强制用于 B0。
2. spatial_freeze_id、boundary/mask 文件和 geometry/coordinate hash、primary/non_primary role；旧泛化 Yunnan_mask_status 应引用真实已冻结版本。
3. native_window_rule_id、analysis_time_binding_id、temporal_evidence_status 与 formal eligibility；规则未批准时值仍 null/provisional。不能按旧候选 [T,T+30min) 实例化正式样本。
4. input_domain_config_id、context_rule_id、target_grid_id、显式裁剪/padding/重采样映射及坐标方向记录；本轮不选择规则或执行变换。
5. split_definition_id 与 Train/Val/Test assignment 的 provenance；normalization_artifact_id、Train-only 来源/split hash、有效像元规则；本轮不赋值、不统计。
6. sample_inclusion_policy_id、loss/metric valid-mask references、channel/time presence 与拒绝原因；latency tail 不自动进入 reject reason。
7. optional-by-stage GFS/DEM 字段、adoption/vintage rule id 与 source-pair evidence。B0 值可为 NOT_APPLICABLE，不伪造成 MISSING_INPUT。
8. formal probability/loss/metric protocol id、种子/checkpoint/inference 版本引用；精确 quantile levels 未冻结。
9. raw source identity/hash（适用时）、evidence run 与生成代码 hash、schema/version、execution purpose/quality status，防止工程 fixture 被提升为正式样本。

NEEDS_UPDATE 指 schema 可以基于上述明确差异继续设计；formal instance generation 仍受决策表约束。既有 schema 的 pipeline 提案不构成科学批准。没有创建全量 sample index、Dataset 或数据库。
