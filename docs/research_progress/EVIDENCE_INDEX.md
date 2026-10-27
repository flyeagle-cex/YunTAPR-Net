# 证据索引与可核验边界

B8恢复准备新增：[单源有界诊断](../research_readiness/20261025/evidence/b8_source_diagnostic_20261028.json)、[限额提案（未批准）](../research_readiness/20261025/evidence/b8_recovery_proposal_20261028.json)、[恢复入口检查](../research_readiness/20261025/evidence/b8_recovery_checks_20261028.json)。旧停止证据、权重及各模型指标不变。

最新B7/B8终态索引：[B7九轮完整、B8六轮/第七轮部分读取、两份实际权重SHA及精确额度](../research_readiness/20261025/evidence/b7_b8_terminal_20261028.json)。B7固定E9 SHA019a6dfabf2eef8eeb48bce993eaed64d86b78ea2da3e413e324f22f347f2e35；B8仅E6，E9不存在。失败原日志/账本保留，公开只含脱敏错误摘要与原件SHA，没有原始源重试或额外模型推理。

最新B7/B8证据：[实际新批准、冻结执行代码、125次RETURNED启动快照、资源入场与只读进度页](../research_readiness/20261025/evidence/b7_b8_approved_launch.json)。B7 RUNNING，B8 PENDING，固定E9/完整Dev科研终点NOT_AVAILABLE；原false提案是准备快照，未改写为批准凭据。

B7/B8新准备证据：[候选科学协议](../research_readiness/20261025/B7_B8_INNOVATION_PROTOCOL.md)、[机器提案](../research_readiness/20261025/evidence/b7_b8_training_proposal.json)、[真实零更新](../research_readiness/20261025/evidence/b7_b8_cached_real_check.json)、[原生压力mask纠正且零重读](../research_readiness/20261025/evidence/b7_b8_physical_cache_correction.json)。正式权重/九轮训练/Dev结果NOT_STARTED；不借用B6批准。

最新完成索引（2026-10-27T15:34:06.069260+08:00）：[B5/B6新增18轮、38读取账本、8,640更新、E9实际SHA和完整配对](../research_readiness/20261025/evidence/b5_b6_completion_and_paired_evidence.json)。B5/B6现为COMPLETE_TRAIN_AND_DEV_EVALUATION；历史启动/失败/IN_PROGRESS快照保留原字节。[根目录统一索引](../../EVIDENCE_INDEX.md)给出当前状态、代码和数据身份以及完整数值入口，旧公开清单仍仅约束原发布范围。

发布清单维护：`PUBLICATION_MANIFEST.json`是当前文档索引；原清单按原字节保存为[PUBLICATION_MANIFEST_20261025.json](PUBLICATION_MANIFEST_20261025.json)。`PUBLIC_VERIFICATION.json`仍是2026-10-25的历史22实验/126轮检查，未改写或冒充本次复核；本次仅做报告发布范围、状态和文件身份检查，继承既有实验验证。

报告合并时点状态：[B5/B6均IN_PROGRESS的脱敏快照](../research_readiness/20261025/evidence/b5_b6_status_for_main_20261027.json)。B6的阶段进行中与执行队列PENDING分别列明；已完成B0–B4结果和历史失败证据继续使用原收据，不把新训练的部分轮次或checkpoint当作完成。

最新纠正训练启动（2026-10-27）：[真实更新、批准绑定与资源入场](../research_readiness/20261025/evidence/b5_b6_corrected_start_launch.json)记录B5已跨过原读取臂问题，179次RETURNED启动快照、原成本与累计上限；B6仍等待。旧首启失败和待批准提案保留历史时点，当前批准已取得并消费。

最新B5/B6执行事实（2026-10-27）：[原批准首启停止收据](../research_readiness/20261025/evidence/b5_b6_initial_start_stop.json)记录0更新、0气象载荷、62,828字节静态读取和B6未启动；[读臂最小修复检查](../research_readiness/20261025/evidence/b5_b6_corrected_start_checks.json)与[唯一待批准修正启动提案](../research_readiness/20261025/evidence/b5_b6_corrected_start_proposal.json)保留新的代码/成本边界。原批准已消费，当前未重启；下面准备完成状态不能误作九轮训练完成。

B5/B6准备新证据（2026-10-27）：[实际100瓦片生产与3430有效点](../research_readiness/20261025/evidence/b5_b6_terrain_production.json)、[真实缓存零更新检查](../research_readiness/20261025/evidence/b5_b6_cached_real_check.json)、[必要检查及失败保留](../research_readiness/20261025/evidence/b5_b6_preparation_checks.json)。这是候选生产/准备完成，正式训练未启动；原DEM发布版本链未独立核实，候选按本地SHA固定，不从HGT头伪造版本。

最新完成证据（2026-10-27）：[三seed固定E9完成与配对收据](../research_readiness/20261025/evidence/b3_b4_three_seed_completion.json)包含恢复新增26轮封口、3份新E9文件SHA、52个新增读取账本核对、原E1引用、精确预算、全部六个终点及分组/上尾充分量；[结果报告](../research_readiness/20261025/B3_B4_MULTI_SEED_PLAN.md)给出三seed差值、均值和样本标准差。[最新27行矩阵](../research_readiness/20261025/B0_B4_EXPERIMENT_MATRIX.csv)优先于此目录保留的22行历史快照。188项仅为新增结果相关文件身份，未重复历史129来源/126逐轮核验。原始数据、权重和私有账本不公开。

本轮数值快照核查时间：2026-10-25 00:04:14 +08:00。所有新文件仅位于 `docs/research_progress/`，不改旧收据或实验源码。

## 读取入口

1. [CURRENT_STATUS.md](CURRENT_STATUS.md)：模型状态、实时观测和主要限制。
2. [EXPERIMENT_MATRIX.csv](EXPERIMENT_MATRIX.csv)：每个 seed/版本/损失臂独立一行，包含历史失败段。
3. [SCIENTIFIC_RESULTS.md](SCIENTIFIC_RESULTS.md)：配对数值、强降水及 UTC 结果。
4. [experiments.json](evidence/experiments.json)：按 `experiment_id` 匹配的全精度终点、来源标识和 checkpoint SHA。
5. [source_manifest.json](evidence/source_manifest.json)：129 个已读取来源的原始字节数、SHA256、可见性；公开来源提供固定 commit 的 URL。

## 重要结论对应的证据

|结论|公开可读材料|核验方法与边界|
|---|---|---|
|B0/B1 seed2026 六组完成|[历史 campaign 摘要](evidence/historical_campaigns.json)、[108 轮历史数值收据摘要所在索引](evidence/epoch_receipts.json)|读取六份正式结果，逐轮重算 validation receipt digest、核对完整九轮及最终 LAST；原完整结果链接见 source_manifest，不重读 checkpoint|
|B0/B1 seed2027 六组完成|[原完成记录，固定 ae4b448](https://github.com/flyeagle-cex/YunTAPR-Net/blob/ae4b448ab3db73fba855a2df5d37e0f1bb2e2f4e/docs/phase_b_v2_seed2027_completion/20261024/README.md)、[原54轮索引](https://github.com/flyeagle-cex/YunTAPR-Net/blob/ae4b448ab3db73fba855a2df5d37e0f1bb2e2f4e/docs/phase_b_v2_seed2027_completion/20261024/epoch_receipt_index.json)|六份完整结果的源 SHA、54 个验证 digest 和 checkpoint SHA 与原索引相符。历史不确定尝试及 session 字段问题仍保留|
|seed2029 B3/B4 九轮真实完成|[执行摘要](evidence/seed2029_execution.json)、[126轮索引](evidence/epoch_receipts.json)、[终点表](endpoint_metrics.csv)|原始完成 JSON、18 个 LAST/Dev 绑定、Train 计数、只读 SQLite 查询一致；原始 JSON/SQLite 为 LOCAL_ONLY|
|B4 相对 B3 的具体改善及反例|[第九轮各分组原数值摘录](evidence/seed2029_groups.json)、[原配对差值摘录](evidence/seed2029_paired_difference.json)、[七雨强层](rain_strata.csv)|逐字段核对现存 `paired_difference_09`；可从公开两模型数值重算差值、Brier 分子/分母、Pinball 和覆盖率，不代表重新跑模型|
|q32 欠覆盖|[全部32分位数](quantile_calibration.csv)、[终点/分组充分量](evidence/seed2029_groups.json)|`covered/N_rain` 对比冻结 `(i−0.5)/32`；雨强分层缺少 covered，不能从总体覆盖推导|
|无当前本地训练被发现|[运行观测](evidence/runtime_observation.json)|只读 Win32_Process，四个 Python 均为监测服务；不覆盖其他主机或未匹配的可执行程序|
|Stage3 QC 与 Train-only 统计完成|[数据与模块摘录](evidence/data_and_modules.json)|复用已有完成证据；共同人口 SHA、统计 SHA 与实际执行账本/启动配置对齐；本轮零原始气象读取|
|DOTE/DTFM 有代码和已有测试，但无正式科研验证|[既有52/20测试索引摘录](evidence/data_and_modules.json)、[DOTE 候选源码](https://github.com/flyeagle-cex/YunTAPR-Net/blob/0ccb3e26e2d50494aba07788fa94dd40ec89b4aa/src/yuntapr/experimental/core_innovation/stage2/dote_v13.py)、[融合源码](https://github.com/flyeagle-cex/YunTAPR-Net/blob/0ccb3e26e2d50494aba07788fa94dd40ec89b4aa/src/yuntapr/experimental/core_innovation/stage2/fusion.py)|测试通过仅说明接口/数学/梯度/掩膜等工程性质；本轮没有重跑既有测试，没有正式 B7/B8 指标|
|旧 Phase-A 与早停 BEST 是另一阶段|[Phase-A V2 终止与计数摘录](evidence/phase_a_v2_closure.json)、[逐实验表](EXPERIMENT_MATRIX.csv)|17轮、LAST 88,876 更新、BEST E9；不得当成固定九轮以外的新随机种子|
|2025 曾有 catalogue/QC，但没有最终模型评估|[历史访问摘要](evidence/data_and_modules.json)、[原目录收据](https://github.com/flyeagle-cex/YunTAPR-Net/blob/0ccb3e26e2d50494aba07788fa94dd40ec89b4aa/docs/final_test_b0/catalogue_gate_v1_1/catalogue_only_runs/run_20261003T015507_526850Z/final_status.json)|历史读取数与零 model-forward 分别保留；不能证明全模态最终测试完整，也不能声称所有历史未访问|

## 版本关系与历史局限

|工作区脱敏别名|用途|对应提交/证据|
|---|---|---|
|PUBLICATION_SEED2027|旧审查、恢复快照、seed2027完整结果的汇集|`ae4b448ab3db73fba855a2df5d37e0f1bb2e2f4e`|
|CORE_STAGE1 / STAGE2|核心接口、B3/B4及DOTE/DTFM候选|`ede6e64569b72d0763e10f33ce82a3ab2b5b3a9b` / `e4563a0554ff6a6ffaaa8cc1e913cc005044688e`|
|STAGE3_PLAN / DATA_PRODUCTION|授权清单、真实共同人口与Train统计|`c5ccd52afb9f7890278109c28a93cd0d13760c5d` / `0cf938fb2037dec84a86cdeb0573b169103330be`|
|STAGE4_IMPLEMENTATION / LAUNCH|13变量接入、配对执行器与首次启动准备|`d475722ed25f2d65319bf3562fd4408365649178` / `5b5298f41025db5b7b718fd736fc3fe6de516875`|
|SEED2029_RECOVERY1|独立恢复执行；当前来源副本还含监测源码发布|执行 `7fa609e89bdb8b744bb0e7eebc9e7b5c3a703e35`，来源快照 `0ccb3e26e2d50494aba07788fa94dd40ec89b4aa`|
|LOCAL_SCIENTIFIC_ANALYSIS|先前seed2029分析报告、图与CSV|本地报告，无独立Git提交；本次提取主要数值公开，原包LOCAL_ONLY|

这些是来源映射，不是修改或合并旧工作区的指令。不同副本的历史状态字段可能滞后；以各阶段的真实完成/终止收据为准。

- 证据文件所在源码快照：`0ccb3e26e2d50494aba07788fa94dd40ec89b4aa`；seed2029 最初运行基准 `5b5298f41025db5b7b718fd736fc3fe6de516875`，恢复基准 `7fa609e89bdb8b744bb0e7eebc9e7b5c3a703e35`。
- seed2026 科学分析原基线 `dbccf220e8e88178388433e3d69e4e0e9682d652`。seed2027 后续完成以六份结果和最终 campaign 收据为准，不能用 2026-10-21 的中途状态覆盖它。
- [历史审查](https://github.com/flyeagle-cex/YunTAPR-Net/blob/ae4b448ab3db73fba855a2df5d37e0f1bb2e2f4e/docs/audits/20261021_completed_work_review/AUDIT_REPORT.md)保留旧恢复批准缺口、1 次未核验尝试和旧失败记录；本次技术完整性核对不追认历史授权。
- `EPOCH_RECEIPTS` 中的 validation SHA 是原规范化 JSON digest，不是 checkpoint 文件 SHA。源清单的 SHA 是原文件字节 SHA，二者不可混用。
- 新公开证据是既有记录的字段摘录，不是新观测。原始 JSON 完整内容、数据库和权重未全部公开；哈希可证明本机对应材料的身份约束，**哈希本身不能证明未公开内容真实无误**。
- 源码中有的历史文案仍写 candidate/no-launch/dry-run；这些是当时版本的标签。正式完成依据是独立实际执行收据与账本，而不是升级这些标签。

## LOCAL_ONLY 清单

|脱敏标识|本地材料|公开内容|仍不能由 ChatGPT 独立完成的检查|
|---|---|---|---|
|SEED2029_ORIGINAL / RECOVERY1|原始更新、源读取 SQLite 和逐轮完整 JSON|[只读查询汇总](evidence/seed2029_execution.json)、129项源 SHA 清单中的相应别名|重查本机账本及未公开分组明细、验证底层原始输入|
|SEED2029_LAST_B3 / LAST_B4|第九轮模型/优化器载荷|`c7780bc6e45992639c90339c88553fe3a722f6d9681bd247a82ad2dce0c08283` / `7c74eb80ab7d754e3262781d85ac370b2319c3bf27d37ac362860c104acfb34d`|载荷反序列化、再次推理或复现训练；本轮也未执行|
|STAGE3_FINAL_POPULATION_AND_STATISTICS|完整人口、源清单、Train 充分统计及数据库|共同人口/统计/候选清单 SHA、样本分布与处理完成摘要|全量数据 QC/统计再生产；不据此取得读取许可|
|SEED2029_LOCAL_RESEARCH_REPORT|先前5页分析 PDF、可编辑 LaTeX、曲线与源材料包|本次公开其主要数值和解释，见 SCIENTIFIC_RESULTS；不上传未逐项脱敏的整包|读取本机报告原件、全部图表与内部来源清单|
|OBSERVATIONS_AND_WEIGHTS|卫星/GFS/IMERG/DEM、所有模型权重与缓存|只公开必要汇总、源码和身份 SHA|访问原始数据、模型独立重算；不声称这些已上传|

旧公开分支已有部分历史材料包含当时获准披露的路径；本次不改写或删除它们，也不将这些路径复制进新文件。

## 复核方法

只读取此目录即可运行 `python docs/research_progress/scripts/verify_public.py`，核对公开数据的终点/逐轮一致性、充分量计算、配对人口、差值、q32 和文件 SHA。该命令不会导入 PyTorch、访问原始数据、打开 checkpoint 或运行推理。

`scripts/build_snapshot.py` 需要原设备明确传入两个既有源码/证据工作区，仅重建此目录的数值摘录。它不执行训练，不是跨机器获取私有证据的工具，也不应被误称为全量原始实验复现。
