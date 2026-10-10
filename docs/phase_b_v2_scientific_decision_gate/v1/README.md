# Phase-B v2 科学决策包 v1

状态：PROPOSED_FOR_RESEARCHER_APPROVAL / RESEARCHER_DECISION_REQUIRED。可提交研究者审议，尚非批准协议或执行授权。

本轮基线为 090ad2e3a912e214976b4236f90f99f41df7cd2e；开始时本地与 GitHub main 一致，受控文件无改动。历史未跟踪文件原样保留。本轮只阅读公开仓库证据与公开文献，新增文档、非执行配置及其静态检查；没有重跑合成训练、真实预检或模型推理。

## 审议入口

先读 [待签决策](RESEARCHER_DECISIONS_TO_SIGN.md)，再按需查看：

- [完整科学协议候选](SCIENCE_PROTOCOL_CANDIDATE.md)：矩阵、公式、评价和解释范围。
- [业务时效定位](OPERATIONAL_LATENCY_POSITION.md)：推荐论文表述 A；B 的证据缺口。
- [效应界限与统计选择](EFFECT_THRESHOLDS_AND_MULTIPLICITY_OPTIONS.md)：推荐 M-C，数值界限未建立。
- [完整性补齐选项](DATA_INTEGRITY_COMPLETION_OPTIONS.md)：未来批准后的 SHA 策略。
- [正式集成差异](FORMAL_INTEGRATION_DIFF.md)：准确的现有函数与未来改动建议，未应用。
- [非执行配置](decision_candidate.json)、[来源身份](source_registry.json)、[检查记录](checks/STATIC_CHECK_REPORT.json)、[最终状态](final_status.json)。

## 证据等级

[真实预检最终状态](../../phase_b_v2_real_data_preflight/v1/final_status.json)始终为 NOT_VERIFIED。20,956 场景身份、67,006 文件引用存在性、scaler/mask/SP04 和 48 场景限定解码通过，不能替代其余 66,712 文件的 payload SHA。27,880 个场景—时相引用的 date_created 晚于分析时刻。历史首次 2025 负面测试可能涉及未计数的路径属性查询；零内容读取不等于系统级零路径访问，修复后也未重新执行真实预检。

所有本轮推荐仍未批准。既有 D01/D02 讨论和本轮确认“按推荐收敛”只约束候选编写方式，不能当成正式科研签署。保持 Phase-B/正式执行未授权、研究者科学审批必需、历史恢复未追认、正式优化器更新 0、2025 像元读取 0。独立批准前无真实数据或训练入口。交付后停止。
