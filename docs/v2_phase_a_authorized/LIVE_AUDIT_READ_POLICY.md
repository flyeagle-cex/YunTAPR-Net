# v2 Phase-A 外部监控与审计读取规则

本规则仅约束外部观察程序与 Codex 手动审计，不修改冻结训练代码。

1. 运行中的追加日志（steps.jsonl、train_diagnostics.jsonl、validation_diagnostics.jsonl）使用已通过并发测试的 Python reader。若使用 .NET，必须显式以 FileShare.ReadWrite | FileShare.Delete 打开 FileStream，并在读取后立即释放。
2. 禁止对运行中的追加日志使用默认 File.ReadLines、StreamReader(path) 或 PowerShell Get-Content。默认共享方式可能拒绝训练进程的下一次追加打开。
3. 不打开运行中会原子替换的 progress.json、checkpoint_registry.json、BEST/LAST identity 或 history JSON。监控只读取追加日志和发布完毕的不可变轮次报告。
4. 完整日志对账优先在进程已有权威退出记录后进行。运行中若需检查，只读取有限尾部，不持有长时间句柄，不修改或删除日志。
5. 所有读取错误作为独立工程证据保留。不得给冻结训练 writer 加重试、吞掉错误、改变计数器或静默跳过 batch。
6. 本次隔离 fixture 已证明：默认 .NET reader 会使冻结 append_event 抛出 PermissionError；显式共享读取下 1,000 次追加通过。此测试不含模型、optimizer 或原始数据访问。

恢复仍遵循研究者原始授权：完整 epoch LAST、身份预检、独立新 attempt、远端授权绑定在前。2025 保持封存，Phase-B 不授权。外部 I/O 修正不是科学参数变更。
