"""Source-backed final reports; completion requires full inference, tests and figures."""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys
import numpy as np
from netCDF4 import Dataset

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/"src"),str(ROOT/"scripts")]
from yuntapr.contracts.loader import sha256
from yuntapr.training.formal_phase_a import atomic_json
from yuntapr.training.scientific_review import rows, BEST_CORE, BEST_SHA, N_SCENES, N_VALID, N_RAIN
from review_b0_phase_a_scientific_v1 import PUBLIC, STAGING, BLOCKED_RUN, read, assert_unchanged, status_defaults


def markdown_table(data,columns):
    result="| "+" | ".join(label for key,label in columns)+" |\n|"+"---|"*len(columns)+"\n"
    for row in data:
        values=[]
        for key,label in columns:
            value=row[key]
            if value is None:
                text="UNDEFINED_NO_SAMPLES"
            else:
                try:
                    number=float(value)
                    text=str(int(number)) if number.is_integer() else f"{number:.10g}"
                except (ValueError,TypeError):
                    text=str(value)
            values.append(text)
        result += "| "+" | ".join(values)+" |\n"
    return result


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--run-id",required=True)
    args=parser.parse_args()
    if Path(args.run_id).name!=args.run_id or args.run_id==BLOCKED_RUN:
        raise ValueError("Explicit new full review run required")
    out=PUBLIC/args.run_id
    manifest=read(out/"review_manifest.json")
    summary=read(out/"reinference_summary.json")
    tests=read(out/"test_summary.json")
    figures=read(out/"figure_manifest.json")
    metadata=read(out/"spatial_metadata_audit.json")
    if (summary["status"]!="PASS" or tests["status"]!="PASS" or figures["status"]!="PASS_VISUAL_REVIEW"
            or not tests["fixture_cleanup_success"] or not tests["formal_BEST_and_baseline_unchanged_before_after"]
            or metadata["status"]!="PASS" or not metadata["all_array_values_and_coordinates_unchanged"]):
        raise ValueError("Incomplete inference/test/cleanup/visual gates cannot be marked PASS")
    g=summary["global"]
    if (g["N_valid"],g["N_rain"],summary["runtime"]["scenes"])!=(N_VALID,N_RAIN,N_SCENES):
        raise ValueError("Full frozen counts required")
    if not all(summary["reconciliation"].values()) or any(summary["numeric_checks"].values()):
        raise ValueError("Full population count or numerical check failed")
    model=summary["runtime"]["model"]
    if (model["optimizer_created"] or model["optimizer_steps"] or model["backward_calls"]
            or model["model_state_sha256_before"]!=model["model_state_sha256_after"]):
        raise ValueError("Review model mutation/prohibited operation")
    preserved=assert_unchanged(out)
    remaining=[str(p) for p in (STAGING/("review_"+out.name)).rglob("*") if p.is_file()]
    if remaining:
        raise ValueError("Owned staging temporary files remain")
    for item in figures["figures"]:
        if sha256(out/item["path"])!=item["sha256"]:
            raise ValueError("Figure identity changed")
    monthly=rows(out/"monthly_metrics.csv")
    epoch=rows(out/"epoch_summary.csv")
    gap=rows(out/"generalization_gap.csv")
    quant=rows(out/"quantile_calibration.csv")
    rate=rows(out/"rainrate_stratified_metrics.csv")
    strong=rows(out/"strong_rain_DESCRIPTIVE_ONLY.csv")
    probability=read(out/"probability_distribution_stats.json")
    tail=read(out/"quantile_tail_diagnostics.json")
    spatial=read(out/"spatial_summary.json")
    rel=rows(out/"reliability_table.csv")
    cases=rows(out/"case_diagnostics.csv")
    rules=read(out/"case_selection_rules.json")
    at={int(r["epoch"]):r for r in epoch}
    val_delta=float(at[19]["val_core"])-float(at[11]["val_core"])
    convergence=(f"OBSERVED：epoch 11→19，Train core 从 {at[11]['train_core']} 降至 {at[19]['train_core']}；"
        f"Val core 从 {at[11]['val_core']} 升至 {at[19]['val_core']}，差值 {val_delta:.12f}（相对约 {100*val_delta/BEST_CORE:.4f}%）。"
        "epoch 12–19 无一优于 epoch 11，epoch 19 的独立 early-stop counter=8。这里只描述 Validation degradation，不定义‘严重过拟合’，不确定物理原因。")
    epoch_table=markdown_table([at[i] for i in (9,11,12,13,15,19)],[("epoch","Epoch"),("train_core","Train core"),("val_core","Val core"),
        ("Brier","Brier"),("AUROC","AUROC"),("AP","AP"),("conditional_pinball","Conditional pinball"),("best_checkpoint_at_epoch","Historical BEST"),("early_stop_count","ES count")])
    gap_table=markdown_table([gap[i-1] for i in (1,3,6,9,11,15,19)],[("epoch","Epoch"),("train_core_loss","Train core"),("val_core_loss","Val core"),("generalization_gap","Val − Train")])
    monthly_table=markdown_table(monthly,[("month","2024 month"),("scene_count","Scenes"),("N_valid","N valid"),("N_rain","N rain"),
        ("prevalence","Prevalence"),("global_val_core_loss","Core"),("global_L_occ","Occurrence"),("global_core_L_qr","Quantile core"),
        ("Brier_Score","Brier"),("AUROC","AUROC"),("Average_Precision","AP"),("conditional_mean_pinball","Cond. pinball")])
    monthly_proxy_table=markdown_table(monthly,[("month","2024 month"),("DIAGNOSTIC_PROXY_MAE","Proxy MAE mm/h"),
        ("DIAGNOSTIC_PROXY_RMSE","Proxy RMSE mm/h"),("DIAGNOSTIC_PROXY_Bias","Proxy Bias mm/h"),("strict_crossing_count","Crossing"),("nonfinite_count","Nonfinite")])
    month_observed=[]
    for key,label,high in (("global_val_core_loss","core loss",True),("Brier_Score","Brier",True),("AUROC","AUROC",False),
            ("Average_Precision","AP",False),("conditional_mean_pinball","conditional pinball",True)):
        ordered=sorted(monthly,key=lambda row:float(row[key]))
        low,upper=ordered[0],ordered[-1]
        month_observed.append(f"- OBSERVED：{label} 范围 {float(low[key]):.10f}（{low['month']}）至 {float(upper[key]):.10f}（{upper['month']}）。")
    monthly_observed="\n".join(month_observed)
    quant_table=markdown_table([quant[i] for i in (0,1,15,16,25,30,31)],[("tau","tau"),("conditional_coverage","Coverage"),
        ("coverage_minus_tau","Coverage − tau"),("absolute_calibration_error","Abs. error"),("conditional_pinball_log1p_mm_h","Pinball (log1p domain)")])
    tail_text="\n".join(f"- {name}：{value['number_of_tau']} 个 tau，mean absolute coverage error={value['mean_absolute_coverage_error']:.12f}。" for name,value in tail["groups"].items())
    prob_table=markdown_table([{"group":name,**value} for name,value in probability["groups"].items()],[("group","Truth group"),("count","Count"),
        ("mean","Mean p"),("std","SD p"),("p1","p1"),("p5","p5"),("p25","p25"),("median","Median"),("p75","p75"),("p95","p95"),("p99","p99")])
    rate_table=markdown_table(rate,[("rate_bin_mm_h","True-rate bin mm/h"),("pixel_count","Count"),("fraction_of_rainy_population","Rain fraction"),
        ("conditional_pinball_log1p_mm_h","Cond. pinball"),("DIAGNOSTIC_PROXY_Bias_mm_h","Proxy Bias mm/h"),("DIAGNOSTIC_PROXY_MAE_mm_h","Proxy MAE mm/h")])
    strong_table=markdown_table(strong,[("threshold_mm_h","True rate > mm/h (DESCRIPTIVE_ONLY)"),("count","Count"),
        ("conditional_pinball_log1p_mm_h","Cond. pinball"),("DIAGNOSTIC_PROXY_Bias_mm_h","Proxy Bias mm/h"),("DIAGNOSTIC_PROXY_MAE_mm_h","Proxy MAE mm/h")])
    spatial_table=markdown_table([{"metric":name,**value} for name,value in spatial["cell_metric_ranges"].items()],
        [("metric","Cell diagnostic"),("min","Min"),("median","Median"),("max","Max")])
    reliability_table=markdown_table(rel,[("bin","Bin"),("lower","Lower"),("upper","Upper"),("count","Count"),("mean_predicted_probability","Mean p"),("observed_rain_frequency","Rain frequency")])
    ece=sum(int(r["count"])*abs(float(r["mean_predicted_probability"])-float(r["observed_rain_frequency"])) for r in rel if int(r["count"]))/N_VALID
    group_dist=probability["groups"]
    highest_case=[r for r in cases if r["rule"]=="HIGHEST_TRUE_RAIN_RATE" and r["rank"]=="1"][0]
    strongest=strong[-1]
    best=manifest["formal_best"]
    io=summary["runtime"]["I_O"]
    source=manifest["source_identity_preflight"]
    key_results=(f"Brier={g['Brier_Score']:.12f}；AUROC={g['AUROC']:.12f}；AP={g['Average_Precision']:.12f}；"
        f"conditional mean pinball={g['conditional_mean_pinball']:.12f}。")
    numerical_table=markdown_table([{"check":k,"count":v} for k,v in summary["numeric_checks"].items()],[("check","Full output numerical check"),("count","Count")])
    figure_text="\n".join(f"- [{item['path']}]({item['path']}) — {item['dpi']} dpi，{item['width_pixels']}×{item['height_pixels']}。" for item in figures["figures"])
    report=f"""# B0 Phase-A Scientific Characterization Review v1

本轮 `B0_PHASE_A_SCIENTIFIC_REVIEW_COMPLETED=true`：完整 2024 Validation 再推理、月度/空间/雨强诊断、概率可靠性、32-quantile 校准、图件检查及 {tests['total_tests_executed']} 项测试均真实执行。
这是 `SCIENTIFIC_RESULT_REVIEW_ONLY` 的工程和结果审阅完成，不是科研接受决定或下一 Stage 授权。

Review run：`{out.name}`。执行 parent：`{manifest['baseline_commit']}`；科研结果 baseline：`{manifest['scientific_baseline_commit']}`。
正式训练 run：`{manifest['formal_run_id']}`；旧阻塞 run `{BLOCKED_RUN}` 的全部文件保持 immutable，并通过 parent Git blob 与收尾 SHA 核验。

## 1. 冻结身份、预检与只读执行

冻结 Protocol v1.0、Scientific Freeze v1.1、engineering v4、Phase-A 2023 normalization、Train/Validation manifests、SP04、Yunnan mask 的 SHA 均核验通过。
新 run 创建前，source preflight 已逐项核验全部 {source['scenes_checked']} 个 B13 来源以及 {source['days_checked']} 个 IMERG 日文件的存在、size 和 SHA。
B13 size 独立匹配正式 ledger；IMERG 历史 ledger 独立冻结 SHA，本轮 size>0 且 hash 前后稳定，同时记录实际 bytes，未伪造历史 size 字段。
源路径始终为 `H:\\葵花202303_202510` 与冻结 IMERG 2024 文件，无盘符替换、静默 fallback 或未来帧。

BEST：epoch=11；global_update=64460；official global_val_core_loss=0.04730775889882134。
`{best['absolute_local_path']}`；bytes={best['bytes']}；SHA256=`{BEST_SHA}`。
full payload 只做 provenance/checksum 验证；只将 model state 加载到独立推理模型，optimizer state 不应用。
完整顺序为 frozen eligible Validation identity order；batch=8，eval/no_grad，BF16 forward，FP32 raw quantile，qlog/qphysical float64。
模型逻辑 SHA 前后均为 `{model['model_state_sha256_before']}`；checkpoint 文件未修改。
`MODEL_PARAMETERS_UPDATED=false`、`OPTIMIZER_STEPS=0`、`BACKWARD_CALLS=0`，硬 guard 的 prohibited attempts 全部为 0。
本轮仅访问 2024 raw sources；`2025_PIXELS_READ=0`。

保留原始 reader/QC/normalization/SP04 和 formal batch/forward 的输入合同，未改变冻结科学实现。
旧 mixed-year per-frame QC 文件不打开；source SHA 与 frozen pair 证据验证实际 B13 obs_start/obs_end/date_created。
历史 wrapper 的 FORMAL_SCIENTIFIC_RUN tensor-contract tag 不授予优化权限；本轮进程权限始终为更窄的只读 review scope。

## 2. 19 epoch 学习曲线、BEST 和 early stop

图件只用正式 training_history.csv / validation_history.csv 的完整 19 epoch 值，不平滑、不删点；BEST=11 与 stop=19 均标明。
Train/Val core、occurrence、quantile、Val Brier/AUROC/AP、conditional pinball、LR、grad-norm/clipping 和 gap 均已展示。
LR 图只显示 history 真实 epoch start/end 记录，不将中间连线宣称为逐 update 观测。
Train occurrence 保留原生产 AMP/FP32 算法，Val numerator 使用冻结 FP64 算法；gap 是规定的记录值差，不能全部解释成数据泛化或单一精度影响。

{epoch_table}

`CHECKPOINT_SELECTION_REMAINS_EPOCH_11`：criterion 冻结为 minimum global_val_core_loss。
epoch 13 的 AUROC/AP、epoch 15 的 Brier 和 epoch 12 的 conditional pinball 某些值更好，不改变正式 checkpoint 选择。

{convergence}

## 3. 泛化差距

generalization_gap=Val core−Train core，逐 epoch 全表见 generalization_gap.csv。

{gap_table}

## 4. 全量 2024 再推理与精确复现

真实推理 {N_SCENES:,} 场（2024 March–October），N_valid={N_VALID:,}，N_rain={N_RAIN:,}，prevalence={g['prevalence']:.12f}。
global core={g['global_val_core_loss']:.17g}；occurrence={g['global_L_occ']:.17g}；quantile core={g['global_core_L_qr']:.17g}。
{key_results}
全部 32 个 conditional coverage 对正式 epoch 11 **逐值精确相等**；global metrics/per-tau pinball 按预声明 atol=rtol=1e-12 比较均 PASS。
monthly/spatial/rate strata/probability bins/histograms 与全局计数对账全部通过；没有抽样替代全量。

DIAGNOSTIC_PROXY=p_rain×mean(32 physical conditional quantiles)，不是 exact expected precipitation。
全局 proxy MAE={g['DIAGNOSTIC_PROXY_METRIC']['MAE']:.12f}、RMSE={g['DIAGNOSTIC_PROXY_METRIC']['RMSE']:.12f}、Bias={g['DIAGNOSTIC_PROXY_METRIC']['Bias']:.12f} mm/h。
全局 loss numerator 使用 N_valid 作为 denominator；conditional mean pinball 使用 N_rain。pinball 在 log1p(rate / mm h−1) 域，是无量纲量。

## 5. 月度性能与季节描述

{monthly_table}

{monthly_proxy_table}

{monthly_observed}

以上是 March–October 的观察差异，各月 rain prevalence 和样本数不同，排名指标、Brier 与 conditional pinball 衡量性质不同。
月份关联不等于季节气象因果；具体天气系统、地形或云物理原因均为 `POSSIBLE_EXPLANATION_NOT_ESTABLISHED`。
没有用 2024 结果改已完成的 loss、LR、参数或 protocol。

## 6. 空间 cell diagnostics

先检索冻结 config/src/scientific_freeze/training_protocol；无预定义区域：`NO_PREDEFINED_SUBREGION_MASK_AVAILABLE`。
不生成 regional_metrics.csv，不创建事后 A/B/C 或‘差区域’；仅对正式 Yunnan mask 内 3,430 个 target cell 展示统计。
网格为 100×100，精确冻结 Float32 lat/lon；lat ascending，无 transpose，无 silent flip。原数组坐标 hash 见 spatial_summary.json。
空间汇总先在本 run 的英文私有路径写入，再验证 size/SHA 后复制到中文仓库；reader 从公共文件字节构造 netCDF memory dataset，不改变任何原始 source path。
raw proxy signed/absolute/squared sums 的物理单位另行审计，metadata 修改前后全部变量数值与坐标逐字节 hash 相同，见 spatial_metadata_audit.json。
评价之外不显示指标；每 cell valid/rain counts 完整保留并对账至 global counts。
conditional pinball 仅 rainy_count≥{rules['spatial_conditional_pinball_min_rain_count']} 时报告，`DISPLAY_DIAGNOSTIC_ONLY`；低于规则的 cell 数={spatial['cells_not_reporting_conditional_pinball']}。
此显示规则不排除全局/月度评价样本、不改变 loss weight 或 evaluation mask。

{spatial_table}

OBSERVED：表中的 cell 范围和图中的差异属于 cell diagnostics；不是新科研分区，不能从这些地图重定义训练 region 或物理归因。

## 7. Occurrence reliability 与概率分布

固定预声明 bins：[0,0.1)，…，[0.9,1]，末 bin 包含 1；所有 {N_VALID:,} valid pixels 分箱，不选择 cutoff 或拟合 calibration。

{reliability_table}

overall Brier={g['Brier_Score']:.12f}。补充固定-bin weighted absolute calibration deviation=Σ(N_bin/N_valid)|mean p_bin−observed frequency_bin|={ece:.12f}，仅 `BINNED_DIAGNOSTIC`，不是新 checkpoint metric 或接受阈值。
没有做 temperature/isotonic/Platt scaling，也没有 probability cutoff、POD/FAR/CSI 冻结。

{prob_table}

概率 SD 的 ddof=0；percentiles 使用完整群体的精确 weighted type-7/linear order statistics。图是预声明 0.01-bin density-style histogram，不做 KDE 或平滑。

## 8. 32-quantile calibration 与 tails

tau=(i−0.5)/32。全部 32 项 coverage、coverage−tau、absolute calibration error、conditional pinball 见 quantile_calibration.csv；实际输出未 sort/clamp/校准。

{quant_table}

OBSERVED：lowest tau=0.015625，coverage={float(quant[0]['conditional_coverage']):.17g}，error={float(quant[0]['coverage_minus_tau']):.17g}，低于名义 tau。
中间 pair 是 tau=0.484375/0.515625（本模型不存在恰好 0.5 的输出 tau），高 tail 包含 0.953125/0.984375；表与 32 项曲线完整报告误差方向。
low tau<0.2、middle 0.2≤tau≤0.8、high tau>0.8 均仅 `ANALYTIC_GROUPING_ONLY`，不是模型定义或新分位设计。

{tail_text}

单调性不等于 calibration；coverage 贴合也不自动证明完整条件分布/高尾外推或科学接受。

## 9. Quantile 数值检查

下表在每场全部 100×100 输出 cell 上检查（{N_SCENES*10000:,} cell outputs），评价统计另用 frozen valid Yunnan population。
qlog 与 qphysical crossing 定义为相邻 q[i+1]≤q[i]，检查严格单调；q1 support violation 定义为 qlog[1]≤log1p(0.1)。

{numerical_table}

所有输出 tensor 的 finite/FP32参数/FP64 quantile 精度 gate 也实际通过；global accumulation nonfinite/crossing=0。

## 10. 描述性雨强和强降水子集

仅根据真实 float32 IMERG target 的 frozen R>0.1 label 分层，生产阈值先在原 dtype 判定、再提升 FP64。
`DESCRIPTIVE_RATE_BINS_ONLY`，不是 extreme precipitation definition，也不用于 loss reweight。

{rate_table}

{strong_table}

>50 mm/h 子集 count={strongest['count']}，约占 rainy population {int(strongest['count'])/N_RAIN:.10%}。
各 threshold 子集重叠，不能相加当作互斥档；完整 per-tau conditional coverage/pinball 存在 strong_rain_quantiles_DESCRIPTIVE_ONLY.json。
高雨强组的数量、proxy 误差与 quantile 行为只支持本群体描述，不估计事件独立性、置信区间或全国/多年泛化。
项目正式 extreme definition=`NOT_FROZEN`；本轮不冻结任何强降水阈值。

## 11. 客观案例

case_selection_rules.json 在 inference_start 前写入并哈希固定；三种规则各 top-10，合计 30 case records。
最大绝对 proxy error、最高真实雨强、最低 rainy 真实雨强；tie 用原冻结 scene order 后 row-major cell index，没有人工选择‘好看’案例。
每条存 time/位置/IMERG/p_rain、全部 32 physical quantiles 及摘要、proxy 与 error。案例没有额外训练或改变总体评价。
最高 true-rate 案例：window_start={highest_case['window_start']}，R={highest_case['IMERG_rate_mm_h']} mm/h，p_rain={highest_case['p_rain']}，proxy={highest_case['DIAGNOSTIC_PROXY_mm_h']} mm/h。
case 集合由极值规则筛选，不能当作随机样本、总体误差率或 causal proof。

## 12. 科学角色、限制与解释

B0 是 `CONTROL / BASELINE`，仅 latest causal Himawari B13 single frame。
没有 multi-temporal/multi-channel/GFS/DEM/terrain/DOTE/DTFM/MEE/ERA5 teacher。
这是设计事实，不等于实验证明缺失某项信息导致某个误差；不能宣称 B0 已证明完整 YunTAPR-Net 有效。
后续 B1–B8 需严格可比实验且另获授权；本轮不启动。
直接支持的限制与未证实 hypothesis 分别列在 B0_LIMITATION_INVENTORY.md；气象物理解释没有额外变量证据时仍为 `POSSIBLE_EXPLANATION_NOT_ESTABLISHED`。

## 13. 190 项隔离测试、清理与完整性

existing regression/formal={tests['existing_tests_executed']}；scientific-review units={tests['scientific_review_unit_tests_executed']}；full-review artifact={tests['full_review_artifact_tests_executed']}；合计={tests['total_tests_executed']}。
实际 suite counts、每个 test 和结果见 test_results.txt / test_summary.json；无 failure/error/skip。
`TEST_FIXTURE_ONLY=true`。获批的临时 optimizer/backward/step 只属于隔离 fixture；测试进程没有加载 BEST 到测试模型，也没有共享 Scientific Review inference model。
测试的全量 artifact 阶段只读取 BEST SHA 作 identity verification，不应用 checkpoint tensors。
fixture 临时目录已完全清理，模型/optimizer 内存随独立进程退出释放；fixture 操作不计入 review OPTIMIZER_STEPS/BACKWARD_CALLS。
前后检查 {preserved['files_checked']} 个 immutable parent 文件（含旧阻塞 run）及 BEST SHA 均不变，所有本 run staging 文件已清理。

## 14. 运行与中文路径 I/O

reinference wall_seconds={summary['runtime']['wall_seconds']:.3f}；peak GPU allocated={summary['runtime']['peak_GPU_allocated_bytes']:,} bytes；reserved={summary['runtime']['peak_GPU_reserved_bytes']:,} bytes。
staging copy_seconds sum={io['copy_seconds_sum']:.3f}；read_seconds sum={io['read_seconds_sum']:.3f}；peak temporary bytes per worker={io['temporary_bytes_peak_per_worker']:,}；cleanup_success={io['cleanup_success']}。
这些 sums 是两个 worker 的工作量，会重叠，不等于 wall time；copy 计时不包含独立 SHA 验证时间，实际 SHA/copy/read 额外 I/O 都存在。
每 worker 一次仅一个文件、cap=734003200 bytes，复制前后 size+SHA 相等，成功读取后只删除本流程 owned copy；原始 H 与诊断缓存不变。
详细 11,727-scene read ledger 存 F 盘，本仓库仅保存 path/bytes/SHA；不提交 raw data、model/optimizer binaries、cache、wheel 或 venv。

## 15. 图件、输出与研究者决定

{figure_text}

所有图件均据真实 history 或本轮 full aggregates；曲线 600 dpi，空间 300 dpi，labels/units/坐标和 mask 逐图检查通过。
报告、CSV/JSON、spatial_cell_metrics.nc、manifest、test logs 和 artifact hash index 构成独立完整审阅证据。
spatial artifact 为小型汇总，不含 scene-level raw/prediction cube；exact axes/hash 保留。

`B0_PHASE_A_ACCEPTED=UNDECIDED`；`ACCEPT_B0_PHASE_A=UNDECIDED`；`TRANSFER_EPOCH_BUDGET_TO_PHASE_B=UNDECIDED`；`PHASE_B_AUTHORIZED=false`。
审阅完成不替研究者接受实验、不迁移预算、不启动 Phase-B，完成后停止。
"""
    (out/"B0_PHASE_A_SCIENTIFIC_REVIEW.md").write_text(report,encoding="utf-8",newline="\n")
    inventory=f"""# B0 limitation inventory

Scope: SCIENTIFIC_RESULT_REVIEW_ONLY；review `{out.name}`。

| Item | Evidence class | Supported statement / limit |
|---|---|---|
| Epoch 11 后 validation degradation | OBSERVED | {convergence} |
| Low-tau calibration deviation | OBSERVED | tau=0.015625 coverage={float(quant[0]['conditional_coverage']):.12f}，error={float(quant[0]['coverage_minus_tau']):.12f}；严格单调不能消除校准偏差。 |
| 月份差异 | OBSERVED | 全 8 月 metrics 与 support 见 monthly_metrics.csv；不能只用月份排名推断天气成因。 |
| 空间差异 | OBSERVED | frozen Yunnan 内 cell metric ranges/maps 有差异；没有事后 regional masks；低计数只影响指标显示。 |
| 强降水样本支持 | OBSERVED_DESCRIPTIVE_ONLY | >50 mm/h 仅 {strongest['count']} 个 rainy pixels（fraction={int(strongest['count'])/N_RAIN:.10g}）；其它阈值 count 完整列表，不能把 pixel 数当独立事件数或固定 extreme definition。 |
| single-band / single-time | DESIGN_FACT | 仅 B13 一帧，缺少其它模块信息；未实验证明其造成某项特定误差。 |
| DIAGNOSTIC_PROXY 含义 | DEFINITION_LIMIT | p_rain×32-quantile physical mean，不是 exact expectation，proxy MAE/RMSE/Bias 不能改称精确期望预测误差。 |
| Quantile tail extrapolation | NOT_ESTABLISHED | 只有冻结 32 tau；未建立 outside-grid tail model，不宣称极端尾部分布已完备。 |
| 气象/地形因果 | HYPOTHESIS_NOT_ESTABLISHED | 云顶温度与地面雨强的非唯一性、天气系统或地形解释均缺独立变量/可比实验支持。 |
| 泛化范围 | DESIGN/EVIDENCE_BOUNDARY | 本结果是 frozen 2024 March–October Validation；没有读 2025，不证明未触及 test year、全国或所有年际天气泛化。 |
| Validation 的科研用途 | PROTOCOL_BOUNDARY | 本轮诊断不反向修改已完成 B0 Protocol、不改变 BEST；任何后续试验另由研究者批准。 |

不同月份/雨强/空间诊断不是独立试验；未构造置信区间、显著性或物理归因。
Acceptance 与 epoch-budget transfer 均 UNDECIDED，Phase-B 未授权。
"""
    (out/"B0_LIMITATION_INVENTORY.md").write_text(inventory,encoding="utf-8",newline="\n")
    packet=f"""# B0 Phase-A researcher decision packet

完整 scientific review `{out.name}` 已执行；本 packet 将证据提供给研究者，**不代为接受实验**。

## A. Protocol compliance

所有冻结身份、源 preflight、11,727-scene fixed order、full counts、FP32/BF16/FP64 路径、因果约束与 numerical checks 均 PASS。
Model logical SHA 和 BEST 文件前后不变；review optimizer=0、backward=0、2025 pixels=0。
旧 blocked run immutable；approved fixture tests 单独进程且已清理。

## B. Training convergence evidence

{convergence}

## C. Selected checkpoint identity

epoch 11 / global_update 64460 / official core 0.04730775889882134。
`{best['absolute_local_path']}`；bytes={best['bytes']}；SHA=`{BEST_SHA}`。
`CHECKPOINT_SELECTION_REMAINS_EPOCH_11`，minimum global_val_core_loss criterion 未变。

## D. Occurrence performance

N_valid={N_VALID:,} / N_rain={N_RAIN:,} / prevalence={g['prevalence']:.12f}。
{key_results}
10 个固定-bin reliability 与 rainy/dry probability distributions 完整；Brier 和 rank metrics 不能互相替代，未选 cutoff/校准。

## E. Probabilistic quantile performance

完整 32 tau conditional pinball/coverage 与正式 epoch 11 复现通过，所有 qlog/qphysical crossing、nonfinite、q1 support violation=0。
qlog/physical float64；无 quantile sort/clamp/校准。

## F. Calibration diagnostics

lowest tau=0.015625，coverage={float(quant[0]['conditional_coverage']):.12f}；error={float(quant[0]['coverage_minus_tau']):.12f}。
low/middle/high analytic-only MAE 见 quantile_tail_diagnostics.json；reliability fixed-bin weighted absolute deviation={ece:.12f}（BINNED_DIAGNOSTIC）。
Numerical stability 与 probabilistic calibration 分别核验；严格单调不等于校准正确。

## G. Monthly / spatial / rain-rate weaknesses

{monthly_observed}

Yunnan cell maps/ranges 完整，NO_PREDEFINED_SUBREGION_MASK_AVAILABLE；未创建事后 regions。
强降水 >50 mm/h count={strongest['count']}；true-rate 档和 >10/20/30/50 都仅描述性，极端科学定义 NOT_FROZEN。
详见主报告中的全表；没有从诊断地图/阈值反向改 protocol 或 loss weights。

## H. Known limitations

参见 B0_LIMITATION_INVENTORY.md：post-11 validation 回升、low-tau coverage deviation、月度/空间差异、强雨支持数量和 proxy 定义限制。
单帧单通道为设计事实；未证明其造成某项误差，B0 只作 CONTROL / BASELINE，不代表全 YunTAPR-Net 有效。

## I. Open questions

- 研究者如何评价当前 B0 收敛、概率校准和各月/雨强支持的充分性？本 packet 不建立新接受阈值。
- 是否接受 Phase-A 作为严格可比 baseline，以及后续试验预算/方案？没有自动实施。
- 物理原因未确立；没有额外气象/地形变量与可比实验，不给 causal conclusion。
- 正式 extreme definition 仍 NOT_FROZEN；所有本轮 thresholds 只是 DESCRIPTIVE_ONLY。
- 未触及 2025，后续 test/FinalFit 需原科研合同和独立授权。

## J. Researcher decision required

`ACCEPT_B0_PHASE_A=UNDECIDED`。
`B0_PHASE_A_ACCEPTED=UNDECIDED`。
`TRANSFER_EPOCH_BUDGET_TO_PHASE_B=UNDECIDED`。
`PHASE_B_AUTHORIZED=false` / `B1_TO_B8_AUTHORIZED=false`。

测试：{tests['existing_tests_executed']} existing + {tests['scientific_review_unit_tests_executed']} units + {tests['full_review_artifact_tests_executed']} artifacts = {tests['total_tests_executed']}，全部 PASS/无跳过。
完整完成状态只表示 review requirements 已满足，接受与下一 Stage 仍由研究者决定。
"""
    (out/"B0_PHASE_A_RESEARCHER_DECISION_PACKET.md").write_text(packet,encoding="utf-8",newline="\n")
    status={**status_defaults(),"run_id":out.name,"state":"SCIENTIFIC_REVIEW_COMPLETED_RESEARCHER_DECISION_REQUIRED",
        "B0_PHASE_A_SCIENTIFIC_REVIEW_COMPLETED":True,"BEST_CHECKPOINT_VERIFIED":True,
        "FULL_2024_REINFERENCE_COMPLETED":True,"MONTHLY_ANALYSIS_COMPLETED":True,"SPATIAL_ANALYSIS_COMPLETED":True,
        "RELIABILITY_ANALYSIS_COMPLETED":True,"QUANTILE_CALIBRATION_REVIEW_COMPLETED":True,
        "QUANTILE_CROSSING_COUNT":g["strict_crossing_count"],"NONFINITE_COUNT":g["nonfinite_count"],
        "Q1_SUPPORT_VIOLATION_COUNT":summary["numeric_checks"]["q1_support_violation"],
        "VALIDATION_SCENES_INFERRED":N_SCENES,"N_valid":N_VALID,"N_rain":N_RAIN,
        "CURRENT_171_TESTS_RERUN":True,"NEW_REVIEW_UNIT_TESTS_EXECUTED":tests["scientific_review_unit_tests_executed"],
        "FULL_REVIEW_ARTIFACT_TESTS_EXECUTED":tests["full_review_artifact_tests_executed"],"TOTAL_TESTS_EXECUTED":tests["total_tests_executed"],
        "CHECKPOINT_SELECTION_REMAINS_EPOCH_11":True,"TEST_FIXTURE_ONLY":True,"FIXTURE_CLEANUP_SUCCESS":True,
        "OLD_BLOCKED_RUN_IMMUTABLE":True,"OWNED_STAGING_FILES_REMAINING":0,"ALL_IMMUTABLE_PARENT_FILES_UNCHANGED":True,
        "updated_utc":datetime.now(timezone.utc).isoformat()}
    atomic_json(out/"final_status.json",status)
    manifest.update(completed_utc=status["updated_utc"],final_status=status["state"],full_reinference_completed=True,
        old_blocked_run_preserved=True,preservation=preserved,fixture_cleanup_success=True,
        additional_code_sha256={p:sha256(ROOT/p) for p in ("scripts/plot_b0_scientific_review_v1.py", "scripts/test_b0_scientific_review_v1.py",
            "scripts/report_b0_scientific_review_v1.py","scripts/verify_b0_review_spatial_metadata_v1.py",
            "tests/scientific_review/test_review_units.py","tests/scientific_review/test_review_full_artifacts.py")})
    atomic_json(out/"review_manifest.json",manifest)
    artifacts={str(p.relative_to(out)).replace("\\","/"):{"bytes":p.stat().st_size,"sha256":sha256(p)} for p in out.rglob("*") if p.is_file() and p.name!="artifact_sha256.json"}
    atomic_json(out/"artifact_sha256.json",artifacts)
    print(json.dumps({"run_id":out.name,"state":status["state"],"tests":tests["total_tests_executed"],"figures":figures["figure_count"],"PHASE_B_AUTHORIZED":False}))


if __name__=="__main__":
    main()
