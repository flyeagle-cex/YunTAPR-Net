# YunTAPR-Net 当前科研进度

2026-10-28终态：B7 seed2029九轮Train/2024 Dev及固定E9完成；B8第七轮源文件路径解析WinError121停止，六轮封口、2,942次RETURNED、E6/2,880已保存，62次更新未保存，无固定E9。整包未完成，不自动恢复。[新终态核查](../research_readiness/20261025/evidence/b7_b8_terminal_20261028.json)。B0–B6继承、2025冻结。下文IN_PROGRESS是历史快照。

最新B7/B8获批执行：b1f072e/64e8提案已被研究者明确批准并单次启动，B7真实训练进行中、B8同控制器串行等待；整包IN_PROGRESS，非COMPLETE。批准已消费，零重放/额外重试，2025冻结。[新启动收据](../research_readiness/20261025/evidence/b7_b8_approved_launch.json)。以下NOT_STARTED和待批准记录保留历史时点。

2026-10-27 B7/B8后续准备：DOTE原物理变量与B6梯度已接通，B7 concat及B8 DTFM同参数单尺度模型、必要检查及真实Train2/Dev1零更新检查通过；正式训练NOT_STARTED，待一份新科学方案/预算批准。B0–B6有效完成证据直接继承。[审批入口](../research_readiness/20261025/B7_B8_INNOVATION_PROTOCOL.md)。

最新地形收口（2026-10-27T15:34:06.069260+08:00）：B5/B6 seed2029九轮Train/2024 Dev与固定E9配对已核验完成（COMPLETE_TRAIN_AND_DEV_EVALUATION）；首轮消融COMPLETE_WITH_LIMITATIONS，B6改善Brier/AUROC但AP、条件Pinball和q32退化，B5总体仅AUROC改善。完整预算、代码/权重身份、反例见[新收据](../research_readiness/20261025/evidence/b5_b6_completion_and_paired_evidence.json)和[统一阶段验收](../../STAGE_ACCEPTANCE.md)。2025与B7/B8仍冻结，无追加训练。以下按日期保留历史状态。

当前报告发布状态（2026-10-27T08:09:47.988894+08:00，北京时间）：已完成结果为B0/B1既有正式实验、B2 seed2029及B3/B4三seed固定E9配对。**B5：IN_PROGRESS；B6：IN_PROGRESS（串行等待，尚未开始优化器更新）**。两模型均未完成九轮Train/Dev，不发布最终评价。见[固定状态快照](../research_readiness/20261025/evidence/b5_b6_status_for_main_20261027.json)。本次通过报告专用PR合入main，不改训练源码和历史证据。

最新纠正运行（2026-10-27）：b251fd9/36fc5dfb已取得明确纠正启动批准，B5真实训练进行中，B6串行等待；07:55:16快照179确认更新，无额外优化器重放。当前IN_PROGRESS，不能宣称E9完成。见[启动与预算收据](../research_readiness/20261025/evidence/b5_b6_corrected_start_launch.json)。下方首启失败保持历史记录。

最新执行停止（2026-10-27）：B5/B6获批首次启动在气象读取前被读取臂白名单拦截；0更新、62,828字节静态读取，B6未启动。最小修复及修正启动额度已备好，未重启；见[真实状态与修正方案](../research_readiness/20261025/B5_B6_READINESS_REPORT.md)。下方旧“待原批准/已就绪”内容保留历史时点。

最新推进（2026-10-27）：B0–B4基线按限定结论带局限完成交接；真实候选DEM、B5/B6模型和真实缓存零更新检查已完成。B5/B6正式训练未启动，需新协议/预算集中明确批准，2025冻结。 见[真实地形与启动预算](../research_readiness/20261025/B5_B6_READINESS_REPORT.md)。

最新完成（2026-10-27）：B3/B4 seed2029、2030、2031的三组固定E9配对训练与2024 Dev评价全部完成；四个新增模型均为COMPLETE_TRAIN_AND_DEV_EVALUATION。943da95恢复包在北京时间00:27封口，390次必要重放已计费，无额外重试。总体Brier/AUROC/AP/条件Pinball三seed均改善；q32方向不一致，强雨仍有退化。总体科学验收继续IN_PROGRESS，2025继续冻结。

最新矩阵为[27行完整矩阵](../research_readiness/20261025/B0_B4_EXPERIMENT_MATRIX.csv)，收据为[三seed完成与配对结果](../research_readiness/20261025/evidence/b3_b4_three_seed_completion.json)。以下旧数值快照保留其明确时点；新增结果优先。B2 seed2029已于3acf7b0收口，B2/B3结论混合。

数值证据核查：**2026-10-25 00:04:14，北京时间**；本机进程观测：**2026-10-25 00:06:43，北京时间**。这是一次只读证据整理，不是新的实验。

源码与证据快照为 [`0ccb3e26e2d50494aba07788fa94dd40ec89b4aa`](https://github.com/flyeagle-cex/YunTAPR-Net/commit/0ccb3e26e2d50494aba07788fa94dd40ec89b4aa)；seed2029 恢复执行代码为 [`7fa609e89bdb8b744bb0e7eebc9e7b5c3a703e35`](https://github.com/flyeagle-cex/YunTAPR-Net/commit/7fa609e89bdb8b744bb0e7eebc9e7b5c3a703e35)，最初启动准备为 `5b5298f41025db5b7b718fd736fc3fe6de516875`。此次文档以远端 main 的 `50254354f59c50ee9afd409d6820789371f76441` 为隔离基线；本文件所属同步提交见 GitHub 文件页的提交记录，避免在文件内制造自引用 SHA。

研究目标是从 Himawari 时序观测、GFS 环境与 DEM 地形出发，研究概率降水估计，以及 DOTE/DTFM 的增量作用。当前证据支持开发集上的有限比较，尚不支持整条创新链已验证。

## B0–B9 的真实状态

|模型|内容|已核实状态|结果与边界|
|---|---|---|---|
|B0|B13 单通道、单时次|已实现；Phase-B V2 在 seed2026、2027 的 E0/E1/E2 各完成九轮及 Dev 评估|有两 seed 的开发集重复证据；旧版 Phase-A/FinalFit 另列，不能混用|
|B1|B13 单通道、六时次|已实现；与 B0 同一 seed/损失臂配对完成|总体发生识别有方向一致的改善；上尾校准不全面改善|
|B2|七通道、单时次|**seed2029/E0/f006九轮及Dev完成，3acf7b0收口**|固定E9同人口配对：B2的Brier更好，B3的AUROC/AP/条件Pinball更好；仅1seed|
|B3|七通道、六时次|**seed2029/2030/2031 E0/f006均完成九轮Train/Dev**|Train=959、Dev=963；保留轨迹4,320次更新；固定E9 LAST|
|B4|B3 + GFS MEE|**seed2029/2030/2031均完成；2030保留原失败＋获批恢复历史**|13变量、width16、目标网格残差融合；每seed与B3配对|
|B5|B4 + 海拔|**IN_PROGRESS**；seed2029已进入获批正式训练|真实DEM/模型接入完成；固定E9与公平配对结果尚不可用|
|B6|B4 + 完整静态地形|**IN_PROGRESS**；同一获批串行包中等待B5收口|实际执行仍PENDING，尚无优化器更新；不得标为COMPLETE|
|B7|B6 + DOTE|动态特征与 concat 融合候选已实现、已有针对性测试|没有完整 B7 正式训练、降水消融或独立物理机制验证|
|B8|B7 + DTFM|多尺度、有界调制与配对融合候选已实现、已有针对性测试|没有完整 B8 正式训练或创新有效性证据|
|B9|ERA5 教师蒸馏，可选|未找到正式实现或实验收据|规划项；不据此读取 ERA5 或启动实验|

“未找到”的范围是本次覆盖的项目证据目录、正式输出目录标签、配置和实验收据，不是对全部磁盘或其他主机的绝对断言。完整记录见 [EXPERIMENT_MATRIX.csv](EXPERIMENT_MATRIX.csv)：**22 行**，包含旧版实验及失败尝试；其中 seed2029 初始失败段是恢复历史，不是额外独立复现。

E0/E1/E2 是损失臂，**不是** B0–B8 模型结构编号。seed2028 只有准备记录，本次未找到正式执行证据，也没有新授权。各模型均**未取得本轮核验范围内的 2025 独立模型测试结果**；没有宣称已具备完整论文确认性结论。

## 历史运行观测（2026-10-25，非当前状态）

只读 Win32_Process 观测到四个 Python 进程，均为两个本地监测服务的包装/子进程；未观察到训练执行器。保留监测服务原状，没有关闭、重启或控制任何进程。观测限于本机，不覆盖远程主机。[运行摘要](evidence/runtime_observation.json)

## 数据状态

- **Himawari/IMERG**：旧 B0/B1 的 2023 Train=10,455、2024 Dev=10,501 共同人口有冻结与评估证据。标签为分析时刻结束的半小时窗口，六帧历史槽位于分析前 60/50/40/30/20/10 分钟；这是回顾估计定义。新增七通道共同 QC 及统计已完成，B13 保留冻结统计，六个新波段仅用最终 2023 Train 拟合。
- **GFS**：本次 B3/B4 使用固定 f006、valid=analysis、2023/2024 三月至十月的共同人口，分别 959/963 场景；只覆盖 00/06/12/18 UTC。13 变量及独立有效掩膜、地下压力层排除已进入 B4。2023 Train 统计 SHA 为 `53ab2f07aabb02e66ad237452447a35e0e2896278eae9d2da179336c06fea980`，两模型共享人口 SHA 为 `2f2cc75cfb6c209fd8195d3419207216c5c3f2a4fc8315b40a1d77cc537dedb8`。历史实际发布时间与完整产品转换来源链仍不足；**retrospective，不代表 operational NRT**。
- **DEM/SRTM**：既有 237 tiles 审计记录云南覆盖 FULL，并有真实小窗口梯度与候选生产接口。DOTE 所需米制导数聚合、拼接边界、footprint 等生产/科学选项仍未全部冻结。没有本轮新读 DEM。
- **2025**：既有 catalogue/QC-only 收据记录候选 10,272、eligible 10,244、reject 28，以及历史 2,676,986,256 次像元读取；模型 forward、checkpoint load 和最终指标计算均为零。**不能宣称历史从未读过 2025**。该旧 B13/IMERG catalogue 也不能证明七通道、GFS 等全部 2025 最终测试输入完整；全模态完整性为 `NOT_VERIFIED`。本轮仅核查旧收据，没有进入 2025 数据目录或读取载荷。[数据证据](evidence/data_and_modules.json)

## 已核实的重要结果

- B0/B1：seed2026、2027 的三损失臂中，B1 相对配对 B0 的 Brier、AUROC、AP、条件 Pinball 方向均改善；q32 覆盖不一致。两 seed 与同一开发年的重复观察不等于独立最终测试。
- B3/B4：第九轮 Brier **0.099578846 → 0.097918992**，AUROC **0.888024778 → 0.894878405**，AP **0.570741768 → 0.592638283**，条件 Pinball **0.129258067 → 0.127193687**。
- `(20,30]`、`(30,50]` mm/h 条件 Pinball 分别从 **0.828964147 → 0.832683393**、**0.983911313 → 0.986955238**，均略差；对应 **564、147 个相关场景像元暴露**，不是独立暴雨事件。
- q32 的冻结名义覆盖率为 **98.4375%**；B3/B4 实际为 **93.504978%/93.622677%**，仍分别差 **−4.932522/−4.814823 个百分点**。06 UTC 的 Brier 略差；各时次与雨强均非全面改善。

完整数值、UTC、强降水和解释边界见 [SCIENTIFIC_RESULTS.md](SCIENTIFIC_RESULTS.md)、[全精度终点表](endpoint_metrics.csv)、[126 份逐轮摘要](epoch_metrics.csv)。不能将不同人口的旧 B1 指标与 B3/B4 直接排序。

## 完成证据与不足

seed2029 的完成结论来自九轮 Train/Dev 收据、每轮 LAST 绑定、完成标记、只读更新账本、相同人口/训练顺序核对的组合，不是仅凭 checkpoint 存在。有效轨迹总计 8,640 次，累计实际返回 9,120 次，含获批重放 480 次。累计读取实例 299,968，实际交付 1,003,563,940,849 字节；保守预登记 1,003,568,959,114 字节。[执行摘要](evidence/seed2029_execution.json)

该旧快照当时尚缺（B2及B3/B4三seed现已补齐；仅seed2029分层q32仍缺）：B2 正式对照；B3/B4 的第二个独立 seed；雨强分层的 q32 covered 计数/逐像元分位数产物；冻结高程分层与实际指标；DOTE/DTFM 正式消融及独立物理证据。现有开发集反复使用、少量强雨像元和历史恢复治理缺口均保留。seed2027 账本有 1 次历史未核验尝试，不能改写为成功。

下一步由研究者先审阅 seed2029 的增益与上尾反例，决定最小上尾损失假设及 DOTE/DTFM 待冻结参数，再另行决定实验与预算；本次不启动任何训练。

## 与上次进度相比

远端 main 仍停留在 2026-10-21 的 v6 发布，后来完成记录与代码分布在独立分支。本次建立统一入口，补上 seed2027 六组完成事实、Stage3 真实共同人口、seed2029 的 B3/B4 真实终点和恢复消耗；纠正“B2 已训练”“旧预算等于有效轨迹”“2025 从未读取”等无证据表述。未修改历史材料、模型、数据或协议。

证据均有 [EVIDENCE_INDEX.md](EVIDENCE_INDEX.md) 和 [源文件 SHA 清单](evidence/source_manifest.json)。`LOCAL_ONLY` 原始账本/结果只公开脱敏摘要和 SHA；ChatGPT 不能据此声称已经读取或独立复核本机原件。
