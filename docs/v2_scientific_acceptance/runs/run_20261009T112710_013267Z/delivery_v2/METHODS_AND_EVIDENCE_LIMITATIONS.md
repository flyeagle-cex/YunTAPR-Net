# 方法和证据限制

分析对象是冻结 common intersection 的 10,501 个 2024 验证场景、36,018,430 个有效云南 scene-pixel 暴露和 4,496,600 个真实雨像元暴露。场景不是独立样本；像元也不是独立重复。所有点估计逐字段复核已发表的全量 BEST 结果，零容差一致；新逐日期统计只用于分层、校准和不确定性。两个 BEST 均为 Epoch 9，本次不重新选择。

UTC target window_start 日期从 2024-03-01 至 2024-10-31 分成 35 个固定、互不重叠的连续 7 日区块。每次有放回抽取 35 块，两模型共享相同区块次数，保留块内所有时次、空间格点和原有效/真实雨条件；seed=2026，2,000 次，2.5/97.5 百分位区间。Core、Brier、pinball 用全局分子/分母重新累计；AUROC/AP 对抽中的原始 BF16 概率精确并列分数组重新排序累计，不平均日期 AUC，不独立抽像元。相对差异=(B1−B0)/|B0|×100%。

区块方法假设跨周依赖足够弱；天气系统可跨越区块边界，季节分布并非平稳，单一年份和 35 块限制有效信息量。7 日不是结果优化所得，也不宣称是最优块长。方法背景参见 [Künsch (1989)](https://doi.org/10.1214/aos/1176347265) 和 [Politis–Romano (1994)](https://www.tandfonline.com/doi/abs/10.1080/01621459.1994.10476870)；本实现是预声明的固定非重叠周块方案，不等同于随机长度 stationary bootstrap。

全部区间属于开发验证集上的探索性分析，是点对点区间，未作多重比较校正，不给确认性 p 值。区间不校正利用同一验证集选择 BEST 的乐观偏差，也不估计训练随机种子变异，更不代表 2025 或真实未来泛化误差。实际有效重采样次数在 paired_uncertainty.json 中逐项记录；单一类别/空条件集合的指标保持不可计算。

Scientific Freeze v2、model/head、loss、epsilon、LR、normalization、样本集合、划分及正式评价规则没有修改。2023 Train=10,455、2024 Validation=10,501；本次只读 2024。源代码执行 checkout 固定为 a1af0325b481202941c57e8fc94f3b20e441630a，完成证据基线为 166b1f86291bbcde167dbec30d3ae43ac23bba4c；科学批准提交为 d049f7ab7b8a382f47a5fe54384ea9416a22cde9。协议、head、normalization SHA 分别为 a0141f21cfa997d5adb72dff5afb32b17dc7edcf5f3397fc9c4bfe2ea42048be、3a865a6e4ab180f61d7ab6e2f684ab6b814bfe6b2e59a34d127ddf1d772fc97e、656fe7a929cbd8617b08427e8d1fa7029b26512253efb44faa576796137d4a31。

新增分析与旧证据、代码和 source SHA 在总清单分开登记；原历史产物没有覆盖。