# YunTAPR-Net B4/B7/B8/B7_ZERO_DOTE 2025 Final Test 一次性执行报告 v1

- 日期：2026-11-27（UTC）
- 性质：工程执行记录；科研授权依据研究者明确批准
- 收据：[FINAL_TEST_RESULTS_V1.json](FINAL_TEST_RESULTS_V1.json)
- 核验：[FINAL_TEST_VERIFICATION_V1.json](FINAL_TEST_VERIFICATION_V1.json)

## 摘要

研究者明确授权后，12 个冻结 E9 模型（B4、B7、B8、B7_ZERO_DOTE × seeds 2029/2030/2031）
在冻结的 2025 年 3–9 月人口（847 个 eligible 场景）上按冻结协议一次性执行完成：847 场景 ×
12 模型前向、无训练、无调参、无检查点选择、无重试、零参数更新；275 项独立核验全部通过。

## 1 执行状态与运行身份

| 字段 | 实际值 |
| --- | --- |
| run id | `run_20261127T134218Z` |
| status | COMPLETED（exit 0） |
| authorization sha256 | `f004778f0edd1feb853da103b69bdc2106248766e583c7d61bcaa5e584865ff3` |
| payload authorization sha256 | `d5c93e094d2f87536265194588945bde96bc0480acce4d95dba1652750552eb8` |
| protocol sha256 | `eb209ff285d93ea029cdf2a68ade635d54afaa9b9acc5452dcc81313ed1e9431` |
| catalogue sha256 | `51c167f19aa8bec887f0d6c1711492a70da86abe96ba05153fea0efd14102b25` |
| population file sha256 | `14ab430f1057d1bfc1eb01637a5c9cc99f0bb373f8627bd74fd3b48964385ece` |
| freeze record sha256 | `dbe0a716d7afc4bfac4b3c45e039229cb3e3896642e01457dc03679aa4c4ebf0` |
| checkpoint catalog sha256 | `7b5bafdf9920b17c78d4949bf8a5d19a0071c06cdae3da3fa95ee57dc14aab46` |
| output root | `E:\YunTAPR_2025_12model_final_test` |
| elapsed | 858.0 s（约 14.3 分钟） |
| guards | `MODEL_PARAMETERS_UPDATED=false`；`OPTIMIZER_STEPS=0`；`BACKWARD_CALLS=0`；`STOP_NO_REPAIR_APPLIED=true` |

## 2 人口与读取账本

- 冻结 2025 人口：847 个 eligible 场景（candidate 856、rejected 9，全部因缺失 Himawari 槽位）。
- 有效像元观测 N_valid = 2,905,210；rainy 像元 N_rain = 417,607；prevalence = 0.143744。
- 逐场景读取（每次调用均计数、无缓存）：7,623 次打开、24,351,305,156 B。
- 唯一文件集：6,990 个文件、23,820,342,517 B（Himawari 5,082/23,309,298,535；GFS main
  847/252,937,333；GFS thermo 847/78,787,769；IMERG 214/179,318,880）。
- 12 个 E9 检查点权重读取：643,891,462 B。
- ledger：847 行；原始 `runtime_ledger.jsonl` 126,036,094 B，SHA-256
  `167b73b4c9eb4b72751c64ed4f43c7bc4c033d56e9f970dc71a35c138b36882b`（不公开，体积超限；
  公开紧凑 ledger 保留每场景计数与哈希列表的规范摘要）。

## 3 12 模型指标（全人口全样本）

| 模型 | seed | Brier | AUROC | AP | 条件 pinball | core loss | 覆盖误差 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| B4 | 2029 | 0.106276 | 0.895556 | 0.620738 | 0.128816 | 0.053074 | 0.009477 |
| B4 | 2030 | 0.102450 | 0.897665 | 0.630026 | 0.128666 | 0.052892 | 0.013012 |
| B4 | 2031 | 0.103862 | 0.898451 | 0.631256 | 0.128880 | 0.052934 | 0.031107 |
| B7 | 2029 | 0.105080 | 0.896599 | 0.622094 | 0.129536 | 0.053057 | 0.009057 |
| B7 | 2030 | 0.101870 | 0.898469 | 0.629326 | 0.128007 | 0.052619 | 0.022707 |
| B7 | 2031 | 0.102886 | 0.899777 | 0.632962 | 0.128814 | 0.052689 | 0.032092 |
| B7_ZERO_DOTE | 2029 | 0.106697 | 0.895949 | 0.616372 | 0.130523 | 0.053379 | 0.011271 |
| B7_ZERO_DOTE | 2030 | 0.102489 | 0.898779 | 0.630114 | 0.128172 | 0.052605 | 0.029626 |
| B7_ZERO_DOTE | 2031 | 0.103618 | 0.899850 | 0.633808 | 0.127875 | 0.052485 | 0.029359 |
| B8 | 2029 | 0.106237 | 0.897419 | 0.626013 | 0.128550 | 0.052847 | 0.007801 |
| B8 | 2030 | 0.101714 | 0.899159 | 0.630395 | 0.128365 | 0.052640 | 0.027967 |
| B8 | 2031 | 0.103483 | 0.899408 | 0.629589 | 0.128903 | 0.052829 | 0.030813 |

三 seed 等权均值：

| 模型族 | Brier | AUROC | AP | 条件 pinball | core loss | 覆盖误差 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| B4 | 0.104196 | 0.897224 | 0.627340 | 0.128787 | 0.052967 | 0.017865 |
| B7 | 0.103279 | 0.898282 | 0.628127 | 0.128786 | 0.052788 | 0.021286 |
| B8 | 0.103811 | 0.898662 | 0.628666 | 0.128606 | 0.052772 | 0.022194 |
| B7_ZERO_DOTE | 0.104268 | 0.898193 | 0.626765 | 0.128857 | 0.052823 | 0.023419 |

全部 12 个模型：Brier 0.101714–0.106697；AUROC 0.895556–0.899850；AP 0.616372–0.633809；
条件 pinball 0.127875–0.130523；32τ 条件覆盖约 0.0139–0.9533。

## 4 冻结成对比较（描述性，不做显著性推断）

`comparisons.json` 的 `inference_status` 原文为 “NOT_FROZEN; DESCRIPTIVE ONLY; NO
SIGNIFICANCE VERDICT”。协议声明比较为三 seed 等权成对描述性差值。

主比较 **B7_REAL − B7_ZERO_DOTE**：

- Brier：均值 −0.000989460；per-seed −0.001617070 / −0.000619629 / −0.000731681。
- 条件 pinball：均值 −7.1091×10⁻⁵；per-seed −0.000987845 / −0.000164766 / +0.000939337。
- AUROC +8.88×10⁻⁵；AP +0.001362693；平均条件覆盖误差 −0.002132920。

次比较（三 seed 均值）：

- B7_REAL − B4：Brier −0.000917355；条件 pinball −1.62×10⁻⁶；AUROC +0.001057；AP +0.000788。
- B8 − B4：Brier −0.000384369；条件 pinball −0.000181020；AUROC +0.001438；AP +0.001326。
- B8 − B7_REAL：Brier +0.000532986；条件 pinball −0.000179400；AUROC +0.000380；AP +0.000538。

## 5 解释边界

1. 本轮是协议冻结后的一次性最终测试，只报告冻结比较的描述性成对差值；协议未冻结推断
   程序，因此不给出显著性、置信区间或显著性判决。
2. 主比较的负向差值只说明冻结的 B7 模型在冻结的 2025 人口上 Brier 与条件 pinball 略低；
   它不建立“DOTE 物理机制被证实”的因果结论。B7_ZERO_DOTE 与 B7_REAL 的差异很小，且部分
   指标方向不一致。
3. 无独立天气事件目录绑定，不做事件级归因；不将结果解释为对未观测降水真值的验证。
4. IMERG V07 Final 是参考观测产品，不是地面真值。
5. 本报告只对应 12 个已冻结 E9 模型与冻结 2025 人口；不延伸到其他模型、时期或 2025 年
   十月之后的任何数据。
6. 2025 结果不得用于调参、模型选择、校准或后续探索性选择。

## 6 独立核验

本地独立核验脚本（不打开任何 2025 载荷，仅重算已落盘产物）执行 275 项检查，全部 PASS：

- eligible 场景顺序、847 计数与读取预算重算（7,623 次打开 / 24,351,305,156 B；唯一
  6,990 文件 / 23,820,342,517 B）。
- ledger 847 行、累计 opens/bytes 与逐场景 SHA 计数一致；原始 ledger SHA-256
  `167b73b4…36882b`。
- 12 个 metrics 文件的 N_valid 一致（2,905,210）、32τ 覆盖有限且单调、数值检查全零。
- comparisons 的 per-seed 差值逐项重算一致；run_manifest 身份绑定、frozen inputs 与 12 个
  检查点重新哈希一致；无 failure.json；运行目录内容白名单通过。

## 7 限制

1. 单一冻结人口与单次确定性执行（单 GPU）；无跨实现、跨硬件或跨运行重复。
2. 三个训练 seed 提供有限方差信息，但非独立统计重复。
3. 原始 126 MB ledger 含逐场景累计哈希列表，因 GitHub 单文件限制未公开；公开紧凑 ledger
   每场景记录累计计数与该场景哈希列表的规范摘要，原始 ledger SHA-256 记录于收据。
4. 对 DOTE 机制的物理解释仍需独立证据；本轮只执行冻结协议。

## 8 复现与文件清单

- 公开收据：`FINAL_TEST_RESULTS_V1.json`（SHA-256
  `2f645523936c10182339f225c7a1ef8104a8946f00c13cabd5afd74f6c0720f4`）。
- 核验收据：`FINAL_TEST_VERIFICATION_V1.json`（SHA-256
  `4d7b2cd3f7456962e55a1d798618c80b30f0e65cb9aeeef85c50a50a2a8acf40`）。
- 公开证据目录：`final_test_runs/run_20261127T134218Z/`（metrics 12 个、comparisons.json、
  final_status.json、runtime_ledger_compact.jsonl）。
- 本地完整运行目录：`E:\YunTAPR_2025_12model_final_test\run_20261127T134218Z`（含原始
  runtime_ledger.jsonl 与 run_manifest.json，不公开原始绝对路径）。
- 复现命令（需有效授权与原数据在位，仅供审计）：

```text
python tools/research_readiness/start_b4_b7_b8_2025_final_test.py run \
  --authorization <auth.json> --authorization-sha256 <sha> \
  --payload-authorization <payload.json> --payload-authorization-sha256 <sha> \
  --output-dir <new dir>
```
