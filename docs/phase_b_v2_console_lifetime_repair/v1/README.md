# 关闭客户端后的控制台生命周期排查

本轮只读排查当前 seed2027 停止状态，并开发、测试独立的人工进程修复候选。没有重启训练、读取真实数据/模型权重、修改旧额度或执行 optimizer 更新。

## 已确认事实

- 用户报告：当时只关闭了 Codex，没有关闭 PowerShell 或按 Ctrl+C。
- 2026-10-21 08:59:57（北京时间）后训练心跳停止。实际 Owner、Worker、命名 Job 都不存在；账本仍为 ACTIVE，属于 `STOPPED_UNCLEAN`。
- 系统任务退出码 `0xC000013A`。这属于控制台终止类退出证据，不能据此唯一确定发起者，更不能反推用户按过 Ctrl+C。
- 本次中断前新增 922 次更新，全部返回核验；累计已预留 166,305，已核验 166,304。历史 1 次不确定调用仍计费。上限 364,047 未修改。
- B0/E0 已完成第九轮；B1/E0 最近完整 LAST 为第七轮，第八轮未提交 LAST。其余四组未开始。
- 再运行原 `Start-Training.ps1` 被 ACTIVE 防重入保护拒绝。它没有创建第二个训练进程，也没有修复失效会话。

## 修复候选及验收

源码：`src/yuntapr/experimental/phase_b_v2_console_lifetime_candidate/`。

1. 使用系统任务启动 GUI bootstrap（`pythonw`），移除外层控制台 PowerShell。
2. GUI bootstrap 仅启动固定的人工 Owner，使用原发布的 `python.exe`，且在解释器创建前固定环境。
3. 在最终原生 Python Owner/Worker 内执行 `FreeConsole`（如已附着），再核验 `GetConsoleProcessList=0` 且 `GetConsoleWindow=0`。不能只检查 venv 包装进程或 `CREATE_NO_WINDOW` 标志。
4. GUI bootstrap、Owner 分别持有 kill-on-close Job；异常仍停止所属进程树，不通过忽略所有控制信号掩盖失败。

新增套件 **5 项通过、0 失败、0 skipped**，详见 [ARTIFICIAL_RESULTS.json](ARTIFICIAL_RESULTS.json) 与 [tests/attempt_006.log](tests/attempt_006.log)。测试覆盖私有人工控制台 CTRL_BREAK、人工客户端 Job 关闭、GUI bootstrap 崩溃、Owner 崩溃和路径拒绝。全部人工进程已清理。

**边界：**没有在本轮真的关闭正在使用的 Codex，因此真实应用退出全链路仍为 NOT_VERIFIED。人工测试证明修复候选的控制台与 Job 隔离能力，不证明本次中断的唯一根因，也不赋予正式恢复权限。

## 继续训练所需的具体变化

修复尚未接入正式恢复发布，旧发布与旧 SQLite 保持原样。现有命令只能在合法 READY/PAUSED 边界启动，不能继续此次未完整结束的 ACTIVE 会话。

若研究者决定继续，应在独立恢复版本绑定同一 B1/E0 第七轮 LAST：

`bd2e12c38551e1356add16990a8edd17fa3c20a8594863005c90461b27b6931a`

第八轮的 922 次消耗不能退还。从第七轮重放并完成既定六组，所需累计额度为 `166305 + 198664 = 364969`，较现上限增加 922。该变化 **尚未批准**；本包不会修改任何授权器、账本或正式启动入口。

## 来源与限制

- [Microsoft：CREATE_NO_WINDOW](https://learn.microsoft.com/en-us/windows/win32/procthread/process-creation-flags)：该标志作用于所创建的进程；必须核查最终解释器状态。
- [Microsoft：控制台事件处理](https://learn.microsoft.com/en-us/windows/console/setconsolectrlhandler)：控制台信号与进程生命周期独立于单纯的父进程名称检查。
- [Microsoft：NTSTATUS](https://learn.microsoft.com/en-us/openspecs/windows_protocols/ms-erref/596a1078-e883-4972-9bbc-49e60bebca55)：`0xC000013A / STATUS_CONTROL_C_EXIT`。

未触及 2025 内容；历史 2025 路径属性审计仍为 NOT_INSTRUMENTED。历史 B1 恢复治理偏差未追认。
