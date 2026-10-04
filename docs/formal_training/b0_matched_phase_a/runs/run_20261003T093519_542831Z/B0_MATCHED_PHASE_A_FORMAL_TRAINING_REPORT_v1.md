# B0-Matched-Control Phase-A 正式训练报告

本轮仅执行 Phase-A Development：2023 年 3--10 月为 Train，2024 年 3--10 月为 Validation。2025 raw access、pixels read、model inference scenes 均为 0，Final Test 未执行。原 Phase-A launch scope 不含 Phase-B。研究者后续追加授权已独立登记：双方完整性及只读重推理对账通过后，按各自 BEST epoch 预算继续配对 fresh FinalFit。B2 训练与 2025 Final Test 始终未授权。历史 B0、冻结科学合同和基线全部 2061 个文件保持 byte-identical。

输入分别为 B0-Matched 的 latest B13 单帧与 B1 的六个因果 B13 历史槽位；B1 的 offsets 为 analysis time 减去 [60,50,40,30,20,10] 分钟，按最旧到最新排列。M1 严格六槽资格规则、共同 Train 10455 / Validation 10501 样本集合、SP04、云南 mask 和 heads 均不变。双方共享已冻结的 2023 train-only normalization；本轮没有 refit。

新增审计适配器显式委托原正式入口，原入口及全部数值函数源文件不改动。两个模型使用各自独立的正式授权 scope，初始化分别 fresh reseed=2026，72 个同名同形 tensors 初始 bit-identical。两个不同形状输入 kernel 保留 B1 自身原生初始化，其中 residual skip 的原生零初始化保留。不加载历史 B0/BEST/FinalFit 初始化，不转移 optimizer 或 scheduler state。

| 项目 | 实际记录 |
|---|---|
| 正式 run ID | run_20261003T093519_542831Z |
| 完成 epochs | 21 |
| BEST epoch | 13 |
| BEST exact val core | 0.04907351353296674 |
| 完成训练轨迹 optimizer steps | 109788 |
| 所有尝试实际正式 optimizer steps | 109788 |
| 中断后未保留的 optimizer steps | 0 |
| BEST checkpoint path | F:\pytorch\Research\outputs\formal_training\b0_matched_phase_a\run_20261003T093519_542831Z\epoch_013.pt |
| BEST SHA256 | 87f9008f506e2e2d77910736da61f494200e0cbb278756e543d236eb705b7493 |
| LAST SHA256 | 8c1859d99881a2016f15e643c5d634a9883e84a1cdede86e02efe2b4a10349a9 |

physical batch=2，accumulation=1，drop_last=false；每 epoch 5227 个 batch2 加一个 singleton，共 5228 次更新。监督分母为 full batch 6860 / singleton 3430。Validation batch=8，固定顺序完整累计 10501 个样本。AdamW、Conv2d.weight only decay、gradient clip=5、BF16/FP32/FP64 策略、loader=2 均按冻结协议。

BEST 仅依据完整 Validation 的 exact global core loss 严格下降选择，ties 保留最早 epoch。early stopping 与 BEST 独立：patience=8、min_delta=1e-4，max epochs=50。数学 scheduler 固定 W=5228 / U=261400；一基 update 的 LR 在 optimizer.step 前设置。warmup 允许低于 min LR；min LR 下界只用于 cosine。只保存 train+validation 完成的 epoch boundary checkpoint，BEST/LAST binary 全部仅存 F 盘。

| BEST 2024 Validation 指标 | 数值 |
|---|---|
| Brier | 0.09315261792422803 |
| AUROC | 0.8876376262558283 |
| Average Precision | 0.5658271604514816 |
| conditional mean pinball | 0.12616981365248964 |
| N valid | 36018430 |
| N rain | 4496600 |
| strict crossing count | 0 |
| nonfinite count | 0 |
| support violation count | 0 |

训练损失只代表训练集记录，不作为 generalization 指标。上述 Validation 指标全部来自 BEST 所在 epoch 对完整 10501 个冻结样本的真实 inference；未根据辅助指标重新选择 checkpoint。

新增及相关 pre-training unique tests=336，post-training read-only tests=28，均通过、0 skipped。

{'source_copy_count': 880152, 'authorized_raw_open_attempt_events': 1760304, 'every_successful_copy_has_two_raw_opens': 'readonly copy plus source SHA read', 'source_bytes_copied_over_epochs': 2283308555073, 'staging_copy_seconds_sum': 9715.245221101628, 'staged_read_seconds_sum': 10571.22061260102, 'peak_single_temporary_bytes_per_worker': 6387344, 'all_source_size_sha_cleanup_pass': True, 'every_scene_count_per_year_equals_completed_epochs': True, '2025_RAW_ACCESS': 0}

每次复制均核验大小与 SHA 后通过英文 staging 解码，成功后清理。本轮没有永久复制完整月份。copy/read seconds 是跨 worker 累计耗时，不等于运行 wall time。正式 run 的 engineering/test-fixture optimizer counters 均为 0。

完整逐 epoch history、checkpoint registry、raw access/staging 审计和 32 tau diagnostics 均作为配套证据保留。POD/FAR/CSI=THRESHOLD_NOT_FROZEN。科研解释等待研究者审阅；后续执行由独立追加授权和各阶段 gates 控制。
