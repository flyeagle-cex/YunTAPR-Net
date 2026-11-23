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

## 4. 每模型与整包预算（拟）

每模型：4,320 更新；477,571,953,840 B；142,813 次打开；21,600 s；初始 24 GiB 可用；检查点 53,906,821 B ×1；E9 加载 1 次；重试 0、重放 0、额外检查点 0。

4 模型串行整包：17,280 更新；1,910,287,815,360 B；571,252 次打开；86,400 s（24 h）；初始 96 GiB；失败即停、零重试、零重放；不访问 2025。

（每模型 Dev 评价由既有训练执行器在训练内完成，不新增读数预算。）

## 5. 评估包（须分别冻结/批准；预算以对应提案为准）

- E1 多 seed 山区配对评价：对 seed2030、2031 各 REAL/ZERO 对运行既有 mountain_pair 评价（读 checkpoint 53.9 MB ×2 + Dev 前向 7,950 打开/26.6 GB ×2 每对）。预计 2 对约 106,989,518,072 B / 31,812 次打开。
- E2 候选跨 seed 复现：对 seed2030/2031 的 REAL 臂（ZERO 对照臂可选）运行冻结候选九门判定；需要 (i) 该 seed/arm 的 Dev 逐像元 p/qlog/truth 数组（121 分片/881,894,762 B 量级；7,950 打开/26.64 GB 量级），(ii) 候选场景末 6 槽卫星 B13/B08 读取（每 seed ≤780 文件 / 3,593,008,460 B 量级）。每 arm 约 8,730 次打开/30.2 GB；2 个 REAL arm 约 60.5 GB / 17,460 次打开。
- E3 独立事件/反例/地形分层：基于 E1/E2 输出离线统计，不新增读数；如需事件目录，沿用 `IMERG_REFERENCE_EVENT_PROTOCOL` 已冻结参数。

## 6. 预注册判定规则（草案）

- D1 地形机制：对 seed ∈ {2029, 2030, 2031}，同调度 REAL−ZERO 高海拔强雨物理 Pinball/20 差值 δ_s。若 ≥2/3 个 seed 的 δ_s < 0 且三 seed 等权均值 < 0，判「地形机制方向可复现」；否则如实记录为未复现/反例。附 UTC 删周稳健性（沿用 seed2029 口径）。
- D2 候选跨 seed：对每个 REAL seed 按冻结九门（同一 STAGE2 口径）判定 PASS/FAIL；全部 REAL seed PASS 才判「候选效应跨 seed 可复现」。ZERO 对照臂仅作描述性对照：若 ZERO 臂也 PASS，则记录「候选机制可能不依赖地形」而非宣称复现。
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

`DRAFT_PREPARATION`：未冻结、未获批、未启动训练、未访问 2025。
