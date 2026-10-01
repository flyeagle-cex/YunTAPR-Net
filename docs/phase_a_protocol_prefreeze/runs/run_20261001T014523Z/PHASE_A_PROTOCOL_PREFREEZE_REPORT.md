# PHASE_A_PROTOCOL_PREFREEZE_REPORT

Run `run_20261001T014523Z`; baseline `bc287755cfade53dd5a52a32c99c7326e2c2dfe8`.

本轮已完成训练协议冻结前的证据审计。所有科研参数保持未选择，供研究者决策；未创建 optimizer、未更新模型参数、未生成训练 checkpoint。D1–D8、eligible population、SP04、模型结构和概率语义均保持基线。

## 最终状态

```json
{
  "PHASE_A_PROTOCOL_EVIDENCE_READY": true,
  "TRAIN_OCCURRENCE_PREVALENCE_READY": true,
  "FOCAL_ALPHA_SEMANTICS_VERIFIED": true,
  "FOCAL_ALPHA_RESEARCHER_DECISION_REQUIRED": true,
  "FOCAL_GAMMA_RESEARCHER_DECISION_REQUIRED": true,
  "OPTIMIZER_RESEARCHER_DECISION_REQUIRED": true,
  "LR_RESEARCHER_DECISION_REQUIRED": true,
  "EFFECTIVE_BATCH_RESEARCHER_DECISION_REQUIRED": true,
  "SCHEDULER_RESEARCHER_DECISION_REQUIRED": true,
  "EPOCH_BUDGET_RESEARCHER_DECISION_REQUIRED": true,
  "CHECKPOINT_METRIC_RESEARCHER_DECISION_REQUIRED": true,
  "SEED_POLICY_RESEARCHER_DECISION_REQUIRED": true,
  "HEAD_IMPLEMENTATION_DETAIL_REQUIRES_PROTOCOL_PIN": true,
  "B0_FORMAL_TRAINING_STARTED": false,
  "FORMAL_TRAINING_AUTHORIZED": false,
  "engineering_evidence_status": "ENGINEERING_EVIDENCE_READY",
  "scientific_parameter_selection": "NONE",
  "researcher_table_choice": "Unselected scientific candidates; prior engineering recommendations retained"
}
```

## 基线与数据身份

Scientific Freeze v1.1 / engineering v4；2023 Train=11720 scenes，2024 Validation=11727 scenes；主云南 mask=3430 target cells。所有引用 SHA 详见 baseline_lock.json。Train manifest 为既有 normalization sample manifest；Validation 既无独立历史文件，本轮从既有 combined eligibility 的2024 eligible行生成身份视图，按 window_start 排序，其SHA独立登记。未改变样本资格。

| Evidence | SHA256 |
|---|---|
| scientific_contract_v1.1 | `14209321d82107f58df96f234485cc56a806971cb62e8b9804ce4d25d05756c3` |
| scientific_freeze_v1.1_document | `48e164cc7b6569d33e1929418ce60b13173957efbab3d97ca70cca0e6f7f1b6c` |
| engineering_v4 | `bfcabbc31a6124d596cba893fc19ded09078a27780c2de40fa2b21ddd6b924a7` |
| phase_a_normalization_artifact | `4bcfa0520550e343dd154fd4436715a306c015a02d16ec4a12bb2ed3cf606e0e` |
| eligible_train_manifest | `dc0559f12f02817f8ec74916d03dd20e40ec0584ec58c59b34b5e02cc9a60e68` |
| eligible_validation_manifest | `ac5405d8185d6760acc15a4ab364804c1d8ec8de84064737d0757f6688aeb410` |
| combined_eligibility_source | `b4bad8ea45a78eddae3832df89cfade00cac3b184fc550eea4f0cf479c29de90` |
| SP04_mapping | `3f4dea000efa0146cec292578bca07c370f897328c933e804346097f8ab9d3fd` |
| SP04_manifest | `e1c5d8ab1b58407503db4b56124f4a34a360507280b0e7989e8b9e2f60888473` |
| yunnan_mask | `9d921def661fc3e58cd1ed783fcf87abbf493da6ae5e5fea79c28043f73495ef` |
| prior_gpu_manifest | `c53cf3804c7f628951cd72d0134b0a4862b2e089d4141e06cf1ff5f420885eb8` |

## 当前 focal 与 core loss 的精确公式

对每个像元：$z$为logit，$y=1[R>0.1]$，$p=\sigma(z)$，$b=\mathrm{softplus}(z)-yz$，$p_t=\exp(-b)=yp+(1-y)(1-p)$。
$\alpha_t=\alpha y+(1-\alpha)(1-y)$。$m=\mathrm{IMERGvalid}\land\mathrm{YunnanMask}$，$D=\sum m$。
$$L_{occ}=\frac{\sum m\,\alpha_t(1-p_t)^\gamma b}{D}.$$
FOCAL_ALPHA_SEMANTICS=ALPHA_IS_POSITIVE_CLASS_WEIGHT。focal_bce_sum 返回 masked sum；b0_core_loss 再除以有效云南监督像元数。γ只作用于真实类别概率的(1−p_t)因子。α=0.5不改变正负相对权重，但将未加权 BCE/focal 整体缩小一半；它不是完全无尺度变化。

$\tau_i=(i-0.5)/32$，$u_i=\log(1+R)-q_i$，$\rho_\tau(u)=\max(\tau u,(\tau-1)u)$。
$$L_{qr}=\frac{\sum my\,\frac1{32}\sum_i\rho_{\tau_i}(u_i)}{D},\qquad L=L_{occ}+L_{qr}.$$
quantile axis=mean；分子只统计rainy valid云南像元，分母仍为全部valid云南监督像元。无雨时core L_qr为零，conditional-only诊断为NA；无valid时current loss跳过，proposed validation metric应报告undefined。qlog/qphysical/pinball保持float64。两个损失共享分母不保证数值尺度相近。

## 全量2023 occurrence与雨量

逐日读取全部245个2023 IMERG V07 Final文件，仅解码对应eligible slots；来源哈希与既有审计一致，大小/SHA验证和清理全部成功。N_valid=40,199,600，N_positive=4,188,966，N_negative=36,010,634；positive_fraction=10.420417119%，negative_fraction=89.579582881%，negative_to_positive_ratio=8.596545。所有selected像元统计与历史逐时次目标计数一致。R==0.1属于negative；精确遵循生产float32比较，不加容差/重分箱。数据中恰等于float32(0.1)的数量为0。

| Month | Scenes | Valid pixels | Positive | Negative | Rain fraction | Dry fraction |
|---|---:|---:|---:|---:|---:|---:|
| 202303 | 1486 | 5096980 | 121230 | 4975750 | 2.3785% | 97.6215% |
| 202304 | 1432 | 4911760 | 93392 | 4818368 | 1.9014% | 98.0986% |
| 202305 | 1483 | 5086690 | 298047 | 4788643 | 5.8594% | 94.1406% |
| 202306 | 1440 | 4939200 | 693738 | 4245462 | 14.0456% | 85.9544% |
| 202307 | 1482 | 5083260 | 803036 | 4280224 | 15.7977% | 84.2023% |
| 202308 | 1485 | 5093550 | 1153524 | 3940026 | 22.6468% | 77.3532% |
| 202309 | 1426 | 4891180 | 549902 | 4341278 | 11.2427% | 88.7573% |
| 202310 | 1486 | 5096980 | 476097 | 4620883 | 9.3408% | 90.6592% |

月度rain fraction范围为1.9014%–22.6468%，变化约11.91倍；描述类别不平衡的季节变化，不据此选择月度α或改变样本权重。

Rainy pixel count=4,188,966；mean=1.503714 mm/h；population std(ddof=0)=2.173704 mm/h。

| Quantile | mm/h |
|---|---:|
| p1 | 0.12000000 |
| p5 | 0.14999999 |
| p10 | 0.19000000 |
| p25 | 0.29999998 |
| median | 0.72999996 |
| p75 | 1.81999993 |
| p90 | 3.65999985 |
| p95 | 5.40999985 |
| p99 | 10.35999966 |

| Strict rate exceedance mm/h | Count | Fraction among rainy pixels |
|---:|---:|---:|
| >1 | 1722973 | 41.13122427% |
| >5 | 243972 | 5.82415804% |
| >10 | 46336 | 1.10614409% |
| >20 | 5008 | 0.11955218% |
| >30 | 841 | 0.02007655% |
| >50 | 39 | 0.00093102% |

这些阈值仅为描述性统计，未定义正式 extreme precipitation threshold。雨量百分位基于所有实际float32解码值排序，rank=p*(N−1)，端点升为float64作线性插值；均值/方差用合并central moments并由sum/squares独立交叉检查。仅约16MiB rainy值短暂留在内存，未创建磁盘中间数组或提交raw/cache。

## α × γ 数学候选

A：α=.25，CANONICAL_REFERENCE_ONLY，未声称适合本项目。B：α=.50，NO_CLASS_REWEIGHTING_REFERENCE。C：α_balanced=N_negative/N_valid=0.895795828814，负类权重1−α=0.104204171186。当γ=0且类别难度相同，α*N_positive=(1−α)*N_negative；γ>0时不同类别的难度分布会打破这种均衡，因此balanced不等于最优。

D：单位期望权重的inverse-frequency为w_pos=1/(2p)，w_neg=1/[2(1−p)]。按权重之和归一后严格等价于C；未归一时仅比例相同，整体尺度不同，会改变L_occ对L_qr的相对贡献。

focal_gamma_weight_table.csv列出p_t=.01,.05,.1,.25,.5,.75,.9,.95,.99与γ=0,1,2,3的(1−p_t)^γ。γ=0为1；γ越大，easy/high-p_t样本被压低越强，hard样本只获得相对占比提升，因子本身不超过1，不能声称绝对权重增大。

focal_loss_shaping.csv调用真实focal实现，对logits=−4,−2,−1,0,1,2,4生成两组诊断：正负类同raw logit；正类z、负类−z的同true-class confidence。贡献=Train类别占比×每类pixel loss；total relative以同logit条件下α=.5,γ=0为参照。这个固定synthetic difficulty分布并非真实模型预测分布；无训练或模型性能结论。

## 固定真实样本的loss尺度

在运行前固定并登记4个2023 Train与4个2024 Validation身份（按eligible序列等间隔选取）；复用正式reader/QC/pinned normalization，在BF16 eval/no_grad下仅forward。未训练模型使用隔离audit seed=20261001，未选择正式seed；模型参数SHA保持不变，无grad/optimizer，CPU RNG及运行设置复原。Train B13 SHA来自历史pinned manifest；Validation B13原先无逐帧SHA，本轮读取前计算登记，再与staging source/copy SHA核验。IMERG两年SHA均与既有证据匹配。

使用既有工程参考α=.25、γ=2，不进行少量样本调参；完整数值见loss_scale_smoke.json。

| Year | Fixed sample | L_occ | L_qr | L_total | Rainy / valid |
|---:|---|---:|---:|---:|---|
| 2023 | 2023-03-01T00:00:00+00:00 | 0.06253549 | 0.01578927 | 0.07832476 | 14/3430 |
| 2023 | 2023-05-21T15:00:00+00:00 | 0.02507901 | 0.00000000 | 0.02507901 | 0/3430 |
| 2023 | 2023-08-11T04:30:00+00:00 | 0.07600069 | 0.21041573 | 0.28641642 | 178/3430 |
| 2023 | 2023-10-31T23:30:00+00:00 | 0.02857612 | 0.02847909 | 0.05705521 | 23/3430 |
| 2024 | 2024-03-01T00:00:00+00:00 | 0.06216266 | 0.00433087 | 0.06649354 | 4/3430 |
| 2024 | 2024-05-21T15:00:00+00:00 | 0.08909628 | 0.44912177 | 0.53821804 | 347/3430 |
| 2024 | 2024-08-11T05:30:00+00:00 | 0.09909702 | 0.74831611 | 0.84741314 | 675/3430 |
| 2024 | 2024-10-31T23:30:00+00:00 | 0.04897326 | 0.05708204 | 0.10605530 | 51/3430 |

共享valid分母不能使两项天然同尺度：L_qr受rain_fraction、log1p target、quantile error影响，L_occ受logits、α、γ影响。当前8个未训练forward仅是尺度证据，不作equal-weight最佳性、α/γ或额外loss multiplier选择。

## 训练协议候选与公平性

全局checkpoint numerator/denominator、Validation指标和probability threshold限制见validation_metric_candidates.md；A/B core loss定义严格等价。不平均不同大小的batch，不用2025选checkpoint。Occurrence候选Brier、AUROC、AP；条件分位数候选per-tau/mean pinball、coverage及strict crossing=0。THRESHOLD_NOT_YET_FROZEN；POD/FAR/CSI依赖批准的probability cutoff。未声称完整CRPS；MAE/RMSE/Bias只能标记DIAGNOSTIC_PROXY_METRIC，proxy不是严格E[R]。

Optimizer组、weight decay/default参考见optimizer_candidates.md；physical2下LR候选5e−5、1e−4、2e−4、3e−4及linear-scaling参考在CSV。effective=2,4,8的updates/epoch分别5860,2930,1465；accumulation不扩大physical forward显存，改变更新频率；未来须按valid denominator正确聚合microbatch，不能默认等权平均不等分母。

当前模型使用GroupNorm，统计沿每个sample内groups计算，不依赖BatchNorm式跨sample batch statistics；physical batch2无需BatchNorm小batch统计修正。见[PyTorch GroupNorm](https://docs.pytorch.org/docs/2.11/generated/torch.nn.GroupNorm.html)。这并不证明batch2的优化噪声与大effective batch相同。

scheduler/epoch/early-stop/clip/seed/fairness各有独立候选文件：Constant LOW、warmup+cosine MEDIUM、Plateau HIGH FinalFit replay complexity。max epochs30/50/80、patience5/8/10、min_delta候选、clip none/1/5均未选择。最终epoch budget由Phase-A development及2024 Validation证据决定，然后FinalFit不再看2025调预算；本轮没有Phase-B normalization。

模型trainable parameters=4,329,361。Occurrence head=Conv1x1 48→1、49参数；quantile head=Conv1x1 48→32、1568参数，两者无hidden layer/raw activation。sigmoid与softplus/sequential float64/expm1分别为语义输出变换。v1.1未单独规定exact depth，HEAD_IMPLEMENTATION_DETAIL_REQUIRES_PROTOCOL_PIN=true；已记录源码SHA，未改变head。

## 已有工程证据

physical batch2、validation batch8、BF16、worker2仅为ENGINEERING_EVIDENCE_READY。既有GPU结果如下（不在本轮重测）：

| Mode batch2 | Reserved MiB | Samples/s |
|---|---:|---:|
| FP32 | 4420 | 9.40 |
| FP16 | 3258 | 12.16 |
| BF16 | 3260 | 12.23 |

3-minute BF16 stability=PASS，最高温度74.0°C，thermal throttle=False，CUDA errors=0。工程推荐没有升级为正式protocol选择。

## 验证、来源与复现

全部126项旧测试通过；另新增11项audit tests通过，覆盖focal α正负语义、mask、R=.1边界、完整矩合并、exact percentile、balanced/inverse-frequency尺度、rain-only tau-mean与valid分母、global metric batch分区不变性。既有测试/Scientific Freeze未修改。

Scientific contract、production src、既有scripts/tests/reports内容在manifest中以基线Git blob和文件SHA复核。仅提交本轮新report/statistics/identity view/audit script/tests；无模型checkpoint/optimizer state/wheel/venv/raw/large cache。全部new-run本地staging均已清理，仅删除本流程创建的UUID副本。

复现使用已验证CUDA Python，按lock → prevalence → math_tables → loss_scale → run_tests → package顺序，在新的run目录执行scripts/audit_phase_a_prefreeze.py。需要既有原始数据与本地pinned证据；每phase保留invocation hash；测量结束后仅停止。本轮脚本不是训练入口。

primary source links与本地源码证据在references.json；PyTorch文档固定2.11以匹配安装版本。所有统计仅描述所定义的2023 Train空间时间population，无独立像元置信区间或泛化结论。研究者下一步批准protocol后才可能另行授权训练，本轮保持FORMAL_TRAINING_AUTHORIZED=false。
