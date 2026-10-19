# seed2027 epoch 1 恢复：零更新修复后重新发布 v2

研究者本次明确回复“授权零更新修复后重新发布启动”。授权事件绑定在 `authority.py` 和 release 中；本版本只启动一次，异常停止、不自动重试或恢复。

- 原 LAST：B0/E0 epoch 1，SHA `e4c0162492ab10bfe3136fa8117c0f5e111078957fa35832e0a88cb5dc1ab0ff`。
- 从 epoch 2 继续 B0/E0，再按既定顺序完成 B1/E0、B0/E1、B1/E1、B0/E2、B1/E2。
- 累计已预留 75,327，已核验 75,326；历史 1 次不确定调用不退款。
- 保留有效更新 5,228，剩余授权 277,084；总上限 352,411，不增加额度。

v1 因 JSON list 与 checkpoint tuple 的直接比较而零更新停止。v2 改用项目既有 `protocol.digest` 算法比较完整训练和验证报告；数组次序、数值、样本身份、字段与非有限值仍严格校验。未改动 loss、模型、训练/验证循环、AdamW、LR、精度、样本划分或资源上限。

13 项本次差异测试通过（8 项规范化比较、5 项重新发布/额度/代码一致性检查），测试没有优化器更新。另已对指定真实 LAST 执行同字节 SHA、`weights_only=True` 读取和修复后的报告核对，通过；检查过程未创建模型或应用状态。实际模型/AdamW/scheduler/RNG 恢复结果另见启动收据。

v1 和更早的失败源码、release、DB、launch.once、日志与原 LAST 全部保留。109 份旧证据以有界流式审核固定 SHA；旧 v1 的预留/执行为 0，epoch 2 从未开始，Job 与工作进程已退出。资源账本延续 v1 的 2,729,520,201,213 字节和 146,838.53063 秒已计费消耗；不会重置原 32 TiB / 7 日等硬上限。

## 日常命令

先进入仓库根目录，然后执行：

```powershell
# 启动；也用于已完成安全暂停后的继续
& .\scripts\phase_b_v2_seed2027_epoch1_recovery_v2\Start-Training.ps1

# 当前完整 epoch 的训练、开发验证、LAST 提交后退出
& .\scripts\phase_b_v2_seed2027_epoch1_recovery_v2\Pause-Training.ps1

# 只读状态
& .\scripts\phase_b_v2_seed2027_epoch1_recovery_v2\Status-Training.ps1

# 本机只读实时页面，每 10 秒刷新
& .\scripts\phase_b_v2_live_monitor_v2\Open-Monitor.ps1
```

页面地址为 http://127.0.0.1:53079/；53078 是上一次失败版本的历史看板。关闭页面不停止训练。`start` 拒绝重复 ACTIVE 和 FAILED 账本，只有 READY 或已核验完整 LAST 的 PAUSED 状态可启动；紧急终止不等于可恢复暂停。

统计仍为 2024 开发集 M-C 探索性分析。seed2028、2025、FinalFit 不在授权范围；历史 B1 恢复未追认，历史 2025 属性查询仍为 NOT_INSTRUMENTED。
