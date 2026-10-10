# 独立研究者待决事项

所有项目均 RESEARCHER_DECISION_REQUIRED；没有代填批准结论。D01/D02 是初步科学讨论，不是签署。下面的统计选项来自既有 preregistration/v1 的 METRICS_AND_GUARDRAILS、STATISTICAL_ANALYSIS_PLAN 和 RESEARCHER_APPROVAL_CHECKLIST；本轮未据合成表现选择阈值。

|事项|候选选择与利弊|依赖 / 未建立字段|
|---|---|---|
|1 E0/E1/E2 科学范围|固定 gamma / lambda 单因素、B0/B1 分别报告；仅2024开发探索|Phase-A接受范围、H-O/H-Q正式协议未签署|
|2 Brier 最小改善|绝对 Brier 差便于统一解释；相对改善依赖 E0 基准|数值 NOT_YET_ESTABLISHED；由应用价值和未来独立证据支持，不以当前点估计倒推|
|3 q32 覆盖误差|abs(coverage-0.984375) 的百分点下降；或预定误差容忍区间|数值 NOT_YET_ESTABLISHED；仅覆盖改善不足以排除过宽分布|
|4 副作用界限|Conditional Pinball用原log1p损失单位或相对增幅；AUROC/AP绝对下降|三个独立容忍界限 NOT_YET_ESTABLISHED；同时查看强雨分层、全部tau、span/上尾|
|5 多重比较|Holm：需有效p值和预定检验家族；配对max-stat：保留相关但需成立的重抽样假设；仅探索效应与区间：不作确认性显著结论|方法/家族/效应界限未选；35日期块不能解决跨周相关和季节非平稳；功效 NOT_YET_ESTABLISHED|
|6 历史 B1 恢复|独立处置治理偏差，分别记录技术证据与研究者判断|不得把 BEST9 早于恢复阶段或合成通过视为追认|
|7 正式 Runner 集成|审查本候选后另做正式版本，接入审计授权服务和执行入口|正式 loss/runner 集成许可未授予|
|8 真实数据 preflight|仅经独立许可核对2023/2024身份、资格、顺序、scaler、mask|本轮没读真实数据；2025保持封存|
|9 资源预算|预定GPU、磁盘、运行窗口、异常停止与保存策略|真实I/O/耗时/存储尚未测；18运行846936更新是计划非执行|
|10 首批seed2026六组|固定D1/Q1/N0/B9/S0/V0，不据中途表现改规则；以后独立许可补齐其他seed|282312计划更新；六组正式执行许可未授予；一个seed不构成完整多种子证据|

真实 LAST 恢复还必须绑定具体文件 SHA、原始授权祖先、完成 epoch/验证边界并由研究者独立批准。合成 checkpoint 恢复仅验证状态接口，绝不授予正式恢复权。
