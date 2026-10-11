# 工程 checkpoint 事务

两份独立 schema=`REAL_TRAIN_SMOKE_ENGINEERING_v1` 的 checkpoint 均保存并读取成功，只存在本轮私有临时目录。
复用旧 SyntheticStore 的原子传输步骤，返回前将提交收据标记为本轮 smoke schema；未改旧模块。
新目录以只读句柄返回的真实长路径绑定，解决 Windows 8.3 别名问题。
读取仅接受自身收据和字节；只读句柄绑定对象，检查大小/前后快照/SHA 后，由 `torch.load(BytesIO(immutable), weights_only=True, map_location='cpu')` 消费同一内容。
没有把读回状态装载到模型，没有读取历史 checkpoint。

| 模型 | 文件字节 | SHA256 | 全状态逐字段逻辑摘要匹配 |
|---|---:|---|---|
| B0 | 52060521 | `3b1860653bbe37a71e35af6cf80a6cdfb1fd4f83cd20bbfcf10822644ebf608e` | 是 |
| B1 | 52089321 | `6e62f28ecf19e559b56c24a0dddaca0029c1a07a4a695792e602c07e5e5fc97b` | 是 |

保存 model、AdamW、scheduler、Python/NumPy/CPU/CUDA RNG、seed/arm、两个样本 ID、实际文件 SHA、scaler/mask/SP04、协议/代码身份、更新前后 SHA、额度和直接指令范围。
checkpoint.progress 明确 formal_epoch=0、complete_epoch=false、validation_complete=false、formal Phase-B step=0、本模型 smoke update=1。
固定 LAST/恢复祖先不适用于这个未完成 epoch 的工程产物。`formal_restore` 无条件拒绝，禁止 warm-start、正式恢复及公开权重。

新防护测试实际注入：序列化后中断、blob 后未提交、rename lock、已有锁、截断、SHA 错误、越界收据、schema 缺失。
均按预期拒绝/保留残件；这些是微型人工 payload，未重试真实更新。
文件 fsync/原子替换不证明所有文件系统断电持久性；内容校验也不保证未来文件不变。
