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

## V3 执行终态（A 包，2026-11-27）

- 执行身份：规范提案 `38d2e9d5a832e663d263eca65173882fbf418141e4b4395cc4a54d012164d9d6`、执行代码 `8d246672de94d3574f2fd6fece308161676e984d`、固定副本 `YunTAPR-Stage4-Eval-Exec-8d24667`、批准 decision `DESCRIPTIVE_MULTISEED_REAL_ZERO_DEV_EVALUATION`（已消费）。
- 终态：`target_exit` 2026-11-27T00:51:32.999655+00:00、`return_code` 0、`automatic_retry` false；`completion.json` status `COMPLETE_STAGE4_MULTISEED_DEV_EVALUATION`、`elapsed_seconds` 2,819.406；无 failure 收据。`completion.json` SHA-256 `87fe93d4b443d0aef92b1970b8bed5e99bce9c8ac7ef4d4f5269bd480a34b7d4`。
- 四任务全部 COMPLETE 且 gate PASS（6 组 identity/counts/frozen_metrics，绝对/相对容差 1e-12）；saved elevation gate 全部 true；总体 963 场景 / 3,303,090 监督像元 / 407,820 有雨 / 717 强雨（每任务相同）。
- 任务账本：每任务 121 批前向、1 次前向、0 更新；逐像元数组 121 分片 / 881,894,762 B/任务；四任务合计 484 分片 / 3,527,579,048 B。`totals`：科学打开 31,812 + 元数据 918 = 32,730；源字节 107,603,418,554；检查点加载 4；模型前向 4；优化器更新 0。
- 检查点（epoch-9）：REAL_s2030 `ee7f81da…`/53,906,437 B、ZERO_s2030 `c8e0f574…`/53,906,757 B、REAL_s2031 `ce2aad58…`/53,906,885 B、ZERO_s2031 `47022bd5…`/53,906,885 B。
- 公开脱敏收据：`STAGE45_STEP4_EVALUATION_RESULTS_V1.json`（33526 B，SHA-256 `2318032d94882dac9df50cf4ce47b8b0e687ad041759f2f86660f4fb3a567ebc`）；含四任务身份/门表/账本、两对 `paired_metrics`（含 primary contrast 与海拔×雨强 cells）、Q1 汇总与证据边界。

## A 包结果与 Q1 判定（2026-11-27）

- 两对新 seed REAL−ZERO 山地强雨配对（primary population：海拔 ≥2000 m 且 FP32 truth >20；n_strong 各 178）primary contrast 均为 `DIRECTIONAL_LOCAL_DEGRADATION`；paired population SHA-256 `056ae0d9…`（与 2029 一致）；paired_metrics 文件 SHA-256：seed2030 `38da3900a3aa6479d6c314d4e597ebad0e85a1da615803417b21194f7489a207`、seed2031 `5b2099448ea30c2a396f4a93a879203b9eda6b546b5165ac80d379a00a87c434`。
- Q1 判定：**`TERRAIN_MECHANISM_NOT_REPRODUCED`**。log Pinball REAL−ZERO：2029 −0.0018427840817258874、2030 +0.0036674256791323595、2031 +0.0015519734424627673（同号数 1，三 seed 均值 +0.0011255383466230798，均值符号不同）；物理 Pinball/20：2029 −0.0006961972905197065、2030 +0.0010402713413337286、2031 +0.00012613554743084573（同号数 1，均值 +0.0001567365327482893）。按预注册规则（≥2/3 同号且均值同号）不成立，记录为 `NOT_REPRODUCED`，不调整阈值、不二次尝试。
- 解释边界：2029 的局部改善未能跨 seed 复现；两个新 seed 的 Dev 山区配对方向为局部退化。`scientific_status=NOT_VERIFIED`；本结果只用于 Q1 判定与 B 包设计，不构成 2025 访问、训练或最终科学验收。
- 下一步：按预注册 Q2/Q3 准备并冻结工作包 B（冻结候选跨 3 个 REAL seed 九门复现 + ZERO 描述性对照；预算上限 ≤18,000,000,000 B / ≤3,700 打开），另行请求一次明确批准。

## 16 固定执行包 · 候选跨 seed 复现 V1（2026-11-27）

- KIND `BOUNDED_STAGE4_MULTISEED_CANDIDATE_REPRODUCTION`；SCOPE `FOUR_MODEL_COSINE9_REAL_ZERO_CANDIDATE_REPRODUCTION_V1`；预期终态 `COMPLETE_STAGE4_MULTISEED_CANDIDATE_REPRODUCTION`；decision `MULTISEED_CANDIDATE_REPRODUCTION_Q2_Q3_EVALUATION`。
- 执行代码 `ca2ed1ab20e5ef9b00b05d22e0d1daefa3c3e7ed`（"Implement the bounded four-model candidate-reproduction package"）；固定副本 `D:\研究\极端降水预测\YunTAPR-Stage4-CandidateRepro-Exec-ca2ed1a`（detached ca2ed1a、工作树干净）。
- 规范提案 SHA-256 `cda647c62402dfa64831f1762c0b1597af0a250d1d9811df242ceb2c8537772b`；私有提案文件 106,260 B（SHA-256 `BE6389BFDF17E1742DFCD3F91FC11AAA944C40BA75AF7F7FE8E6DBC0A0F2AB76`）；公开副本 `STAGE45_STEP4_CANDIDATE_REPRODUCTION_EXECUTION_PROPOSAL_V1.json`（LF 规范化，105,090 B，SHA-256 `EFA39F278AE71887A43719C4C023826EF4406A8D82174BC94E66E58DFBB88DA8`；JSON 内容与私有提案全等，规范 SHA 一致）；private seal `945f1c3f975bb0e18c9a58202057b72d4339a1ac98d178927c00ca6578c00313`（文件 92,563 B，SHA-256 `9182CD9D05EB8329A10F97D65BACCA8CC3C22FE88467D5598A83D2828EDF465A`）；执行 spec 文件 1,483 B（SHA-256 `1C58A049991C635A0A88371C381556921E2A51265F6DEFE65E91BB98EE1496CA`）。
- 私有命名空间 `docs/research_readiness/.local/train_stage4_multiseed_candidate_repro_v1`；输出根 `F:\pytorch\Research\YunTAPR_stage4_multiseed_candidate_reproduction_20261127_v1`（尚不存在）。
- 输入身份：A 公开结果 `2318032d…`（33,526 B）、A completion `87fe93d4…`（含四任务 121 项数组 SHA 清单）、V4 地形结果（9,900 B）、seed2029 Dev 验收结果 `5e184d57…`（7,082 B）、2024 卫星 manifest 内部 SHA `6bd5a810…`（963 场景 / 5,778 文件）；四模型固定 E9 检查点与 A 包相同（`ee7f81da…`/53,906,437 B、`c8e0f574…`/53,906,757 B、`ce2aad58…`/53,906,885 B、`47022bd5…`/53,906,885 B）。
- 任务：REAL_s2030 → ZERO_s2030 → REAL_s2031 → ZERO_s2031 串行；每任务读 121 个数组分片（881,894,762 B）+ 其 S1 候选场景卫星 6 槽 `tbb_08/tbb_13`（78/66/132/144 文件）+ 元数据 3 文件；每任务按自身基线计算九门；REAL 任务给 Q2 PASS/FAIL，ZERO 任务给 Q3 描述性统计。
- 冻结规则逐字沿用：S1 `p*q32>20 ∧ a0≥9.5373`；候选场景=含 ≥1 S1 行；SP04 25 原生格面积均值（25 格全有效否则该像元未定义）；split=`tbb_08−tbb_13` 面积均值、`split_min` 为 6 槽最小；S2 `split_min≥2.3612`；动作 blend-to-top 至 `A=20.01`（u 公式、分母>0、0<u<1、节点严格递增、new A>20）；门 1 强雨物理 Pinball/20 严格改善、门 2 真强雨命中≥1 且不减少、门 3 非强雨误报不增加、门 4/5 q32 支撑计数不变、门 6 弱雨 log Pinball 不变、门 7/8/9 按构造恒等。判定：全 REAL PASS → `CANDIDATE_REPRODUCED_ACROSS_SEEDS`；部分 PASS → `PARTIAL`；全 FAIL → `NOT_REPRODUCED`；任一任务失败即 `STOP_NO_RETRY`，不重试不重放。
- 预算：科学打开 904 + 元数据 3 = **907**；源字节 5,402,764,976 + 7,269,111 = **5,410,034,087**；检查点 0、模型前向 0、优化器更新 0、重试/重放 0；最长 1,800 秒；最小可用 8 GiB；输出上限 4 GiB；Dev 963 场景；不访问 2025。均低于本次申请上限（≤3,700 打开 / ≤18,000,000,000 B / 1,800 秒 / 零前向）。
- 准入核验：`prepare` 在固定副本执行成功（输入 artifact、A completion 数组清单、卫星 manifest、预算合计）；准入干跑 `ENTRY_OK` / `CHECKED_OK True` / `OUTPUT_ROOT_ABSENT True` / `DRYRUN_B_CHECKED_OK`；固定副本 HEAD=ca2ed1a、干净；提案 status `READY_WAITING_EXACT_RESEARCHER_APPROVAL`、authorized=False、final_2025_access=False。
- 偏差披露：① V4 地形收据无 `final_2025_access` 字段，其校验改为 status 以 `COMPLETE` 开头、`automatic_retry/replay` 为 False、逐任务 epoch-09 检查点 SHA/字节与 4×4,320 更新/1,910,287,815,360 B 合计；② seed2029 的 PASS 仅引用既有 `STAGE45_DEV_ACCEPTANCE_RESULTS_V1.json`（prepare 校验并绑定 SHA），不重读数组、不重算；③ metadata 计量：`checked()` 仅做存在性与字节数检查（stat，不读内容），唯一计量读取在 `load_metadata` 的 ReadGuard，保证 metadata 恰 3 次、总打开恰 907；④ 结果文件命名 `STAGE45_STEP4_MULTISEED_CANDIDATE_REPRODUCTION_RESULTS_V1.json`。
- 状态：**READY_WAITING_EXACT_RESEARCHER_APPROVAL**、authorized=False、final_2025_access=False；未创建批准文件、未创建输出目录、未执行任何科学读取；公开副本仅供冻结。获批后由独立监督器单次派发并记录 Q2/Q3 终态与账本对账。
