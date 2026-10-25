# B2 七通道单时次训练与配对评价报告

**正式训练：NOT_STARTED；B2/B3 配对结果：NOT_VERIFIED；准备工作：已完成可复核候选，等待研究者审查。**

核查时间：2026-10-25T17:42:33+08:00（北京时间）。研究者为主体，AI 仅辅助核查和实现。本文文件已生成，不代表正式实验或科学验收完成。

本轮授权范围：用户明确确认历史 B3/B4 seed2029 和获批重放不能授权本轮 B2 或新 seed；本轮只做核查、方案、预算和合成测试。正式训练更新=0，原始气象数据读取=0，checkpoint（检查点）反序列化=0。另对两份旧 LAST 权重读取文件字节计算 SHA256，未做推理。

2025最终测试期继续冻结：本轮不读取其原始载荷、不推理、不调参或探索性选模；历史catalogue/QC访问事实单独保留。

版本：GitHub main=`6c505d0ec63ed39f679720b82a65f601139dcd35`；本地代码基线=`0ccb3e26e2d50494aba07788fa94dd40ec89b4aa`；seed2029 恢复执行=`7fa609e89bdb8b744bb0e7eebc9e7b5c3a703e35`，首次准备=`5b5298f41025db5b7b718fd736fc3fe6de516875`。本轮最终代码提交见交付消息及 Git 历史；可执行文件 SHA 绑定在最终提案和 `DELIVERY_MANIFEST.json`，不在文档内编造自引用提交。

证据入口：[本轮本机状态](evidence/state_audit.json)、[重新读取129个原件来源的清单](rechecked_snapshot/evidence/source_manifest.json)、[原公开证据边界](../../research_progress/EVIDENCE_INDEX.md)。两次独立摘录的22个实验及126轮数值须相同；核查不等于重跑模型。

## 已恢复的真实状态

本机检查17个 Git 工作区、103个指定输出范围内的 checkpoint 文件条目；已有未提交运行记录保留原状。状态快照中匹配的 Python/训练/WSL/SSH 进程为 0；只代表本机观测时刻。未发现比 seed2029 更晚的 B2 或其他 B3/B4 seed 完整收据；不宣称遍历所有主机或全部磁盘。

B0/B1：seed2026、2027 的 E0/E1/E2 共12组正式九轮配对结果；B3/B4：seed2029/E0/f006 各九轮。B2 原来只有7通道接口；本轮新增候选初始化、输入适配和带授权门控的执行器。执行器真实数据完整链路仍为 NOT_VERIFIED，不把候选代码测试写成正式完成。

B3/B4 的第九轮权重文件已重新哈希：B3=`c7780bc6e45992639c90339c88553fe3a722f6d9681bd247a82ad2dce0c08283`；B4=`7c74eb80ab7d754e3262781d85ac370b2319c3bf27d37ac362860c104acfb34d`。完成判据还包括18轮 Train/Dev/LAST 绑定及只读更新账本；累计9,120次历史返回中，8,640次保留、480次获批重放。重放不是独立 seed。

## 待审的公平比较协议

|项目|B2 预案及与 B3 的关系|
|---|---|
|数据人口|固定2023 Train=959、2024 Development（开发集）=963；f006、3–10月、00/06/12/18 UTC；完全继承六帧七通道共同 QC（质量控制）资格|
|人口版本|`2f2cc75cfb6c209fd8195d3419207216c5c3f2a4fc8315b40a1d77cc537dedb8`；populations 文件 SHA=`ea6abae6a493f2abdf19f938365407a35f0f0be71ba1346241264635318a32d2`|
|统计版本|`53ab2f07aabb02e66ad237452447a35e0e2896278eae9d2da179336c06fea980`；标签 QC SHA=`b4bad8ea45a78eddae3832df89cfade00cac3b184fc550eea4f0cf479c29de90`|
|输入|B08/B09/B10/B11/B13/B15/B16；建议选择 analysis−10分钟的最后一帧（slot5）；B2为7×501×501，B3为42×501×501|
|标签与时序|沿用分析时刻结束的半小时 IMERG Final V07 标签；六帧位于分析前60/50/40/30/20/10分钟；属于 retrospective（回顾估计），不声称业务近实时|
|归一化|所有通道仅来自2023 Train；六个新增通道使用959场景×6槽位统计；B13继承旧2023训练冻结统计，未在959人口重拟合。不能写成七个通道均由本次959样本重新拟合|
|损失与终点|E0不变、32个冻结条件分位数、九轮固定第九轮 LAST；不选 BEST，不调上尾损失|
|优化器|AdamW：lr=1e−4、betas=(0.9,0.999)、eps=1e−8；仅Conv2d核weight decay=1e−4，其余偏置/GN仿射=0；全局梯度范数上限5|
|学习率|首480步线性warmup（预热）；保持50轮/24,000步余弦原轨迹的前4,320步，不把学习率压缩到九轮归零|
|batch与更新|Train batch=2，最后一批1场景，每轮480步；Dev batch=8，每轮121批；4,320步，无重放额度|
|随机性|seed=2029；Python/NumPy/PyTorch/CUDA、确定性算法、禁TF32、禁cuDNN benchmark；BF16 autocast（混合精度）与原分位数高精度参数化一致|
|顺序与评价|全部九轮样本顺序已与历史B3逐项相同；目标SP04映射、3430云南有效像元/场景、发生事件float32(rate)>float32(0.1 mm/h)、精确分数AUROC/AP保持不变|

初始化是待研究者冻结的核心条目：先按历史 seed2029 构造全新 B3，实际复现其初始化 SHA=`a8a0731e309d6ddd1765a753707bf334e1f1fd7f66d7b24e581748ddfe7ddc2e`，再复制72个形状兼容张量给 B2。输入层两组核从42维变为7维，候选取最后槽位并乘sqrt(6)校正fan-in（输入连接数）方差；skip核原本为零。其余兼容张量逐位相同。B2参数4,332,290，比B3少16,800；不能声称两模型参数量或首层完全一致。此映射不是既定科研决策，只有批准 `LATEST_SLOT_FANIN_RESCALED_SQRT6_PROPOSED` 后才可执行；若研究者选择另一初始化，必须重新生成提案及收据。

缺测与泄漏检查：Train/Dev ID不相交；清单年份和月份、每个槽位偏移、obs_end≤analysis均通过元数据检查。B2仍拒绝任一历史槽位/通道无效或非有限的样本，不因只消费最后一帧扩大人口。现加载器沿用六帧和GFS读取，B2 forward（前向计算）仅接收最后7通道，不向B2输入GFS。输入维数改变会改变算子计算，确定性仅约束各模型在固定环境中的复现，不能声称B2/B3逐步数值轨迹相同。历史GFS实际发布时刻和完整转换链仍不足，故近实时无泄漏声明为 NOT_VERIFIED。真实载荷完整性沿用已有QC，未用本轮元数据检查替代全量重验。

## 代码、验证与可执行入口

新增 `src/yuntapr/experimental/research_readiness/b2.py`、`b2_runner.py`；旧B3/B4执行代码保持不变。`tools/research_readiness/prepare_b2.py`仅读清单/统计/只读SQLite，拒绝打开原始气象文件及权重；生成提案、逐源预算与本机私有准备绑定。`tools/research_readiness/train_b2.py`默认拒绝执行，须明确--execute、研究者批准文件、精确提交/提案SHA及额度。历史授权、占位符或False模板均不能通过。逐步INTENT/RETURNED账本阻止未确认更新重试；遇额度、数据SHA、掩膜、样本顺序或数值异常即停止，保留失败与历史权重。

本轮新增检查覆盖：首层映射与共同初始化、最后槽位/通道序、未消费帧缺测拒绝、授权拒绝、更新上限与不确定状态、配对人口/掩膜漂移拒绝。已用历史CUDA环境跑合成B2前向/反向和验证，未构造优化器。真实全量训练、恢复及模型评价属于 NOT_STARTED/NOT_VERIFIED。

合成显存：Train batch2峰值allocated（分配）=2.745 GiB，reserved（保留）=3.279 GiB；Dev batch8分别为3.596/4.766 GiB。AdamW两份动量另按参数量计算约33.1 MiB；未实际分配，不作为正式峰值证明。详见[GPU收据](evidence/b2_gpu_probe.json)。环境：Python3.12.14、PyTorch2.11.0+cu128、CUDA12.8、RTX5060 Laptop 8GiB。

## 待批准资源额度

|资源|B2单次九轮预案|
|---|---|
|优化器更新上限|4,320；replay=0|
|Train/Dev源遍历|各9次，共18次|
|源读取实例|142,812|
|逻辑源字节|477,571,641,012 bytes（约477.572 GB）|
|Train/Dev单次源字节|26,424,262,556 / 26,639,253,112 bytes|
|IMERG缓存上限|512 MiB；两年唯一日文件合计374,860,979 bytes|
|九份LAST张量理论下限|467,887,320 bytes，另有序列化/RNG等开销|
|评价数据库理论上限|每组256 MiB ×6组×9轮=13.5 GiB，非实际消耗|
|磁盘预留提案|B2新输出预留20 GiB，启动前至少24 GiB空闲；不自动清理旧文件|
|GPU/主机入场|至少5 GiB空闲GPU、8 GiB空闲RAM、2 GiB可用系统commit，执行时重新检查|
|建议运行时间上限|6小时/单模型，待研究者批准；不是已测耗时或费用报价|

这是保守加载器预算，含B2未消费的历史帧/GFS读取；不擅自更改数据流水线省预算。源字节为Python实际接收载荷，不是磁盘扇区流量；不含元数据、checkpoint及评价数据库I/O，不包含另做源验证、重放、归一化重拟合或额外终点评价。历史B4九轮的文件修改时间跨度约3小时51分，仅作本机调度参考，不是严格GPU计时或计费证据。单次冷启动合成耗时不能换算正式总耗时。

## B2/B3 配对评价结果

|指标|B2|历史B3 seed2029|B2−B3|
|---|---|---|---|
|Brier Score（布里尔分数）|NOT_STARTED|0.0995788457841|NOT_VERIFIED|
|AUROC（ROC 曲线下面积）|NOT_STARTED|0.888024778135|NOT_VERIFIED|
|AP（平均精确率）|NOT_STARTED|0.570741767909|NOT_VERIFIED|
|Conditional Pinball（条件分位数损失）|NOT_STARTED|0.129258066651|NOT_VERIFIED|
|q32 Coverage（最高分位数覆盖率）|NOT_STARTED|0.935049776862|NOT_VERIFIED|

**当前没有B2实验结果，无法交付有效的B2/B3数值比较。** 表内B3来自真实第九轮Dev收据，不能充当B2。未来获批完成后，执行器用同人口、同分组、同掩膜的B2 E9收据与历史B3 E9计算差值；不得改换最佳轮。

最终可复核提案：[b2_proposal_v3.json](evidence/b2_proposal_v3.json)；[授权模板（False）](B2_RESEARCHER_APPROVAL_TEMPLATE.json)；[最小运行说明](RUNBOOK.md)。
