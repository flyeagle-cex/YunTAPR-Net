# 正式集成前代码审查交接

基线 ccfa6869672c96634fede157b06984741cc71c1b。本轮完成剩余合成批次边界：49 CPU、12 CUDA、16静态项通过；原91 CPU/6 CUDA仅核对身份，未重跑。全部为 SYNTHETIC_ENGINEERING_ONLY，不能证明概率校准、q32欠覆盖或上尾问题已改善。审批状态没有升级。

## 本人应审的准确源码

路径前缀：A=src/yuntapr/experimental/phase_b_v2_ablations/；I=src/yuntapr/experimental/phase_b_v2_integration/；B=src/yuntapr/experimental/phase_b_v2_boundaries/；M=src/yuntapr/models/quantile_v2/；T=src/yuntapr/training/；F=src/yuntapr/losses/。每个函数起止行与完整SHA见 [HANDOFF_SOURCE_MAP.json](HANDOFF_SOURCE_MAP.json)；下表是同一索引中的实际符号，全部需研究者阅读，不含审批勾选。

|源文件|函数或类|本人审查重点|
|---|---|---|
|A/config.py|get_config, RunSpec, workload, learning_rate_prefix|闭合E0/E1/E2；候选种子与18身份；50epoch轨迹前9epoch|
|A/validation.py|supervision, graph_zero|FP32比较后提升；独立mask；无雨零图与零监督停止|
|A/focal.py|occurrence_numerator|稳定BCE；gamma0仍保留alpha=.5|
|A/pinball.py|frozen_taus, conditional_pinball_numerator|32tau均值、FP64、仅有雨有效像元、无物理转换|
|A/total.py|combine_numerators, candidate_loss, CandidateLossResult|lambda仅乘一次；训练N_valid和报告N_rain|
|M/models.py|B0MatchedV2, B1V2|1/6帧完整501网格；原SP04；不能替换结构|
|M/heads.py|ProbabilityHeadsV2|BF16发生；FP32 raw33；FP64输出q32|
|M/parameterization.py|normalized_monotonic_quantiles|归一化正增量与独立span，epsilon不改|
|M/outputs.py|validate_log_quantiles|严格单调、支撑和非有限值停止|
|I/initialization.py|seeded_environment, fresh_paired_models|独立reseed；同形复制；B1两输入权重保留；状态/非持久buffer身份|
|I/controls.py|synthetic_epoch_order, endpoint_boundary|seed+epoch独立排列；9epoch终点；无BEST替代|
|I/controls.py|reject_resume, reject_formal_start|缺批准永拒；字符串不是批准；不加载LAST|
|A/readiness.py|review_checkpoint_binding, BlockedRunner|具体run/LAST/code/data/init绑定；无启动能力|
|I/resources.py / safety.py|resource_snapshot, require_resources, install_process_file_guard, synthetic_operation_guards|模型构造前准入；不足停止；进程守卫不是OS沙箱|
|B/boundary.py|BoundaryBatch, make_boundary_pair, losses_from_output, forward_boundary|只允许train1、validation8/5；M1/Q1；inference_mode|
|B/boundary.py|evaluation_components, aggregate_evaluation|复用冻结FP64验证器；未加权先累加再相除|
|B/gradients.py|checked_gradients|全部参数梯度；干批分位数头零梯度；NaN/缺失停止|
|F/total_loss.py|b0_core_loss|E0数学参照；零监督返回skip标记与正式入口停止对应|
|T/phase_a_validation_v2.py|LogDomainValidation|固定gamma2，发生项FP64重算；不是训练S_occ|
|T/formal_phase_a_v2.py|paired_initialization, forward_loss, update, loader|只读对照；训练batch2尾1，验证8尾5；update本轮未调用|
|T/checkpoint_v2.py|validate_payload, verify_file, apply_verified, CheckpointStore|Phase-A 50epoch/BEST schema不能直接作B9/V0入口；后3符号未调用|

## 必须理解的公式与实际边界

valid是两个掩膜交集；rain先在原FP32参考上严格比较，不先cast到FP64。人工3430格点仅测试计数，不代表真实云南地理配准。

$$
v=m_{\mathrm{reference}}\land m_{\mathrm{artificial}},\quad
z=\mathbf1\{y_{32}>\operatorname{float32}(0.1)\},\quad
N_v=\sum v,\quad N_r=\sum vz.
$$

Focal映射A/focal.py。E0/E2的gamma=2，E1的gamma=0；所有alpha=.5。BF16 logit的BCE提升FP32，gamma0不等于未加权BCE。

$$
b=\operatorname{BCEWithLogits}(\ell,z),\quad p_t=e^{-b},\quad
S_{\rm occ}=\sum_v\alpha_t(1-p_t)^\gamma b,\quad
\alpha_t=\alpha z+(1-\alpha)(1-z).
$$

q映射M/parameterization.py：32allocation+1span原通道，正权重和FP64前缀；不是排序或截断输出。两个epsilon均1e-4，qlog支撑/单调检查仍由原函数执行。

$$
w_i=\operatorname{softplus}(a_i)+\epsilon_w,\quad
q_i=\log(1+0.1)+(\operatorname{softplus}(s)+\epsilon_s)
\frac{\sum_{j\le i}w_j}{\sum_{j=1}^{32}w_j},\quad
\tau_i=\frac{i-0.5}{32}.
$$

Pinball映射A/pinball.py与A/total.py；先均值32tau，再仅在有雨有效像元求和。lambda不进入科学Conditional Pinball。空雨时S_qr=0、图连接、CPB=None；零有效监督停止。

$$
S_{\rm qr}=\sum_{vz}\frac1{32}\sum_{i=1}^{32}
\max\{\tau_i e_i,(\tau_i-1)e_i\},\quad
e_i=\log(1+y_{32})-q_i,
$$
$$
L_{\rm train}=\frac{S_{\rm occ}+\lambda_qS_{\rm qr}}{N_v},\qquad
\mathrm{CPB}=\frac{\sum S_{\rm qr}}{\sum N_r}\ \ (\sum N_r>0).
$$

共同Core必须从T/phase_a_validation_v2.py在FP64重算固定gamma2发生分子并全局累加，使用lambda=1的未加权分位数项。不能将E1/E2的training_objective当共同Core，甚至E0训练发生分子也不是同精度的验证分子。本轮首次静态发现并修复这一差别，旧attempt完整保留。

## 尚未通过或未执行的检查

本轮定义的49 CPU/12 CUDA边界检查均通过，没有待修的数值失败；下列是未执行项，不能写成通过。

1. 真实2023/2024数据资格、冻结地理mask/SP04配准、shared scaler实际应用、真实ID顺序和读取防火墙。需要独立真实数据preflight许可，2025继续封存。
2. 正式optimizer/clip/scheduler更新事务、长时epoch循环、实际吞吐与共享GPU持续资源风险。没有step；无优化器显存测量。
3. 新v2 runner、B9终点checkpoint schema、原子写入/耐久性、故障注入和审批验真。没有私有checkpoint加载、保存或恢复。
4. 新批次边界本轮仅seed2026；另外两seed初始化与训练顺序核验使用原始已通过证据，不伪称重新覆盖。CPU完整模型forward/backward未运行，实际完整路径在CUDA执行。
5. 正式未来runner中异常停止、阶段批准、LAST绑定审批和失败后人工处置的端到端测试；当前只有隔离保护与静态候选，不能启动训练。

## 必须本人决定的科学与治理问题

全部保持 RESEARCHER_DECISION_REQUIRED：H-O/H-Q及E0/E1/E2最终科学接受；三个seed、D1/Q1/N0/I3/B9/S0/V0；Brier与q32覆盖误差主指标、完整32tau与强雨Pinball/上尾副作用；最小有意义效应、副作用界限、多重比较仍NOT_YET_ESTABLISHED；2024历史开发验证的解释范围，不能作为全新独立确认集。

Phase-A科学接受范围和B1历史恢复处置须独立决定，历史恢复仍NOT_GRANTED。数据权限、计算资源、正式集成范围、具体阶段执行及LAST恢复均另需明确授权。文档、JSON、测试PASS和Git commit不构成批准事件。

建议本人按 A/config→validation→focal/pinball/total→M/heads/parameterization→I/initialization/controls→B/boundary/gradients→测试顺序阅读；现场解释FP32阈值反例、两个分母、空雨零梯度、FP64共同验证、epoch9终点与LAST绑定。随后审查正式集成差异与独立执行授权。本轮在审批边界停止，不派生新工作包。

V2_PHASE_B_AUTHORIZED=false；RESEARCHER_SCIENTIFIC_APPROVAL_REQUIRED=true；HISTORICAL_RECOVERY_RATIFICATION=NOT_GRANTED；2025_RAW_ACCESS=2025_PIXELS_READ=0。
