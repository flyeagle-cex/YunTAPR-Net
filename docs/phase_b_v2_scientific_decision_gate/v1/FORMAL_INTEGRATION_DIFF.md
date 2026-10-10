# 正式源码集成差异（提案，未应用）

本轮没有修改任何 src、正式配置、模型/损失或历史证据。以下是实际源码静态审查与未来新增版本的语义差异，不是已经可执行的 patch。不能把现有合成入口删除一个布尔值便用于真实数据。

## 准确的现状及待增功能

所有路径相对仓库；source_registry.json 固定各文件 SHA。

|现有源文件 / 函数|实际能力 / 限制|未来正式版本所需变更；批准前不应用|
|---|---|---|
|experimental/phase_b_v2_ablations/config.py：get_config、RunSpec、proposed_runs、learning_rate_prefix|封闭三臂/两模型/三 seed、18身份、S0数学与47052单运行更新范围|复用科学参数，新增经批准的协议/执行范围绑定，不增搜索空间|
|experimental/phase_b_v2_integration/initialization.py：fresh_paired_models、seeded_environment|真实 fresh 同形状配对、SHA证明、固定seed环境；来源核验涉及冻结物件|复用算法，正式依赖经授权的精确 artifact 验证；不 warm-start，不更换初态|
|experimental/phase_b_v2_formal_runner_candidate/protocol.py：fresh_models_without_observational_artifacts、run_identity|合成版本用 scoped verifier 避免真实 scaler 访问；identity 指向合成注册表和2轮夹具|正式版不得照搬 verifier 替身；绑定真实 data/scaler/mask/protocol/code/resource SHA 和批准事件|
|同目录 data.py：Scene.validate、Registry、Loader、Coverage|人工 pathless ID、years=()、每角色恰好5场景；串行2/8批、一次覆盖|另建真实适配器，精确冻结ID/角色/因果/单位/同bytes SHA、防火墙；继承全覆盖算法，10455/10501实际loader顺序另测。不放宽合成Scene让其冒充真数据|
|同目录 adapter.py：forward|真实v2结构与候选loss形状/精度适配|复用经审查的候选损失和输出，正式语义数据批次独立类型；模型定义不动|
|experimental/phase_b_v2_runner_candidate/optimizer.py：new_adamw、clip_and_check、PrefixSchedule|冻结AdamW分组、clip5、S0 pre-step；原恢复 completed≤2|正式版调度进度校验改为批准单运行B9预算，绑定更新/epoch/LR；不可放宽现有合成类|
|experimental/phase_b_v2_formal_runner_candidate/engine.py：EpochEngine.__init__、train_epoch、validate_and_commit|限定 seed2026、CUDA、合成Registry、最多2轮、每轮3step、先验证再LAST；异常poison停止|新增正式引擎支持已批I3范围、真实5228step/epoch、B9固定终点；资源/完整性/权限前置核验。合成与正式独立命名空间|
|同目录 metrics.py：StreamingValidation.add/finish；training/phase_a_validation_v2.py：LogDomainValidation.add/report|已接入 FP64共同Core和unweighted CPB，全覆盖；并检查每场景3430有效|新增全协议 Brier、十箱、exact-score AUROC/AP、全32覆盖、七雨强层、tail/span摘要及35块充分统计。不是现有类已经输出的指标；可复用科学审查算术，需新独立测试与内存/磁盘预算|
|同目录 checkpoint.py：EpochStore、validate_last；engine.py：restore_completed_last|临时合成存储、1–2完整epoch收据、update=epoch×3；状态/SHA/顺序/父LAST校验|正式store独立路径；完成train+完整validation后原子LAST；schema绑定正式epoch×5228、原许可祖先、预算不可回滚；实际崩溃/锁/持久性另测|
|同目录 safety.py：Ledger、install_guard|合成总额度30，保存/读取仅临时范围；不是正式授权服务|新正式执行账本具跨进程/崩溃耐久性，先检查资源/权限，再消耗不可退款预算；异常无自动重试/改seed/跳样|
|同目录 authorization.py：FutureApprovalBinding、FutureResumeBinding、FutureAuthorityVerifier|仅类型接口，无签发者/验证器；start_formal/open_real_data 无条件抛PermissionError|独立审查的权限验证机制绑定研究者真实事件、范围、版本、资源与撤销；恢复另绑LAST SHA、原授权祖先和新的独立决定。字符串/JSON不可证明权限|

路径完整前缀为 src/yuntapr/；表中“同目录”均指 phase_b_v2_formal_runner_candidate。正式新模块命名空间可提议为 training/phase_b_v2_approved，但该目录本轮未创建，名称本身也不能证明批准。不要修改 Phase-A 正式 runner 或借用 v1 FinalFit。后续需独立代码集成许可，不能凭本轮文档委托施工正式入口。

## 不能视为已通过的项目

真实身份绑定loader、全量数据 QC与SHA、完整18运行评价、真实9轮/多seed、完整指标存储/排序、业务延迟、实际长期资源/崩溃耐久性、权限验证服务与正式恢复祖先均尚未验证。已有 79 CPU/8 CUDA、30合成更新仅引用旧[状态](../../phase_b_v2_formal_runner_candidate/v1/final_status.json)，本轮没有重跑，也不能拿它们替代这些项目。48真实场景只读预检不含模型推理。

正式 Core 必须固定 gamma2 FP64，与三臂训练损失分开；共同 CPB 不带 lambda_q。正式覆盖/稀疏层/尾摘要应输出 NA/暴露数，不降级成“所有指标完成”。未经新审查不得启用新的阈值、统计方法或指标实现。科学接受、工程集成、未来真实只读预检和首批训练是不同权限。
