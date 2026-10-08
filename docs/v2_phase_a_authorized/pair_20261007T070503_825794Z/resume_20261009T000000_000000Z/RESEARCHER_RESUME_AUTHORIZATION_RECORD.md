# B1-v2 失败证据与恢复候选：更正记录

本文件取代此前本地草稿中未经完整核验的“研究者已授权恢复”表述。原始字节已复制归档并由 SHA256 登记，原始正式启动授权、失败原件、完整 epoch 报告和 checkpoint 保留。

当前研究者指令为“你看着进行一些修改后推送”，本次据此整理并发布失败与核验材料。当前 authorization.json 是不可执行的证据发布记录，不能用于启动正式训练。

Epoch 14 LAST 的文件 SHA、保存的 model/optimizer/scheduler/RNG 身份及下一 epoch permutation 已只读核验。Epoch 15 实际完成 3095 次未 checkpoint 更新；任何未来获准恢复必须全部丢弃，重新从 Epoch 14 完整边界开始。监控快照滞后一次 optimizer step，不使用快照计数替代正式 attempt counter。

文件锁持有者及 progress.json 原子替换失败根因尚未确认；恢复数据/GPU/存储预检与远端绑定仍需完成。本次没有训练、state application、forward、backward 或 optimizer update。2025 继续封存，Phase-B 未授权。
