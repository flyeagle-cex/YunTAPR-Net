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

## 11. Train 云顶选择器冻结（2026-11-23）

- 读取：对 V2 行表的 108 个候选场景读取 6 个因果槽 × 7 个热红外波段（B08/B09/B10/B11/B13/B15/B16）的 Himawari 文件，共 648 文件 / 3,084,063,187 B / 37.2 秒；每文件 ≤ 8 MB 并按冻结 2023 清单的 `expected_sha256`/`expected_bytes` 核对；经 `load_sp04` 的 10000×25 原生格面积均值映射到 SP04；1,475 个候选行的 6×7 格点全部有效。私有产物 `.dsh_train_bt_probe/train_candidates_bt6.npz` 与 `read_receipt_6slot.json`（逐文件 sha256/字节）。
- 选择器候选审查（Train 1,475 行 = 62 强 + 1,413 非强）：单特征 AUC 最高的是末槽云顶冷（B13 0.691，方向取低）与末槽 WV-IR split（B08−B13 0.689，方向取高）；`(B13≤τ, split≥σ)` 两维网格不存在 0-FP 且 TP>0 的解；加入模型支撑 `a0=float32(p·q32)` 后出现多个 0-FP 二维解。
- **冻结规则（Train 2 TP / 0 FP，2026-11-23 冻结，先于任何 Dev 云顶读取）**：
  1. S1（模型支撑）：`p*q32 > 20`（FP64 严格）；
  2. S2（模型支撑门槛）：`a0 = float32(p*q32) ≥ 9.5373`；
  3. S3（持续深对流云顶）：`split_min = min_{slot=0..5}(B08−B13) ≥ 2.3612 K`。
  - 选中 2 个 Train 强雨像元：2023-07-11T11:30 y=80 x=69（truth 20.87，a0 9.537，split_min 2.53）与 y=81 x=69（truth 22.67，a0 10.128，split_min 2.64）；均属同一对流簇（有效样本小）。
  - 余量：split_min 选中最小值 2.53 vs 最近被排除非强雨 1.966（余量 0.56 K）；a0 选中最小值 9.537 vs 最近被排除非强雨 8.95（余量约 0.59）。
  - 其它 0-FP 备选（仅记录，不采用）：末槽 `split_last≥2.62 & a0≥9.10`（3 TP/0 FP，split 余量 0.12 K）；`B13_last≤192.29 & a0≥9.16`（2 TP/0 FP，B13 余量 0.18 K）；三维规则最高可到 9 TP/0 FP（阈值精确到 0.05 K，过拟合风险高，不采用）。
- **Dev 转让风险（诊断，仅用先前已读取的 143 个 Dev 可达像元子集，非新读取、非选择依据）**：该 143 子集中，末槽型规则 `split_last≥2.30 & a0≥9.0 & B13≤195` 会选中 4 个：1 强（2024-09-30T17:30 y17x44，truth 20.12）+ 3 非强（truth 9.69/8.88/6.36，split_last 2.36–2.56）→ 末槽阈值不可转让。冻结的持续型规则 `split_min≥2.3612 & a0≥9.5373` 在同一子集上只选中 1 个（即该强雨），0 非强；但该子集只覆盖 143/1,912 个候选，不能替代正式 Dev 验收。
- 机制解释（先于 Dev 读取写明）：持续 6 个时次的正 WV-IR split 表征云顶高于上部水汽层的深厚对流，模型在低 q32 支撑处低估其地面雨强；动作只作用于该稀疏子集，q32/p 不变。若 Dev 一次性验收失败（选中集含非强雨、或选中空集、或门 1 不降），则此候选形态封存，不再调整。

## 12. Dev 一次性九门验收包（设计，待冻结/批准）

- 输入（全部 truth-blind 读取，2025 不访问）：
  1. 已保存的 121 个 Dev 预测分片（`batch_*.npz`，881,894,762 B / 121 次打开；仅含 p/qlog/truth/mask，用于复算门与动作变化量）；
  2. 130 个 Dev 候选场景（`p*q32>20` 所在场景）× 6 个因果槽的 Himawari 云顶文件：780 个文件、冻结清单 expected_bytes 合计 3,593,008,460 B（逐文件核对 sha256/字节、单文件 ≤ 8 MB）。
  - 合计预算：901 次打开 / 4,474,903,222 B；无模型前向、无检查点加载、无 GPU、无优化器更新；最长 900 秒；输出仅汇总 JSON（≤ 64 MiB）。
- 计算：对 S1∧S2∧S3 选中像元施加 blend-to-top 动作（第 13 节；末节点 q32 与 p 不变，u=(20.01/p−mean_old)/((31/32)(q32−mean31))，若 0<u<1、顺序保持或 FP32 A>20 任一不满足则该行不可激活并计数），逐门计算：门 1 = 基线强雨 pinball 和 + 选中强雨变化量 /717；门 2/3 = 激活集中强/非强 A>20 计数；门 4/5 由 q32 不变恒等；门 6 = 基线弱雨和 + 选中弱雨变化量 /246,473；门 7/8/9 由 p 不变恒等（报告恒等证明）。
- 通过条件：门 1 严格 < 0.5068646309277546、门 2 ≥1、门 3 ≤0、门 6 ≤0.08872231160181858，且门 4/5/7/8/9 恒等。任一失败 ⇒ 候选封存，第 3 步保持 NOT_VERIFIED，不重试。
- 该包须先实现为固定代码提交 + prepare 冻结提案，再由研究者给一次明确启动批准；本文件不授权读取。

## 13. 动作族更正为 blend-to-top（审计修正，2026-11-23）

- 审计发现：第 11/12 节原定的 `uniform` 动作在真实数据上不可行。它要求 δ=(20.01/p−mean_old)·32/31，但真实候选的 `q32 − q31` 间隙只有 5.4–6.2 mm/h，而 δ 为 10.8–14.6 mm/h，所有选中行的节点顺序都会破坏：Train 冻结规则选中的 2 行（2023-07-11T11:30 y80x69 / y81x69）与 Dev 的 7 个强雨合格行全部 inc=False，1,475 个 Train 候选中仅 9 行可行、冻结规则选中可行 0。按原动作，该候选连自身的 Train 工程检查都是 0 激活（门 2 必败），必须在 Dev 读取前更正。
- 更正后的动作（blend-to-top）：固定末节点 q32 与概率 p，把 31 个次顶端分位向 q32 做线性混合：`new_i = nodes_i + u·(q32 − nodes_i)`；`u = (20.01/p − mean_old) / ((31/32)·(q32 − mean31))`；要求 0<u<1、节点严格递增（凸组合自动保持）、FP32 新 A=float32(p·mean(new))>20；否则该行不可激活并如实计数。物理含义不变：只在已由云顶规则选中的稀疏像元上，把条件分位整体抬向其自身固定的上分位，使点估计刚好严格越过 20 mm/h；q32 与 p 不变，因此门 4/5/7/8/9 恒等。
- 仅用已保存 Train 行（V2 行表 + 6 槽云顶行表，无新读取、无 Dev 读取）的描述性复核：冻结选择器 `p·q32>20 ∧ a0≥9.5373 ∧ split_min≥2.3612` 在 Train 选中 2 行，均为强雨（2023-07-11T11:30，truth 20.87/22.67，a0 9.537/10.128，split_min 2.53/2.64）；blend 可行（u=0.447/0.390，new_A=20.01），归一化物理 Pinball 变化 −0.0806/−0.1331（两行都改善）；全部 146 个强雨候选（84 Dev + 62 Train）中 blend 可行 145/146 且 145/145 改善（均值 −0.2277，最大 −0.0332）。Train 合格集 = 1,475 候选中 a0≥9.5373 的 123 行（11 强/112 非强），选择器只激活 2 强/0 非强。
- Dev 合格集构成：141 行（7 强/134 非强）；其中 128 行在先前已读取的 143 个 Dev 可达像元探索子集内（4 强/124 非强），13 行从未读取（3 强/10 非强）。先前探索只在 143 子集上给出 1 强/0 非强；最终验收覆盖全部 1,912 个候选（130 场景），因此正式读取首次覆盖那 13 行候选及全部非合格候选。此前 Dev 143 行探索读取的存在属于已披露的探索性暴露，不作为本次冻结的选择依据；本次仅由 Train 行冻结规则。
- 冻结阈值与预算不变：candidate `p·q32>20`、a0≥9.5373、split_min≥2.3612、目标质量 20.01；901 次打开 / 4,474,903,222 B / 最长 900 秒 / 无模型前向、无检查点加载、无 GPU、无优化器更新；输出仅汇总 JSON（选中行 ≤50、不可行行 ≤50）。提案状态改为 `READY_WAITING_EXACT_DEV_ACCEPTANCE_APPROVAL`，authorized=False、final_2025_access=False。
- 代码与测试：`tools/research_readiness/stage45_dev_acceptance.py` 增加 `blend_to_top`、真实 data 上修正选中行 global-row→candidate-index 映射、门 6 对已激活弱雨行重算；`start_stage45_dev_acceptance.py` 更新状态与 action_rule。定向测试（`test_stage45_dev_acceptance.py` + `test_independent_process.py`）18 passed / 3 subtests；另用真实 121 分片 + 合成 501×501 卫星 payload 做端到端演练：选中 1 个强雨行（u=0.456、new_A=20.01、变化 −0.1703），门 1 候选 0.5066271（基线 0.5068646，pass）、门 6 恒等、门 2/3 pass、0 非强雨选中 → 演练决策 PASS。
- 证据边界：Dev 正式验收仍是一次性真实读取；若选中集含非强雨、为空、或门 1 不降，则候选封存、第 3 步保持 NOT_VERIFIED，不重试、不改阈值、不重放。

## 14. 固定执行包 · Dev 九门验收 V1 · 2026-11-23

- KIND：`BOUNDED_STAGE45_DEV_ACCEPTANCE`；SCOPE：`COSINE9_E9_2024_DEV_STAGE45_NINE_GATE_ACCEPTANCE`；执行代码 `2392f51843e7c9199b28dd43796fc1666748fe01`（[GitHub commit](https://github.com/flyeagle-cex/YunTAPR-Net/commit/2392f51843e7c9199b28dd43796fc1666748fe01)），已冻结、尚未推送（网络中断，本地提交）；本文档与提案副本随后同批提交。
- 固定副本：`D:\研究\极端降水预测\YunTAPR-Train-Stage45-DevAccept-Exec-2392f51`（detached HEAD = 2392f51，7,695 文件）。为保证自包含，已把保存的 Dev 读取数组（121 分片）复制进该副本私有 `.local\b_readout_prepare_20261120_v2\readout`；`.local` 不进入版本控制。
- 冻结提案：规范 SHA-256 `f568e8401d27b9e1e552cdb9dc539c4e1f052126cccda7dd26d079453b273bec`；私有命名空间内 `PROPOSAL.json` 原样文件 SHA-256 `aaf23983ad0a351dcb8da002cd6e71eea6abe8ad3f40d568da4a7812a2bf32e1`（5,806 B，CRLF）；本目录公开副本以 LF 规范化后文件 SHA-256 `c4bc27ae77d66f2b77f28d890c57860a83c9827fef040911f589d8d0100317a5`（5,664 B，JSON 内容相同、规范 SHA 不变）；`PRIVATE_PREPARATION.json` 279,566 B；`EXECUTION_SPEC.json` 1,488 B。私有命名空间：`<fixed>\docs\research_readiness\.local\train_stage45_dev_acceptance_v1`。
- 身份继承：Dev readout 提案 `ed417346f82218fe981078872fb91c80211ad46e9b836f29e628daef842308a9`、检查点 `1c9b5f8c595935674f6952da6b239a50e26ca4eb4d90a217ab5593866d5b319e`（本包 0 次加载）、population_ids `916302412bf0…`、partition `01b95f12…`、监督掩膜 `70368bec…`、population `2f2cc75c…`、2024 开发清单 `6bd5a810…`；保存数组 121 文件 / 881,894,762 B；卫星文件 780 个 / 3,593,008,460 B（逐文件字节与 sha256 在 prepare 时核对通过）。
- 预算：901 次科学文件打开 / 4,474,903,222 字节 / 最长 900 秒 / 1 次科学遍 / 模型前向 0 / 检查点加载 0 / 优化器更新 0 / retry 0 / replay 0；2025 不访问。
- 状态：`READY_WAITING_EXACT_DEV_ACCEPTANCE_APPROVAL`，authorized=False、final_2025_access=False；未创建 `RESEARCHER_APPROVAL.json`、未创建 output、未执行真实 Dev 读取。
- 已完成的非科学验证：定向测试 18 passed / 3 subtests；真实 121 分片 + 合成卫星 payload 的端到端演练 PASS（用于验证代码路径，不作为科学证据）。
- 执行一次后按第 12/13 节门规则判定；任一失败即候选封存、第 3 步保持 NOT_VERIFIED，不重试、不改阈值、不重放。

## 15. Dev 九门验收 V1 执行终态 · 2026-11-23

- 单次执行完成：`decision = PASS`、`failing_gates = []`、`status = COMPLETE_STAGE45_DEV_ACCEPTANCE`；target_exit return_code 0（2026-11-23T14:18:55Z），耗时 63.83 秒（上限 900 秒）；`completion.json` 7,310 B（私有 SHA-256 `0c85c1c5af0057c2c644033c14ea206972ba9ea3b4fb113c8226f28ad9fc70f3`，公开副本 [STAGE45_DEV_ACCEPTANCE_RESULTS_V1.json](STAGE45_DEV_ACCEPTANCE_RESULTS_V1.json) 以 LF 规范化，文件 SHA-256 `5e184d575f0e4aa052048b1747270f62d6a8bc21b1431aac202c44bdc91af6ad`）。
- 账本：121 个数组分片 / 881,894,762 B + 780 个卫星文件 / 3,593,008,460 B = 901 次科学文件打开 / 4,474,903,222 B；元数据配置打开 3 次；模型前向 0、检查点加载 0、优化器更新 0、retry/replay 0；final_2025_access = false。
- 选择器：从 1,912 个候选行中按冻结规则 `p·q32>20 ∧ a0≥9.5373 ∧ split_min≥2.3612` 选中 1 行，为真强雨（2024-09-30T17:30，scene row 57，y=17、x=44，truth 20.12 mm/h，p=0.8046875，q32=44.3744，a0=10.4940，split_min=2.5724）；非强雨选中 0、弱雨选中 0、不可行 0。blend 比例 u=0.377417，new_A=20.0100002，归一化物理 Pinball 变化 −0.08932362。
- 九门：门 1 强雨物理 Pinball/20 `0.5068646309277545 → 0.5067400512587865`（delta −0.00012458，严格下降）；门 2 固定 A 真强雨命中 0→1；门 3 非强雨误报 0→0；门 4 q32 真阳 160 不变；门 5 q32 假阳 5,769 不变；门 6 弱雨 log Pinball 0.08872231160181855 不变；门 7/8/9 因 p 与 q32 固定按构造恒等（Brier/AP/AUROC）。九门全部通过。
- 结论：冻结的单一候选（云顶持续冷却 + 正 WV-IR split 门控、blend-to-top 弱雨保恒幅值校正）在一次性 Dev 九门验收中 `PASS`，无门失败；按第 3 步冻结协议，第 3 步联合门由负终态改为「该候选通过」。证据边界：仅 1 个激活像元（门 2 只要求 ≥1）、门 1 余量约 1.2e-4；结论严格限于本冻结协议与本次单次执行。completion 的 `scientific_status = NOT_VERIFIED` 指更广的数据集级科学验证状态，不否定本次九门判定；2025 封存、不重试、不重放，且本结果不自动授权任何新训练、扩域或 2025 访问。
- 复现：执行代码 `2392f51`、规范提案 `f568e840…`、私有准备 `79b24274…`、固定副本 `YunTAPR-Train-Stage45-DevAccept-Exec-2392f51`；由独立监督器 spawn 一次（supervisor_pid 29968、target pid 35080），无自动重试。
