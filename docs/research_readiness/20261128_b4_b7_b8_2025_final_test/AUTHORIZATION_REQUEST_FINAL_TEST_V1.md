# 一次性 12 模型 2025 最终测试 · 研究者授权请求（V1）

- 日期：2026-11-28（Asia/Shanghai）
- 状态：`READY_WAITING_EXACT_RESEARCHER_AUTHORIZATION`（本文件不构成授权；未打开任何 2025 载荷）
- 决策标识：authority `FINAL_TEST_2025_12MODEL_ONESHOT`；payload `FINAL_TEST_2025_12MODEL_PAYLOAD_ONESHOT`

## 1. 请求事项

请求研究者一次性批准以下两件事，二者共同构成冻结后最终测试所需的全部授权：

1. **执行授权**：以冻结协议 `config/evaluation/b4_b7_b8_b7zero_2025_final_test_protocol_v1.yaml`（SHA-256 `eb209ff2…`）执行一次 12 模型 2025 最终推理（`B4_B7_B8_2025_FINAL_TEST_ONLY`）。
2. **载荷授权**：允许该次执行只读打开 catalogue/QC 已冻结并声明 SHA 的 2025 文件（Himawari 六槽、GFS main/thermo、IMERG 日文件），且仅限 847 个 eligible 场景。

批准后将会（且只会）发生一次只读推理：12 个冻结 E9 检查点 × 847 场景、无梯度、无训练、无参数更新、无模型/epoch 选择、无后处理校准、无重试；失败即 `STOP_REQUIRED` 并保留部分结果与 `failure.json`。

## 2. 冻结绑定（全部已核验）

| 对象 | SHA-256 / 数值 |
|---|---|
| 协议 | `eb209ff2…`（五阶段 gate，最终阶段 `FINAL_READ_ONLY_INFERENCE`） |
| 实现（authority 绑定 9 文件） | digest `675ac33709307ed0cd17998866810391289d299f45289b6a6cdfba30a0a57d57` |
| catalogue CSV | `51c167f19aa8bec887f0d6c1711492a70da86abe96ba05153fea0efd14102b25` |
| population manifest | `14ab430f1057d1bfc1eb01637a5c9cc99f0bb373f8627bd74fd3b48964385ece` |
| freeze record | `dbe0a716d7afc4bfac4b3c45e039229cb3e3896642e01457dc03679aa4c4ebf0`（`CATALOGUE_FROZEN`，856 候选 → 847 eligible / 9 rejected） |
| 2023 Train 统计件 | `53ab2f07…`（`fit_role=Train`、`fit_years=[2023]`、`ddof=0`、`B13_refitted=false`） |
| B6 static pack | `788572b1…`（312,828 B） |
| static production receipt | `180599379509dd5a49639feb1df9ca22ed97afd34d8e4d021c6eb4a24a0cd32d` |
| frozen Yunnan mask | `9d921def…`（20,916 B，3430 像元） |
| SP04 grid | `e1c5d8ab…` |
| B13 normalization | `656fe7a9…` |
| 检查点 | 12 个 E9 文件，逐文件 SHA/bytes 已核验，合计 **643,891,462 B** |

其中 6 个检查点位于 `F:\pytorch\Research\...`，B4/2029 位于 `D:\研究\极端降水预测\YunTAPR-seed2029-recovery-20261024\...`（D: 为 junction，运行期必须可访问）；全部为公开目录下的归档文件，非 2025 载荷。

## 3. 授权模板（待研究者批准后按批准时刻重签 `created_utc`）

- `final_test_authority_template_v1.json`：16 键有序（version / AUTHORIZED_BY / scope / FINAL_TEST_2025_AUTHORIZED / FINAL_TEST_2025_EXECUTED / protocol / implementation / catalogue / population / freeze / checkpoints / frozen_inputs / dote / inference / output_root / created_utc），文件 SHA-256 `f13d8cbe7734ab91e97f95b90ea090ff4579f6403970ead97ac6c80a485567a1`；`FinalTest2025Authority.load` + `require_final()` 已通过。
- `payload_authorization_template_v1.json`：9 键（version / AUTHORIZED_BY / scope / FINAL_TEST_2025_PAYLOAD_AUTHORIZED / protocol / catalogue_sha256 / roots / allow_october / created_utc），文件 SHA-256 `ba5c1ad32a7e1b14d040e8041d379591651cd65e5963591ab31332089d978777`；`PayloadAuthorization2025.researcher` 校验通过；`allow_october=false`。
- 冻结字段（scope、implementation、catalogue/population/freeze、checkpoints、frozen_inputs、dote、inference、output_root）在重签时逐字节保持不变；仅 `created_utc` 改为批准时刻的整分钟 UTC，且必须晚于 freeze record 的 `created_utc`（`2026-11-27T08:38:11.452234+00:00`）。
- 重签后将生成正式文件 `config/evaluation/b4_b7_b8_2025_final_test_authorization_v1.json` 与 `config/evaluation/b4_b7_b8_2025_final_test_payload_authorization_v1.json`，并在运行前用真实 loader 复核。

## 4. 预算（冻结后精确核算）

- 按场景读取（`PayloadAccess2025` 逐次调用计数，IMERG 日文件在相邻场景中被复用但重复计量）：**7,623 文件 / 24,351,305,156 B**。
- 唯一文件集：6,990 文件 / 23,820,342,517 B（Himawari 5,082 / 23,309,298,535；GFS main 847 / 252,937,333；GFS thermo 847 / 78,787,769；IMERG 214 / 179,318,880）。
- 检查点权重：643,891,462 B（12 个文件，各只 torch.load 一次）。
- 前向：847 场景 × 12 模型 = 10,164 次 no-grad forward（batch=1，BF16 CUDA autocast，FP32 参数，FP64 分位/覆盖/指标）。
- 预计墙钟：约 1.5–4 小时（源自 gate 2 实测 276 MB/s 的顺序读取 + RTX 5060 Laptop 8 GB 上的 10,164 次小批量前向；非承诺值，失败即停）。
- 输出：`E:\YunTAPR_2025_12model_final_test\` 新建唯一子目录，写入 12 个 `metrics/<model>_<seed>.json`、`comparisons.json`、`run_manifest.json`、`runtime_ledger.jsonl`（847 行）与 `final_status.json`，总量 <1 GiB。

## 5. 禁止与保证（由实现和授权 schema 双重约束）

零训练 / 零反向 / 零优化器 / 零参数更新；零模型、epoch、检查点、阈值或校准选择；不得读取 2025 年十月数据；不得对 2025 结果做后验调参、选择或再训练；不得重跑或静默替换失败；不删除原始数据、不覆盖历史权重与既有证据。审计字段 `MODEL_PARAMETERS_UPDATED=false`、`OPTIMIZER_STEPS=0`、`BACKWARD_CALLS=0`、`SELECTION=FINAL_ONLY_NO_SELECTION` 将写入 run manifest 与 final status。

## 6. 已完成的准备与验证

- 适配器缺陷修复并测试：freeze 时钟改读 `created_utc`；删除错误的 2023/2024 population 比对，改为 freeze↔population 绑定；按 catalogue 布尔 eligible 过滤为 847；B13 分位身份按冻结统计件的 `656fe7a9…` 解释；协议 CUDA BF16 autocast 已接入前向；`_expected_from_catalogue` 的 IMERG 列名改为真实 `imerg_sha256`/`imerg_bytes`。
- 测试：`tests/research_readiness/test_final_test_2025_*.py` → **74 passed / 1 skipped**；py_compile、`git -c core.whitespace=cr-at-eol diff --check` 通过。
- dry-run（真实 authority + payload 模板，`--dry-run`）：`DRY_RUN_AUTHORIZED_NO_PAYLOAD_IO`、`payload_access=NOT_REQUESTED_NOT_OPENED`、`checkpoint_bytes_total=643,891,462`、`output_root=E:\YunTAPR_2025_12model_final_test`、inference（device=cuda, seed=2026, threads=2, scenes_per_batch=1）。
- 输出根 `E:\YunTAPR_2025_12model_final_test` 为空目录，E: 可用 79.98 GiB；GPU RTX 5060 Laptop 8,151 MiB 总显存。

## 7. 风险与披露

1. 12 个检查点合计约 0.64 GB；单次顺序加载需约 8 GB 级 GPU 显存余量，实际由 `scenes_per_batch=1` 控制。
2. B4/2029 检查点位于 D: junction 路径，若运行期 junction 失效会立即 STOP（不重试）。
3. 估计时长非承诺值；失败保留部分 ledger 与 failure.json。
4. 本阶段不产生新的训练证据；结果只能作为冻结模型的 2025 留出评价，不得回流调参或选择。
5. 本请求文件与两份模板均不在 REPO 实现绑定内，但模板 SHA 已在发送前记录；正式授权文件在批准后生成。

## 8. 请求的明确回复

请研究者明确批准：**“批准执行 12 模型 2025 一次性最终测试（B4_B7_B8_2025_FINAL_TEST_ONLY + 载荷授权）”**。批准后按上述流程单次执行并将证据（运行目录、metrics、comparison、manifest、final status、独立核验）落档、提交推送与 Obsidian 同步；不重复申请、不重跑。

## 9. 重新授权请求（实现缺陷修复后，2026-11-27）

上一份授权被三次启动尝试消耗：前两次在打开任何 payload 之前即因参数/绑定缺陷 STOP；第三次
打开 1 个 2025 卫星文件后因帧时间窗校验缺陷 STOP（无指标）。缺陷已修复、全套 2025 测试
70 passed / 1 skipped、authority 已重新封签（模板 `0af1fab7…`、implementation digest
`521aa9eb…`）。失败证据归档于 `docs/research_readiness/.local/final_test_invalid_runs/`。

现请求研究者对**修复后的单次执行**再给一次明确授权：

- scope：`B4_B7_B8_2025_FINAL_TEST_ONLY`（payload scope 同前）
- 模型/人口/预算不变：12 个 E9 检查点、847 eligible 场景、按场景读取 7,623 次 /
  24,351,305,156 B、唯一文件集 6,990 文件
- 零训练、零调参、零选择、零重试；失败即停并保留 `failure.json`
- 获批后：签发 `created_utc` 晚于批准时刻的 authority/payload 授权 → 单次运行 → 独立核验 →
  提交推送并汇报主比较（B7_REAL−B7_ZERO_DOTE；Brier + conditional Pinball）

回复“批准重跑（推荐）”即视为一次明确授权；回复停止则不再执行。

## 10. 最后一次重授权请求（尝试 D 之后，2026-11-27）

研究者上一次“批准重跑”对应的尝试 D 在打开 9 个 2025 源文件（32,563,149 B）后因真实卫星帧
子分钟时间戳与 `planning.utc` 整分钟约束冲突 STOP（无指标、无前向）。该缺陷已修复并通过
test fixture 更新（adapter 16 passed、全套 2025 测试 70 passed / 1 skipped）。

为降低再次启动的工程风险，另完成两项**无 2025 载荷**预检：12 个检查点全部加载并通过参数
计数；用 2023 年真实卫星波段值加 canonical 合成环境/目标，走通完整场景构建、DOTE、四族
CUDA BF16 前向与指标累积（无任何 2025 源打开）。

现请求研究者对修复版**最后一次单次执行**给一次明确授权：

- scope：`B4_B7_B8_2025_FINAL_TEST_ONLY`（payload scope 同前）
- 冻结绑定：authority 模板 SHA-256
  `6946eb7db26e7ed6c8a0e7c6d4254ead0a684433e2b29862489b65861adbedef`、implementation digest
  `c6d614b921e05f3d116c1793381607f90b253d026d116b344fdbedbe995c017e`（9 文件）
- 模型/人口/预算不变：12 个 E9 检查点、847 eligible 场景、按场景读取 7,623 次 /
  24,351,305,156 B、唯一文件集 6,990 文件 / 23,820,342,517 B、权重 643,891,462 B
- 零训练、零调参、零选择、零重试；失败即停并保留 `failure.json`
- 获批后：签发 `created_utc` 晚于批准时刻的 authority/payload 授权 → 单次运行 → 独立核验 →
  提交推送并汇报主比较（B7_REAL−B7_ZERO_DOTE；Brier + conditional Pinball）

回复“批准重跑（推荐）”即视为一次明确授权；回复停止则不再执行。

