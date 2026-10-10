# Phase-B v2 首次真实数据只读预检 v1

本轮独立授权仅覆盖冻结 2023 Train / 2024 Development、shared scaler、云南 mask 与 SP04。真实预检状态：**NOT_VERIFIED**；科学审批与训练许可均未升级。基线 e0920d9375e1f351bc30933cd83b4e7ea41a68ae。

- FROZEN_DATA_IDENTITY_AUDIT.md：冻结 ID、配对资格与准确文件引用。
- TEMPORAL_CAUSALITY_AUDIT.md：六时相、观测完成时间与 Final 标签角色。
- SCALER_MASK_SP04_AUDIT.md：真实字节 SHA、归一化和地理轴。
- DECODE_AND_RESOURCE_REPORT.md：预先固定取样、限定解码、CPU 资源。
- DATA_ACCESS_LEDGER.json：受控读取账本及计数范围。
- BLOCKERS_AND_REPAIRS.md：阻塞、初次工具启动失败与修复。
- REAL_DATA_READINESS_GATE.md / final_status.json：真实完成范围及停止边界。
- audit_results.json / DECODE_SELECTION.json / manifest.json：机器证据及 SHA。

代码位于 src/yuntapr/experimental/phase_b_v2_real_data_preflight/；入口 scripts/phase_b_v2_real_data_preflight/run_preflight.py。只读检测不会实例化模型，未接入正式 Runner，未改冻结源文件。原始影像、降水数组、地理 mask 数组、私有路径和机器日志不公开。

本轮按明确指定的 Markdown/JSON 交付；不重复旧 PDF。公开证据不是科学接受或执行授权。

最终只读工具测试44项通过；保护顺序修正及前期路径属性计数缺口见READONLY_GUARD_HARDENING.md与CODE_CHANGE_PROVENANCE.json。真实预检没有重复运行。
