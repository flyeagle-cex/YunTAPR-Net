# Phase-B v2 生产结构隔离 Runner 候选 v1

状态：SYNTHETIC_ENGINEERING_ONLY；RESEARCHER_DECISION_REQUIRED。已实现完整人工 epoch 事务，不具备真实数据读取和正式执行能力。

基线：435f303a1bdebb30a687f8e02dd8576d0d28cb55。新源码：src/yuntapr/experimental/phase_b_v2_formal_runner_candidate/，9 个模块。测试：tests/phase_b_v2_formal_runner_candidate/。本轮 79 CPU、8 CUDA 唯一检查通过；30 次合成更新；正式更新/运行均 0。

- EXISTING_FUNCTION_INVENTORY.md：既有功能与本轮新增结构。
- COMPLETION_AND_RESUME_CONTRACT.md：epoch → 完整验证 → LAST、恢复与额度。
- ENGINEERING_RESULTS.md：实际闭环、资源与未验证项。
- TEST_AND_FIX_RECORD.md / tests/：首轮失败、修复与真实日志。
- FUTURE_DATA_ADAPTER_SPEC.md：未来数据及批准接口，当前不可执行。
- EXECUTION_DECISION_GATE.md：压缩后的独立研究者决策。
- source_identity.json / manifest.json / final_status.json：来源、SHA 和真实状态。

本轮选择以简洁代码和 Markdown 交接；既有 LaTeX/PDF 审查材料继续保留，未复制旧报告。合成权重和完整机器日志只在本轮 .local 临时目录，不提交 GitHub。
