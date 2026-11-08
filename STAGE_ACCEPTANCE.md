# 2026-11-08 Harness终态独立复核完成 / LIVE.21

Harness已完成E2工程终态、保存证据身份与四格算术独立复核，结论PASS_WITH_LIMITATIONS。报告4071字节，SHA256 85eb17a8cefc202d24ce16b2eb090af51a99ea889eb3794c89268fe88514d569，已直接读取。终态与指标解释继续沿用LIVE.20，科学NOT_VERIFIED、外部PARTIAL、研究者NOT_ASSESSED。

审核分支Git同步PENDING。DSH HEAD仍471f5b45c4936d9e5bfedcde3049534a8358516a，审核报告尚未提交，执行方记录index.lock权限拒绝及SEC_E_NO_CREDENTIALS。复核完成与远端归档分别登记，回执见 `docs/research_readiness/20261108_lambda2_recovery/TERMINAL_REVIEW_ACK.json`。以下为历史快照。

# 2026-11-08 E2固定E9完整封口 / LIVE.20

B8限定恢复于北京时间09:44:38正常退出0，480必要重放完成、有效4320更新，完整963场景2024 Dev和新E9权重已核验。新增53063828496源字节/15869次，2319.634秒，额外重试0。重放第九轮训练摘要与原停止前记录逐字段一致。工程PASS。

主指标未加权条件Pinball的lambda2减lambda1，B7为−0.00059658845（改善0.4683%），B8为+0.00019483716（退化0.1536%）。B7 Brier退化，发生AP两者下降，q32整体覆盖均升。B8−B7主指标差E0为−0.00051842344、E2为+0.00027300218，交互+0.00079142561。结果呈取舍，强雨改善及DTFM去留待科学收敛。

证据见 `docs/research_readiness/20261108_lambda2_recovery/TERMINAL_VERIFICATION.json` 与 `RESULTS.json`。仅Seed2029，历史E0环境全指纹缺失、条件继承；AP20[q32] NOT_VERIFIED。终态独立复核待完成。科学NOT_VERIFIED，外部PARTIAL，研究者NOT_ASSESSED。以下为历史快照。

# 2026-11-08 B8/E2限定恢复运行中 / LIVE.19

研究者在前述480重放/1小时范围后直接回复“恢复”。工程版本经检查冻结为f3b90f654b67fda538f4f156422841b69cc50b23，提案规范SHA9feaa59397a95ab3c97dd0f26b15a2520f91b62370687e7e6ff48a5ce61c2713。29项CPU检查通过，Harness独立10项通过，限定审核PASS_WITH_LIMITATIONS。

北京时间09:05:58独立WMI单次启动，实际更新快照3841–3899返回，新增59次。仅B8/2029/E2从E8执行E9，480重放/53063828496源字节/15869次/3600秒/24GiB，检查点SHA及加载各1次，后续重试0。继承完整B7，原失败记录保留，批准已消费。原只读进度页已切恢复并通过HTTP身份/额度核对。

当前恢复IN_PROGRESS，固定E9和完整配对比较待封口。科学NOT_VERIFIED，外部PARTIAL，研究者NOT_ASSESSED。证据见 `docs/research_readiness/20261108_lambda2_recovery/`。Harness审核未读真实权重或私有批准，审核范围和外部授权依据另在REVIEW_OUTCOME解释。以下为历史快照。

# 2026-11-08 E2失败终态 / LIVE.18

B7固定E9完成。B8九轮Train共4320更新完成，E9 Dev计分808/963场景时触发单模型21600秒上限，控制器06:26:52停止并退出1。最新B8完整检查点是E8/3840，最后480更新没有保存为可恢复权重。

两模型累计8640更新、951352206452逻辑源字节/284363次打开，重放及额外重试0。直接全文件SHA核对B7 E9和B8 E8通过，失败日志和部分评价保留。工程整包FAIL，科学NOT_VERIFIED，研究者NOT_ASSESSED。

最小恢复范围为B8/2029/E2从E8执行E9，新增480更新（全部重放）、53063828496源字节/15869次、候选1小时。当前只是PROPOSED范围设计，E2恢复入口、准确新commit/提案/输出和研究者追加批准尚待完成。独立主控已提交事实通报，接收与回复待核实。

证据见 `docs/research_readiness/20261108_lambda2_stop/TERMINAL_VERIFICATION.json` 与 `RECOVERY_SCOPE.json`。LIVE.17及以下内容为历史快照。

# 2026-11-07 E2已获准确批准并启动 / LIVE-20261107.17

研究者已明确批准YT-E2-20261107-001，绑定执行提交8339fe407fdd084b0271c1af2ae42f98888bbd8e和提案0d5afe6d97b25a163a8adecd95664ffe0b0b0468f157fd20a15cddf4ba44f53f。独立WMI监督器北京时间20:41单次启动并证明无Job/应用包身份。

- 真实更新账本已确认E2、alpha=.5/gamma=2/lambda_q=2、Seed2029和正确原初态引用。启动核验快照B7 RETURNED116，B8 PENDING。当前状态按本机只读进度页查看，私有地址在当前对话与运行记录。
- 已批准各9轮/4320更新，B7→B8串行，总8640更新/955143907680逻辑源字节/285626次/12小时，初始48GiB、每任务24GiB，零重放和额外重试。批准已消费，后台由同控制器接续，失败封口。
- 主指标未加权条件Pinball Sqr/Nrain，发生AP与AP20辅助缺口区分。新E9结果尚待封口，科学NOT_VERIFIED，外部PARTIAL，研究者NOT_ASSESSED。

启动证据为 `docs/research_readiness/20261107_lambda_dispatch/START_RECEIPT.json`。LIVE.17与LaTeX维护实际状态，固定科学执行副本8339fe4保持，旧LIVE.16留存。以下为历史快照。

# 2026-11-07 原初态E2调度包 / LIVE-20261107.16

CLI→控制器→worker→engine显式E2已接通，原初态/九轮顺序设为优化器创建前的必要门槛，独立WMI入口仅接受两模型2029/E2及准确批准。19项合成检查通过（11新调度+8原损失），训练更新0。

- CPU实测两架构完整原初态及九轮顺序匹配。H盘重连后指定2023/2024卫星源SHA一致。准备读取静态1份、卫星2份共10,212,631B，元数据另列，无2025访问。
- 主指标为未加权条件Pinball Sqr/Nrain，Sqr/Nvalid与发生概率AP另列。AP20辅助缺失为NOT_VERIFIED。历史完整数值环境指纹缺失，E0继续有条件复用，不宣称逐位无中断等价。
- 待专项批准包为B7→B8、2029、各9轮，合计8640更新/955143907680逻辑源字节/285626次打开/12小时，初始48GiB、每任务24GiB，重放0、额外重试0。当前没有肯定批准文件或训练输出目录。

方案见 `docs/research_readiness/20261107_lambda_dispatch/EXECUTION_PROPOSAL.json`，实际检查见同目录VERIFICATION。总计划与可修改LaTeX同步为LIVE.16，旧LIVE.15保留。科学NOT_VERIFIED，外部PARTIAL，研究者NOT_ASSESSED。以下为历史快照。

# 2026-11-07 显式分位数损失入口 / LIVE-20261107.15

B7/B8新增独立RunSpec，lambda_q由run_task传至实际engine和既有closed E0/E2损失。默认1保持旧E0；新2限Seed2029、单架构、原初非恢复路径，须显式匹配提案protocol。旧B0/B1的18格RunSpec与网络、数据顺序、AdamW/LR源码保持。

- 8项CPU合成测试通过。默认/显式1损失和输出导数与旧E0逐元素一致，2仅加倍分位数项及qlog导数。实际run_task/真实executor构造/forward通过mock数据边界验证，完整CUDA循环只核对配置传递。
- optimizer.step=0、真实模型前向=0、真实数据/权重/缓存/2025读取=0。初始环境和夹具失败已修正并保留日志，未安装依赖。
- 入口准备不证明幅值或创新收益。历史E0仍有条件继承，正式主指标/保护指标、配对预检、运行环境、输出及限额预算未冻结。科学NOT_VERIFIED，外部PARTIAL，研究者NOT_ASSESSED。

证据与必要限定审核另见 `docs/research_readiness/20261107_lambda_entry/VERIFICATION.json` 及本目录审核回执。可修改LaTeX与 `output/pdf/YunTAPR-Net_Master_Plan_Live_20261107_15.pdf` 同步维护，旧LIVE.14保留。以下为历史快照。

# 2026-11-07 首Seed历史E0继承 / LIVE-20261107.14

按网页主控限额完成Seed2029的B7/B8元数据核对。18份保存epoch记录、完整原初态摘要、九轮顺序、人口/mask及固定E9身份链一致。历史E0端点裁定为CONDITIONALLY_REUSABLE_FROM_ORIGIN，未来新λq=2两格仍为PROPOSED。

- B8从E6/2880恢复后完成1440更新，有效4320。62次旧未保存更新由恢复替代，累计尝试4382，不叠加有效终点，不主张与无中断轨迹逐位一致。
- 固定源码支持fresh AdamW和既定LR规则，保存epoch支持实际E0。初始optimizer实际指纹、逐步LR遥测及E9完整终态加载仍NOT_VERIFIED。
- 原初四格复用历史端点与E9续训分开裁定。未来新格须匹配各自原初态、九轮顺序和科学环境，独立损失入口、成败阈值和精确执行预算尚待完成。
- 2030/2031仅登记已有完整端点，不外推继承资格。4份保存元数据及准备文档保守计1,523,513B；没有权重/manifest正文、真实数据、受限缓存或2025访问，没有模型执行、新指标或训练。
- 本轮新增Harness审核0次、新测试0项。必要的元数据断言、源码身份与文档自检已执行。科学NOT_VERIFIED、外部Stage4.5 PARTIAL、研究者NOT_ASSESSED。

证据为 `docs/research_readiness/20261107_e0_inheritance/MATRIX.json`。总计划为 `output/pdf/YunTAPR-Net_Master_Plan_Live_20261107_14.pdf`，可修改LaTeX同步维护。旧LIVE.13及下列历史内容保留。

以下为前轮历史快照。

# 2026-11-07 DTFM合成梯度检查 / LIVE-20261107.13

按网页主控限定规格完成隔离CPU探针。真实fusion初始化保持，48/26/28通道、width16、工程Seed20261107，每臂5步诊断SGD，weight_decay=0。7项回归通过，一次CLI合计10次合成optimizer.step，科研更新和真实载荷读取均0。

- B7条件投影从第2次反向出现非零梯度，B8从第3次出现，调制投影从第2次出现。梯度均有限且非None。
- B8 GFS/terrain投影五步内实际参数delta仍为0。图可达不证明有效学习，正式AdamW、真实mask/损失及长期性能原因仍NOT_VERIFIED。
- 主控将汇总登记为SYNTHETIC_GRADIENT_PATH_CHECK=PASS_WITH_LIMITATIONS。原始CLI的PASS逐字保留，B8条件投影实际更新仍未验证。默认执行链和科研初始化保持原版本，按主控采用诊断SGD，现有依赖保持。
- 结果见 `docs/research_readiness/20261107_dtfm_gradient_release/RESULT.json`，检查与指纹见 `VERIFICATION.json`，独立审核及同步实际收据另列。后续E0继承/正式四格仍待精确方案和新预算。
- 科学NOT_VERIFIED，外部Stage4.5 PARTIAL，研究者NOT_ASSESSED。计划为 `output/pdf/YunTAPR-Net_Master_Plan_Live_20261107_13.pdf`，旧LIVE.12和历史记录保留。

以下为前轮历史快照。

# 2026-11-07 DOTE/DTFM增益不足讨论 / LIVE-20261107.12

三名独立代理、网页GPT总控与DeepSeek Harness接受新的候选顺序。先检查DTFM真实初始化下的梯度通路，再核对历史E0可继承性，有条件地做B7/B8 × 全局λq∈{1,2}四格对照。二次评分转为辅助分析。当前仅讨论和文档维护，探针及新训练均未执行，预算未批准。

- 初始内层零梯度由代码和链式法则推导，长期延迟及性能原因尚未验证。旧梯度测试手填非零后检查，未覆盖自然释放。
- 严格匹配各架构原初态、科学代码、顺序、AdamW/LR、数值环境、人口/mask和固定E9时，可复用E0两格。首个预指定Seed新增λ2两格仅为候选，不能自动扩为三Seed或四格重跑。
- 分开报告loss收益、同loss的B8−B7与交互。λ2只加强整个条件分位任务，尾部改善未知。DOTE两边共有，贡献仍另审。
- 建议共同未加权条件Pinball主评价，强雨幅值、尾部损失/覆盖/锐度与q32 AP辅助，Brier和整体误差护栏。数值效应门槛、允许退化、Seed和预算未冻结。
- 工程PASS仅限讨论与文档核对。新干预NOT_STARTED，科学NOT_VERIFIED，外部Stage4.5 PARTIAL，研究者NOT_ASSESSED。

当前记录见 `docs/research_readiness/20261107_innovation_resolution/DISCUSSION.json`，计划见 `output/pdf/YunTAPR-Net_Master_Plan_Live_20261107_12.pdf`。下列2026-11-06内容保留为历史快照。

# 2026-11-06 强雨性能路线讨论收敛 / LIVE-20261106.11

三名独立代理、网页总控及Harness已完成路线讨论：优先一次固定T17 P20_c开发性评分pilot，损失配比训练为独立条件候选，DOTE机制对照/多尺度补证后移。此为PROPOSED路线共识，不是实验批准或性能改善结果。

- 读出试验只检验AP与同报警数量的TP/FP；固定网络和A/B/C时，原点雨强及其20mm/h零检出保持不变，不能宣称修复幅值或校准。
- TopK不等于固定FPR；尾形有额外假设；稳定log风险须保持原候选和真实并列；delta_AP>.001未冻结为业务或科学达标线。
- 若另做训练，须同B7 E9起点、等步数/顺序/学习率的E0对照，不能直接和旧E9比，也不能根据pilot成败自动启动；B7 E2入口与完整状态身份尚未核实。
- 总控65bbaaba已接收Harness22:53独立意见并确认讨论闭环。本轮无真实载荷读取、新统计/测试/推理/训练或预算，2025封存。科学NOT_VERIFIED、研究者NOT_ASSESSED。
- 最新总计划19页；旧LIVE.10保留。讨论来源、分歧处置与文档指纹：docs/research_readiness/20261106_performance_route/DISCUSSION.json。新PDF为root审后文档维护/视觉自检，不冒称Harness审核新PDF。

---

# 2026-11-06 委托决策共识与B7完整精度AP恢复 / LIVE-20261106.10

研究者明确将本轮方案与有限预算交由多代理讨论，一致后推进、有实质分歧才回报。Codex、三代理与网页总控已就真实DOTE对场景固定随机旋转、AP20[q32]、2029→2030→2031固定顺序和描述性判据达成共识；不据此产生无限训练或2025权限。

- 已有2024 Dev B7三Seed的q32 AP完整精度恢复为0.020566094533768432、0.014264745852766623、0.01350099359125544；同963场景/3303090像元时次/717个严格R>20，标签/像元/场景时间对齐，逐archive SHA通过。不是P20校准或DOTE优于旋转的结果。
- 首次排序内存分配失败真实保留；精确低内存修正通过24项人工检查和同规模1GiB Job人工probe后，只做一次明示纠正。两次累计archive4243320264B/484次、metadata8883044B/18次，准备另计，零后续重试；无模型推理/训练/2025读取。
- lookup完整manifest的排除边界修正另2项检查通过；C/D指定准备文件samefile已核。真实完整manifest未读，元数据/预检、E9主评分回调和新路径仍待绑定；控制训练未启动。
- 证据：docs/research_readiness/20261106_q32_baseline/CONSENSUS.json、RESULT.json、VERIFICATION.json；旧失败ATTEMPT_V1_FAILED.json保留。新总计划18页及可编辑LaTeX已更新。限定Harness审核/Git结项见后续回执；科学NOT_VERIFIED、外部PARTIAL、研究者NOT_ASSESSED。

---

# 2026-11-06 三代理实际接口补缺 / LIVE-20261106.9

本轮只补三项可执行工程接缝，不承诺“完美指标”，不注册正式模型或启动科研实验。

- 原生多尺度：实际四层encoder的显式2+tap经旧融合返回同一decoder；真实条件映射、MEE/static/SP04投影及概率头仍未接。
- DOTE桥接：完整已内存原manifest和已验证plan显式绑定到两参数factory；分角色保留SHA，缺正文即拒绝。原run_task未自动提供这些上下文，不伪造绑定。
- 尾部：复用已有严格P(R>r)实现，补P(R>=r)、CDF左右极限及阈值原子质量的保守界，不补全CDF或伪造精确尾概率。
- root合并28项人工CPU检查通过（原生9/桥接7/尾部12），其中1项新贯通实际DOTE公式；旧43/8不重跑。代理另验证复用尾部入口14项，单独记载。
- 总控024a5480及657329d1确认本轮三接口、一次新增差异审核；AP20[q32]仅PROPOSED，B7优先核验复用，不机械重训，不要求逐样本梯度相等。科学/预算门槛未批。
- 实际证据：docs/research_readiness/20261106_parallel_core/VERIFICATION.json；最新计划output/pdf/YunTAPR-Net_Master_Plan_Live_20261106_9.pdf及可编辑LaTeX。科学NOT_VERIFIED，外部PARTIAL，研究者NOT_ASSESSED。

---

# 2026-11-06 DOTE场景映射与局部风接口 / LIVE-20261106.8

按研究者“继续，避免大量无效准备审查”的指令，只补LIVE.7已定位的接口阻塞。新增SceneManifestLookup与DirectionDoteTransform；不改默认BatchReader/PhysicalDote，不注册正式执行器。

- 内存中的既有scene_records结构按冻结digest口径核对，拒绝重复/缺失/冲突；canonical时间角色显式选择，不从frame猜sample_id。
- 在原生pressure mask与目标网格映射之后干预DOTE局部风，重算O/W/L/M；保持frame/MEE/DEM/PS/PWAT及真实mask，支持变化或数值溢出即停。
- 本轮8项人工合成CPU检查通过，旧43项和14来源/8历史端点直接继承，不重复全量审核；限定新增差异的Harness审核及Git状态见回执。
- 真实manifest尚未读取/绑定，正式接线、科学判据和新预算/授权均未完成；候选不是可执行科研实验。科学NOT_VERIFIED，外部PARTIAL，研究者NOT_ASSESSED。
- 接口与检查：docs/research_readiness/20261106_dote_interface/VERIFICATION.json。最新计划output/pdf/YunTAPR-Net_Master_Plan_Live_20261106_8.pdf及同目录可编辑LaTeX源；旧LIVE.7保留。

---

# 2026-11-06 DOTE方向控制冻结候选 / LIVE-20261106.7

在LIVE.6工程准备已经闭环后，按总控6115f59a修正意见，仅核对源码和保存元数据，形成PROPOSED、不可执行的方向控制冻结候选。没有运行新模型、梯度检查、训练或评价。

- 旧B6/B7/ZERO/PERP共8个固定E9身份按原收据绑定；本轮没有重新读取权重。旧ZERO不重训，128无梯度权重不冒充等有效容量。
- 澄清B6旧提案baseline_E9字段对应的是development JSON，权重SHA另按LAST_epoch_09.pt绑定；旧文件不改。
- 新建议为场景稳定刚性随机旋转及固定toward-east控制，仅改DOTE局部物理风。场景ID/analysis窗口映射和正式包装器尚未接入。
- 主指标/效应门槛/退化规则/推断/资源与允许路径均待明确批准；不可自动执行。q和no-mask保持NOT_AVAILABLE，外部PARTIAL、科学NOT_VERIFIED、研究者NOT_ASSESSED。
- 方案与来源：docs/research_readiness/20261106_dote_direction_freeze/；最新计划output/pdf/YunTAPR-Net_Master_Plan_Live_20261106_7.pdf及同目录可修改LaTeX源。旧LIVE.6与43项合成检查历史保留，未重跑。

---

# 2026-11-06 CORE-PREP-20261106.1 / LIVE-20261106.6

研究者明确独立观测验证当前无法完成；原Stage4.5缺口保留，不记PASS或自动豁免。其余原目标已由3个辅助代理讨论并开始隔离工程准备，总控限定范围见d813781b。

- 三个新候选：显式多尺度融合接口、DOTE方向/可用性控制、场景身份与日历分组；未接旧默认、训练入口或真实数据。
- 最终人工合成CPU检查43项通过（13/10/20）；旧扩展回归在收集阶段缺PyYAML而未执行，不安装依赖、不冒称通过。
- 多尺度接口仍未接原生encoder/decoder和真实物理映射；元数据一致性不证明载荷正确；天气事件NOT_IDENTIFIED。
- 最新总计划：output/pdf/YunTAPR-Net_Master_Plan_Live_20261106_6.pdf；可修改源仍为同目录YunTAPR-Net_Master_Plan_Live.tex。旧LIVE.5及初稿保留。
- 证据：docs/research_readiness/20261106_core_completion_prepare/。本轮工程等待Harness限定审查和Git闭环；科学NOT_VERIFIED，掌握NOT_ASSESSED。后续真实实验/2025无新增批准。

---

# 阶段验收统一入口

## 2026-11-06 项目总进度

当前处于IMERG参考下的开发资料成果收敛与证据整理阶段。研究主线为云南复杂地形约束下的近实时卫星概率降水反演，既有实证采用 2023 Train 与反复使用的 2024 Dev。

- 2026-11-06 论文成果收敛：已编写内部 Results/Discussion/Limitations 初稿，10项主张、12份来源与反例索引；仅引用已有保存结果，无新指标/图表/训练或2025读取。B3/B4、真实DOTE/ZERO、B7/B8三seed及B5/B6、B3_DOTE_ONLY单seed分列，科学NOT_VERIFIED。见 [可编辑初稿](output/pdf/YunTAPR-Net_Internal_Results_Discussion_Draft_20261106.tex) 和 [证据索引](docs/research_readiness/20261106_internal_paper_draft/CLAIM_EVIDENCE.json)。
- 2026-11-06 研究者报告目前没有已落实外部参考资料，并提出无可落实公开替代来源时采用IMERG。监督参考既已冻结为IMERG V07 Final，本轮沿用；只整理既有参考一致性结果，不能替代独立外部真实性或自动获得确认性E。Stage4.5仍PARTIAL，不再泛搜；H1/H2 INCONCLUSIVE，2025封存，无新增数据/计算授权。见 [本轮参考路线与证据边界](docs/research_readiness/20261106_imerg_reference_scope/REFERENCE_SCOPE.json)。
- 2026-11-06 CMA进一步核实：A.0012.0001及云南_530当前为近7日/三小时累计降水；公开附件109条云南站号不是有效历史序列；J.0017.0009.S002为近24h的24小时降水估测图像，更新6分钟不代表6分钟雨量。历史小时档案、QC及项目许可未落实，不能用这些产品替代2023/2024外部验证。见 [本轮产品身份收据](docs/research_readiness/20261106_cma_hourly_radar_metadata/CMA_PRODUCT_IDENTITY.json)。
- 2026-11-06 Stage 4.5公开元数据实查：NOAA发现框内176条身份记录（非云南可用站数）；DPR V07在2023/2024暖季发现框CMR命中325/324，每年仅保存3条元数据。昆明跨产品站号未绑定、小时降水覆盖/许可未核实；DPR与IMERG存在共享上游链，不能标记完全独立真值。未获取观测或执行模型。详见 [可追溯元数据收据](docs/research_readiness/20261106_external_reference_metadata/METADATA_FEASIBILITY.json)。
- B0–B8 及既有控制实验的完成范围继承下方历史收据。本轮没有新增训练或重新评价。
- 11月5日已提交的 B3_DOTE_ONLY / seed2029 收据报告固定 E9、4320 更新完成。四项发生概率/条件分布指标小幅改善，RMSE 上升，强雨点检出仍为 TP/FP/FN=0/0/717。该单 seed 既有收据处于原 V3 九模型比较范围之外，AP 使用降水发生标签，与强雨排序 AP 的标签不同。单 seed 结论与参数变化局限保留。详见 [既有收据](docs/research_readiness/20261105_b3_dote_without_mee/receipt.json)。
- 本轮已只读核实11月5日后续工作簿保存了182个完整2024日期、19个固定端点、每Seed624260像元日的日累计结果。旧交付收据的零完整日是历史快照。高程评价仍只覆盖策略五/八/九，坡度/坡向和Train W/L/M分组未补齐。保存结果存在不等于本轮独立复算，详见 [补全回执](docs/research_readiness/20261106_research_convergence/HISTORICAL_EVIDENCE_RECOVERY.json)。
- T12–T14 的限定排序证据与科研收敛结论继承。T15 理论结项，T16 原稿保留 Harness 的 NEEDS_REVISION，T16-R1 经总控接受，T17 理论结项并保留补充定义。完整来源与覆盖缺口见 [本轮证据索引](docs/research_readiness/20261106_research_convergence/REVIEW_INDEX.md)。
- T18-R1 已获 Harness 限定 PASS，仅限 PROPOSED 纸面推断候选。初稿 NEEDS_REVISION 与修订关系保留；C1/C2 数值为必要拒判保护，不能证明真实覆盖。独立 E、联合 AP/Top1 推断适用性材料和精确执行批准仍缺失。详见 [T18 审查状态](docs/research_readiness/20261106_research_convergence/T18_REVIEW_STATUS.md)。
- 原V1.3开发池与后续2023Train/2024Dev具体口径分开登记。原计划已有独立外部验证，额外E是T16–T18确认性要求，不能作为所有原计划工作的共同阻塞。H1/H2仍INCONCLUSIVE / INDEPENDENT_NOT_VERIFIED，具体执行预算与批准仍须满足。已有外部参考候选调查，实际许可/观测/独立源链未落实。详见 [入口条件](docs/research_readiness/20261106_research_convergence/EVALUATION_ENTRY_GATES.md)。
- 总项目计划书按研究者要求建立持续维护的 [执行状态更新版PDF](output/pdf/YunTAPR-Net_Master_Plan_Live_20261106_5.pdf) 和 [可修改LaTeX源文件](output/pdf/YunTAPR-Net_Master_Plan_Live.tex)，原20260924方案保留，不以文档更新自动批准科研变更。
- 科学状态 NOT_VERIFIED，研究者掌握 NOT_ASSESSED。网页 GPT 总控、Codex 执行、Harness 独立审核，研究者保留最终科学决定。
- 本轮记录与 Git 同步限定在各自工作分支。2025 Final Test 保持封存。下方记录按各自历史时点阅读。

## 2026-10-31 本地与GitHub进度清算

项目目标是云南复杂地形下近实时卫星概率降水反演（QPE）。当前实验证据来自2023 Train/2024 Dev，核心959/963场景、GFS f006回顾估计、四UTC时次；尚未证明业务全天近实时可用。正式研究路线按V1.3区分方案与已验证范围。

**已经完成：**B0/B1两seed×E0/E1/E2，B2单seed，B3/B4及B7/B8各三seed，B5/B6单seed，ZERO_DOTE三seed和方向性探针单seed的既定Train/2024 Dev。19份固定E9指标补算、31配置单表及既有极端降水专项审计也已交付。全部训练完成结论均限登记口径；不存在B0-B8整体科学验收全部通过的结论。

**等待实验验证：**DOTE物理归因、DTFM全面/多尺度增益、独立事件极端技能与跨年泛化。实际B7/B8训练使用单SP04尺度、width16；不能写成完整多尺度B8已通过。九份B4/B7/B8的A/B/C候选点估计在严格>20 mm/h均TP=FP=0、FN=717，强雨点检出没有改善证据；候选点估计未冻结。

**正在进行：**带局限的科学验收、论文主张收敛和研究者理解对齐；本轮没有运行训练。**尚未开始：**B9与2025独立最终测试。**等待本人掌握：**指研究者待核验的知识清单，不由代码或AI代替本人宣称已掌握。2025继续封存，旧失败/重放/未验证时间预算原样保留。

源档已普通推送工作分支，公开main仍是2026-10-27快照；PR #1保持草稿，未合并。[完整清算PDF](output/pdf/YunTAPR-Net_本地与GitHub同步及科研进度清算报告_20261031.pdf) · [逐文件提交清单](docs/sync_audit/20261031/submitted_files.csv) · [安全审计索引](docs/sync_audit/20261031/README.md)。下方旧时间状态按历史快照阅读，不作为当前状态。

2026-10-31展示修订完成：[逐阶段、逐seed、全损失方案对比](outputs/01a17251-29bb-7172-89f8-380b42c4d290/YunTAPR-Net_V1.3_逐阶段逐seed全方案对比_20261031.xlsx)只有一个工作表、一张31行配置表。每行是实际模型×seed×E0/E1/E2之一；只有B0/B1存在全部三种损失方案，其他完成模型为E0。主要指标、20条有效同seed配对差值、均值/样本标准差及改善次数便于比较变量/模块增量。12条点估计未补算配置保留灰底空白和原因，不将缺失填零；无同seed参考不强行配对。原4718行明细与全部科学结果不变，新训练/推理/原始数据及2025读取为0。[本次展示核验](docs/research_readiness/20261025/evidence/compact_stage_comparison_delivery_20261031.json)。以下同日较早交付及运行状态按历史时点保留。

2026-10-31本轮交付完成：19/19项获批固定E9指标补算及B7_PERP_GRADIENT/2029九轮Train/Dev均已封口；一份Excel仅含“完整指标”一个工作表、一张4718行×42列的大表，覆盖31条模型/seed/损失臂记录、全部可得分组、992条分位覆盖记录及配对/seed均值与样本标准差。B0–B9和两类控制说明位于表下方，B9明确未启动。导出文件结构、数字类型、分类分母、配对源值、单seed无伪造SD、公式缓存/重算、左右/底部版面及脱敏检查通过。原19项范围外的B0/B1 E1/E2、ZERO及探针点估计缺口明确n.a.，没有追加推理或补零。该交付是获批范围与现存证据的完整版本，不代表所有方法均已计算或独立年份科学验收通过。原失败、480重放及旧时间NOT_VERIFIED全部保留，2025继续冻结。 [完整单表](outputs/01a17251-29bb-7172-89f8-380b42c4d290/YunTAPR-Net_V1.3_完整指标与消融对照_20261031.xlsx) · [交付核验](docs/research_readiness/20261025/evidence/complete_metric_workbook_delivery_20261031.json)。下方进行中/停止条目是历史记录。

2026-10-31终态核验：B7_PERP_GRADIENT seed2029已完成固定E9及九轮2024 Dev。继承E1–E5，新E6–E9四轮全部Train/Dev、8天气账本、1静态与1失败源校验均封口；恢复1920更新含480必要重放，新源212,259,080,749字节/63,474次，新段6364.619秒，小于10800秒。有效更新4320，累计尝试4800；累计交付509,171,050,013字节、预约509,175,755,262字节/152,398次，旧失败、不确定源与旧时间验收NOT_VERIFIED不清零。实际E9 SHA5406e20e241a3697b867ba4f44519397c2943b2381bc047d938c4eb141ce34e6已单次复核。19项指标补算完整保留，未新推理或读取2025。训练/评价为COMPLETE_TRAIN_AND_DEV_EVALUATION；科学结论仅COMPLETE_WITH_LIMITATIONS，真实B7相对探针总体Brier/AP较好、AUROC/Pinball/q32绝对误差较差，20–50强雨Pinball退化。最终单张大表正在完成导出核对。 [终态证据](docs/research_readiness/20261025/evidence/dote_physical_control_completion_20261030.json)。以下运行/停止/待批准条目保留为历史时点。

2026-10-31恢复已获准确批准并单次启动：研究者对完整限额申请回复“好”，7d4970d/ebd2391e已在独立WMI固定副本运行。出错2024源一次4,705,249字节完整SHA校验通过，E5模型/AdamW/学习率及RNG恢复成功，本次快照新增157次RETURNED（有效训练位置2557，累计尝试3037，本段已重放157）；E1–E5继承，E6–E9进行中，尚无E9，不算训练完成。只读页面已切换并分列有效位置、本段和累计尝试，原480未保存及旧失败保留；19项指标不重算。仍限新增1920更新含480重放、212259080749字节/63474次、3小时/24GiB，额外重试及额外重放0，批准已消费不得重复启动。按批准每30分钟最多8次/4小时静默跟进，已取消的资源保护不恢复。2025冻结，最终单大表等待E9封口。 见[真实批准及恢复启动收据](docs/research_readiness/20261025/evidence/dote_physical_recovery_started_20261031.json)。下方失败/待批准描述为历史时点。

2026-10-31恢复准备已完成，正式恢复仍未启动：唯一候选B7_PERP_GRADIENT seed2029从真实E5/2400检查点恢复E6–E9；新增1920次更新，其中480次必要重放，累计4800次尝试仍为同一seed。新增源读取上限212,259,080,749字节/63,474次（四轮训练/Dev 212,254,062,672字节/63,472次，另加失败源一次4,705,249字节校验及静态312,828字节一次读取）；新段限时3小时，至少24GiB，额外重试及额外重放0。代码7d4970d，规范化提案SHA ebd2391e0d6e95b1aa0a573df21416822f5173e1a6a11a8eafd6b74679e1f0d6。8项新增CPU检查通过，实际E5 SHA验证通过；失败源元数据/打开检查通过，0气象载荷读取、0优化器更新。系统Event1确认00:05:44Z低功耗恢复，紧接读取异常，但I/O因果仍未核实；新入口按UTC挂钟和单调时钟中较早截止值保护，旧超时验收不追认。19项指标不重算、旧失败/480未保存更新完整保留。原零重放批准已消费，须一次明确批准该恢复提案及新增资源后才运行；2025冻结。 见[唯一限额恢复提案](docs/research_readiness/20261025/evidence/dote_physical_recovery_proposal_20261031.json)。

2026-10-31终态：B7_PERP_GRADIENT/2029在E6 Dev的Himawari实际内容读取抛出OSError [Errno22] Invalid argument，按失败即停退出，未自动重试。已执行2880更新、6轮Train/5轮Dev，最新完整检查点E5/2400（原收据SHA9330e71c…），480次更新未保存，E9不存在。实际记录交付296,911,969,264逻辑字节、保留296,916,674,513字节预约/88,924实例，含1份4,705,249字节PARTIAL_UNCERTAIN源；不能将其物理读取当作零。启动至退出挂钟跨度约10小时22分44秒，超过6小时批准值；活动GPU时长和休眠/时钟原因未核实，时间预算不能宣称验收通过。底层源/存储故障未确定，不等同此前WinError121。19/19指标结果完整保留不重算；最终完整单表因候选E9缺失而BLOCKED，不用E5代替E9，不形成新的公平性能结论。原批准已消费，任何恢复和至少480次必要重放须新的限额批准，本轮未启动恢复。2025继续冻结。 见[真实失败与保留账本](docs/research_readiness/20261025/evidence/dote_physical_control_failure_20261031.json)。下方运行快照为历史时点。

2026-10-30最新核对：19/19份固定E9指标补算已完成，冻结概率指标与整数计数gate全部通过；四项修正实际读取389,975,899,096字节/88,692内容实例、0优化器更新，用时4441.9秒，继承15项。原自动衔接在模型加载前因跨副本相对配置路径找不到文件而退出，0训练更新/0气象读取，历史失败保留。配置改为绝对路径后，原9b4046a/0444d92e已于北京时间21:43:11由独立WMI完成首次正式启动，当前B7_PERP_GRADIENT/2029为IN_PROGRESS（本次快照68次RETURNED），尚无E9，不算训练完成。原4320更新/477571953840字节/142813次/6小时/24GiB、零重放/额外训练重试额度不变；2025冻结。最终一工作表一大表等待该候选封口，未导出冒充完整。 见[指标完成与首次训练启动收据](docs/research_readiness/20261025/evidence/metric_completion_candidate_started_20261030.json)。下方排队、待批准与早期进度为历史时点。

B5/B6终态元数据时点：`2026-10-27T07:30:47.980516+00:00`。B7/B8后续状态由独立启动/终态收据和本次Git提交绑定，不把该旧时点冒充新训练时间。B0–B4限定基线交接为 **COMPLETE_WITH_LIMITATIONS（带局限完成）**；B5/B6为 **COMPLETE_TRAIN_AND_DEV_EVALUATION**，地形单seed消融带局限完成；最终泛化验收为 **NOT_VERIFIED（未核实）**。B7/B8三seed及DOTE真实数值对零控制三seed均已完成固定E9/2024 Dev与描述性分析。DOTE仅Brier三seed一致降低，排序/强雨收益未稳定复现，q32仍不足；限定科学验收COMPLETE_WITH_LIMITATIONS，物理因果与最终泛化NOT_VERIFIED。 后续研究者直接指令已选择单seed方向性探针；候选等待19项指标评价全部通过后串行启动，当前NOT_STARTED/QUEUED，不写成训练完成。不能把训练完成等同于全部科学假设通过。

|模型|已经完成|尚未完成或限制|本阶段判断|
|---|---|---|---|
|B0/B1|seed2026、2027，各E0/E1/E2固定九轮Train/2024 Dev|两seed；10,455/10,501人口；历史执行commit绑定不完整；历史不确定尝试未追认|限定人口内基线对照可交接|
|B2|seed2029/E0/f006，九轮、4,320更新及2024 Dev，固定E9 LAST|仅一seed；B2/B3指标方向混合，未证明时序增量全面改善|当前探索性配对条目完成|
|B3/B4|2029/2030/2031三个独立seed的九轮Train/Dev及固定E9配对|强雨和q32缺陷、同一开发年，未证明最终泛化或统计显著性|描述性随机性复现完成|
|B5/B6|seed2029/E0/f006各九轮Train/Dev、4,320更新、固定E9权重身份与B4公平配对均完成|仅单seed；总体收益混合、q32和强雨仍有退化、DEM发布链未验证|训练/评价完成；探索性地形消融COMPLETE_WITH_LIMITATIONS|
|B7/B8|2029/2030/2031各九轮Train/2024 Dev、固定E9及三组配对完成；原62/441重放保留|仅总体AUROC三seed同向改善，AP/Pinball/q32不稳定，Brier/强雨仍退化；DOTE数值主对照另列；物理因果与最终泛化未验证|COMPLETE_TRAIN_AND_DEV_EVALUATION；科学验收COMPLETE_WITH_LIMITATIONS|
|DOTE零数值主对照/2029（历史单seed）|同B7架构、真实mask、全初值逐位匹配；7项新CPU检查通过|128权重无损失梯度，不能称有效容量完全匹配；九轮固定E9已核验；真实B7总体四指标改善、q32退化，单seed归因有限|COMPLETE_TRAIN_AND_DEV_EVALUATION；COMPLETE_WITH_LIMITATIONS|
|论文/最终测试|主张分级、精确经验Brier分解、35周块探索性区间和预注册草案完成|无独立暴雨ID；2025全模态人口/新适配器未核实，未解封|PREPARATION_COMPLETE；强归因/最终泛化NOT_VERIFIED|
|ZERO_DOTE/2030、2031|2030/2031各九轮Train/Dev、实际E9 SHA与账本均封口；连同2029形成三seed配对|Brier改善3/3；排序与强雨增益不稳定、q32退化2/3，128无损失梯度权重/同Dev年局限|COMPLETE_TRAIN_AND_DEV_EVALUATION；科学验收COMPLETE_WITH_LIMITATIONS|
|非零方向性探针|B7_PERP_GRADIENT/2029固定E9及九轮Train/2024 Dev已完成；有效4320、尝试4800含480获批重放|单seed；分布/空间混杂保留；原失败段时间验收NOT_VERIFIED；物理因果未验证|COMPLETE_TRAIN_AND_DEV_EVALUATION；科学结论COMPLETE_WITH_LIMITATIONS|
|2025最终测试|继续冻结；12模型身份目录及合成元数据检查完成|全模态人口未核实、适配器未实现、预注册未冻结、揭盲预算未批准|DRAFT / NOT_STARTED|

## 同人口比较范围

- B0/B1：同seed、同E臂的10,455 Train / 10,501 Dev，允许比较单通道时序增量。E0/E1/E2分别记录，损失臂及恢复不算新seed。
- B2/B3：seed2029，959/963，E0/f006、固定E9 LAST。B2为7通道×1时次t−10分钟，4,332,290参数；B3为7×6，4,349,090参数。槽位权重映射乘sqrt(6)，其余72个兼容张量同初始化，不宣称模型完全等价。
- B3/B4：三seed各自共享959/963、初始化兼容部分、顺序与评价掩膜；B4增加13变量GFS MEE（气象环境编码器）。跨seed改变初始化与排列，恢复重放仍属于原seed。
- B5/B6：已与B4 seed2029在同人口、同初始B4身份、同顺序、同评价口径下完成固定E9配对。不得跨B0/B1与B2–B6的不同训练人口直接归因架构优势。

## 当前训练状态

以下为一次只读元数据快照，不是实时页面，也不把已封口的一轮当作九轮完成。

|模型|seed|阶段状态|执行状态|已返回更新|完整Train/Dev轮数|
|---|---|---|---|---|---|
|B7|2030|COMPLETE_TRAIN_AND_DEV_EVALUATION|COMPLETE|4761|9|
|B8|2030|COMPLETE_TRAIN_AND_DEV_EVALUATION|COMPLETE|4320|9|
|B7|2031|COMPLETE_TRAIN_AND_DEV_EVALUATION|COMPLETE|4320|9|
|B8|2031|COMPLETE_TRAIN_AND_DEV_EVALUATION|COMPLETE|4320|9|
|B7_ZERO_DOTE|2029|COMPLETE_TRAIN_AND_DEV_EVALUATION|COMPLETE|4320|9|
|B7_ZERO_DOTE|2030|COMPLETE_TRAIN_AND_DEV_EVALUATION|COMPLETE|4320|9|
|B7_ZERO_DOTE|2031|COMPLETE_TRAIN_AND_DEV_EVALUATION|COMPLETE|4320|9|

## 本轮交付核对

五个根目录文件为统一入口，旧报告和实验收据保留。矩阵含39条历史/当前记录；不是39个独立seed或39个已完成模型。新增四任务全部九轮/有效4320；B7/2030实际4761尝试含441重放，其余各4320。新段14400、累计17721；三seed含旧2029，恢复不是独立seed。 新B7_ZERO_DOTE/2029九轮Train/Dev、4320更新及实际E9已核验，零重放/额外重试。 新两控制均已完整九轮Train/Dev、4320更新及实际E9核验；2029继承形成三seed，不重训成功任务。`epochs`表示该记录已封口轮数，`global_steps`为实际RETURNED计数，失败时可高于最新保存更新；训练完成须同时具备全部Train/Dev收据、账本、预算和固定E9身份。

本次继承6份完整指标补算结果，新13项由独立WMI控制器串行继续，旧B4/2031部分25,621,522,638字节账本保留。候选2场景缓存前向/E0/反向已通过、0优化器更新，128列梯度探针响应；新增续算4项与训练入口4项CPU检查通过。旧125项公式测试及原模型检查继承。只在19项指标全过后启动一份新候选；训练尚未开始、旧成功模型不重训、2025冻结。

本轮出版基线：`9b4046a655e2ec91633104eaa64bd507cca81aad`。文件所属最终提交由Git历史标识；实际训练代码另见[矩阵](EXPERIMENT_MATRIX.csv)和[证据索引](EVIDENCE_INDEX.md)，不得用本次文档commit替代执行commit。

[实验矩阵](EXPERIMENT_MATRIX.csv) · [完整数值与差值](METRICS.csv) · [科学分析](SCIENTIFIC_ANALYSIS.md) · [证据索引](EVIDENCE_INDEX.md)

## DOTE数值主对照三seed已完成：COMPLETE_WITH_LIMITATIONS（带局限完成）

新增ZERO_DOTE/2030、2031于北京时间`2026-10-29T23:39:52.803307+08:00`全部封口。[新增两模型完成收据与三seed配对](docs/research_readiness/20261025/evidence/dote_control_three_seed_completion_20261029.json)已核对18轮Train、18轮2024 Dev、36气象账本、2静态账本及2份实际固定E9权重SHA；2029真实B7/零控制及2030/2031真实B7直接继承，未重训。新增实际8,640更新、955,143,907,680逻辑源字节/285,626次，均等于批准上限；重放/额外重试0。文件mtime区间27052.308秒（约7小时31分），小于43,200秒/12小时；两任务分别小于21,600秒/6小时，这不是精确GPU计费。

执行`8a4668377dbd40013245b54550c0963d10c286fb`，提案SHA `a53d38293e9b783b787e84baca7c9c0f1502cbae051828e4578a24051733a6c6`。E0/f006、959 Train/963 Dev、Train2/Dev8、AdamW/原LR前4320步、固定E9 LAST、精确AUROC/AP与全部掩膜继承。实际E9身份如下：

|控制seed|完成时刻（北京时间）|更新|任务mtime秒|E9权重SHA256|
|---|---|---|---|---|
|2030|2026-10-29T19:55:10.865172+08:00|4320|13570.225|`b03ee41cd190dc7579a1fb993afb1f5598997fca91af3b1c2addc6eed430f0ba`|
|2031|2026-10-29T23:39:51.627064+08:00|4320|13479.642|`f99952905157d8e649e567af671d0ee3ff02f11530a9996b80306ef758acdac0`|

下表差值一律 **真实B7−B7_ZERO_DOTE**，保留全部三个seed。均值和样本标准差（ddof=1）描述训练随机性，不是独立年份或独立暴雨的置信区间，也不构成显著性证明。q32名义水平0.984375，以距名义绝对误差判定改善；覆盖率、偏差、误差均采用0–1概率单位。

|指标|Δ2029|Δ2030|Δ2031|均值|样本标准差|改善seed|差值符号|
|---|---|---|---|---|---|---|---|
|Brier（布里尔分数）↓|-0.00164552334109|-0.000425722974357|-0.000606637739566|-0.000892628018339|0.000658271268807|3/3|一致|
|AUROC（ROC曲线下面积）↑|0.000834969708618|-0.000781947735366|-0.000338124899657|-9.50343088016e-05|0.000835419225112|1/3|不一致|
|AP（平均精确率）↑|0.00469357842999|-0.00145198063148|-0.000485921816268|0.000918558660747|0.00330475386409|1/3|不一致|
|条件Pinball（分位数损失）↓|-0.000882871078732|-0.000360876247541|0.000651098343787|-0.000197549660829|0.000779918090412|2/3|不一致|
|q32覆盖率|-0.00426904026286|-0.00101024961993|0.00186111519788|-0.00113939156164|0.00306711749433|1/3|不一致|
|q32−名义覆盖率|-0.00426904026286|-0.00101024961993|0.00186111519788|-0.00113939156164|0.00306711749433|1/3|不一致|
|q32距名义绝对误差↓|0.00426904026286|0.00101024961993|-0.00186111519788|0.00113939156164|0.00306711749433|1/3|不一致|

有限结论：**Brier在三个seed均下降；AUROC/AP仅2029改善，条件Pinball改善2/3，q32距名义误差改善1/3、退化2/3；20–30和30–50 mm/h的2029 Pinball收益在两个新seed均未复现。** 因此不支持全面预测优势、稳定强雨收益或极端尾部已校准。当前三组对照的实际训练/评价完成，科学验收为COMPLETE_WITH_LIMITATIONS。原始指标和完整分层在METRICS.csv保留，2025继续冻结。

## B7/B8三seed固定E9完成：COMPLETE_WITH_LIMITATIONS（带局限完成）

完成于北京时间 `2026-10-29T07:19:48.193141+08:00`；[新增30轮封口、60气象账本、4静态账本、4份实际E9 SHA及三seed汇总](docs/research_readiness/20261025/evidence/b7_b8_three_seed_completion_20261029.json)已核对。2030/2031四模型均为COMPLETE_TRAIN_AND_DEV_EVALUATION，旧2029原值与62次重放记录继承，恢复不算额外seed。

执行代码`e81c6e1e0306e2a1e31103f1cc632be3c0d84d8c`；准确恢复提案SHA `3314231ac64531bf523a06d5ff8e3dc4f688d705fc4f4324b57c1548a846aa3e`。新段14,400更新含441必要重放，累计17,721实际尝试；新源读取1,591,906,721,352字节/476,044次，累计1,934,666,227,950字节/578,566次，额外重放/重试均0。新包mtime区间约15.2679小时，低于21.2239小时上限；保守计入旧9,994秒后约18.0440小时，仍在原24小时内。这里是文件mtime区间，不是GPU计算计费；分模型实际量及上限见收据。

DTFM仅总体AUROC在三seed同向改善；AP、条件Pinball、q32未稳定复现，Brier在两个seed退化。科学假设没有因工程完成而自动通过。B7/B8共享条件信息、4,411,058活跃参数、公共初始化与同seed顺序，比较的是concat残差与有界DTFM的替换融合。2025冻结，没有新增推理、调参或训练授权。


## 2026-10-30物理归因增量

ZERO三seed经验Brier分解补齐：真实B7的REL项3/3下降、RES项2/3下降，不能等同总体校准或物理机制证明。非零方向性探针有实质混杂，不建议立即投入正式GPU；本轮新正式训练/推理/优化器更新均0，2025无新增访问。详见[科学决策](docs/research_readiness/20261025/evidence/physical_attribution_decision_20261030.json)。

## 后续执行指令：先指标补算，再单候选

研究者回复“是，准备并启动该候选”，按此前披露的同一单模型上限绑定至`9b4046a655e2ec91633104eaa64bd507cca81aad`/`0444d92ef9b10afa2b661c58b32fe57782c3ab5750879bec675f04967c68ce67`；该直接启动原文不包含SHA，不伪称研究者逐字批准过SHA。13项剩余评价在新目录进行，前段报告中的0新推理/缓存RAM阻塞均为较早时点。候选仅在19个COMPLETE且gate全过后启动，至多4320更新、477571953840源字节/142813次、6小时，零重放重试。按最新要求，最终Excel只有一个工作表内的一张分类大表，模型解释位于表格下方；待全部终态后更新，不交付半成品冒充完整。

## 2026-10-30指标补算停止快照

15/19指标补算已有效完成；B0/2026 E0在16:32因条件Pinball及q32冻结一致性检查失败，后续3项与方向性候选均被阻断。原有训练科学验收不因此改写，B0新复算结果不得替代原冻结指标。最终完整单表仍IN_PROGRESS；本轮仅启动只读监测页、通过3项新CPU检查及HTTP/浏览器验证，没有训练、推理、重放、2025访问或自动恢复。完整事实见[面板及停止收据](docs/research_readiness/20261025/evidence/metric_pipeline_monitor_20261030.json)。

## 四项补算修正准入：PREPARED_NOT_APPROVED_NOT_STARTED

15项既有指标结果继承；唯一修正包为B0/B1的2026/2027四项Dev推理，原B0/2026的一次必要重复单独记账。内容总上限389,975,899,096字节/88,692次/12小时、0优化器更新、无后续自动重试。已有B0计数22,838是日志事件，实际内容读取10,775次，不能混用；原失败记录保留。精度/推理上下文已修正、脚本快照及batch8已锁定，5项新门控检查和1项计数检查通过，缺少准确批准时实际入口拒绝。尚无新GPU推理结果，数值一致性仍待真实通过严格gate；不提前称修正成功或完整交付。见[唯一提案](docs/research_readiness/20261025/evidence/metric_b01_correction_proposal_20261030.json)。

## 修正包批准已消费：IN_PROGRESS

研究者已明确批准3d632954/daa745a0。独立WMI已一次启动，B0/2026完整10501场景Dev已精确通过五项冻结指标与全部计数gate，15项成功继承后16/19，B1/2026已接续；尚不能宣布四项或完整表通过。新增补算仍0训练更新，389975899096内容字节/88692次/12小时，后续重试/重复0。候选原训练批准仅在全部19项gate通过后由同控制链使用，当前未开始；[实际批准与启动](docs/research_readiness/20261025/evidence/metric_b01_correction_started_20261030.json)保留权限与真实状态，2025继续冻结。
