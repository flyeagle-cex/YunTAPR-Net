# B1 Phase-A 正式训练报告

本轮仅执行 Phase-A Development：2023 年 3--10 月为 Train，2024 年 3--10 月为 Validation。2025 raw access、pixels read、model inference scenes 均为 0，Final Test 未执行。原 Phase-A launch scope 不含 Phase-B。研究者后续追加授权已独立登记：双方完整性及只读重推理对账通过后，按各自 BEST epoch 预算继续配对 fresh FinalFit。B2 训练与 2025 Final Test 始终未授权。历史 B0、冻结科学合同和基线全部 2061 个文件保持 byte-identical。

输入分别为 B0-Matched 的 latest B13 单帧与 B1 的六个因果 B13 历史槽位；B1 的 offsets 为 analysis time 减去 [60,50,40,30,20,10] 分钟，按最旧到最新排列。M1 严格六槽资格规则、共同 Train 10455 / Validation 10501 样本集合、SP04、云南 mask 和 heads 均不变。双方共享已冻结的 2023 train-only normalization；本轮没有 refit。

新增审计适配器显式委托原正式入口，原入口及全部数值函数源文件不改动。两个模型使用各自独立的正式授权 scope，初始化分别 fresh reseed=2026，72 个同名同形 tensors 初始 bit-identical。两个不同形状输入 kernel 保留 B1 自身原生初始化，其中 residual skip 的原生零初始化保留。不加载历史 B0/BEST/FinalFit 初始化，不转移 optimizer 或 scheduler state。

| 项目 | 实际记录 |
|---|---|
| 正式 run ID | run_20261003T093522_417735Z |
| 完成 epochs | 16 |
| BEST epoch | 15 |
| BEST exact val core | 0.04787160352568951 |
| 完成训练轨迹 optimizer steps | 83648 |
| 所有尝试实际正式 optimizer steps | 88876 |
| 中断后未保留的 optimizer steps | 5228 |
| BEST checkpoint path | F:\pytorch\Research\outputs\formal_training\b1_phase_a\run_20261003T093522_417735Z\epoch_015.pt |
| BEST SHA256 | 564bec95ea18df837f3dfb9b9235c2fdabdfd601daaa03b0cd46cd7fa978a0bd |
| LAST SHA256 | 4418a15c365a0e40e628b06f83a489f436ee37097cafaf66c114c2605a6b95e2 |

physical batch=2，accumulation=1，drop_last=false；每 epoch 5227 个 batch2 加一个 singleton，共 5228 次更新。监督分母为 full batch 6860 / singleton 3430。Validation batch=8，固定顺序完整累计 10501 个样本。AdamW、Conv2d.weight only decay、gradient clip=5、BF16/FP32/FP64 策略、loader=2 均按冻结协议。

BEST 仅依据完整 Validation 的 exact global core loss 严格下降选择，ties 保留最早 epoch。early stopping 与 BEST 独立：patience=8、min_delta=1e-4，max epochs=50。数学 scheduler 固定 W=5228 / U=261400；一基 update 的 LR 在 optimizer.step 前设置。warmup 允许低于 min LR；min LR 下界只用于 cosine。只保存 train+validation 完成的 epoch boundary checkpoint，BEST/LAST binary 全部仅存 F 盘。

| BEST 2024 Validation 指标 | 数值 |
|---|---|
| Brier | 0.09392464048396917 |
| AUROC | 0.8940050888743675 |
| Average Precision | 0.5849030052620285 |
| conditional mean pinball | 0.12424061094322172 |
| N valid | 36018430 |
| N rain | 4496600 |
| strict crossing count | 0 |
| nonfinite count | 0 |
| support violation count | 0 |

训练损失只代表训练集记录，不作为 generalization 指标。上述 Validation 指标全部来自 BEST 所在 epoch 对完整 10501 个冻结样本的真实 inference；未根据辅助指标重新选择 checkpoint。

新增及相关 pre-training unique tests=336，post-training read-only tests=28，均通过、0 skipped。

{'source_copy_count': 2347072, 'authorized_raw_open_attempt_events': 4694144, 'every_successful_copy_has_two_raw_opens': 'readonly copy plus source SHA read', 'source_bytes_copied_over_epochs': 9173717868880, 'staging_copy_seconds_sum': 29382.620995896206, 'staged_read_seconds_sum': 35993.747273000496, 'peak_single_temporary_bytes_per_worker': 636106619, 'all_source_size_sha_cleanup_pass': True, 'every_scene_count_per_year_equals_completed_epochs': True, '2025_RAW_ACCESS': 0}

研究者先停止后明确要求继续。B1 从已验证的 epoch 8 LAST 恢复 model/optimizer/RNG，重跑未完成的 epoch 9；未保存的 5228 次真实更新保留在所有尝试账目中。完成训练轨迹与实际累计更新分开记账，原停止记录和 partial I/O 不删除。I/O 主表仅对账完成训练轨迹；所有尝试及停止时两份临时副本清理另见 resume_all_attempts_execution_audit.json。恢复前 103 项相关测试、修订后的 7 项治理测试和 200 项继承测试兼容复验均真实通过；重跑不重复计为 unique tests。epoch 9 全部 5228 次重跑更新的样本、LR、loss 和梯度范数与停止前记录逐项完全一致；这不等同于逐更新 full-state SHA 验证。中文临时目录、缺失历史证据环境绑定及旧 v1 inventory 与已批准 v1.1 的差异造成的测试失败均保留，随后使用隔离 fixture 解决。

每次复制均核验大小与 SHA 后通过英文 staging 解码，成功后清理。本轮没有永久复制完整月份。copy/read seconds 是跨 worker 累计耗时，不等于运行 wall time。正式 run 的 engineering/test-fixture optimizer counters 均为 0。

完整逐 epoch history、checkpoint registry、raw access/staging 审计和 32 tau diagnostics 均作为配套证据保留。POD/FAR/CSI=THRESHOLD_NOT_FROZEN。科研解释等待研究者审阅；后续执行由独立追加授权和各阶段 gates 控制。
