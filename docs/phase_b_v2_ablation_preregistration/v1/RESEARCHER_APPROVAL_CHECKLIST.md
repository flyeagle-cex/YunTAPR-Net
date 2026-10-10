# 独立研究者审批清单（全部未批准）

这是待审事项清单，不是人类批准记录或代签表。没有“已批准”勾选、签名、approval token或执行授权。protocol_proposed中approval fields均null；本轮最高PROPOSED_FOR_RESEARCHER_APPROVAL。

|事项|研究者须独立决定并绑定的范围|当前状态|
|---|---|---|
|Phase-A科学证据|接受哪些2024开发结论、哪些只作探索、BEST审查与限制|RESEARCHER_DECISION_REQUIRED|
|B1历史恢复偏差|技术对账与独立LAST批准缺口的处置、补救和论文披露|NOT_GRANTED；不由fresh追认|
|H-O/H-Q|干预问题、可否证性、共同骨干副作用和研究用途|RESEARCHER_DECISION_REQUIRED|
|E0/E1/E2|alpha.5；gamma2/0/2；lambda1/1/2；排除扩展|RESEARCHER_DECISION_REQUIRED|
|D1/Q1/N0|2023训练/2024开发、M1配对四manifest/scaler/mask/SP04身份|RESEARCHER_DECISION_REQUIRED|
|I3与fresh|三seed、同seed跨臂锚点、B0/B1同形状copy、RNG及排列规则|实物初态NOT_YET_MATERIALIZED|
|预算/S0/V0|9epoch47052/run、50epoch LR前缀、固定epoch9；取消性能early-stop|RESEARCHER_DECISION_REQUIRED|
|验证/保存|每epoch验证及诊断、完成train+validation边界、epoch9 observer复用|RESEARCHER_DECISION_REQUIRED|
|主指标/效应|Brier及abs q32 coverage误差、四比较、minimum meaningful effects|数值NOT_YET_ESTABLISHED|
|安全评价|CPB/强雨层/32coverage/发生/尾分布及容忍、NA规则|容忍范围NOT_YET_ESTABLISHED|
|多重比较/功效|M-A/M-B/M-C、p值/同时区间方法、有效块及功效限制|NOT_YET_ESTABLISHED|
|研究者核心代码|独立最小PyTorch实现、代码SHA、数学审查及随后集成许可|尚无实现、审查或许可|
|数据权限|2023/24实际读权限、仅批准集合、2025 firewall、公开限制|未由本轮授予数据执行权|
|GPU与存储|硬件、依赖、私有roots、时长/空间实测及并发、资源上限|NOT_YET_ESTABLISHED|
|异常停止|数值/缺测/身份/OOM/锁/日志缺失、no skip/no fallback|RESEARCHER_DECISION_REQUIRED|
|保存与审计|初态/代码/配置/数据/模型/optimizer/RNG/LR/epoch SHA、事务marker|新scope尚未工程化|
|恢复|每次具体LAST SHA、原授权祖先、完整epoch、剩余预算和额外尝试资源|任何一次都须新的独立批准|
|阶段1执行|明确授权seed2026全部6臂、起止范围、资源、真实数据与推理|NOT_AUTHORIZED|
|阶段2执行|另批seed2027/2028全部12臂，设计不按阶段1成绩改变|NOT_AUTHORIZED|
|公开解释|仅2024开发探索；全seed/偏离/失败披露；不得声称独立物理确认|RESEARCHER_DECISION_REQUIRED|

科学批准与执行授权必须分别是真实的人类事件。未来记录须绑定批准者可核验身份、原文/时间、提案版本及SHA、具体批准内容和未批准项；执行批准另绑定代码版本、运行ID/seed/数据年限/预算/资源。此处描述的是证据要求，不生成其内容。缺失/模糊范围一律拒绝执行，Git作者、commit、自动JSON true或测试PASS均不能替代。

任何部分接受不自动接受其余事项。例如研究者接受H-O不等于接受lambda2、I3或阶段2；接受历史BEST技术身份不等于追认B1恢复；资源许可不等于科学批准；loss理解练习不等于集成许可。批准后如需改指标、seed、LR/预算、验证频率或失效处理，先建立新版本/偏离审查，不能覆盖本v1。
