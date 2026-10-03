# YunTAPR-Net B0 2025 catalogue-only QC + 资格样本清单冻结 v1.1

本轮已完整执行真实 2025 March–September catalogue QC，10272 个候选槽位全部登记；实际 eligible=10244，rejected=28。两个 CSV 与 freeze record 已冻结。最终闭环测试 128 项全部通过，零跳过。正式 Final Test 未授权、未执行；没有加载 FINAL、实例化模型、forward、backward、optimizer 或计算结果统计。

## 独立 run 与历史保护

Baseline: `c661d8a31dbd8cc205624716d8a2d0fcd0867023`。本轮 run: `run_20261003T015507_526850Z`。完成 UTC: `2026-10-03T02:19:36.127822+00:00`。基线 1771 个文件逐文件 Git blob/SHA256 核验，原字节均保留。历史 v1/v1.1、preflight、失败和 final_status 均未修改。本轮所有提交变更均为新增。

独立授权为 `config/evaluation/b0_2025_catalogue_only_authorization_v1.1.json`，scope=`B0_2025_FINAL_TEST_CATALOGUE_ONLY`。主入口为 `scripts/execute_b0_2025_catalogue_only_v1_1.py`，适配器为 `src/yuntapr/evaluation/catalogue_execution_v1_1.py`。本轮在冻结 baseline 上执行后停止；已完成/失败 run 与已有 staging child 不可复用，重复调用不会重新读取源数据。

## FROZEN：范围、schema、资格与身份

候选窗口精确为 UTC `[2025-03-01 00:00, 2025-10-01 00:00)`，30 分钟间隔，10272 行，固定顺序。9 月末窗口可止于 10 月 1 日 00:00，但其最新卫星 nominal 仍在 9 月；未读取 October source。candidate CSV 严格 28 列，eligible CSV 严格 12 个 identity 字段，只是 eligible rows 的精确 projection；无缺槽、重复、乱序、older-frame fallback 或 silent replacement。

沿用原冻结资格：IMERG V07 Final；latest B13 nominal=T+20min；obs_start≤obs_end≤T+30min；B13 501×501 full-valid finite；IMERG exact time/grid provenance；云南 valid supervised pixels>0。部分 IMERG 有效性保留；不新增 3430 全有效条件；不以雨强决定资格。输出只含源身份、QC、valid-mask count、固定 rejection enum。两个源全程只读。

拒绝原因实际计数如下。一个槽位可含多个固定原因，因此各原因计数之和不必等于 rejected_count。

|冻结 rejection reason|实际槽位计数|
|---|---:|
| `B13_FULL_SCENE_REQUIRED` | 28 |
| `B13_METADATA_INVALID` | 16 |
| `B13_NOT_READABLE` | 4 |
| `EXPECTED_LATEST_B13_MISSING_NO_FORMAL_FALLBACK` | 4 |

## 来源绑定与研究者补充批准

H root: `H:\葵花202303_202510`；IMERG root: `F:\云南极端降水数据\raw\IMERG`。没有使用其它盘符替代源数据。completion manifest 固定绑定已存在的 `F:\云南极端降水数据\manifests\imerg_manifest.jsonl`；384292 bytes，SHA 与历史登记一致。本轮只增加独立适配器处理已批准的 manifest 元数据路径；未移动/复制 manifest 到 raw root，未修改原协议、reader、schema 或资格规则。

旧 freeze schema 中 `implementation_sha256` 保持原 v1.1 bundle。新执行模块、入口和适配器测试的 SHA 由独立授权 `execution_implementation_sha256` 锁定；freeze record 的 authorization SHA 绑定完整授权。`execution_manifest.json` 与 `authorization_binding.json` 记录该递归来源链，避免把新适配器伪称为旧代码。

FINAL 按研究者本轮决定，只核验 C 仓库冻结 identity 记录不变。实际 FINAL 文件没有打开，实际文件 SHA256 **NOT_RECOMPUTED**，不得将登记的二进制 SHA 解释为本轮对实际文件重新核验。normalization frozen identity 原样保留，未 refit。

## 冻结 SHA256

- candidate CSV: `b11006105aebc92370d0c37042f3d0c27ec08aeb3a8b602987c62d131f18b16d`
- eligible identity CSV: `53ce28a5dc70b2e39401870fb7b99847e095ae921c372b9240d240fd4501855e`
- catalogue freeze record: `0fe4995888a40d77c4df761c2f1510596dd6e2fc0388c2dabe2a1ca890a94d3f`
- independent authorization: `00ed1e1de442832e2197d71ee5412aafa95496b144cae73781adfeb3e13ac1c0`
- frozen v1.1 protocol: `b1be82d5bc03293c35ddc793faa1187e97fa48c537039181c0eb68a689f15eb8`
- normalization: `c7042beac2412594ca9fc264d7df10981755b393158c539cb48c9b56cd314327`
- FINAL registered binary identity (NOT RECOMPUTED): `05359d2fee2ae61daf654ae5a59b7977cb65247fd46d97a69a690a0133da7f65`
- FINAL frozen identity record: `d88bc7ec861ffcfd654ba339ea519f5fc061adb6ebcaf7477d052230b4b5899a`
- completion metadata manifest: `7efef36f05545ac6b9482e5d8fd68367aea875bc59145606a1bf45b5848968c1`

## Raw-access telemetry 与中文路径额外 I/O

使用 `F:\pytorch\Research\stage0_himawari\cache\staging\catalogue_only_run_20261003T015507_526850Z` 的单文件 bounded English staging，cap=734003200 bytes。每次复制都核验 size 和 source/staged SHA，再经 netCDF4 读取；仅删除流程自己创建的 UUID 临时 nc。现已全部清理，无遗留临时副本；没有删除原始 H/IMERG 或旧 diagnostic cache。staging 目录仅为空目录，可保持登记。

|实际 telemetry|值|
|---|---:|
| `2025_PIXELS_READ` | 2676986256 |
| `2025_CATALOGUE_QC_ACCESS` | true |
| `raw_source_open_events` | 20964 |
| `b13_pixel_values_read` | 2574266256 |
| `imerg_pixel_values_read` | 102720000 |
| `source_hash_bytes_read` | 45912491227 |
| `source_copy_bytes_read` | 45912491227 |
| `source_copy_bytes_written` | 45912491227 |
| `copy_seconds` | 144.56355669996628 |
| `read_seconds` | 97.77970909999749 |
| `temporary_bytes_peak` | 6112392 |
| `cleanup_success` | true |

QC 到最后槽位 elapsed=346.151848 s；随后还执行完整 schema/projection/hash/history 核验。copy_seconds 与 read_seconds 为各 staging 操作实测加总；read 包含 reader/QC，未包含 hash 验证时间。原始源复制读取和 source SHA 读取各为 45912491227 bytes；另有等量 staging 写入、staged SHA 读取及 netCDF staging 读取。这里计数的是工程 I/O 与真实读取像元数量，均不是 Final Test metric，也不是降雨结果统计。

原始 source_open_events 为 backend 在复制/源 SHA 两个原始只读 open 的计数；source_guard_raw_open_events=20964，metadata_manifest_open_events=2 单独记录。bootstrap 只读 completion metadata，2025 raw pixels=0。

## 实际测试与修复记录

|suite|实际执行|结果|
|---|---:|---|
| `tests.final_test_catalogue.test_catalogue_gate` | 80 | PASS; 0 failure/error/skip |
| `tests.final_test_b0.test_catalogue_backend_v1_1` | 18 | PASS; 0 failure/error/skip |
| `tests.final_test_catalogue.test_catalogue_execution_v1_1` | 22 | PASS; 0 failure/error/skip |
| `tests.final_test_catalogue.test_real_catalogue_artifacts_v1_1` | 8 | PASS; 0 failure/error/skip |

最终合计 128 项。预先执行的当前授权闭包为 120 项；真实 freeze 后重跑 120 项并执行 8 项真实 artifact 检查，闭环 128 项。只运行 catalogue 相关测试；没有跑 optimizer/backward/training fixture。guard 中禁止操作的拒绝探针不等于实际执行这些操作。fixture 文件均在隔离 C 目录创建并清理。

首次测试启动器漏加 scripts 导入路径，118 项中 2 项 import error，未读 raw；失败日志与摘要保留。修正外部测试启动器后 118 项通过；新增 staging 固定目录及复用拒绝测试后 120 项通过。真实 QC 无失败重跑、无人工改动资格规则。closure tests 不重读 2025 raw，只读 C 仓库 CSV/JSON。原 98 项 catalogue tests 原样全部执行。

环境 `F:\pytorch\Research\.venv-cuda\Scripts\python.exe`，Python 3.12.14；versions={"numpy": "2.5.3", "torch": "2.11.0+cu128", "netCDF4": "1.7.4", "PyYAML": "6.0.3"}。未安装/升级环境包。源码、测试、CSV、JSON、日志、报告可提交；没有提交 raw nc、cache、checkpoint、optimizer/model binary。

## 最终状态与停止点

```text
FINAL_TEST_PROTOCOL_V1_1_FROZEN=true
FINAL_TEST_CATALOGUE_AUTHORIZED=true
REAL_2025_CANDIDATE_CATALOGUE=FROZEN
REAL_2025_CANDIDATE_COUNT=10272
REAL_2025_ELIGIBLE_COUNT=10244
REAL_2025_REJECTED_COUNT=28
2025_CATALOGUE_QC_ACCESS=true
FINAL_TEST_2025_AUTHORIZED=false
FINAL_TEST_2025_EXECUTED=false
2025_MODEL_INFERENCE_SCENES=0
2025_FINAL_TEST_METRICS_COMPUTED=false
2025_TARGET_OUTCOME_SUMMARIES_EXPOSED=false
MODEL_PARAMETERS_UPDATED=false
OPTIMIZER_STEPS=0
BACKWARD_CALLS=0
FINAL_CHECKPOINT_LOADS=0
MODEL_FORWARD_CALLS=0
```

`FINAL_actual_file_sha256_recomputed=false`；`FINAL_identity_record_sha256_unchanged=true`。完整状态见 `final_status.json`；完整 SHA 和 IO 见 `catalogue/catalogue_freeze_record.json`。

NOT_YET_AUTHORIZED: 正式 2025 Final Test。RESEARCHER_DECISION_REQUIRED: 对冻结 candidate CSV、eligible identity CSV、freeze record、协议/实现、FINAL 与 normalization 绑定的独立第二阶段授权。完成报告与 GitHub main 发布后 STOP，不进入 Final Test 或 B1–B8。
