# 2026-10-31 本地同步审计索引

本阶段只保存既有代码和元数据、对齐状态并形成报告；没有新增模型模块、训练、推理、原始气象读取或2025结果访问。

- `initial_snapshot.json`：重新fetch后的分支/SHA、30个仓库及执行副本、原有1996项改动、忽略目录与大文件边界。
- `uncommitted_dispositions.csv`：旧副本及仓库外文件逐路径处理决定；未提交原件的位置和原因均保留。
- `ignored_inventory.csv`：主开发仓库10041项可见忽略文件的路径/大小/分类；14个不可访问临时目录仅记录边界，没有改权限或取消忽略。
- `archive_manifest.csv`：396份既有源码/记录的原始与脱敏副本SHA256、字节数、用途；对应`research_snapshots/20261031_sync/`。
- `checkpoint_metadata_reconciliation.json`：九份B4/B7/B8固定E9的当前存在性、大小/mtime与同日既有SHA核验衔接；不加载或重算权重。
- `quality_checks.json`：106项轻量测试/断言、静态语法、原件哈希与JSON数字不变核验。临时目录权限首次失败和相同代码重跑通过均披露。
- `validate_archive.py`：只读验证公开副本的SHA、尺寸、语法和泄漏模式；不导入历史执行器。

旧目录和原件一律保留。归档源码附加`.txt`防止被自动发现或执行；Python格式规范化，注释保留在文件头，非字符串AST不变。JSON数字、布尔值和null均保持不变。源码/日志中出现的旧RUNNING、已消费批准或旧FinalFit流程不代表当前状态，也不构成任何新启动批准。

四份未能闭合脱敏的原件仍留本地，未公开内容：

1. `YunTAPR-Net-push-chunks/docs/formal_training_v2/pair_20261007T070503_825794Z/B1_V2/progress.json`
2. 项目总目录的`authorize_yuntapr_paired_training_v1.py`
3. 项目总目录的`create_yuntapr_resume_closure_v1.py`
4. 项目总目录的`validate_yuntapr_inventory_recovery_v2.py`

前三类不应公开的负载包括权重、私有定位/账本和中间清单；临时文件与重复公开副本也不混入有效科研成果。完整路径清单以CSV为准。忽略规则未改，未force-add，未删除/覆盖用户原件。源码归档不等于科学验收。

本轮完整报告：[PDF](../../../output/pdf/YunTAPR-Net_本地与GitHub同步及科研进度清算报告_20261031.pdf) / [可编辑LaTeX](../../../output/pdf/YunTAPR-Net_本地与GitHub同步及科研进度清算报告_20261031.tex)。当前状态元数据修订见`progress_reconciliation.json`；首次源档push/fetch见`push_archive_verification.json`；全部提交文件见`submitted_files.csv`。PR #1保持草稿，GitHub当前返回不可直接合并，本轮不解决main合并冲突或自动合并。
