# v2 配对 Phase-A 只读评价准备

此目录独立于固定 implementation checkout，不修改正在运行的模型、训练逻辑或科学配置。

已实现 `metrics.py`：复用冻结 `LogDomainValidation` 核心损失与历史 `grouped_occurrence_metrics` 的精确同分组 AUROC/AP 定义；新增汇总 Brier 与条件 pinball。发生事件仍按原 float32 target > 0.1 mm/h 判定。Brier/AUROC/AP 使用全部有效云南 scene-pixel，条件 pinball 使用 rainy 有效 scene-pixel；每个像元先对 32 tau 求均值。不进行物理量实例化，不参与 BEST 或早停。

CPU 合成测试 5/5 PASS，见 `synthetic_test_results.txt`。测试不构建模型，不读取 checkpoint/raw，不执行 forward/backward/optimizer。既有 770 项预检测试证据保持原样；本轮没有重新运行整套 regression。

尚未完成：两模型正常结束后的 BEST 只读全量 2024 reinference、最终 counters/历史/身份对账、paired comparison packet。该组件测试通过不代表这些工作完成。后续仅在两个 `final_report.json` 均为 COMPLETE 且 BEST 身份、SHA、完成标记及授权核验通过后，才允许独立评价进程使用 GPU；不与训练竞争资源。不访问 2025，不加载 optimizer 状态用于执行，不进入 Phase-B。
