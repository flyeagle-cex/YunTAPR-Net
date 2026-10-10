# Phase-B v2 消融候选代码与合成验证 v1

本轮交付真实候选实现，而非另一版实验计划。研究者本轮明确委托先开发、后学习与审查；因此上轮“先由研究者亲自写练习”的开发前置顺序在本轮独立候选范围内被新指令替代。历史预注册材料保持原样，正式科学批准、正式路径集成和训练执行仍须独立决定。

起始本地/远端 main 同为 c6d938f4afc7780b29caf3ae84cfc2ef8ff70ed9，已跟踪工作区干净；新候选目录不存在，只读进程核对未见 Python/LaTeX 任务。旧未跟踪文件不清理、不提交。旧 v1 FinalFit 入口不作为本轮 runner。

1. [架构](IMPLEMENTATION_ARCHITECTURE.md)、[配置合同](ABLATION_CONFIG_CONTRACT.md)。
2. [Focal 解读](FOCAL_LOSS_WALKTHROUGH.md)、[Pinball 解读](PINBALL_LOSS_WALKTHROUGH.md)、[总损失解读](TOTAL_LOSS_WALKTHROUGH.md)。
3. [E0 兼容性](E0_COMPATIBILITY_REPORT.md)、[合成梯度结果](SYNTHETIC_GRADIENT_TEST_REPORT.md)、[测试与失败记录](tests/README.md)。
4. [逐模块源码学习](RESEARCHER_CODE_STUDY_GUIDE.md)、[审查清单](RESEARCHER_REVIEW_CHECKLIST.md)、[未来集成](RUNNER_INTEGRATION_PROPOSAL.md)。
5. [可编辑 LaTeX](PHASE_B_V2_IMPLEMENTATION_STUDY.tex) / [中文 PDF](PHASE_B_V2_IMPLEMENTATION_STUDY.pdf)；[源身份](source_identity.json)、[manifest](manifest.json)、[最终状态](final_status.json)。真实发布 SHA 在追加 publication_receipt.json。

实现位于 src/yuntapr/experimental/phase_b_v2_ablations/；测试位于 tests/phase_b_v2_ablation_implementation/；测试与静态检查工具位于 scripts/phase_b_v2_ablation_implementation/。只复用冻结 qlog 守卫，正式损失和训练入口没有导入候选模块。任意合成 H/W 仅便于单元测试，未来正式接入仍须固定 [B,1,100,100]、云南 3430 格点及配对样本资格。

最终项目环境结果：CPU 177 passed / 0 failed / 0 skipped，CUDA 3 passed / 0 failed / 0 skipped；11 项源码静态检查通过。重复 attempt 不累加为新独立证据。之前的缺依赖收集错误、CUDA 超时及修复完整保留；旧 87 项验收不重跑。合成 loss forward/backward 已执行，真实模型 forward、optimizer.step、真实数据和 checkpoint 读取均为 0。

科学状态仍 PROPOSED_FOR_RESEARCHER_APPROVAL / RESEARCHER_DECISION_REQUIRED；V2_PHASE_B_AUTHORIZED=false，RESEARCHER_SCIENTIFIC_APPROVAL_REQUIRED=true，HISTORICAL_RECOVERY_RATIFICATION=NOT_GRANTED，2025_RAW_ACCESS=2025_PIXELS_READ=0。合成工程 PASS 不证明校准、q32 覆盖或上尾物理问题已改善。
