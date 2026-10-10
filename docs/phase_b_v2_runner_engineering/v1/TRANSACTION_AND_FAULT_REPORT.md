# Checkpoint 事务与恢复

schema=SYNTHETIC_B9_V0_CANDIDATE_v1，实际文件只存在本轮 .local/synthetic_checkpoint_workspace/session_* 临时目录，不发布任何合成权重。

包含 model、AdamW state、S0 scheduler、Python/NumPy/CPU/CUDA RNG、seed、arm、模型、来源 commit、冻结来源 SHA、候选源码 SHA、protocol SHA、initial SHA、人工数据角色及完成边界。formal_epoch=0、FORMAL_OPTIMIZER_STEPS=0；proposed_epochs/endpoint=9 仅为待审批候选字段。FRESH0 的 synthetic_updates=0；LAST1 只表示一个人工微循环完成，不能宣称完整 2023/2024 epoch 或 V0 科学终点评价完成。

原子候选：独占创建锁 → 临时 blob 序列化 → flush/fsync → 文件 SHA → rename blob → flush/fsync 并 rename receipt → 返回可恢复 reference。读取时先核对 byte size/SHA，再 weights_only=True 反序列化。保存未提交不返回 reference，禁止覆盖。原子 rename 和注入测试不证明 Windows 断电后目录持久性；正式集成仍需独立验证。

|故障 / 风险|实际测试结果|
|---|---|
|序列化后中断、blob 提交后中断|无 commit receipt；保留 part/orphan；不能恢复|
|rename 文件锁异常、预存外部锁|拒绝保存；不删除外部锁|
|文件截断、byte 修改、receipt SHA 错|在反序列化前拒绝|
|model/optimizer 缺失、错误 seed/arm/epoch/source/protocol/code SHA|完整校验拒绝；真实 B0/B1 恢复负面测试证实 live state 不变|
|AdamW moment 缺失/形状/dtype/NaN/Inf/负二阶矩/step/LR 错|纯合成元数据校验拒绝|
|train/validation 边界不完整、未知字段|拒绝保存或恢复|
|apply 阶段注入异常|runner poisoned；后续 update 拒绝；无自动重试|
|FRESH0 重放、完成 LAST1 恢复|6 个完整模型事务的 model/optimizer/scheduler/RNG SHA 完全一致|

恢复不恢复 task_step_ledger，故无法用 checkpoint 回滚获得额外合成额度。当前 synthetic_updates 最多 2；完整 B9 正式 runner 的 epoch 事务、验证 10501 样本完成证明、真实 LAST 祖先与独立批准均尚未实现。
