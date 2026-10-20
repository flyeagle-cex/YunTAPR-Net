# 心跳快照读写冲突：人工复现与修复候选

2026-10-20 约 07:57，当前 epoch2 恢复任务在替换 `heartbeat.json` 时收到 WinError 5，按约束停止。632 次新增更新全部 RETURNED_VERIFIED，无在途更新；累计预留 86,415、核验 86,414。最近完整 LAST 仍是 B0/E0 epoch 2，SHA `b6062fe5b747924cc7cdf6cfce38f43f9f71fa9a1ad8ee10065cc987e875c3ce`。终止收据及独立原生查询确认 Worker、Supervisor、Job 均不存在。

`live_monitor_v2` / 53079 显示的是上一次 epoch1 恢复任务。`live_monitor_epoch2` / 53080 才指向本次任务，但本次任务确实也已停止，不能只以“打开旧页面”解释。

## 已确认与未确认

- 普通 Python JSON 读取句柄可复现 Windows 拒绝 `os.replace`；看板的 `read_json` 和状态查询的严格心跳 reader 存在这种并发冲突路径。
- 没有记录失败时具体持锁进程，不能断言该次错误完全由看板引起。
- 首先尝试的“仅让读取句柄允许共享删除”在本机依然无法通过替换与并发测试，候选已拒绝；沙箱与原生主机首次失败记录均保留。
- 新修复使用路径绑定的 Windows named mutex，让可变状态文件的读取与原子替换互斥。每次等待最多 2 秒；超时、弃置锁、写入异常均报错，保留 `.part`，不重试、不涉及优化器。
- 冻结数据和 checkpoint 的严格 reader 完全不变。新接口不能提供训练权限或作为 checkpoint reader。

## 验证

9 项人工 JSON 检查通过：旧行为复现、读者退出后写者继续、80 次写入/160 次一致读取、词法拒绝、大小/格式、锁超时、非有限与重复键、严格 reader 未削弱、跨进程互斥。未导入 PyTorch、读取原始数据、加载权重或执行模型更新。

## 必须同时接入的差异（未应用到失败版本）

未来获准的新恢复版本需同时：

1. 对 `heartbeat.json`、`progress.json`、`execution_status.json` 的 writer 调用 `atomic_status_json(path, value, OUT)`。
2. 看板的固定元数据读取改为 `read_json_snapshot(path, ROOT, maximum)`。
3. `control.status` 的心跳读取也使用同一互斥 reader；不可继续用未协调的严格只读句柄打开可变心跳。
4. immutable identity、授权、数据与 checkpoint 的拒绝规则、身份与 SHA 规则保持不变。

不能只替换看板 reader 而让 writer 不参与互斥。外部不合作读者或杀毒软件等仍可能阻止替换，此时继续 fail-closed；本次测试不证明所有外部干扰已消除。

旧失败源码、账本、launch.once、`.part` 和 checkpoint 未修改。恢复训练需要新的具体决定：保留 86,415 次消耗，从同一 epoch2 LAST 重放本次 632 次消耗，若完成原矩阵则累计上限需从 357,639 增至 358,271。此处只是算术与修复候选，没有创建启动授权。
