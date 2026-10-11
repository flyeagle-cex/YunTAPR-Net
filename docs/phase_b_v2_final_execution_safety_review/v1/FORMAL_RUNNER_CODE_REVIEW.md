# 正式候选源码最终审查（静态；无模型实例化）

表中路径统一在 `src/yuntapr/experimental/` 下。PASS只指审查到的限定逻辑或历史证据，正式运行均未执行。本轮未改动以下源码。

| 接口与定位 | 状态 | 结论/最小待审批差异 |
|---|---|---|
| formal_integration_candidate/access.py:15 RealDataAdapter.open_scene/open_manifest/open_artifact；:9 RejectingAuthority | PASS（阻断）；正式能力NOT_VERIFIED | 任何路径操作前拒绝。独立真实approval事件验证服务不存在，不能改bool打开；未来另批版本及connector |
| real_forward_pilot/adapter.py:41 VerifiedReader.authenticate、:67 read、:116 view | PASS（静态及旧限定证据） | 词法拒绝→固定registry→只读句柄→hash→immutable bytes→同字节解码。仅pilot计划/预算，不能直接当全量正式loader |
| formal_integration_candidate/engine.py:27 IntegratedEngine.__init__、:51 _batch、:56 train_epoch、:77 validate_and_commit | NOT_VERIFIED（正式全量集成未实现） | 硬编码seed2026/E0与2/2人工Profile；一个epoch只有一个人工batch，验证仅两个固定日期。需要独立正式实现真实batch iterator、10455/10501覆盖、tail1/5、真实日期、所有预注册arm/seed与全程身份。不得“移除if”直接启用 |
| ablations/config.py get_config；focal.py occurrence_numerator；pinball.py conditional_pinball_numerator；total.py candidate_loss | PASS（静态/旧测试） | E0(.5,2,1)、E1(.5,0,1)、E2(.5,2,2)。BCEWithLogits；gamma0仍有alpha；FP32 rate>.1；32tau均值→雨有效像元求和；FP64 log空间，无修补/排序 |
| ablations/metrics.py:38 common_validation_sums；formal_integration_candidate/metrics.py:50 add、:109 summary | PASS（定义审查）；正式数据规模NOT_VERIFIED | 共同Core始终E0 gamma2/FP64且lambda1，S_q未加权/Nrain；score精确二进制分组保留ties，不用十箱替代AUROC/AP；32覆盖、七雨强层、上尾、UTC块。未来实际scratch预算与整体身份需验收 |
| integration/initialization.py:48 fresh_paired_models；formal_runner_candidate/protocol.py:89 fresh_models_without_observational_artifacts | PASS（旧合成/烟测+静态） | 同名同形状共享参数精确配对；保留B1输入差异，不载历史权重。正式上下文需独立核验整个依赖source、数据/scaler身份和RNG，而不是读取旧smoke产物 |
| formal_integration_candidate/state.py:13 B9State.begin/finish_train/validate/commit_last/endpoint/check_restore | PASS（候选状态约束）；正式事务NOT_VERIFIED | 固定9终点、不采用BEST，完整验证才提交LAST，pending不恢复、不回滚预算；已有LOGICAL_B9不等于真实九轮消费 |
| formal_integration_candidate/state.py:97 ActualQuota.perform；real_train_smoke/quota.py:78 SmokeQuota | PASS（范围内防重复）；正式额度服务NOT_VERIFIED | 前者固定四次人工额度；后者封存两次真实smoke。不能扩展/重置复用作正式run授权。新正式额度必须绑定独立事件与运行矩阵及跨进程原子预留 |
| formal_integration_candidate/checkpoint.py:35 Store.read → runner_candidate/checkpoint.py:76 SyntheticStore.read | FAIL（若用于正式恢复） | 当前继承路径先resolve/stat/hash，再torch.load(path)重新打开；存在SHA与反序列化字节的TOCTOU窗口，且base reader在外来拒绝前resolve。最小另批修复：词法/根范围先拒绝、只读句柄绑定、不可变同字节SHA+weights_only反序列化；复用smoke/checkpoint.py:50 SmokeStore.read的模式而非历史权重 |
| formal_integration_candidate/checkpoint.py:49 validate、engine.py:106 restore_completed_last | PASS（人工字段校验）；正式审批NOT_VERIFIED | 当前只允许自己的人工last_reference；形式化恢复必须额外绑定具体LAST SHA与原授权祖先、独立研究者新决定，未接验真接口 |
| formal_integration_candidate/protocol.py:26 code_sha、:58 identity | NOT_VERIFIED（完整发布身份） | code_sha仅哈希该命名空间，source_commit是候选来源常量，不覆盖复用loss/initializer/reader所有依赖与实际release HEAD。正式版本需完整依赖SHA清单+实际发布commit、审批绑定 |
| formal_integration_candidate/storage.py:25 Workspace.__init__ | NOT_VERIFIED（当前受限环境适用） | 使用mkdtemp；旧交付记录见smoke最终状态中受限临时目录DACL失败。本轮人工目录使用继承ACL的mkdir。另批在正式存储位置验证建目录、读写/锁/fsync，不默认旧workspace可写 |
| real_train_smoke/launch.py:25 launch | FAIL（不能复用旧watchdog） | wrapper寿命当监控寿命、PID缺创建身份、taskkill未检查树清空。新Job后端通过人工验证，但真实入口集成尚未发生；历史smoke不可重启 |

数学复核：训练 `L=(S_occ(gamma)+lambda_q*S_q)/N_valid`；统一Core `(S_occ(gamma=2,FP64)+S_q)/N_valid`；条件Pinball `S_q/N_rain`；tau_i=(i-.5)/32，tau32=.984375；雨标签由原始float32参考值严格>.1定义。Nrain=0报告不可估计，不能作为零技能。科学成功/非劣效阈值与多重比较均不在本轮自动判定。

优先级：正式checkpoint同字节读取与启动树封闭是P1；全量loader/权限/预算/资源/版本身份是进入正式运行的必需门槛。此处只给最小修复建议，没有应用未批准的正式源码差异。
