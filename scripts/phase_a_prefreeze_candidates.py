"""Build an unselected researcher decision package from measured pre-freeze evidence."""
from pathlib import Path
import json
import math
import subprocess
import sys
from audit_phase_a_prefreeze import (ROOT, BASELINE, PRIOR, GPU, STAGING, read_json, read_csv,
                                    save, text_file, table, sha256)

SOURCES = {
    "AdamW": "https://docs.pytorch.org/docs/2.11/generated/torch.optim.AdamW.html",
    "GroupNorm": "https://docs.pytorch.org/docs/2.11/generated/torch.nn.GroupNorm.html",
    "Reproducibility": "https://docs.pytorch.org/docs/2.11/notes/randomness.html",
    "Average_precision": "https://scikit-learn.org/stable/modules/generated/sklearn.metrics.average_precision_score.html",
}


def package(out):
    lock = read_json(out/"baseline_lock.json")
    prevalence = read_json(out/"train_occurrence_prevalence.json")
    rain = read_json(out/"train_rainrate_distribution.json")
    alpha = read_json(out/"focal_alpha_candidates.json")
    focal = read_json(out/"focal_implementation_audit.json")
    heads = read_json(out/"head_architecture_audit.json")
    param = read_json(out/"model_parameter_groups.json")
    smoke = read_json(out/"loss_scale_smoke.json")
    tests = read_json(out/"test_summary.json")
    monthly = read_csv(out/"train_occurrence_monthly.csv")
    prior_gpu = read_json(GPU/"engineering_recommendation.json")
    stability = read_json(GPU/"gpu_stability_smoke.json")
    gpu_rows = read_csv(GPU/"gpu_amp_benchmark.csv")
    cpu_before = read_json(out/"reproducibility_settings.json")
    validations = {
        "population_sizes_and_mask": (lock["train_scenes"],lock["validation_scenes"],lock["yunnan_target_cells"]) == (11720,11727,3430),
        "complete_2023_only_prevalence": prevalence["scenes"] == 11720 and prevalence["N_valid"] == 40199600 and prevalence["years"] == [2023],
        "counts_partition": prevalence["N_positive"]+prevalence["N_negative"] == prevalence["N_valid"],
        "eight_months_reconcile": len(monthly) == 8 and sum(int(r["positive_pixels"]) for r in monthly) == prevalence["N_positive"],
        "rainy_distribution_reconciles": rain["count"] == prevalence["N_positive"],
        "all_245_IMERG_days_hashed_cleaned": prevalence["staging_operations"] == 245 and prevalence["all_cleanup_success"],
        "alpha_semantics_verified": focal["FOCAL_ALPHA_SEMANTICS"] == "ALPHA_IS_POSITIVE_CLASS_WEIGHT",
        "alpha_not_selected": alpha["recommended_alpha"] is None,
        "eight_forward_only_samples": len(smoke["samples"]) == 8 and smoke["status"] == "PASS" and smoke["no_backward"] and smoke["parameters_unchanged"],
        "old_126_tests_pass": len(tests) == 8 and sum(t["tests"] for t in tests[:7]) == 126 and all(t["pass"] for t in tests),
        "no_2025_pixels": not prevalence["2025_pixels_read"],
    }
    save(out/"artifact_validation.json", validations)
    if not all(validations.values()):
        raise RuntimeError("Evidence package gate failed")
    p = prevalence["positive_fraction"]
    balanced = alpha["candidates"][2]["alpha"]
    text_file(out/"validation_metric_candidates.md", r"""# Validation metric candidates — RESEARCHER_DECISION_REQUIRED

All definitions below pool only eligible 2024 Validation pixels with
`m = IMERG_valid AND Yunnan_evaluation_mask`. Labels are `y=1[R>0.1 mm/h]`.
No metric has been computed on 2025, and no decision threshold was optimized.

## Checkpoint loss A and B

Let D=sum(m) over every validation sample/batch. Accumulate in float64:

\[
 S_o=\sum m\,\alpha_t(1-p_t)^\gamma\operatorname{BCEWithLogits}(z,y),\qquad
 S_q=\sum m y\,\frac1{32}\sum_{i=1}^{32}\rho_{\tau_i}(\log(1+R)-q_i).
\]

Candidate A: `val_core_loss=(S_o+S_q)/D`.
Candidate B: `val_occurrence_loss=S_o/D`, `val_quantile_loss=S_q/D`, then their sum.
A and B are mathematically equivalent with the SAME global valid denominator,
mask, fixed alpha/gamma, quantile precision and quantile-axis mean.
Accumulate raw numerators before division, rather than recovering them from
rounded batch losses. Average batch losses only with weights D_batch/D_total;
an unweighted mean changes the metric when the last batch is smaller or valid
counts differ. D=0 means undefined/reject, not a passing or zero metric.

Example: batches with D=(8,1), core numerators=(24,30) give 54/9=6;
unweighted batch means give (3+30)/2=16.5. Tests verify partition invariance.

Candidate checkpoint action: minimize global val_core_loss; candidate exact-tie
rule is earliest epoch. Neither metric nor tie handling is selected here.
Validation is eval/no_grad with identical AMP/precision policy. Nonfinite output,
nonfinite numerator, invalid causal/QC sample or crossing requires an explicit
failure. Do not silently reduce the frozen validation population.

## Occurrence report

Brier score: sum(m*(p_rain-y)^2)/D, pooled pixel weighting.
AUROC: P(score_positive>score_negative)+0.5*P(tie), pooled valid pixels.
No positive or no negative class makes AUROC undefined; log counts and NA.
AUPRC needs a pinned convention: candidate non-interpolated Average Precision,
AP=sum_k (recall_k-recall_(k-1))*precision_k. Group equal scores at one threshold;
this differs from trapezoidal PR-AUC. No-positive cases report NA plus counts.
The [official AP definition](https://scikit-learn.org/stable/modules/generated/sklearn.metrics.average_precision_score.html)
supports this convention; this audit installs no sklearn dependency.
Always report prevalence because PR summaries depend on it. These pooled pixels
are temporally/spatially dependent; no independent-pixel significance claim is made.

The physical event threshold 0.1 mm/h does not justify probability cutoff 0.1.
`THRESHOLD_NOT_YET_FROZEN`: no scientific basis has been supplied for a binary
probability decision threshold. POD=TP/(TP+FN), FAR=FP/(TP+FP),
CSI=TP/(TP+FN+FP) all require an approved probability cutoff and comparator
(candidate `p_rain >= t_prob`); zero denominators are NA. Do not use a 2024-optimal
cutoff on Final Test without a separately approved calibration/threshold protocol.

## Conditional quantiles

q_i is log1p conditional on R>0.1; tau_i=(i-0.5)/32.
Per-tau conditional pinball: sum(m*y*rho_tau_i(log1p(R)-q_i))/N_rain.
Mean conditional pinball: average over 32 taus of that metric.
Core quantile loss instead divides by D, so L_qr=(N_rain/D)*mean_conditional_pinball.
When N_rain=0, conditional diagnostic is NA; current core skips the rainy term
with differentiable zero. Keep both denominators explicit.
Conditional coverage C_i=sum(m*y*1[log1p(R)<=q_i])/N_rain; compare C_i with tau_i
as a calibration diagnostic. Pin the <= convention and report per-tau counts.
Pooling does not establish conditional calibration for every month/location.
Adjacent crossing count=sum(1[q_(i+1)<=q_i]) must be zero for all emitted grids,
with nonfinite checks and q_1>log1p(0.1) separately required. No posthoc sort.
No complete CRPS: the 32-point conditional support and unresolved tails/drizzle
component do not establish a complete unconditional predictive distribution.

## Deterministic proxy only

d=p_rain*(1/32)*sum_i expm1(q_i) is the probability-weighted 32-point midpoint
threshold-censored diagnostic. It omits 0–0.1 drizzle and unresolved tails and
is not exact E[R]. Optional MAE=sum(m*abs(d-R))/D,
RMSE=sqrt(sum(m*(d-R)^2)/D), signed Bias=sum(m*(d-R))/D are all
`DIAGNOSTIC_PROXY_METRIC`, never posterior-mean precipitation error or exact
expected-rainfall RMSE. No threshold or metric selection is made by this audit.
""")
    text_file(out/"optimizer_candidates.md", f"""# Optimizer candidates — RESEARCHER_DECISION_REQUIRED

No optimizer object or optimizer state was created. AdamW is a candidate only.
beta1=0.9, beta2=0.999, eps=1e-8 are **DEFAULT_REFERENCE**, verified from installed
torch 2.11.0's signature and [PyTorch 2.11 AdamW]({SOURCES['AdamW']}). Defaults
are API references, not scientific truths. Weight decay grid 0, 1e-4, 1e-3,
1e-2 is an explicit unselected candidate grid; no value is adopted.

| Count | Parameters |
|---|---:|
| Total trainable | {param['total_trainable_params']} |
| Bias, including GroupNorm beta | {param['bias_params_including_GroupNorm_beta']} |
| GroupNorm affine gamma+beta | {param['GroupNorm_affine_params']} |
| Bias/GroupNorm overlap | {param['bias_GroupNorm_overlap_params']} |
| Conv weights, including heads | {param['Conv_weight_params_including_heads']} |
| Head weights, subset of Conv weights | {param['head_weight_params_subset_of_Conv']} |

Counts overlap as stated; summing every row would double count. Full named groups
and set-partition assertions are in model_parameter_groups.json.

Candidate A explicitly means decay **every trainable parameter**, including
bias and GroupNorm affine, {param['A_decayed_params']} elements. This avoids an
implicit interpretation of 'weights' that changes treatment of biases.
Candidate B decays Conv kernels only ({param['B_decayed_params']} elements),
excluding every bias and GroupNorm affine parameter ({param['B_no_decay_params']}).
The exclusion set is a union, so GroupNorm beta is not counted twice.
A shrinks biases and normalization scale/offset; B leaves those affine degrees
unshrunk. Decoupled decay interacts with LR and number of optimizer updates;
effective batch changes update frequency. No claim of better validation skill.

Two float32 Adam moments alone would add approximately
{8*param['total_trainable_params']/1024**2:.2f} MiB persistent state. This is
arithmetic, not an allocation measurement; foreach/fused temporaries, step latency
and full optimizer VRAM were not benchmarked. Prior GPU headroom is forward/backward
evidence. Future authorized training must log AdamW implementation flags, groups,
LR, decay, betas, eps and real optimizer memory.
""")
    text_file(out/"scheduler_candidates.md", r"""# Scheduler candidates — RESEARCHER_DECISION_REQUIRED

| Candidate | Explicit candidate definition | FINALFIT_REPLAY_COMPLEXITY | Reason |
|---|---|---|---|
| Constant LR | eta(u)=eta0 for every optimizer update | LOW | No validation-triggered schedule; still pin steps, budget and LR |
| Warmup + Cosine | linear eta0*(u+1)/W during W updates; then eta_min+(eta0-eta_min)*(1+cos(pi*(u-W)/(U-W)))/2 | MEDIUM | Must define update-vs-epoch clock, W, U, eta_min and replay alignment |
| ReduceLROnPlateau | after each global 2024 validation metric, reduce LR by factor after patience non-improvements | HIGH | FinalFit consumes 2023+2024 and has no same held-out 2024 control signal |

Warmup candidates 0, 1 or 3 epochs, minimum LR ratio 0, 0.01 or 0.1; no choice.
Cosine formula assumes W<U and a pinned endpoint/step-index convention;
W=0 skips warmup. Updates depend on accumulation; changing effective batch
changes U even if epochs are equal. Pin whether FinalFit replays normalized epoch
progress or an absolute update sequence; these are not automatically equivalent.

Plateau candidates factor 0.1 or 0.5, patience 2 or 3 validation calls, minimum
LR 1e-6 or 1e-5; no choice. Metric, min_delta/threshold mode, cooldown, ordering
relative to validation and early stopping must be pinned. In Phase B, directly
feeding 2024 into the same scheduler would reuse training data as control data.
Possible future approved replay options are a recorded LR sequence mapped to
progress, or a fully predetermined replacement schedule; neither is selected.
Never use 2025 to trigger changes. Complexity labels are engineering assessments
of the proposed replay conditions, not measured model-performance results.
""")
    text_file(out/"epoch_earlystop_candidates.md", r"""# Epoch, early stopping and clipping candidates

All entries are RESEARCHER_DECISION_REQUIRED and unselected.
max_epochs candidates: 30, 50, 80.
Early-stopping patience candidates: 5, 8, 10 validation calls, if validation is
once per completed epoch. Absolute min_delta candidates: 0, 1e-4, 1e-3 in
global val_core_loss units; they need scale/sensitivity review, not interpretation
as physical rainfall units. Candidate improvement: new_loss < best_loss-min_delta.
Record exact strict/tie comparison, initial best value, skipped-validation policy,
minimum epoch/warmup guard and whether stopping counts begin after warmup.
Checkpoint minimum/tie policy and early-stop min_delta serve different purposes;
do not silently substitute one for the other.

The pre-development candidate max cap and patience must be approved before fitting.
The final epoch budget to transfer to Phase B is then decided from Phase-A
development evidence using 2024 Validation, under an approved transfer rule.
Candidate transfer summaries include the selected checkpoint epoch or a specified
multi-seed aggregation rule; no transfer summary is selected now. FinalFit cannot
consult 2025 for epoch choice. No Phase-B normalization is computed here.

Gradient clipping candidates: none; global_norm=1.0; global_norm=5.0.
Global norm means sqrt(sum over every parameter of ||gradient||_2^2). Clipping
rescales gradients when norm exceeds the candidate cap and may limit unusually
large updates; no performance conclusion follows. Future authorized training must
log pre-clip norm, cap, whether clipping occurred, post-clip norm/action and
nonfinite handling. If AMP loss scaling is adopted, unscale before norm/clipping.
No gradients were generated by this task's real-data forward diagnostics.
""")
    minutes = 31.19
    cost = []
    for epochs in (30,50,80):
        for policy,runs in (("B0_SINGLE_SEED",1),("B0_THREE_SEEDS",3),("ALL_B0_B8_SINGLE_SEED",9),
                            ("ALL_B0_B8_THREE_SEEDS",27),("MAIN_ONE_KEY_TWO_MODELS_THREE_SEEDS_EXAMPLE",13)):
            cost.append({"policy":policy,"epochs_per_seed":epochs,"seed_model_runs":runs,
                         "B0_reference_minutes_per_epoch":minutes,"wall_hours_arithmetic":minutes*epochs*runs/60,
                         "status":"ENGINEERING_ESTIMATE_ONLY"})
    table(out/"seed_gpu_time_cost_candidates.csv",cost)
    text_file(out/"seed_policy_candidates.md", f"""# Seed and reproducibility candidates

All seed policies and values are unselected, RESEARCHER_DECISION_REQUIRED.
A: one fixed seed, identical across the complete B0–B8 main ablation.
B: three prespecified seeds, each used for all B0–B8, reporting each run and a
specified aggregate/dispersion. An illustrative candidate set is 17, 42, 2026;
these values are not chosen or tested as performance hyperparameters.
C: one seed for main ablation, three seeds for specified key models. Different
repeat counts make uncertainty precision unequal; do not compare three-seed
means against one-seed points as if replication were balanced. If K key models
receive two additional seeds, total seed-model runs=9+2K (K=2 gives 13).

At 31.19 min/epoch from the earlier B0 engineering estimate, 30/50/80 epochs cost
15.595/25.992/41.587 hours per B0 seed. Three seeds multiply by three. The CSV
also shows 9-model and mixed examples, assuming EVERY model had B0 throughput;
future B1–B8 may differ substantially. Optimizer, checkpoint and sustained full
epoch changes can alter real time; these are arithmetic cost scenarios only.

Before authorized training, pin Python random seed, NumPy seed, torch CPU seed,
all CUDA seeds, DataLoader generator and worker seed derivation. Candidate worker
derivation uses torch.initial_seed()%2**32 to initialize NumPy/Python, with a
separately seeded generator; exact epoch/worker/persistent-worker behavior and
shuffle order must be recorded. Cross-model initialization differs by shape,
so equal seed alone is not identical random-number consumption or initialization.
The forward diagnostic's isolated seed 20261001 is an audit fixture, not a
recommended formal seed. Its RNG state and temporary thread count were restored.

Read-only current settings are in reproducibility_settings.json. Consider
torch.use_deterministic_algorithms(True), cuDNN determinism, benchmark and TF32
policies as a package. Deterministic kernels can lower performance and unsupported
operations can raise; versions/device still matter, and one seed does not promise
identical results across releases/platforms. These tradeoffs follow the
[PyTorch reproducibility guide]({SOURCES['Reproducibility']}). No deterministic,
TF32 or cuDNN setting was changed by this audit.
""")
    text_file(out/"b0_b8_fairness_contract_candidate.md", r"""# B0–B8 fairness contract candidate

Status: RESEARCHER_DECISION_REQUIRED. A proposed shared experiment protocol,
not a scientific freeze or training authorization.

Every comparison must pin and share optimizer family/betas/eps/parameter-group
rule, LR policy and schedule clock, core loss family/alpha/gamma/reduction,
probability head architecture/semantics/numerics, checkpoint metric/tie rule,
validation metric definitions/masks/aggregation/threshold protocol, seed policy,
and training budget/early-stop/FinalFit replay policy.
Shared engineering policies also include normalization-fit scope, eligibility,
AMP precision, accumulation weighting/tail policy, clipping and data shuffle.

B0–B3 retain the already specified shared backbone/decoder/SP04/heads/loss family,
with the approved input-information differences. B4–B8 add their protocol-defined
scientific modules; additions do not implicitly authorize new optimizers, losses,
heads, metrics, validation populations or seed/epoch budgets.
If a future B1–B8 changes any shared item, record the reason and reconsider fair
comparison; separate the module effect from protocol/tuning-budget effects.
If memory requires a different physical batch, preserve a researcher-approved
effective-batch/accumulation policy or disclose the confound. Effective batch,
epochs and number of optimizer updates are different notions of training budget;
the chosen fairness criterion must be explicitly approved. Freeze which settings
transfer from B0 and what model-specific tuning is allowed before results are seen.
Checkpoint and all tuning decisions use 2024 Development Validation only; 2025
is sealed from protocol selection. After Phase-A decisions, FinalFit replay must
be approved without 2025 feedback. No model or contract was changed here.
""")
    # The researcher explicitly requested no preferred scientific value.
    unselected = "未选择，待研究者决定"
    rows = [
      ("Focal alpha",f"正类权重；Train rain={p:.6%}",f"0.25; 0.50; balanced={balanced:.9f}","类别贡献及 L_occ 相对尺度","无新增算力",unselected,"prevalence 不证明最优性能","RESEARCHER_DECISION_REQUIRED"),
      ("Focal gamma","已核对 (1-p_t)^gamma", "0; 1; 2; 3 数学展示","easy/hard 相对贡献","算子成本小",unselected,"未训练的数学诊断","RESEARCHER_DECISION_REQUIRED"),
      ("Optimizer","参数分组计数与默认签名已测", "AdamW; beta=(.9,.999), eps=1e-8 DEFAULT_REFERENCE","优化动力学","状态/step 额外显存未实测",unselected,"需共同协议","RESEARCHER_DECISION_REQUIRED"),
      ("Weight decay / groups","A 全参数；B 排除 bias/GN", "decay 0;1e-4;1e-3;1e-2, A/B","正则化作用不同","参数组已完整列出",unselected,"无性能证据","RESEARCHER_DECISION_REQUIRED"),
      ("Learning rate","physical=2 的候选表", "5e-5;1e-4;2e-4;3e-4","更新尺度","线性 scaling 仅参考",unselected,"未做 LR 搜索","RESEARCHER_DECISION_REQUIRED"),
      ("Effective batch","updates=5860;2930;1465", "2;4;8 (accum=1;2;4)","梯度噪声/更新频率","physical 显存相同；accum 未执行",unselected,"需决定公平预算","RESEARCHER_DECISION_REQUIRED"),
      ("Scheduler","FinalFit replay 复杂度已分析", "Constant; warmup+cosine; Plateau","LR 演化","LOW;MEDIUM;HIGH",unselected,"Plateau 不可自动复用 2024 控制信号","RESEARCHER_DECISION_REQUIRED"),
      ("Max epochs / transfer","31.19 min/epoch 工程估算", "30;50;80; transfer rule 待定","模型选择/最终预算","optimizer 后时间可变",unselected,"最终预算依 Phase-A development 决定","RESEARCHER_DECISION_REQUIRED"),
      ("Early stopping","明确 validation calls 和比较式", "patience 5;8;10, absolute delta 0;1e-4;1e-3","停止/选择偏差","减少算力但触发动态",unselected,"需要记录每次调用和 min_delta","RESEARCHER_DECISION_REQUIRED"),
      ("Gradient clipping","仅提出 global-norm 定义", "none;1.0;5.0","限制更新","后续记录 pre/post/action",unselected,"未生成真实样本梯度","RESEARCHER_DECISION_REQUIRED"),
      ("Seed policy","时间成本按 B0 算术展开", "全体1 seed;全体3 seeds;混合","重复性/不确定性精度","约1x/3x算力",unselected,"混合重复程度不一致","RESEARCHER_DECISION_REQUIRED"),
      ("Determinism / TF32","当前设置只读登记", "deterministic True/False; TF32 policy","数值可复现性","性能可能变化",unselected,"种子和环境必须共同登记","RESEARCHER_DECISION_REQUIRED"),
      ("Checkpoint metric / ties","global numerator / global D 已定义", "A val_core_loss; B occ+qr (等价); tie earliest 候选","checkpoint 选择","可流式聚合",unselected,"不可简单平均不同大小 batch","RESEARCHER_DECISION_REQUIRED"),
      ("Validation metrics","精确定义候选集合", "Brier;AUROC;AP;pinball;coverage;crossing","报告与校准诊断","AUROC/AP 排序成本",unselected,"probability cutoff 未确定","RESEARCHER_DECISION_REQUIRED"),
      ("Probability cutoff / calibration","降水阈值与概率阈值已区分", "未指定；POD/FAR/CSI 需批准 cutoff","阈值迁移影响 Final Test","需要独立 calibration protocol",unselected,"概率阈值尚未确定","RESEARCHER_DECISION_REQUIRED"),
      ("Exact head architecture pin","代码为1x1 48→1 / 48→32，0 hidden", "沿用实际代码须研究者登记","容量与公平比较","不改 head",unselected,"HEAD_IMPLEMENTATION_DETAIL_REQUIRES_PROTOCOL_PIN","RESEARCHER_DECISION_REQUIRED"),
      ("B0–B8 fairness","共同项目与变化复核规则已提出", "统一 optimizer/LR/loss/heads/metric/seed/budget","消融归因","额外模型可能改变时间",unselected,"共享协议待批准","RESEARCHER_DECISION_REQUIRED"),
      ("Physical batch","FP32 batch2 reserved4420MiB; batch4余量失败", "2 既有工程证据","不得自动提升为科研协议","满足先前20%余量", "2，仅工程建议","复用已提交测量","EVIDENCE_READY"),
      ("AMP mode","BF16约3260MiB、12.23samples/s", "BF16/FP16/FP32 已测", "float64 quantile 合同保持","BF16稳定性通过", "BF16，仅工程建议","已有 GPU audit","EVIDENCE_READY"),
      ("Validation batch","eval/no_grad已测", "8 既有工程建议", "不影响全局聚合定义","batch16余量失败", "8，仅工程建议","已有 GPU audit","EVIDENCE_READY"),
      ("DataLoader workers","32scene active吞吐2/4近似，启动开销不同", "0;2;4 已测", "eligible/QC保持","worker独立staging", "2，仅工程建议","更少worker且吞吐接近最佳","EVIDENCE_READY"),
      ("Train descriptive evidence","11720 scenes 全量，40199600 valid pixels", "月度/条件雨量已统计", "未改 extreme threshold", "245天哈希读取完成", "EVIDENCE_READY", "仅2023统计","EVIDENCE_READY"),
    ]
    columns = ("Parameter","Current evidence","Candidate values","Scientific impact","Engineering impact","Recommended candidate","Reason","Status")
    decision = ["# RESEARCHER_DECISION_TABLE", "", "科研参数保持未选择；已有工程建议仅作为 ENGINEERING_EVIDENCE_READY。", "",
                "| "+" | ".join(columns)+" |", "|"+"---|"*len(columns)]
    for row in rows:
        if row[-1] not in ("EVIDENCE_READY","RESEARCHER_DECISION_REQUIRED"):
            raise ValueError("Invalid decision status")
        decision.append("| "+" | ".join(row)+" |")
    text_file(out/"RESEARCHER_DECISION_TABLE.md","\n".join(decision))
    final = {
        "PHASE_A_PROTOCOL_EVIDENCE_READY": True,"TRAIN_OCCURRENCE_PREVALENCE_READY": True,
        "FOCAL_ALPHA_SEMANTICS_VERIFIED": True,
        **{k+"_RESEARCHER_DECISION_REQUIRED": True for k in ("FOCAL_ALPHA","FOCAL_GAMMA","OPTIMIZER","LR","EFFECTIVE_BATCH","SCHEDULER","EPOCH_BUDGET","CHECKPOINT_METRIC","SEED_POLICY")},
        "HEAD_IMPLEMENTATION_DETAIL_REQUIRES_PROTOCOL_PIN": True,
        "B0_FORMAL_TRAINING_STARTED": False,"FORMAL_TRAINING_AUTHORIZED": False,
        "engineering_evidence_status": "ENGINEERING_EVIDENCE_READY", "scientific_parameter_selection": "NONE",
        "researcher_table_choice": "Unselected scientific candidates; prior engineering recommendations retained"}
    save(out/"final_status.json",final)
    save(out/"references.json", {"verified_on_UTC_date": "2026-10-01", "primary_documentation": SOURCES,
         "scope": "Optimizer defaults independently checked in installed torch 2.11; AP is a proposed definition, no external library installed."})
    rain_range = [float(r["rain_fraction"]) for r in monthly]
    report = ["# PHASE_A_PROTOCOL_PREFREEZE_REPORT", "", f"Run `{out.name}`; baseline `{BASELINE}`.", "",
      "本轮已完成训练协议冻结前的证据审计。所有科研参数保持未选择，供研究者决策；未创建 optimizer、未更新模型参数、未生成训练 checkpoint。D1–D8、eligible population、SP04、模型结构和概率语义均保持基线。", "",
      "## 最终状态", "", "```json", json.dumps(final,indent=2,ensure_ascii=False), "```", "",
      "## 基线与数据身份", "", "Scientific Freeze v1.1 / engineering v4；2023 Train=11720 scenes，2024 Validation=11727 scenes；主云南 mask=3430 target cells。所有引用 SHA 详见 baseline_lock.json。Train manifest 为既有 normalization sample manifest；Validation 既无独立历史文件，本轮从既有 combined eligibility 的2024 eligible行生成身份视图，按 window_start 排序，其SHA独立登记。未改变样本资格。", "",
      "| Evidence | SHA256 |", "|---|---|"]
    report += [f"| {name} | `{info['sha256']}` |" for name,info in lock["references"].items()]
    report += ["", "## 当前 focal 与 core loss 的精确公式", "",
      r"对每个像元：$z$为logit，$y=1[R>0.1]$，$p=\sigma(z)$，$b=\mathrm{softplus}(z)-yz$，$p_t=\exp(-b)=yp+(1-y)(1-p)$。",
      r"$\alpha_t=\alpha y+(1-\alpha)(1-y)$。$m=\mathrm{IMERGvalid}\land\mathrm{YunnanMask}$，$D=\sum m$。",
      r"$$L_{occ}=\frac{\sum m\,\alpha_t(1-p_t)^\gamma b}{D}.$$",
      "FOCAL_ALPHA_SEMANTICS=ALPHA_IS_POSITIVE_CLASS_WEIGHT。focal_bce_sum 返回 masked sum；b0_core_loss 再除以有效云南监督像元数。γ只作用于真实类别概率的(1−p_t)因子。α=0.5不改变正负相对权重，但将未加权 BCE/focal 整体缩小一半；它不是完全无尺度变化。", "",
      r"$\tau_i=(i-0.5)/32$，$u_i=\log(1+R)-q_i$，$\rho_\tau(u)=\max(\tau u,(\tau-1)u)$。",
      r"$$L_{qr}=\frac{\sum my\,\frac1{32}\sum_i\rho_{\tau_i}(u_i)}{D},\qquad L=L_{occ}+L_{qr}.$$",
      "quantile axis=mean；分子只统计rainy valid云南像元，分母仍为全部valid云南监督像元。无雨时core L_qr为零，conditional-only诊断为NA；无valid时current loss跳过，proposed validation metric应报告undefined。qlog/qphysical/pinball保持float64。两个损失共享分母不保证数值尺度相近。", "",
      "## 全量2023 occurrence与雨量", "",
      f"逐日读取全部245个2023 IMERG V07 Final文件，仅解码对应eligible slots；来源哈希与既有审计一致，大小/SHA验证和清理全部成功。N_valid={prevalence['N_valid']:,}，N_positive={prevalence['N_positive']:,}，N_negative={prevalence['N_negative']:,}；positive_fraction={p:.9%}，negative_fraction={1-p:.9%}，negative_to_positive_ratio={prevalence['negative_to_positive_ratio']:.6f}。所有selected像元统计与历史逐时次目标计数一致。R==0.1属于negative；精确遵循生产float32比较，不加容差/重分箱。数据中恰等于float32(0.1)的数量为0。", "",
      "| Month | Scenes | Valid pixels | Positive | Negative | Rain fraction | Dry fraction |", "|---|---:|---:|---:|---:|---:|---:|"]
    for r in monthly:
        report.append(f"| {r['month']} | {r['scenes']} | {r['valid_pixels']} | {r['positive_pixels']} | {r['negative_pixels']} | {float(r['rain_fraction']):.4%} | {float(r['dry_fraction']):.4%} |")
    report += ["",f"月度rain fraction范围为{min(rain_range):.4%}–{max(rain_range):.4%}，变化约{max(rain_range)/min(rain_range):.2f}倍；描述类别不平衡的季节变化，不据此选择月度α或改变样本权重。", "",
      f"Rainy pixel count={rain['count']:,}；mean={rain['mean']:.6f} mm/h；population std(ddof=0)={rain['std']:.6f} mm/h。",
      "", "| Quantile | mm/h |", "|---|---:|"]
    report += [f"| {key} | {rain[key]:.8f} |" for key in ("p1","p5","p10","p25","median","p75","p90","p95","p99")]
    report += ["", "| Strict rate exceedance mm/h | Count | Fraction among rainy pixels |", "|---:|---:|---:|"]
    report += [f"| >{key} | {value['count']} | {value['rainy_fraction']:.8%} |" for key,value in rain["strict_exceedance"].items()]
    report += ["", "这些阈值仅为描述性统计，未定义正式 extreme precipitation threshold。雨量百分位基于所有实际float32解码值排序，rank=p*(N−1)，端点升为float64作线性插值；均值/方差用合并central moments并由sum/squares独立交叉检查。仅约16MiB rainy值短暂留在内存，未创建磁盘中间数组或提交raw/cache。", "",
      "## α × γ 数学候选", "",
      f"A：α=.25，CANONICAL_REFERENCE_ONLY，未声称适合本项目。B：α=.50，NO_CLASS_REWEIGHTING_REFERENCE。C：α_balanced=N_negative/N_valid={balanced:.12f}，负类权重1−α={p:.12f}。当γ=0且类别难度相同，α*N_positive=(1−α)*N_negative；γ>0时不同类别的难度分布会打破这种均衡，因此balanced不等于最优。", "",
      "D：单位期望权重的inverse-frequency为w_pos=1/(2p)，w_neg=1/[2(1−p)]。按权重之和归一后严格等价于C；未归一时仅比例相同，整体尺度不同，会改变L_occ对L_qr的相对贡献。", "",
      "focal_gamma_weight_table.csv列出p_t=.01,.05,.1,.25,.5,.75,.9,.95,.99与γ=0,1,2,3的(1−p_t)^γ。γ=0为1；γ越大，easy/high-p_t样本被压低越强，hard样本只获得相对占比提升，因子本身不超过1，不能声称绝对权重增大。", "",
      "focal_loss_shaping.csv调用真实focal实现，对logits=−4,−2,−1,0,1,2,4生成两组诊断：正负类同raw logit；正类z、负类−z的同true-class confidence。贡献=Train类别占比×每类pixel loss；total relative以同logit条件下α=.5,γ=0为参照。这个固定synthetic difficulty分布并非真实模型预测分布；无训练或模型性能结论。", "",
      "## 固定真实样本的loss尺度", "",
      "在运行前固定并登记4个2023 Train与4个2024 Validation身份（按eligible序列等间隔选取）；复用正式reader/QC/pinned normalization，在BF16 eval/no_grad下仅forward。未训练模型使用隔离audit seed=20261001，未选择正式seed；模型参数SHA保持不变，无grad/optimizer，CPU RNG及运行设置复原。Train B13 SHA来自历史pinned manifest；Validation B13原先无逐帧SHA，本轮读取前计算登记，再与staging source/copy SHA核验。IMERG两年SHA均与既有证据匹配。", "",
      "使用既有工程参考α=.25、γ=2，不进行少量样本调参；完整数值见loss_scale_smoke.json。", "",
      "| Year | Fixed sample | L_occ | L_qr | L_total | Rainy / valid |", "|---:|---|---:|---:|---:|---|"]
    for r in smoke["samples"]:
        report.append(f"| {r['year']} | {r['sample_id']} | {r['L_occ']:.8f} | {r['L_qr']:.8f} | {r['L_total']:.8f} | {r['rainy_count']}/{r['valid_Yunnan_denominator']} |")
    report += ["", "共享valid分母不能使两项天然同尺度：L_qr受rain_fraction、log1p target、quantile error影响，L_occ受logits、α、γ影响。当前8个未训练forward仅是尺度证据，不作equal-weight最佳性、α/γ或额外loss multiplier选择。", "",
      "## 训练协议候选与公平性", "",
      "全局checkpoint numerator/denominator、Validation指标和probability threshold限制见validation_metric_candidates.md；A/B core loss定义严格等价。不平均不同大小的batch，不用2025选checkpoint。Occurrence候选Brier、AUROC、AP；条件分位数候选per-tau/mean pinball、coverage及strict crossing=0。THRESHOLD_NOT_YET_FROZEN；POD/FAR/CSI依赖批准的probability cutoff。未声称完整CRPS；MAE/RMSE/Bias只能标记DIAGNOSTIC_PROXY_METRIC，proxy不是严格E[R]。", "",
      "Optimizer组、weight decay/default参考见optimizer_candidates.md；physical2下LR候选5e−5、1e−4、2e−4、3e−4及linear-scaling参考在CSV。effective=2,4,8的updates/epoch分别5860,2930,1465；accumulation不扩大physical forward显存，改变更新频率；未来须按valid denominator正确聚合microbatch，不能默认等权平均不等分母。", "",
      "当前模型使用GroupNorm，统计沿每个sample内groups计算，不依赖BatchNorm式跨sample batch statistics；physical batch2无需BatchNorm小batch统计修正。见[PyTorch GroupNorm](https://docs.pytorch.org/docs/2.11/generated/torch.nn.GroupNorm.html)。这并不证明batch2的优化噪声与大effective batch相同。", "",
      "scheduler/epoch/early-stop/clip/seed/fairness各有独立候选文件：Constant LOW、warmup+cosine MEDIUM、Plateau HIGH FinalFit replay complexity。max epochs30/50/80、patience5/8/10、min_delta候选、clip none/1/5均未选择。最终epoch budget由Phase-A development及2024 Validation证据决定，然后FinalFit不再看2025调预算；本轮没有Phase-B normalization。", "",
      f"模型trainable parameters={param['total_trainable_params']:,}。Occurrence head=Conv1x1 48→1、49参数；quantile head=Conv1x1 48→32、1568参数，两者无hidden layer/raw activation。sigmoid与softplus/sequential float64/expm1分别为语义输出变换。v1.1未单独规定exact depth，HEAD_IMPLEMENTATION_DETAIL_REQUIRES_PROTOCOL_PIN=true；已记录源码SHA，未改变head。", "",
      "## 已有工程证据", "",
      "physical batch2、validation batch8、BF16、worker2仅为ENGINEERING_EVIDENCE_READY。既有GPU结果如下（不在本轮重测）：", "",
      "| Mode batch2 | Reserved MiB | Samples/s |", "|---|---:|---:|"]
    report += [f"| {r['mode']} | {float(r['peak_reserved_MiB']):.0f} | {float(r['samples_per_second']):.2f} |" for r in gpu_rows]
    report += ["",f"3-minute BF16 stability={stability['status']}，最高温度{stability['max_temperature_C']}°C，thermal throttle={stability['thermal_throttle_detected']}，CUDA errors={len(stability['CUDA_errors'])}。工程推荐没有升级为正式protocol选择。", "",
      "## 验证、来源与复现", "",
      f"全部126项旧测试通过；另新增{tests[-1]['tests']}项audit tests通过，覆盖focal α正负语义、mask、R=.1边界、完整矩合并、exact percentile、balanced/inverse-frequency尺度、rain-only tau-mean与valid分母、global metric batch分区不变性。既有测试/Scientific Freeze未修改。", "",
      "Scientific contract、production src、既有scripts/tests/reports内容在manifest中以基线Git blob和文件SHA复核。仅提交本轮新report/statistics/identity view/audit script/tests；无模型checkpoint/optimizer state/wheel/venv/raw/large cache。全部new-run本地staging均已清理，仅删除本流程创建的UUID副本。", "",
      "复现使用已验证CUDA Python，按lock → prevalence → math_tables → loss_scale → run_tests → package顺序，在新的run目录执行scripts/audit_phase_a_prefreeze.py。需要既有原始数据与本地pinned证据；每phase保留invocation hash；测量结束后仅停止。本轮脚本不是训练入口。", "",
      "primary source links与本地源码证据在references.json；PyTorch文档固定2.11以匹配安装版本。所有统计仅描述所定义的2023 Train空间时间population，无独立像元置信区间或泛化结论。研究者下一步批准protocol后才可能另行授权训练，本轮保持FORMAL_TRAINING_AUTHORIZED=false。", ""]
    text_file(out/"PHASE_A_PROTOCOL_PREFREEZE_REPORT.md","\n".join(report))
    # Verify every tracked baseline file has unchanged content, including history.
    baseline_sha, expected_blobs = {}, {}
    tree = subprocess.check_output(["git","ls-tree","-r","-z",BASELINE],cwd=ROOT).decode("utf-8")
    for entry in tree.rstrip("\0").split("\0"):
        meta, name = entry.split("\t", 1)
        expected_blobs[name] = meta.split()[2]
    names = list(expected_blobs)
    hashes = subprocess.run(["git","hash-object","--stdin-paths"],cwd=ROOT,
        input="\n".join(names)+"\n",text=True,encoding="utf-8",capture_output=True,check=True).stdout.splitlines()
    if len(hashes) != len(names):
        raise ValueError("Baseline blob inventory incomplete")
    for name, actual in zip(names, hashes):
        if actual != expected_blobs[name]:
            raise ValueError("Baseline file content changed: "+name)
        baseline_sha[name] = sha256(ROOT/name)
    owned = list((STAGING/f"prefreeze_{out.name}").rglob("yuntapr_b0_*.nc"))+list((STAGING/f"gpu_{out.name}").rglob("yuntapr_b0_*.nc"))
    if owned:
        raise ValueError("Staging copies remain")
    public = {str(p.relative_to(out)).replace("\\","/"): {"sha256":sha256(p),"bytes":p.stat().st_size}
              for p in sorted(out.rglob("*")) if p.is_file() and p.name != "manifest.json"}
    scripts = (ROOT/"scripts/audit_phase_a_prefreeze.py",Path(__file__),ROOT/"tests/phase_a_protocol_prefreeze/test_prefreeze_audit.py")
    save(out/"manifest.json", {"task":"B0 PHASE-A TRAINING PROTOCOL PRE-FREEZE EVIDENCE AUDIT v1",
         "baseline":BASELINE,"public_files":public,"scripts":{str(p.relative_to(ROOT)).replace("\\","/"):sha256(p) for p in scripts},
         "unchanged_baseline_files_sha256":baseline_sha,"staging_copies_remaining":0,
         "raw_data_committed":False,"model_checkpoint_created":False,"optimizer_created":False,
         "formal_training_started":False,"formal_training_authorized":False,"2025_pixels_read":False})
    print(json.dumps(final),flush=True)
