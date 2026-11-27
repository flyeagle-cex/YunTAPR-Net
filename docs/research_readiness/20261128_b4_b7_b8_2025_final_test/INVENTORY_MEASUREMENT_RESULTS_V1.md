# 12 模型 2025 最终测试 · Gate 0 清单测量结果 v1

- 状态：`MEASURED_STAT_ONLY`；run id `run_20261127T074800Z`；完成于 2026-11-27T07:48:47Z（UTC），耗时 **1.98 s**，`os.stat` 调用 **7,063 次**。
- 授权：decision_id `INVENTORY_MEASUREMENT_2025_STAT_ONLY`、`AUTHORIZED_BY=RESEARCHER`、scope `B4_B7_B8_2025_INVENTORY_MEASUREMENT_ONLY`、created_utc `2026-11-27T07:48:00+00:00`；授权文件 `config/evaluation/b4_b7_b8_2025_inventory_measurement_authorization_v1.json`，SHA-256 `25e65f5ffe14211ae79de2d56b95c29a90ab10ee6543e71ec708bfbf7458d30a`。
- 协议与实现绑定：协议 SHA-256 `3b5608a2b406c927a7d99aba9aace6f782ce1e19478460cb794954c6dc662421`；实现哈希绑定 4 个文件（协议、inventory 模块、planning 模块、CLI），与授权文件逐项一致。
- 授权来源披露：研究者于 m04884 指示“继续”，据此推进本次 **stat-only 元数据测量**；此前交互式授权询问被系统中断、结果未持久化。本阶段未打开、读取、哈希或解码任何 2025 载荷文件，仅做 `os.stat`。
- 守卫（run 内记录，全部为零）：`payload_content_reads=0`、`payload_content_hashes=0`、`payload_files_opened=0`、`checkpoint_stats=0`、`checkpoint_hashes=0`、`checkpoint_loads=0`、`model_builds=0`、`inference_scenes=0`、`metrics_computed=0`、`october_paths=0`、`stat_only=true`。

## 1. 观测结果

| 模态 | 预期唯一文件 | 实存 | 缺失 | 总字节 | 单文件最小 | 单文件最大 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Himawari（6 槽） | 5,136 | 5,122 | 14 | 23,461,923,781 | 2,672,346 | 6,112,392 |
| GFS main f006 | 856 | 856 | 0 | 255,602,095 | 278,828 | 303,789 |
| GFS thermo f006 | 856 | 855 | 1 | 79,537,689 | 88,442 | 96,923 |
| IMERG 日文件 | 215 | 215 | 0 | 179,643,152 | 304,355 | 1,543,497 |
| **合计** | **7,063** | **7,048** | **15** | **23,976,706,717** | — | — |

## 2. 缺失文件（精确清单）

```
himawari  202502/28/NC_H09_20250228_2300_R21_FLDK.06001_06001.nc
himawari  202502/28/NC_H09_20250228_2310_R21_FLDK.06001_06001.nc
himawari  202502/28/NC_H09_20250228_2320_R21_FLDK.06001_06001.nc
himawari  202502/28/NC_H09_20250228_2330_R21_FLDK.06001_06001.nc
himawari  202502/28/NC_H09_20250228_2340_R21_FLDK.06001_06001.nc
himawari  202502/28/NC_H09_20250228_2350_R21_FLDK.06001_06001.nc
himawari  202503/27/NC_H09_20250327_1130_R21_FLDK.06001_06001.nc
himawari  202503/27/NC_H09_20250327_2330_R21_FLDK.06001_06001.nc
himawari  202504/21/NC_H09_20250421_1740_R21_FLDK.06001_06001.nc
himawari  202504/28/NC_H09_20250428_1740_R21_FLDK.06001_06001.nc
himawari  202505/05/NC_H09_20250505_1740_R21_FLDK.06001_06001.nc
himawari  202508/11/NC_H09_20250811_1110_R21_FLDK.06001_06001.nc
himawari  202508/17/NC_H09_20250817_1140_R21_FLDK.06001_06001.nc
himawari  202508/31/NC_H09_20250831_1710_R21_FLDK.06001_06001.nc
gfs_thermo  2025/20250228/gfs_thermo_0p25_2025022818_f006.nc
```

## 3. 推论（待 catalogue/QC 冻结确认）

- 2025-02-28 carry-in 场景的 6 个卫星槽与 1 个 GFS thermo 初始化文件缺失 → 该理论首场景预计不可入人口；其余 8 个单槽缺口分别影响至多 8 个理论场景。
- 因此理论 856 场景的**上界**需剔除至少 9 个场景（carry-in + 8 个单槽缺口），即至多 **847 个场景**可在 QC 后入人口；实际 eligible 数量需由 catalogue/QC 阶段按全部 6 槽有效性、B13 全有限、IMERG/GFS 身份与云南监督像元规则逐场景判定；`real_population` 仍为 `NOT_VERIFIED`。
- 阶段预算参考：当前可 stat 的 2025 载荷共 **23,976,706,717 B（约 23.98 GB）**，可作为 catalogue/QC 阶段“读取并哈希全部实存文件”的源字节上限（不含目录/进程开销）；若最终推理对每个模型重读原始源，则 12 模型约 287.7 GB；若采用单次 staging 复用，则原始源字节仍为 1× 23.98 GB。最终预算需在人口冻结后按冻结口径写入协议，并由研究者批准。

## 4. 独立核验

- 独立只读核验（本地脚本，仅读已提交 run 产物与授权文件）：**56 项检查全部 PASS、0 失败**，覆盖授权 8 键与哈希绑定、预期/实存计数与字节算术逐项对账、7,063 条记录唯一性、缺失 15 项清单、守卫全零、`FINAL_TEST_2025_EXECUTED=false`、`PAYLOAD_CONTENT_READS=0`、`MODEL_INFERENCE_SCENES=0`。
- 核验 JSON：`inventory_measurement_verification_v1.json`（SHA-256 `5546ae2ecd114c2657b28ae8f55eea612d6255717a6adf9b99158a91fa901447`）。

## 5. 证据文件

| 文件 | 字节 | SHA-256 |
| --- | ---: | --- |
| `config/evaluation/b4_b7_b8_2025_inventory_measurement_authorization_v1.json` | — | `25e65f5ffe14211ae79de2d56b95c29a90ab10ee6543e71ec708bfbf7458d30a` |
| `inventory_measurement_v1.json` | 1,575,913 | `4b9113697080f7aed66f22d6981279e02128c420a7e3ac6b43d04c9654186533` |
| `inventory_measurement_summary.json` | 1,525 | `0fb6c6b137a040b5537c392f82853d47c2b3eae976f1655496493172b4f921b8` |
| `final_status.json` | 437 | `a78152e2a08577cfe563b135c6be23bd580027be418ae170519d0e17c01705c8` |

## 6. 边界与下一步

本测量结果**不构成** 2025 载荷内容读取授权、catalogue/QC 冻结、最终测试或指标计算授权；`FINAL_TEST_2025_EXECUTED=false`、`MODEL_INFERENCE_SCENES=0`、`PAYLOAD_CONTENT_READS=0`。2025 仍保持封存。

下一步需研究者对 **catalogue/QC 阶段**（在 2025 年 3–9 月范围内读取并 SHA-256 哈希实存原始文件、按冻结规则逐场景判定 eligibility、生成 candidate catalogue / eligible population / freeze record 三件套并冻结人口与精确预算；零模型前向、零结果指标、零调参）给一次明确授权；获批后单次运行、独立核验、提交并冻结人口，再请求一次性最终推理授权。
