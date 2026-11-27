# 种子补齐预注册（B2/B5/B6 × seed 2030/2031）V1

- 日期：2026-11-27
- 状态：`DRAFT_NON_EXECUTABLE_NOT_RESEARCHER_FROZEN`（准备完成后改为 `READY_WAITING_EXACT_RESEARCHER_APPROVAL`）
- 代码基线：`8f54c4587505628a929d5a204a7d2130ecaaba4f`（准备提交的父提交；实际执行 commit 由批准对象绑定干净固定副本 HEAD）
- 协议：`config/training/seed_completion_protocol_v1.yaml`
- 范围：`SEED_COMPLETION_B2_B5_B6_2030_2031`

## 1 研究问题与动机

2026-11-27 阶段汇报的 2024 Development 指标表混合了 3-seed 与 1-seed 配置：S2 单时次基线（B2）、S4 高程单通道（B5）、S4 六通道静态地形（B6）只有 seed2029 一个种子，属于探索性证据。按常规确认性研究实践，用于确认性主张的每个配置至少需要 3 个独立训练 seed 才能估计 seed 间离散度并避免单 seed 偶然性。

本预注册只回答一个问题：**把 B2、B5、B6 的 seed 2030 与 2031 按与 seed2029 完全一致的冻结配方补齐，使每个阶段配置达到 3 seed 最低线。**

不回答机制因果、不改变 2025 最终测试结论、不建立显著性判决。

## 2 任务清单（共 6 个新模型）

| # | 模型 | seed | 用途 |
|---|------|------|------|
| 1 | B2 | 2030 | S2 单时次基线 |
| 2 | B2 | 2031 | S2 单时次基线 |
| 3 | B5 | 2030 | S4 + 高程单通道（对照） |
| 4 | B6 | 2030 | S4 + 六通道静态地形（对照） |
| 5 | B5 | 2031 | S4 + 高程单通道（对照） |
| 6 | B6 | 2031 | S4 + 六通道静态地形（对照） |

执行顺序固定为上述顺序，串行、单次、失败即停。

## 3 冻结配方（只改 seed）

- **B2**：7 光谱通道、单一时次（t−10），冻结 B2 stem rule 从 B3 参考初始化；E0 九轮、4,320 更新；固定 2023 Train / 2024 Dev 人口；数据、scaler、评估代码不变。
- **B5**：Stage4 B4 主干 + SP04 高程单通道（width 16、加性残差零输出初始化）；E0 九轮、4,320 更新；数据/scaler/评估不变。
- **B6**：Stage4 B4 主干 + 六静态地形通道（高程、东/北梯度、坡度、坡向 sin/cos，width 16、加性残差零输出初始化）；E0 九轮、4,320 更新。
- seed 只改变初始化 RNG 与 epoch 顺序派生；不得改变数据、模型结构、优化器或预算。
- 实现层：新模块复制既有 `b2_runner.py` / `static_training.py` 的训练循环逻辑并参数化 seed，**既有模块保持字节不变**（避免改变既有证据链）。B2 输出根从仓库内 `.local` 改为仓库外私有绝对目录，作为已接受的新策略写入协议。

## 4 不变量与禁止项

- 人口：2023 Train / 2024 Dev 固定人口（核心人口 959/963）。
- 固定 E9 端点；无早停、无 Dev 选择、无 checkpoint 选择。
- 每任务单次执行；零 replay、零额外重试；失败写 `failure.json`，需新批准才能重跑。
- 2025 年任何数据（Himawari/IMERG/GFS）永不读取，不得用于调参、选择或训练。
- 不改静态地形输入、GFS f006 字段顺序、归一化与评估代码。
- 不修改既有 `b2_runner.py`、`static_training.py` 等既有模块。

## 5 比较与分析计划

同 seed 配对基线（全部为固定 E9 的 Dev 报告）：

- B2_2030 vs B3_2030；B2_2031 vs B3_2031；
- B5_2030 / B6_2030 vs B4_2030；
- B5_2031 / B6_2031 vs B4_2031。

次比较：B6−B5（同 seed 与三个 seed 均值）；B2/B3/B4/B5/B6 三 seed 等权家族均值。

指标（冻结评估代码）：Brier、AUROC、Average Precision、条件 pinball、q32 覆盖与偏差、分组指标。报告 per-seed 值与三 seed 等权均值，**描述性、不做显著性推断**。

## 6 预算（精确冻结）

| 项目 | 每模型 | 数量 | 小计 |
|------|--------|------|------|
| 更新 | 4,320 | 6 | 25,920 |
| 源读取次数 | B2 142,812；B5/B6 142,813 | 6 | 856,876 |
| 源字节 | B2 477,571,641,012；B5 477,571,703,840；B6 477,571,953,840 | 6 | 2,865,430,597,384 |

- 每任务墙钟上限 21,600 s；包上限 129,600 s（36 h 串行）。
- 初始空闲 ≥48 GiB，每任务 ≥24 GiB；输出根 `F:\pytorch\Research\YunTAPR_seed_completion_20261128_v1`（当前不存在）。
- 零 checkpoint 加载、零推理前向、零 replay、零额外重试。

## 7 执行门与治理

1. `PREPARE_FROZEN_PROPOSAL_AND_PRIVATE_PREPARATION`：生成含任务、预算、code SHA、数据身份与基线 pins 的 proposal 与 private preparation。
2. `NO_PAYLOAD_DRY_RUN_AND_CODE_HASH_BINDING`：dry-run 只校验身份/预算/输出根/磁盘，不读 Train/Dev、不建模型。
3. `SEPARATE_EXACT_RESEARCHER_AUTHORIZATION`：一份明确批准，必须逐字段绑定 code_commit、proposal_sha256、tasks、budget、scientific_choices、output_root。
4. `ONCE_ONLY_SERIAL_EXECUTION_WITH_FAILURE_STOP`：单控制器串行 6 个 worker；每任务 wall cap 21,600 s；包 cap 129,600 s。
5. `INDEPENDENT_VERIFICATION_AND_DOCS_GITHUB_OBSIDIAN_SYNC`：独立核验账本/哈希/闭合；文档、提交推送与 Obsidian 同步。

## 8 失败策略

任何任务或控制器失败：写 `failure.json`（`STOP_NO_AUTOMATIC_REPLAY`），保留全部部分账本与控制台日志；不重试、不重放、不续跑。任何重跑要求新提案 + 新预算 + 新明确批准。

## 9 不包含项（明确排除）

- B0/B1 第三 seed：历史 Phase-A 基线，人口（10,455/10,501）与本次核心人口不同，不属本阶段对比表。
- B0 FINAL：Phase-B FinalFit 单模型终测，设计上不补 seed。
- PERP：单 seed 探针，不属阶段对比主链。
- B9：尚未启动。
- 12 模型 2025 最终测试：结论已冻结（E0 家族三 seed 已存在），本包不重跑 2025 推理。
- E0 对照行与 COSINE9 行：以既有检查点/Dev 报告重排三 seed 表，不新训练。

## 10 预期产物

- `proposal.json`、`private_preparation.json`、`execution_spec.json`（新输出根与 .local 私有准备）。
- 每任务：`{model}_s{seed}/` 下 9 个 LAST 检查点、train/dev 报告、pass receipts、updates ledger、`completion.json`。
- 包级：`authorization_binding.json`、`package_completion.json`、`failure.json`（失败时）、每 seed 对比摘要、独立核验收据。
- 文档：本预注册 + 结果报告 + 公开证据收据；GitHub 提交与 Obsidian 段落。

## 11 批准对象（一次明确批准）

批准文件必须包含：`approved_by_researcher: true`、`decision_id`、`code_commit`、`proposal_sha256`、`tasks`、`budget`、`scientific_choices`、`output_root`，与冻结 proposal 全等。批准前不写任何授权文件、不启动任何训练。
