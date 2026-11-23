# 第 4 步：同 COSINE9 调度 REAL/ZERO 多 seed 地形机制与候选跨 seed 复现预注册（V1 草案）

状态：`DRAFT_PREPARATION`（预注册草案；未冻结、未获批、未启动任何训练）

日期：2026-11-23

依据：`STAGE45_OBSERVATION_INTAKE.md` WP4；`STRONG_RAIN_GATE_ENTRY_V1.md`（强雨主门通过后，再申请同调度、同山区联合分层的 REAL/ZERO 复现）；`STAGE2_EVALUATION_FREEZE_V1.md`；`IMERG_REFERENCE_EVENT_PROTOCOL_V1.md`。

## 1. 目的

第 3 步单一预注册候选已在 Dev 一次性九门验收 PASS（2026-11-23；规范提案 `f568e8401d27b9e1e552cdb9dc539c4e1f052126cccda7dd26d079453b273bec`，执行代码 `2392f51`，公开收据 SHA `5e184d57…`）。其证据边界已如实记录：717 个强雨中仅 1 个激活像元、门 1 余量约 `1.2e-4`；门 4/5/7/8/9 因 p 与 q32 固定按构造恒等；`scientific_status=NOT_VERIFIED`。

第 4 步要回答：

- Q1（地形机制）：同 COSINE9 调度、同山区联合分层下，REAL 相对 ZERO 的高海拔强雨幅值改善是否能跨 seed 复现（2029 之外新增 2030、2031）。
- Q2（候选复现）：已冻结的云顶选择器 + blend-to-top 动作，在 seed2029 之外的 REAL 臂上是否仍能通过同一套冻结 Dev 九门判定。
- Q3（机制归因）：冻结候选的效应是否依赖 REAL 地形机制（在 ZERO 控制臂上应不出现同向强雨幅值改善，或给出预注册对照判定）。

## 2. 已有证据（冻结，不重跑）

- REAL seed2029 / COSINE9：`status=COMPLETE_TRAIN_AND_DEV_EVALUATION`，`code_commit=e54ccc16f988628e2dc6c4b91f76051ae94c4629`，4,320 更新，477,571,953,840 B / 142,813 文件，COSINE9_V1（9 epochs ×480，peak_lr 1e-4 / min 1e-6）。
- ZERO seed2029 / COSINE9：`code_commit=b4f15fb8dfeced23c28824f04b35158077678950`，同预算；`dynamic_control=ZERO_NUMERIC_RETAIN_REAL_MASKS`；`scientific_acceptance=NOT_VERIFIED`。
- 山区配对评价 seed2029：`.local/mountain_pair_evaluation_v1`，`status=COMPLETE_REAL_ZERO_MOUNTAIN_EVALUATION`，16,365 次打开 / 54,108,659,903 B；REAL−ZERO 高海拔强雨物理 Pinball/20 = −0.000696197（约 −0.1367%），log Pinball −0.001842784，q32 覆盖 6/178→11/178；低/中海拔强雨退化；两臂固定 A（>20 mm/h）命中均 0/717；UTC 删周（27 周含高海拔强雨）差值 −0.001219001 至 +0.000262621（26 负 1 正）。
- 历史 E0 三 seed（旧调度）：REAL−ZERO 20–50 log Pinball = −0.02804406 / +0.00580321 / +0.00528748（仅 1/3 改善）。调度与协议不同，不能替代 COSINE9 多 seed 证据。
- 冻结 Dev 评价口径：9 项联合条件；963 场景 / 3,303,090 监督像元 / 717 强雨 / 246,473 弱雨；基线见 `STAGE2_EVALUATION_FREEZE_V1.md` 与 `CONDITIONAL_TAIL_BASELINE`。
- 第 3 步候选 PASS：门 1 `0.5068646309277545 → 0.5067400512587865`（−1.2458e-4）；门 2 tp 0→1；门 3 fp 0；门 4/5 160/5,769 不变；门 6 `0.08872231160181855` 不变；门 7/8/9 由构造恒等；唯一激活像元 2024-09-30T17:30 row 57（y=17, x=44）。

## 3. 新增 arms（本次拟申请）

| arm | model | seed | 调度 | dynamic_control | 端点 |
|---|---|---|---|---|---|
| REAL_COSINE9 | B7 | 2030 | COSINE9_V1 | REAL_PHYSICAL_DOTE | epoch9 last |
| ZERO_COSINE9 | B7 | 2030 | COSINE9_V1 | ZERO_NUMERIC_RETAIN_REAL_MASKS | epoch9 last |
| REAL_COSINE9 | B7 | 2031 | COSINE9_V1 | REAL_PHYSICAL_DOTE | epoch9 last |
| ZERO_COSINE9 | B7 | 2031 | COSINE9_V1 | ZERO_NUMERIC_RETAIN_REAL_MASKS | epoch9 last |

匹配要求（预注册；工程冻结时逐项核对）：

1. 同一 COSINE9_V1 调度实现与更新顺序（9 epochs ×480；`ONE_BASED_LR_SET_BEFORE_OPTIMIZER_STEP`）；
2. 同 seed 的 REAL 与 ZERO 使用同一 B7 初始 state 摘要（E0 初始化按 seed 构造；ZERO 仅替换数值通道为零并保留真实 mask/RH，沿用 seed2029 ZERO 协议）；
3. 训练数据、批次顺序与源清单与 COSINE9 seed2029 完全一致（477,571,953,840 B / 142,813 文件；manifest `f0c0a9188e771bfbba7c1e8a8ffdbfabd2d4e927bd1428d353b290be236a13dc`）；
4. 每模型保存 epoch9 last 检查点与 Dev 评价报告，格式与 seed2029 一致。

E0 初始化的额外预注册要求（2026-11-23 事实清单补充）：

- seed2030/2031 的 COSINE9 E0 必须由当前冻结的 E0 构造函数重新构造并导出完整 state SHA，写入 proposal/private；不得假定旧调度包中的 B7 全态 SHA（2030 `50dcc329…`、2031 `65c48896…`）与 COSINE9 E0 相同，也不得直接搬用。
- 同 seed 的 REAL/ZERO 必须在运行前用机器断言比对完整 state SHA 相等（沿用 seed2029 `paired_initial_identity.json` 的 B7 `ab749c88…` / common `4404bc9d…` 方式），不相等即停止。
- 旧调度 E9（REAL 2030 `820796…`、2031 `4537be7…`；ZERO 2030 `b03ee41…`、2031 `f999529…`）只作历史对照，不得替代 COSINE9 多 seed 证据。

工程身份补充（2026-11-23 事实清单）：

- 现有实现硬锁：`cosine9_training.py:186`、`zero_cosine9_training.py:167`、`stage4/engine.py:208` 仅允许 B7/seed2029；目录与 PYTHONHASHSEED 也写死 2029。多 seed 包必须在新的、经审查的代码 commit 中加入合法分支（seed 白名单、每任务 seed 绑定、目录名 `B7_s<seed>`、PYTHONHASHSEED 按任务赋值），不得绕过既有校验。
- 干净树门控：canonical 仓库存在历史未跟踪文件，会被既有 clean checkout 校验拒绝；冻结执行必须在全新固定 worktree（clean）中进行。

## 4. 每模型与整包预算（拟）

每模型：4,320 更新；477,571,953,840 B；142,813 次打开；21,600 s；任务启动可用 ≥24 GiB；检查点加载 0 次（seed 驱动 fresh 初始化，不加载任何既有权重）；零重试、零重放；由训练执行器写出 epoch9 last 检查点与 Dev 评价报告各 1 份。

4 模型串行整包：17,280 更新；1,910,287,815,360 B；571,252 次打开；86,400 s（24 h）；初始可用 ≥48 GiB；失败即停、零重试、零重放；不访问 2025。

存储校准（2026-11-23，冻结前修订）：4 模型串行执行时峰值为单任务；seed2029 单模型完整产出实测约 0.55 GB；48 GiB = 2× 单任务 24 GiB 下限，而固定数据卷可用 ≥80 GiB。私有输出放在独立数据卷，精确路径与创建检查在冻结提案中记录；若冻结时该卷可用空间低于 48 GiB，直接拒绝启动。

（每模型 Dev 评价由既有训练执行器在训练内完成，不新增读数预算。）

## 5. 评估包（须分别冻结/批准；预算以对应提案为准）

- E1 多 seed 山区配对评价：对 seed2030、2031 各 REAL/ZERO 对运行既有 mountain_pair 评价（读 checkpoint 53.9 MB ×2 + Dev 前向 7,950 打开/26.6 GB ×2 每对）。预计 2 对约 106,989,518,072 B / 31,812 次打开。
- E2 候选跨 seed 复现：对 seed2030/2031 的 REAL 臂（ZERO 对照臂可选）运行冻结候选九门判定；需要 (i) 该 seed/arm 的 Dev 逐像元 p/qlog/truth 数组（121 分片/881,894,762 B 量级；7,950 打开/26.64 GB 量级），(ii) 候选场景末 6 槽卫星 B13/B08 读取（每 seed ≤780 文件 / 3,593,008,460 B 量级）。每 arm 约 8,730 次打开/30.2 GB；2 个 REAL arm 约 60.5 GB / 17,460 次打开。
- E3 独立事件/反例/地形分层：基于 E1/E2 输出离线统计，不新增读数；如需事件目录，沿用 `IMERG_REFERENCE_EVENT_PROTOCOL` 已冻结参数。

## 6. 预注册判定规则（草案）

- D1 地形机制：对 seed ∈ {2029, 2030, 2031}，同调度 REAL−ZERO 高海拔强雨物理 Pinball/20 差值 δ_s。若 ≥2/3 个 seed 的 δ_s < 0 且三 seed 等权均值 < 0，判「地形机制方向可复现」；否则如实记录为未复现/反例。附 UTC 删周稳健性（沿用 seed2029 口径）。
- D2 候选跨 seed：对每个 REAL seed 按冻结九门（同一 STAGE2 口径）判定 PASS/FAIL。判定采用「各 seed 自身基线」：每个 seed 用其自身冻结 Dev 预测计算基线指标，再与其候选后（选择器 + blend-to-top）指标比较；门的方向与绝对条件（门 2 ≥1 真强雨命中、门 3 =0 非强雨命中、门 4/5 q32 计数不变、门 6 弱雨不变、门 7/8/9 由构造恒等）与 seed2029 完全一致；不得用 seed2029 的基线数值替代其他 seed 的基线。全部 REAL seed PASS 才判「候选效应跨 seed 可复现」。ZERO 对照臂仅作描述性对照：若 ZERO 臂也 PASS，则记录「候选机制可能不依赖地形」而非宣称复现。
- D3 证据边界：3 seed 不等于广泛泛化；2025 仍封存；门 4/5/7/8/9 恒等性质同样适用于跨 seed 判定（只计真实变化项）。
- D4 停止规则：任一模型训练/评价失败 → 失败即停、记录、不自动重试；任一预注册判定不成立 → 如实记录负结果，不扩展 seed、不追加读数。

## 7. 工程与身份（待冻结）

- 新执行器：COSINE9 多 seed REAL/ZERO 串行包（4 任务，失败即停）；
- 评估扩展：多 seed 山区评价；每 seed/arm Dev 逐像元数组读取 + 冻结候选判定（复用第 3 步冻结的 selector/blend 与 SP04 读取，不重算阈值）；
- 待冻结：代码 commit、规范提案 SHA、私有准备 SHA、每 arm 初始 state 摘要、检查点与评价收据 SHA。

本文件为预注册草案；正式冻结以对应 `EXECUTION_PROPOSAL` 为准。

## 8. 待决事项

1. 是否同时训练 ZERO 2030/2031 → 建议是（地形机制 Q1 必需）。
2. E2 是否对 ZERO arm 也跑候选判定 → 建议是，但仅作预注册对照（见 D2）。
3. 训练顺序 → 建议按 seed 配对（REAL2030→ZERO2030→REAL2031→ZERO2031），利于失败时保留可评价对；若 GPU 次序有更优方案，在提案中显式声明。
4. 初始 state 摘要来源 → 工程冻结时从执行器初始化路径导出并逐项核对。
5. 若只批准 seed2030 一对（n=2）→ 明确降级为 n=2 并调整 D1 判定。

## 9. 状态

`PROPOSAL_FROZEN_PENDING_RESEARCHER_APPROVAL`：代码与提案已冻结，等待研究者对本次 4 模型包的一次明确批准；未启动训练、未读原始气象载荷、未访问 2025。

## 10. 固定执行包 · 多 seed 训练 V1（2026-11-23）

- 执行器：`BOUNDED_TRAIN_COSINE9_MULTISEED_TERRAIN`；SCOPE=`FOUR_TASK_COSINE9_REAL_ZERO_SEED2030_2031`；单次批准、串行四任务（REAL2030 → ZERO2030 → REAL2031 → ZERO2031）、失败即停、零重试零重放。
- 执行代码：`061a4d94ed6f1387eebeed04ece75d94779cc534`（[GitHub](https://github.com/flyeagle-cex/YunTAPR-Net/commit/061a4d94ed6f1387eebeed04ece75d94779cc534)）；固定副本：`D:\研究\极端降水预测\YunTAPR-Train-Cosine9-Multiseed-Exec-061a4d9`（detached HEAD）。
- 规范提案 SHA-256：`65624e55361b9c39912fd89de4c917f1dd0dda993cbe434c1ea1cccbc877fb21`；公开副本：[STAGE45_STEP4_MULTISEED_TERRAIN_EXECUTION_PROPOSAL_V1.json](STAGE45_STEP4_MULTISEED_TERRAIN_EXECUTION_PROPOSAL_V1.json)（文件 SHA-256 `EF6AA724E32F0C1BFDFC51B005381DD58A269DF5C94607B005BAFBAF3A0C9B93`，111,357 B）。
- 私有命名空间：`docs/research_readiness/.local/train_cosine9_multiseed_v1`（PROPOSAL.json / PRIVATE_PREPARATION.json / EXECUTION_SPEC.json / service/），无 `RESEARCHER_APPROVAL.json`、无 output。
- 提案状态：`READY_WAITING_EXACT_RESEARCHER_APPROVAL`、authorized=False、final_2025_access=False。
- 身份链：UQ E0 对照 → COSINE9 REAL seed2029（`e54ccc16…`）→ ZERO seed2029（`b4f15fb8…`）→ 本包；seed2029 REAL 原始初始化 `ab749c88…`（与冻结提案一致）；B7@2030 初始化 `50dcc3295f13b4cd1dfe79ee9b549d767dd6e708195bfb8c6afdc782d2d0c56e`、B7@2031 初始化 `65c4889632e0dd1770473016ced5cb5deeff2eade8b64db3ce2d6a347315fa91`（各 9 个 epoch order 已封存）；ZERO 数值控制复用 seed2029 收据（真实 mask 保留、128 个无损失梯度权重）。
- 预算（提案 budget 逐字冻结）：4 模型 × 4,320 更新 = 17,280；4 × 477,571,953,840 B = 1,910,287,815,360 B；4 × 142,813 = 571,252 次打开；每模型 21,600 s / 整包 86,400 s；初始可用 ≥48 GiB、每任务 ≥24 GiB；checkpoint 加载 0、replay/额外重试 0；2025 不访问。
- 输出根：`F:\pytorch\research\YunTAPR_cosine9_multiseed_s2030_s2031_20261123_v1`（不存在；父目录已存在；F: 可用约 86.6 GiB ≥ 48 GiB）。
- 验证：定向测试 29 passed / 38 subtests（`test_cosine9_multiseed.py` + `test_independent_process.py`，base python 3.13 + shim）；相关既有回归 58 passed / 178 subtests；py_compile 与 `git diff --check` 通过；只读冒烟（继承漂移允许集、ZERO 绑定、seed 初始化摘要）通过。
- 未执行：未创建批准文件、未加载模型/检查点、未创建输出根、未读原始气象载荷、未访问 2025。获批后由独立监督器按 `EXECUTION_SPEC.json` 单次派发。

> 执行前须由研究者对该提案身份（`65624e55…`）与预算给出一次明确批准；旧批准不可复用，2025 继续封存。
