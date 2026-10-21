# YunTAPR-Net 已完成工作审查 · 2026-10-21

审查基线：本机 `YunTAPR-Net-push-chunks` 的 `96a2a61eeb9b0c4a8513133133c75bfdf4b58726`。整改位于完全独立 Git 仓库 `YunTAPR-Net-completed-review-20261021`、分支 `audit/completed-work-20261021`。本报告不批准训练、恢复、部署或合并。来源编号、SHA、可用历史中的最后修改 commit 见 [EVIDENCE_MATRIX.csv](EVIDENCE_MATRIX.csv)、[SOURCES.md](SOURCES.md) 与 [REVIEWED_SOURCE_INDEX.json](evidence/REVIEWED_SOURCE_INDEX.json)。

## 1. 主要结论及运行保护

- 审查初期已确认本机运行的是 seed2027 epoch7 恢复 **v7**，PID 29388/Owner 48220 的创建时间匹配身份收据。**截至北京时间19:28收尾观察，二者已退出**；Owner traceback为 `MemoryError: AVAILABLE_COMMIT_LIMIT`，GUI终止收据记录退出码1、Job已清空。旧状态JSON仍写RUNNING，不能作为实时依据。B0/E0、B1/E0已完成；B0/E1最新状态只证明epoch1已提交，epoch2进度快照不是完整epoch收据。见[运行事件](RUN_STATE_CHANGE.md)。[RUNTIME、V7]
- v7 发布登记的 **667 个源码/配置/启动器 pin 全部匹配本机原文件**。隔离建立时副本也完全匹配。修复只改变隔离副本中的一个候选接口；该副本因此不再是可直接执行的原发布版本。[evidence/v7_code_identity.json](evidence/v7_code_identity.json)
- 新确认并隔离修复 **1 项 P1**：seed2028 前序检查只识别旧 seed2027 fresh 账本，无法识别获批 v7 的实际完成账本。失败复现后最小修改，5 项针对性回归通过。未触碰 seed2028 执行授权门。[FIX_LOG.md](FIX_LOG.md)
- 未发现本轮需要修改现有 B0/B1 模型或科学协议的新缺陷。GFS 来源/vintage、上尾欠覆盖、历史恢复治理缺口等仍需研究者判断；没有以工程修复代替这些判断。

本轮审查新发起的正式更新、推理、原始观测/2025 数据读取、checkpoint payload 读取、训练环境修改、实盘账本查询均为 0。未停止、暂停、重启任何进程；没有访问训练 GPU。没有运行训练入口、控制入口、发布核验入口或完整旧测试套件。CIM 进程命令行查询被系统拒绝，改用 Get-Process 与创建时间核对；未验证当前 native Job 的成员全集。[RUNTIME]

运行保护的结果不能写成“v7始终正常运行”或“审查对共享资源零影响”。本轮未发出任何控制命令，源码pin始终一致，但与训练共用机器上的Git副本建立和元数据解析仍会使用CPU、内存及磁盘资源。**在建立副本前未核验共享系统commit余量，是本轮审查安全流程的缺口。**没有本轮全部进程的连续commit峰值记录，不能排除资源叠加，也不能把现有内存压力归因于某个具体进程。观察到保护退出后停止额外资源验证，仅完成证据与报告；未恢复、加预算或放宽资源阈值。

远端 GitHub compare 只读请求返回 404，不能确认远端 main 的最新 SHA，也不能解释为仓库不存在。此次结论绑定本地实际版本，修复只在本地分支提交，不宣称已发布。

## 2. 科学版本与适用范围

沿用 Scientific Freeze v1.1、B1 样本/共享 scaler 的后续批准、2026-10-07 Scientific Freeze v2 及其冻结 Phase-A 协议，再追溯后续正式执行/恢复指令。冻结时刻的 `TRAINING_AUTHORIZED=false` 和后来单独批准的执行可以同时为真，不能把历史快照改写成实时状态。冻结登记的 15 个可读引用 SHA 一致；私有 mask payload 未重开，保留其已有验证证据。[FREEZE]

v7 的直接人类指令、具体 B1/E0 epoch7 LAST SHA、原授权祖先、364,969 累计尝试上限和禁止自动重试均在 release/authority 中明确绑定。普通 config 仍标注 PREPARATION 并不是授权，实际权限来自后续独立指令。未将候选 DG 决策表当成最新版许可。[V7]

在已检查仓库内未定位到可独立引用的 V1.3 计划全文。因此研究主线兼容性依据本次研究者明确列出的链路、现存冻结记录与后续批准核对；不能宣称已逐条验收 V1.3 全文。B2–B8 也未被擅自恢复到旧候选规则。[MAINLINE]

## 3. 数据与 Stage 0

|模块|真实完成情况|本轮结论与局限|
|---|---|---|
|Himawari/B13|Stage 0 reader/QC/index；后续 2023/2024 六槽审计与 M1 严格样本冻结均有真实证据|对 70,560 条现有帧元数据及 20,956 个配对场景做元数据复核，名义槽、CF 因果、有效像元和配对目标未发现不一致；未重读观测载荷。[DATA]|
|IMERG V07 Final|产品来源、48 半小时 granules、单位、裁剪坐标、有效零雨和 missing 区分均已实现|当前目标窗为 `[window_start, window_start+30min)`，分析时刻为窗末；历史槽为分析时刻前 60/50/40/30/20/10 分钟。它支持回顾反演定义，不能表述为预测窗末之后的未来降水。[DATA、SPATIAL]|
|QC/mask|读 packed 值时先关自动 mask/scale，按 FillValue/valid range 构建 mask，再解码；B1 M1 拒绝任何不完整槽|有效参考与云南 mask 取交集，当前冻结样本每场 3,430 格。当前代码路径无未来帧 fallback，无静默缺失填零。历史工程 partial 策略不替代后续 M1 批准。[DATA]|
|共享 normalization|2023-only，10,455 场 × 6 槽；μ=271.60515414265217 K，σ=19.93959597783802 K，ddof=0|B0-Matched 与 B1 共享冻结 scaler；2024 不参与拟合。原独立 B0 的旧 scaler/样本人口不同，不能混为同一配对对照。[DATA、FREEZE]|
|科学输出网格|实际坐标位模式固定；SP04 为显式 10,000×25 成员映射，输出 100×100|reader 检查实际轴；投影按冻结成员索引平均，保留源边缘作为卷积 context。未擅自翻纬度、重建中心或插值；本轮核对公开网格元数据，未重开私有 mask。[SPATIAL]|
|GFS main/thermo|main 24,388 文件与 thermo 12,960 文件有 metadata/time/grid/兼容性审计；研究期 8,820 对 T/RH 候选有结构证据|主库单独缺 T/RH，不能据此说所有来源缺 T/RH。main+thermo 仍 PARTIALLY_COMPATIBLE，未正式组合；非全像元有效性验收。[GFS]|
|GFS 时间/来源|init+lead=valid 及源 token 等调查已完成|17,665 辅助时间冲突及其中 3,628 stale-history 已分类，不是新增真实起报冲突。转换代码/内容链和历史首发时间仍缺；init+5h 是假设，release/vintage 尚未冻结。[GFS]|
|DEM|237 SRTM tiles 真正完成覆盖、CRS、像元 QC、共享边界等审计；云南覆盖 FULL；另有33×33真实地形物理距离梯度smoke|真实smoke使用WGS84椭球距离，但不是生产特征或高程精度验证；生产投影、尺度、聚合和缺测规则尚未全部冻结。AWS Skadi 三块不能作为已完成云南替代源。[DEM]|

配对元数据复核结果：[paired_data_contract.json](evidence/paired_data_contract.json)。2023/2024 样本分别 10,455/10,501，B0/B1 sample ID 顺序及目标路径、索引、SHA 相同，六槽 oldest-to-latest，所有选中观测 `obs_start≤obs_end≤analysis_time`。其中 **27,880 次 scene-slot 引用的 date_created 晚于分析时刻**，与已有审计一致；不等于发现未来观测，却明确限制“当时实时可获取”的论断。没有把文件创建、下载或转换时刻当作首发时刻。[DATA]

### 2025 封存必须准确表述

现有证据支持“尚无已授权的 2025 模型最终评价、无已发表最终测试指标”，**不支持“2025 像元从未读取”**。2026-10-03 曾经有研究者明确批准的 catalogue/QC-only 执行，旧收据记录 2,676,986,256 次像元读取，候选 10,272、eligible 10,244、reject 28；同时记录模型 forward、checkpoint load 和 outcome summaries 暴露均为 0。Stage 0 的历史定向审计也包含部分 2025 源检查。[TEST2025]

本轮仅阅读这些旧授权和访问审计 JSON，没有打开 catalog 对应数据、重做 QC 或访问 2025 目录。当前训练记录 `PIXELS_2025_READ=0` 是相应执行作用域的声明；历史路径属性访问仍 `NOT_INSTRUMENTED`，不能外推系统级“从未接触”。未来论文中封存/独立性措辞仍由研究者结合这段历史决定。

## 4. B0、B1 与 Phase-A

|版本/任务|真正执行状态|证据边界|
|---|---|---|
|原独立 B0 Phase-A|19 个完整 epoch，BEST=11，2024 验证 11,727 场|已有正式训练及全量只读复核；不是后来的共同交集 B0-Matched。[OLDTRAIN]|
|原独立 B0 FinalFit|历史上完成 11 epoch、128,964 次更新|是旧授权范围的完成事实，不能当作本轮 FinalFit 许可或 2025 测试已完成。[OLDTRAIN]|
|v1 B0-Matched/B1 Phase-A|分别 21/16 完整 epoch，保留轨迹更新 109,788/83,648|B1 旧收据另记丢弃 5,228、全部实际尝试 88,876；不能只用保留数计算成本。[OLDTRAIN]|
|v1 paired Phase-B FinalFit|B0-Matched 第5轮物理分位数 overflow 后失败；完整 epoch=4|50,537 实际更新，LAST update=41,912；没有完成这轮 FinalFit，B1 未因此获准启动。[OLDFAIL]|
|v2 配对 Phase-A|两模型均 17 完整 epoch；BEST 均 epoch9/update47,052|有全量 10,501 场 BEST 复核和后续证据 hardening；开发集结论仍非独立最终测试。[PHASEA]|

当前 v2 定义：发生概率为 `P(R>0.1 mm/h)`；雨标签在原始 float32 上比较。条件分位数为 `log1p(R) | R>0.1` 上的 32 个 τ，`τ_i=(i−0.5)/32`。归一化正权重累计比例与独立 span 形成严格递增 qlog；训练路径不隐式 expm1。物理转换仅显式 FP64 执行，溢出/失序报错，不 clamp/sort/修补。[MODEL]

这是发生概率与条件分布的阈值截断表示，未建立完整细雨分布或任意高阈值尾部外推。`p×mean(32个条件物理分位数)` 是诊断代理，不能宣称精确 `E[R]`。没有将 v2 新模型定义偷偷回写到已经封存的 v1。[MODEL]

令 N 为有效云南暴露，R 为其中真实有雨暴露，`S_qr` 为有雨像元逐 τ 平均 pinball 之和。共同 Core=`(S_occ+S_qr)/N`，Conditional Pinball=`S_qr/R`；后者在 log1p 域。E0/E1/E2 训练权重不同，验证共同 Core 始终用 E0 的 gamma2/lambda1，不能直接跨臂比较加权训练 loss。[METRICS]

Brier 在全部有效云南格包含干像元；AUROC 按真实输出的精确相同分数组排序、并列半分，AP 按同组末端 precision 的非插值口径。BF16 同分数必须保留，不能从十箱可靠性图近似排序指标。概率二分类 cutoff 未冻结，所以 POD/FAR/CSI 不能补算成正式结果。[METRICS]

v2 Phase-A 的 B0/B1 Brier 为 0.0968676263/0.0952534705，AUROC 为 0.8863570373/0.8934688218，AP 为 0.5672326912/0.5859049245；Conditional Pinball 为 0.1248854583/0.1241132229。既有探索区间对 conditional pinball 差异跨零，不能概括为所有指标均确定改善。强雨层误差和 q32 欠覆盖继续保留。[PHASEA、ANALYSIS]

## 5. Phase-B、恢复与历史真实性

seed2026 六组 E0/E1/E2×B0/B1 全部 epoch9 COMPLETE：54 份 epoch 收据可重算 digest，Train/Development 人口及配对排列一致，公布表中六项核心指标可从最终 receipt 追溯，最终 LAST SHA 与完成账本导出一致。[seed2026_receipt_audit.json](evidence/seed2026_receipt_audit.json)

其保留轨迹总更新为 **282,312**；历史累计消耗 **298,474**，包括 **16,162** 丢弃尝试，无退款。完成材料分布在 `seed2026_v2` 和 `seed2026_operator_v3`，前者早期 `final_status=RUNNING_NOT_COMPLETED` 是启动快照，不应覆盖后者的完成证据。六份最终 payload 与 42 项异盘备份已有独立 SHA 审计，本轮继承该证据，不重新打开权重；这也不是验证全部历史 checkpoint 当前均永久可恢复。[SEED2026、BACKUP]

seed2027 v7 的旧累计 reserved/verified 为 166,305/166,304，保留祖先 83,648，丢弃/不确定总计 82,657；旧的 1 次不确定尝试没有被升级为成功或退款。v7 自身剩余额度 198,664，合并上限 364,969。退出前最后状态快照显示累计187,161/187,160，新20856/20856，B0/E1 run_updates10400；这些数不是退出时实际最终账本，未据此判定最后一次更新或epoch2完成。[RUNTIME、V7]

|历史版本|可确认的失败/修复事实|不能声称的内容|
|---|---|---|
|epoch7 recovery v4|11 项 delta 检查通过，但 v5 的祖先记录确认 v4 零新增更新、spawn failed/uncertain、缺原 termination receipt|测试通过不等于真正启动成功；现有公开材料不足单独确定其接口根因。[RECOVERY]|
|v5|真实 traceback 为缺少 re-export 的 `COMPLETE_PREFIX` ImportError，零新增更新|旧故障源码及失败收据未改写；本轮未重新执行旧失败入口。[RECOVERY]|
|v6|补回所需接口；随后真实零更新 watchdog Job snapshot WINERROR_5|“接口修复发布”仍不等于执行成功。[RECOVERY]|
|v7|绑定新的人类零更新重发指令；真实恢复证明及B1/E0 epoch8、epoch9完成结果存在；随后B0/E1期间触发AVAILABLE_COMMIT_LIMIT保护退出|既非六组完成，也非当前仍在运行；原RUNNING快照已陈旧，缺原supervisor termination.json，不补造。[V7、RUNTIME]|

历史 v2 B1 Phase-A 的独立 LAST-bound 恢复批准仍未在登记记录中找到，状态 `HISTORICAL_RECOVERY_RATIFICATION=NOT_GRANTED`。BEST9 早于 LAST14/恢复15，不能据此自动豁免整个后续训练历史。现有治理记录区分保留 88,876 与全部尝试 92,353；该偏差由研究者决定，不补签、不抹除。[GOVERNANCE]

没有新发现足以认定重复计费的证据。可确认存在因中断丢弃并获批重放的计算，账本未退款。当前审查未穷尽所有旧 SQLite/event log，故不承诺所有历史异常均已经解释；v4 缺失原终止收据、旧 1 次不确定尝试与治理缺口均保留。

## 6. 风险与修复分类

|编号|级别/性质|结论及处理|
|---|---|---|
|P1-001|真实后续工程接口缺陷|已隔离修复 seed2028 的 seed2027 前序账本识别；不改变科学矩阵、更新额度或执行权限。详见 FIX_LOG。|
|RUN-01|P0级运行安全事件，未确定新代码缺陷|v7因AVAILABLE_COMMIT_LIMIT保护退出；内存压力来源未定，原RUNNING快照陈旧。保留新事件证据，禁止自动恢复/改上限；资源与具体LAST/额度问题交研究者决定。|
|H-P1-v5/v6|历史真实运行故障|已有后续版本修复与 v7 实际执行证据；本轮复核，不重复修改旧版。|
|G-01|科研治理重大风险，P0 级审查关注|历史 B1 恢复独立批准缺口未追认；研究者决定可用性和处置，不能作为自动作废/自动通过的工程结论。|
|G-02|科学完整性风险，P0 级审查关注|2025 曾获批 catalogue/QC 读取；禁止写成从未读取或已有最终测试结果。仅保存事实，不改变测试划分或历史记录。|
|S-01|科学解释/外部有效性限制|q32 欠覆盖、强雨层不稳定、极端条件高分位暴露、单年开发集反复使用，均不属于可通过改阈值修好的软件缺陷。|
|I-01|后续未完成接口|GFS main+thermo/vintage、真实 DEM 特征/压力掩膜、DOTE/DTFM 与 B2–B8 尚未形成正式训练链；未实现项不记 PASS。|

没有据此确认可直接打补丁解决的v7 P0代码根因。RUN-01只作事件记录与研究者决策，不介入运行控制。P2 格式、重复目录、性能和架构清理不执行。

## 7. 科学主线与最短推进路线

现有科学链真正落地到“B13 单帧/六时相 → 配对网络 → 发生概率与条件分位数”。GFS/DEM 审计、33×33真实地形梯度smoke及后续synthetic地形数学已经有证据，但没有正式 GFS Dataset、地表以上 pressure mask、动态 DOTE、DTFM 多尺度调制或 B0–B8 全消融执行。[GFS、DEM、MAINLINE]

地形候选 `terrain_fields` 使用米制 dx/dy、列向东/行向南；当前 IMERG 纬度轴向北递增，未来适配时必须显式处理轴方向，不能直接套 stencil。梯度应用真实物理距离；气压层和 PS 统一单位后排除地下层；这些原则已存在，但真实掩膜/动态水汽强迫尚未验证。冻结 100×100 SP04 科学输出、3430 云南格、现有概率输出与后续辅助分支在接口上无已见硬冲突；这不是已实现 DOTE/DTFM 的证据。

对已保护退出的v7保持现状，不自动恢复；现在只整理既有来源。研究者先处置运行资源事件，并解决 GFS main/thermo 来源可接受程度与 vintage 语义，再限定 2023/2024 的小范围 GFS 接口验证；DEM 复用既有237 tiles/真实梯度smoke，先决定导数尺度和聚合，再做最小生产适配；两者身份/单位/掩膜就绪后才进入独立 DOTE/DTFM 开发任务。不得为推进这些工作自动新增训练、访问2025、启动seed2028或FinalFit。[NEXT_RESEARCH_STEPS.md](NEXT_RESEARCH_STEPS.md)

## 8. 六项验收回答

1. **真完成**：数据索引/QC与配对冻结、旧 B0/B1 正式训练、v2 Phase-A、seed2026 六组及分析、seed2027 两个 E0；**候选/未完成**：seed2027 其余臂、seed2028、正式 GFS/DEM 接入、DOTE/DTFM/B2–B8、2025 最终评价。
2. **真实新缺陷**：P1-001 已最小修复且有前后日志；历史 v5 接口与 v6 watchdog 故障已有 v7 后续执行证据，保留旧失败。
3. **可信度约束**：共同人口和主要指标追溯支持 B0/B1 的开发性比较；历史恢复治理、上尾/强雨表现、反复使用的开发集和业务可用性证据不足限制科学结论。
4. **历史完整性**：seed2026六组/54收据与最终LAST引用一致；不能宣称所有历史epoch载荷现存可恢复或所有失败有原始termination receipt。v7已保护退出，B0/E1最后完整边界及实际最终尝试账本未新核验，不具备六组最终验收条件。
5. **有证据**：六时相在现有开发集总体发生识别有方向性收益，seed2026 E1 的 Brier 改善、E2 的 B0 q32 覆盖改善有探索证据；**不能成立**：所有强度全面优越、确认性成功、真实业务实时可用、独立 2025 泛化或 DOTE/DTFM 有效。
6. **最少工程**：不自动恢复v7，保留运行事件；复用审计先完成GFS来源/vintage决策与DEM生产参数，然后按真实单位/坐标/压力有效层建立小接口；不重做已有效训练或全量审计。

本次审查覆盖 A–D 的任务清单和关键实现/证据链，并不声称逐行审查所有历史副本、重新验证原始数据全集或获得平台级历史访问证明。跳过项及其理由见证据矩阵。
