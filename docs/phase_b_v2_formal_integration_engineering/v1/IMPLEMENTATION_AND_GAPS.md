# 已实现的代码与具体边界

相对路径前缀：`src/yuntapr/experimental/phase_b_v2_formal_integration_candidate/`。

|文件 / 关键入口|实际实现与测试范围|
|---|---|
|`protocol.py`：`Profile`, `identity`|封闭 LOGICAL_B9 与 SYNTHETIC_SMALL；复用 RunSpec、E0/E1/E2、两个模型、三个 seed；绑定代码、协议、数据资格、scaler、mask、SP04、资源摘要及人工授权祖先。人工 SHA 明示 synthetic，不能充当真实来源。|
|`state.py`：`B9State.begin/reserve/complete_step/finish_train/validate/commit_last/check_restore`|SQLite FULL 同步与 BEGIN IMMEDIATE；READY→TRAINING→WAIT_VALIDATION→VALIDATED→READY/COMPLETE；错误转 FAILED。完整训练顺序、验证身份、场景数和 3430/场景分母检查；完整第 9 epoch 终点，无 BEST 替换。|
|`state.py`：`ActualQuota.perform/report`|单独持久化四步额度，每模型最多两步；预约在 optimizer.step 前提交。失败或不明预约不退款，不自动重试。每次预约保留代码 SHA；修复版本的新实例仍共享原额度，不清空旧记录。|
|`storage.py`：`Workspace`, `database`, `install_guard`|专用 `.local/`；有界数据库与磁盘准入；原始数据扩展名及封存年份 open 拒绝；optimizer 调用限定受控 AdamW 上下文。Python hook 不等价于内核沙箱，也不是审批验真。|
|`metrics.py`：`Evaluator.add/finish/score_groups`, `block_id`|复用 common_validation_sums 与 supervision；FP64 共同 Core、未加权 CPB、Brier、十箱、精确并列 AUROC/AP、32 覆盖率、q32 偏差、七雨强层、上尾与 35 UTC 块；每块保留可加总量与 exact-score 频数。|
|`checkpoint.py`：`Store`, `Schedule`, `validate`|复用原子 blob+SHA+receipt 传输，新增 B9 候选 envelope；验证模型/AdamW moments/LR/RNG/初态/代码/数据/完整 train+validation/父 LAST/额度；默认安全 weights_only 读取。|
|`engine.py`：`IntegratedEngine`|继承既有 EpochEngine 状态摘要工具；复用 fresh 配对算法、Batch/forward、AdamW、clip=5、S0。内部生成 batch=2、501×501 输入与独立验证，完成一轮→验证→保存→读取验证→控制器 LAST。当前真实模型工程运行只准 seed2026/E0 两模型，受四步额度限制。|
|`access.py`：`audit_scene_metadata/audit_manifest_metadata/verify_synthetic_bytes`|纯内存角色、10455/10501、顺序唯一性、六时相、IMERG 版本单位与 SHA 合约代码；元数据一致不证明来源真实或有权限。|
|`access.py`：`RealDataAdapter`, `RejectingAuthority`, `start_formal`|真实路径在转换、resolve、stat、open 前无条件拒绝；没有 reader/provider 注入，也没有审批签发者。JSON、布尔值、环境变量或 commit 均不能启用。|

## 不扩大合成证据的适用范围

LOGICAL_B9 使用人工 ID 完成九轮覆盖与 5228×9=47052 更新预算的整数模拟，**没有执行这些优化器更新**。完整矩阵 18 runs 的候选预算仍为 846936，正式运行 0。实际小型 profile 每轮两个人工场景、一批训练、一批验证；复用 S0 原 261400 更新轨迹中的第 1 个 LR，未压缩调度 horizon。

实际 E0 的 B0/B1 模型、优化器、调度器、RNG 重放 SHA 一致。E1/E2 的损失通过既有候选适配器接入数学接口，但本轮没有消耗 E1/E2 实际优化器更新；旧实现测试作为来源证据保留，不重复计算。新指标完全不接收 arm/lambda 参数。

跨进程测试验证预约持久化、锁互斥与不退款；真实模型状态恢复在本轮同一进程的合成引擎内核验。尚未验证进程被强杀或操作系统掉电后的真实模型跨进程继续运行。保存与控制器是两份事务：blob 已提交而控制器未确认的窗口会停止，**不会自动采纳孤立 LAST**。这保留安全性，但可用性与人工对账流程仍需未来工程版本。

正式 10455 场景训练 loader、10501 场景完整验证、九轮真实 AdamW、独立权限服务、资源租约/撤销、真实 checkpoint 目录及跨主机调度均未启用。正式恢复必须另外绑定具体 LAST SHA、原始执行授权祖先和研究者新的独立批准事件；本版本无法验证该事件，因此拒绝。
