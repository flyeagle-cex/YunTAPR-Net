# Scientific Freeze v2 paired Phase-A 实现与工程预检交接

科学基线：`d049f7ab7b8a382f47a5fe54384ea9416a22cde9`。本次新增独立 v2 runner、恢复事务、只读诊断、预检、监控和发布模块；不修改既有科学合同或历史训练证据。

## 已完成

- 入口：`scripts/run_paired_phase_a_v2.py`。正式 train/resume 必须另行提供绑定代码、配置、预检、样本身份及 checkpoint 的研究者授权；科学冻结批准不等于启动授权。
- 独立 checkpoint 根目录、完整 epoch 恢复身份核验、BEST/early-stop 分离、计数器分域、2023/2024 数据白名单、只读 upper-tail 诊断及 localhost 监控已实现。
- [五份执行规范](../v2_phase_a_execution_plan/V2_PHASE_A_EXECUTION_PLAN.md)已保存。
- [最终测试证据](test_runs/run_20261007_full_004/test_summary.json)：770/770 PASS（新 runner 34、v2 数值 39、既有 regression 697），无 skip。测试代码 SHA 已绑定。
- 此前失败保留在 `implementation_attempts/` 与 `test_runs/run_20261007_full_001` 至 `003`。分别修复测试临时目录权限/中文 NetCDF 路径、历史源清单核验作用域、既有 optimizer 执行层约束；未改写旧测试或旧科学证据。
- 历史 FinalFit artifact 测试使用显式隔离的历史文件清单，逐项核验原清单 SHA；新增 v2 文件单独绑定当前代码身份，不把新增文件误当成旧 run 曾执行的代码。

## 尚未关闭的工程门

独立 `ENGINEERING_ONLY` run：`runs/run_20261007T031200_000001Z/`。
交接时为 `SOURCE_SHA_PREFLIGHT`：核验全部 67,006 个允许的 2023/2024 源文件，随后执行两个模型各自的 batch2、singleton、validation batch8/tail5 GPU smoke 与存储预算核验。

**此报告不宣布预检 PASS 或正式 runner 已获准启动。** GPU smoke 尚未完成，不把 NOT_RUN 当作 PASS。只有完整 `preflight_manifest.json` 和最终 IO 对账形成后，才可关闭这些工程门。后台流程不包含 train/resume 命令；成功后等待审批，失败则保留独立失败证据并停止。

进度页：http://127.0.0.1:8769/ 。用户可等待脚本结束后通知继续收尾。此次 Git 提交发布实现、规范和已经完成的测试证据，不将正在写入的预检日志作为最终证据。

## 状态

```text
PLAN_READY_FOR_RESEARCHER_REVIEW=true
V2_SCIENTIFIC_FREEZE_APPROVED=true
ENGINEERING_PREFLIGHT_STATUS=RUNNING
FORMAL_TRAINING_AUTHORIZED=false
V2_PHASE_A_AUTHORIZED=false
V2_PHASE_A_STARTED=false
V2_PHASE_B_AUTHORIZED=false
FORMAL_OPTIMIZER_STEPS=0
2025_RAW_ACCESS=0
2025_PIXELS_READ=0
RESEARCHER_DECISION_REQUIRED=true
```

2025 零访问声明限于本轮受控执行路径及已完成测试；完整预检结束仍需 IO 收据对账。正式训练、旧 Phase-B 恢复和 B1 Phase-B 均未启动。
