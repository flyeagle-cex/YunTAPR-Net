---
type: research-progress-snapshot
project: YunTAPR-Net
date: 2026-11-14
engineering: PASS
engineering_scope: EXACT_APPROVAL_AND_STARTUP_ONLY
scientific: NOT_VERIFIED
researcher_knowledge: NOT_ASSESSED
execution: STARTED_SNAPSHOT_TERMINAL_RECEIPT_TAKES_PRECEDENCE
---
# 配对评价V4准确批准与启动

研究者在列明代码、提案、模型数据、限额、输出位置及Harness待审事实的准确问题中明确选择“批准V4并立即执行”。批准号YT-POINT-V4-20261114-001，固定独立执行器已单次派发，目标于北京时间2026-11-14 08:16:08启动。

两轮preflight、独立host与资源准入通过，E0 worker创建并进入开发集读取。启动收据保存时尚无target_exit。后续运行与终态以对应V4退出和completion/failure收据为准。

| 项目 | 准确绑定 |
|---|---|
| 执行代码 | `525ee38ae9c1a446202055b8cb0422f6947b5712` |
| 提案规范SHA256 | `ba2f07954affbf9a4d24dd26cb82eeab5826851f963914e746e0c7d6e6fa0ffb` |
| 顺序 | E0 → COSINE9，两臂B7/seed2029固定E9 LAST |
| 数据 | 2024 Development，963场景、3,303,090有效像元时次、407,820有雨像元时次 |
| 读出和阈值 | A/B/C全部报告，FP32严格大于0.1、1、5、10、20、50 mm/h |
| 分类指标 | TP/FP/FN/TN、POD、FAR、CSI、Precision、F1、ETS、HSS、频率Bias |
| 连续指标 | FP64 MAE、RMSE、平均Bias、Pearson CC |
| 新包限额 | 54,971,148,540字节、21,538打开、7200秒、输出4GiB |
| 累计保守限额 | 83,030,274,964字节、32,546打开、7446秒 |
| 更新／重放／额外重试 | 0／0／0 |

原六组概率指标、监督mask、真值计数和R>20真值717由固定执行器核对。此次从头完成两臂各一遍全量Development评价，旧V3部分结果继续保留。

历史停止段的28,059,126,424字节/11,008打开/246秒按缺失worker整份额度保守登记，完整实际消耗仍待Harness对账。代码修复63项回归和13,504次并发快照自测证据继承已公开收据。

GPT网页继续负责总控，Harness负责独立审核，Codex负责技术执行与归档，研究者保留科学决策和验收。Harness审核尚未取得，Computer Use界面转交曾因URL识别受阻。研究者准确批准时已知悉该状态。

启动工程PASS，科学NOT_VERIFIED，研究者掌握NOT_ASSESSED。单seed、复用2024 Development、历史运行时指纹缺口及既有弱雨代价随结果保留。

## 资料入口

- [[资料快照/20261114_paired_point_correction_v4/EXECUTION_PROPOSAL.json|V4准确提案]]
- [[资料快照/20261114_paired_point_correction_v4/LAUNCH_RECEIPT.json|实际准确批准和单次启动收据]]
- [[资料快照/20261114_paired_point_correction_v4/PREPARATION_RECEIPT.json|版本与输入绑定]]
- [[资料快照/20261114_paired_point_correction_v4/CONTROLLER_START_ACK.txt|网页总控启动回执]]
- [[进度快照_2026-11-14_配对评价V3停止与Harness待审|V3停止和Harness待审包]]
- [[极端降水预测]] · [[各阶段模型训练与评价指标汇总]]
