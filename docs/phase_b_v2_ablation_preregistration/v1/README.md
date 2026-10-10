# Phase-B v2 核心模型消融预注册候选包 v1

协议状态：PROPOSED_FOR_RESEARCHER_APPROVAL；所有科学与执行决定仍为 RESEARCHER_DECISION_REQUIRED，实验 NOT_EXECUTED。本轮按研究者指定 A 路线将候选收敛为完整审查材料，未完成独立人类批准或对外注册。Git 版本留痕只证明提案身份。

接续核验：本地与远端 main 均为 8fbc06ba341aeee43136c18f20ebd6acd3463efd，已跟踪工作区无改动；只读进程核对未见 Python/LaTeX 进程，新目录此前不存在。旧未跟踪日志及恢复文件不动、不提交。既有 87 项补强检查不重跑；上一候选包 23/20 项记录不计作本轮测试。

1. [科学目的](SCIENTIFIC_OBJECTIVES.md)、[矩阵与固定终点](FROZEN_EXPERIMENT_MATRIX_CANDIDATE.md)、[控制变量](CONTROLLED_VARIABLE_MATRIX.md)。文件名中的 FROZEN 表示拟冻结设计，状态仍是待审批。
2. [损失数学与研究者练习](LOSS_MATHEMATICS_AND_RESEARCHER_EXERCISE.md)：先理解真实代码，再由研究者独立写最小 PyTorch 实现；本轮没有新损失代码。
3. [指标与安全评价](METRICS_AND_GUARDRAILS.md)、[统计计划](STATISTICAL_ANALYSIS_PLAN.md)、[算力与存储](COMPUTE_AND_STORAGE_BUDGET.md)。
4. [审批清单](RESEARCHER_APPROVAL_CHECKLIST.md)、[安全交接](SAFE_IMPLEMENTATION_HANDOFF.md)、[测试设计](TEST_PLAN.md)、[待决字段](RESEARCHER_DECISION_REQUIRED.md)。
5. [机器协议](protocol_proposed.json)、[封闭 schema](protocol_schema.json)、[18 运行预算](run_budget.csv)、[来源 SHA 与代码定位](source_identity.json)、[源码审查](STATIC_CODE_REVIEW.md)。
6. [可编辑 LaTeX](PHASE_B_V2_ABLATION_REVIEW.tex)、[中文 PDF](PHASE_B_V2_ABLATION_REVIEW.pdf)、[测试记录](tests/README.md)、[manifest](manifest.json)、[真实最终状态](final_status.json)。发布身份见追加 publication_receipt.json。

D1/Q1/N0/I3/B9/S0/V0、E0/E1/E2、两个模型、三个 seeds 构成 18 runs。单运行 47,052 更新，全矩阵 846,936 更新。保留完成训练及验证 epoch 的 checkpoint 边界，提案每 epoch 验证；V0 是选择 epoch 9，不是只验证一次。每运行验证 11,817 batches、全矩阵 212,706 batches，均只是工作量计算。

科学资料仅引用已发表的 [Phase-A 科学证据](../../v2_scientific_acceptance/README.md)、[补强](../../phase_a_evidence_hardening/README.md)及[上轮候选](../../phase_b_v2_protocol_candidates/v1_20261010/README.md)。重要公式定位到本项目源码，不引入外部理论结论或新结果。本轮只审查仓库代码、配置及发表的元数据字节，未读取外部掩膜、原始观测或 checkpoint；没有真实模型 forward、backward、optimizer step。

RESEARCHER_SCIENTIFIC_APPROVAL_REQUIRED=true；V2_PHASE_B_AUTHORIZED=false；2025_RAW_ACCESS=0；2025_PIXELS_READ=0；HISTORICAL_RECOVERY_RATIFICATION=NOT_GRANTED。缺少效应界限、容忍范围、多重比较和资源配置时不能宣称预注册已获批准，更不能启动训练。交付完成即停在审批边界。
