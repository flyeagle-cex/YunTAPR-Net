# B1 / B0-Matched Phase-A v1

当前完整协议已冻结，两个正式入口已实现；training authorization均为false。本轮只完成ENGINEERING_ONLY真实历史小样本与fixture验证，没有完整Train/Val epoch或2025读取。

- [完整协议与报告](B1_B0_MATCHED_PHASE_A_TRAINING_PROTOCOL_v1.md)
- [独立完成run](preflight/run_20261003T074333_289400Z/)
- 配置：config/training/b1_b0_matched_phase_a_protocol_v1.yaml
- 权威新registry：config/training/b1_b0_matched_phase_a_freeze_registry_v1.json
- Entry：scripts/train_b1_phase_a_v1.py / train_b0_matched_phase_a_v1.py；实际共享loop：scripts/paired_phase_a_entry.py。
- 启动前环境必须设PYTHONHASHSEED=2026与CUBLAS_WORKSPACE_CONFIG=:4096:8，使用既有CUDA Python。
- 未提供另行model-specific、SHA固定的researcher authorization，入口在源读取和model/optimizer构造前拒绝。两个authorization模板均false，不构成训练授权。
- 未来checkpoint只在F盘b1_phase_a / b0_matched_phase_a根内；Git不得包含model/optimizer binary；epoch boundary verified LAST恢复下一完整epoch。
- 本轮288不同tests最终通过，299次实际调用；全部失败与复验保留。旧Phase-B hash test在原inventory隔离fixture核验，新源码单独登记hash；历史文件1982个byte-identical。

同名LaTeX/PDF保存在本轮独立run目录，可编辑源与完整交付hash链一并保存。停止，不自动开始training/B2/2025 Final Test。
