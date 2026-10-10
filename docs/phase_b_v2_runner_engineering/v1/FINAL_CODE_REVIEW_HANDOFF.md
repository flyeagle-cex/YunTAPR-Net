# 本人代码审查与正式集成前交接

现在可以审查候选工程；正式训练仍不能启动。

1. 配置：phase_b_v2_ablations/config.py:get_config/RunSpec/learning_rate_prefix，以及 runner_candidate/identity.py。核对 E0=(2,1)、E1=(0,1)、E2=(2,2)，alpha=0.5，三个seed，18运行，禁止warm-start。
2. 数学：phase_b_v2_ablations/focal.py:occurrence_numerator、pinball.py:conditional_pinball_numerator、total.py:candidate_loss/combine_numerators。核对 FP32>0.1、32tau平均、FP64、训练分母N_valid、科学条件分母N_rain。
3. 精度与双头：quantile_v2/heads.py:ProbabilityHeadsV2.forward、parameterization.py:normalized_monotonic_quantiles；原 33 raw channels → 32 quantiles、epsilon1e-4不改、BF16发生/FP64分位数边界。
4. 更新：runner_candidate/optimizer.py 与 runner.py:update_once。核对正式冻结 parameter_groups、AdamW参数、clip=5、LR在step前赋值、成功后commit；核心 loss 无重写。
5. 评价：training/phase_a_validation_v2.py:LogDomainValidation.add/report 与 runner.py:evaluate_synthetic。共同Core用gamma2 FP64重算，lambda_q不进入评价。
6. 事务与身份：checkpoint.py:SyntheticStore/validate_payload、rng.py、safety.py:StepLedger，以及 runner.py:save/restore。核对先验证再应用、失败停用、拒绝未完成边界、恢复不回滚额度。

未通过的检查：没有当前失败。尚未执行/尚未具备：最终收尾源码再次完整 optimizer 更新回归（12次硬额度已耗尽）；多步连续长期轨迹；正式完整 epoch/验证事务；真实数据权限/preflight；正式审批证据服务和 LAST 祖先链；Windows断电/磁盘满及长期文件系统耐久性；正式资源、调度、报告和9epoch结果。不能把这些记为已通过。

独立授权后的安全顺序：本人审查核心loss/控制变量/决策材料 → 确定科学效应与副作用界限并独立签署协议 → 授予正式集成版本开发许可 → 另建真实数据preflight许可及审计机制 → 确认资源和失败/恢复机制 → 单独签署seed2026六组执行范围。其余seed及任何恢复另受相应许可约束。本候选没有正式执行入口，不能直接翻转布尔值开始训练。

本轮合成工程开发是研究者委托AI的工作，不代替本人理解或最终科研审查。
