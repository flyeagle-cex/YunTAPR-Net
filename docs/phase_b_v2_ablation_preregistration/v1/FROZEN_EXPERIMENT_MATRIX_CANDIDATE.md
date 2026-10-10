# 拟冻结实验矩阵（尚未批准）

PROPOSED_FOR_RESEARCHER_APPROVAL；NOT_EXECUTED。这里形成可审批、可计算、可审计的单一提案，并未改写 Phase-A frozen 文件。

## 主矩阵

|条件|alpha|gamma|lambda_q|相对E0唯一损失因素|模型×seed|
|---|---|---|---|---|---|
|E0|0.5|2|1|无，fresh v2 baseline|B0-Matched-v2/B1-v2 ×2026/2027/2028|
|E1|0.5|0|1|gamma|同上|
|E2|0.5|2|2|固定 Pinball 权重|同上|

18个运行ID为 E{0,1,2}__{B0_MATCHED_V2,B1_V2}__s{2026,2027,2028}，机器表逐行枚举，未创建 run 输出、参数或 optimizer。E0不直接复用历史 BEST；三个条件同 seed 同模型的完整 fresh state 必须相同。

## 配方与数据角色

D1：2023年3–10月冻结训练10,455场景，2024年3–10月冻结开发验证10,501场景；Q1：两模型相同M1配对资格与样本/标签身份；N0：同一冻结2023 shared scaler，不refit。I3：预声明seeds2026/2027/2028，每seed按原独立reseed、同名同形状拷贝策略建立一对fresh锚点。B9：每run固定9个完整epoch，47,052更新，无丢样本/重复补尾/accumulation。S0：W=5,228，U=261,400，保留50-epoch余弦轨迹的前47,052步。V0：统一选择完成epoch9，禁止根据任一loss、验证结果、seed或时相改终点。

旧训练函数的seed2026与gamma2均硬编码；增加seed参数和损失参数以后需要研究者核心代码审查及工程集成批准。本轮JSON不能让旧runner自动支持18个运行。

## Fresh、顺序与执行次序

每seed分别重新设定Python/NumPy/CPU/CUDA初始化随机状态，创建B0锚点及独立reseed的B1；只拷贝同名同shape张量，B1两处输入shape不同权重保持native初始化，零skip惯例不变。对每模型固定锚点逻辑SHA及序列化字节SHA，E0/E1/E2复现完全相同初态；不把历史BEST/LAST、optimizer、scheduler、RNG或恢复批准当fresh来源。初态身份本轮NOT_YET_MATERIALIZED，不能填假SHA。

同seed跨三个条件及两个模型使用同一 sample-ID 排列。候选推广规则是 CPU Generator(seed+zero_based_epoch_index)，train每样本每epoch恰好一次，validation冻结顺序；无增强。跨seed改变初始化及种子控制的排列，属于训练随机性重复，不是独立天气重复。相邻seeds加epoch可能出现相同随机种子，不能宣称各排列相互独立。实际种子环境及排列SHA未来逐epoch登记。

候选串行队列：seed2026先E0/B0、E0/B1、E1/B0、E1/B1、E2/B0、E2/B1；另两seed同次序。固定顺序方便审计，但可能受机器负载/时间漂移影响；硬件及软件环境必须固定，负载变化登记，不能将耗时当loss科学效果。未来若随机化队列须执行前版本化批准。

## 验证与停止边界的提案选择

保留每epoch全2024只读验证和上尾诊断，checkpoint仅在TRAIN与VALIDATION均完成后保存。V0固定终点只改变选择规则：epoch1–8不是BEST候选，不按core early-stop；epoch9作为主终点。原Phase-A patience8/min_delta1e-4不应用于本B9消融，9epoch是所有臂统一的预定停止预算，异常安全停止仍有效。这项新选择/停止规则需要科学批准，不称“原runner无需变更”。

每run有9×1,313=11,817验证batch，18runs共212,706。epoch9的一次forward可供core、全指标和只读observer共同使用，未来若实现无法复用，必须登记额外推理预算并另批。只验证终点会使checkpoint边界及逐epoch诊断变化，不作为本提案默认规则；上一候选23,634是18个终点的一次评价下界，本轮没有重写历史预算。

## 两阶段批准

阶段1单独执行批准才可运行seed2026完整6run矩阵，282,312更新；不能只跑有利臂。阶段2独立执行批准再补seed2027/2028共12runs、564,624更新。阶段间只审查安全、资源、完整性和批准范围，不根据阶段1模型表现调整矩阵、主指标或threshold。若决定停止扩展，公开报告为计划18但仅完成6及原因；单seed不构成完整I3证据。

运行中断不替换seed、不自动增加epoch、试参数或无限重试。任何LAST恢复都需要具体LAST字节SHA、逻辑state身份、原授权祖先、下一完整epoch、剩余预算及独立人类恢复批准。详细审批与恢复方案见安全交接；本轮没有执行任何阶段。
