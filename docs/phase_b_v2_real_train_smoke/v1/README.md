# 首次真实数据训练链路冒烟测试

本轮完成 `BOUNDED_REAL_TRAIN_SMOKE_PASS`：B0/E0、B1/E0 各一次真实更新，永久账本 `COMPLETE_SEALED`，不再执行。
这是限定工程测试，正式 Phase-B 更新为 **0**。原始数据、像元数组、模型权重和私有路径未纳入公开交付。

基线本地与 GitHub main：`86cf8ea0ab8410542997ced6e3689880f6e2e0e0`；新提交身份以本目录的 Git 历史为准。
实际执行 UTC：2026-10-10T15:52:46.218195+00:00 至 2026-10-10T15:53:01.162848+00:00；上海时间为 2026-10-10 23:52 至 23:53。

- [真实训练审计](REAL_TRAINING_SMOKE_AUDIT.md)：固定样本、次数、结构与公式。
- [梯度和优化器](GRADIENT_AND_OPTIMIZER_REPORT.md)：分组、裁剪、参数 SHA。
- [Checkpoint 事务](CHECKPOINT_TRANSACTION_REPORT.md)：两份本地工程产物及安全读取。
- [数据身份](DATA_IDENTITY_AND_ACCESS_REPORT.md)、[资源](RESOURCE_REPORT.md)、[问题](FAILURES_AND_BLOCKERS.md)。
- `final_status.json`、`DATA_ACCESS_RECEIPTS.json`、`QUOTA_RECEIPT.json` 和 `TRANSACTION_EVENTS.jsonl` 为脱敏机器收据。
- [源码身份](source_identity.json) 区分真实执行版本与执行后 PID 监控修复；准确执行源码副本在 `execution_source_snapshot/`。
- 两页中文审查摘要：[PDF](REAL_TRAIN_SMOKE_REVIEW.pdf)、[可编辑 LaTeX](REAL_TRAIN_SMOKE_REVIEW.tex)。未修改此前打开的 forward pilot 文档。
- 新代码：`src/yuntapr/experimental/phase_b_v2_real_train_smoke/`。入口是一次性工程任务，正式入口始终拒绝。

最终新增静态/微型张量防护测试 **39 通过、0 失败**；实际 smoke 2 个事务通过。保留首轮失败及后续环境权限失败记录。
外部 watchdog 曾监控 venv 包装进程，不能采用其 5 MB 数字作为工作进程峰值；该修复未重跑真实 smoke。
实际进程自身 Win32 峰值工作集 2.285 GiB，GPU 峰值 reserved 3.199 GiB，均未超过本轮上限。

学习与审查顺序：`data.py` → `quota.py` → `operations.py` → `run.transaction` → `checkpoint.py` → `resources.py`/`launch.py`。
保留科学审批边界，IMERG Final 仅为回顾性监督，随机初态 loss 不作科研比较。
