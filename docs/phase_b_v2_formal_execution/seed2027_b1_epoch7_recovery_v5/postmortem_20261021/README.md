# 本次零更新启动失败：精确原因与修复候选

状态：**FAILED_NO_RETRY，新增预留 0，新增执行 0**。累计预留仍为 166,305，已核验 166,304，上限 364,969 未改动。

本文件是后续只读观察，不重写 v4/v5 release、账本、启动标记或原始失败记录。B0/E0 第九轮结果保留，B1/E0 最近完整 LAST 仍为第七轮，SHA：

`bd2e12c38551e1356add16990a8edd17fa3c20a8594863005c90461b27b6931a`

## 具体源码问题

`src/yuntapr/training/phase_b_v2_seed2027_b1_epoch7_recovery_v5/engine.py::completed_result`

读取已经完成的 B0/E0 结果时执行 `from .ancestor import Guard, COMPLETE_PREFIX`。v5 的 `ancestor.py` 未重新导出 `COMPLETE_PREFIX`，因此在 Engine 构造阶段触发 ImportError，尚未创建本次训练模型或进行更新。Worker 的原始错误、Supervisor 的停止收据及 GUI Job 清理收据均保留。

进一步检查全部运行模块的函数内相对导入，另发现 `recovery.py::load_authorized_last` 需要的 `RECOVERY_PREFIX`、`SOURCE_CP` 也未导出。不能只修复第一个报错后就再次启动。

## 已完成的修复验证

- 独立候选：`src/yuntapr/experimental/phase_b_v2_recovery_interface_candidate/exports.py`。
- 6 项回归全部通过，包含原始缺失绑定复现、全量相对祖先导入核对、实际 `completed_result` 函数在人工收据上的执行、实际恢复导入语句核验及源码未改动检查。
- 仅需保留原有 v4 提供的三个路径常量；模型、loss、数据资格、checkpoint 字节、训练预算与科学参数均不应变化。
- `MINIMUM_INTERFACE_FIX.diff` 是非执行提案，未应用到失败版本。其前提是模块中的 `prior` 仍指向 v4；若未来新版本以 v5 为直接祖先，应显式从原 v4 提供者导入这三项，不能向缺少它们的 v5 再次索取。

## 已核验的停止边界

Owner、Worker、GUI bootstrap 及两个命名 Job 均已不存在。已保存的内外层 termination 收据确认进程树清空。三个实际进程登记的控制台检查均为 `hwnd=0`、`process_count=0`。

这证明本次无控制台启动结构实际运行过，**没有证明真实关闭 Codex 的长期训练场景已通过**。当前失败是 Python 模块接口遗漏，不能归因于用户启动命令，也不能归因于新的 GPU 训练崩溃。

任务已按“异常停止、不得自动重试”停止。本次审查没有启动 v6、重置旧账本或再次读取原始观测。进入新启动版本仍需研究者明确允许一次零更新修复后重新发布；不需要再次增加额度。

历史 2025 路径属性审计继续为 NOT_INSTRUMENTED，历史 B1 恢复治理偏差未追认，seed2028 未获执行许可。
