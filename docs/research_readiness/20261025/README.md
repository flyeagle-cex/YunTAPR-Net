# B2完成记录与阶段验收

最新纠正运行（2026-10-27）：b251fd9/36fc5dfb已取得明确纠正启动批准，B5真实训练进行中，B6串行等待；07:55:16快照179确认更新，无额外优化器重放。当前IN_PROGRESS，不能宣称E9完成。见[启动与预算收据](evidence/b5_b6_corrected_start_launch.json)。下方首启失败保持历史记录。

最新执行停止（2026-10-27）：B5/B6获批首次启动在气象读取前被读取臂白名单拦截；0更新、62,828字节静态读取，B6未启动。最小修复及修正启动额度已备好，未重启；见[真实状态与修正方案](B5_B6_READINESS_REPORT.md)。下方旧“待原批准/已就绪”内容保留历史时点。

最新推进（2026-10-27）：B0–B4基线按限定结论带局限完成交接；真实候选DEM、B5/B6模型和真实缓存零更新检查已完成。B5/B6正式训练未启动，需新协议/预算集中明确批准，2025冻结。 见[真实地形与启动预算](B5_B6_READINESS_REPORT.md)。

最新完成（2026-10-27）：B3/B4 seed2029、2030、2031的三组固定E9配对训练与2024 Dev评价全部完成；四个新增模型均为COMPLETE_TRAIN_AND_DEV_EVALUATION。943da95恢复包在北京时间00:27封口，390次必要重放已计费，无额外重试。总体Brier/AUROC/AP/条件Pinball三seed均改善；q32方向不一致，强雨仍有退化。总体科学验收继续IN_PROGRESS，2025继续冻结。 见[三seed完成与配对收据](evidence/b3_b4_three_seed_completion.json)与[B3/B4三seed结果](B3_B4_MULTI_SEED_PLAN.md)。

B2 seed2029/E0/f006九轮及Dev评估已核实完成；B2/B3固定E9配对已补齐。B0–B4总体科研验收仍IN_PROGRESS。

历史2026-10-26（此停止状态已由上方获批恢复完成结果取代）：B3/B4 seed2030/2031 四模型串行包已获研究者明确批准，在52a8e90固定副本启动，GPU/RAM及新目录空间入场通过。预算为17,280更新、1,910,286,564,048源字节、串行24小时、零重放；**B3 seed2030九轮完成；B4在870更新处中止；seed2031未启动，整包已停**。提案、准备检查、启动及停止收据见多seed方案。本机只读进度页交给研究者查看，不持续聊天轮询。本轮不重复B2、seed2029或历史全面检查。

- [B2训练与配对评价报告](B2_TRAINING_AND_EVALUATION_REPORT.md)
- [B3/B4多seed计划与上尾诊断](B3_B4_MULTI_SEED_PLAN.md)
- [B0–B4阶段验收](B0_B4_STAGE_ACCEPTANCE.md)
- [B5/B6就绪审计](B5_B6_READINESS_REPORT.md)
- [完整矩阵](B0_B4_EXPERIMENT_MATRIX.csv)
- [运行与审批入口](RUNBOOK.md)

最新完成证据见[evidence/b2_completion_and_paired_evidence.json](evidence/b2_completion_and_paired_evidence.json)：4,320更新、18次数据遍历、477,571,641,012逻辑源字节，约3小时27分26秒，无重放。DELIVERY_MANIFEST.json及DELIVERY_VERIFICATION.json保留先前准备快照，不能当作本次训练完成收据。2025继续冻结。
