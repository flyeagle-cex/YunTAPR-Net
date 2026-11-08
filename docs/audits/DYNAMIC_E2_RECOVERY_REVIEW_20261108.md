# DYNAMIC-E2-RECOVERY-20261108｜限定新增差异审核

- 审核者：Harness（独立于 Codex）
- 审核对象：B8/2029/E2/E8→E9 恢复的 4 份既有源码改动、新 `dynamic_loss_recovery.py`、新启动器、新测试、EXECUTION_PROPOSAL/VERIFICATION
- 范围：只审恢复启动差异与 10 项 CPU 合成检查；未读真实数据/权重/缓存/2025，未启动训练，未改 Codex
- 结论：**PASS_WITH_LIMITATIONS（限定恢复启动准备；无执行批准）**

## 1. 指纹与测试

Codex 执行提交 `f3b90f654b67fda538f4f156422841b69cc50b23`（已 push），当前固定副本起点；`VERIFICATION` 的 8 artifact 匹配：

- EXECUTION_PROPOSAL 100,638 B / `2D74177F...225D`
- engine.py 19,391 B；recovery.py 14,327 B；dynamic_loss_recovery.py 19,199 B；dynamic_training.py 22,568 B
- test 9,504 B；start_dynamic_loss_recovery 2,182 B；start_independent_process 13,161 B
- proposal 规范 SHA `9FEA...2713`；`VERIFICATION` SHA `E88FA4CB...F665`
- 提案 `authorized=false`、无输出目录、无 affirmative approval。

独立运行：

```text
F:\conda_envs\rain-basics\python.exe -B -m unittest -v tests.research_readiness.test_dynamic_loss_recovery
```

首次运行因主机无可写默认临时目录失败（torch AdamW 导入需要 temp），不是测试断言失败；设置自身工作区外临时 `TMP/TEMP/TORCHINDUCTOR_CACHE_DIR` 后重跑，**Ran 10 tests, OK**，failures/errors/skips 均 0；未安装依赖、未读真实载荷。

## 2. 代码审查

- `prepare` 校验原 E2 proposal/private digest、researcher-visible scope/STOP 指纹、上一包 proposal/execution commit、B8 updates=4320、E9 checkpoint 尚不存在、E8 checkpoint 收据 SHA/epoch/updates/E2 loss、checkpoint size、24 GiB 空闲、完整 data/runtime/code 依赖。
- `budget` 精确：480 新更新全部重放；53,063,828,496 源字节/15,869 次；3600 秒上限；24 GiB；检查点 SHA 读 1/反序列化 1；累计 9120 更新/1,004,416,034,948 B/300,232 次；后续重试 0；与用户范围一致。
- `B8E2Resume` 只允许 B8/E9，校验 plan/decision/checkpoint SHA，`RecoveryLedger` offsets=3840/segment=480/prior=4320/cumulative=4800，仅 3841–4320；`restore_last` 校验 model/AdamW/optimizer groups/schedule/loss_config/data identity，恢复 Python/NumPy/CPU/CUDA RNG，并分别校验模型与优化器 state digest。
- `RemainingReaders` 只允许 B8 E9 Train/Development；`worker` 核对 controller PID/claim/code commit、PYTHONHASHSEED=2029、24 GiB、静态源额度、E9 Train 摘要与失败前保存值逐字段相等、480 段 ledger、E9 full source pass、E9 receipt loss/mode/commit。
- `execute` 在 `checked` 后建立 fresh output，写授权/claim，超时/失败立即停止且无重试；B7 仅由 parent pins 继承，恢复任务只含 B8，不重训 B7。
- WMI `APPROVAL_BOUND_EXECUTION` 仅新增 `start_dynamic_loss_recovery` 白名单；新 gate 要求精确 B8/2029/E2/480 replay/3600s/解释器 SHA，并保留外部 approval、提案/预算/选择/输出、实际 HEAD 和未消费目录检查；未借用 ENGINEERING_PROBE，旧入口规则保持。

## 3. 非阻断观察

1. WMI gate 本身未核对 checkpoint SHA、new_source_bytes/files 和 B7 parent pins；这些由 `dynamic_loss_recovery.checked` 在创建输出前或 `restore` 时校验。实际 checkpoint 错误会在恢复读取阶段失败，不会训练，但 WMI 层可以再前置检查 checkpoint/完整预算。
2. 恢复仍要求 3600 s/24 GiB/单次 WMI 批准；`execute` 失败即停、无自动重放。没有任何真实 CUDA 证明 480 更新能在上限内完成。
3. 当前提案 authorized=false、无研究者批准对象；本审核不是启动批准，也未生成 approval。
4. 10 项为 CPU/mocks；`VERIFICATION` 的 29 项总通过包含 19 项旧检查，本审核未重跑旧检查；B7 继承/真实 checkpoint 内容未由本审核读取。
5. 首次测试失败是主机临时目录缺失，已用自身临时目录重跑；未改 Codex 或安装依赖。

## 4. 结论与状态

**PASS_WITH_LIMITATIONS（限定恢复启动准备）**：E2 身份、E8→E9 恢复、全模型/AdamW/调度/RNG、3841–4320 账本、E9-only readers、外部 approval 绑定、WMI 入口、源额度、失败即停及 B7 继承边界均与请求一致；未发现阻断性错误。当前仍未获研究者准确批准，不启动。

- 工程：**PASS_WITH_LIMITATIONS（不构成启动/科学验收）**
- 科学：**NOT_VERIFIED**
- 外部 Stage 4.5：**PARTIAL**
- 研究者掌握：**NOT_ASSESSED**

本轮未生成批准、未启动模型、未读科研载荷/缓存/2025，未改 Codex/Shared 共同决策/规则/main。
