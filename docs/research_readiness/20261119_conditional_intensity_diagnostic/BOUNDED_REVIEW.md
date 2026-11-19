# 条件雨强诊断方案：限定科学/工程审核

**状态：`REVIEW_COMPLETE_NOT_APPROVED`。本文件是审核记录，不是批准，不构成计算授权。**
**范围：只读代码与既有收据；未运行训练、推理、反传；未复算任何指标。**
**被审对象：本目录 `DIAGNOSTIC_PROTOCOL.md` + `DIAGNOSTIC_PLAN.json`（2026-11-19 22:22）。**
**科学状态维持 `NOT_VERIFIED`；2025 封存不变。**

## 总判断

分箱可加性、有限节点界限方法、禁止插值/外推/未冻结 cutoff 的三条禁令，与已冻结合同一致，方案方向可用。
但当前文本**不能冻结**：B 有一处指标定义自相矛盾（识别率/未决率），A 有一处会系统性误导的度量设计（箱范数/余弦），且两处身份绑定与一处预算缺口未解决。

## A. 梯度剖面：关键修正

**A1（阻塞，零计算可解）身份绑定不完整。** 实际执行臂已可逐字确定：
`cosine9_training.py:158,222` 绑定 `loss="E0"`、`lambda_q=1.0`；
`phase_b_v2_ablations/total.py:27` 为 `(S_occ + λ·S_qr)/N_valid`（λ 恰好一次）；
`pinball.py:26-27` 为 32 个 τ 先取均值、再对雨像元求和。
故 `g_bin = (1/N_valid)·∇S_qr,b`。计划必须从 E9 收据绑定这三条，并明确
“S_qr 是 τ 均值而非 τ 求和”——两者相差 32 倍，是本题最容易出的量纲错误。

**A2（修正）N_valid 不是恒定 6860。** `stage4/__init__.py:4-6`：`TRAIN_N=959, BATCH=2, STEPS=480`，
每轮末批只有 1 个场景；`engine.py:81` 的门为 `loss.n_valid == len(ids)*3430`。
即 479 批为 6860、末批为 3430。汇总规则必须写成“按 update 平均的每批梯度”
（与 SGD 目标一致），并说明末批权重为其数据占比的约 2 倍；不得默认统一除以 6860 后相加。

**A3（防误读，最重要）箱梯度范数混淆“采样占比”与“残差幅度”。**
pinball 对每个节点的梯度是 ±τ 或 ±(1−τ)，故 `‖g_b‖` 随箱内像元数 n_b 与其残差幅度增长。
因此箱间范数比较基本在复述已知的数据频率分配（本目标没有按箱加权），
不能支持“强雨被梯度饥饿”的结论。必须并列报告逐雨像元敏感度 `∇S_qr,b/n_b`，
并声明“分配”与“残差大小”在范数里不可分。

**A4（防误读）余弦含自项。** `g_full = Σ_b g_b` 包含 `g_b` 本身，
`cos(g_b, g_full)` 有 `‖g_b‖²` 的自项，正交箱也会得到非零正值，不能证明方向对齐。
应改报箱间两两余弦，或 `cos(g_b, g_full − g_b)`；跨参数组的范数不可直接比较
（backbone 参数量远大于 head），应报每参数 RMS 或相对完整梯度的比例。

**A5（防误读）E9 是近驻点。** COSINE9 收尾学习率趋零，E9 处梯度本身最小；
“某箱梯度小”不能解释为该箱在整个训练中被忽视，也不能归因强雨退化。
计划已写“不代表历史”，需再加一句“E9 处信噪比低是该方法的结构性弱点”。

**A6（阻塞，预算）计算量未估，且远高于一次前向。** 每批需要约 7 次反传才能得到 7 个箱梯度
（若同时按箱拆 occurrence 则约 14 次）；全 2023 Train 一轮为 480 批、约 53 GB
（按既有 477,571,953,840 B / 4320 更新 ≈ 110.5 MB/更新 量级）。
这必须进入提案预算，不能按“一次训练轮”估算。

**A7（可行性）最稀有箱大概率不可估。** 以 2024 Dev 密度外推
（717 强雨像元 / 3,303,090 有效像元 ≈ 0.022%），2023 Train 单轮约 3,289,370 有效像元
只对应约 700 个 >20 mm/h 像元，其中 >50 可能接近 0（山区 ≥2000 m 已无 >50 样本）。
必须预登记每箱最小 n_b，低于阈值一律标 `NOT_ESTIMABLE`，不得用 0 梯度表示“无贡献”。
若只跑 48–96 批，>20 各箱样本量不足以支撑稳定梯度估计；不建议。

**A8（工程门）** 必须与训练同 dtype/autocast 策略重算（S_qr 在 autocast 关闭下算 FP64）；
断言参数与 buffer 的 SHA 前后不变、optimizer step 为 0、无 `.grad` 残留；
当前块结构为 GroupNorm、无 dropout/BN（`models/blocks.py`），模式风险低，但执行的固定副本须核实而非假设；
“分箱向量和复原完整梯度”的合成检查须给浮点容差（各次 backward 的加法顺序不同）。

## B. 读出诊断：关键修正

**B1（阻塞，内部矛盾）识别率/未决率当前不可定义。**
32 个有限节点下，p>0 时 `P(R>20)` 的点识别在数学上不可能：
20 落在相邻节点之间时包络宽度恰为 `p/32`（落在 q0 以下或 q32 以上为 `p/64`）。
故“识别率”结构性恒为 0；而“未决率”必须依赖 cutoff
（`extreme_diagnostic_candidates.py:99-109` 的 `decision_identification` 需要 `probability_cutoff`），
计划又明令“不设未冻结 cutoff”。二者只能删。
建议替代指标：逐像元包络宽度分布；全人口包络 `[mean lo, mean hi]` 及宽度；
以及“32 个节点中位于 20 以上的节点数”分布（0…32，与 V7 节点诊断同口径）。
另建议同时报条件形式 `1−F₊(20)` 的宽度（恒为 1/32），把发生项与尾部形状分开。

**B2（数据前提）全人口数组确实不存在。** 现有收据只有 21 格（海拔×雨强）聚合与
717 个真值强雨像元记录（`NEXT_STEP.json`：798,882 B/4 次；`CONDITIONAL_INTENSITY_EVIDENCE.json`
只有聚合与节点计数）。故 B 的“先查有无”必须以否证归档（路径、SHA、字节），
不可假设私有数组存在；B 实质仍需一次 2024 Dev 前向。

**B3（工程阻塞）bf16 存储会破坏输入合同。** `exceedance_bounds` 要求
`p∈[0,1]`、`q` 为 `[N,32]` 严格递增且 `q[:,0] > log1p(0.1)`，且无任何排序/修复
（`extreme_diagnostic_candidates.py:39-63`）。bf16 在 log1p≈1.5–4 处的间距约 0.008–0.016，
足以让相邻节点并列而触发 raise（历史已出现过 bf16 概率转 NumPy 的失败）。
必须规定 qlog 以 FP32 以上落盘，并加“输入可接受性预检；不通过即停，禁止排序/裁剪修复”。
同时保持与训练一致的 FP32 阈值 0.1（`validation.py:87`），否则边界像元会换箱。

**B4（防误读）界限语义还要加两条。** 除“不是置信区间”外：
(i) 全人口 `[mean lo, mean hi]` 只是同口径保守包络（模块自注
`CONSERVATIVE_CLOSED_NOT_ENDPOINT_ATTAINABILITY`，端点不可联合达到）；
(ii) 包络描述“与冻结 p、q 相容的分布集合”，与真值比较只检验模型隐含分布的自洽性——
真值落在包络内**不是**校准证据，落在包络外才是有信息的事件。

**B5（防误读）>50 基本空泛。** 当 q32≤50 时界限为 `[0, p/64]`。
报告时须标“不可识别/空泛”，不能作为尾部分布证据，更不能用于候选筛选。

**B6（省数据）落盘即为资产。** B 的真正增量是 `P(R>20)` 包络与 32 节点覆盖；
“雨强箱 Pinball”与既有 21 格部分重复。建议 B 单臂一次前向即把 `p/qlog/truth/mask`
全部落盘（约 3.3M×32×4 B ≈ 0.42 GB/臂），此后读出类诊断零新推理。

## 2. 是否拆为两项授权

**是，拆。** 理由：数据域不同（2023 Train vs 2024 Dev）、操作不同（反传 vs 纯前向）、
身份绑定不同（A 还需 λ/E9/batch 顺序/训练数据预算，B 只需 E9 与 Dev 数组）、
失败语义不同（混包时任一身份不匹配会使整包失败，与“失败即停、不自动重放”边界冲突）。
顺序上 B→A：B 更便宜，且其结论直接决定 A 的解释上限（若包络已宽到无法区分，
A 的“梯度分配”价值更低）。不建议打包，也不建议 A 先行。

## 3. 更省数据的顺序

0. **零计算**：归档“无全人口数组”的否证；从收据逐字绑定 λ_q=1.0、N_valid=6860/3430、
   E9 checkpoint SHA、`epoch_order(seed=2029, epoch=9)` 的 480 批身份。今天即可完成。
1. **B**：单臂 REAL/COSINE9 2024 Dev 一次前向（963 场景、121 批、约 27 GB 量级，
   按既有 pair 评价收据），强制落盘数组 → 产出包络 + 节点覆盖 + 箱 Pinball。
2. **A**：仅在 B 完成后申请；先用冻结 2023 Train 标签统计各箱像元数，
   按最稀有需要箱反推批数（预计接近 1 轮 ≈ 53 GB，而非 10% 子集），
   预登记最小 n_b；`>50` 预计 `NOT_ESTIMABLE`，须事先声明。

（以上字节为按既有收据的量级估算，不是本次预算，提案前须按实际收据重算。）

## 4. 结论上限

- **A**：仅 E9 单点、单 seed、单臂（REAL，无 ZERO_DOTE 配对）、2023 Train 局部分布；
  不能归因历史训练、不能证明梯度冲突导致强雨退化、不能外推到其他 seed/轮次/2025；
  箱范数受 n_b 与残差幅度混淆，最强只能给“E9 处局部目标的强度分配与逐像元敏感度描述”。
- **B**：只给“与冻结 p、32 节点相容的 `P(R>20)` 包络”及宽度，分辨率 ≥ `p/32` 量级；
  >50 空泛；不是 CI、不是风险保证、不能给校准/排序结论、不能设 cutoff 做决策；
  真值落在包络内 ≠ 校准通过；单 E9/单 seed/2024 Dev 描述性。
- **合并**：最多回答“读出端是否足以支撑 >20 的判定”与“训练目标在 E9 处的强度分配形状”，
  仍为 `NOT_VERIFIED`，不能据此宣称任何训练改进有效或给出因果机制。

## 2026-11-19 有界复核结果与修订处置

Harness 对 `DIAGNOSTIC_PROTOCOL.md`、`DIAGNOSTIC_PLAN.json`、`B_READOUT_PROPOSAL.json`、`B_DATA_AVAILABILITY.md` 做了第二次只读短复核，结论为 `REVIEW_COMPLETE_NOT_APPROVED`：首轮公式/批次/度量与 FP32 输入问题已修复；科学范围、字节合计和人口数量算术无明显矛盾。复核提出的三项送批前要求及当前处置如下：

1. **新增执行器身份和数组导出路径**：有效阻塞。`e8d2a9b` 是双臂聚合评价代码，不写全人口 `p/qlog/truth/mask`；提案已将旧 commit 标为来源参考，明确新 exporter/entry 尚未实现，且将其设为 fail-closed gate。不得据旧 SHA 请求推理批准。
2. **真值来源与 source opens**：已基于 Stage4 `ReaderFactory` 与读账合同澄清。IMERG `imerg_YYYYMMDD.nc` 目标输入属于 7,950 个去重 Development source files，不另外产生 963 次标签打开；另计 static 1 次与 checkpoint hash/load 两次，payload opens 参考为 7,953。修订后仍须让新执行器 source ledger 按此定义逐项绑定。
3. **计划中的陈旧预算状态**：已将 `NOT_ESTIMATED` 改为提案中的精确 byte/open caps，并注明执行器绑定前须复核限额。

后续网页总控指出旧 `dev_source_manifest_sha256=65e8…` 无收据依据。该字段已删除，并改用已保存评价报告与冻结证据中的 population、populations 文件、statistics、target QC、Dev scene-order 与 partition 身份。另补充整体 envelope 是保守闭包（端点不联合可达）及 `1-F₊(20)` 有限节点宽度 `1/32` 的解释。

本复核没有批准任何训练或推理。当前唯一实质工程阻塞仍是新增且可复核的单臂数组导出入口及其固定代码 SHA；科学状态保持 `NOT_VERIFIED`，2025 Final Test 继续封存。

## 附：本次核验的代码基线

`src/yuntapr/experimental/research_readiness/cosine9_training.py:158,222`；
`src/yuntapr/experimental/phase_b_v2_ablations/total.py:27,62`、`pinball.py:26-27`、`validation.py:79-88`；
`src/yuntapr/experimental/core_innovation/stage4/__init__.py:4-6`、`engine.py:81,85-88,238,251`；
`tools/research_readiness/extreme_diagnostic_candidates.py:39-63,99-109`；
`src/yuntapr/experimental/research_readiness/tail_identifiability.py:76-88`；
证据收据 `docs/research_readiness/20261115_mountain_pair_results/CONDITIONAL_INTENSITY_EVIDENCE.json`、
`docs/research_readiness/20261115_v7_followup/NEXT_STEP.json`。
