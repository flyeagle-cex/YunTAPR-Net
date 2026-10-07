# Scientific Freeze v2 研究者批准记录

研究者已批准 Quantile Head v2 科学冻结及当前已登记的 Phase-A 候选协议。本次仅记录批准，没有执行训练或诊断。

## FROZEN

- 训练路径解耦、归一化单调分位数参数化 v2；发生阈值 0.1 mm/h；32 个条件分位数；tau_i=(i-0.5)/32；z0=log1p(0.1)。
- epsilon_w=epsilon_span=1e-4；FP64 归一化变换；严格浮点保护；禁止 clamp、sort、nan_to_num、自动修复、自动跳过批次。数学严格性与有限精度可表示性仍区分；不可表示时报告错误。总跨度不设物理上界，不保证未来物理转换绝不溢出。
- B0-Matched-v2 仅最新 B13；B1-v2 为六个因果 B13 槽位。2023 Train 样本集合 10,455；2024 Validation 样本集合 10,501。
- 共享 Phase-A normalization：mean=271.60515414265217 K，std=19.93959597783802 K；SHA256 `656fe7a929cbd8617b08427e8d1fa7029b26512253efb44faa576796137d4a31`。不重新拟合。
- seed=2026；分别重新设种子，执行全新同名同形配对初始化；禁止历史 checkpoint 转移。
- 原候选 Phase-A 协议数值设置原样继承：AdamW、focal alpha=0.5/gamma=2、batch=2、drop_last=false、5,228 steps/epoch、W=5,228、U=261,400、最多 50 epoch、base LR=1e-4、cosine min LR=1e-6、clip norm=5、validation batch=8、patience=8/min_delta=1e-4。完整设置以冻结 JSON 为准；未宣称这些参数对 v2 最优。

## 逐 epoch 只读上尾诊断计划

每个 epoch 必须保存：云南 mask 内/外 max qlog、q32 per-forward max 的 p99/p99.9、FP64 physical overflow risk，以及 10/50/100/500/1000 mm/h 的描述性超越计数。

这些诊断不得影响 loss、BEST selection、early stopping，不得触发自动调参或跳过 batch，不得成为 outcome-guided protocol change。本次仅登记要求，没有新增统计口径、实现诊断或生成任何诊断结果。

## 授权状态与证据

`V2_SCIENTIFIC_FREEZE_APPROVED=true`。所有正式训练授权仍为 false：`FORMAL_TRAINING_AUTHORIZED`、`V2_PHASE_A_AUTHORIZED`、`V2_PHASE_B_AUTHORIZED`、`B0_MATCHED_PHASE_B_RESUME_AUTHORIZED`。`V2_PHASE_A_STARTED=false`、`B1_PHASE_B_STARTED=false`、`2025_RAW_ACCESS=0`。模型参数未更新，新增 optimizer step=0。

正式 v2 runner 和 checkpoint roots 尚未授权；本次不设置目录、不启动训练。历史候选文件及审查结果保留原样，新冻结记录独立登记。

- [研究者批准原文转录](researcher_approval.txt)：UTF-8/LF 转录；SHA 绑定转录文件，不冒充平台消息签名。
- [当前冻结注册表](../../../../config/science_v2/scientific_freeze_v2_registry_v1.json)：绑定原候选 SHA、批准转录 SHA、冻结文件 SHA 和基线提交。
- [完整冻结 Phase-A 协议](../../../../config/science_v2/phase_a_protocol_frozen_v1.json)。
- [冻结 Quantile Head v2 合同](../../../../config/science_v2/quantile_head_v2_frozen_v1.json)。
- [核验结果](verification.json)、[最终状态](final_status.json)、[新增文件 SHA 清单](artifact_manifest.json)。

本轮仅运行标准库元数据一致性核验；未重新运行历史 GPU/regression suite。未打开原始数据、mask NetCDF 或 checkpoint 二进制；外部 mask SHA 仅继承原证据，未重算。原候选文件与全部基线已跟踪文件保持不变。

本记录绑定基线：`93e0f4ed78625638391dd98a1a63078818daf8be`。提交 GitHub main 后停止。
