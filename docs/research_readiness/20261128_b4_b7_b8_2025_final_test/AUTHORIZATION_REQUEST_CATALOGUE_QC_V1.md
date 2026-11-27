# B4/B7/B8 × 2029/2030/2031 · 2025 编目与 QC 阶段授权请求 V1

- 日期：2026-11-27（UTC+08:00）
- 状态：`READY_WAITING_EXACT_RESEARCHER_AUTHORIZATION`
- 本文件是阶段 gate 2（`CATALOGUE_ONLY_RESEARCHER_AUTHORITY`）的授权请求对象说明，不是授权本身，也不构成执行许可。
- 协议：`config/evaluation/b4_b7_b8_b7zero_2025_final_test_protocol_v1.yaml`（SHA-256 `eb209ff285d93ea029cdf2a68ade635d54afaa9b9acc5452dcc81313ed1e9431`）
- gate 0 测量：`docs/research_readiness/20261128_b4_b7_b8_2025_final_test/inventory_runs/run_20261127T074800Z/`（inventory `c45b30d1e86d1094c23975592cba6c9cb22a0eeb0b12418ee69cd5dc836055c1`，measurement JSON SHA-256 `4b9113697080f7aed66f22d6981279e02128c420a7e3ac6b43d04c9654186533`，created_utc `2026-11-27T07:48:45+00:00`）

## 1. 请求

研究者以具名授权（`AUTHORIZED_BY: RESEARCHER`，scope `B4_B7_B8_2025_FINAL_TEST_CATALOGUE_ONLY`）批准本阶段一次执行：

1. **只读哈希与尺寸核对**：读取 gate 0 冻结清单中的恰好 7,048 个实存文件（15 个缺失），逐文件 `size` 核对 + 流式 SHA-256（不落盘副本，不重排，不新增文件集合）。
2. **IMERG 元数据 QC**：每个 IMERG 日文件仅解码一次，核对 48 个半小时时次网格、时间 provenance、Yunnan 网格映射与逐场景有效像元计数（48×100×100 裁剪），使用冻结 mask `9d921def…`。
3. **构图与冻结**：按协议 42 列 schema 生成 `b4_b7_b8_2025_candidate_catalogue_v1.csv`、`b4_b7_b8_2025_population_manifest_v1.json`、`b4_b7_b8_2025_catalogue_freeze_record_v1.json`；冻结固定身份（见 §3）与唯一源字节预算。
4. **输出目录**：新的 append-only 运行目录 `docs/research_readiness/20261128_b4_b7_b8_2025_final_test/catalogue_qc_runs/run_<UTC>/`（当前不存在），含 `inventory_qc_entries.json`、`inventory_qc_summary.json`、`runtime_ledger.jsonl`、`final_status.json` 及三件套。

## 2. 明确禁止（越界即失败）

- 不加载任何 checkpoint（12 个 E9 权重零访问）、不构建模型、不做前向/推理。
- 不加载 torch，不计算任何评价指标（Brier/AUROC/AP/pinball/coverage 等），不做任何模型/epoch/阈值选择。
- 不读取 2025 年十月文件，不读取清单以外的任何 2025 路径。
- 不训练、不调参、不改协议、不重试：任何不一致写 `failure.json`（`STOP_REQUIRED`）并保留 partials。
- 本阶段结果不得回流到任何调参/选择；2025 最终测试仍保持未授权。

## 3. 冻结身份与绑定

| 项 | 值 |
|---|---|
| protocol SHA-256 | `eb209ff285d93ea029cdf2a68ade635d54afaa9b9acc5452dcc81313ed1e9431` |
| implementation digest | `1f3f4b9e58ded7758ba9af6a6b700a95d6458bb0cd086f26fc272f5129826714`（7 文件映射，见授权 JSON `implementation.files`） |
| checkpoint catalog SHA-256 | `7b5bafdf9920b17c78d4949bf8a5d19a0071c06cdae3da3fa95ee57dc14aab46` |
| sp04_grid_sha256 | `e1c5d8ab1b58407503db4b56124f4a34a360507280b0e7989e8b9e2f60888473` |
| supervision_mask_sha256 | `70368bec3149e998922d565dab83347ba33f465df481a03ac3f90b85f1286d4b` |
| static_sha256 | `788572b1e82ba388d6ddcd6b1f8a987af818f44cdde9d5d613db5d35af5281bd` |
| train_scalers_sha256 | `53ab2f07aabb02e66ad237452447a35e0e2896278eae9d2da179336c06fea980` |
| inventory_measurement | `path` = 上述 measurement JSON 相对路径；`sha256` = `4b911369…`；`created_utc` = `2026-11-27T07:48:45+00:00` |
| source_roots | `himawari` = `H:\葵花202303_202510`；`imerg` = `F:\云南极端降水数据\raw\IMERG`；`gfs` = `F:\云南极端降水数据\raw\GFS`；`gfs_thermo` = `F:\云南极端降水数据\raw\GFS_THERMO` |

## 4. 预算与耗时

- 预期读取：**23,976,706,717 B（23.98 GB）**（Himawari 23,461,923,781 B + GFS main 255,602,095 B + GFS thermo 79,537,689 B + IMERG 179,643,152 B）。
- 预期写入：三件套 + QC JSON/ledger，量级 <50 MB（以实际运行账本为准）。
- 实测吞吐参考：2023 授权 probe 热缓存 1,381.58 MB/s；CPU SHA 4,538 MB/s；B0 参考 470 MB/s。预计 **2–8 分钟**（热 2–5；冷外置盘 4–6；最坏 ~8），硬上限由实现时长与失败即停保护。
- 预期人口：理论 856 分析时次；剔除非时序缺口的 9 个场景后至多 847 个可能 eligible，真实 eligible 以本阶段冻结为准；15 个缺失路径清单见 gate 0 结果文档。

## 5. 授权 JSON（恰好 14 键；由研究者授权后写入）

```json
{
  "version": "v1",
  "decision_id": "<研究者决定编号，如 CATALOGUE_QC_2025_HASH_ONLY>",
  "AUTHORIZED_BY": "RESEARCHER",
  "scope": "B4_B7_B8_2025_FINAL_TEST_CATALOGUE_ONLY",
  "FINAL_TEST_CATALOGUE_AUTHORIZED": true,
  "FINAL_TEST_2025_AUTHORIZED": false,
  "CATALOGUE_QC_PAYLOAD_AUTHORIZED": true,
  "protocol": {"path": "config/evaluation/b4_b7_b8_b7zero_2025_final_test_protocol_v1.yaml", "sha256": "<§3 protocol>"},
  "implementation": {"sha256": "<§3 implementation>", "files": {<§3 7 文件映射>}},
  "checkpoint_catalog_sha256": "<§3 catalog>",
  "source_roots": {"himawari": "...", "imerg": "...", "gfs": "...", "gfs_thermo": "..."},
  "inventory_measurement": {"path": "<measurement 相对路径>", "sha256": "4b9113697080f7aed66f22d6981279e02128c420a7e3ac6b43d04c9654186533", "created_utc": "2026-11-27T07:48:45+00:00"},
  "identity": {"sp04_grid_sha256": "e1c5d8ab…", "supervision_mask_sha256": "70368bec…", "static_sha256": "788572b1…", "train_scalers_sha256": "53ab2f07…"},
  "created_utc": "<整分钟 UTC，且不早于 inventory created_utc>"
}
```

## 6. 批准后的单次执行

```powershell
$env:PYTHONPATH="D:\研究\极端降水预测\YunTAPR-Collab-Codex\src"
F:\devtools\miniconda3\python.exe tools\research_readiness\run_b4_b7_b8_2025_catalogue_qc.py run `
  --authorization config\evaluation\b4_b7_b8_2025_catalogue_qc_authorization_v1.json `
  --authorization-sha256 <auth-sha256> `
  --inventory-measurement docs\research_readiness\20261128_b4_b7_b8_2025_final_test\inventory_runs\run_20261127T074800Z\inventory_measurement_v1.json `
  --inventory-measurement-sha256 4b9113697080f7aed66f22d6981279e02128c420a7e3ac6b43d04c9654186533 `
  --output-dir docs\research_readiness\20261128_b4_b7_b8_2025_final_test\catalogue_qc_runs\run_<UTC>
```

执行一次后：独立只读核验 → 冻结人口与唯一源字节预算 → 提交/推送 → 另行请求一次性最终推理授权（`SEPARATE_POST_FREEZE_FINAL_TEST_AUTHORITY` + payload 授权）。失败即停，不重试。

## 7. 边界声明

- 截至本文件，2025 原始载荷内容读取为 0（gate 0 仅 `os.stat` 元数据）。
- 本阶段不是最终测试授权，不产生任何 2025 模型指标；`FINAL_TEST_2025_AUTHORIZED` 必须保持 `false`。
- 若本请求被拒绝或需修改范围，须重新提交授权对象，不得以默认值执行。
