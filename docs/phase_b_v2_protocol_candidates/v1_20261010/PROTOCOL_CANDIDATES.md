# Phase-B v2 协议候选

全部选项均为 RESEARCHER_DECISION_REQUIRED，NOT_EXECUTED。以下比较不会改变 Phase-A 既有实验角色或冻结文件。

## 1. 必须继承的科学语义

记 T 为 IMERG 原生半小时窗口起点，监督支撑为 [T,T+30min)，分析时刻 A=T+30min。B1 六帧 nominal 时隙为 A−60、−50、−40、−30、−20、−10min，按旧到新排列；实际观测结束时间必须不晚于 A。B0 使用同一场景最新合资格帧。nominal 时间和文件创建时间本身不证明历史业务可用性；当前实验是因果观测反演，尚未证明实时业务回放延迟。

共用 M1 严格完整六时隙交集；不缺帧回退、不插值补帧、不因 B0 可以单帧工作而扩大对照集合。保留 SP04 坐标映射、100×100 目标和云南中心入界 3,430 格点掩膜。不得依据误差或尾部表现重画边界。监督保留 IMERG V07 Final，不混 V08、Early 或 Late。2023/2024 三月至十月资格身份沿冻结 manifest；2025 封存。原 2023 Train=10,455，2024 Validation=10,501，只是现有开发集合，不是未来独立事件数量。

骨干和双头保持 v2：发生 logit 经 sigmoid；另一头 33 raw 通道（32 allocation + 1 span）产生 32 条件 qlog。设 w_i=softplus(a_i)+epsilon_w，c_i=Σ_{j≤i}w_j/Σ_jw_j，s=softplus(b)+epsilon_span；q_i=log1p(0.1)+s c_i，tau_i=(i−0.5)/32。epsilon、精度与守卫继承冻结 head，FP64 参数化，不新增 clamp、排序修补或通道。q32=log1p(0.1)+s；其物理值是 expm1(q32)，不是确定性雨强。

## 2. 科学目的与可兼容组合

|路线|候选目的与数据角色|可以回答|主要风险与成本|
|---|---|---|---|
|D1 固定开发集合|2023 全部合资格场景训练；2024 保留开发诊断；固定预算 checkpoint|同一集合、初始化和预算下单因素干预是否改变发生校准或条件上尾|2024 已多次审查，任何新结果仍是探索性；每设置每 seed 训练一次|
|D2 开发内分离|在 2023 合资格身份中预先按完整日期块分 Train/Selection/Calibration；2024 仅报告|在拟合与校准角色分离后评估校准干预|2023 训练样本减少、需 train-only scaler；2024 也不是全新独立集；计数待批准分区后从 manifest 取得|
|F1 最终拟合准备|冻结资格规则下 2023∪2024 合并作为训练，理论上 20,956 场景|固定方法使用更多开发数据后的最终模型准备|2024 不能再独立选择或报告泛化；未来独立验证另批；此时没有可启动的 FinalFit|

D1 是机制消融的较简路线候选；D2 是拟合任何校准器前必要的角色分离候选；F1 应在设计锁定、科学验收与恢复偏差处置之后另行决定。选择其中之一不会自动批准其他路线。F1 的 20,956 是整数相加，尚未生成或批准新的合并 manifest。

## 3. Fresh initialization

|编号|候选|科学意义|风险/代价|
|---|---|---|---|
|I1|单 seed=2026；独立 reseed，B0/B1 同名同形状参数配对拷贝；历史参数与 optimizer/RNG 不迁移|复用 Phase-A 初始化语义，尽量隔离时相因素|一个 seed 不能表征训练随机性；是新 run，仍需批准|
|I2|同一预定 seed，两个模型各自完整 fresh，取消同形状配对拷贝|检查初始化耦合的敏感性|初始化成为额外因素，不能只归因于时相；只作独立敏感性臂|
|I3|预定 seeds={2026,2027,2028}，每 seed 按 I1 配对 fresh|在 seed 与日期块两个层面报告不确定性|训练成本为 I1 的 3 倍；三种子仍不足精确估计极端尾部方差|

I3 中三个整数是候选预注册值，未执行、未由表现挑选。fresh 不是仅换 run 名；需以后证明初始化前无历史权重、optimizer、scheduler 或 RNG 状态应用。历史 BEST warm-start 会混入 Phase-A 选择历史，LAST 恢复还涉及审批缺口；不纳入本轮最小矩阵，也不把新 fresh 作为追认历史的手段。

## 4. 数据资格和 normalization

|编号|候选|适用与优点|泄漏/依赖/成本|
|---|---|---|---|
|Q1|保留整个 2023/2024 M1 配对集合及既有角色|D1；与 Phase-A 对照最直接|2024 已用于 BEST 与诊断，不是独立确认集；无新资格算法|
|Q2|对 M1 身份作按日期块的角色分区和边界 purge|D2；减小相邻帧、标签窗口共享|新 partition 本身需批准；不得改变 M1 基础资格或原 manifest；场景数未知|
|Q3|合并合资格 2023/2024，角色统一 Train|F1；开发资料使用增加|失去原 2024 验证角色；不能一边全量训练一边据其成绩调参|
|N0|复用 frozen 2023 shared scaler，mean=271.60515414265217 K，std=19.93959597783802 K|D1 最易解释；B0/B1 使用同一 scaler|如果改用 Q2，原 scaler 含 2023 保留分区输入，是无标签的跨角色预处理，不可称严格 train-only|
|N1|仅获批 Train 角色拟合一个 shared B1 scaler，B0 同用；六帧/像元计权规则显式登记|D2；杜绝 Selection/Calibration/Report 输入参与拟合|需真实 2023 读取的新授权；重叠时隙多重计数与按场景/去重帧权重必须先定；新数值尚不存在|
|N2|F1 合并训练角色重新拟合 shared scaler|最终合并训练的分布适配|不得使用封存 2025；2024 一旦参与 scaler 和训练便不是独立验证；须新 SHA 与数据角色记录|

每模型分别拟合自己的 scaler 会同时改变输入统计和时相，不能用于最小时间信息对照。不同 normalization 可另设单因素敏感性实验，但不能和 loss、预算、数据角色一起变化后声称因果归因。任何重新拟合都只影响新候选实验，绝不覆盖 frozen scaler（SHA=656fe7a929cbd8617b08427e8d1fa7029b26512253efb44faa576796137d4a31）。

Q2 的候选日历例：2023 三月至八月 Train、九月 Selection、十月 Calibration；边界两侧各移除预定 1 日或 7 日，不靠预测挑选。1 日超过输入一小时/标签半小时的共享支撑，但不保证不同天气过程独立；7 日更保守且更少样本。需检查全部实际帧区间与标签区间，保证角色支撑不相交；同一过程不得跨角色。上述日历/间隔尚未选择，不能把原全量计数用于分区后的预算。

## 5. 训练预算与 scheduler

物理 batch=2、accumulation=1、no-drop/no-duplicate 候选继续沿 Phase-A；每 epoch updates=ceil(N/2)。仅从已发表计数计算下表，未测新 GPU 吞吐。

|训练集合|9 epoch updates|17 epoch updates|50 epoch updates|每 epoch 场景|
|---|---|---|---|---|
|2023 M1|47,052|88,876|261,400|10,455（末 batch 单例）|
|2023∪2024 M1 算术候选|94,302|178,126|523,900|20,956|

B9 固定 9 epoch：成本较低、便于固定 checkpoint 消融；9 来自已知 BEST 的候选预算，带开发选择历史，不证明新 loss 最优。B17 固定 17 epoch：与历史保留训练长度有参照，但需要约 1.89 倍 B9 更新。B50 每 epoch 验证、最多 50 epoch：可延续原 patience=8/min_delta=1e−4 和原 core BEST 规则，但增加模型选择偏差；不能用新 loss 数值作为跨臂 BEST 标准。

等 epoch 与等 updates 回答不同问题。合并集合按 B9 约两倍更新；若匹配 47,052 updates，则为 4 个完整 epoch + 5,140 updates（不是 9 epoch），需要部分 epoch、检查点和公平曝光的新规则，故仅登记预算敏感性候选，不默认允许突破现有 completed-epoch checkpoint 边界。最低成本消融优先保持同一 N，不混这两种预算。

S0 候选继承 50-epoch cosine 形状，以候选 Train N 的 steps/epoch 定义一个 epoch warmup 和 50-epoch 总 horizon；B9/B17 提前固定终止，不会自然到 min LR。S1 改为 B9/B17 对应的短 horizon，会同时改变 LR 历程，须单独 scheduler 对照；禁止把 S1 暗称沿用 Phase-A。等 update 比较需固定同一 W/U 与 LR 序列，合并训练的 epoch 含义则不同。

每 epoch 全 2024 验证需 ceil(10,501/8)=1,313 forwards；B9/B17 若每 epoch 验证分别为 11,817/22,321，而只在终点报告为 1,313。新增完整模型 forward 均需批准。六帧输入 tensor 数据量约单帧 6 倍，但骨干主体相同，不能推断 GPU 小时为 6 倍；实际工时需以后获批测量。预算报告采用 updates、validation forwards、run 数及 I/O 规模，不伪造 GPU-hour 或报价。

## 6. 验证、选择与复现

V0 固定终点 checkpoint、同一历史评价 observer：有利于 loss 消融，避免以不同训练目标挑 BEST。V1 原 global core BEST/early-stop：与 Phase-A 历史接近，但已知 2024 多次使用，只能开发探索。V2 D2 中 Selection 选择、Calibration 拟合、2024 Report：角色隔离改善，但全部已知开发时期无法重新变成未经探索的确认集。V3 F1 无内置验证：固定获批预算，封存最终测试保持单独审批。

core、Brier、AUROC、AP、rain-only conditional Pinball、全部 32 coverage 沿历史口径报告。新增实验训练 loss 变化时仍报告原 core 作为共同辅助指标；主终点与容忍界限在批准前锁定，不能在看到结果后改为最有利指标。对 AUROC/AP 单类分层报告不可估计；不引入未批准的 POD/FAR/CSI 阈值。

未来每臂配对同一场景/seed、同一批次排列、精度、optimizer、clip、mask、target、LR 与终点；只改变预定单因素。日期区块与 seed 分层分别呈现；沿用 35 个七日区块可作 2024 开发探索，但不当作独立风暴。新实验仍须控制多重比较、最低有雨区块数与效应阈值；这些参数未决定。出现非有限值、顺序/支撑丢失、SHA/角色不符即停止，不自动 skip、clamp、延长预算。恢复必须另有绑定具体 LAST SHA、原授权链和代码身份的独立批准。

## 7. 不可自动选择的事项

研究者需先选择科学目的 D1/D2/F1，再选择兼容的 I/Q/N/B/S/V；批准预注册的主终点、seed、预算和边界后才可另行编写/批准 v2 runner。旧 src/yuntapr/training/phase_b_preparation.py 的 23,447/11 epoch 是 v1，不能搬作本协议。

来源：冻结 config/science_contract_v1.1.yaml、config/science_v2/phase_a_protocol_frozen_v1.json、v2 head 源码；[上轮入口检查](../../phase_a_evidence_hardening/PHASE_B_ENTRY_READINESS_CHECKLIST.md)。所有方案未执行。
