# 第 3 步新候选的 Train 工程检查：有界候选流形读数 V1

日期：2026-11-23
状态：设计冻结；固定执行包待 prepare 后补记（见文末）。

## 1. 目的

为 `STRONG_RAIN_GATE_ENTRY_V1.md` 的单一候选准入提供一次**不依赖 2024 Dev 选择**的 Train（2023）工程检查，使随后的一次性 Dev 九门验收具备可证伪基础。本读数只回答「动作机制 + 候选流形在真实 Train 上是否存在可冻结的选择器原料」，不构成科学验收，`scientific_status=NOT_VERIFIED`。

## 2. 已确立事实

### 2.1 九门与基线（2024 Dev，只读已保存数组）
- 总体：963 场景 / 3,303,090 监督像元 / 407,820 有雨 / 717 强雨（truth>20 mm/h）/ 246,473 弱雨（0.1<truth≤1 mm/h）。
- 门 1 `strong_physical_pinball_over20=0.5068646309277546`（严格 <）；门 2 `q32_support_tp=160`（≥）；门 3 `q32_support_fp=5769`（≤）；门 4 `point_a_tp=0`（≥1）；门 5 `point_a_fp=0`（≤0）；门 6 `weak_log_pinball=0.08872231160181858`（≤）；门 7 `brier=0.09233015567445307`（≤）；门 8 `ap=0.6066547555865263`（≥）；门 9 `auroc=0.8990243638708331`（≥）。命中一律 FP32 严格 `>20`。

### 2.2 动作机制（单像元核验）
弱雨保恒族（`a20_fixed_endpoint_bounds.py` 的 `weak_preserving_vertex` + `strict_hit`）冻结 q32（第 32 节点）与 p，对弱雨真值 0.11/0.5/1.0 的物理 log pinball 精确不变。对 Dev 强雨 r58（2024-09-30T17:30，truth=31.71，p=0.8125，q32=49.5867）：

- A0=11.5077028 → 最小跨界 A=20.0327473（FP32 严格 >20），严格有序、q32 不变；
- 归一化物理 Pinball 变化 −0.1299363393282169 → 总体门 1 变化 −0.1299363/717=−0.00018122，门 1 降至 0.5066834086971713（严格改善）；
- A_tp=1、A_fp=0 ⇒ 门 2/3 满足；q32 与 p 不变 ⇒ 门 4/5/7/8/9 恒等；唯一改动行为强雨 ⇒ 门 6 恒等。

**结论：动作机制本身足以通过九门，唯一缺口是真值无关的选择器**——它必须选中这类像元且不选中任何非强雨/弱雨。

### 2.3 Dev 选择器探索（仅作假设来源，非准入证据）
- `p*q32>20` 候选 1,912（84 强、81 弱、其余 1,747）；三类模型特征（p、q32、mean）完全重叠，无 0 弱单特征前缀；仅 `p>0.78906 且 q32/mean>3.9312` 给出 strong=1/other=12/weak=0，明显过拟合。
- 广域内部提升可改善门 1，但触及 81 个弱候选 ⇒ 门 6 失败；必须精确选择器。
- 卫星云顶特征（末槽 B13、B08−B13 split）在 Dev 143 可达像元上：5 强雨 B13_last 190.76–194.02 K（非强雨中位 204.5 K），split_last 1.61–2.57 K（非强雨 −6.61–2.56 K），AUC 0.926。窄规则 `B13≤192 ∧ split≥2.5` 在 143 像元上恰好隔离 r58（TP=1/FP=0）。这些阈值由 Dev 调出，**不得**直接作为候选；本读数的作用是提供 Train 侧独立冻结原料。

## 3. 冻结的候选形态（选择器阈值不在本读数内确定）

- 触发集合：`p*q32>20` 的候选像元中，同时满足 S1（模型支撑，阈值在 Train 候选流形上冻结）与 S2（末槽云顶：`B13≤τ13 ∧ B08−B13≥τsplit`，τ 由物理推理 + Train 冻结）的子集。
- 动作：对触发像元执行 `weak_preserving_vertex → strict_hit` 最小跨界；p 与 q32 不变；其余像元恒等。
- 机制路径：组织化深对流（极冷云顶 + 正 WV-IR split）处模型低估幅值；该族像元稀疏（Dev 1,912/3.3M=5.8e-4），非弱雨毛毛雨族。
- 可证伪预期（Train 独立检查）：冻结规则在 Train 上选中像元全部 truth>20（0 非强雨、0 弱雨），选中强雨 ≥1，且总体强雨归一化 pinball 变化 <0。
- 推翻条件：任一预期不满足，或选中数超出合理倍数 ⇒ 候选否决，不进入 Dev。

## 4. 本工程检查（有界读数）

一次固定 E9 / B7 / seed2029 / 2023 Train 前向，覆盖与 MFC700 幅值臂相同的 560 场景 / 70 批冻结子集：

- 预算：16,066,485,320 源字节 / 4,637 次打开 / 70 批 / 最长 2,400 秒；静态 312,828 B / 1 次；检查点 53,906,821 B / 1 次加载；优化器更新、refit、retry、replay 均为 0；2025 年数据不访问。
- 保留：所有严格 `p*q32>20` 候选像元的有界行（上限 20,000），字段包括场景 id、场景内监督行号 r、网格 y/x、truth、p、q32、mean、A0、动作可达性与 A_after、归一化 pinball 变化、强雨标志、all-below 标志；不保留原始逐像元数组或中间场。
- 不拟合系数、不改变预测、不写入任何选择器阈值、不做 Dev 读取（`development_scientific_reads=0`）。

## 5. 后续（另行批准，不在本包内）

1. 候选场景的有界云顶特征读取（仅末槽 B13、B08；truth-blind，按场景清单逐文件核对 sha256/字节，约 200 个文件、≤1 GB 量级），供 Train 冻结 S2。
2. 用第 4 步候选行 + 第 1 项特征在 Train 上冻结 S1/S2 与最终规则。
3. Dev 一次性九门验收（保存的 121 分片 881,894,762 B / 121 次打开 / 300 秒量级数组 + 仅候选场景云顶读取）；通过即完成第 3 步，失败则按门规则封存。

## 6. 固定执行包 · 2026-11-23

- KIND：`BOUNDED_TRAIN_STAGE45_CANDIDATE_MANIFEST`；SCOPE：`COSINE9_E9_2023_TRAIN_STAGE45_CANDIDATE_MANIFEST`。
- 执行代码：`7646b371ea81af7813c2547a3c80fb5e689d2d3b`（[GitHub commit](https://github.com/flyeagle-cex/YunTAPR-Net/commit/7646b371ea81af7813c2547a3c80fb5e689d2d3b)），固定副本 `D:\研究\极端降水预测\YunTAPR-Train-Stage45-Candidates-Exec-7646b37`（detached HEAD）。
- 冻结提案：规范 SHA-256 `d054082c3681ecb243cf078c75cb09f7d44eb5b0d1e4c972ec67349d87fe2b0f`；本目录副本 [STAGE45_CANDIDATE_MANIFEST_EXECUTION_PROPOSAL_V1.json](STAGE45_CANDIDATE_MANIFEST_EXECUTION_PROPOSAL_V1.json)，文件 SHA-256 `c060b010bceaeeb8cb401e3fb4f0a88471144c6a00b51a35a8e74bb28773819a`。
- 私有命名空间：`docs/research_readiness/.local/train_stage45_candidates_v1`（EXECUTION_SPEC / PRIVATE_PREPARATION / PROPOSAL / service；`RESEARCHER_APPROVAL.json` 尚不存在）。
- 身份继承：训练清单 `3de8b53c…`、检查点 `1c9b5f8c…`（53,906,821 B / 1 次加载）、静态地形 `788572b1…`（312,828 B / 1 次打开）、源收据 `14fb38b5…`、DOTE/调制上限/投影/额外 GFS 打开数与冻结参考一致。
- 预算：16,066,485,320 B / 4,637 次打开 / 70 批 / 最长 2,400 秒；零更新、零 refit、零 retry、零 replay；2025 封存。
- 状态：`READY_WAITING_EXACT_TRAIN_READOUT_APPROVAL`、`authorized=False`、`final_2025_access=False`；测试收据：25 passed / 5 subtests（含本臂 6 项 collector 测试与 supervisor 预算/超时测试）。
- 尚未执行：无 RESEARCHER_APPROVAL.json，未加载检查点、未阅读任何气象源、未跑前向。

## 7. V1 执行尝试终态 · 2026-11-23

- V1 提案（规范 SHA `d054082c…`，代码 `7646b37`）经研究者单次批准（decision_id `STAGE45-CANDIDATE-MANIFEST-20261123-ONE`）于北京时间 19:58 单次派发；20:06 目标进程退出码 1，落盘 `failure.json`：`STOP_NO_RETRY`、`TypeError: Object of type int64 is not JSON serializable`。
- 实际完成：前向全部 70 批、560 场景、1,920,800 监督像元、484 真强雨全部评估；候选行表已完整写出（`stage45_candidate_manifest.npz`，1,475 行 / 108 场景；可达 105 行 = 10 强雨 + 95 非强雨；已跨界 0；不可达 1,370 行 = 52 强雨 + 1,318 非强雨）。
- 失败点：终态 `completion.json` 写聚合计数时遇到 numpy `int64` 而崩溃（文件截断）。该失败属终态收据写出缺陷，不改变行表字节；但按冻结协议本次不构成有效终态。
- 处置：不自动重试、不重放；V1 行表仅保留为私有描述性残件，不用于任何正式冻结；批准已消费。修复提交 `e00edf09` 后重新冻结 V2。

## 8. 固定执行包 V2 · 2026-11-23

- 修复提交：`e00edf09e6707ad889359ef66fe20ebd45bb0f57`「Serialize the candidate-manifest aggregate receipt as plain Python」（[GitHub commit](https://github.com/flyeagle-cex/YunTAPR-Net/commit/e00edf09e6707ad889359ef66fe20ebd45bb0f57)）：聚合计数全部显式转 `int`，并新增 JSON 序列化回归测试；定向测试 26 passed / 5 subtests。
- 执行代码：`e00edf09…`；固定副本 `D:\研究\极端降水预测\YunTAPR-Train-Stage45-Candidates-Exec-e00edf09`（detached HEAD）。
- 冻结提案：规范 SHA-256 `283033ee8a951b8fd104fcb6f6b94fdd7d8b218f902faec5cda7447e9e601c61`；本目录副本 [STAGE45_CANDIDATE_MANIFEST_EXECUTION_PROPOSAL_V2.json](STAGE45_CANDIDATE_MANIFEST_EXECUTION_PROPOSAL_V2.json)，文件 SHA-256 `3cffbc1e4ea2cc28112a417b5a04e6d487abb1c8293f8a9676debb43a6b68ce8`。
- 私有命名空间：`docs/research_readiness/.local/train_stage45_candidates_v2`（无 `RESEARCHER_APPROVAL.json`）。
- 身份继承、预算与 V1 逐字段一致：训练清单 `3de8b53c…`、检查点 `1c9b5f8c…`（53,906,821 B / 1 次）、静态地形 `788572b1…`（312,828 B / 1 次）、源收据 `14fb38b5…`、DOTE/调制上限/投影/额外 GFS 打开数不变；16,066,485,320 B / 4,637 次 / 70 批 / 最长 2,400 秒；零更新、零 refit、零 retry、零 replay；2025 封存。
- 状态：`READY_WAITING_EXACT_TRAIN_READOUT_APPROVAL`、`authorized=False`、`final_2025_access=False`；尚未执行（未创建批准文件、未加载检查点、未跑前向）。
- 预期输出：与 V1 相同的 1,475 行候选行表 + 合法终态收据；结果仅作描述性工程原料，不构成 Dev 验收。

## 9. V2 执行终态 · 2026-11-23

- V2 提案（规范 SHA `283033ee…`，代码 `e00edf09`）经研究者单次批准（decision_id `STAGE45-CANDIDATE-MANIFEST-20261123-TWO`）于北京时间 20:08 单次派发；20:18:36 目标进程退出码 0，`completion.json` 有效，无 `failure.json`。
- 实际完成：前向 70 批、560 场景、1,920,800 监督像元、484 真强雨；训练源读取 4,635 文件 / 16,012,265,671 B；静态源读取 2 文件 / 54,219,649 B；优化器更新 0；2025 未访问。
- 候选行表：1,475 行 / 108 场景（`stage45_candidate_manifest.npz`）；V2 与 V1 行表字节一致（SHA-256 `8a5a4145…`），证明固定执行包确定性。行表键：scene_id / row / y / x / truth / p / q32 / nodes_log / mean_intensity / a0 / reachable / already_crossed / strong / all_nodes_below_truth / a_after / delta。
- 聚合计数（有效收据）：evaluated_scenes 560、evaluated_supervised_pixels 1,920,800、true_strong 484、candidate_scenes 108、candidate_rows 1,475、reachable_rows 105（强 10 / 非强 95）、unreachable_rows 1,370（强 52 / 非强 1,318）、already_crossed 0、improving_rows 0（旧「最大均值顶点 + 最小跨界」动作族）、numerical_failure_rows 0、all_nodes_below_truth_rows 6（全为强雨）。
- 结论：旧动作族在 Train 上 0 改善，机制上对 Pinball 敌对；V2 只提供描述性候选行表，不构成 Dev 验收。第 3 步仍 `NOT_VERIFIED`。

## 10. 动作族修订（私有探索，基于 V2 行表）· 2026-11-23

- 仅用已保存行（无新源读取）评估三种「末节点固定、仅调节点 0–30」动作族：
  - `uniform`：对节点 0–30 统一加 δ = (target_mean − mean) × 32/31，使 A = float32(p·mean) 恰好 > 20.01；
  - `constant`：节点 0–30 填同一常数 m；
  - `scale`：全节点乘同一系数（末节点随之改变，仅作对照）。
- Train 行表（1,475 行，62 强雨）：`uniform` 1,475 行全部可达、62/62 强雨改善（归一化物理 Pinball 变化 −0.0583 ~ −0.4399），非强雨仅 65/1,413 改善；`constant` 1,470 可达、60/61 强雨改善（−0.3662 ~ +0.0198），非强雨 21 改善；`scale` 0 可达。
- Dev 候选（1,912 行，84 强雨；仅用保存数组复核性质）：`uniform` 1,912 全部可达、84/84 强雨改善（−0.0774 ~ −0.4240），非强雨 49 改善；`constant` 1,909 可达、84/84 改善（−0.4001 ~ −0.0267），非强雨 14 改善；`scale` 2 可达、0 强。
- 修订决定：候选动作改为 `uniform` 最小均匀上抬（q32 与 p 不变），并把「精确选择器」作为唯一剩余条件——若选择集 ⊆ 真强雨且非空，则门 1（严格改善）、门 2（≥1 命中）、门 3（0 误报）由构造满足，门 4–9 因 p/q32/弱雨不变而恒等。下一步在 Train 冻结 S2 云顶选择器（末槽 B13、B08−B13 split），再对 Dev 做一次性验收；本修订不改变已冻结的 V2 提案与行表，仅为后续候选协议设计依据。
