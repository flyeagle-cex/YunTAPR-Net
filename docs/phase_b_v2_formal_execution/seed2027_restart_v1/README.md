# seed2027 单次 fresh 重启

本次真实人类答复：“授权重新启动及额外 386 次额度”。完整问题和来源身份保存在 release.json。原任务在 B0/E0 第1轮因 AVAILABLE_COMMIT_LIMIT 停止，尚无完整 LAST，不能精确恢复。新任务从相同 seed2027 fresh 初态重新运行固定六组，不加载任何历史权重。

旧任务预留386、核验385、未核验1；旧账本和全部失败文件保留原样并以只读句柄绑定。新任务最多282,312次，累计最多282,698次。旧的1次未核验永远不自动改为核验成功，且不退款。新 LAST 和安全暂停只要求新事务全部核验，同时完整保留历史不确定性。

科学配置 config.json 与原任务字节相同。固定 B0/E0 → B1/E0 → B0/E1 → B1/E1 → B0/E2 → B1/E2，9轮/组，seed2027；D1/Q1/N0/I3/B9/S0/V0、FP64统一评价及M-C不变。新campaign/账本用于显式获批的一次重启，失败后无自动重试或恢复。

原系统资源门槛不降低，原累计时间216.172秒、读取3,772,749,927字节继续计入7日/32TiB上限。初次整理祖先字节账时漏计公开清单字节，被检查拒绝；已修复并保留记录。新增测试只检查重启额度、祖先、暂停和checkpoint元数据适配，不重复旧模型测试。

## 命令（仓库根目录 PowerShell）

```powershell
& .\scripts\phase_b_v2_seed2027_restart_v1\Operator.ps1 -Action check
& .\scripts\phase_b_v2_seed2027_restart_v1\Start-Training.ps1
& .\scripts\phase_b_v2_seed2027_restart_v1\Status-Training.ps1
& .\scripts\phase_b_v2_seed2027_restart_v1\Pause-Training.ps1
```

启动只允许本次一次发布，不能用旧入口恢复失败任务。安全暂停等完整epoch、完整开发验证、可信LAST提交后退出，之后同一账本按已授权剩余额度继续。紧急停止用同目录 Emergency-Stop-Training.ps1；失败或不完整事务后恢复需要另行决定。

源版本、依赖、祖先和授权范围在 release.json 固定。新账本 .git/phase_b_v2_seed2027_fresh_restart_v1.sqlite；新权重和完整日志只留本目录忽略的 .local。旧原始数据不修改、不重扫全量SHA；实际消费仍逐次同字节SHA，Windows Job自动监督保持原实现。

旧source、冻结模型/损失/资格和已发表结果均不改。仅纠正复制的结果汇总脚本中静态“SEED2026”说明为实际seed2027，无统计数值定义变化。不启动seed2028或2025/FinalFit，不追认历史B1恢复；历史2025路径属性审计仍为 NOT_INSTRUMENTED。
