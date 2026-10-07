# Checkpoint 与中断恢复规范

唯一正式状态根目录：

```text
F:\pytorch\Research\outputs\formal_training\b0_matched_v2_phase_a\run_<UTC>\
F:\pytorch\Research\outputs\formal_training\b1_v2_phase_a\run_<UTC>\
```

本轮不创建正式状态。保存每个已完成 train+validation 的 epoch 文件；BEST/LAST 只登记身份，不保存另一份二进制。工程 fixtures 绝不能写入这些目录。

二进制写入 `checkpoints/run_<attempt UTC>/epoch_NNN.pt`，仍全部位于唯一正式根目录内。这样失败的 orphan/incomplete 文件可以保留，后续获准恢复后的新 attempt 不覆盖同名旧文件。

## 原子事务

独占创建 `.incomplete` → 写盘/fsync → 不覆盖的原子更名 → SHA/大小及回读核验 → epoch audit → immutable complete marker → registry/LAST/BEST。任一步失败保留已有内容，不把 orphan 当可恢复 LAST。恢复只认 registry 与 matching complete marker；不自动修复不完整事务。

Payload 保存 model/buffers、optimizer及分组、scheduler规则/W/U/update/last-next LR、Python/NumPy/Torch CPU/CUDA RNG、completed_epoch、已完成/下一 epoch 排列 SHA、BEST/early-stop独立状态、覆盖证明、初始化及代码/配置/normalization/manifest/环境身份。文件 SHA 与逻辑状态树 SHA 都验证。

## 恢复

必须另有绑定具体 LAST SHA 和原授权祖先的研究者恢复批准。先验模型/run/root/字节/SHA和provenance，随后反序列化并校验内部状态、keys/shapes/dtypes、optimizer分组、scheduler边界、RNG与排列；全部通过后才应用状态。所有构造结束后恢复 RNG，复核恢复后状态 SHA。

只从完整 train+validation+audit 轮次进入下一 epoch 的首批；不能以 BEST 代 LAST，不能从半轮恢复或保留未 checkpoint 更新。已达到早停或50轮的运行不能追加更新。首轮无完成 checkpoint 时须另行批准 fresh 新尝试。

每个 attempt 独立保留，reconciliation 同时记录 retained trajectory、all-attempt 和 discarded updates；崩溃发生在 step 与回执之间时记录上下界，不编造精确数值。历史半轮证据不删除、不计入恢复轨迹。

## STOP 政策

qlog nonfinite、严格单调/支持域失败、loss/gradient/参数/optimizer非有限、数据/坐标/身份/顺序/分母失败立即阻断后续更新。OOM、I/O或审计失败属于执行故障，暂停配对流水线。有限高 qlog 或描述性阈值超越只记录，不构成 STOP。

保存错误、堆栈、attempt/epoch/batch/update、样本身份、已存在的数值摘要、真实 counters 和最后完整身份；不可取得的信息如实注明，不补做 forward。禁止修复、重排分位数、降精度、跳 batch、改变科学规则或自动恢复。失败内存不能成为正式可恢复 checkpoint。
