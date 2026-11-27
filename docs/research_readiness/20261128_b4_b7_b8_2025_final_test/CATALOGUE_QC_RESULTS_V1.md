# B4/B7/B8 × 2029/2030/2031 · 2025 编目与 QC 结果 V1（gate 2，已冻结）

- 日期：2026-11-27（UTC+08:00）
- 状态：`CATALOGUE_FROZEN`（`FINAL_TEST_2025_AUTHORIZED=false`，最终推理仍未授权）
- 授权：研究者批准单次重跑（decision_id `CATALOGUE_QC_2025_HASH_ONLY_RERUN`，scope `B4_B7_B8_2025_FINAL_TEST_CATALOGUE_ONLY`，`AUTHORIZED_BY=RESEARCHER`）；授权文件 `config/evaluation/b4_b7_b8_2025_catalogue_qc_authorization_v1.json`，SHA-256 `8c98bed3161f33beeeef064b484b0de830c5ca97259f562ef05520ae8afe7a87`（2,726 B）。
- 运行：`docs/research_readiness/20261128_b4_b7_b8_2025_final_test/catalogue_qc_runs/run_20261127T083600Z/`；started `2026-11-27T08:36:44.953002+00:00`，completed `2026-11-27T08:38:11.733066+00:00`，elapsed **86.78 s**；`payload_access = HASH_AND_IMERG_METADATA_ONLY`。

## 1. 读取与 QC（只读）

- 读取 gate 0 冻结清单内 **7,048** 个实存文件、**23,976,706,717 B**，逐文件 size 核对 + 流式 SHA-256（速率 276.3 MB/s）：Himawari 5,122/5,136（23,461,923,781 B，14 缺失）、GFS main 856/856（255,602,095 B）、GFS thermo 855/856（79,537,689 B，1 缺失）、IMERG 215/215（179,643,152 B）。
- 缺失共 15 个：2025-02-28 carry-in 六槽 + 1 个 `2025/20250228/gfs_thermo_0p25_2025022818_f006.nc` + 8 个孤立卫星槽（清单见 `inventory_qc_summary.json`）。
- IMERG 元数据 QC：215 个日文件各解码一次共 10,320 个半时次；全部 `product=GPM_3IMERGHH_07`、`version=V07`、`run_type=Final`、`time_grid_provenance_pass=true`，48 个时次有效 Yunnan 计数各 3,430（每文件 164,640）。
- 守卫全零：checkpoint 哈希/加载/stat、模型构建、前向场景、指标、参数更新、阈值、训练、归一化重拟合均 0；`FINAL_TEST_2025_EXECUTED=false`。

## 2. 冻结结果

- 856 个理论 2025 候选场景 → **eligible 847 / rejected 9**（9 个均为 `MISSING_HIMAWARI_SLOT`：2025-02-28 carry-in 场景 + 8 个孤立单槽场景）。
- 冻结推理人口 = 847 个 catalogue-eligible 场景（population manifest 含 856 条候选记录；最终推理按 catalogue eligible 过滤）。
- 月度候选场景数：3 月 124、4 月 120、5 月 124、6 月 120、7 月 124、8 月 124、9 月 120（含 2025-02-28 23:30 UTC carry-in 窗口）。

## 3. 冻结身份与工件

| 项 | 值 |
|---|---|
| protocol SHA-256 | `eb209ff285d93ea029cdf2a68ade635d54afaa9b9acc5452dcc81313ed1e9431` |
| implementation digest | `a10711d283af1b17d809b67a0252b5c127e28e2b2e9727cd1f0f74875e550547`（7 文件） |
| checkpoint catalog SHA-256 | `7b5bafdf9920b17c78d4949bf8a5d19a0071c06cdae3da3fa95ee57dc14aab46` |
| sp04 / mask / static / train_scalers | `e1c5d8ab…` / `70368bec…` / `788572b1…` / `53ab2f07…` |
| candidate catalogue | `51c167f19aa8bec887f0d6c1711492a70da86abe96ba05153fea0efd14102b25`（1,078,582 B，856 行） |
| population manifest | `14ab430f1057d1bfc1eb01637a5c9cc99f0bb373f8627bd74fd3b48964385ece`（1,188,331 B，856 条候选记录） |
| catalogue freeze record | `dbe0a716d7afc4bfac4b3c45e039229cb3e3896642e01457dc03679aa4c4ebf0`（2,385 B） |
| inventory QC entries / summary / ledger | `3,375,038 B` / `4,019 B` / `1,859,319 B`（7,278 行 = 7,048 hash + 215 decode + 15 missing） |
| 独立核验 | `catalogue_qc_verification_v1.json`，SHA-256 `0e683608d4e72ea4747dd8db0d7cd8ad72c5f458348bebcc0a7e9910878fea49`（4,542 B），**99 项全 PASS** |

## 4. 冻结推理源字节预算（单次读取）

847 个 eligible 场景所需唯一文件 **6,990 个 / 23,820,342,517 B（约 23.82 GB）**：

| 模态 | 文件数 | 字节 |
|---|---:|---:|
| Himawari（6 槽） | 5,082 | 23,309,298,535 |
| GFS main | 847 | 252,937,333 |
| GFS thermo | 847 | 78,787,769 |
| IMERG 日文件 | 214 | 179,318,880 |
| **合计** | **6,990** | **23,820,342,517** |

最终推理实现按“每场景读取一次源、对 12 个 E9 模型各做一次前向”设计，因此单次通过预算即上述 23.82 GB；12 个检查点权重读取另计（每个约 52.9 MB）。

## 5. 首次无效执行（已停止、已披露）

首次获授权执行（`run_20261127T082700Z`）因本机 netCDF4/HDF5 无法打开非 ASCII 的 2025 IMERG 路径，导致全部 IMERG 元数据 QC 失败、0 eligible；该结果无效，不是人口或模型结论。解码器已改为 ASCII staging 并加“全部不可解码即 STOP”守卫，三份无效运行与旧授权移入 gitignored `.local/catalogue_qc_invalid_runs/`；本文件所述运行是唯一公开有效运行。

## 6. 边界与下一步

- 本阶段零 checkpoint、零模型、零前向、零指标、零调参；`FINAL_TEST_2025_EXECUTED=false`。
- 冻结人口与源字节预算仅供一次性 2025 最终推理使用；不得回流调参/选择/校准。
- 下一步：12 个 E9 模型（B4/B7/B8/B7_ZERO_DOTE × 2029/2030/2031）在 847 个冻结场景上的一次性最终推理（主比较 `B7_REAL_MINUS_B7_ZERO_DOTE`，共同主指标 Brier + conditional Pinball），需要研究者一次新的明确授权（`SEPARATE_POST_FREEZE_FINAL_TEST_AUTHORITY` + payload 授权）。
