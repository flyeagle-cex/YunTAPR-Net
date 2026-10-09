# v2 配对 Phase-A 收尾：当前工程证据

本次新增的是独立收尾审计与只读评价入口，运行目录与冻结 implementation checkout 分离。

## 已实际执行

B0-Matched-v2 的全部 17 个完整 epoch 审计 PASS，见 `closure_audits/run_20261009T005719_747987Z/B0_MATCHED_V2/`。

逐轮核验了实际训练/验证日志的样本身份和顺序、5228 次训练更新、6860/3430 真实分母、1313 次固定顺序验证、LR、梯度有限性及 clip 记录、全局分子累计、诊断逐 forward 覆盖、云南内外 exposure 与超阈值计数、p99/p99.9、FP64 风险，以及全部 checkpoint 的文件和内部 model/optimizer/scheduler/RNG/permutation SHA。恢复状态没有应用到模型或优化器；审计没有 forward、backward 或 optimizer update。

BEST 与 early-stop 分别从实际历史重算：BEST=epoch 9；best_es_epoch=9；best_es_value=0.0487596076193766；epoch 17 counter=8，patience=8，min_delta=1e-4。B0 保留轨迹 88,876 次更新；历史未正常退出尝试仍保留 all-attempt 89,175–89,176 与 discarded 299–300 的已知区间，没有补造精确值。

6 项收尾反例测试、7 项只读指标测试均 PASS，分别见对应 JSON。现有已完成的 770 项 preflight 测试证据没有被覆盖，本次没有重新运行该整套 suite。

## 尚未执行

B1 仍由已授权的冻结 runner 训练。B1 完整终止审计、两个 BEST 的全量 2024 reinference、配对比较决策包、可编辑 LaTeX/PDF 和最终 Goal completion audit 尚未完成。当前不得把此 handoff 或 fixture PASS 当作配对实验完成。

实际以最新恢复授权调用新评价入口，即使指定 `--execute`，仍返回 `WAITING_FOR_BOTH_PHASE_A_COMPLETION`；没有创建评价目录、加载模型、读取 raw 或分配 GPU。证据在 `current_resume_early_review_rejected_20261009.json`。

## 正式结束后的调用顺序

1. 等待当前 B1 runner 与其 wrapper 正常退出。最新恢复目录的 `process_exit.json` 必须为 exit_code=0，两个 final_report 必须 COMPLETE，pair_training_completed 必须存在，正式 GPU lock 必须释放。
2. 使用 `closeout_audit_v2.py` 对 B1 完整历史执行同一审计。允许复用 B0 已完成审计，但必须重新核验已登记 artifact/checkpoint 字节，确认 B0 没有变化。
3. 用 `docs/v2_phase_a_authorized/review_paired_best_v2.py` 执行一次完整只读 BEST 2024 评价。必须传入最新完成的恢复授权路径和 SHA，并显式传入 `--execute` 与独立新 `--output`。不使用历史失败 attempt 的 exit record。
4. 评价在导入 PyTorch 或读取 checkpoint/raw 之前复用已测试的生命周期完成门；随后核验历史 checkpoint 与完整轮次 artifact、环境、manifest、源白名单及 BEST provenance。仅应用 model state，在 inference-only 保护内禁止 optimizer 构造与 backward。
5. 按固定 10,501 场景顺序、batch8/tail5 推理，原始分子全局累计。两模型均必须逐项零容差复核 BEST 时保存的核心验证值。额外 Brier/AUROC/AP/conditional pinball 只用于研究者比较，不选新 checkpoint 或 epoch。
6. 整理两个终止审计、完整 histories、upper-tail histories、checkpoint identity 与范围明确的 counters，生成最终可编辑 LaTeX/PDF 决策包；核验并推送 GitHub main 后才能声明 Goal 完成。

最新恢复授权：`pair_20261007T070503_825794Z/resume_20261009T003216_479921Z/authorization.json`；SHA256=`73d8e76649ac1310ff1a541cb7f0e7518c4ad527c8571113726b56312c7115a2`。其执行范围继承研究者原始 Phase-A 正式授权。

中途若失败，保留独立 evidence 并停止，不自动重试评价、不追加训练更新、不进入 Phase-B。任何运行中审计仍遵循已发布的共享写入读取政策，禁止默认 .NET reader 打开 live journal，禁止读取 live atomic-replacement JSON。

始终保持 2025_RAW_ACCESS=0、2025_PIXELS_READ=0、V2_PHASE_B_AUTHORIZED=false。最终需要研究者审查，不能自行接受实验或启用 FinalFit。
