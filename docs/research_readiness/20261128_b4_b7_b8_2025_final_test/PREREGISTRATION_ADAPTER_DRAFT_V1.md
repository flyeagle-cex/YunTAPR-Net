# B4 / B7 / B8 / B7_ZERO_DOTE 2025 最终测试适配器与冻结协议草案 v1

- 日期：2026-11-27
- 状态：`DRAFT_NON_EXECUTABLE_NOT_RESEARCHER_FROZEN`
- 分支/基线：`collab/codex-20261102` / `27be27ee7df3c3135e145259f73589cc587b6565`
- 范围：2025 年 3–9 月、分析时次 00/06/12/18 UTC、12 个 E9 检查点（B4/B7/B8/B7_ZERO_DOTE × 2029/2030/2031）
- 本阶段不做真实 2025 推理、不读取任何 2025 原始载荷、不加载真实检查点前向、不训练、不选择、不 commit/push。

## 1. 目标与边界

目标是为研究者提供一个**可审计、默认拒绝、单次只读**的 2025 最终测试实现草案，使人口、目录、授权、指标与比较在同一套身份绑定下可复核。该草案不构成执行授权，也不产生任何 2025 结果。

硬边界：

1. 不读取/stat/list/open 任何 2025 原始载荷（Himawari 2025 月度目录、GFS/GFS_thermo 2025、IMERG 2025）。
2. 不训练、不优化器、不做 checkpoint/超参/阈值/掩膜/集成选择。
3. 不削弱既有 2023/2024 守卫；2025 能力只存在于新模块，并由显式授权对象开启。
4. 不修改冻结的 B0 v1.1 协议及既有 evidence JSON。
5. 本阶段不写仓库外持久产物；合成 fixture 仅用系统临时目录。

## 2. 已实现内容

### 2.1 纯函数规划（planning）

`src/yuntapr/experimental/research_readiness/final_test_2025_planning.py`

- 年份 2025、默认月份 3–9、可授权扩展到 10 月；分析时次 00/06/12/18 UTC。
- 时钟约定：`sample_id = window_start = analysis_time − 30min`（UTC ISO，含 `+00:00`）。
- 6 个卫星名义时次：分析前 60/50/40/30/20/10 分钟。
- GFS 初始化 = 分析 − 6h，lead = 6h；IMERG 日文件与半小时索引由 window_start 决定。
- 默认 2025-03-01T00:00Z..2025-10-01T00:00Z 共 **856** 个候选场景；首场景为 2025-03-01T00:00Z 分析（window 2025-02-28T23:30Z），最后一个为 2025-09-30T18:00Z 分析。
- 10 月默认 `PermissionError`；所有路径均为相对路径模板渲染，纯内存、无 I/O。
- 路径模板集中在 `PathLayout2025`，默认采用 2023/2024 冻结证据中的 Himawari `YYYYMM/DD/NC_H09_..._R21_...nc`、GFS `YYYY/YYYYMMDD/gfs[_thermo]_0p25_[YYYYMMDDHH]_f006.nc`、IMERG `YYYY/imerg_YYYYMMDD.nc`，可由研究者显式覆盖。

### 2.2 人口清单（manifest）

`src/yuntapr/experimental/research_readiness/final_test_2025_manifest.py`

- 16 列人口清单 schema；每场景 6 卫槽 + GFS main/thermo + IMERG 日文件 + 冻结 identity。
- `population_sha256` 覆盖 identity digest、fixture 标志、月份与全部场景记录；`manifest_sha256` 覆盖全文。
- fixture 模式只放宽“整历计数”，不放宽时钟、唯一性、路径与监督像元规则；fixture 文档标记 `SYNTHETIC_FIXTURE_2025`。
- identity 四字段：`sp04_grid_sha256`、`supervision_mask_sha256`、`static_sha256`、`train_scalers_sha256`；四个字段均已可绑定（SP04 于 2026-11-27 绑定到 `config/b0_engineering_v4.yaml::sp04_manifest_sha256` = `e1c5d8ab…`，语义为 pinned SP04 coordinate manifest identity；其余三项来自 2023/2024 冻结证据常量）。

### 2.3 目录与授权（catalogue）

`src/yuntapr/experimental/research_readiness/final_test_2025_catalogue.py`

- 42 列候选目录 schema（6 卫槽 path/bytes/sha256、GFS main/thermo、IMERG、资格审查列），任何未知/嵌套/结果字段一律拒绝。
- `InventoryIndex` 只接受调用方提供的相对路径/大小/SHA/可读性/产品元数据；**不遍历目录**。inventory 的生成属于另行授权的 payload 阶段。
- `CatalogueAuthorization2025`：严格键集、`AUTHORIZED_BY=RESEARCHER`、`FINAL_TEST_CATALOGUE_AUTHORIZED=true`、`FINAL_TEST_2025_AUTHORIZED=false`、checkpoint catalog digest 必须等于实现中的常量、source roots 必须等于规划默认四根。
- `FinalAuthority2025`：绑定 catalogue/population/freeze 三个文件 SHA，freeze 状态必须 `CATALOGUE_FROZEN`，`created_utc` 不得早于 freeze 完成时间。
- 输出 append-only；先授权后建目录；写出 candidate CSV、population JSON、freeze record 并立即只读复核。
- `authorize_payload` 恒抛 `PermissionError`。

### 2.4 读取器（readers）

`src/yuntapr/experimental/research_readiness/final_test_2025_readers.py`

- `PayloadAuthorization2025` + `PayloadAccess2025`：没有显式授权对象时所有读取路径默认拒绝；授权 JSON 严格键集，fixture 根不得指向真实源根。
- 2025 卫星 7 通道、6 槽、501×501、K 单位、CF 起止时间与六槽网格一致性校验。
- `ForecastIdentity2025`：仅 2025、lead 6h、init 00/06/12/18；允许 2025-02-28T18:00Z 作为 2025-03-01T00:00Z 分析的 carry-in 初始化。旧 `gfs.ForecastIdentity`、`gfs.read_gfs_file` 对 2025 仍然拒绝（有测试覆盖）。
- GFS main+thermo 受限只读解码（复刻 `decode_gfs_bytes` 的校验并增加 2025 身份）；环境帧以 retrospective 模式合成。
- IMERG 日文件：产品/版本/时间网格/单位/半小时索引/目标窗口校验，裁剪 `[10:110, 20:120]` 后解码为 100×100 mm/hr。
- 新增 `prepare_multispectral_2025`：2025 专用归一化入口，复刻冻结 2023/2024 规则但显式 2025 门禁；既有 `prepare_multispectral` 的 2023/2024 守卫保持不变。

### 2.5 适配器（adapter）

`src/yuntapr/experimental/research_readiness/final_test_2025_adapter.py`

- `FinalTest2025Authority`：16 键严格授权文档，绑定 protocol/implementation/catalogue/population/freeze、12 检查点 SHA/bytes、四个冻结输入、DOTE 定义、inference 参数与 output_root。
- 模型构造：B4 用 `SpectralCandidate('B4', ...)`；B6 静态地形；B7/B8 由 `DynamicTerrainModel` 共享条件投影；B7_ZERO_DOTE 复用 B7 架构 + `ZeroNumericDote`。
- 检查点加载：SHA-256 + bytes + `epoch=9`、`updates=4320`、`identity.model`（ZERO 文件内为 `B7`）、population SHA、参数数、strict `load_state_dict`。
- 推理：`torch.inference_mode()`、scene 外层循环、12 模型一次驻留、每次读 1 个场景；默认拒绝；`FINAL_ONLY_NO_SELECTION`。
- 指标累加器：包装冻结的 `GlobalValidationAccumulator`，追加 B0 v1.1 的 coverage_error（signed/absolute/mean absolute）、`q32_signed_bias`、`q32_absolute_error`、support/crossing 计数；数值违规立即 `FloatingPointError`，不修复。
- 比较：每 seed 配对差值，然后 3 seed 等权平均；主比较 `B7_REAL − B7_ZERO_DOTE`（Brier 与条件 pinball 共主），次比较 `B8−B7`、`B7−B4`、`B8−B4`；全部仅描述性。
- 输出：`metrics/{model}_{seed}.json`、`comparisons.json`、`run_manifest.json`、`final_status.json`、`runtime_ledger.jsonl`；异常写 `failure.json`（`STOP_REQUIRED`）并以非零退出。

### 2.6 CLI

`tools/research_readiness/start_b4_b7_b8_2025_final_test.py`

- `plan`：纯日历计划，打印 856 场景与首末槽；无任何 2025 I/O。
- `prepare`：只写非执行的 `preparation_manifest.json`，不生成授权。
- `catalogue`：必须显式 `--authorization`、`--population`、`--inventory`、`--output-dir`。
- `run`：必须显式 `--authorization` 与 `--payload-authorization`；`--dry-run` 仅打印绑定计划；无授权时退出码 2。

### 2.7 协议草案

`config/evaluation/b4_b7_b8_b7zero_2025_final_test_protocol_v1.yaml`

- `DRAFT_NON_EXECUTABLE_NOT_RESEARCHER_FROZEN`，FROZEN/AUTHORIZED/EXECUTED 均为 false。
- 绑定 12 检查点 SHA/bytes/执行 commit（仅身份，不含私有路径；ZERO_DOTE 2030/2031 bytes 于 2026-11-27 由归档 epoch-09 文件 stat+SHA 复核补齐为 53,905,157 / 53,906,117）、`catalog_sha256` = `7b5bafdf9920b17c78d4949bf8a5d19a0071c06cdae3da3fa95ee57dc14aab46`、冻结输入 SHA（含 SP04 pinned manifest SHA）、指标定义、比较、禁项、四阶段授权、must-bind、预算公式（`NOT_COMPUTED`，依赖授权 inventory 阶段测得唯一源字节）与开放问题。

## 3. 授权与冻结顺序

1. **CATALOGUE_ONLY_RESEARCHER_AUTHORITY**：研究者单独批准目录阶段；调用方提供 inventory，程序只做元数据校验。
2. **OUTCOME_FREE_CATALOGUE_QC_AND_FREEZE**：只看目录/人口/冻结记录，不接触结果；生成 `CATALOGUE_FROZEN`。
3. **SEPARATE_POST_FREEZE_FINAL_TEST_AUTHORITY**：冻结完成后，研究者另行批准最终测试；绑定 12 检查点与冻结输入，允许 dry-run。
4. **FINAL_READ_ONLY_INFERENCE**：研究者再单独批准 payload 访问；程序执行一次只读推理，失败保留部分产物且不自动重试。

任何阶段未获授权，CLI 与服务层都以 `PermissionError`/退出码 2 拒绝。

## 4. 已实现 / 未实现

已实现：

- planning、manifest、catalogue、readers、adapter、CLI、协议草案与合成测试。
- 2023/2024 旧守卫仍然拒绝 2025（测试覆盖）。
- 指标定义与 B0 v1.1 对齐；配对描述性比较。

未实现（本阶段有意不做）：

- 真实 2025 inventory 的生成与 2025 原始载荷读取。
- 真实检查点加载与前向；真实 2025 人口/QC。
- 研究者冻结的预算（source bytes、checkpoint/score 存储、wall-clock）。
- PD/FAR/CSI 阈值（协议中明确 `THRESHOLD_NOT_FROZEN`）。
- 任何推断性统计或显著性裁决。

## 5. 开放问题

1. **2025 卫星产品号/模板（已解决，2026-11-27）**：冻结 2023/2024 证据使用 H09/R21 与 `YYYYMM/DD`（`docs/b0_pretraining_closure/runs/run_20260930T095416Z/real_normalized_forward_smoke.json:149`），协议 `product` 已改为 `HIMAWARI_9_AHI_L1B`；H08/R02 不是后备。2025 目录实际存在性仍属授权 inventory 阶段，本阶段未访问。
2. **GFS 2025 目录布局（已解决，2026-11-27）**：`YYYY/YYYYMMDD` 由 2023/2024 冻结原始布局证据确认（`F:\云南极端降水数据\raw\GFS\2023\20230101\gfs_0p25_2023010100_f006.nc` 及 GFS_thermo 对偶）；本阶段未列出/stat/open 任何 2025 目录。
3. **ZERO_DOTE 2030/2031 字节数（已解决，2026-11-27）**：对归档的 `B7_LAST_epoch_09.pt`（B7 架构、epoch 09）做 stat+SHA-256，SHA 与增量草案一致，bytes 绑定为 53,905,157 / 53,906,117；代码常量与协议草案同步更新，`catalog_sha256` 重算为 `7b5bafdf…`。
4. **SP04 grid SHA（已解决，2026-11-27）**：绑定 `config/b0_engineering_v4.yaml::sp04_manifest_sha256` = `e1c5d8ab1b58407503db4b56124f4a34a360507280b0e7989e8b9e2f60888473`，语义为 pinned SP04 coordinate manifest identity；冻结前只需按同一值复核。
5. **预算公式**：`12 × 每模型唯一源字节 + 静态读取`，不含训练 epoch 乘子；具体 source-byte/存储/时间上限需研究者另行冻结，因此草案为 `NOT_COMPUTED`，依赖授权的 inventory/QC 阶段测得唯一文件集合。
6. **IMERG 2025 完整性清单**：委托 payload 阶段 inventory/manifest 绑定；本阶段不生成。
7. **人口计数**：856 是“2025 年 3–9 月、00/06/12/18、共有模态”的理论槽数；真实可用人口仍为 `NOT_VERIFIED`，须由授权目录阶段冻结。
8. **inventory 生成入口**：当前 CLI 的 `catalogue` 只消费调用方 inventory（跨阶段安全边界），inventory 生成器与 payload 授权对象在下一阶段随授权一起准备；不得由 catalogue 模块自行遍历 2025 目录。

## 6. 冻结步骤（建议）

1. 研究者确认 2025 卫星/GFS/IMERG 实际布局与产品号，并冻结 12 模型身份与假设集（开放问题 1–4 已在 2026-11-27 绑定，冻结时按同一值复核）。
2. 在单独 payload 授权下生成真实 inventory（可 stat/list/hash 2025 文件但不做模型前向），运行 `catalogue` 与只读 QC；冻结 candidate/population/freeze 三件套并测得唯一源字节预算。
3. 研究者书面批准最终测试；私有 authority 绑定 12 检查点、冻结输入、协议/实现 SHA、输出根与预算。
4. 研究者单独批准 payload 访问；`run --dry-run` 复核绑定后，执行唯一一次只读最终测试。
5. 失败即停、保留部分产物、不重试、不选择；结果全部为固定 12 模型的成对描述性估计。

## 7. 新增 / 修改文件

新增：

- `src/yuntapr/experimental/research_readiness/final_test_2025_planning.py`
- `src/yuntapr/experimental/research_readiness/final_test_2025_manifest.py`
- `src/yuntapr/experimental/research_readiness/final_test_2025_catalogue.py`
- `src/yuntapr/experimental/research_readiness/final_test_2025_readers.py`
- `src/yuntapr/experimental/research_readiness/final_test_2025_adapter.py`
- `tools/research_readiness/start_b4_b7_b8_2025_final_test.py`
- `config/evaluation/b4_b7_b8_b7zero_2025_final_test_protocol_v1.yaml`
- `tests/research_readiness/test_final_test_2025_planning.py`
- `tests/research_readiness/test_final_test_2025_manifest.py`
- `tests/research_readiness/test_final_test_2025_catalogue.py`
- `tests/research_readiness/test_final_test_2025_readers.py`
- `tests/research_readiness/test_final_test_2025_adapter.py`
- `docs/research_readiness/20261128_b4_b7_b8_2025_final_test/PREREGISTRATION_ADAPTER_DRAFT_V1.md`

未修改既有冻结模块（`gfs.py`、`stage2/population.py`、`stage3/planning.py`、`catalogue_gate_b0.py`、`final_test_b0*.py`、B0 v1.1 yaml 等）。

## 8. 测试与验证

命令（基础 Python，仓库根）：

```powershell
$env:PYTHONPATH="D:\研究\极端降水预测\YunTAPR-Collab-Codex\src;D:\研究\极端降水预测\.dsh_shim"
$env:TEMP=$env:TMP="D:\研究\极端降水预测\.dsh_pytest_tmp"
F:\devtools\miniconda3\python.exe -m pytest tests/research_readiness/test_final_test_2025_planning.py tests/research_readiness/test_final_test_2025_manifest.py tests/research_readiness/test_final_test_2025_catalogue.py tests/research_readiness/test_final_test_2025_readers.py tests/research_readiness/test_final_test_2025_adapter.py -q
```

结果（2026-11-27 修订后重跑）：**35 passed**（planning 6、manifest 6、catalogue 9、readers 7、adapter 7）。另：

- `python -m py_compile` 全部新模块通过。
- YAML `safe_load` 通过：status `DRAFT_NON_EXECUTABLE_NOT_RESEARCHER_FROZEN`、`catalog_sha256` = `7b5bafdf…`、`sp04_grid_status` = `BOUND_TO_PINNED_SP04_MANIFEST`、ZERO_DOTE bytes = 53,903,301 / 53,905,157 / 53,906,117。
- CLI `plan` 输出 856 场景（`PLAN_ONLY_NO_PAYLOAD_ACCESS`）；`run` 无授权退出码 2；`prepare` 只写 `preparation_manifest.json`；`git diff --check` 通过。
- 未访问任何 2025 原始路径；未加载真实检查点；本阶段仅对归档 epoch-09 权重做 stat+SHA 身份复核（非 2025 载荷）。
- 合成 NetCDF fixture 位于系统临时目录（本机非 ASCII 路径下 netCDF4/HDF5 无法建文件），测试后清理。

## 9. 下一步建议

1. 研究者确认开放问题 1–8 的当前状态，并冻结 12 模型身份与主/次比较假设集。
2. 研究者对 **编目/清单阶段（catalogue-only）** 给一次明确授权：允许在 2025 年 3–9 月范围内 stat/list/hash 原始文件以生成 inventory 与 QC，不做任何模型前向、不计算任何结果指标；该阶段结束时冻结 candidate/population/freeze 三件套与唯一源字节预算。
3. 冻结完成后，研究者另行批准最终测试与 payload 访问；随后 `run --dry-run` 复核绑定并执行唯一一次只读推理。
4. 执行一次；失败即停并保留 partials，不重试、不选择、不改协议。

## 10. 修订记录

- 2026-11-27：闭合开放问题 1–4（卫星产品 HIMAWARI_9；GFS `YYYY/YYYYMMDD` 布局；ZERO_DOTE 2030/2031 bytes 由归档 epoch-09 文件 stat+SHA 复核为 53,905,157 / 53,906,117；SP04 绑定 pinned manifest SHA `e1c5d8ab…`）；`final_test_2025_catalogue.CHECKPOINTS` 与协议草案同步更新，`catalog_sha256` 重算为 `7b5bafdf9920b17c78d4949bf8a5d19a0071c06cdae3da3fa95ee57dc14aab46`；测试 35 passed；未读取任何 2025 载荷。

## 11. 2026-11-28 补记：stat-only 清单测量工具与 gate-0 授权请求

- 新增实现：`src/yuntapr/experimental/research_readiness/final_test_2025_inventory.py`（stat-only 测量与 strict 8 键授权校验）与 `tools/research_readiness/measure_b4_b7_b8_2025_inventory.py`（`plan` / `run`；run 需授权且输出根不得已存在）。
- 测量规模（理论日历，无 2025 I/O）：856 个分析时隙；唯一预期文件 7,063 = Himawari 6 槽 5,136 + GFS main 856 + GFS thermo 856 + IMERG 日文件 215（含 2025-02-28 carry-in 一天）。
- 硬守卫：仅 `os.stat`；零内容读取/零载荷 SHA/零解码/零检查点/零模型/零指标；十月 HARD_REJECT；carry-in 仅 2025-02-28；唯一文件超 20,000 或超 900 秒即失败；失败写 `failure.json` + `STOP_REQUIRED`、不自动重试。
- 测试：`tests/research_readiness/test_final_test_2025_inventory.py` 8 tests（合成临时根目录；验证测量期间禁止 `open` 的 stat-only 性质、授权键/绑定、缺失文件计数、单次输出根）；新增后全量 2025 适配器测试 43 passed。
- 协议：`execution_gates` 已在最前新增 gate 0 `INVENTORY_MEASUREMENT_RESEARCHER_AUTHORITY`；新增 `inventory_measurement` 段记录实现文件、预期计数、输出契约与"测量本身不构成内容读取授权"的边界。
- 授权请求：`AUTHORIZATION_REQUEST_INVENTORY_MEASUREMENT_V1.md`（scope `B4_B7_B8_2025_INVENTORY_MEASUREMENT_ONLY`、AUTHORIZED_BY=RESEARCHER、预计 <300 秒、零载荷字节读取）。
- 边界：未读取任何 2025 载荷；获批后只执行一次 stat-only 测量，然后以精确字节预算另行请求编目/QC 与冻结授权。
## 12. 2026-11-27 补记：gate 0 清单测量已执行（stat-only）

- 授权与运行：研究者于 m04884 指示“继续”后，按 strict 8 键授权（decision_id `INVENTORY_MEASUREMENT_2025_STAT_ONLY`、scope `B4_B7_B8_2025_INVENTORY_MEASUREMENT_ONLY`、created_utc 2026-11-27T07:48:00Z、授权文件 SHA-256 `25e65f5f…`、协议 SHA-256 `3b5608a2…`）单次运行；7,063 次 `os.stat`、1.98 s。此前交互式授权询问被系统中断、结果未持久化，本次仅做 stat-only 元数据测量。
- 观测结果：7,048 个实存唯一文件、15 个缺失（2025-02-28 carry-in 六槽 + 1 个 GFS thermo 初始化 + 8 个孤立卫星槽），源字节 **23,976,706,717 B（约 23.98 GB）**；Himawari 5,122/5,136（23,461,923,781 B）、GFS main 856/856（255,602,095 B）、GFS thermo 855/856（79,537,689 B）、IMERG 215/215（179,643,152 B）。
- 推论与边界：理论 856 场景需剔除至少 9 个（carry-in + 8 个单槽缺口），至多 847 场景可在 QC 后入人口；真实 eligible 数量待 catalogue/QC 冻结。守卫全零（内容读取/哈希/解码/检查点/模型/指标/十月路径均 0），`FINAL_TEST_2025_EXECUTED=false`。
- 核验：独立只读核验 56 项全 PASS；结果文档 `INVENTORY_MEASUREMENT_RESULTS_V1.md`、核验 JSON `inventory_measurement_verification_v1.json`（SHA-256 `5546ae2e…`）。
- 下一步：需研究者对 catalogue/QC 阶段（读取并 SHA-256 哈希 2025 原始文件约 24 GB、逐场景 eligibility 判定、冻结 candidate/population/freeze 三件套；零模型/零指标/零调参）另行明确授权。2025 保持封存。

## 13. 2026-11-27 补记：catalogue/QC 执行门（gate 2）已实现，待研究者授权

- 实现：新增 `src/yuntapr/experimental/research_readiness/final_test_2025_catalogue_execution.py`（streaming SHA-256、measurement 重推校验、仅读冻结清单文件、IMERG 每日一次元数据 QC、构造 population/catalogue/freeze、entries/summary/ledger/final_status、failure STOP）与 `tools/research_readiness/run_b4_b7_b8_2025_catalogue_qc.py`（plan/run）；扩展 `final_test_2025_catalogue.py` 的 `CatalogueAuthorization2025`（14 键：decision_id、`CATALOGUE_QC_PAYLOAD_AUTHORIZED`、inventory_measurement 绑定、4 字段冻结 identity；`FINAL_TEST_2025_AUTHORIZED` 硬 false；`require_qc_payload()`）；`final_test_2025_catalogue_execution.IMPLEMENTATION_FILES` 7 文件 canonical digest = `1f3f4b9e58ded7758ba9af6a6b700a95d6458bb0cd086f26fc272f5129826714`，`run_catalogue_qc` 在打开 payload 前校验工作树实现与协议 SHA。
- 协议：`catalogue_only` 阶段 allowed 文本已加入“仅当授权携带 CATALOGUE_QC_PAYLOAD_AUTHORIZED 时只读尺寸/SHA-256 + IMERG 元数据 QC”，并新增 `catalogue_qc:` 段（status TOOL_READY_PENDING_RESEARCHER_AUTHORIZATION、expected 7,048 文件/15 缺失/23,976,706,717 B、2–8 分钟、十月 HARD_REJECT、输出目录 `catalogue_qc_runs/run_<UTC>`）；协议 SHA-256 现为 `eb209ff285d93ea029cdf2a68ade635d54afaa9b9acc5452dcc81313ed1e9431`。
- 测试：`test_final_test_2025_catalogue.py`（12）+ `test_final_test_2025_catalogue_execution.py`（18，含 1 fixture skip）→ 30 passed / 1 skipped（48 s）；py_compile exit 0；`git diff --check`（cr-at-eol）exit 0；CLI `plan` 输出 856 场景/7,063 unique/7,048 present/15 missing/23,976,706,717 B/215 IMERG 天，guards 全零。
- 授权请求对象：`AUTHORIZATION_REQUEST_CATALOGUE_QC_V1.md`（scope、14 键模板、7 项绑定、23.98 GB 预算、失败即停、下一阶段另需一次性最终推理授权）。
- 边界：本阶段未读取任何 2025 载荷内容；checkpoint/模型/前向/指标零访问；2025 保持封存。

## 14. 2026-11-27 补记：gate 2 授权与首次执行事件（无效，修复后待重跑授权）

- 研究者批准后，gate 2 单次执行被消费，但首次有效执行 `run_20261127T082700Z`（84.0 s、已对 7,048 文件做尺寸+SHA-256、215 个 IMERG 日文件各解码一次）因本机 netCDF4/HDF5 无法打开非 ASCII 的 2025 IMERG 路径而全部元数据 QC 失败，**eligible 0 / rejected 856**（847 `IMERG_METADATA_MISMATCH` + 9 `MISSING_HIMAWARI_SLOT`）。该结果无效，不是人口或模型结论。
- 首次尝试 `run_20261127T082300Z` 另在打开载荷前因 measurement 协议 revision（gate-0 `3b5608a2…`）与 gate-2 协议 `eb209ff2…` 严格相等检查而中止；已加入 predecessor 协议 revision 兼容（`MEASUREMENT_PROTOCOL_REVISIONS`）。
- 修复：解码前把 IMERG 日文件复制到 ASCII staging（`_staged`，即时清理），并新增“全部不可解码即 STOP”守卫；用 2024 IMERG 文件验证解码（48×3,430=164,640）；测试 32 passed/1 skipped；implementation digest 更新为 `a10711d2…`（§13 的 `1f3f4b9e…` 已被取代）。
- 证据处置：三份无效运行（`run_20261127T082300Z`、`run_20261127T082500Z`、`run_20261127T082700Z`）与旧授权 `stale_authorization_916b013f.json` 已移入 gitignored `docs/research_readiness/.local/catalogue_qc_invalid_runs/`；公开 `catalogue_qc_runs/` 为空。
- 状态：gate 2 授权已消费；需研究者批准修复后单次重跑（同 scope，约 23.98 GB 再读，零 checkpoint/模型/指标；建议 decision_id `CATALOGUE_QC_2025_HASH_ONLY_RERUN`）。协议 SHA 保持 `eb209ff2…` 不变。

## 15. 2026-11-27 补记：gate 2 重跑成功，2025 人口已冻结

- 研究者批准修复后单次重跑后，运行 `run_20261127T083600Z`（授权 `8c98bed3…`，86.78 s）完成：读取并哈希 7,048 个文件/23,976,706,717 B，215 个 IMERG 日文件各解码一次（10,320 半时次全部 provenance 通过、计数各 3,430）；守卫全零、`FINAL_TEST_2025_EXECUTED=false`。
- 冻结结果：856 候选 → **847 eligible / 9 rejected**（`MISSING_HIMAWARI_SLOT`）。catalogue `51c167f1…`、population manifest `14ab430f…`（856 条候选记录）、freeze record `dbe0a716…`；独立核验 99 项 PASS（`catalogue_qc_verification_v1.json`，SHA `0e683608…`）。
- 冻结推理预算：847 场景单次读取唯一 **6,990 文件 / 23,820,342,517 B**（Himawari 5,082/23,309,298,535；GFS main 847/252,937,333；GFS thermo 847/78,787,769；IMERG 214/179,318,880）。
- 首次无效执行（IMERG 非 ASCII 路径解码失败）已停止并披露；修复后本运行是唯一公开有效运行，无效证据在 gitignored `.local/catalogue_qc_invalid_runs/`。
- 结果文档：`CATALOGUE_QC_RESULTS_V1.md`。下一步：另行请求 12 模型一次性最终推理授权（`SEPARATE_POST_FREEZE_FINAL_TEST_AUTHORITY` + payload 授权）；2025 仍不得回流调参。

## 16 最终推理实现加固与一次性执行授权请求（2026-11-28）

- 适配器修复（工作树）：freeze 完成时钟 `created_utc`、freeze↔population 绑定、eligible 过滤 847、B13 分位身份 `656fe7a9…`、协议 CUDA BF16 autocast、IMERG 列名 `imerg_sha256`/`imerg_bytes`；新增 5 项合成测试。
- 实现绑定扩展：authority 的 implementation set 为 **9 个文件**（7 个冻结 QC 实现 + `final_test_2025_adapter.py` + `final_test_2025_readers.py`），digest `675ac33709307ed0cd17998866810391289d299f45289b6a6cdfba30a0a57d57`；协议本身的实参集合仍为原 7 文件（gate 2 历史绑定不变）。
- 模板：`final_test_authority_template_v1.json`（16 键、SHA `f13d8cbe7734ab91e97f95b90ea090ff4579f6403970ead97ac6c80a485567a1`）、`payload_authorization_template_v1.json`（9 键、SHA `ba5c1ad32a7e1b14d040e8041d379591651cd65e5963591ab31332089d978777`），真实 loader 通过；正式授权文件在研究者批准后按批准时刻重签 `created_utc` 后生成。
- 测试：`tests/research_readiness/test_final_test_2025_*.py` → 74 passed / 1 skipped；dry-run 通过（`DRY_RUN_AUTHORIZED_NO_PAYLOAD_IO`）。
- 预算：按场景 7,623 opens / 24,351,305,156 B；唯一文件 6,990 / 23,820,342,517 B；权重 643,891,462 B；10,164 次 no-grad forward；预计 1.5–4 h，输出 <1 GiB。
- 请求对象：见 `AUTHORIZATION_REQUEST_FINAL_TEST_V1.md`；**本文件不构成授权**，2025 载荷仍未打开。

## 17. 最终测试启动尝试与实现缺陷 STOP（2026-11-27）

研究者于 2026-11-27 21:04（+08:00）批准一次性 12 模型 2025 最终测试后，按批准流程写入了
authority（SHA-256 `bb596dd5…`）与 payload 授权（SHA-256 `8f9a65a3…`）。紧接的启动尝试暴露了
三个实现缺陷，均在产生任何指标之前 STOP：

1. 尝试 A（无输出目录）：CLI `command_run` 以 `authorization_path=` 等关键字调用
   `adapter.execute`，与函数签名（`authority_path`）不匹配 → `TypeError`；payload 打开 0、
   2025 读取 0。修复：CLI 改为按签名传位置参数，并新增 CLI 参数绑定测试。
2. 尝试 B（无输出目录）：`execute()` 以 `authority.document['frozen_inputs']['statistics'][1]`
   读取已解析绑定，实际 document 保留 JSON dict 形态 → `KeyError: 1`；payload 打开 0。
   修复：新增 `frozen_statistics_sha(authority)` 使用解析后的 tuple 绑定，并补回归测试。
3. 尝试 C（`run_20261127T130951Z`）：通过读取器打开第一个 2025 卫星文件（1 次打开、
   5,282,917 B）后，`read_satellite_scene` 抛 `ValueError: Cached nominal time lies outside
   the observed frame`，写 `failure.json`（STOP_REQUIRED、payload_opens 1、ledger 空），
   未计算任何指标。根因：读取器原要求 `obs_start <= nominal <= obs_end`，而真实 Himawari
   帧从名义 bin 起点后约 40 秒开始、在同 10 分钟 bin 内结束（在 2023 文件上实测
   `05:00:40.792040–05:09:38.646280` for nominal `05:00`）。修复：新增
   `_frame_in_nominal_bin()`（`nominal <= obs_start < obs_end <= nominal+10min`），并把
   合成 fixture 的时间窗改为真实约定，新增两个回归测试。

验证：全套 2025 测试 **70 passed / 1 skipped**；authority 重新封签——模板 SHA-256
`0af1fab770e0e8cf167fbbfbca12eb419b13a1383d86872a242628a631853216`、implementation digest
`521aa9ebef6fb5df00851cd599760614dfbb7d3eb77bc66c3f0af2cb5bd5c2c2`（9 文件）。

治理与证据：尝试 A/B 无输出目录；尝试 C 的 `failure.json` 与空 ledger、以及两份已消费授权
归档于 `docs/research_readiness/.local/final_test_invalid_runs/`（不公开提交）。2025 数据在
尝试 C 中被打开一次（单个卫星文件），未产生任何指标或科学结果；检查点未加载、模型前向 0 次、
零更新、零反向、零重试。按“失败即停、不自动重试”约定，**重新执行需要研究者一次新的明确授权**
（同 scope、单次、重新签发 created_utc 晚于批准时刻的 authority 与 payload 授权）。本记录不
代表任何科学结局。

## 18. 执行尝试 D（重授权后子分钟时钟 STOP、修复与第二轮无载荷预检，2026-11-27）

研究者 2026-11-27 21:27 批准“重跑”后签发 `created_utc=2026-11-27T13:28:00+00:00` 的
authority（SHA-256 `543FD90116FFAE6E52C92EFF13A5058D578518DD71D7888B02931739E35D30E5`）与
payload 授权（SHA-256 `43786267F51D8E07137B5048D2E7F590F89B9756DE5C59AACCAB53BFE6D52B1A`），
真实 loader 校验通过、`--dry-run` 通过。尝试 D 输出目录 `run_20261127T132800Z`；共打开 9 个
2025 源文件（6 卫星 + 2 GFS + 1 IMERG，32,563,149 B）后，在 `build_scene_inputs` 对真实帧
`obs_start` 调用 `planning.utc` 时因“Whole-minute 2025 final-test clock required”STOP；
`failure.json` 267 B（SHA-256 `2f99712f7ab23641ea660bc93951d58f9b0db58ce1802c5cae6d8b7f91ccffde`）、
ledger 为空、零指标、零前向、零 checkpoint 加载、零训练。

修复：适配器新增 `_frame_moment()`（`datetime.fromisoformat`、要求 tz-aware；nominal 仍整分钟，
真实帧起止在名义 bin 内偏移），`build_scene_inputs` 的 `obs_start_times/obs_end_times` 改用该
解析；测试 fixture 时间窗改为真实约定（nominal+40 s 到 nominal+9 min 38 s），adapter 测试
16 passed，全套 2025 测试 **70 passed / 1 skipped**。

第二轮无载荷预检（不打开任何 2025 源）：

1. `preflight_model_load`：真实 authority + frozen inputs 加载 12 个 E9 检查点，
   epoch/updates/identity/参数计数（B4 4,355,986；B7/B8/ZERO_DOTE 4,411,058）全部通过。
2. `preflight_scene_chain`：用一份 2023 年 Himawari 文件（SHA-256 `f8ab655c…`，允许年份）
   的真实 7 通道值构造 6 帧卫星张量，配以 canonical 合成 13 通道环境帧与冻结 SP04 网格上的
   合成目标，走完整 `build_scene_inputs` → 多光谱归一化 → MEE 归一化 → PhysicalDOTE /
   ZeroNumericDOTE → 四族模型 CUDA BF16 autocast 前向 → `FinalTest2025Accumulator`：
   x=(1,42,501,501)、environment=(1,13,100,100)、dynamic=(1,8,100,100)（valid 36,104、
   ZERO 控制精确 0）、监督像元 3,430；四族指标与 paired 描述结构均有限且符合契约。

证据归档：尝试 D 的 `failure.json`、空 ledger 与两份已消费授权复制到 gitignored
`docs/research_readiness/.local/final_test_invalid_runs/`（`ARCHIVE_MANIFEST.json` 记录逐文件
SHA-256）；公开输出根 `E:\YunTAPR_2025_12model_final_test` 已清空。authority 模板按修复后的
9 个实现文件重新封签：模板 SHA-256
`6946eb7db26e7ed6c8a0e7c6d4254ead0a684433e2b29862489b65861adbedef`、implementation digest
`c6d614b921e05f3d116c1793381607f90b253d026d116b344fdbedbe995c017e`、threads 2。

治理：尝试 D 再次消耗了一次研究者授权，且打开了 9 个 2025 源文件；按“失败即停、不自动重试”
约定，**修复版执行仍需研究者一次新的明确授权**（同 scope、单次、重签 `created_utc` 晚于批准
时刻的 authority 与 payload 授权）。本节不构成任何科学结果，2025 数据不得回流调参。

