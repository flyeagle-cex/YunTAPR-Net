# 配对点指标评价 V3 终态与技术修正待审包

研究者已指定 GPT 网页负责总控、Harness 负责独立审核、Codex 负责技术实现与受权执行。本文由 Codex 整理执行事实和待核对问题，Harness 审核状态为 PENDING。

## 执行绑定与终态

- 执行代码为 `7f550c27a03f83f3f717b888e0e6df1e288fa2db`，准确提案为 `0a615efc8cdccccc68b72f57b2f17357b3cdc95a861cb1a9b50049c751e83a14`，研究者批准号为 YT-POINT-V3-20261114-001。
- 任务为 E0 → COSINE9，两臂 B7、seed2029、固定 E9 LAST，2024 Development 963 场景。预定输出为 A/B/C 物理雨强代理的六阈值分类与连续误差指标。
- 目标在北京时间 2026-11-14 07:51:36 返回1，控制器报 `Output links outside the claimed namespace` 并终止 worker。E0 留下457个 READ_COMPLETE、1,285,614,934字节的天气读取及1个 PENDING job，COSINE9 未启动。
- 控制臂 worker 终态记账和前向次数未封口。完整点指标文件及配对 completion 均未生成。原准确批准已消费，额外重试/重放/优化器更新均0。
- Codex 曾依据保留的目录与读取账本误报运行状态，现以目标退出收据优先，状态回报更正已发往网页总控。

## 待 Harness 核对的问题

1. 核对终态来源身份、停止边界和缺失的 worker 记账。父过程及两次 preflight 实际封口元数据213,555,786字节/165次打开。技术记录暂按整份控制臂载荷26,747,373,950字节/7,953次打开，加完整512MiB/2,048次元数据额度形成保守上界。此次上界27,497,800,648字节/10,166次打开，含此前两次停止累计上界28,059,126,424字节/11,008次打开/246秒。完整实际读取量待独立对账。
2. 核对本提交的 OutputLimit 差异及其存储上限、链接和 reparse point 处理。旧实现对并发删除的临时文件调用 Path.resolve，合成复现出现扩展 DOS 路径或 NTFS $Deleted 路径，产生相同包含关系误判及 FileNotFound 竞态。原失败的具体触发条目未被记录，历史归因按推断登记。
3. 核对修正的工程自测证据。63项CPU回归通过，修正后的5秒并发创建/删除测试完成13,504次快照，错误数0。链接/reparse拒绝、消失条目跳过、4GiB输出和preflight/console计数由针对性测试覆盖。上述测试的科学源读取、模型加载和评价前向均0。

## 资料

- `TERMINAL_VERIFICATION.json` 保存实际终态、身份、读取账本摘要、未封口项和保守计数范围。
- `OUTPUT_BOUNDARY_FIX.json` 保存旧实现复现、修正后的并发测试和63项工程自测结果。
- `CONTROLLER_START_ACK.txt` 保存网页总控对研究者角色分工与此前启动回报的接收原文。实际终态以本包停止收据及后续总控更正回执为准。
- 代码差异位于本提交的 `tools/research_readiness/start_paired_point_evaluation.py` 和 `tests/research_readiness/test_paired_point_evaluation.py`。
- 私有执行位置与完整保存日志索引登记在对应 Obsidian 进度快照中，历史原件均保留。

审核结论请由 Harness 依据实际读取的证据独立形成并记录证据范围。Codex 仅更新自己的交接文件。共同科研决策和新实验批准按研究者既定流程处理。当前执行工程 FAIL，科学 NOT_VERIFIED，研究者知识掌握 NOT_ASSESSED。
