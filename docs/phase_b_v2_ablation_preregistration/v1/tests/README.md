# 实际检查与保留记录

本轮只测试新提案审查工具、合成metadata与整数预算；无torch/yuntapr import、真实loss、模型forward、backward、optimizer或raw读取。旧87项及上一候选23/20项不重跑或计入。

命令：python -m pytest -q tests/phase_b_v2_preregistration -p no:cacheprovider --junitxml=docs/phase_b_v2_ablation_preregistration/v1/tests/synthetic_attempt_001.xml。首轮实际62 passed / 0 failed，随后静态来源review CLI因遗漏两个已发表helper白名单路径FAIL_CLOSED；完整脱敏控制台及原因保留。修复后新增两个精确允许路径用例，append synthetic_attempt_002及static_review_attempt_002，不替换首轮记录。

review.py仅打开固定提案、schema和source_identity；源字节核验限定仓库代码/已发表metadata，CSV只hash不解析。即使candidate_valid=true，can_launch_formal_training仍false。它不是实际数据preflight、模型runner或审批器。schema是封闭v1常量结构，支持关键字列在源码SUPPORTED；未知关键字拒绝。

构建、编译、逐页复核与交付静态检查见本目录attempt JSON及最终状态。XML hostname、compiler返回中的工作区路径在公开版脱敏；原记录、完整本机编译日志和PNG渲染保留.local。公开日志不含访问凭据、原始资料或模型状态。

环境探测失败单列environment_preparation.json，不算科研测试失败；真正审查失败及修复清楚保留。后续损失/梯度/模型与数据测试均NOT_EXECUTED，须研究者实现、审查和另行范围批准。
