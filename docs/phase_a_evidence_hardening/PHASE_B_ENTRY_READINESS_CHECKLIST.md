# Phase-B 工程入口准备清单

结果：允许范围内的只读核验和合成准备完成；正式 v2 Phase-B 入口尚不具备启动资格。v1 训练路径存在不能代表 v2 已就绪。

|项目|本轮证据|状态/下一步|
|---|---|---|
|v2 模型入口|B0MatchedV2/B1V2，1/6 帧、32+1 raw head|静态源码核对；全模型 synthetic 推理未重复|
|checkpoint|两个 Epoch 9 BEST SHA、状态未改收据与历史指标身份|元数据核对；私有 checkpoint 字节未重读|
|冻结输入|协议内 10 个仓库输入 SHA|通过；外部静态 mask 未重新打开|
|数据年限|本轮只访问发表的 2024 聚合统计|2025 raw/pixels=0|
|随机性|seed=2026、2,000×35 配对重采样矩阵零差异|通过；不估计训练种子变异|
|数值保护|实际 v2 CPU tiny fixtures 无梯度更新|单调、有限性、支撑、物理溢出拒绝通过|
|恢复安全|checkpoint_v2 的身份先校验、完成 epoch marker、原授权链|静态核对；历史独立恢复审批缺口保留|
|批准检查|prepare-only assess_entry，严格 bool/身份/年份/恢复字段|合成通过；永远不能启动训练|
|正式 v2 Phase-B 协议及 runner|未发现已授权入口|RESEARCHER_DECISION_REQUIRED|

现有 src/yuntapr/training/phase_b_preparation.py 是旧 v1 单时相 FinalFit 规则：SCENES=23,447、2023=11,720、2024=11,727、EPOCHS=11；不能默认为 v2 的匹配训练集合或训练长度。v2 冻结 Phase-A 集合为 10,455/10,501，但不据此擅自定义 Phase-B 合并集合。数据资格、重新拟合 normalization、fresh/resume 初始化、训练预算、checkpoint 选择和评价策略均需研究者独立决定。

新 src/yuntapr/diagnostics/readiness.py 是待审核的检查表模拟器，不是 authorization 颁发器。即使 synthetic 字段全部满足仍不启动；JSON 中 true 不证明实际人类身份。未来正式入口需从独立研究者批准的不可变文档验证范围、SHA、代码版本、数据年限和 provenance，随后才可准备真实 preflight。本轮没有修改任何正式训练入口、冻结配置或权重。

停止条件：缺独立批准、SHA 不符、非完成 epoch、原授权链变化、2025 请求、格网不合、非有限值、支持/严格序丢失、源文件锁或清理失败。实际正式 run 的停止/恢复策略仍需由审批协议确定；不得自动跳过 batch、降级数据或修改 loss。

未执行：正式配置实例化、真实数据 preflight、checkpoint 反序列化、正式恢复、训练更新。后续测试若涉及合成 optimizer step，也必须与正式更新分别计数且取得该范围授权。本轮 48 个合成测试无 backward/optimizer step，历史 770 项不是本轮执行数。

本轮仅诊断与工程准备；RESEARCHER_SCIENTIFIC_APPROVAL_REQUIRED=true；V2_PHASE_B_AUTHORIZED=false；2025_RAW_ACCESS=0；2025_PIXELS_READ=0。
