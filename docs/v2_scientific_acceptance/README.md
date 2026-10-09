# v2 paired Phase-A 科学验收材料

本目录仅提供科学证据，研究者尚未科学验收；Phase-B 未授权，2025 outcome 保持封存。

当前完整交付：

- [主证据包](runs/run_20261009T112710_013267Z/delivery_v2/PHASE_A_SCIENTIFIC_ACCEPTANCE_PACKET.md)
- [可编辑 LaTeX](runs/run_20261009T112710_013267Z/delivery_v2/PHASE_A_SCIENTIFIC_ACCEPTANCE.tex) / [11 页 PDF](runs/run_20261009T112710_013267Z/delivery_v2/PHASE_A_SCIENTIFIC_ACCEPTANCE.pdf)
- [完整分层结果](runs/run_20261009T112710_013267Z/delivery_v2/PAIRED_STRATIFIED_ANALYSIS.csv) / [配对绝对、相对差异及探索区间](runs/run_20261009T112710_013267Z/delivery_v2/PAIRED_STRATIFIED_COMPARISONS.csv)
- [概率校准报告](runs/run_20261009T112710_013267Z/delivery_v2/PROBABILITY_CALIBRATION_REPORT.md)
- [上尾物理审查](runs/run_20261009T112710_013267Z/delivery_v2/UPPER_TAIL_PHYSICAL_REVIEW.md)
- [恢复治理偏差](runs/run_20261009T112710_013267Z/delivery_v2/RECOVERY_GOVERNANCE_DEVIATION.md)
- [研究者决策表（未填写）](runs/run_20261009T112710_013267Z/delivery_v2/RESEARCHER_SCIENTIFIC_DECISION_FORM.md)
- [最终状态](runs/run_20261009T112710_013267Z/delivery_v2/final_status.json) / [总清单](runs/run_20261009T112710_013267Z/delivery_v2/acceptance_manifest.json)

数据与复现代码：

- `analysis_v1/analysis_preregistration.json`：补充推理前登记的日期块、分层、固定 bins 和诊断单位。
- `analysis_v1/run_read_only_2024.py`、`sufficient_stats.py`：已完成的冻结 BEST 2024 只读推理适配与聚合 observer；未改动原正式 runner。
- `analysis_v1/analyze.py`：精确概率分数组排序评价和 2,000 次 paired week-block bootstrap。
- `analysis_v2/`：独立报告修复、本地科学绘图、LaTeX 和元数据/聚合验证代码。当前任务不需要再次运行模型。
- 各模型 `sufficient_statistics.npz` 仅保存日期/分组计数、损失分子和 BF16 概率直方图，未保存完整预测 tensor 或模型状态。
- `paired_bootstrap_block_multiplicities.npy` 仅为 2,000×35 的抽样次数矩阵，非模型二进制。
- 模型目录内的 `.jsonl.gz` 是 2024 来源访问日志无损压缩，解压后 SHA 逐项复核；原日志本地保留。没有上传 raw pixels、checkpoint 或 optimizer binary。
- 完整逐 epoch 上尾直接引用 [已发表历史](../v2_phase_a_review/upper_tail_full_history_comparison_20261009_v1.json)，未重新计算或修改历史。

故障与修订明确分开：原 run 的 `closeout_failure.json` 和部分 v1 文档保留，起因为报告变量遮蔽；`delivery_v2` 为新尝试，不重跑推理。LaTeX 首次生成和首轮交付测试的失败也保留；`verification_tests.json` / `verification_tests_attempt_001.json` 是首轮失败结果，当前实际通过记录是 `verification_tests_attempt_002.json`。前一次渲染的缺失数学字形已修正并保存编译日志。不可把保留的失败记录当作当前结果。

验证口径：11 个聚合单元测试、3 个 bootstrap 数值检查、14 个交付验证通过，共 28 项；没有运行含 backward/optimizer fixture 的旧训练全套测试，本次不将历史 770 项预检当成新执行。

术语统一使用“样本集合”“有效暴露数”，population 不译为“人口”。独立事件及地形分层缺少既有定义，保持不可估计。

`RESEARCHER_SCIENTIFIC_APPROVAL_REQUIRED=true`；`V2_PHASE_B_AUTHORIZED=false`；新增 backward/optimizer step=0；2025 raw/pixels=0。提交后停止。
