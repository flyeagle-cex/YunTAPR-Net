# Researcher formal Phase-A launch authorization

本记录为本次研究者明确授权的结构化转录与执行解释，不冒充平台消息签名。来源：当前对话任务 AUTHORIZE AND LAUNCH YunTAPR-Net v2 paired Phase-A 及随后 Goal。

研究者正式批准 FORMAL_TRAINING_AUTHORIZED=true、V2_PHASE_A_AUTHORIZED=true；只运行 B0_MATCHED_V2 Phase-A 与 B1_V2 Phase-A，顺序独占 GPU。V2_PHASE_B_AUTHORIZED=false，2025 raw/pixels 必须为零。科学冻结、implementation、final preflight commit 和各项 SHA 详见同目录 authorization.json、PAIR_IDENTITY.json 及两个 RUN_MANIFEST。

使用 seed=2026 fresh same-name same-shape paired initialization；禁止加载历史模型、optimizer、scheduler 或 RNG。Train 10,455、Validation 10,501，所有科学参数原样继承冻结 protocol。BEST 仅按 global_val_core_loss，早停 patience=8/min_delta=1e-4。upper-tail diagnostics 只读且不参与训练控制。数值合同违反立即停止，无修复、无跳 batch。

正式根目录沿用已通过预检的 runner 固定 v2 根目录，在其下使用新的唯一 run_id。研究者给出的 formal_training_v2 路径为建议，未改动绑定 implementation。两个模型各自从冻结 fresh paired state 开始；完整 train+validation+diagnostics 与 audit 完成后才提交有效 checkpoint。临时未提交状态不是可恢复 LAST。

授权证据必须先发布 GitHub main；独立启动包装器验证授权所在 commit、远端 main、授权文件 SHA 和执行代码身份后才能调用原版 train。实际代码仍在固定 implementation checkout，publication 在独立 main checkout。日志发布失败按已冻结队列政策处理，不改变训练。状态计数均来自 FORMAL scope，不混入 smoke/test。

意外中断时只允许从核验后的完整 LAST 恢复；本启动文件只授权 fresh train，不自动重试或自动挑选恢复 checkpoint。恢复操作必须另建绑定具体 LAST 和原授权 SHA 的记录，保存丢弃更新证据。禁止 Phase-B、FinalFit、2025、重设计与自动调参。

两模型结束后形成完整 BEST/LAST、history、diagnostics、counters、样本与 checkpoint 身份证据。Brier/AUROC/AP/conditional pinball 在固定 2024 validation 上对各自 BEST 只读评价，沿用历史 Scientific Review 指标定义；不回传训练、不重新选择 epoch，不读取 2025。该决策包尚未生成，不能把训练完成等同于 Goal 完成。

本文件发布时 V2_PHASE_A_STARTED=false。启动后另存启动收据，保持本批准记录不可变。RESEARCHER_PHASE_A_REVIEW_REQUIRED=true 在两模型审计完成后输出，随后停止。
