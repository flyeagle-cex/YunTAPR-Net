# 阶段验收统一入口

B5/B6终态元数据时点：`2026-10-27T07:30:47.980516+00:00`。B7/B8后续状态由独立启动/终态收据和本次Git提交绑定，不把该旧时点冒充新训练时间。B0–B4限定基线交接为 **COMPLETE_WITH_LIMITATIONS（带局限完成）**；B5/B6为 **COMPLETE_TRAIN_AND_DEV_EVALUATION**，地形单seed消融带局限完成；最终泛化验收为 **NOT_VERIFIED（未核实）**。最新B7/B8三seed固定E9训练/评价及三seed描述性分析已完成，创新收益混合，限定验收COMPLETE_WITH_LIMITATIONS。 本轮论文级审计/离线诊断完成；DOTE零数值主对照NOT_STARTED，2025方案DRAFT，论文强物理归因与最终泛化验收仍未通过。不能把训练完成等同于全部科学假设通过。

|模型|已经完成|尚未完成或限制|本阶段判断|
|---|---|---|---|
|B0/B1|seed2026、2027，各E0/E1/E2固定九轮Train/2024 Dev|两seed；10,455/10,501人口；历史执行commit绑定不完整；历史不确定尝试未追认|限定人口内基线对照可交接|
|B2|seed2029/E0/f006，九轮、4,320更新及2024 Dev，固定E9 LAST|仅一seed；B2/B3指标方向混合，未证明时序增量全面改善|当前探索性配对条目完成|
|B3/B4|2029/2030/2031三个独立seed的九轮Train/Dev及固定E9配对|强雨和q32缺陷、同一开发年，未证明最终泛化或统计显著性|描述性随机性复现完成|
|B5/B6|seed2029/E0/f006各九轮Train/Dev、4,320更新、固定E9权重身份与B4公平配对均完成|仅单seed；总体收益混合、q32和强雨仍有退化、DEM发布链未验证|训练/评价完成；探索性地形消融COMPLETE_WITH_LIMITATIONS|
|B7/B8|2029/2030/2031各九轮Train/2024 Dev、固定E9及三组配对完成；原62/441重放保留|仅总体AUROC三seed同向改善，AP/Pinball/q32不稳定，Brier/强雨仍退化；DOTE单独增量及最终泛化未验证|COMPLETE_TRAIN_AND_DEV_EVALUATION；科学验收COMPLETE_WITH_LIMITATIONS|
|DOTE零数值主对照|同B7架构、真实mask、全初值逐位匹配；7项新CPU检查通过|128权重无损失梯度，不能称有效容量完全匹配；新科学选择/预算未批准|NOT_STARTED|
|论文/最终测试|主张分级、精确经验Brier分解、35周块探索性区间和预注册草案完成|无独立暴雨ID；2025全模态人口/新适配器未核实，未解封|PREPARATION_COMPLETE；强归因/最终泛化NOT_VERIFIED|
|2025最终测试|继续冻结|没有当前最终模型推理与评价|NOT_STARTED，不得据此选模|

## 同人口比较范围

- B0/B1：同seed、同E臂的10,455 Train / 10,501 Dev，允许比较单通道时序增量。E0/E1/E2分别记录，损失臂及恢复不算新seed。
- B2/B3：seed2029，959/963，E0/f006、固定E9 LAST。B2为7通道×1时次t−10分钟，4,332,290参数；B3为7×6，4,349,090参数。槽位权重映射乘sqrt(6)，其余72个兼容张量同初始化，不宣称模型完全等价。
- B3/B4：三seed各自共享959/963、初始化兼容部分、顺序与评价掩膜；B4增加13变量GFS MEE（气象环境编码器）。跨seed改变初始化与排列，恢复重放仍属于原seed。
- B5/B6：已与B4 seed2029在同人口、同初始B4身份、同顺序、同评价口径下完成固定E9配对。不得跨B0/B1与B2–B6的不同训练人口直接归因架构优势。

## 当前训练状态

以下为一次只读元数据快照，不是实时页面，也不把已封口的一轮当作九轮完成。

|模型|seed|阶段状态|执行状态|已返回更新|完整Train/Dev轮数|
|---|---|---|---|---|---|
|B7|2030|COMPLETE_TRAIN_AND_DEV_EVALUATION|COMPLETE|4761|9|
|B8|2030|COMPLETE_TRAIN_AND_DEV_EVALUATION|COMPLETE|4320|9|
|B7|2031|COMPLETE_TRAIN_AND_DEV_EVALUATION|COMPLETE|4320|9|
|B8|2031|COMPLETE_TRAIN_AND_DEV_EVALUATION|COMPLETE|4320|9|

## 本轮交付核对

五个根目录文件为统一入口，旧报告和实验收据保留。矩阵含36条历史/当前记录；不是36个独立seed或36个已完成模型。新增四任务全部九轮/有效4320；B7/2030实际4761尝试含441重放，其余各4320。新段14400、累计17721；三seed含旧2029，恢复不是独立seed。`epochs`表示该记录已封口轮数，`global_steps`为实际RETURNED计数，失败时可高于最新保存更新；训练完成须同时具备全部Train/Dev收据、账本、预算和固定E9身份。

仅核对新增30轮Train/Dev、60气象账本、4静态账本、4份实际E9 SHA、初始化/顺序及已生成三seed汇总算术；旧六轮和全部既有结果继承。0新模型推理/权重加载/原始载荷/2025读取。 本轮再追加7项新控制/诊断CPU测试、一次成功真实静态缓存CPU初始化及离线算术；准备缓存两次共625656字节含一次环境门控失败，0正式更新。六套既有Dev元数据和精确分数计数用于诊断，无原始气象载荷/权重/新推理。

本轮出版基线：`e81c6e1e0306e2a1e31103f1cc632be3c0d84d8c`。文件所属最终提交由Git历史标识；实际训练代码另见[矩阵](EXPERIMENT_MATRIX.csv)和[证据索引](EVIDENCE_INDEX.md)，不得用本次文档commit替代执行commit。

[实验矩阵](EXPERIMENT_MATRIX.csv) · [完整数值与差值](METRICS.csv) · [科学分析](SCIENTIFIC_ANALYSIS.md) · [证据索引](EVIDENCE_INDEX.md)

## B7/B8三seed固定E9完成：COMPLETE_WITH_LIMITATIONS（带局限完成）

完成于北京时间 `2026-10-29T07:19:48.193141+08:00`；[新增30轮封口、60气象账本、4静态账本、4份实际E9 SHA及三seed汇总](docs/research_readiness/20261025/evidence/b7_b8_three_seed_completion_20261029.json)已核对。2030/2031四模型均为COMPLETE_TRAIN_AND_DEV_EVALUATION，旧2029原值与62次重放记录继承，恢复不算额外seed。

执行代码`e81c6e1e0306e2a1e31103f1cc632be3c0d84d8c`；准确恢复提案SHA `3314231ac64531bf523a06d5ff8e3dc4f688d705fc4f4324b57c1548a846aa3e`。新段14,400更新含441必要重放，累计17,721实际尝试；新源读取1,591,906,721,352字节/476,044次，累计1,934,666,227,950字节/578,566次，额外重放/重试均0。新包mtime区间约15.2679小时，低于21.2239小时上限；保守计入旧9,994秒后约18.0440小时，仍在原24小时内。这里是文件mtime区间，不是GPU计算计费；分模型实际量及上限见收据。

DTFM仅总体AUROC在三seed同向改善；AP、条件Pinball、q32未稳定复现，Brier在两个seed退化。科学假设没有因工程完成而自动通过。B7/B8共享条件信息、4,411,058活跃参数、公共初始化与同seed顺序，比较的是concat残差与有界DTFM的替换融合。2025冻结，没有新增推理、调参或训练授权。
