"""Seal a truthful partial review when the frozen raw-data drive is unavailable."""
from __future__ import annotations
import argparse
import csv
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "src"),str(ROOT / "scripts")]
from yuntapr.contracts.loader import sha256
from yuntapr.training.formal_phase_a import atomic_json
from yuntapr.training.scientific_review import rows, table, TAU, BEST_SHA, BEST_BYTES
from review_b0_phase_a_scientific_v1 import FORMAL, identities, assert_unchanged, status_defaults, PRIVATE


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--run-id",required=True)
    args=parser.parse_args()
    if Path(args.run_id).name!=args.run_id:
        raise ValueError("Safe run identifier required")
    out=ROOT/"docs/scientific_review/b0_phase_a/runs"/args.run_id
    if Path("H:/").exists():
        raise ValueError("Drive is available now; do not seal as unavailable")
    failures=sorted(out.glob("failure_*.json"))
    if not failures or "FileNotFoundError" not in read(failures[-1])["traceback"]:
        raise ValueError("Actual failed source-read evidence required")
    auth,protocol,preflight,best,payload=identities()
    del payload
    preserved=assert_unchanged(out)
    epoch=rows(out/"epoch_summary.csv")
    gap=rows(out/"generalization_gap.csv")
    historical=rows(FORMAL/"selected_checkpoint_quantile_metrics.csv")
    calibration=[]
    for row in historical:
        tau,coverage=float(row["tau"]),float(row["conditional_coverage"])
        calibration.append({"selected_epoch":11,"tau":tau,"conditional_coverage":coverage,
            "coverage_minus_tau":coverage-tau,"absolute_calibration_error":abs(coverage-tau),
            "conditional_pinball":float(row["conditional_pinball"]),"evidence_scope":"HISTORICAL_FORMAL_EPOCH11_ONLY_NOT_REINFERENCE"})
    table(out/"historical_quantile_calibration.csv",calibration)
    errors=np.array([r["absolute_calibration_error"] for r in calibration])
    tail={name:{"tau_count":int(use.sum()),"mean_absolute_coverage_error":float(errors[use].mean())}
        for name,use in (("low",TAU<.2),("middle",(TAU>=.2)&(TAU<=.8)),("high",TAU>.8))}
    atomic_json(out/"historical_quantile_tail_diagnostics.json",{"scope":"HISTORICAL_FORMAL_EPOCH11_ONLY_NOT_REINFERENCE",
        "grouping":"ANALYTIC_GROUPING_ONLY","groups":tail,"source_sha256":sha256(FORMAL/"selected_checkpoint_quantile_metrics.csv")})
    fig=read(out/"figure_manifest.json")
    for item in fig["figures"]:
        if sha256(out/item["path"])!=item["sha256"]:
            raise ValueError("Figure changed since rendering")
    fig.update(status="PASS_HISTORY_FIGURES_ONLY",visual_review={"method":"all six figures inspected in local contact sheet",
        "labels_readable":True,"best_and_early_stop_markers_visible":True,"all_19_epochs_visible":True,
        "raw_points_not_smoothed":True,"no_spatial_figures_generated":True})
    atomic_json(out/"figure_manifest.json",fig)
    identity={"status":"PASS","BEST":best,"pinned_files":[{"name":name,"path":ref["path"],
        "expected_sha256":ref["sha256"],"actual_sha256":sha256(Path(ref["path"]) if Path(ref["path"]).is_absolute() else ROOT/ref["path"])}
        for name,ref in auth.config["identity"].items()],"baseline_preservation":preserved,
        "payload_verified_against_original_checkpoint_expected":True,"no_optimizer_state_applied":True}
    atomic_json(out/"identity_verification.json",identity)
    available=subprocess.check_output(["powershell","-NoProfile","-Command","Get-PSDrive -PSProvider FileSystem | Select-Object -ExpandProperty Name"],text=True).splitlines()
    ledger=PRIVATE/out.name/"read_ledger.csv"
    if ledger.stat().st_size!=0:
        raise ValueError("Partial scenes were read; use a distinct partial-population report")
    block={"status":"BLOCKED_SOURCE_DRIVE_UNAVAILABLE","checked_utc":datetime.now(timezone.utc).isoformat(),
        "available_file_system_drives":available,"H_drive_available":False,
        "required_source":r"H:\葵花202303_202510\202403\01\NC_H09_20240301_0020_R21_FLDK.06001_06001.nc",
        "failure_artifact":failures[-1].name,"scenes_inferred":0,"validation_pixels_read":0,"2025_PIXELS_READ":0,
        "IMERG_first_day_exists":Path(r"F:\云南极端降水数据\raw\IMERG\2024\imerg_20240301.nc").is_file(),
        "no_data_relocation_or_path_fallback":True,"no_source_modified":True,
        "empty_private_read_ledger":{"absolute_local_path":str(ledger),"bytes":0,"sha256":sha256(ledger)},
        "staging_files_remaining":[str(p) for p in (Path(r"F:\pytorch\Research\stage0_himawari\cache\staging")/("review_"+out.name)).rglob("*") if p.is_file()]}
    if block["staging_files_remaining"]:
        raise ValueError("Unexpected owned staging files remain")
    atomic_json(out/"source_drive_gate.json",block)
    test={"status":"PARTIAL_NOT_FULL_REVIEW_PASS","new_review_unit_tests_executed":8,"unit_failures":0,"unit_errors":0,"unit_skips":0,
        "current_171_tests":{"status":"NOT_RUN_PENDING_TEST_SCOPE_CONFIRMATION","executed":0,
            "reason":"Some existing fixture tests create optimizers/backward. One researcher clarification remains unanswered; no approval inferred."},
        "full_review_artifact_tests":{"status":"NOT_RUN_SOURCE_DRIVE_UNAVAILABLE","executed":0,"implemented":11},
        "no_2025_path_and_operation_guards":"8 actually executed unit tests include negative safety probes; no optimizer object or backward was executed",
        "historical_tests_not_substituted_for_execution":True}
    atomic_json(out/"test_summary.json",test)
    status={"run_id":out.name,"state":"BLOCKED_SOURCE_DRIVE_UNAVAILABLE","updated_utc":block["checked_utc"],**status_defaults(),
        "BEST_CHECKPOINT_VERIFIED":True,"HISTORY_ANALYSIS_COMPLETED":True,"HISTORY_FIGURES_COMPLETED":True,
        "VALIDATION_SCENES_INFERRED":0,"VALIDATION_PIXELS_READ":0,"CURRENT_171_TESTS_RERUN":False,
        "NEW_REVIEW_UNIT_TESTS_EXECUTED":8,"FULL_REVIEW_ARTIFACT_TESTS_EXECUTED":0,
        "FULL_POPULATION_NUMERICAL_CHECKS_STATUS":"NOT_RUN","CHECKPOINT_SELECTION_REMAINS_EPOCH_11":True,
        "FORMAL_CHECKPOINT_UNCHANGED":True,"ALL_BASELINE_FILES_UNCHANGED":True,
        "blocking_conditions":["H drive unavailable","Existing 171-test fixture scope clarification pending"]}
    atomic_json(out/"final_status.json",status)
    at={int(r["epoch"]):r for r in epoch}
    comparison="| epoch | Train core | Val core | Brier | AUROC | AP | conditional pinball | historical BEST | ES count |\n|---:|---:|---:|---:|---:|---:|---:|---:|---:|\n"
    for n in (9,11,12,13,15,19):
        r=at[n]
        comparison += "| "+" | ".join([str(n)]+[format(float(r[k]),".10f") for k in ("train_core","val_core","Brier","AUROC","AP","conditional_pinball")]+[r["best_checkpoint_at_epoch"],r["early_stop_count"]])+" |\n"
    gap_table="| epoch | Train core | Val core | Val - Train |\n|---:|---:|---:|---:|\n"
    for n in (1,3,6,9,11,15,19):
        r=gap[n-1]
        gap_table += f"| {n} | {float(r['train_core_loss']):.10f} | {float(r['val_core_loss']):.10f} | {float(r['generalization_gap']):.10f} |\n"
    historical_val=read(FORMAL/"epoch_011.json")["validation"]
    summary=(f"Brier={historical_val['Brier_Score']:.12f}, AUROC={historical_val['AUROC']:.12f}, "
        f"AP={historical_val['Average_Precision']:.12f}, conditional mean pinball={historical_val['conditional_mean_pinball']:.12f}")
    delta=float(at[19]["val_core"])-float(at[11]["val_core"])
    history_findings=(f"OBSERVED：epoch 11→19，Train core 从 {at[11]['train_core']} 降至 {at[19]['train_core']}，"
        f"Val core 从 {at[11]['val_core']} 升至 {at[19]['val_core']}，增加 {delta:.12f}（相对 epoch 11 约 {delta/float(at[11]['val_core'])*100:.4f}%）。"
        "epoch 12–19 均未优于 epoch 11；epoch 19 的独立 early-stop counter 达到 8。该记录支持‘验证损失在 epoch 11 后未继续改善并总体上升’的描述，"
        "不据此定义‘严重过拟合’，也不确立气象物理原因。")
    tail_text="\n".join(f"- {name}：{v['tau_count']} 个 tau，mean absolute coverage error={v['mean_absolute_coverage_error']:.12f}。" for name,v in tail.items())
    unavailable=("本轮完整 2024 再推理、monthly_metrics、空间 cell diagnostics、reliability、概率分布、雨强分层、强降水子集、客观案例"
        "及全量 quantile numerical checks 均为 NOT_RUN_SOURCE_DRIVE_UNAVAILABLE。没有用既有总体指标或抽样填充这些产物。"
        "全量覆盖、monthly/spatial/rain-bin/probability-bin 对账和新再推理 coverage 精确复现测试未执行，不能当作 PASS。")
    report=f"""# B0 Phase-A Scientific Characterization Review v1

状态：**BLOCKED_SOURCE_DRIVE_UNAVAILABLE / REVIEW INCOMPLETE**。

Review run：`{out.name}`；baseline：`5383dfceda6cc64e6907c6953032a14935c0ee46`。
Scope：`SCIENTIFIC_RESULT_REVIEW_ONLY`。正式 training run：`{FORMAL.name}`。

## 执行结果与阻塞证据

真实全量再推理已启动，但第一个 B13 staging read 的 `resolve(strict=True)` 返回 WinError 3 / FileNotFoundError；当前文件系统 drive 列表没有 H。
第一场样本未进入模型，scenes inferred=0、Validation pixels read=0、2025 pixels read=0。
失败 trace 保存在 `{failures[-1].name}` 与 `reinference_console.log`；私有 read ledger 长度为 0；本 run staging 内无临时文件残留。
F 盘第一日 IMERG 路径可见。没有把其它盘、其它时间或其它来源替换为冻结 H 源。

{unavailable}

## 正式身份核验

Protocol v1.0、Scientific Freeze v1.1 文档与配置、engineering v4、Phase-A 2023 normalization、Train/Validation manifests、SP04 和云南 mask 的全部冻结 SHA 均核验通过，见 `identity_verification.json`。
正式 BEST：epoch=11，global_update=64460，global_val_core_loss=0.04730775889882134。
路径：`{best['absolute_local_path']}`；bytes={BEST_BYTES}；SHA256=`{BEST_SHA}`。
checkpoint full payload 对原始 `checkpoint_expected` 核验通过；只把 model state 加载到独立推理模型，不实例化或恢复 optimizer。
收尾复核原有 {preserved['files_checked']} 个 baseline 文件的 SHA 未变，BEST 文件 SHA 与大小未变。

`CHECKPOINT_SELECTION_REMAINS_EPOCH_11`。冻结 criterion 是 minimum global_val_core_loss。
epoch 13 的 AUROC/AP 较 epoch 11 高、epoch 15 的 Brier 较 epoch 11 低、epoch 12 的 conditional pinball 较 epoch 11 低，都不能事后替换 criterion 或 BEST。

## 19 epoch 学习曲线和比较

只使用原始 `training_history.csv` 与 `validation_history.csv` 的完整 19 epoch 数值生成 6 张 600 dpi 图。
Train/Val core、occurrence、quantile loss、Val Brier/AUROC/AP、conditional pinball、历史 LR、gradient norm/clipping fraction 和 generalization gap 均已绘制。
BEST=11 与 early-stop=19 标记可见；没有平滑、删点或省略不利 epoch。LR 图显示 history 的真实 epoch start/end 值，未伪造每 update 的观测。
表中 historical BEST/ES count 来自原有 epoch JSON，不对 checkpoint 进行新选择。

{comparison}

{history_findings}

## 泛化差距

gap 固定为 Val core − Train core，逐 epoch 记录在 `generalization_gap.csv`。
Train 是 2023、Val 是 2024；Train occurrence 使用原有生产 AMP/FP32 算法，Val numerator 使用冻结 float64 算法。
因此 gap 是所定义的记录值差，不能将其全部归因于数据泛化、物理过程或单一精度因素。

{gap_table}

## 历史 epoch 11 的概率指标与 quantile 校准

下列全部来自已核验的正式 epoch 11 历史统计，**不是本轮再推理结果**。
N_valid=40,223,610；N_rain=4,809,183；prevalence={historical_val['prevalence']:.12f}。
{summary}。
DIAGNOSTIC_PROXY 为 p_rain × mean(32 physical conditional quantiles)，不是 exact expected precipitation。

tau=0.015625 的历史 coverage={calibration[0]['conditional_coverage']:.17g}，coverage−tau={calibration[0]['coverage_minus_tau']:.17g}。
这直接显示该最低 quantile 的历史 coverage 低于名义 tau。全部 32 个历史值与误差另存 `historical_quantile_calibration.csv`，没有变动 quantile、sort、clamp 或校准模型。

以下分组均为 `ANALYTIC_GROUPING_ONLY`：low tau<0.2；middle 0.2≤tau≤0.8；high tau>0.8。

{tail_text}

历史 epoch 11 crossing/nonfinite 为 0；**本轮全量 numerical count 为 null / NOT_RUN**，历史 0 不替代新检查。
单调性与校准是不同性质；历史严格单调不表示 coverage 已贴合 tau。

## 预声明诊断规则与空间边界

`case_selection_rules.json` 在再推理启动前已保存：10 个等宽 reliability bins（末 bin 包含 1）、7 个 true-rate bins、>10/20/30/50 的 DESCRIPTIVE_ONLY 子集，
以及三种固定 top-10 case 规则（最大绝对 proxy error、最高 truth rate、最低 rainy truth rate），ties 使用冻结 scene order 和 row-major cell index。
真实 rainy label 在 float32 target 上判定 R>0.1，再提升到 float64；没有改动生产阈值边界。
空间 conditional pinball 仅在 rainy_count≥30 时显示，规则为 DISPLAY_DIAGNOSTIC_ONLY；评价计数和 loss 样本不变。
没有发现 config/src/scientific_freeze/training_protocol 中预冻结 subregion masks：`NO_PREDEFINED_SUBREGION_MASK_AVAILABLE`。
因此准备使用 Yunnan-wide cell diagnostics，不创建事后地区，不从误差地图改 mask 或 loss weight。
由于 H 不可访问，本轮没有生成上述全量统计、case 结果或空间图。

## B0 的科学角色与解释边界

B0 是 `CONTROL / BASELINE`：只使用 latest causal Himawari B13 single frame。
没有 multi-temporal、multi-channel、GFS、DEM/terrain、DOTE、DTFM、MEE 或 ERA5 teacher。
这是设计事实，不等同于已证明某种缺失信息导致某个误差；B0 不能独立证明完整 YunTAPR-Net 有效。
月份差异、空间差异和强降水稀疏性在本轮未获新统计支持，不作结论。
具体天气成因均为 `POSSIBLE_EXPLANATION_NOT_ESTABLISHED`；没有以 hypothesis 替代 observed。

## 测试与科研授权

新增 8 项 unit tests 真实执行，通过、零 failure/error/skip，见 `test_results.txt`。
这些检查覆盖 probability edges/1.0、weighted percentiles、float32 threshold、toy count reconciliation、2025/path escape 拒绝、optimizer/step/backward 硬 guard 和分开的 quantile numerical counts。
现有 171 项未重跑：部分独立 fixture 会执行 optimizer/backward，已向研究者发出一项范围确认，尚未收到答复；没有把历史 171 PASS 当作本轮结果。
11 项 full-review artifact tests 已编写，因全量产物缺失未执行。测试总体为 PARTIAL_NOT_FULL_REVIEW_PASS。

`B0_PHASE_A_SCIENTIFIC_REVIEW_COMPLETED=false`；`FULL_2024_REINFERENCE_COMPLETED=false`。
`B0_PHASE_A_ACCEPTED=UNDECIDED`；`TRANSFER_EPOCH_BUDGET_TO_PHASE_B=UNDECIDED`；`PHASE_B_AUTHORIZED=false`。
没有训练、epoch 20、模型更新、normalization 拟合、校准、阈值选择或 B1–B8 执行。
需要 H 恢复以及测试范围答复后，另建可追溯完整 review run；本次失败记录保留，不自动进入下一 Stage。
"""
    (out/"B0_PHASE_A_SCIENTIFIC_REVIEW.md").write_text(report,encoding="utf-8",newline="\n")
    inventory=f"""# B0 limitation inventory — partial history evidence

Review `{out.name}` 未完成完整再推理。以下区分已观察、设计事实和待核验。

| Item | Evidence class | Current evidence / limit |
|---|---|---|
| Epoch 11 后 Validation degradation | OBSERVED | {history_findings} |
| 最低 tau calibration deviation | OBSERVED_HISTORICAL_ONLY | tau=0.015625，正式历史 coverage={calibration[0]['conditional_coverage']:.17g}；本轮未再推理。 |
| 月份差异 | NOT_EVALUATED_THIS_REVIEW | 完整月度分析缺失，不能给月份排名或物理解释。 |
| 空间差异 | NOT_EVALUATED_THIS_REVIEW | 尚无本轮 cell-level 统计；未创建 subregions。 |
| 强降水样本稀疏 | NOT_ESTABLISHED_THIS_REVIEW | 未计算 >10/20/30/50 计数；不推断稀疏程度或 extreme 定义。 |
| single-band / single-time 信息限制 | DESIGN_FACT | 输入仅 B13 一帧；不存在多通道/时序/GFS/地形/teacher。不能直接归因为某个误差。 |
| Historical probability calibration | OBSERVED_HISTORICAL_ONLY | 单调性不保证 coverage；各 tau 历史校准误差已列表。没有进行再校准。 |
| 科学因果解释 | HYPOTHESIS_NOT_ESTABLISHED | 云顶—地面降水非唯一性等尚无额外变量证据，不作为结论。 |
| 数据可用性 | ENGINEERING_BLOCKER | 当前 H 不可见；第一场未进入模型；不是已经完成的科研链回退。 |

接受 Phase-A 与是否迁移预算由研究者决定；本 packet 未完备，Phase-B 仍未授权。
"""
    (out/"B0_LIMITATION_INVENTORY.md").write_text(inventory,encoding="utf-8",newline="\n")
    packet=f"""# B0 Phase-A researcher decision packet — INCOMPLETE

Review `{out.name}`。**不能把这份 partial packet 视为完整 Scientific Characterization Review 通过。**

## A. Protocol compliance

冻结身份与 BEST 核验 PASS，{preserved['files_checked']} 个 baseline 文件及 BEST 未修改。没有训练、optimizer step/backward、2025 pixels 或下一 Stage。
正式协议符合性以原有 run evidence 为历史输入，本轮 171-test rerun 尚未执行。

## B. Training convergence evidence

{history_findings}

## C. Selected checkpoint identity

epoch 11；update 64460；Val core 0.04730775889882134；bytes {BEST_BYTES}。
`{best['absolute_local_path']}`；SHA `{BEST_SHA}`。`CHECKPOINT_SELECTION_REMAINS_EPOCH_11`。

## D. Occurrence performance

HISTORICAL_ONLY：{summary}。固定-bin reliability 和 rainy/dry probability distributions 尚未计算。

## E. Probabilistic quantile performance

冻结 32 个 tau；历史 conditional pinball 已列表。本轮 full float64 numerical checks 未执行。

## F. Calibration diagnostics

最低 tau 历史 coverage={calibration[0]['conditional_coverage']:.17g}；32 项历史 calibration 表与 analytic-only tail grouping 已保存。
完整再推理精确 coverage reproduction 尚未执行，不能以历史统计替代。

## G. Monthly/spatial/rain-rate weaknesses

NOT_RUN_SOURCE_DRIVE_UNAVAILABLE。没有预冻结 subregion masks，未来只按原冻结 Yunnan mask 做 cell diagnostics。
未据模型输出画区域、选择阈值或调整训练。

## H. Known limitations

见 `B0_LIMITATION_INVENTORY.md`。已观察的 history loss 回升和最低 tau 误差，与单帧单通道设计事实分别表述。
月份、空间与强降水限制尚缺本轮证据。

## I. Open questions / missing gates

- 需要冻结 H 源重新可见；不使用另源替代 11,727 场完整样本。
- 研究者尚未答复：是否允许既有 171 tests 在独立 fixture 执行 optimizer/backward，同时审阅进程硬禁止这些操作。
- 尚缺 full population metrics、所有计数对账、full artifact tests 和完整图件。
- 具体物理误差原因未确立；项目 extreme definition 仍为 NOT_FROZEN。

## J. Researcher decision required

`ACCEPT_B0_PHASE_A=UNDECIDED` / `B0_PHASE_A_ACCEPTED=UNDECIDED`。
`TRANSFER_EPOCH_BUDGET_TO_PHASE_B=UNDECIDED`。
`PHASE_B_AUTHORIZED=false`；`B1_TO_B8_AUTHORIZED=false`。
本轮没有替研究者决定接受、迁移预算或启动 Phase-B。
"""
    (out/"B0_PHASE_A_RESEARCHER_DECISION_PACKET.md").write_text(packet,encoding="utf-8",newline="\n")
    manifest=read(out/"review_manifest.json")
    manifest.update(last_updated_utc=block["checked_utc"],final_status="BLOCKED_SOURCE_DRIVE_UNAVAILABLE",
        original_formal_sources_preserved=True,full_reinference_completed=False,
        preservation=preserved,additional_code_sha256={p:sha256(ROOT/p) for p in
            ("scripts/plot_b0_scientific_review_v1.py","scripts/report_b0_review_blocked_v1.py",
             "tests/scientific_review/test_review_units.py","tests/scientific_review/test_review_full_artifacts.py")})
    atomic_json(out/"review_manifest.json",manifest)
    artifacts={str(p.relative_to(out)).replace("\\","/"):{"bytes":p.stat().st_size,"sha256":sha256(p)}
        for p in out.rglob("*") if p.is_file() and p.name!="artifact_sha256.json"}
    atomic_json(out/"artifact_sha256.json",artifacts)
    print(json.dumps({"run_id":out.name,"state":status["state"],"history_figures":fig["figure_count"],"new_units_passed":8,
        "full_review_completed":False,"BEST_unchanged":True,"baseline_files_unchanged":preserved["files_checked"]}))


if __name__=="__main__":
    main()
