# Checkpoint 同字节与状态审计

结论：**ARTIFICIAL_CHECKPOINT_SAME_BYTES_PASS**；正式真实模型恢复 **NOT_VERIFIED**。

## 风险与新路径

旧 runner_candidate/checkpoint.py:SyntheticStore.read 先 file_sha(blob) 后 torch.load(blob)，后者重新打开路径。formal_integration_candidate/checkpoint.py:Store.read 委托该函数。本轮不修改旧文件；正式版本禁止继续使用此路径。

新 p1_integration_candidate/checkpoint.py:Store.read：

1. 原生 Path、禁止年份、词法目录/父路径/ADS 和**进程内成功提交的注册表**先于文件 API。外来路径、孤立 payload、重启后未注册引用直接拒绝；外部 JSON 不能建立注册或审批。
2. Workspace 持有目录只读句柄，拒绝 reparse 与实际路径偏离。复用 full_payload_integrity/winio.py:ReadHandle，FILE_SHARE_READ 禁止常规写/删共享。
3. 收据最多 16 KiB，严格字段、唯一 JSON 键、大小整数、文件名、SHA/来源；payload 最多 1 MiB，人工 tensor 最多 256 KiB。单句柄记录卷/文件索引/大小/mtime/属性与实际路径，读前后要求一致。
4. 收据对象/完整字节 SHA 与注册相符；payload 按同一个只读句柄读到末尾，检查截断、多余字节、元数据与 SHA。
5. SHA 匹配后才 torch.load(io.BytesIO(immutable), weights_only=True, map_location='cpu')。不重开路径；校验后替换不改变此次消费字节，后续因对象身份不符拒绝。
6. 校验模型键/shape/dtype/有限性，AdamW 组/矩/step/LR，scheduler，Python/NumPy/CPU RNG，epoch/update，训练排序、完整验证收据、来源、LAST 关系与人工额度。CPU RNG 仅在隔离函数 globals 中替换 GPU 拓扑分支；不改旧函数或全局 RNG。
7. restore_fixture / restore_artificial_boundary 只接受 FixtureState；完整校验和 B9 非回退边界通过后才安装人工字典。live model/optimizer 被拒绝。

保存复用 SyntheticStore.save 原子 blob/receipt 事务，不复用其 reader/构造器。冻结人工 payload，限定序列化字节，再核对原 transport 收据与**预序列化同源字节 SHA**，才写本版本收据并登记。保存到登记之间替换同样拒绝。失败 store 不可重试，保留残留文件，不采用旧 LAST。

## 实际测试

27 个 unittest 方法通过：替换/同内容新对象、截断、错误 SHA、逃逸/年份/任意 PathLike、收据篡改、孤立引用、保存后替换、映射并发写、隐藏元数据变化仍由 SHA 拒绝、体积上限、常规写/rename 锁拒绝、元数据变化、校验后替换、缺 model/optimizer/moment/RNG/validation、拒绝后不安装、无预算回退。子测试不另计。证据：tests/checkpoint_final_27.log。

| 项目 | 状态 |
|---|---|
| 人工同字节/完整 envelope/拒绝后不安装 | PASS |
| 冻结源、旧 smoke 和封存额度不变 | PASS |
| 已批准正式 LAST、跨进程可信注册恢复 | NOT_VERIFIED；本版本重启后无注册即拒绝 |
| 真实模型恢复、CUDA RNG 重建 | NOT_VERIFIED；本轮禁止 |
| 全面敌对文件沙箱/DoS 防护 | NOT_VERIFIED；仅自生成登记限额 CPU 文件 |
| 掉电后目录项/数据库同步持久性 | NOT_VERIFIED |

sharing 不能代替 SHA，尤其已建立映射；SHA 不证明未来字节永远不变。weights_only 不保证任意敌对文件安全。[CreateFile sharing](https://learn.microsoft.com/en-us/windows/win32/api/fileapi/nf-fileapi-createfilea)、[torch.load](https://docs.pytorch.org/docs/stable/generated/torch.load)、[序列化安全限制](https://docs.pytorch.org/docs/stable/notes/serialization)。在线 stable 文档不代替本机实际版本。
