# 源码结构与学习顺序

所有路径均以仓库为根；新命名空间为 src/yuntapr/experimental/phase_b_v2_runner_candidate/。

|顺序 / 文件|重点函数与用途|本人审查要点|
|---|---|---|
|1 identity.py|identity、verify_sources、candidate_plan、reject_formal_execution|18 个封闭身份；333 个冻结来源；本候选源码摘要；审批状态不可升级|
|2 optimizer.py|new_adamw、clip_and_check、PrefixSchedule、check_finite|冻结分组；clip=5；先赋 LR 后 step；step 成功后提交调度计数|
|3 safety.py|install_guard、checkpoint_io、StepLedger.read/_mutate/perform|contextvars 限制操作作用域；独占锁；预算先预留并落盘，失败不退回|
|4 rng.py|capture、validate、restore|Python/NumPy/CPU/CUDA RNG；weights_only 可读类型；本地 generator 校验不修改全局 RNG|
|5 checkpoint.py|SyntheticStore.save/read、validate_payload|SHA 校验先于反序列化；全字段校验先于恢复；部分写入不能当作提交|
|6 runner.py|SyntheticRunner.__init__、empty_rain_gradient_check、update_once、evaluate_synthetic、save/restore|只能内部造数据；双头梯度；FP64 共同评价；恢复失败后 poisoned|
|7 __init__.py|SCOPE|明确人工合成工程用途|

主要张量：B0 输入 [2,1,501,501]、B1 [2,6,501,501]，FP32；参数 FP32，骨干和发生头在 BF16 autocast 下执行；参考 [2,1,100,100] 为 FP32；32 分位数 [2,32,100,100] 为 FP64。人工掩膜每场景含 3430 个格点，用于接口计数，不能代表冻结云南地理分布。

Python 学习提示：dataclasses.replace 保留合成身份只替换无雨 rate；with 管理临时上下文；try/finally 保证释放锁和 contextvars；raise 中止事务而不修补参数。torch.no_grad/inference_mode 用于状态与评价；训练损失的 backward 构建参数梯度；zero_grad(set_to_none=True) 清除上次梯度；AdamW.step 只在额度账本批准的本轮合成上下文中调用。

不要把 optimizer 的权重衰减视为 Pinball 权重。无雨批次的条件头仍连接计算图、梯度为零；若以后允许其执行 AdamW，已有动量或权重衰减仍可能改变参数。本轮无雨检查只 backward、不 step；12 次实际 step 都使用混合人工参考。

练习：解释 gamma=0 为什么仍有 alpha=0.5；手算梯度 [6,8] 被裁剪到近似 [3,4]；解释 LR 更新 1 为 1e-4/5228；找出评价路径中为何没有 lambda_q；解释为何恢复 RNG 不恢复本轮额度账本。

详细损失教学继续使用此前 implementation/v1 的 FOCAL、PINBALL、TOTAL walkthrough，本轮不复制或改写。
