# 种子补齐预注册（B2/B5/B6 × seed 2030/2031）V1

- 日期：2026-11-27
- 状态：`READY_WAITING_EXACT_RESEARCHER_APPROVAL`（提案已冻结、无载荷 dry-run 通过；尚未授权、尚未启动训练）
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

## 12 冻结提案与无载荷 dry-run（重封于 2026-11-27，提交 f4d44a7）

- 固定执行副本：`D:\研究\极端降水预测\YunTAPR-SeedCompletion-Exec-f4d44a7`，HEAD `f4d44a76880f844531139beef5d3a8941a83e038`；工作树干净。
- 执行器：`F:\pytorch\Research\.venv-cuda\Scripts\python.exe`（Python 3.12.14、torch 2.11.0+cu128）。
- 规范提案摘要：`proposal_sha256 = eb9ac98fa1ce12d12384fca3e29220aca78b625672ca5d4aad852ee93041ffa9`。
- 公开提案副本：`docs/research_readiness/20261128_seed_completion/SEED_COMPLETION_EXECUTION_PROPOSAL_V1.json`，LF 规范化后 108,893 B、文件 SHA-256 `e5ec42b14b7b5538d9b69842743b298566c78e623fa1b1b1cbbd13042724bd48`。
- 私有准备（不提交，位于固定副本 gitignored `.local/seed_completion_20261128_v1/PRIVATE_PREPARATION.json`）：6,805 B、文件 SHA-256 `57ba26165ea2630557c0eec16edc7f18e9d5b70edd6238b7b6e6d130145e318c`；绑定 output_root `F:\pytorch\Research\YunTAPR_seed_completion_20261128_v1`（当前不存在）。
- 提案内容：6 任务、25,920 更新、856,876 次源读取、2,865,430,597,384 B；672 个代码文件 SHA 绑定；21 个 input pins；每 seed 配对基线（B2→B3、B5/B6→B4 的 Dev E9）与 `paired_initial_identity` / `paired_orders` 引用；startup 存储准入 86,537,695,232 B（≥48 GiB）；created_utc `2026-11-27T15:06:00Z`。
- 无载荷 dry-run：使用本地内存中的工程 stub 批准对象（`decision_id: ENGINEERING_DRY_RUN_STUB_NOT_RESEARCHER_AUTHORIZATION`，**不是研究者授权**）调用 `dry_run` → `DRY_RUN_OK`；校验提案摘要、8 键批准结构、预算算术、代码 SHA、21 个 pins、输出根与 48 GiB 准入；未读 Train/Dev、未建模型、未 `torch.load`、未创建输出根。
- 批准对象（待研究者给出）：恰 8 键，必须逐字段绑定 `code_commit = f4d44a76880f844531139beef5d3a8941a83e038`、`proposal_sha256 = eb9ac98fa1ce12d12384fca3e29220aca78b625672ca5d4aad852ee93041ffa9`、tasks、budget、scientific_choices、output_root。

## 13 首次启动失败（WinError 206）、修复与重封（2026-11-27）

- 上一版冻结（固定副本 `Exec-ee69b65`、HEAD `ee69b65`、规范提案 `efd99057…`）获研究者批准后首次执行，控制器在启动第 1 个 worker 时于 `seed_completion.py` 的 `subprocess.Popen` 抛 `FileNotFoundError: [WinError 206] 文件名或扩展名太长`。
- 根因：控制器在 `checked()` 之后用已校验的**文档字典**（proposal/private/approval）而不是文件路径调用 `worker_command(...)`；`str(dict)` 生成约 115 KB 的单参数，超过 Windows 命令行上限。
- 证据与消费：输出根仅创建 `authorization_binding.json`、`task_1_claim.json`、0 B 控制台日志与 `failure.json`（STOP_NO_AUTOMATIC_REPLAY）；0 训练、0 源读取、0 指标；失败 run 与已消费批准归档于 `docs/research_readiness/.local/seed_completion_invalid_runs/run_20261127T230031Z/`。
- 修复：`execute()` 保留 `proposal_path`/`private_path`/`approval_path` 并使用路径构造 worker 命令；新增回归测试 `test_execute_spawns_worker_with_path_strings_not_documents`（断言参数为短字符串路径）；测试 **15 passed**；提交 `f4d44a76880f844531139beef5d3a8941a83e038` 并推送。
- 治理：首次批准已因工程缺陷作废（一次尝试消费）；本重新冻结需研究者给出**一次新的明确批准**后才能启动；失败即停、零重放零重试、零 2025 读取。

## 14 第二次启动失败（worker 父进程校验 vs uv venv shim）与启动环境修复（2026-11-27）

- 第二次批准（`decision_id = SEED_COMPLETION_B2B5B6_2030_2031_REAPPROVED_20261128`，批准文件 SHA-256 `D6F59FA01719940735D09EC0BFDC408A0F64A305498543FB4FFA18A21A0A0360`）对应冻结身份：固定副本 `YunTAPR-SeedCompletion-Exec-f4d44a7`（HEAD `f4d44a76880f844531139beef5d3a8941a83e038`）、规范提案 `eb9ac98fa1ce12d12384fca3e29220aca78b625672ca5d4aad852ee93041ffa9`、私有准备 6,805 B / SHA-256 `57ba26165ea2630557c0eec16edc7f18e9d5b70edd6238b7b6e6d130145e318c`。
- 失败现象：控制器创建输出根、`authorization_binding.json` 与 `task_1_claim.json` 后启动 worker，worker 立即抛 `PermissionError: Worker must be started once by the approved live serial controller`（`seed_completion.py` 的父进程校验）；0 更新、0 源读取、0 指标。
- 根因：`F:\pytorch\Research\.venv-cuda\Scripts\python.exe` 是 262,144 B 的 uv shim。控制器 `subprocess.Popen([venv_python, ...])` 的实际子进程是 shim，shim 再启动真实解释器 `C:\Users\chenerxiao\AppData\Roaming\uv\python\cpython-3.12.14-windows-x86_64-none\python.exe`；worker 的 `os.getppid()` 等于 shim 的 pid，而 `binding.controller_pid` 是控制器真实解释器 pid，二者永远不等。探针链路：controller_pid 41352 → 子进程 27908（shim）→ worker_pid 40400（ppid 27908）。
- 修复（不改代码、不改提案、不重封）：控制器继续使用 venv python，但 worker 改用真实解释器 `--worker-python C:\Users\chenerxiao\AppData\Roaming\uv\python\cpython-3.12.14-windows-x86_64-none\python.exe`，并让控制器/worker 继承 `PYTHONPATH=F:\pytorch\Research\.venv-cuda\Lib\site-packages`、`PYTHONUTF8=1`。实测：base python 直接 `subprocess.Popen` 得 controller 40612、子进程 40188、worker ppid 40612（相等）；base python 在上述 `PYTHONPATH` 下导入 torch 2.11.0+cu128（`torch.cuda.is_available() == True`）、numpy 2.5.3、yaml 6.0.3、netCDF4 1.7.4 全部成功。
- 证据与消费：第二次失败的输出根残留（`authorization_binding.json` 7,496 B、`B2_s2030_console.log` 1,020 B、`failure.json` 307 B / SHA-256 `0fef0e5ac433e6c2a4af17a473b9ab253e52ff9bf779cd8146e6431d7114ed1a`、`task_1_claim.json` 107 B）、控制器日志与已消费批准归档于 `docs/research_readiness/.local/seed_completion_invalid_runs/run_20261127T230756Z/`（含 `ARCHIVE_MANIFEST.json`）；F: 输出根已删除。
- 治理：第二次批准因工程缺陷作废（一次尝试消费）；冻结身份（commit `f4d44a7`、提案、私有准备、预算、任务表、科学选择）不变；需研究者给出**第三次明确批准**后方可启动。启动命令必须显式使用 `--worker-python`（真实解释器）并继承上述 `PYTHONPATH`；失败即停、零重放零重试、零 2025 读取。

## 15 第三次启动（研究者批准后，运行中，2026-11-27）

- 第三次批准：`decision_id = SEED_COMPLETION_B2B5B6_2030_2031_THIRD_APPROVED_20261128`，批准文件 `RESEARCHER_APPROVAL.json` 6,170 B、SHA-256 `399EC8C5C5901C900A33DC53E4CC3D968271D99C027C907FB1E191F08BBACBBC`，恰 8 键并与冻结提案全等（`code_commit = f4d44a7…`、`proposal_sha256 = eb9ac98f…`、6 任务、预算、scientific_choices、`output_root = F:\pytorch\Research\YunTAPR_seed_completion_20261128_v1`）；`dry_run` 通过（`DRY_RUN_OK`，输出根不存在）。
- 启动（本地 2026-11-27 23:16:20）：控制器 = 固定副本 `YunTAPR-SeedCompletion-Exec-f4d44a7` 下 `F:\pytorch\Research\.venv-cuda\Scripts\python.exe -B tools/research_readiness/start_seed_completion.py execute …`，`--worker-python C:\Users\chenerxiao\AppData\Roaming\uv\python\cpython-3.12.14-windows-x86_64-none\python.exe`；控制器/worker 继承 `PYTHONPATH=F:\pytorch\Research\.venv-cuda\Lib\site-packages`、`PYTHONUTF8=1`。绑定文件记录 controller_pid 40600；进程链 18356（shim）→ 40600（真实控制器）→ 13064（worker，ppid 40600），父进程校验通过。
- 启动证据：输出根已创建，`authorization_binding.json` 7,501 B、`task_1_claim.json` 108 B；`B2_s2030/initialization.json` 952 B、`train_orders.json` 311,790 B；截至 23:21，`updates.sqlite` 表 `updates` 已 174 行（RETURNED），`B2_Train_reads_01/reads.sqlite` 3,004 jobs / 3,004 file_io，凭据与既有 B2 训练循环一致；无 `failure.json`。
- 运行上限：每任务 21,600 s、整包 129,600 s（36 h）；零重放、零额外重试；任何任务失败即 STOP_NO_AUTOMATIC_REPLAY 并保留已写入账本。完成后按预注册执行独立核验（ledger 4,320/任务、三 seed 表与比较摘要、检查点身份）。


## 16 研究者暂停（2026-11-28，未恢复）

- 指令：研究者（m07171）指示“暂停进度”。暂停时间 2026-11-28 00:02:48（本地）/ 2026-11-27T16:02:48Z（UTC）。
- 终止顺序与进程：先终止控制器真实解释器 pid 40600，再终止 worker pid 13064（父 pid 40600）；控制器先终止可避免其把中断写成 `failure.json`。终止后确认三者均已退出。
- 暂停点进度：`B2_s2030` 已完成 2/9 个 epoch（960/4320 更新），暂停于 epoch 2 Development evaluation (Dev_reads_02)；该任务 reads 28883/142812 jobs、字节 96959556099/477571641012；整包累计 960/25920 更新、28883/856876 reads、96959556099/2865430597384 B。其余 5 个任务均未启动。
- 证据状态：输出根无 `failure.json`、无 `completion.json`、无 `package_completion.json`；包状态记为 `INCOMPLETE_PAUSED_MID_EXECUTION`。本暂停不是工程失败，也不是科学结果，不得据此写任何结论。
- 暂停记录：私有位置 `D:\研究\极端降水预测\.dsh_seed_completion_pause.json`（不写入已批准的证据目录）；看板 `http://127.0.0.1:8766/` 显示 PAUSED。
- 恢复治理：不自动恢复。已批准的一次性执行已被中断并消费；继续或重跑属于新的执行，必须由研究者给出新的明确批准（新提案或修订提案、预算按已消费部分重算、失败即停、零静默重试），且不得覆盖现有输出根 `F:\pytorch\Research\YunTAPR_seed_completion_20261128_v1`。可选路径：A 从零重跑 `B2_s2030`（旧目录留证、新输出目录）；B 仅执行剩余 5 任务并按已消费 960 更新重算预算；C 保持暂停。
## 17 选项 B 恢复包（2026-11-28，已消耗 960 更新核算）

- 研究者指令：m07293「恢复，按B来」。按暂停记录 `resume_policy.future_resume_options` 的选项 B 执行新批准包。
- 暂停事实：上一包（proposal `eb9ac98f…`、code `f4d44a7…`、批准 `399EC8C5…`）于 2026-11-28 00:02:48 被研究者暂停；`B2_s2030` 完成 960/4,320 更新（28,883 reads / 96,959,556,099 B），其余 5 任务未启动；整包无 `failure.json` / `completion.json`，状态 `INCOMPLETE_PAUSED_MID_EXECUTION`。
- 关键发现：暂停产物只保存了 `B2_LAST_epoch_01.pt`（52,625,195 B），**没有 epoch-02 检查点**；冻结 worker 没有 resume/replay 语义。因此“从第 960 更新续跑”无法在不动代码、不重放的前提下实现。
- 决策（选项 B 的忠实实现）：新批准包在**新输出根**完整重跑 6 个任务；把上一包的 960 更新 / 28,883 reads / 96,959,556,099 B 记为**已消耗**且不重用；两者合并核算为 26,880 更新 / 885,759 reads / 2,962,390,153,483 B。
- 冻结身份：固定副本 `YunTAPR-SeedCompletion-Resume6-Exec-a03899f`（HEAD `a03899f…`）；规范提案 SHA-256 `b9d6700f5201ef27f960a45d4ecf11e4e9709a168dff52a24ffb1044563064dc`；公开提案 `SEED_COMPLETION_RESUME6_EXECUTION_PROPOSAL_V1.json`（110946 B，SHA-256 `43dcd63ade2c43b4a2e0177be61f1ebf0c935d5592eaa77d6491b85a40e9e3f1`）；私有准备 6,829 B（SHA-256 `95d20244a39dfa802d90b60d0580e1e23b078231804a4885cfb2edd34a3b5187`）；提案内 `resume_context` digest `a4a0cb21…`；代码提交 `a03899f…` 已推送。
- 任务与预算：6 任务顺序 B2/2030, B2/2031, B5/2030, B6/2030, B5/2031, B6/2031；25,920 更新 / 856,876 源读取 / 2,865,430,597,384 B；每任务 21,600 s、整包 129,600 s；初始 48 GiB、每任务 24 GiB；零 replay、零额外重试。
- 输出根：`F:\pytorch\Research\YunTAPR_seed_completion_20261128_v1_resume6`（必须不存在）；**不得覆盖**暂停根 `F:\pytorch\Research\YunTAPR_seed_completion_20261128_v1`；暂停根与暂停记录（SHA-256 `e7c1bc825726e78c521f4e3f5697542b389d4a3e4bef1f259353e9d61591af8a`）保留为证据。
- 比较与不变量：与全量包相同的 B2→B3、B5/B6→B4 三 seed 配方与 Dev E9 基线；三 seed 表补齐后只作描述性汇总（均值±SD，不宣称显著性）。
- 批准对象：恰 8 键（approved_by_researcher / decision_id / code_commit / proposal_sha256 / tasks / budget / scientific_choices / output_root），`dry_run` 通过后方可单次启动。
- 失败策略：任一任务失败即 `STOP_NO_AUTOMATIC_REPLAY`，保留已写入账本，不自动重试；2025 数据不读取、不回流。
- 边界：本包是训练补齐与描述性 Dev 汇总，不构成 2025 最终测试、独立验证或机制因果结论。
## 18 选项 B 恢复包第四次启动（因 H: 卷离线 STOP，2026-11-28）

- 授权对象：`decision_id = SEED_COMPLETION_B2B5B6_RESUME_OPTION_B_APPROVED_20261128`，8 键批准文件 6,355 B / SHA-256 `28a1e63ee84374e839d51d24dd2b3320007534bf02ca41393682a6cc0f884ed8`（`researcher_instruction = "恢复，按B来"`，ref m07293；`dry_run` 通过）。
- 冻结身份：固定副本 `YunTAPR-SeedCompletion-Resume6-Exec-a03899f`（HEAD `a03899f…`）；规范提案 `b9d6700f5201ef27f960a45d4ecf11e4e9709a168dff52a24ffb1044563064dc`；公开提案 SHA-256 `43dcd63ade2c43b4a2e0177be61f1ebf0c935d5592eaa77d6491b85a40e9e3f1`；输出根 `F:\pytorch\Research\YunTAPR_seed_completion_20261128_v1_resume6`。
- 启动与失败：2026-11-28 08:42:21 创建输出根，控制器（venv python）与 worker（真实解释器 cpython-3.12.14 + `PYTHONPATH` 指向 venv site-packages）父进程校验通过；worker 在 `B2_s2030` 第一批准 Train 批次读取时抛 `FileNotFoundError: [WinError 3] H:\葵花202303_202510\202310\03\NC_H09_20231003_1700_R21_FLDK.06001_06001.nc`；**0 更新、0 源读取、0 指标**，根/任务两级 `failure.json` 均为 `STOP_NO_AUTOMATIC_REPLAY`。
- 环境证据：`Get-Volume` / `Get-CimInstance Win32_LogicalDisk` 仅显示 C/D/E/F（内部 NVMe），无 exFAT 卷，H: 不存在；即训练所依赖的外置 Himawari 2TB 卷当前未连接（物理离线），非代码缺陷。
- 证据归档：本次输出根已删除，授权绑定、两级 failure、claim、console、controller 日志与已消费批准归档至 `docs/research_readiness/.local/seed_completion_invalid_runs/run_20261128T084221Z/`（含 `ARCHIVE_MANIFEST.json`）；暂停根 `F:\pytorch\Research\YunTAPR_seed_completion_20261128_v1` 未触碰。
- 治理：本次一次性批准已被该次尝试消费；不自动重试、不重放。重新启动需 ①研究者重新连接 H: 卷并确认；②研究者给出一次新的明确批准（同提案/预算，新 decision_id 与批准文件）；③再次 `dry_run` 通过后单次启动。
## 19 选项 B 恢复包第五次启动（H: 卷恢复在线，retry2，2026-11-28）

- 触发：研究者于 2026-11-28 08:48 重新接入外置 Himawari 卷并回复「已接入」（m07555）。
- 环境复核：`H:\葵花202303_202510` 在线（H: 1,376.5 GB 可用）；抽查 `H:\葵花202303_202510\202310\03\NC_H09_20231003_1700_R21_FLDK.06001_06001.nc`（2,857,879 B）、`202303\01` 首帧与 `202506\15` 帧均存在。
- 新批准（同冻结提案/预算，新 decision_id）：`SEED_COMPLETION_B2B5B6_RESUME_OPTION_B_RETRY2_APPROVED_20261128`，8 键批准文件 6,362 B / SHA-256 `0c0d0acc7d163da8c6f2b08636191cbdcf4fe2dc3eb4e595ea838fd80a8b7ea6`；`researcher_instruction = "已接入"`，ref m07555；上一份已消费批准轮换为 `CONSUMED_RESEARCHER_APPROVAL_attempt4_28a1e63e.json`。
- 冻结身份：固定副本 `YunTAPR-SeedCompletion-Resume6-Exec-a03899f`（HEAD `a03899f…`）；规范提案 `b9d6700f5201ef27f960a45d4ecf11e4e9709a168dff52a24ffb1044563064dc`；公开提案 SHA-256 `43dcd63ade2c43b4a2e0177be61f1ebf0c935d5592eaa77d6491b85a40e9e3f1`；`dry_run` 通过（6 任务、25,920 更新、2,865,430,597,384 B、129,600 s 上限、零重放零重试）。
- 启动：2026-11-28 08:49:09 创建输出根 `F:\pytorch\Research\YunTAPR_seed_completion_20261128_v1_resume6`；控制器 venv python + worker 真实解释器（cpython-3.12.14 + `PYTHONPATH` 指向 venv site-packages）父进程校验通过；`B2_s2030` 初始化完成并开始写入 updates 账本，无 `failure.json`。
- 运行边界：每任务 21,600 s、整包 129,600 s 上限；零 replay、零额外重试；任一任务失败即 STOP_NO_AUTOMATIC_REPLAY；2025 数据不读取。
