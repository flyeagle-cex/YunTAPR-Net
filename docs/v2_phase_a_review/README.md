# v2 配对 Phase-A 只读评价准备

此目录独立于固定 implementation checkout，不修改正在运行的模型、训练逻辑或科学配置。

已实现 `metrics.py`：复用冻结 `LogDomainValidation` 核心损失与历史 `grouped_occurrence_metrics` 的精确同分组 AUROC/AP 定义；新增汇总 Brier 与条件 pinball。发生事件仍按原 float32 target > 0.1 mm/h 判定。Brier/AUROC/AP 使用全部有效云南 scene-pixel，条件 pinball 使用 rainy 有效 scene-pixel；每个像元先对 32 tau 求均值。不进行物理量实例化，不参与 BEST 或早停。

CPU 合成测试 5/5 PASS，见 `synthetic_test_results.txt`。测试不构建模型，不读取 checkpoint/raw，不执行 forward/backward/optimizer。既有 770 项预检测试证据保持原样；本轮没有重新运行整套 regression。

尚未完成：两模型正常结束后的 BEST 只读全量 2024 reinference、最终 counters/历史/身份对账、paired comparison packet。该组件测试通过不代表这些工作完成。后续仅在两个 `final_report.json` 均为 COMPLETE 且 BEST 身份、SHA、完成标记及授权核验通过后，才允许独立评价进程使用 GPU；不与训练竞争资源。不访问 2025，不加载 optimizer 状态用于执行，不进入 Phase-B。

`run_review.py` 为独立执行入口，要求原授权 SHA。即使传入 `--execute`，两模型尚未完成时也会在导入 PyTorch、读取 checkpoint 或 raw 之前返回 `REVIEW_INFERENCE_ALLOWED=false`；当前拒绝证据见 `early_execution_rejected.json`。完成门另有 4 项纯元数据生命周期测试。真实评价尚未运行；语法/禁止更新调用检查不能替代未来真实全量核验。

正式评价前重新核验所有完成 checkpoint 和逐 epoch 本地 artifact SHA；BEST provenance 核验后仅应用模型状态，不应用 optimizer/RNG。只允许 2024 源白名单，固定 batch8/顺序全量推理；逐项精确复核训练时保存的 BEST validation 指标，检查前后模型与 checkpoint 身份不变，再生成 `paired_comparison_packet.json`。最终仍需对训练、恢复计数、发布状态及人类可读决策包进行收尾审计，不因 JSON 生成而自动标记整个 Goal 完成。

2026-10-08 恢复适配：研究者主动停止的原 `process_exit.json` 保持原样。后续评价应传入 `docs/v2_phase_a_authorized/pair_20261007T070503_825794Z/resume_20261008T001111_821825Z/authorization.json`，SHA256 为 `321a768205efc3116ab4e1185d9c7d54dc6a2c4b27e21f605bb7e27c26dffc93`。完成门读取该恢复 attempt 的退出凭证，并核验恢复授权与原授权的冻结科学、代码、运行及样本身份一致；checkpoint provenance 仍绑定原始授权 SHA，不将恢复授权冒充 fresh 初始化授权。

纯元数据完成门测试现为 8/8 PASS（原 4 项及新增恢复身份 4 项），见 `recovery_completion_gate_tests.txt`。两次沙箱临时目录权限失败分别保存在独立日志；正常权限下测试通过，不修改正式训练环境或 runner。实际未完成门见 `recovery_early_execution_rejected.json`，仍在导入 PyTorch、读取 checkpoint 二进制和 raw 之前拒绝评价。
