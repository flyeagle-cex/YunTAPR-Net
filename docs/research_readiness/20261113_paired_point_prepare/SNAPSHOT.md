---
type: research-progress-snapshot
project: YunTAPR-Net
date: 2026-11-13
engineering: PASS_WITH_LIMITATIONS
scientific: NOT_VERIFIED
researcher_knowledge: NOT_ASSESSED
execution: PENDING_EXACT_RESEARCHER_APPROVAL
---
# 强雨与物理雨量评价执行包准备

## 当前进度

研究者要求按上轮下一步推进。本轮完成两臂评价代码、固定副本、CPU合成检查、元数据接线检查和准确预算提案。正式执行处于待一次准确启动批准状态。

## 冻结科学范围

- 两个模型均为B7、seed2029、固定E9 LAST，顺序为历史E0对照到COSINE9候选。
- 2024 Development固定963场景、3,303,090个有效像元时次、407,820个有雨像元时次，沿用原mask与f006回顾口径。
- A、B、C三种继承的有限分位节点雨强代理全部报告。阈值为0.1、1、5、10、20、50 mm/h，分类采用FP32严格大于，保留边界相等计数。
- 每个阈值保存TP、FP、FN、TN、POD、FAR、CSI、Precision、F1、ETS、HSS和频率Bias，连续雨量保存MAE、RMSE、平均Bias和Pearson相关系数。
- 同一次前向同时送入原Evaluation和新ABC累积器。原六组人口、来源、分区、Brier、AP、AUROC、Pinball及q32覆盖须复现。两臂监督mask摘要和各阈值真值数须相同，严格R>20真值数为717。

## 版本与限额

| 项目 | 冻结值 |
|---|---|
| 执行代码 | `4fada6856bcd8bef1ee92c7209cb55f6d1d6a0c6` |
| 提案规范SHA256 | `06340722ae532c0eeef42ac36f98e746d6a19dff376f6c0665ba9b86e1772ef9` |
| 新开发集前向 | 两臂各一次 |
| 天气/掩膜、静态与权重档案预留 | 53,494,753,532 字节，15,906 次打开 |
| 元数据上限 | 1,476,395,008 字节，5,632 次打开 |
| 总源预留上限 | **54,971,148,540 字节** |
| 累计墙钟上限 | **7,200 秒，2小时** |
| 单臂上限 | 3,000 秒 |
| 输出存储上限 | 4 GiB |
| 启动及任务可用磁盘 | 至少8 GiB |
| 主机可用内存/GPU空闲显存 | 至少8 GiB / 5120 MiB |
| 优化器更新、重放、额外重试 | 0 / 0 / 0 |

读取预算按每次打开预留完整档案长度。两轮启动校验、控制器和两worker分别计入元数据。权重各安排一次SHA核验与一次加载。批准文件绑定方法、代码、提案、预算和私有输出目录。独立后台监督仅作一次派发。

## 工程检查与实际读取

正式Python3.11.15、Torch2.11.0+cu128、CUDA build12.8、NumPy2.4.4的身份probe与训练记录匹配。60项CPU合成/回归检查通过，包括17项指标、28项控制器、7项worker、4项新host入口、4项旧host检查。

集成时发现累积器人口参数遗漏、preflight路径解析触发重复天气stat、旧元数据漏计和临时目录ACL问题，已修正并复验。旧host的4项检查在最终测试harness中使用等价工作区UUID临时目录，断言保持。失败事实及原stdout身份随收据保留。

仅元数据接线检查完成原模块导入和PopulationPlan构造，确认963个Dev场景，预留110,751,210字节/15次元数据打开。该检查中模型构造、权重加载和GPU前向均为0。准备脚本另有76,937,874字节/60次元数据账，独立agent的52份元数据SHA核对68,337,999字节有单独收据范围。

缺少准确批准文件的真实CLI入口已拒绝，正式输出和preflight声明均未创建。

## 审核范围与科学状态

独立agent完成changed-code、CPU/mock、52份元数据身份与预算算术复核，结论PASS_WITH_LIMITATIONS。Harness本轮独立审核待取得。真实CUDA前向与原指标复现由正式评价门控核验，当前科学状态NOT_VERIFIED，研究者掌握NOT_ASSESSED。

历史E0完整driver/cuDNN指纹缺口继续登记。现有单seed、复用2024 Dev、弱雨Pinball约7.59%退化等局限随结果报告。研究者对弱雨代价的接受尚待记录。

## 启动决定

项目约定要求新推理/评价的批准绑定明确方案、代码版本、数据、预算、时限和输出位置。本提案已具备这些绑定字段，等待研究者作一次准确启动决定。

## 资料入口

- [[资料快照/20261113_paired_point_prepare/EXECUTION_PROPOSAL|准确执行提案]]
- [[资料快照/20261113_paired_point_prepare/ROOT_CPU_SUITE_FINAL|正式解释器CPU检查收据]]
- [[资料快照/20261113_paired_point_prepare/METADATA_ONLY_PROBE|仅元数据接线检查]]
- [[资料快照/20261113_paired_point_prepare/PREPARED_PACKAGE_AGENT_REVIEW|独立agent限定审核]]
- [[资料快照/20261113_paired_point_prepare/NO_APPROVAL_ENTRY_CHECK|缺批准入口拒绝检查]]
- [[各阶段模型训练与评价指标汇总]] · [[极端降水预测]]
