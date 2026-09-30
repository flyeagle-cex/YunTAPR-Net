# 2024-07-01 B0 真实单样本工程验证

本轮状态：`ENGINEERING_ONLY_REAL_SAMPLE_VERIFIED`。科学依据仍为 Scientific Freeze v1；`B0_FORMAL_SCIENTIFIC_CONTRACT=FROZEN`，`B0_FORMAL_TRAINING_STARTED=false`。本轮没有多年样本索引、训练、优化器更新、正式 checkpoint、2025 Test 参数选择或科研性能结论。[机器可读证据](evidence.json)保存了来源指纹、四个候选帧的时间、实际形状与有限性、临时副本 I/O 和清理记录。

IMERG 转换后 CF 时间 `T=2024-07-01 00:00:00 UTC`，按冻结合同得到 `analysis_time=00:30:00 UTC`。从 2024-07 月度 Himawari master index 的 4,390 条成功记录中选择最新完成帧，并实际重读本窗口四个 H: 原文件。00:00、00:10、00:20 名义帧的 `obs_end` 分别为 00:09:38.185414、00:19:38.175684、**00:29:38.162509 UTC**；00:30 帧的 `obs_end=00:39:38.155073 UTC`，因晚于分析时刻被拒绝。最终选中 00:20 帧，未使用未来帧或静默回退。上游 Stage-0 索引的 `TIME_MISMATCH` 原标记保留，本轮仅验证独立的因果条件，并不改写上游 QC。

选中帧的 `date_created=00:38:48 UTC`，晚于分析时刻。本轮仅是**离线工程验证**；`date_created` 只记录，不能据此宣称历史实时可用或 operational replay 已获证明。实际 B13 为 `[501,501]`，251,001/251,001 像元有效。IMERG 文件的全局属性为 `GPM IMERG Final Run V07B regional subset` / `GPM_3IMERGHH_07`；独立下载 manifest 记载该日 48 granules、complete、字节数与文件一致。转换文件含 48 个半小时槽位，选中 time index 0，目标窗口中 10,000/10,000 像元有效，其中 5,896 个有效零雨像元。冻结云南中心落区 mask SHA256 为 `9d921def661fc3e58cd1ed783fcf87abbf493da6ae5e5fea79c28043f73495ef`，目标域内 3,430 格点。损失分母为 3,430 个有效云南监督像元，其中 1,967 个条件有雨像元。

真实输入下，原 v1 工程初始化首先触发严格分位单调性异常；[失败记录](attempt_1_failure.md)保留了堆栈结论和数值诊断，未覆盖旧 skeleton run。v2 仅显式调整首层可训练残差投影的**初始化**，其余科研合同未变。v2 真实前向恢复 `[1,48,501,501]` 原生特征，再按冻结 SP04 membership 得到 `[1,48,100,100]` 目标特征；`rain_logit=[1,1,100,100]`、条件分位数 `[1,32,100,100]`，严格单调且物理分位支持大于 0.1 mm h⁻¹。计算一次 masked-loss **有限性检查**时显式使用 `alpha=0.5, gamma=1.0`，仅为本次工程测试值；二者仍是未冻结的 `DEVELOPMENT_ESTIMATED_PARAMETER`，未记录或解释 loss 数值为科学结果。极端阈值超出当前实现的概率接口仍返回 `NOT_ESTABLISHED`。

七次读取均采用单文件英文临时 staging，单次峰值 5,585,672 字节，累计临时复制 30,004,915 字节；每次大小与 SHA256 一致、清理成功，当前没有本流程遗留的 staging 副本。四个 H: 候选与一个 F: IMERG 源文件的前后大小和 SHA256 完全一致。私有边界/mask、原始 B13/IMERG 数组、模型输出张量均未上传。`F:\pytorch\Research\.venv\Scripts\python.exe` 下新 B0 测试 **19/19**、原 Scientific Freeze 测试 **42/42** 通过。

剩余限制：该单样本检查不证明多年月度完整性、历史 operational availability、正式训练损失配置、模型精度或泛化能力。Focal alpha/gamma、部分 B13 与 target-support 的正式阈值仍待 2023/2024 开发阶段确定。本轮在真实工程链验证与 GitHub 提交后停止，不进入正式训练。
