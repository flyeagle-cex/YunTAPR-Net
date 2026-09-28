# B0 Entry Requirements

本包判断下一步进入条件，不授权或执行 B0。READY 表示可以开展工程实现；不是已有 B0 forward/loss/metrics/checkpoint/inference 通过。

## B0_ENGINEERING_SMOKE_ENTRY

状态：READY；本轮执行：NOT_RUN_THIS_TASK

### required

- 明确工程 smoke 标签与独立 run；仅 B13 单时次
- 使用已审计 2024-07 reader / dummy-loading 证据作为实现基础
- 显式有效性 mask、float32 tensor、源方向记录、obs_end 因果原则
- 将未来 Dataset -> Tensor -> forward -> loss -> metric -> checkpoint -> inference 逐环验证；本轮不执行
- 空间/标签接口若尚未冻结，使用显式非科学 fixture/synthetic targets 验证接口；不做未经批准的真实监督时间配对
- 保持 raw/old-run 只读与审计可追溯

### optional

- 使用已冻结云南评价 mask 做 shape/hash 接口检查
- 使用已保存小样本中间格式；storage recommendation 尚非永久冻结
- 现有七通道/六槽 reader 能力可复用，但不是 B0 模型输入要求

### not_required

- GFS main
- GFS thermo
- GFS vintage
- DEM
- DOTE
- DTFM
- MEE
- 完整 2025-03~10 测试数据
- 独立外部验证下载完成
- 正式 model_input_bbox/context margin 冻结
- 正式 Train/Val 划分及 Train mean/std

## B0_FORMAL_EXPERIMENT_ENTRY

状态：NOT_READY；本轮执行：NOT_RUN_THIS_TASK

### required

- 研究期与 2025 final-test 框架保持，2025-10 缺月处理明确
- 真实 IMERG target grid 与 3430 主评价 mask（已满足）
- native IMERG 窗口、analysis_time、单帧 selection 与 obs_end 因果绑定获批
- 正式 model_input_bbox/context 定义及裁剪/padding/输出映射获批
- 2023–2024 development 内 Train/Val 精确块和隔离规则获批
- Train-only 归一化来源/有效像元/统计协议获批后再计算
- missing/QC/sample inclusion 规则与分阶段单帧/六槽要求明确
- 实际拟用 Himawari 各研究月完成工程验证，不把 NOT_AUDITED 写 READY
- 正式概率实验 protocol（quantiles/loss/metrics/seeds/checkpoint）定版
- 明确 retrospective physical causality 与 operational NRT availability 的报告范围

### optional

- 外部验证可先规划；若要作真实降水独立优越性结论则必须先就绪

### not_required

- GFS main
- GFS thermo
- GFS vintage
- DEM
- DOTE
- DTFM
- MEE
- B8 全部 terrain hyperparameters

## 分离原则

Smoke 的 fixture 接口不得解释为真实科研标签配对；如果要求 smoke 就使用正式真实监督标签，则必须先解决 D02/D03/D04/D06/D08 等对应规则，不能沿用本包 READY 的非科学范围。正式实验的全部 gate 仍 NOT_READY。已冻结 target grid/行政 mask 不等于已冻结模型输入域。

独立外部验证：B0 smoke 不要求；正式 IMERG-reference baseline 不要求预先全部下载；最终关于真实降水的独立真实性结论前必须就绪。GFS/DEM 均不是 B0 mandatory input。

规范追溯：[RUN_himawari](F:/pytorch/Research/stage0_himawari/outputs/202407/resume_20260927T104625_772423Z/reports/final_dry_run_status_202407_v2.json); [RUN_p0](F:/pytorch/Research/outputs/stage0_p0_audit/run_20260927T161311_417313Z/audit_final_status.json); [SCHEMA](F:/pytorch/Research/outputs/stage0_continuous_engineering/run_20260928T041855_828904Z/schemas/sample_index_schema.md); [FREEZE](F:/pytorch/Research/outputs/stage0_spatial_decision_update/run_20260928T102636_513428Z/freeze_registry.json); [CURRENT_REQUEST](C:/Users/chenerxiao/.codex/attachments/941e14c0-8939-4052-a477-98d4aac32de5/已粘贴的文本.txt)
