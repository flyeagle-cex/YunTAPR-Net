# v2 formal runner 规范

入口 `scripts/run_paired_phase_a_v2.py` 提供 preflight、initialization-proof、train、resume、monitor、publish 子命令。无默认训练命令；train/resume 必须提供独立授权 JSON 和 SHA，不支持 CLI 覆盖科学参数。

## 模块职责

|模块|职责|
|---|---|
|formal_phase_a_v2|元数据合同、授权、fresh pairing、train/validation/epoch 状态机|
|phase_a_validation_v2|FP64 原始分子全局累积；没有物理分位数依赖|
|checkpoint_v2|完整 epoch 事务、状态身份和恢复验证|
|upper_tail_v2|只读、分阶段、分区的上尾统计|
|phase_a_audit_v2|独立计数、原始访问防火墙、不可变证据|
|scripts/paired_phase_a_v2|工程 preflight、隔离测试、只读网页和发布进程|

沿用已有仓库分层：实际 `optimizer.step` 由 scripts 执行层 `execution_ops.py` 持有，src 模块负责梯度计算、保护与审计并显式调用该操作。科学冻结合同测试仍可确认 src 不直接持有 optimizer.step；正式启动授权门和独立 counter scope 均保留。

## Fresh pairing

分别 seed=2026 后构建新 B0 anchor、新 B1；核验 state_dict 同名同 dtype。只复制同名同形 tensor；仅 `backbone.enc0.conv1.weight`、`backbone.enc0.skip.weight` shape 不同。保存 B1 原生不同形 kernel 的复制前后 SHA，保持原生零 skip。记录全部共享 tensor SHA、完整模型 SHA、构建后 RNG SHA、参数分组。B0 参数总数4329410，B1=4331810。

两个独立进程重复构建必须逐位相同；正式进程再次构建并核验。后运行的 B1 也从全新 anchor 配对，不能复用训练后的 B0。

## 完整 epoch

Train → Validation → checkpoint → audit → 发布完成标记，之后才能开始下一轮。

Train：10455 scenes，batch2/drop_last=false/accumulation1，5228 updates。排列由独立 CPU torch.Generator(seed=2026+epoch_index) 生成，逐批核验 index，整轮恰好一次。分母普通批6860、singleton3430。每次先设置 stateless LR，再 forward/loss/backward、有限性检查、global clip5、AdamW.step，记录调用和成功回执。

LR：W=5228、U=261400，u≤W 使用 `1e-4*u/W`；之后使用冻结50轮 cosine 至1e-6。warmup 不套用 min_lr 下界。optimizer/loss/精度/loader 原样继承冻结 JSON：BF16 forward、FP32 parameters/raw、FP64 normalized transform/pinball、TF32/GradScaler=false，workers2/prefetch1/persistent=false/pin_memory=false。

Validation：eval+inference mode，batch8、固定顺序、tail5，10501 scenes/1313 forwards。FP64 累积 S_occ 与 S_qr，global_val_core_loss=(S_occ+S_qr)/36018430；不平均 batch mean，不使用旧 physical-output accumulator。

BEST 仅在 global_val_core_loss 严格更低时更新，平局保留较早轮。early stop 独立比较 `v < best_es_value-1e-4`，patience=8，最大50轮。新增诊断不进入任一选择逻辑。

## 计数

FORMAL、ENGINEERING_ONLY、TEST_FIXTURE_ONLY 不共享 counters。FORWARD_CALLS 包含失败调用；另分 TRAIN_FORWARDS/VALIDATION_FORWARDS；BACKWARD_CALLS 记实际调用；OPTIMIZER_STEP_ATTEMPTS 与成功返回的 OPTIMIZER_STEPS 分离；CHECKPOINT_WRITES 和可恢复完成标记分离；RAW_SOURCE_OPENS 由各父/worker 实际原始文件打开记录对账。

无失败完整轮应有6541 forwards、5228 backwards/steps、1313 validation forwards。raw copy 与 hash 各一次打开，必须与 staging exposures 和 worker 日志对账，不凭常量宣称2025零访问。

## Monitor / publication

localhost:8769 默认只读，每5秒刷新；显示模型、epoch/step、损失、LR、梯度、BEST、patience、ETA、诊断及显存。未见完成证据不能显示完成。monitor 无 raw/checkpoint/control endpoint。发布进程与执行 checkout 隔离；网络失败留 pending，禁止 force push 和提交非白名单文件。
