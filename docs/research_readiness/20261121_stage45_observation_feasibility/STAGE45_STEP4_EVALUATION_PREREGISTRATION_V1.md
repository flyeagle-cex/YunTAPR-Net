# 第 4 步评估预注册草案 · 多 seed 山区机制与冻结候选跨 seed 复现（2026-11-26）

- 状态：`DRAFT_PREPARATION`（未冻结、未实现、未获批、未启动；等待研究者对方向与预算上限的一次确认）
- 依据：`STAGE45_STEP4_MULTISEED_TERRAIN_PREREGISTRATION_V1.md`（Q1–Q3 定义与 D1/D2 判定规则）；`STRONG_RAIN_GATE_ENTRY_V1.md`；`STAGE2_EVALUATION_FREEZE_V1.md`；2029 山区配对评价终态（`mountain_pair_evaluation_v1`，提案 `85bc55e0…`）。
- 现有资产（V4 四模型包，提交 `5173436`，终态收据 `STAGE45_STEP4_MULTISEED_TERRAIN_RESULTS_V1.json`）：REAL/ZERO × seed2030/2031 各 4,320 更新 / 9 epoch 的 epoch-9 检查点与逐轮 `B7_development_*.json`；配对身份已冻结（seed2030 `50dcc329…`、seed2031 `65c48896…`，同 seed 两臂初始全态与 epoch 顺序逐字节相同）；执行代码 `a5503df`。
- 已有 seed2029 对照：REAL `1c9b5f8c…`、ZERO `e5689a57…`；2029 山区配对终态（高海拔 >20 强雨 n=178：log Pinball REAL−ZERO −0.001842784，物理/20 −0.000696197；q32 覆盖 6→11/178）。

## 1. 科学问题与判定规则（沿用已冻结定义，不修改）

- **Q1 地形机制跨 seed**：在 `MOUNTAIN_TERRAIN_PAIR_V1` 口径下（海拔 <1000 / 1000–2000 / ≥2000 m × 雨强分层；主群体 = 海拔 ≥2000 m 且 truth >20 mm/h；指标 = log Pinball 与物理 Pinball/20），新增 seed2030、seed2031 的 REAL−ZERO 配对差值。
  判定 D1：三个 seed（2029 已有 + 2030/2031 新增）中 **≥2 个同向**（REAL−ZERO < 0）且**三 seed 等权均值同向** → `TERRAIN_MECHANISM_REPRODUCED`；否则 `TERRAIN_MECHANISM_NOT_REPRODUCED`；单 seed 方向不一致但总体同向记为 `PARTIAL`（仅描述）。
- **Q2 冻结候选跨 seed 复现**：对每个 REAL seed，用该 seed 自身的 Dev 基线，运行冻结候选（S1：`p*q32>20 ∧ a0≥9.5373`；S2：`split_min = min_{slot 0..5}(B08−B13 面积均值) ≥ 2.3612 K`；动作：节点 0–30 向固定 q32 线性混合到 `A=20.01`，q32 与 p 不变）并计算冻结 Nine-Gate。
  判定 D2：若**全部 REAL seed**（2029 已有 PASS + 2030/2031）九门全过 → `CANDIDATE_REPRODUCED_ACROSS_SEEDS`；否则按 `PARTIAL` / `NOT_REPRODUCED` 如实记录，不得调整阈值、不得二次尝试。
- **Q3 ZERO 对照归因（描述性）**：在同一候选规则下对两个 ZERO seed 做只读描述性统计（命中数、门 1–6 数值）。若 ZERO 也出现同等候选命中与 Pinball 改善 → 记录「候选机制可能不依赖地形强迫」的归因警示；Q3 不构成任何验收或复现声明。

## 2. 工作包 A：四模型 Dev 评价 + 逐像元数组留档（E1 主体）

- 输入：V4 四模型 epoch-9 检查点（见上）与其 epoch-9 Dev 报告（`B7_development_09.json`，作为冻结指标对账参照）；固定 Dev 963 场景总体（3,303,090 监督像元、717 强雨、246,473 弱雨）；固定静态地形包（`b6_static.npz`，SHA `788572b1…`）与 `MOUNTAIN_TERRAIN_PAIR_V1` 地形总体（SHA `056ae0d9…`）。
- 任务（串行，每模型 1 次固定 E9 Dev 前向，无训练）：REAL2030 → ZERO2030 → REAL2031 → ZERO2031。每个任务：
  1. 加载对应 epoch-9 检查点（1 次 checkpoint 加载）；
  2. 固定 Dev 读取（963 场景，7,950 次科学打开 / 26,639,253,112 B）；
  3. 计算逐像元 `p`（float32）与 `qlog`（32 节点，float64），与对应 epoch-9 Dev 报告做 identity/计数/冻结指标对账（绝对/相对容差 1×10⁻¹²，不过即 STOP）；
  4. **留档逐像元数组**（`p`、`qlog`、`truth_mm_h`、监督掩膜，私有命名空间，供工作包 B 复用）：每模型约 0.88 GB，4 模型合计约 3.6 GB；
  5. 对每个 seed 计算 REAL−ZERO 配对山区指标（2 对新配对）。
- 产出：2 对新配对的 `paired_metrics`（与 2029 同一口径，含 elevation×rainfall 分层与主对比）、4 模型 identity/计数/冻结指标门收据、4 模型逐像元数组（私有）、Q1 三 seed 汇总判定。
- 预算（上限）：payload 4 × 26,747,379,518 = **106,989,518,072 B / 31,812 打开**（含每模型 7,950 次 Dev 读取、1 次检查点、1 次静态）；metadata archive **1,227,801,734 B / 918 打开**（按 2029 单配对实测值 613,900,867 B / 459 的 2 倍保守计）；合计 **108,217,319,806 B / 32,730 打开**；checkpoint 加载 4；模型推理 4 次；优化器更新 0；重试/重放 0；最长 7,200 秒（2029 单配对实测 1,239.2 秒，2 倍 + 留档余量）；存储：数组 3.6 GB + 收据 <1 GB，最小可用 8 GiB；不得访问 2025。

## 3. 工作包 B：冻结候选跨 seed 复现 + ZERO 对照（E2）

- 输入：工作包 A 留档的四模型逐像元数组（121 分片/模型，共 484 个文件 ≈ 3.5 GB 读取）、冻结候选规则与动作（同上，阈值逐字冻结）、Dev 卫星第 0–5 因果槽 `tbb_08/tbb_13`（每模型仅其候选像素所在场景，6 槽/场景）。
- 任务：
  1. 读入某模型数组，计算 S1 候选（`p*q32>20 ∧ a0≥9.5373`）；在 seed2029 Dev 上实测该阶段仅 141 行 / 20 个场景（≤120 个卫星文件 / 约 0.55 GB），其它 seed 以数组实测场景列表为准；
  2. 读取候选场景 6 个因果槽的 `tbb_08/tbb_13`，SP04 25 格面积均值 → `split_min`；S2 选择（≥2.3612 K）；
  3. 对选中行执行冻结 blend-to-top 动作（目标 `A=20.01`，q32 与 p 不变，严格保持节点有序），计算该模型自身基线下的冻结 Nine-Gate（门 1 强雨物理 Pinball 严格改善、门 2 ≥1 真强雨命中、门 3 非强雨误报 0、门 4/5 q32 计数不变、门 6 弱雨 log Pinball 不变、门 7/8/9 按构造恒等）；
  4. 对 REAL2030、REAL2031 给出 Q2 逐 seed PASS/FAIL；对 ZERO2030、ZERO2031 给出 Q3 描述性统计。
- 预算（上限，按每模型最多 130 个候选场景×6 槽保守计）：数组读取 484 次打开 / 约 3.5 GB；卫星读取 ≤ 4 × 780 文件 = 3,120 打开 / ≤14,372,033,840 B（实际由实测候选场景列表决定，预计远低）；metadata ≤ 64 MiB / ≤64 打开；合计 **≤ 18.0 GB / ≤3,700 打开**；checkpoint 加载 0；模型推理 0；最长 1,800 秒；最小可用 8 GiB；不访问 2025。
- 说明：工作包 B 的精确场景列表与精确字节数在 A 完成后由数组直接枚举，冻结提案时写入；本节给出的上限为本次申请预算上限，执行不得超出。

## 4. 预算汇总（本次申请确认的上限）

| 工作包 | 打开次数上限 | 字节上限 | 检查点加载 | 模型前向 | 最长 |
|---|---|---|---|---|---|
| A：四模型 Dev 评价 + 数组留档 | 32,730 | 108,217,319,806 B | 4 | 4 | 7,200 s |
| B：候选跨 seed 复现 + ZERO 对照 | ≤3,700 | ≤18,000,000,000 B | 0 | 0 | 1,800 s |
| **合计** | **≤36,430** | **≤126,217,319,806 B** | 4 | 4 | — |

零优化器更新、零重试、零重放；2025 最终测试期继续封存；不新增训练、不改模型、不改冻结阈值。

## 5. 失败与停止规则

- 任一任务 identity/计数/冻结指标对账失败、账本超限、磁盘 < 8 GiB、源卷 `H:` 不可用 → 立即 `STOP_NO_RETRY`，保留终态收据，不自动重试。
- 工作包 A 完成并被独立核验后，才准备并冻结工作包 B 的提案；工作包 B 不重新训练、不重读气象载荷（除上述卫星槽位）。
- 判定结果只按本文件与冻结提案的规则记录；不得在看到结果后修改阈值或追加第二次 Dev 尝试。

## 6. 证据边界

- 本评估为**描述性/复现性**：Q1 跨 seed 地形机制、Q2 冻结候选跨 seed 九门、Q3 ZERO 归因警示，均不构成对 2025 或更广总体的验证；每步结果 `scientific_status = NOT_VERIFIED`（总体层面），仅在其冻结口径内报告 PASS/PARTIAL/NOT_REPRODUCED。
- 独立事件验证（`IMERG_REFERENCE_EVENT_PROTOCOL_V1`）与 2025 一次性泛化不在本草案内，另行预注册。

## 7. 待冻结/待批准事项

1. 本方向与预算上限（A+B ≤36,430 打开 / ≤126,217,319,806 B / 4 次检查点加载 / 零训练）需研究者一次明确确认；
2. 确认后实现工作包 A 执行器与测试 → 冻结 A 提案（含代码提交、检查点 SHA、epoch-9 Dev 报告 SHA、数组留档清单、账本上限）→ 申请 A 的一次精确启动批准；
3. A 完成并留档后，枚举 B 的精确场景列表与字节数 → 冻结 B 提案 → 申请 B 的一次精确启动批准；
4. 两个包均不改变 2025 封存状态，不自动重试/重放。

## 15 固定执行包 · 多 seed Dev 评价 V1（2026-11-27）

- KIND `BOUNDED_STAGE4_MULTISEED_DEV_EVALUATION`；SCOPE `FOUR_MODEL_COSINE9_REAL_ZERO_DEV_MOUNTAIN_EVALUATION_V1`；预计终态 `COMPLETE_STAGE4_MULTISEED_DEV_EVALUATION`；decision `DESCRIPTIVE_MULTISEED_REAL_ZERO_DEV_EVALUATION`。
- 执行代码 `c612b122feaa0204a74f4adda884a7241fe8b759`；固定副本 `D:\研究\极端降水预测\YunTAPR-Stage4-Eval-Exec-c612b12`（detached c612b12）。
- 规范提案 SHA-256 `b4c722b278715d614859aa85ad6495962ce3ced314d7a009932136f60b9708b3`；提案文件 SHA-256 `c45d94ad34fd04ff1455a7e319c57c698a50bb3a77134515e83df29cb35ac10d`（公开副本同字节，100,738 B）；private seal `b4ed41cb029d7a8bcc41936407cd7076f8db6a34452a065c6f2d18166f0c3fe3`。
- 私有命名空间 `docs/research_readiness/.local/train_stage4_multiseed_dev_eval_v1`；输出根 `F:\pytorch\Research\YunTAPR_stage4_multiseed_dev_eval_20261127_v1`（尚未创建）。
- 身份链：V4 提案文件 `0648beb6…`/内部 `cd5948b6…`、V4 终态 `COMPLETE_FOUR_TASK_COSINE9_REAL_ZERO_MULTISEED`；静态地形 `788572b1…`（312,828 B）；运行解释器 `0562f573…`；四模型固定 E9 检查点：REAL_s2030 `ee7f81da…`/53,906,437 B、ZERO_s2030 `c8e0f574…`/53,906,757 B、REAL_s2031 `ce2aad58…`/53,906,885 B、ZERO_s2031 `47022bd5…`/53,906,885 B。
- 任务顺序 REAL_s2030 → ZERO_s2030 → REAL_s2031 → ZERO_s2031；每任务一次固定 E9 Dev 前向（963 场景/121 批），四路累积（冻结指标、点指标、山地海拔、tail 读数）并留档逐像元数组（121 个分片/任务，约 3.55 GB）；两对同 seed 初始全态配对（s2030 `50dcc329…`、s2031 `65c48896…`）。
- 预算：科学打开 31,812 + 元数据 918 = 32,730；源字节 106,989,518,072 + 1,227,801,734 = 108,217,319,806；检查点加载 4；模型前向 4；优化器更新 0；重试/重放 0；最长 7,200 秒；启动可用磁盘 8 GiB；数组存储上限 4 GiB。
- 准入门槛：固定副本 HEAD=c612b12、工作树干净、proposal 在 `READY_WAITING_EXACT_RESEARCHER_APPROVAL`（authorized=False、final_2025_access=False）；准入干跑（含身份、artifact、父包、预算与 artifact 哈希校验）返回 `VERTICAL_CHECKED_OK`，干跑临时批准未落命名空间。
- 测试：定向测试 29 passed / 3 subtests（base python + shim）；5 文件 py_compile 通过；`git diff --check` 通过。
- 状态：**READY_WAITING_EXACT_RESEARCHER_APPROVAL**、authorized=False、final_2025_access=False；未创建批准文件、未创建输出目录、未执行任何前向；公开副本仅供冻结。

## V1 执行尝试终态与 V2 执行包（2026-11-27）

- V1 执行：提案 `b4c722b2…`、代码 `c612b12`，2026-11-26T23:33:26Z 以 `RuntimeError: Set the selected hash seed before Python startup` 终止（`return_code` 1、`automatic_retry` false）；在包目录与授权绑定创建后、任何科学读取前失败：0 场景读取、0 前向、0 优化器更新；批准已消费，按冻结规则不重试、不自动重放；V1 输出根残件仅作审计保留。
- 根因：Dev 重算须在与训练时各 seed 相同的 `PYTHONHASHSEED` 下对账，而父进程固定 `PYTHONHASHSEED=2029`；修复 = 每任务在独立子进程中运行，环境 `PYTHONHASHSEED=<task seed>`，父进程仅做准入、任务 claim、逐任务收尾与两对汇总。
- 修复代码：提交 `c4e12bb`（`multiseed_dev_evaluation.py` 增加 `task_worker` 与 `_initialize_runtime(create=False, hash_seed=...)`；`execute` 以 `subprocess.run` 逐任务启动 worker；CLI 增加 `worker --task-index/--seconds-cap`）；定向测试 31 passed / 3 subtests；`py_compile` 通过；未改动预算与科学口径。
- V2 冻结：固定副本 `D:\研究\极端降水预测\YunTAPR-Stage4-Eval-Exec-c4e12bb`（HEAD `c4e12bb`、干净）；私有命名空间 `docs/research_readiness/.local/train_stage4_multiseed_dev_eval_v2`；输出根 `F:\pytorch\Research\YunTAPR_stage4_multiseed_dev_eval_20261127_v2`（尚不存在）；规范提案 SHA-256 `48637a348dc2a5a1f54ad5b71cc34234e11bd0db8caf1a3f7c88121ab2fc14be`、私有准备 SHA-256 `2688efbb72c9421930e6e68f10e536df1029be390722b168995a2e8f4ac004c1`；公开副本 `STAGE45_STEP4_EVALUATION_EXECUTION_PROPOSAL_V2.json`（LF 规范化，100,738 B，文件 SHA-256 `457a6713145c8a2ada9c52517019ace0a4a05e73308fbbf1f5a000c935b39a04`；私有原样文件 100,738 B，SHA-256 `457a6713145c8a2ada9c52517019ace0a4a05e73308fbbf1f5a000c935b39a04`）。
- 准入干跑：`VERTICAL_CHECKED_OK`（HEAD `c4e12bb`；四任务 REAL_s2030/ZERO_s2030/REAL_s2031/ZERO_s2031；checkpoint 身份 `ee7f81da…`/`c8e0f574…`/`ce2aad58…`/`47022bd5…`；q1 参考 sha `5a25a2dc…`；预算 31,812 payload opens / 106,989,518,072 B / 4 checkpoint loads / 4 forwards / 7,200 s 不变）。
- 状态：`READY_WAITING_EXACT_RESEARCHER_APPROVAL`、`authorized=False`、`final_2025_access=False`；尚未执行；获批后单次派发并记录四任务终态与两对 REAL−ZERO 描述指标；证据边界保持 `NOT_VERIFIED`。

## V2 执行尝试终态与 V3 执行包（2026-11-27）

- V2 执行：提案 `48637a34…`、代码 `c4e12bb`，2026-11-26T23:41:56Z 以 `RuntimeError: The frozen per-seed worker failed for REAL_s2030` 终止（`return_code` 1、`automatic_retry` false）；worker 在首批 `DevelopmentReadout.add` 处停止，父进程按失败即停写入 `STOP_NO_RETRY`；无任务输出、无 completion；已完成 dev/tail/收据元数据读取、静态包与检查点两次打开及首批数据读取，0 前向完成、0 优化器更新。批准已消费，不重试、不自动重放；V2 输出根残件仅作审计保留。
- 根因：`DevelopmentReadout` 的回调契约要求 `check(reserve_bytes)`（`conditional_intensity_readout.py:77` 在每批写分片前传入预留字节，`__init__`/分片哈希时调用 `check()`），而 `run_task` 内定义的是零参 `check()`；该不匹配只在第一批 `readout.add` 时暴露。此前 V1 的哈希种子问题已由 `c4e12bb` 修复。
- 修复代码：提交 `8d24667`（`multiseed_dev_evaluation.py` 新增模块级 `_task_check(output, deadline, reserve_bytes=None)`：校验剩余时间，并在给定预留字节时校验 `输出已用字节 + reserve ≤ 4 GiB` 上限（`MemoryError`）；`run_task` 的 `check` 改为 `check(reserve_bytes=None)` 并委托 `_task_check`）。测试新增 `test_task_check_accepts_a_reservation_and_enforces_the_output_cap` 与 `test_development_readout_uses_the_task_check_with_a_reservation`（真实 `DevelopmentReadout` + 合成 FP32/FP64 批次，验证 `check()`/`check(reserve)` 契约）；定向测试 33 passed / 3 subtests；`py_compile` 通过；未改动预算与科学口径。
- V3 冻结：固定副本 `D:\研究\极端降水预测\YunTAPR-Stage4-Eval-Exec-8d24667`（HEAD `8d24667`、干净）；私有命名空间 `docs/research_readiness/.local/train_stage4_multiseed_dev_eval_v3`；输出根 `F:\pytorch\Research\YunTAPR_stage4_multiseed_dev_eval_20261127_v3`（不存在，父目录存在）；规范提案 SHA-256 `38d2e9d5a832e663d263eca65173882fbf418141e4b4395cc4a54d012164d9d6`、私有准备 SHA-256 `08e047ef547e4d518ec4c6ac60ec571af77abd897c3f59c141bc671a30dc3b44`；公开副本 `STAGE45_STEP4_EVALUATION_EXECUTION_PROPOSAL_V3.json`（100,738 B，LF 无 CRLF，文件 SHA-256 `752AB1C967E12C48E77E22D0815CDACEC3A65A0777FDE84B9121DBB76B6271B7`，与私有原样字节一致）。
- 准入干跑：`VERTICAL_CHECKED_OK`（HEAD `8d24667`；四任务 REAL_s2030/ZERO_s2030/REAL_s2031/ZERO_s2031；checkpoint 身份 `ee7f81da…`/`c8e0f574…`/`ce2aad58…`/`47022bd5…`；父提案文件 `0648beb6…`/内部 `cd5948b6…`、静态地形 `788572b1…`、运行解释器 `0562f573…`、q1 参考 sha `5a25a2dc…`；spec 环境固定 `PYTHONHASHSEED=2029`（子进程按任务 seed 覆盖）；预算 31,812 payload opens / 106,989,518,072 B / 4 checkpoint loads / 4 forwards / 7,200 s 不变）。
- 状态：`READY_WAITING_EXACT_RESEARCHER_APPROVAL`、`authorized=False`、`final_2025_access=False`；尚未执行；获批后单次派发并记录四任务终态与两对 REAL−ZERO 描述指标；证据边界保持 `NOT_VERIFIED`。
