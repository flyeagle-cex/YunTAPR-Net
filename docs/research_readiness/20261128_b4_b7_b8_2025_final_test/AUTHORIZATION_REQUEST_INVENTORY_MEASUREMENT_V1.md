# 2025 十二模型最终测试 · Stat-Only 清单测量授权请求 V1

- 日期：2026-11-28
- 状态：`TOOL_READY_PENDING_RESEARCHER_AUTHORIZATION`
- 协议：`config/evaluation/b4_b7_b8_b7zero_2025_final_test_protocol_v1.yaml`（DRAFT，gate 0 = `INVENTORY_MEASUREMENT_RESEARCHER_AUTHORITY`）
- 实现：`src/yuntapr/experimental/research_readiness/final_test_2025_inventory.py`、`tools/research_readiness/measure_b4_b7_b8_2025_inventory.py`
- 测试：`tests/research_readiness/test_final_test_2025_inventory.py`（8 tests，仅合成临时目录）

## 1. 请求授权的操作

请求研究者对「2025 清单测量」（gate 0）给一次明确授权，唯一允许的操作是：

- 按冻结布局渲染 856 个理论分析时隙的**预期相对路径**；
- 对每个**唯一**预期路径调用 `os.stat`（仅取存在性、文件字节数、mtime）；
- 写出一份只含相对路径/字节数的测量清单与汇总（不写入任何原始载荷）。

实测预期规模：**7,063 次 stat**，其中 Himawari 6 槽 5,136 个唯一文件、GFS main 856、GFS thermo 856、IMERG 日文件 215（含 2025-02-28 carry-in 一天）。

预计用时 < 300 秒（硬上限 900 秒），不读取任何文件内容（读取字节数为 0）。

## 2. 明确禁止的操作

以下操作在本次授权中**全部禁止**，且由代码守卫与测试共同证明：

- 不 `open`/读取/`SHA-256`/解码任何 2025 原始文件内容；
- 不打开 NetCDF 头、不检查变量/网格；
- 不 stat/加载任何检查点，不建立模型、不做前向、不计算任何指标；
- 不列出、不访问 2025 年 10 月路径（HARD_REJECT）；
- 不训练、不调参、不做模型/epoch 选择；
- 不写于输出目录之外的任何位置，不覆盖既有产物。

## 3. 为什么必须单独授权

协议要求：任何 2025 内容读取（哈希、编目 QC、推理）之前，必须先有**精确的唯一文件集与字节预算**，预算必须由研究者冻结。856 只是理论日历数；真实人口、缺失文件与精确字节只能由 stat-only 测量得到。测量是后续「编目/QC 与冻结」授权请求的唯一合法依据。

## 4. 授权对象（获批后写入，strict 8 键）

获批后写 `config/evaluation/b4_b7_b8_2025_inventory_measurement_authorization_v1.json`，恰含：

- `version`: `"v1"`
- `decision_id`: 唯一标识（如 `B4_B7_B8_2025_INVENTORY_MEASUREMENT_20261128`）
- `AUTHORIZED_BY`: `"RESEARCHER"`
- `scope`: `"B4_B7_B8_2025_INVENTORY_MEASUREMENT_ONLY"`
- `INVENTORY_MEASUREMENT_2025_AUTHORIZED`: `true`
- `protocol_sha256`：冻结协议文件的 SHA-256（提交后计算）
- `implementation_sha256`：四个实现文件的逐文件 SHA-256 映射
- `created_utc`：RFC 3339 UTC 时间戳

## 5. 获批后的执行与交付

1. 生成上述授权 JSON（绑定确切协议/实现 SHA）；
2. 在固定实现副本中单次运行 `measure_b4_b7_b8_2025_inventory.py run`，输出到新的追加式目录（计划：`docs/research_readiness/20261128_b4_b7_b8_2025_final_test/inventory_runs/run_<UTC>`）；
3. 独立复核测量结果（重算唯一文件集计数、逐项核对输出哈希、确认 guards 全零）；
4. 提交/推送公开的测量汇总（相对路径与字节数，不含私有运行路径或载荷内容），更新 Obsidian；
5. 带着**精确字节预算**另行请求「编目/QC + 人口冻结」授权（下一阶段），本阶段不读取内容。

## 6. 边界

- 本次授权只覆盖 stat/list；不构成任何 payload 内容读取授权；
- 失败即停，写 `failure.json` 与 `STOP_REQUIRED`，不自动重试，不静默重放；
- 测量结果不改变 2025 数据仅用于一次性最终测试的冻结语义。
