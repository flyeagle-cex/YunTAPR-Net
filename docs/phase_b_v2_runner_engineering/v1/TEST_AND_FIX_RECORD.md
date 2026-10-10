# 实际测试、失败与修复

本轮唯一检查：75 CPU + 8 CUDA 全部有通过记录，未解决失败 0。执行日志保留每次尝试；重复尝试不增加唯一检查数。12 次真实合成 AdamW.step，FORMAL_OPTIMIZER_STEPS=0；mocked dispatch 不调用原 AdamW，不计更新。

1. cpu_attempt_001：22 passed、1 failed。Windows 在锁句柄仍打开时不能 unlink。修复为独占创建后先 close，再 finally unlink；checkpoint 和账本两处同时修复。失败文件及初次 part/lock 留在本轮私有临时目录。
2. cpu_attempt_002：56 passed。含配置、LR、解析 clipping、额度、RNG、I/O、完整性与故障矩阵。
3. cuda_attempt_001：6 passed，12 actual synthetic steps。每模型×臂一次混合更新和一次 FRESH0 重放；额外无雨 backward 不 step。出现一次 requires_grad scalar 转换 warning，后续改为 detach 后读取，未更改数学。
4. hardening_attempt_001：3 CPU + 2 CUDA passed，0 steps；绑定候选源码 SHA，真实对象的恢复拒绝和 poisoned 检查。
5. final_static_attempt_001：14 passed。增加 AdamW moments 的元数据边界及其他 optimizer 阻断。
6. final_static_attempt_002：收集阶段 1 error、0 tests executed。追加 fsync 时缩进错误，未执行更新；修正后 final_static_attempt_003：16 passed。
7. final_cuda_state_attempt_001：最终候选源码身份的 2 个无更新 CUDA 恢复检查通过；为源码/guard 变化后的针对性复核，没有重新执行 12 次 step。

最终源码在 checkpoint 身份字段、额度持久化、guard、dtype 校验和 warning 处理处比首次 CUDA 更新版本更严格。executed_source_before_hardening.json 保留实际完成更新时的文件摘要；final_source_identity.json 保留最终摘要。最后的无更新 CUDA 检查与 CPU dispatch spy 校验覆盖这些追加保护。受硬上限约束，最终源码没有再次完整重跑优化器更新；不把分阶段结果伪称为同一源码的一次全套运行。

完整原始日志保存在 .local/raw_test_logs；公开 log/XML 仅替换机器路径，不改测试结果。JSON、XML、stdout 均保留真实次数和失败原因。以前 91 CPU / 6 CUDA 及既有边界/loss 测试未重跑。
