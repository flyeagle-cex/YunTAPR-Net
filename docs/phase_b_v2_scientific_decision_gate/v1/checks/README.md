# 本轮静态检查记录

这些是新决策文档/JSON的一致性检查，不是此前模型、优化器或真实数据测试的重跑。最终 attempt_003 为28项通过、0失败，其中20项为对不合法候选JSON的拒绝测试。58个明确列出的公开来源文件SHA及27个旧预检交付成员核验通过。

attempt_001和attempt_002各有1项失败：先是README引用尚未生成的汇总，再是隐私正则将https URL误认作盘符。已补齐真实汇总并修正匹配边界，保留原失败JSON。最终28项为独立检查数，不把三次执行的84项累计冒称84项独立测试。

复查命令：python docs/phase_b_v2_scientific_decision_gate/v1/static_checks/verify.py --check-only。工具仅用标准库阅读公开来源和本包，无项目导入、数据解码、模型或授权验证能力。未使用新真实数据访问；不会赋予训练权限。最终manifest检查记录另存package_verification.json，它和manifest自身、发布收据排除自哈希，避免循环身份。
