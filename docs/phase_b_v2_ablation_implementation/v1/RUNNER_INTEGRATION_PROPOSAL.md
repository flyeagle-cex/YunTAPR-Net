# 独立 v2 runner 的非执行型集成提案

当前只有readiness.BlockedRunner：describe()返回18身份、预算、阻塞事项，run(*args,**kwargs)无条件抛FormalExecutionBlocked。传入approved=true或字符串AUTHORIZED_TO_EXECUTE也不能运行。没有训练loop、DataLoader、模型实例、Optimizer、checkpoint应用或旧FinalFit引用。

未来建议新增隔离v2 runner，而非修改Phase-A原入口；因此本轮没有需要应用到正式路径的diff补丁。建议模块责任：审定协议/执行授权读取与独立真实性验证；数据防火墙与2023/24配对资格；可复核fresh initializer；seed和固定样本排列；训练objective适配本候选；固定E0 FP64科学汇总；逐epoch验证与immutable LAST事务；异常停止与具体LAST独立恢复；日志和资源审计。这里不实现实际训练启动。

Fresh一致性接口readiness.py逐项解释：TensorIdentity(shape,dtype,sha256)要求正整数tuple、float32、64位小写十六进制SHA。state_metadata_digest(tensors)将按参数名排序的声明serialize为JSON再hash，是声明层digest，不能替代真实tensor bytes哈希。FreshRecord包含RunSpec、张量映射、state/RNG/order/initializer_code SHA及historical_checkpoint_loaded=false；validate重验字段与digest。

audit_fresh_metadata(records)要求完整18项、不重复；同模型/seed跨三臂full state digest一致；同seed六run的post_pair RNG与样本order SHA一致；initializer代码身份一致；B0/B1名字集合相同，只允许backbone.enc0.conv1.weight和backbone.enc0.skip.weight的shape不同，其他声明完全相同。函数只检查输入metadata，不打开模型、权重或原始样本，所以actual_initialization_proven=false，即使metadata_consistent=true。

后续实际initializer仍要证明参数总数、同名同形拷贝、B1两个不同形状权重保留native初始化及zero skip、独立reseed、没有historical optimizer/RNG转移、完整初态真实SHA。正式shape必须冻结501输入/100输出与模型参数量；本轮tiny metadata fixture不证明真实模型满足这些条件，也不构造这18个模型。

review_checkpoint_binding(metadata,expected,resume_approval_reference=None)要求封闭字段：run/LAST/model/optimizer/RNG/scheduler/code/protocol/data/init SHA、完成epoch、retained updates、完成train+validation边界、原执行事件reference。epoch1..9，updates=epoch*5228，expected明确绑定六项run/LAST/code/protocol/data/init。epoch9 remaining=0，不能继续训练。函数不加载或应用状态；即使给reference字符串，approval_authenticity_verified=false、can_apply_checkpoint_state=false。

这些字符串只是合成fixture或待独立核验的来源引用，不是生成审批。未来恢复须真实研究者独立决定并绑定具体LAST SHA、原运行祖先、剩余预算、额外重放成本，再由经审查的正式gate处理；每次独立批准，禁止自动retry/resume。原B1 LAST14恢复偏差继续NOT_GRANTED。

训练和评价必须分离：candidate_loss按各臂gamma/lambda优化；metrics.common_validation_sums固定E0 FP64共同core，CPB始终unweighted S_qr/N_rain。18run固定epoch9，不使用新成绩选择BEST或改阈值/样本。阶段1 seed2026完整六run和阶段2另两seed十二run各有独立执行批准；阶段1成绩不能修改已批准规则或自动启动阶段2。

安全接续顺序：核对本版Git/SHA与失败记录→研究者学习并审查代码、处理科学待决字段→独立批准候选数学及正式集成范围→另版工程化新runner与获授权的模型/数据preflight→绑定真实初始化、数据、资源身份→另行批准具体阶段执行。当前开发委托已覆盖候选loss合成forward/backward，但不覆盖这些后续正式步骤。
