# YunTAPR-Net 基线指标补全与消融分析 · 阶段B Tier-0 交付

生成时间：2026-10-29（Asia/Shanghai）
授权：研究者 2026-10-29 对阶段A汇报的“批准”（阶段B；先 Tier-0 零 GPU，GPU 部分排队到当前训练包封口后）。

## 1. 本轮做了什么（Tier-0，零 GPU、零推理、零原始数据读取）

从**既有**的 2024 Development 固定 E9 评价产物（dev report JSON / s2027 completion results JSON /
stage4 evaluation JSON）中只读提取，生成：

1. 主表 19 个 E9 run 的既有概率指标（Brier / AUROC / AP / 条件 Pinball / q32 coverage）；
2. 由 10 档可靠性分箱**精确重建**的 r=0.1 mm/h 发生事件混淆矩阵与其 POD / FAR / CSI / HSS
   （概率规则 `P(rain>0.1) ≥ 0.5`，标注 EXPLORATORY / POST-HOC）；
3. B0/B1 12 个 loss-arm run 的逐臂结果；B2–B8 15 个 run；
4. 公平配对消融差值（B1−B0、B3−B2、B4−B3、B5−B4、B6−B4、B7−B6、B8−B7，含三 seed 均值/样本标准差）；
5. 六工作表 Excel 工作簿 + 6 张图 + 机器可读 CSV + 校验报告。

**未做**：任何模型推理、任何原始气象数据读取、任何 2025 数据访问、任何训练/权重修改。
**未生成**：点估计阈值分类（r=1/5/10/20）与 MAE/RMSE/Bias/CC（需 Tier-1 重推理）。

## 2. 目录结构

```
YunTAPR-metric-backfill-20261029/
├─ README.md                     本文件
├─ REPORT.md                     阶段B Tier-0 汇报（数字摘要）
├─ scripts/
│  ├─ tier0_build.py             从既有产物提取/重建/校验（纯标准库）
│  ├─ build_excel.py             生成六表工作簿（openpyxl）
│  └─ make_figures.py            生成报告图（matplotlib）
├─ outputs/
│  ├─ YunTAPR-Net基线指标与消融对照_v1_Tier0_20261029.xlsx
│  ├─ tier0_runs_all.csv         28 行（19 主表 E0 + 8 B0/B1 其他臂 + 1 DOTE 控制）
│  ├─ tier0_groups.csv           96 行（B2–B8 的 UTC/强雨场景分组重建结果）
│  ├─ tier0_pairwise_deltas.csv  20 行（逐 seed 差 + 三 seed 均值/样本标准差）
│  ├─ tier0_provenance.csv       每个 run 的产物路径/SHA、checkpoint 路径/SHA、executed commit
│  ├─ tier0_proxy_continuous.csv B0/B1 既有 DIAGNOSTIC_PROXY MAE/RMSE/Bias（phase-A 代次）
│  ├─ tier0_validation.json      全部计数/身份/分箱校验结果
│  └─ figures/                   6 张 PNG（见下）
└─ phaseB_inference/             Tier-1 研发（另任务；封口后执行，见该目录）
```

## 3. 复现命令

```powershell
# 1) 提取与校验（只读既有 JSON；约 20 秒）
<PRIVATE_LOCATOR_96eb50e1d44a> scripts\tier0_build.py

# 2) 工作簿（openpyxl）
<PRIVATE_LOCATOR_96eb50e1d44a> scripts\build_excel.py

# 3) 图（matplotlib）
<PRIVATE_LOCATOR_96eb50e1d44a> scripts\make_figures.py
```

脚本内所有输入路径均为绝对路径，只读打开；不会写入任何既有目录。
环境：`<PRIVATE_LOCATOR_96eb50e1d44a>`（openpyxl 3.1.5，matplotlib）；不需要 PyTorch/GPU。

## 4. 方法定义（与项目冻结口径一致）

- 评价集：2024 Development；2023 Train 训练；**2025 Final Test 冻结未读取**。
- 固定 E9：每个 run 的第 9 轮 LAST 检查点（不是 BEST）。
- 人口：B0/B1 = 10,455 Train / 10,501 Dev（B13-V2）；B2–B8 = 959 Train / 963 Dev（f006，4 UTC，3–10 月）。
- 事件：`float32(rate) > float32(0.1) mm/h`，在升 FP64 前比较。
- 条件分位数：`log1p(mm/h)` 域，τ_i=(i−0.5)/32，q32 名义 0.984375。
- 可靠性分箱：`bins=searchsorted([0.1..0.9], p, side='right')`；bin b = [b/10,(b+1)/10)（bin9 含 1），
  故 `p=0.5` 落入 bin5，**bins 5–9 与 P≥0.5 精确对应**。
- 重建公式：
  - `TP=Σ_{b=5..9} rain_b`，`FP=Σ_{b=5..9}(n_b−rain_b)`，`FN=N_rain−TP`，`TN=(N_valid−N_rain)−FP`
  - `POD=TP/(TP+FN)`，`FAR=FP/(TP+FP)`（不是 FPR），`CSI=TP/(TP+FP+FN)`
  - `HSS=2(TP·TN−FP·FN)/[(TP+FP)(FP+TN)+(TP+FN)(FN+TN)]`
- 既有指标口径：Brier=(1/N_valid)Σ(p−1[rain])²；AUROC/AP 精确分数分组、tie 半分、AP 非插值；
  条件 Pinball=(1/N_rain)ΣΣ_τ max(τe,(τ−1)e)，e=log1p(y)−q；q32 coverage=#{log1p(y)≤q32}/N_rain。

## 5. 校验（全部通过）

`outputs/tier0_validation.json` 的 required checks：
- `Σ bins n = N_valid`、`Σ bins rain = N_rain`；
- `TP+FP+FN+TN = N_valid`；
- 期望人口计数：B0/B1 = 36,018,430 / 4,496,600；B2–B8 = 3,303,090 / 407,820；
- q32 coverage 与 `covered[31]/N_rain` 一致；
- B2–B8 的 16 个 run 另有精确分数 sqlite 校验：`P≥0.5` 计数 = `P>0.5` 计数 + 恰好 0.5 的边界质量，
  逐 run 通过（边界质量合计 62,101 个有雨像元）。

## 6. 重要限制（必须随数字一起报告）

1. POD/FAR/CSI/HSS（r=0.1、P≥0.5）是**探索性事后**指标；既有协议明确 `THRESHOLD_NOT_FROZEN`，
   不得冒充预注册主指标，也不得用于 2025 选模。
2. B0/B1 与 B2–B8 **人口不同**，不能合并计数、不能把差异归因于架构或输入因素；工作簿已分表。
3. B0/B1 的 `executed_commit` 为 `NOT_VERIFIED_EXECUTION_COMMIT_BINDING`（历史执行绑定不完整，保留原状）。
4. B0/B1 存有两代 E9 证据：主表用 final campaign LAST；2026-10-09 v2 验收的 phase-A epoch9 仅历史证据。
5. MAE/RMSE/Bias/Pearson CC 与 r=1/5/10/20 点估计分类**尚未计算**：项目没有冻结的确定性点估计规则
   （现有只是 DIAGNOSTIC_PROXY `p×mean(expm1(q))`），需 Tier-1 重推理阶段按研究者选定规则输出。
6. 本目录所有新增内容均为研究分析产物，不修改仓库、不推送、不影响正在运行的训练包。

## 7. 图目录

| 文件 | 内容 | 标注要点 |
|---|---|---|
| figures/fig1_model_metrics.png | 主表 E9 的 Brier/AUROC/q32 coverage | 两种人口用颜色区分；单 seed 无误差棒 |
| figures/fig2_B1_minus_B0.png | B1−B0 六组配对差值 | 同 seed 同臂；绿=按指标方向改善 |
| figures/fig3_ablation_gains.png | B3−B2、B4−B3、B5−B4、B6−B4、B7−B6、B8−B7 的配对增益热图 | 单 seed 行不计算 SD；三 seed 行给均值 |
| figures/fig4_B3_vs_B4_three_seed.png | B3 vs B4 三 seed 四指标 | 每 seed 独立；不声称显著性 |
| figures/fig5_occurrence_r01.png | r=0.1、P≥0.5 的 POD/FAR/CSI | 唯一可零 GPU 得到的分类结果；其余阈值待重推理 |
| figures/fig6_q32_coverage.png | q32 条件覆盖 vs 名义 98.4375% | 全部 run 欠覆盖 |

## 8. 下一步（需研究者确认后执行）

- **Tier-1（GPU）**：当前 ZERO_DOTE 训练包（seed2030 已完成、seed2031 运行中）封口后，对 19 个 E9
  checkpoint 各做一次 Dev 推理，一次前向同时输出多个候选点估计与全部阈值分类；预计 4–7 GPU·h、
  约 1.45 TiB 读取（估计）。前置：训练包封口 + GPU 空闲 + Tier-1 脚本/冒烟验证通过。
- 点估计规则：A 现有诊断代理 / B 混合中位数 / C 条件均值近似 / D 概率式 P(R>r)；
  建议同一次推理输出多候选，由研究者后定，不提前冻结。
- 工作簿/图如需并入仓库或生成 PDF，需另行确认（本轮未推送、未合并 main）。
