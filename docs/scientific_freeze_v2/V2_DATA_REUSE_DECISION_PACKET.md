# V2_DATA_REUSE_DECISION_PACKET（v2 数据复用决策包）

本文件是 candidate（候选方案），不是已批准 v2 数据合同。manifest（样本身份清单）与 normalization（标准化：将 Kelvin 按训练集均值、标准差变换）仅做只读核验。

## 1. 为什么输出头改变不要求自动重定义样本集合

head（输出头）改变没有改变 B13 输入、时间绑定、六槽因果性、M1（严格完整六槽缺帧拒绝政策）、IMERG target（降水监督目标）或云南 mask（行政区评价掩膜）。旧 common intersection（两模型共同合格的样本集合）仍能表示相同科研比较对象。改变头不构成按结果重新剔除样本的理由；最终复用需研究者批准。

2023 Train（训练集）10,455；2024 Validation（验证集）10,501。B0-Matched 与 B1 的样本、目标、时间及目标源 SHA 逐值一致，已只读核验；没有打开 raw source（原始数据源）。

## 2. 为什么标准化可以作为复用候选

输出头并不改变输入 B13 的物理量与单位。已有共享 scaler（标准化参数）仅基于 2023 B1 Train 的 scene-slot exposure（样本与时槽的重复使用暴露量）拟合：10,455×6=62,730 个暴露，ddof（标准差自由度修正）0。

mean=271.60515414265217 K；std=19.93959597783802 K。SHA256（字节内容指纹）`656fe7a929cbd8617b08427e8d1fa7029b26512253efb44faa576796137d4a31`。它不是 Phase-B 的 2023+2024 scaler；后者不得混作本轮 Phase-A 候选。没有重新拟合，也不允许用 2024/2025 拟合 Phase-A 标准化。

## 3. 对 B0-v2 / B1-v2 fairness（公平性）的影响

使用同一 scaler 能避免给单帧和六帧模型不同缩放这一额外差异。旧政策采用 B1 六槽共同训练暴露来拟合，并同时用于匹配单帧控制；复用保持旧公平性政策，无法证明其对 v2 最优。正式 paired initialization（全新配对初始化）政策、seed（随机种子）和训练协议仍待批准。

## 4. outcome-guided choice（结果导向选择）审查

本次候选按研究者指定旧身份形成，不按 v2 验证损失改变样本、mean/std、事件阈值或 2025 指标。v1 已知失败机制是研究者批准方法升级的依据；这不构成声称方法选择完全独立于历史实验。2025 outcome（封存的评价结果）没有读取或参与选择。

RESEARCHER_APPROVAL_REQUIRED=true
V2_DATA_REUSE_APPROVED=false
NORMALIZATION_REFIT=false
2025_RAW_ACCESS=0

来源、SHA 与配对逐值核验证据：`runs/run_20261006T145404_426214Z/candidate_data_reuse_audit.json`。
