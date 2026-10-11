# 零更新失败后重新发布：seed2026 v2

研究者明确授权一次重新发布与启动。这不是 checkpoint 恢复，不使用任何历史权重，也不重置旧任务。旧源码、release、失败收据、launch.once、SQLite 和全部日志保持原样；`old_zero_update_ancestor.json` 绑定祖先 SHA、零更新与无 LAST 的事实。新 worker 对祖先证据保留不允许写入/删除共享的只读句柄。

独立源码：`src/yuntapr/training/phase_b_v2_seed2026_v2/`。代码直接版本化复用 v1 已修复的 Runner，只改变输出、campaign/额度身份、失败祖先绑定及审计进度。518 个目录的精确注册逻辑、科学设计和所有资源上限不变；完整解码器、模型、损失、fresh 初始化、评价、checkpoint 和 Job 后端继续复用。

固定顺序 B0/E0、B1/E0、B0/E1、B1/E1、B0/E2、B1/E2；seed2026，每组九轮，每轮 5,228 更新，每组 47,052 更新。旧任务零更新 + 新任务至多 282,312 次尝试，总授权上限仍为 282,312。一次性新版 launch 和永久额度位于独立 `.local/` 与固定 `.git/phase_b_v2_seed2026_a1863dc_republish_v2.*`，无自动第三次启动或退款。

2023 Train 10,455、2024 Development 10,501 场景，D1/Q1/N0/I3/B9/S0/V0、M-C 探索性解释不变。2025、其他 seeds、FinalFit、历史 B1 恢复不在授权内。历史 2025 属性访问仍 NOT_INSTRUMENTED。

`release.json` 固定源码 commit、源码/冻结配置 SHA、软件依赖清单 SHA 和失败祖先。`execution_status.json` 记录真实进度；完整 epoch 及 LAST 未完成时不宣称通过。训练权重、精确分数和完整日志只保存在 `.local/`，不公开。
