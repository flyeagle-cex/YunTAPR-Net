---
type: research-progress-snapshot
project: YunTAPR-Net
date: 2026-11-13
engineering: PASS
scientific: NOT_VERIFIED
researcher_knowledge: NOT_ASSESSED
---
# 2026-11-13 指标补算与下一步

## 本轮研究者要求

开展多agent讨论并补算POD、FAR等常用指标。后续进度以Obsidian项目目录的Markdown快照维护。正式项目计划最近版本为LIVE-20261111.30，本轮交付为本笔记和可追溯JSON。

## 多agent与网页总控讨论

- 路线agent建议补齐E0与COSINE9的固定E9分类及物理雨量评价，之后再决定后续模型改动。
- 工程agent发现两份保存的可靠性分箱足以精确恢复固定0.5操作点的有雨混淆矩阵，并实现仅依赖标准库和严格输入SHA的补算脚本。
- 笔记agent定位当前实际使用的Obsidian项目主页、11月12日快照与11月13日模型指标表。
- 网页总控在研究者明确批准发送具体摘要后，支持先完成已有分箱的发生分类补算，再形成强雨逐像元配对评价方案。该意见依据回报摘要。
- 独立agent完成源码/合成检查和新输出的Fraction算术复核。Harness本轮新审核处于待取得状态。

## 固定口径与新结果

本节使用原生降水发生概率 p_occ≥0.5 判定预测有雨，真实标签沿用 float32(R)>float32(0.1) mm/h。0.5 是本轮固定的补充报告阈值，记录时间晚于原训练。统计覆盖相同 963 个2024 Development场景、3,303,090个有效像元时次，其中407,820个真实有雨。

| 指标 | E0 对照 | COSINE9 | 候选减对照 |
|---|---:|---:|---:|
| POD | 42.8274729047% | 42.1634544652% | -0.664018 个百分点 |
| FAR | 34.4476471427% | 32.1266593248% | -2.320988 个百分点 |
| CSI | 34.9595578890% | 35.1487091433% | +0.189151 个百分点 |
| Precision | 65.5523528573% | 67.8733406752% | +2.320988 个百分点 |
| F1 | 51.8074576352% | 52.0148647606% | +0.207407 个百分点 |
| ETS | 0.3037507336 | 0.3071903046 | +0.0034395710 |
| HSS | 0.4659644299 | 0.4700008921 | +0.0040364622 |
| frequency_bias | 0.6533323525 | 0.6212078858 | -0.0321244667 |

| 模型 | TP | FP | FN | TN |
|---|---:|---:|---:|---:|
| E0 | 174,659 | 91,783 | 233,161 | 2,803,487 |
| COSINE9 | 171,951 | 81,390 | 235,869 | 2,813,880 |

固定 p_occ≥0.5 时，COSINE9 的 TP 减少 2,708，FP 减少 10,393，FN 增加 2,708。POD 下降约 0.6640 个百分点，FAR 下降约 2.3210 个百分点，CSI 提高约 0.1892 个百分点。该操作点的虚警减少，同时漏报增加。概率排序、条件雨强评分和单一操作点分类各自描述相应性能。

HSS、ETS、频率 Bias 在本节统一使用小数，频率 Bias 的参照值为1。主表 COSINE9 行的四项分类数值来自本节。历史行显示精度沿用原资料，历史分类阈值及点估计口径需要按各自来源核对。

强雨 R>20 mm/h 的 POD/FAR/CSI 与物理点估计 MAE/RMSE/Bias 处于 PENDING。下一项候选为固定E9的E0↔COSINE9配对前向评价，采用继承的A/B/C读出、固定雨强阈值与相同mask，具体执行代码和完整预算待冻结。

补算源为两份严格SHA绑定的保存E9可靠性分箱及既有RESULTS，读取3,778,488B，单次0.2304482秒。十个分箱中索引5–9对应p_occ≥0.5，可精确重建本节四格计数。

工程与算术复核PASS。科学NOT_VERIFIED，研究者掌握NOT_ASSESSED。Harness本轮审核待取得。


## 已有结果与科学决策

COSINE9原七项开发筛查7/7通过，强雨log Pinball改善约10.00%，Brier改善约4.55%。弱雨(0.1,1] mm/h的log Pinball退化约7.59%，研究者对该代价的接受尚待记录。新补充分类结果属于固定0.5操作点的描述性分析，原七项冻结判据按原协议登记。

下一步首选准备一次固定E9、同2024 Dev人口的E0↔COSINE9强雨分类与物理雨量误差评价。以A/B/C读出逐项给出TP/FP/FN/TN、POD/FAR/CSI/ETS/HSS及MAE/RMSE/Bias/CC，保留原FP32边界规则，输出明确阈值。强雨指标需要全部有效人口以统计FP。现有保存汇总对这组物理雨强联合统计的信息不足，执行实现、完整读取预算、时限和输出目录仍待冻结。

结果将用于判断调度收益是否延伸到强雨点估计，以及弱雨代价的取舍。跨seed稳定性、独立观测和DOTE/DTFM增量证据仍各有待办。

## 证据与版本

- 补算代码提交 `9ea1a4cdffdc3482b0648e32d6b0ea82afe86113`，脚本SHA256 `d45225081d08f150ce0c263509cfc25b6b7ac46b06745763c3e3bd5f7292e03c`。
- [[资料快照/20261113_metrics_supplement/OCCURRENCE_METRICS|OCCURRENCE_METRICS.json]]，SHA256 `c46fb4193066a7f191a9ddc06b5628884d988ed7fca3c3e37356f7f0162d82dc`。
- [[资料快照/20261113_metrics_supplement/EXECUTION_BINDING|EXECUTION_BINDING.json]]，SHA256 `b349ac89d96506c88e222b0ae59c84a986e6de0db60c1ebad6057d07c4161e79`。
- [[资料快照/20261113_metrics_supplement/EXECUTION_RECEIPT|EXECUTION_RECEIPT.json]]，SHA256 `bdb2fb8908e86de62791d216c7e8bd6309959b49067b6cbb92d3ad5d64daaaab`。
- [[资料快照/20261113_metrics_supplement/AGENT_ARITHMETIC_REVIEW|AGENT_ARITHMETIC_REVIEW.json]]，SHA256 `54eb3e52232d7c711a080d51e55feb463734ab3368fb4cfee9acdf0f28c0d8dd`。
- [[资料快照/20261113_metrics_supplement/DISCUSSION|DISCUSSION.json]]，SHA256 `441574e984baab471b4bba35cbcb7af050111ca9c714c483b50c86e116c4edf5`。

- [网页总控讨论](https://chatgpt.com/g/g-p-6a9440772f60819190c353a4a133106e/c/6ae89873-7ee8-83e8-858d-ad3bc2cf5f88)
- [MET官方分类指标](https://dtcenter.org/book/export/html/2906)
- [HESS卫星降水原始研究](https://hess.copernicus.org/articles/27/169/2023/index.html)

## 后续评价设计

[[资料快照/20261113_metrics_supplement/NEXT_EVALUATION_DESIGN|配对强雨与物理误差评价设计]] 已登记为PROPOSED，执行器和完整预算待冻结。已有载荷参考53,494,753,532字节，元数据及重复读取尚需计入上限。

## 续作入口

[[各阶段模型训练与评价指标汇总]] · [[极端降水预测]]
