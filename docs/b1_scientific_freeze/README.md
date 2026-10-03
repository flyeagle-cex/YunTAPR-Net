# B1 approved scientific freeze v1

当前独立冻结 run：`run_20261003T045139_110133Z`。报告：[B1 Scientific Freeze](runs/run_20261003T045139_110133Z/B1_SCIENTIFIC_FREEZE_REPORT_v1.md)。可编辑LaTeX与PDF在同一run目录。

术语 population = 样本集合 / 样本总体。历史B0和旧B1审计不回写；旧候选状态由独立registry supersede。

本轮已冻结M1、无2月补齐、六槽合同、Train=10455/Validation=10501、primary common intersection、独立B0-Matched-Control identities、2023 scene-slot shared scaler；71项相关测试通过。
训练协议仅冻结已批准项，其余具体训练参数与matched-control scaler待研究者决定。B1/Control training unauthorized，2025 outcome sealed。

权威登记：`config/b1/b1_approved_scientific_freeze_registry_v1.json`。初始design/event与完成fit identity分开保存，禁止混用历史B0 scaler。

工程入口：`scripts/freeze_b1_science_v1.py`（prepare / fit），**不是训练入口**。已完成run不能覆盖或重复启动；该v1的基线及源evidence被固定绑定。英文staging每次单文件，original/staged/pinned SHA核验，700MiB cap，清理自己新建的UUID临时副本。

本轮测试：`python -m unittest tests.b1_scientific_freeze.test_scientific_freeze tests.b1_scientific_freeze.test_freeze_artifacts`（还需相关既有B1/data/spatial regressions；完整本轮结果见run日志）。测试使用synthetic/归档metadata与histogram，不打开raw source或model checkpoint。

STOP；不自动开始训练、Final Test或B2-B8。
