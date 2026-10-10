# 测试、首次失败与修复

仅运行本目录新增测试。首次 CPU 开发检查 38 项通过（工具输出记录，1.360 秒）；扩展后分别 52、53、55 项通过，带时间戳日志在 `tests/`。最终独立测试方法数为 **55 CPU + 2 CUDA**，不把重复回归运行累加为独立测试数量。

## 首次 CUDA 失败

首次 `test_b0_replay` 在第 1 次 AdamW 更新、独立验证及 blob 保存后，`torch.load(weights_only=True)` 拒绝 NumPy scalar。原因是 `coverage[-1] - TAU[-1]` 产生 numpy.float64，写入 q32 偏差字段。该问题不是模型非有限值，也不是科研性能异常。

引擎进入 FAILED；控制器未确认 LAST；该次更新仍记为已消耗。原始日志保留 `Unsupported global: GLOBAL numpy._core.multiarray.scalar`。修复仅把两个报告字段显式转换为 Python float，新增 `test_report_weights_only_roundtrip`。默认 Store 没有降低 weights_only 安全设置，也没有加入 NumPy allowlist。

为比较第 1 次更新与剩余额度中的 B0 重放，`inspect_first_failure.py` 只检查本轮生成的明确临时文件，先核验文件 SHA、当前 campaign 的原代码 SHA、合成标记及 update=1；在一次性 forensic 读取中仅允许 NumPy scalar/dtype/Float64DType 构造器。提取 model/optimizer/scheduler/RNG 摘要，不恢复引擎、不采纳该 LAST、不执行更新、不退款。其输出 `first_failure_state.json` 可公开审查；本地 blob 不发布。

四步额度表保持原文件与记录，代码修复后的新实例继续使用原计数；不同源码版本的 SHA 分别留存。余下实际更新为 B0 一次、B1 两次，累计 **4**。两个 CUDA 检查最终通过；B0 与 forensic 摘要一致，B1 两次完整成功事务一致。

## 故障与负面测试

- 保存序列化后中断、blob 后/receipt 前中断、rename 锁失败：无可用提交 receipt。
- 不完整 blob、SHA 错误、已有文件锁、重复保存、外部 checkpoint 路径：拒绝。
- 缺 model/optimizer/scheduler/RNG/validation/父 LAST/额度字段；seed/arm/model 身份、epoch、LR、moment 形状/有限性错误：拒绝。
- 训练丢失或重排、验证缺失、先提交 LAST、失败后重启、旧 LAST 回滚、未完成更新预约：拒绝。
- SQLite 资源不足、磁盘准入不足、并发锁、子进程重复消费已预约额度：拒绝。
- 假审批对象、真实 reader 参数、封存年份、未来观测时刻、错误产品/单位、SHA 不一致：拒绝；路径转换陷阱未触发。
- 人工额度表耗尽或存在不明预约时，optimizer.step spy 调用数为 0。这些是纯元数据测试，不计入实际四步。

本轮没有真实观测读取测试，没有重跑历史 2025 预检；历史路径属性计数仍不可追溯补零。日志只做换行规范化和本机路径脱敏，不删除错误信息。

交付静态扫描首次把检查器自身的凭据前缀字面量识别为敏感内容，断言停在 validate_delivery.py；这是自扫描误报，没有检测到实际凭据。将检测常量分段构造后再检查，保留 `tests/static_first_failure.json`。没有跳过检查器自身或移除敏感扫描规则。
