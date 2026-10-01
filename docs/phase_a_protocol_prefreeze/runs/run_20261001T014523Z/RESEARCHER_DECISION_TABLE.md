# RESEARCHER_DECISION_TABLE

科研参数保持未选择；已有工程建议仅作为 ENGINEERING_EVIDENCE_READY。

| Parameter | Current evidence | Candidate values | Scientific impact | Engineering impact | Recommended candidate | Reason | Status |
|---|---|---|---|---|---|---|---|
| Focal alpha | 正类权重；Train rain=10.420417% | 0.25; 0.50; balanced=0.895795829 | 类别贡献及 L_occ 相对尺度 | 无新增算力 | 未选择，待研究者决定 | prevalence 不证明最优性能 | RESEARCHER_DECISION_REQUIRED |
| Focal gamma | 已核对 (1-p_t)^gamma | 0; 1; 2; 3 数学展示 | easy/hard 相对贡献 | 算子成本小 | 未选择，待研究者决定 | 未训练的数学诊断 | RESEARCHER_DECISION_REQUIRED |
| Optimizer | 参数分组计数与默认签名已测 | AdamW; beta=(.9,.999), eps=1e-8 DEFAULT_REFERENCE | 优化动力学 | 状态/step 额外显存未实测 | 未选择，待研究者决定 | 需共同协议 | RESEARCHER_DECISION_REQUIRED |
| Weight decay / groups | A 全参数；B 排除 bias/GN | decay 0;1e-4;1e-3;1e-2, A/B | 正则化作用不同 | 参数组已完整列出 | 未选择，待研究者决定 | 无性能证据 | RESEARCHER_DECISION_REQUIRED |
| Learning rate | physical=2 的候选表 | 5e-5;1e-4;2e-4;3e-4 | 更新尺度 | 线性 scaling 仅参考 | 未选择，待研究者决定 | 未做 LR 搜索 | RESEARCHER_DECISION_REQUIRED |
| Effective batch | updates=5860;2930;1465 | 2;4;8 (accum=1;2;4) | 梯度噪声/更新频率 | physical 显存相同；accum 未执行 | 未选择，待研究者决定 | 需决定公平预算 | RESEARCHER_DECISION_REQUIRED |
| Scheduler | FinalFit replay 复杂度已分析 | Constant; warmup+cosine; Plateau | LR 演化 | LOW;MEDIUM;HIGH | 未选择，待研究者决定 | Plateau 不可自动复用 2024 控制信号 | RESEARCHER_DECISION_REQUIRED |
| Max epochs / transfer | 31.19 min/epoch 工程估算 | 30;50;80; transfer rule 待定 | 模型选择/最终预算 | optimizer 后时间可变 | 未选择，待研究者决定 | 最终预算依 Phase-A development 决定 | RESEARCHER_DECISION_REQUIRED |
| Early stopping | 明确 validation calls 和比较式 | patience 5;8;10, absolute delta 0;1e-4;1e-3 | 停止/选择偏差 | 减少算力但触发动态 | 未选择，待研究者决定 | 需要记录每次调用和 min_delta | RESEARCHER_DECISION_REQUIRED |
| Gradient clipping | 仅提出 global-norm 定义 | none;1.0;5.0 | 限制更新 | 后续记录 pre/post/action | 未选择，待研究者决定 | 未生成真实样本梯度 | RESEARCHER_DECISION_REQUIRED |
| Seed policy | 时间成本按 B0 算术展开 | 全体1 seed;全体3 seeds;混合 | 重复性/不确定性精度 | 约1x/3x算力 | 未选择，待研究者决定 | 混合重复程度不一致 | RESEARCHER_DECISION_REQUIRED |
| Determinism / TF32 | 当前设置只读登记 | deterministic True/False; TF32 policy | 数值可复现性 | 性能可能变化 | 未选择，待研究者决定 | 种子和环境必须共同登记 | RESEARCHER_DECISION_REQUIRED |
| Checkpoint metric / ties | global numerator / global D 已定义 | A val_core_loss; B occ+qr (等价); tie earliest 候选 | checkpoint 选择 | 可流式聚合 | 未选择，待研究者决定 | 不可简单平均不同大小 batch | RESEARCHER_DECISION_REQUIRED |
| Validation metrics | 精确定义候选集合 | Brier;AUROC;AP;pinball;coverage;crossing | 报告与校准诊断 | AUROC/AP 排序成本 | 未选择，待研究者决定 | probability cutoff 未确定 | RESEARCHER_DECISION_REQUIRED |
| Probability cutoff / calibration | 降水阈值与概率阈值已区分 | 未指定；POD/FAR/CSI 需批准 cutoff | 阈值迁移影响 Final Test | 需要独立 calibration protocol | 未选择，待研究者决定 | 概率阈值尚未确定 | RESEARCHER_DECISION_REQUIRED |
| Exact head architecture pin | 代码为1x1 48→1 / 48→32，0 hidden | 沿用实际代码须研究者登记 | 容量与公平比较 | 不改 head | 未选择，待研究者决定 | HEAD_IMPLEMENTATION_DETAIL_REQUIRES_PROTOCOL_PIN | RESEARCHER_DECISION_REQUIRED |
| B0–B8 fairness | 共同项目与变化复核规则已提出 | 统一 optimizer/LR/loss/heads/metric/seed/budget | 消融归因 | 额外模型可能改变时间 | 未选择，待研究者决定 | 共享协议待批准 | RESEARCHER_DECISION_REQUIRED |
| Physical batch | FP32 batch2 reserved4420MiB; batch4余量失败 | 2 既有工程证据 | 不得自动提升为科研协议 | 满足先前20%余量 | 2，仅工程建议 | 复用已提交测量 | EVIDENCE_READY |
| AMP mode | BF16约3260MiB、12.23samples/s | BF16/FP16/FP32 已测 | float64 quantile 合同保持 | BF16稳定性通过 | BF16，仅工程建议 | 已有 GPU audit | EVIDENCE_READY |
| Validation batch | eval/no_grad已测 | 8 既有工程建议 | 不影响全局聚合定义 | batch16余量失败 | 8，仅工程建议 | 已有 GPU audit | EVIDENCE_READY |
| DataLoader workers | 32scene active吞吐2/4近似，启动开销不同 | 0;2;4 已测 | eligible/QC保持 | worker独立staging | 2，仅工程建议 | 更少worker且吞吐接近最佳 | EVIDENCE_READY |
| Train descriptive evidence | 11720 scenes 全量，40199600 valid pixels | 月度/条件雨量已统计 | 未改 extreme threshold | 245天哈希读取完成 | EVIDENCE_READY | 仅2023统计 | EVIDENCE_READY |
