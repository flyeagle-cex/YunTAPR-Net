# 第 2 步｜IMERG 评价协议冻结

2026 年 11 月 21 日，网页总控 High 确认冻结开发筛查与证据边界。2024 Dev 继续用于候选筛查，2025 实际范围和执行保持封存。当前证据不足以绑定新的可证伪单变量候选，第 3 步正式实验尚未准入，科学状态为 NOT_VERIFIED。[IMERG 参考与事件协议](IMERG_REFERENCE_EVENT_PROTOCOL_V1.md)

## 固定人口与比较

参考为 IMERG V07 Final，SP04 约 0.1° 格点、UTC 半小时靶窗和原云南监督掩膜。比较器为 B7/REAL/COSINE9 seed2029 固定 E9。使用共同场景、真值、掩膜、分区和节点合同的身份摘要。2024 Dev 固定 963 个场景、3,303,090 个有效像元时、407,820 个有雨像元时。强雨为 FP32 真值严格 >20 mm/h，共 717 个。非强雨 3,302,373 个，弱雨 0.1 < R ≤ 1 mm/h 共 246,473 个。[机器基线及身份](../20261119_conditional_intensity_diagnostic/CONDITIONAL_TAIL_BASELINE.json)

## 联合通过条件

| 判据 | 比较器实际值 | 候选条件 |
|---|---:|---|
| 真强雨物理 Pinball/20 | 0.5068646309277546 | 严格下降 |
| q32 真强雨越线数 | 160 | ≥160 |
| q32 非强雨越线数 | 5,769 | ≤5,769 |
| A 固定阈值强雨命中 | 0 | >0 |
| A 固定阈值误报 | 0 | =0 |
| 弱雨 log Pinball | 0.08872231160181858 | 不升高 |
| 发生 Brier | 0.09233015567445307 | 不升高 |
| 发生 AP | 0.6066547555865263 | 不降低 |
| 发生 AUROC | 0.8990243638708331 | 不降低 |

强雨物理 Pinball/20 使用 FP64 物理反变换后的 32 个条件分位，先节点取均值，再在强雨像元时取均值。q32 支持采用 FP64 qlog32 > log1p(20)。A 由 FP64 发生概率乘以 32 个物理分位的均值，再转换为 FP32 以执行严格 A>20。发生评分基于全部有效像元时、沿用真值 R>0.1 mm/h 的定义和并列规则。执行时要求原九项比较通过，且固定点值 A 恢复检出。每项都用机器收据精度比较。[固定定义](../20261119_conditional_intensity_diagnostic/CONDITIONAL_TAIL_V1.md) · [点值联合门](../20261119_conditional_intensity_diagnostic/A20_BISIDE_V1.md)

**报告而不加硬门的结果。** AP20 是必报辅助排序指标，以固定 A 分数及同一强雨真值按同分组计算。分别列全人口及海拔 ≥2,000 m 的强雨幅值、TP/FP/FN、召回和 AP20。高海拔既有人口含 178 个强雨像元时。连续参考及共同模型覆盖尚未证实，过程结论限于实际可评价窗口。当前报告匹配窗口或事前定下的时块，207 个含强雨窗口保持窗口计数。[配对排序结果](../20261119_conditional_intensity_diagnostic/A20_POINT_RANK_RESULTS.json) · [2024 时间覆盖](../20261106_research_convergence/history/T13_RECOVERED_REDACTED.md)

**停止规则。** 身份、有效性或评价边界不符即停。任一联合判据失败即封存候选，历史 A20（原筛查 2/9 且 AP20 下降）与 TAIL20（原筛查 8/9 且固定 A 无命中）的失败结论有效。新的假说须写清唯一改变、作用路径、预期如何同时改善物理幅值和控制误报、结果怎样推翻假说。候选、对照、预注册规则和精确预算获批后方可正式尝试。当前尚无足以绑定的方案。[A20 终态](../20261119_conditional_intensity_diagnostic/A20_RESULTS.json) · [TAIL20 终态](../20261119_conditional_intensity_diagnostic/TAIL20_RECOVERY_RESULTS.json)

## 单独锁定 2025 最终测试

保留 B0 v1.1 的 3–9 月与原 V1.3 / 10 月 30 日主线草案的 3–10 月两种历史范围，状态为 PENDING_RESEARCHER_SCOPE_BINDING。由研究者在最终执行前绑定唯一范围、时间戳语义、比较模型和主终点。共同人口、数据适配与预算分别按真实获准范围核验。真实适配器尚缺，编目和一次性最终评价保留各自授权。2025 保持封存，最终结果无调参用途。[范围沿革](../20261106_research_convergence/EVALUATION_ENTRY_GATES.md) · [旧 B0 v1.1 配置](../../../config/evaluation/b0_2025_final_test_protocol_v1.1.yaml) · [主线最终测试草案](../20261025/evidence/final_test_preregistration_increment_20261030.json)

## 本轮检查

从四份已发布聚合收据重建既有基线，与冻结 JSON 一致，基线 SHA-256 为 6c100deae46db77d683757429a37354d390bd31daf67196589a385a85fafd3b7。7 项合成联合门覆盖通过、零命中、1 次误报、主指标持平、弱雨退化、错掩膜及最终年标记拒绝。3 项现有最终测试草案测试通过，验证固定端点目录、合成元数据拒绝条件和载荷禁用。真实科学载荷、权重、预测分片和 2025 访问均为零，未训练或推理。

网页 GPT-6 High 冻结科学口径，Codex 建议 Sol High 准备新候选的技术方案，Harness 建议 Flash High 在可审查的新执行差异出现后做一次限定审核。
