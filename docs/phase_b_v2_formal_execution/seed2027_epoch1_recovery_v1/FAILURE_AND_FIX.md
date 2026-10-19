# 本次零更新失败及最小修复

2026-10-19 13:57:14 UTC，`recovery.load_authorized_epoch1` 在 `AUTHORIZED_LAST_METRICS` 检查停止。原因来自本次新增对照，而不是旧 LAST 损坏：10,501 项 `scene_blocks` 在公开 JSON 中是 list，在 checkpoint 中是 tuple。直接 Python `!=` 返回不相等；冻结 `protocol.digest` 对二者生成完全相同的 SHA。train 数据也完全相等。

最小修复见 `METADATA_FIX_PROPOSAL.diff`：使用项目原有的规范化 JSON SHA 比较 train 和完整 validation，仍然拒绝任何数值、顺序、样本身份、字段缺失或非有限变化。`metadata_fix_candidate.py` 及 8 项人工元数据测试已通过；尚未替换本次已封存运行，也没有重新启动。

本次新增预留 0、执行 0；累计预留保持 75,327，上限保持 352,411，原 epoch 1 LAST 完好。实际计费读取 55,517,165 字节（公开元数据与冻结地理初始化），未进行训练样本 forward/backward 或 optimizer.step。终止收据确认 Job 清空；独立原生查询确认 Worker、Supervisor 和 Job 不存在。峰值工作集 959,614,976 字节，峰值 Private Commit 2,223,874,048 字节。

旧 release、源代码、SQLite、launch.once、checkpoint 及本次失败日志全部保留。根据研究者本次“异常停止且不自动重试”的明确约束，修复后的再次发布/启动须获得新的具体决定；本修复文件不提供启动授权。

实时页面仍可独立打开，当前显示真实失败状态；旧启动命令会拒绝 FAILED 账本。安全暂停命令只适用于活跃训练，不能把本次失败转为 PAUSED。
