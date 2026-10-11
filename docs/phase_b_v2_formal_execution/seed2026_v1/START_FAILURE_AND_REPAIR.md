# 首次正式启动：预更新停止及精确修复

研究者最新直接指令已授权 seed2026 六组正式执行，并采用 M-C；本次停止不是科学审批缺失。实际启动源码 commit 为 `926cbc09701443366f40faf2b4908c21ebadf7b4`，启动发布收据 commit 为 `e0b17fb`。原 `release.json` 原样保留，没有用修复源码覆盖失败运行的代码身份。

## 真实结果

**STOPPED_NO_RETRY**。自动进程于 2026-10-11 08:02:51 UTC 启动，约 6.016 秒后确认终止。尚未进入第一个模型 fresh 初始化、真实 forward 或 optimizer 调用。

`worker.py:main` 在调用 `adapter.reader.lock_parents()` 时命中继承自 `experimental/phase_b_v2_real_forward_pilot/adapter.py:VerifiedReader.lock_parents` 的 `SELECTED_DIRECTORY_HANDLE_LIMIT`。

该函数面向 48 场景 pilot，最多 512 个父目录句柄。全量清单实际诱导 510 个原始数据父目录，加上冻结 mask 的八个额外祖先，共 518 个。首次集成未替换这一专用上限，属于本次工程遗漏。它在任何原始数据目录句柄创建之前拒绝；不是 SHA 不匹配，也不是 GPU 资源耗尽。

更新永久预留 **0**，实际返回 **0**，真实训练/验证 forward **0**，原始文件 payload 读取 **0**。只读取冻结公开元数据。Job 身份已绑定实际 worker，终止后 Job 空且全部保留句柄 signaled；无自动重试和退款。六组均未开始 epoch。

## 已完成的最小源码修复（未重新执行）

`training/phase_b_v2_seed2026/data.py:Reader.lock_parents` 现在在本次冻结来源下要求恰好 **518** 个目录，禁止重复入场，逐项使用完整注册父目录和原生对象身份核验。未知目录或对象身份异常仍拒绝。`protocol.py:LIMITS.directory_handle_limit` 固定为 518；没有动态放宽正在运行的额度。旧 pilot 和历史冻结源码未改动。

沿用已审计的 `Scope` 年份防火墙：检查精确数据根下的相对年份，而不是将多年份档案基目录名称里的文字误认为已访问 2025。修复人工句柄测试首轮出现这种过宽字符串误拒绝，已在 `directory_repair_attempt_001.json` 保留；修正后 3/3 通过，没有原始文件 I/O。

`supervisor.py:main` 的清理记录改为仅在 campaign 仍 ACTIVE 时填充 watchdog 原因，避免覆盖 worker 已记录的首因。首次失败旧额度库中的通用原因仍原样保留；原始 worker 错误见本目录启动状态与私有 traceback。

## 当前停止边界

修复代码已交付，但未替换原失败发布收据，未删除 `.local/launch.once`，未重置 `.git/phase_b_v2_seed2026_2131d576.*`，未重新执行。原发布 SHA 与修复源码不一致时，正式入口还会在启动前拒绝。

恢复推进只需要研究者另行明确决定：是否允许以新固定源码版本重新启动这次 **零更新** 的失败任务，保持原 seed2026 六组矩阵和总授权额度，并保留本次失败祖先。无需重签 M-C 或重复决定科学矩阵。

正式完整 epoch、全量验证、实际模型 LAST roundtrip 及长程资源稳定性本次均 **NOT_VERIFIED**；既有 smoke 与合成检查不能替代这些未到达的阶段。2025 继续封存，历史路径属性访问维持 NOT_INSTRUMENTED，历史 B1 恢复不追认。
