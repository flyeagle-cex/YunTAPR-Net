# PHASE_A_OPTIMIZER_DRYRUN_REPORT

状态：STOPPED_AUDIT_HARNESS_EXTRA_DTYPE_REQUIREMENT。原16项测试和全部 exact scheduler / FinalFit replay 已通过，六个真实2023样本 reader/QC/normalization/SHA/cleanup 通过。

首个前向符合全部冻结 dtype 要求：parameters/raw quantile=float32，BF16 autocast开启，qlog/qphysical/pinball=float64，finite、crossing=0、监督像元6860。新审计脚本错误地额外要求末端 backbone activation 为BF16；实际为float32，因此在 backward 前中止。

该 activation dtype 不属于已冻结要求。根据 [PyTorch2.11 AMP](https://docs.pytorch.org/docs/2.11/amp.html)，autocast 按算子混合选取dtype；既有Conv-GN-GELU residual代码未改变。后续只修复新 harness 的额外条件，不改变模型/AMP/冻结参数，并在独立新run继续。此尝试的脚本原样保存在 attempt_script_snapshot.py，其SHA与 gpu_started.json 一致。

optimizer.step=0；backward、clipping、VRAM optimizer state、A/B replay、checkpoint/resume、完整137历史+protocol测试为NOT_RUN；没有 checkpoint 或原始数据副本遗留。所有 frozen protocol 和历史baseline保持不变。详细错误见 gpu_failure.json，样本证据见 real_sample_read_audit.json。
