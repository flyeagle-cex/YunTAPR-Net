# 故障与修复记录

原日志/人工文件保留在新 .local/；公开日志仅脱敏绝对路径前缀，不删错误/失败数。tests/log_provenance.json 记录原始与公开 SHA。无自动重试、退款、真实更新。

| 顺序 | 状态 | 原因与处置 |
|---|---|---|
| 初始静态编辑 | FAIL（已修正） | 路径比较曾含多余条件表达式优先级错误，执行前删去，保留严格原生路径比较 |
| checkpoint 初跑 | FAIL（23 errors） | 我误写 RunSpec 参数顺序/模型展示名；全部停在 fixture 构造，无模型/数据/优化器 |
| 第一次 fixture 修正 | FAIL（23 errors） | 我误用 model_id 关键字；改为真实 experiment_id='E0', model='B0_MATCHED_V2', seed=2026 |
| 23 方法复测 | PASS | checkpoint_repair_2.log |
| 保存到登记补强后25方法 | PASS | 三者 SHA 一致与拒绝伪批准 flags |
| PowerShell 命令构造 | FAIL（执行前） | Bash 花括号列表导致 ParserError；改为明确参数；原命令未执行测试/目标访问 |
| 最终27方法 | PASS | checkpoint_final_27.log |
| 新 Job15方法 | PASS（首次） | 14外层+1内层启动，无失败后重启 |
| 新边界8方法 | PASS（首次） | 匹配才安装人工 dict；拒绝 pending/FAILED/回退 |
| CIM 进程枚举 | NOT_VERIFIED | sandbox 拒绝；使用 Job 句柄清空与 Get-Process，后者无残留 |
| PDF初版导出 | FAIL（位置/版面已修正） | native参数未展开，写入本轮新建的字面变量目录；已移入本轮.local，使用固定build目录重编为两页并逐页检查 |

最终 **50 方法通过，0 未修复失败**。子测试不另加计数；之前46个错误实例不伪计通过。没有重跑历史模型、真实 smoke 或完整指标套件。

另8项交付静态检查通过，独立记录于delivery日志。普通sandbox内GitHub读取曾网络连接失败；使用已授权的网络提升重新核对，不据缓存假设远端身份。

负面测试 PASS 指正确拒绝/停止，不是故障事务成功。孤立文件仍在但不能采用。sharing 与 SHA 联合验证，不声称所有恶意主机/掉电风险已消除。
