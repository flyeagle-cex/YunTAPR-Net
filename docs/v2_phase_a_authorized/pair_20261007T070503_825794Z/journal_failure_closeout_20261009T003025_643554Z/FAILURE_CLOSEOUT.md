# B1-v2 日志读取冲突：失败归档与恢复前提

B1 在 epoch 15 的 batch 383 因追加 steps.jsonl 被拒绝而停止。前 382 次 optimizer update 完成，第 383 次在记录尝试事件时失败，尚未调用 optimizer.step；没有新 checkpoint。正式保留轨迹仍为 epoch 14 的 73,192 次更新。累计实际成功更新为 76,669 次，其中 3,477 次没有进入完整 checkpoint，后续恢复必须丢弃。

本次外部审计曾使用默认 .NET File.ReadLines 读取运行中的日志。其 Windows 文件共享方式不允许其他进程写入；隔离 fixture 复现了相同 PermissionError。读取与本次失败同时发生，证据支持它是冲突来源，但没有独立捕获当时的 OS handle。该读取由 Codex 执行，应由 Codex 承担工程排查责任。

修正只涉及外部观察与审计：运行中追加日志只允许已测试的 Python reader，或显式 FileShare.ReadWrite | FileShare.Delete；不打开训练进程会原子替换的 JSON。显式共享读取下 1,000 次追加均通过。冻结训练代码、模型、loss、LR、normalization 和数据集合未改。

本次重跑的前 382 次更新，其样本、LR、loss、梯度范数、分母及 clipping 与原 epoch 15 日志逐项零容差一致。此结论仅覆盖已完成前缀。model/optimizer/scheduler/RNG 的已应用恢复身份见原始 resume_identity 快照与核验记录。31 个历史 checkpoint 的大小和 SHA256、冻结代码与不可变轮次证据已复核。

当前失败已关闭并独立保留。恢复必须另建运行记录，重新核验 epoch 14 LAST、冻结身份、当前环境和来源；先推送远端 main 绑定后，才可调用未修改的正式 runner。2025_RAW_ACCESS=0，2025_PIXELS_READ=0，V2_PHASE_B_AUTHORIZED=false。配对 Phase-A 尚未完成。
