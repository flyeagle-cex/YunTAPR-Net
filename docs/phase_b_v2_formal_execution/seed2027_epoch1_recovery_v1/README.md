# seed2027：从完整 epoch 1 恢复

本版本绑定研究者本次明确回复“授权从此 LAST 恢复，额度不变（推荐）”。只恢复 B0/E0 的指定 epoch 1 LAST，从 epoch 2 继续，并保持既定六组顺序与全部科学、资源配置。不是 fresh 重跑。

- 指定 LAST SHA256：`e4c0162492ab10bfe3136fa8117c0f5e111078957fa35832e0a88cb5dc1ab0ff`。
- 旧累计预留 75,327，核验 75,326；历史 1 次不确定调用仍计费。
- 保留科研更新 5,228，废弃旧运行消耗 70,099；剩余可调用 277,084，总上限 352,411，不增加额度。
- 旧 DB、失败记录、原 checkpoint 和 epoch 1 验证结果只读保留。新账本只登记已提交边界，不伪造新 optimizer 调用。

## 修复与实际检查

首次停止原因是 epoch 2 前的祖先日志校验把大量 JSONL 完整展开为 Python 列表，触发 MemoryError。新 `evidence.scan` 分块计算完整 SHA 并逐行审核；旧文件以原生只读句柄保持无写/删除共享，后续边界检查同一对象元数据。不会每个 epoch 重新构造大列表。

91 份祖先证据及唯一获准 LAST 共 841,127,979 字节，流式审核约 4.1 秒。独立审核进程峰值工作集 32,272,384 字节；缓存检查小于计时分辨率。此测量只代表审核，不是训练性能预测。

`load_authorized_epoch1` 先复用 v4 完整 Contract 和同字节 `weights_only=True` reader，核对原 identity、数据、AdamW、scheduler、RNG、验证收据，再调用已验证的状态应用函数。新 epoch 2 LAST 的父 SHA 指向指定旧 LAST；安全暂停后继续使用本版本完整 LAST。异常停止不允许自动重试。

## 操作

在仓库根目录 PowerShell 中：

```powershell
# 启动 / 已完成安全暂停后继续
& .\scripts\phase_b_v2_seed2027_epoch1_recovery_v1\Start-Training.ps1

# 等本轮训练、完整开发验证、LAST 提交结束后暂停
& .\scripts\phase_b_v2_seed2027_epoch1_recovery_v1\Pause-Training.ps1

# 本机实时监控，每 10 秒只读刷新
& .\scripts\phase_b_v2_live_monitor\Open-Monitor.ps1

# 只读查询
& .\scripts\phase_b_v2_seed2027_epoch1_recovery_v1\Status-Training.ps1
```

关闭浏览器不会停止训练。启动命令拒绝重复 ACTIVE 或 FAILED 任务；紧急停止不是安全暂停。旧启动脚本不能用来继续本版本。

## 检查记录与限制

只运行新增 13 项恢复/流式/额度检查及 7 项只读监控检查，均通过。首次测试包含 3 个测试环境/夹具错误（Windows 临时目录权限和错误引用不存在的 data.py），随后还有一个重复预留异常类型断言错误；已保留所有日志并修正夹具，未降低安全断言或数值容差，测试没有模型更新。真实恢复结果另见启动收据。

没有重新扫描原始数据。过去未闭合的两项读取不能认定为零，按每项 6 GiB 保守计费；已计费内容总量 2,729,464,684,048 字节，计费时间 146,786.48363 秒。原资源上限不变；这些数值含祖先开销，不可用来外推训练耗时。

统计保持 M-C / 2024 开发探索性；seed2028、FinalFit、2025 不授权；历史 B1 恢复不追认；历史 2025 路径属性查询仍为 NOT_INSTRUMENTED。旧 GPU 驱动崩溃风险未被本次日志修复消除。
