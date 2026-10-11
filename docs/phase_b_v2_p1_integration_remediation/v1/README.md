# Phase-B v2 P1 隔离工程修复 v1

2026-10-11；本地与核验时远端 main：ef74d94eecaa8ee74a23e02d0c0fedbc419414de。

**新隔离人工路径通过；正式训练 NOT_READY / NOT_AUTHORIZED。** 旧读路径与启动器没有被覆盖，本轮没有模型实例化、数据读取、GPU 操作或优化器更新。

| 能力 | 状态 | 范围 |
|---|---|---|
| 同句柄、同字节 checkpoint 与人工状态恢复 | PASS | 微型 CPU 人工容器；27 项测试 |
| Windows Job 启动、身份绑定与整树关闭 | PASS | 无科学依赖的人工进程；15 项测试 |
| 完整边界交接与正式入口拒绝 | PASS | 8 项新增合成/静态检查 |
| 正式真实模型/AdamW/CUDA RNG 恢复 | NOT_VERIFIED | 未打开历史/smoke checkpoint，未加载模型 |
| GPU、长程训练、掉电持久性 | NOT_VERIFIED | 人工 Job 的 256 MiB 上限不适用于模型 |

源码：src/yuntapr/experimental/phase_b_v2_p1_integration_candidate/。

- scope.py：词法防火墙与持有的目录句柄。
- contract.py：复用完整 B9 envelope 校验，独立 CPU RNG 适配。
- checkpoint.py：原子保存复用、注册收据、同字节读取与人工状态安装。
- launcher.py / worker.py：固定人工启动预算和 Job 监控，无任意 argv 接口。
- integration.py：ArtificialRunner 聚合两个修复能力；复用 B9State.check_restore。
- __init__.py：正式启动/恢复无条件拒绝。

审查顺序：[同字节审计](CHECKPOINT_SAME_BYTES_AUDIT.md)、[Job 审计](JOB_WATCHDOG_INTEGRATION_AUDIT.md)、[故障记录](FAULT_INJECTION_RESULTS.md)、[正式差异](FORMAL_ENGINEERING_READINESS.md)、[审批门槛](REMAINING_AUTHORIZATION_GATES.md)。可编辑摘要：P1_REMEDIATION_REVIEW.tex 与对应 PDF。

最终 27 + 15 + 8 = **50 通过，0 未修复失败**。最初两轮各 23 个 fixture 参数错误全部保留，未计入通过。14 次外层人工启动、1 次内层 monitor，共 15 个永久预留；上限预先固定 24，不退款、无自动重试。进程测试一次已全通过，不应无理由重复。

另有8项交付静态检查通过：manifest字节/SHA、脱敏、方法计数、旧文件保护、启动当时源码身份、额度/终止收据、拒绝式状态和LF/Python语法。它们不计入上述50项功能测试。两页PDF已编译并逐页检查。

本地 Python 环境设置 PYTHONPATH=src、PYTHONUTF8=1，分别运行 tests/test_checkpoint.py、tests/test_launcher.py、tests/test_integration.py。Job 测试仅支持 Windows，不降级 PID-only 终止；固定 campaign 账本有跨进程额度。tests/protected_audit.py 只读检查原文件 SHA 和封存额度。.local/ 只保留人工 payload、原始日志及账本，不公开。

manifest.json 绑定新成果及未改动来源 SHA。为避免自引用哈希矛盾，交付身份取包含本文件的 Git commit；不是科学批准。未编辑原先打开的 LaTeX 文档。
