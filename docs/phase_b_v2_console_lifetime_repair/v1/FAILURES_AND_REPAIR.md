# 人工测试失败与修复

原始日志留在本包 `.local/raw_logs/`，公开日志仅删除本机私有路径前缀。SHA 对照见 TEST_LOG_IDENTITY.json。所有失败均发生于人工进程，不涉及训练更新。

| 尝试 | 结果 | 发现与处理 |
|---|---|---|
| 001 | 1 通过，4 error | 人工客户端 AllocConsole 返回 WinError 5，尚未生成注册收据；无系统任务启动。保留原日志。 |
| 002 | 单用例 error | 增加人工异常收据，确认客户端已附着控制台。测试先对自身 FreeConsole，再创建独占控制台。 |
| 003 | 1 通过，4 error | GUI bootstrap 无控制台，但最终 `python.exe` Owner 仍附着控制台，被严格断言拒绝。仅改创建标志或隐藏窗口不足够。 |
| 004 | 单用例 error | Owner/Worker 脱离后存活，但对人工 HWND 发送 WM_CLOSE 未证明客户端退出。Windows Terminal/伪控制台情形下不能将此动作记作关闭通过。 |
| 005 | 单用例 fail | 改为严格绑定人工客户端私有控制台的 CTRL_BREAK，信号隔离通过；停止收据过早，仅等待 Job PID 列表为空，尚未等持有的原生句柄进入 exited。 |
| 006 | 5 通过，0 失败 | 同时等待 Job 列表为空与全部持有句柄退出；控制事件、客户端 Job 关闭、GUI/Owner 崩溃及清理全部通过。 |

未修改容差、科研模型、batch、精度、真实数据路径或更新额度。没有重复真实 smoke 或重跑正式训练。

WM_CLOSE 测试仍保留为失败证据。最终通过的是私有人工控制台控制事件和客户端 Job 销毁两类测试，不冒称真实 Codex GUI 已在本轮关闭验证。

最终静态公开检查首次把检查器自身包含的通用路径模式误判成私有路径（`PRIVATE_PATH_IN_PUBLIC_ARTIFACT:finalize_review.py`），在写入 manifest 前停止。修复为以字符构造检查模式，保留相同拒绝规则；未放宽隐私检测或重跑任何训练。

首次暂存差异检查把新生成公开文件的 CRLF 识别为尾空白。仅将本次未发布包规范化为 LF，并同步重算公开日志/manifest SHA；私有原始日志和历史证据未改动。
