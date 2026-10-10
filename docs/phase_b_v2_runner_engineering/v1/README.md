# Phase-B v2 独立 Runner 工程候选 v1

状态：SYNTHETIC_ENGINEERING_ONLY / RESEARCHER_DECISION_REQUIRED。

本轮基线为 8958745558ee0a1a2928454ccf894287d8cbfbe9。本候选仅内部生成 batch=2 的人工张量；没有真实数据入口、正式训练命令或审批开关。

- 源码：src/yuntapr/experimental/phase_b_v2_runner_candidate/，7 个独立模块。
- 测试：tests/phase_b_v2_runner_candidate/；本轮新增 75 CPU、8 CUDA 唯一检查通过。12 次实际合成 AdamW 更新，正式更新 0。旧 91 CPU、6 CUDA 检查未重跑。
- 首先阅读 FINAL_CODE_REVIEW_HANDOFF.md，再阅读 RUNNER_ARCHITECTURE_AND_STUDY.md。
- 数学和评价：E0_E1_E2_CONSISTENCY_REPORT.md。
- 事务与故障：TRANSACTION_AND_FAULT_REPORT.md、TEST_AND_FIX_RECORD.md、tests/。
- 资源：RESOURCES_AND_LIMITS.md；审批：RESEARCHER_DECISION_REQUIRED.md。
- 中文审查文档：RUNNER_ENGINEERING_REVIEW.tex / .pdf；源文件可人工修改。
- manifest.json 记录交付及来源 SHA；publication_receipt.json 在实际推送后追加，不作为授权。

成功仅支持工程接口判断；概率校准、q32 欠覆盖、上尾物理可信性及历史 B1 恢复治理问题均未由本轮解决。
