# 2026-11-06 科研证据归档索引

本目录由 Codex 维护。它保存现有理论文本及修订关系。项目当前总进度继续由仓库 README.md、STAGE_ACCEPTANCE.md 与本地 Shared/PROJECT_STATE.md 登记。

本轮依据研究者于 2026-11-06 直接要求持续三方协作、更新各自 Git 和项目总进度的指令。范围限管理记录、证据索引和当前工作分支普通提交推送。研究者保留科学方案、资源预算和最终验收权。

## 1. 已有成果与证据覆盖

| 对象 | 当前结论 | 本轮证据与核验范围 |
|---|---|---|
| T12 既有 V3 排序统计 | 存在强雨排序信息，概率校准和独立泛化待验证 | T12完整报告消息已实际恢复，原始消息逐字导出与公开脱敏副本可追溯；计算stdout仅截断节选，完整原始计算输出仍PARTIAL，未重算 |
| T13 独立复核 | q32 的 27 个 TopK 锚点及 p/A 的限定范围已有独立复核，全部 81 个历史锚点覆盖仍为 PARTIAL | T13原始回传全文及Codex审核回传已恢复；未取得审核者原始收据，不替代原审核范围。本轮未重复统计 |
| T14 科研收敛 | 条件雨强与上尾表达优先于立即加模块，属于 PROPOSED 研究方向 | T14原始回传全文已实际恢复并保留脱敏副本，来源与原消息SHA见HISTORICAL_EVIDENCE_RECOVERY.json |
| T15 | 理论结项，方法 PROPOSED | T15_THEORY_RECORD.md，保存 Codex 已提交文本并脱敏本机定位 |
| T16 初稿 | Harness 审查 NEEDS_REVISION | T16_INITIAL_PROTOCOL.md 与下述五项问题，原稿保留 |
| T16-R1 | 已由总控接受，科学 NOT_VERIFIED | T16_R1_AMENDMENT.md。未发生 Harness 对 R1 的第二轮独立审查 |
| T17 | 理论框架结项，后续推断候选见 T18 | T17_RISK_SCORE_FRAMEWORK.md 与 T17_DEFINITION_ADDENDUM.md |
| T18 / T18-R1 | Harness 对 R1 限定 PASS，保持 PROPOSED | T18_INITIAL_PROTOCOL.md、T18_R1_AMENDMENT.md、T18_REVIEW_STATUS.md；初稿 NEEDS_REVISION 保留，真实适用性及执行门控未解除 |
| B3_DOTE_ONLY / seed2029 | 既有收据报告 E9/4320 更新完成，单 seed、收益混合，处于原 V3 九模型比较范围之外 | 本轮直接读取 ../20261105_b3_dote_without_mee/receipt.json、result.json、validation.json。AP 使用降水发生标签，与强雨排序 AP 的标签不同。权重载荷及计算过程本轮未复核 |
| 2026-11-05 三类反演表 | 后续保存表已记录182完整日/19端点；地形仍PARTIAL | 本轮只读比较原版及两份后续表，日期/数值/公式差异与限制见HISTORICAL_EVIDENCE_RECOVERY.json，未运行评价器 |

DIRECT_VERIFIED 仅用于本轮实际读取的文本、Git 状态及随后文件完整性检查。继承的统计与执行收据本轮按来源转述，不能升级为本轮载荷直接核验或独立科学验收。T12–T14 完整原始对话及计算收据的长期归档仍有缺口，不能把此索引称为全部原始证据归档完成。

## 2. 原 Harness 对 T16 的五项必要修正

以下是 Codex 从指定 Harness 会话正式审查提取的摘要，审核原文由 Harness 自行保留和归档。

1. 块 bootstrap 的抽样次数及块数量门槛不能保证有限样本 95% 覆盖。依赖假设与数值精度不明时保持 INCONCLUSIVE。
2. 单模型、单粒度控制不能声称九模型与两粒度同时 95% 覆盖。区分联合成功命题及失败发现的多重性。
3. 任何必要分量失败都会阻止协议整体通过。跨粒度冲突及留一块分析须分别解释。
4. 基线损失接近零时需明确绝对容差及分支规则。
5. 2024 Dev 不具独立评价资格。33 个系数候选属于拟合内部选择，E 的独立身份应在拟合前确定。

T16-R1 已针对五项问题修订。总控接受与独立审核通过分别记录。本轮进度记录审核不能代替 R1 的科学复核。

## 3. 科研主张边界

- 研究主线为云南全境复杂地形约束下的近实时卫星概率降水反演。既有实证仍受 2024 Dev、采样时次和回顾性输入约束。
- T12 继承的强雨阳性数为严格 R>20 mm/h 的 717 个像元时次，独立天气事件 NOT_IDENTIFIED。
- q32 整体有雨人口覆盖范围继承为 93.48241871%–95.05933990%，名义覆盖为 98.4375%。本轮未重新提取九模型数值。
- A/B/C 严格 >20 的零检出与评分具备排序能力可以同时成立。p 表示雨发生概率，q32 表示条件分位，二者都不能直接解释成已校准 P20。
- B3_DOTE_ONLY 已保存结果显示 Brier、发生概率 AUROC/AP、条件 pinball 小幅改善，RMSE 上升，严格 >20 的 TP/FP/FN 为 0/0/717。发生概率 AP 与强雨排序 AP 使用不同标签，必须分开。
- DOTE 物理因果、DTFM 普遍增益、H1 校准收益、H2 新评分收益及独立泛化均待验证。
- 新模型、最终模型选择、2025 最终测试及业务完整部署均未在本轮决定。

## 4. 当前分工与状态

网页 GPT 负责路线收敛与任务边界，Codex 负责管理记录、实现与获批执行，Harness 负责独立审核及自身版本留痕，研究者负责最终科学决定。

本目录理论方法 PROPOSED。H1/H2 均为 INCONCLUSIVE / INDEPENDENT_NOT_VERIFIED。科学状态 NOT_VERIFIED，研究者掌握 NOT_ASSESSED。管理归档工程检查与远端同步结果以本轮完成回执为准。

Shared/DECISIONS.md 存在两条同名 YT-GOV-20261105-001，分别登记于 2026-11-05 08:31:04 和 08:41:55（Asia/Shanghai），均记为 APPROVED 并引用规则 0.2.0-T07-R1 的同一 SHA256 8631C186735E46DDFE7D07CC5DB2D82CF8E4F484AFDCD100F98510CDC6072440。此处登记直接读到的文本事实，唯一正式批准时间及重复登记的处置待研究者裁定。正文保留 PROPOSED 历史快照。本轮直接聊天指令仅用于限定工作分支记录同步，未改写该制度或代填新的研究者批准编号。Shared 的 main 提交与远程配置继续由研究者管理。

Harness 已对提交 9b02e2c 的管理记录独立审核，完整性与证据等级主体 PASS，最终 NEEDS_REVISION。上述 B3 范围文字已按 F1 补齐，F2 的重复批准记录歧义已明确登记为待研究者裁定。其原审核由 Harness 自行保存在自身工作区 docs/audits/MANAGEMENT_SYNC_20261106_REVIEW.md，当前只读版本 SHA256 为 C15833E5C30E5F7C8A339BFCC9D755101E023BA7ED03DCFDA76876E8DC27AAC8。其后 Harness 已对 fc608c78bb4170d99104ae09490d7455a67aaee2 完成 R1 限定复核，结论 PASS。R1 审核记录为 4257 字节，SHA256 DA7CF3C8A15D6A5CF23ADBD5EA4BC4E3D758CB34299C3243CDC891350C7F2B8C。两份独立审核均由 Harness 自行提交到 collab/dsh-20261102 的 8242607d4e0cb4eecc93543865b4c5c413c8825c，并普通推送。Codex 已只读核对该提交仅包含两份审核记录、工作树干净，另用 git ls-remote 独立核对远端同名 SHA 一致。

MANAGEMENT_RECEIPT.json 是 9b02e2c 内的预提交历史快照，其文件指纹适用于该提交。F1/F2 修订版本 fc608c7 的文件指纹见 MANAGEMENT_REVIEW_R1_RECEIPT.json。本段属于其后的闭环状态补记，原回执按其绑定提交阅读。前序“未送达”描述按当时状态保留，当前交接已送达并取得上述审核。

## 5. 后续最短路线

管理同步已完成。T18-R1 纸面候选已获限定独立 PASS，接下来须满足 E 的合法身份与独立性、真实联合推断适用性材料和精确执行授权。条件满足后依次验证 H1、H2。新方法或训练由结果和研究者决定。现有理论阶段已封口，继续工作围绕实质缺口展开。

执行入口的待满足项目见 EVALUATION_ENTRY_GATES.md。

本轮管理归档、限定差异复核及双方各自分支同步的闭环状态为 PASS。该范围不包含 F2 的正式时间裁决、T12–T14 原始归档缺口补齐、H1/H2 验证或最终科研验收。F2 待研究者裁定，科学 NOT_VERIFIED，研究者掌握 NOT_ASSESSED。下一阶段门槛继续按 EVALUATION_ENTRY_GATES.md 登记。

## 6. 历史证据补全与总计划维护（2026-11-06）

当前已找回T12报告、T13/T14原始回传全文与T13审核回传，逐字原消息在本地忽略归档保留，公开副本在history/。这些是原始消息恢复，不是重写总结或原生计算收据。接口标识T12/T13输出原长54141/65536字符，仅恢复20000字符，更早完整性未核实，完整计算归档继续PARTIAL。

总项目计划书新增output/pdf/YunTAPR-Net_Master_Plan_Live.tex及PDF，作为原V1.3执行状态附录，按每轮实质工作维护。已直接核对原PDF第9–11页与知识Gate；不改变原科学批准。额外E并非原V1.3预留集，外部验证已在原计划中；已有R1–R9参考候选调查，实际观测与许可/源链未验收。各自状态不能相互代替。

本轮合并回执HISTORICAL_EVIDENCE_RECOVERY.json记录来源、工作簿差异、计划溯源和指纹。Harness已完成一次限定独立审核，结论PASS，仅覆盖来源/状态分类、保存工作簿差异与计划书边界，不构成科学验收。审核快照6166字节、SHA256 1EBCD1F1DC5909F95C255EB6AADF0812AEB3D4BCFE0BD40936EAE1BC907AF290。另有4处说明文字调整的非阻断观察已在合并回执补记；PDF与tex保持审核版本。双方Git完成结果以提交后Shared/聊天回执为准，科学NOT_VERIFIED，研究者NOT_ASSESSED。

本轮归档/总计划主提交85203ff71209e05d771822692c557d133a5191a8已普通推送并核对远端一致。Harness审核提交d8c4069a506cb9427cf80029f1400445f60448a1仅含自身本轮审核记录，Codex已只读核对其本地树干净及远端同SHA。研究者本人完成一次性执行许可，Codex未代点。工程闭环PASS仅限本轮证据/状态/文档与各自记录同步，科学NOT_VERIFIED，研究者NOT_ASSESSED。

本次仅对合并回执和本索引补记提交后事实，计划书PDF/tex及历史恢复文本保持已审版本。闭环提交最终SHA与Shared完整终值指纹由聊天及交接回执引用，不通过自身指纹自引用，也不冒称Harness预先审核过本条新字节。

## Stage 4.5元数据准备（2026-11-06后续进展）

已取得NOAA站点身份与2023/2024 DPR候选颗粒元数据；独立观测验证仍NOT_VERIFIED。发现框命中不等于省内配对或事件数。见 [实际元数据收据](../20261106_external_reference_metadata/METADATA_FEASIBILITY.json) 和 LIVE-20261106.2 总计划；不改变本页历史审核结论。

Harness已完成一次限定公开元数据审核并给出PASS；记录5852B，SHA256 `8BBF616509903CEECE4A93E403BCAB9C3054ABFF80EC65452C708E5AF5F9F108`，审核分支提交 `8a2af59158a269ea2ef0db53c93babe2be02f36e` 已独立核对远端。此PASS不构成Stage4.5完成、观测验证、数据/实验批准或研究者掌握。获取收据创建时的待审状态由 [结项回执](../20261106_external_reference_metadata/REVIEW_OUTCOME.json) 解释；元数据原记录不改写。

## CMA产品身份继续核实（2026-11-06）

当前公开三小时/近7日站点产品、109条云南身份附件与近24h雷达24小时估测图像不能替代目标历史小时观测。详见 [产品身份收据](../20261106_cma_hourly_radar_metadata/CMA_PRODUCT_IDENTITY.json) 及LIVE-20261106.3。新的限定审核待完成；旧审核结论保持各自范围。


Harness已对修正提交3efb20a完成一次限定独立审核，结论PASS；正式记录5437B，SHA256 `365C2499073346A4D6C1C9EFFB7D1EFED0B844B8079B24030BAC1A33C06CABB0`，自身提交 `976b1816d48dfeb0dcf617cd9e3b7e2543f7bf2c` 已普通推送且由Codex独立核对远端一致。22/22保存证据指纹、109站号/51+53+5及产品语义通过；该审核未重做网络获取或逐页像素视觉检查。S011独立身份主要在计划文本，JSON当前产品数组仅全国/云南两项，作为非阻断观察登记。原失败7831641及三文件修正3efb20a完整保留，未改写为旧版本通过。

结项见 [本轮回执](../20261106_cma_hourly_radar_metadata/REVIEW_OUTCOME.json)。工程PASS仅限本轮公开元数据/文档、独立审核和各自分支同步；Stage4.5 PARTIAL，科学NOT_VERIFIED，研究者NOT_ASSESSED。小时档案、QC、源链和项目许可仍缺，P0/P1为METADATA_INSUFFICIENT；预算NOT_ESTIMABLE，观测获取及实验NOT_AUTHORIZED。计划PDF/tex保持已审LIVE-20261106.3，不为结项补记另增版本；本次仅回执与本索引事实补记，未声称Harness预审过新增字节。


## IMERG参考路线与证据边界（2026-11-06）

研究者报告无已落实的外部资料，提出无可落实公开替代来源时采用IMERG参考。总控0314e4a3据此限定LIVE-20261106.4文档修订、一次差异审核和各自Git同步；研究者回复及本轮维护不产生科研执行批准。既有冻结产品IMERG_V07_Final保持，参考一致性、外部真实性、确认性E及物理/业务主张分开。详见 [本轮记录](../20261106_imerg_reference_scope/REFERENCE_SCOPE.json)。原元数据核查与审核保持各自历史范围，不重复泛搜或理论审查。新差异审查待完成，Stage4.5 PARTIAL，科学NOT_VERIFIED，研究者NOT_ASSESSED。


Harness已对66a2a13的八文件差异完成一次限定独立审核，结论PASS；正式记录5372B，SHA256 `C3CD9114773F7EEA4FD64A396C04EA62100385E816B543F15C4899CB6F9F95FF`，审核者自身分支提交 `8cdd0d4d2e357c0944211370364d3f468ee03ba9` 已普通推送，Codex独立ls-remote核对一致、提交仅审核文件且树干净。审核未逐字重算历史前后缀或逐页像素检查，未把保护快照升级为OS监控。

[结项回执](../20261106_imerg_reference_scope/REVIEW_OUTCOME.json)登记此后事实，原记录中的待审状态按创建时点阅读；计划PDF/tex和两份原收据保持已审字节，不为闭环另增版本。本次仅回执与本索引补记，不声称新增字节已被预审。工程PASS限本轮文档/边界/审核/各自Git，Stage4.5 PARTIAL、H1/H2 INCONCLUSIVE、科学NOT_VERIFIED、研究者NOT_ASSESSED。按冻结IMERG参考整理既有成果，外部资料缺口不阻塞所有整理工作；没有新载荷、计算、训练或2025权限。


## 内部结果/讨论/局限初稿（2026-11-06）

按总控d88c7bbc，本轮把既有保存结果转成唯一内部INTERNAL-DRAFT-20261106.1，保留两份旧分析/验收报告，不另起完整投稿终稿。包含10项逐主张证据映射、12份来源指纹与字段、14个直接数值排版绑定；其他历史报告数字按章节标注。正文保留B3/B4三seed、真实DOTE/ZERO三seed、B7/B8混合方向、V3强雨排序/点估计/尾部反例及补充单seed，科学NOT_VERIFIED、研究者NOT_ASSESSED。见 [主张索引](../20261106_internal_paper_draft/CLAIM_EVIDENCE.json)；计划更新LIVE-20261106.5。限定内容审核待完成，不重算指标/推理/训练、不新增数据图、不访问2025。


Harness已完成内部初稿的一次限定内容审核，结论PASS（两处非阻断措辞建议）；记录6107B，SHA256 `B53D13243B4A71984342EFB21D97EBA928C3D6A3B63A58D503091F8E137EA3B2`。其本人仅提交审核文件到 `61f560963cddac430dbb4ce1b4db4c8cc0d3cb95`，普通推送且由Codex独立ls-remote核对一致，树干净。12来源、10主张、7聚合块、14数值绑定及关键反例核对通过；不是底层载荷重算或逐页像素审查。

非阻断编辑事项已记入 [结项回执](../20261106_internal_paper_draft/REVIEW_OUTCOME.json)：C2应读为“B5除AUROC外四项不利”；2.9节AUROC/AP应明确是发生降水R>0.1目标，非强雨R>20排序。正文与源值的实际方向未变，保留本轮已审PDF/tex字节，留待下一编辑修订；不声称建议已改进文件。

工程PASS仅本轮内部写作、来源/边界审核及各自Git；科学NOT_VERIFIED、H1/H2 INCONCLUSIVE、研究者NOT_ASSESSED、Stage4.5 PARTIAL。初稿不是投稿终稿，未选择最终模型、未新增指标或2025权限。初始标记调用重复的规范偏差与排版失败真实保留；ChatGPT浏览器观察被自动审批拒绝后仅用授权API。原收据按创建时点阅读，本次仅结项回执与索引补记，不冒称新增闭环字节预先获审。


## CORE-PREP-20261106.1：原目标核心缺口工程准备

研究者报告外部观测验证当前无法完成，其余原目标继续。总控d813781b仅接受隔离工程范围。3辅助代理分别实现多尺度接口、DOTE控制与元数据对齐，交叉审查修复batch/有序容器契约，并明确窗口关系未核验。人工合成CPU最终43项通过；旧回归收集缺yaml未执行，历史失败保留。

工作包、讨论、测试及保留检查见 ../20261106_core_completion_prepare/。LIVE.6为14页更新版，原LIVE.5和初稿保留。当前Harness及Git最终状态待同轮REVIEW_OUTCOME补记；科学NOT_VERIFIED，外部Stage4.5 PARTIAL，研究者NOT_ASSESSED。无真实载荷、模型执行或2025访问。


### CORE-PREP限定审核与同步最终回执

Harness独立静态+43项合成CPU审核PASS，首审7073B/59701143；JSON换行纠正后追加格式核验PASS，最终8478B/0E6FB0EB，首审前缀保留。Codex首审后暂存检查拦截CRLF，提交前停止；仅四JSON规范化LF，三业务JSON解析不变、VERIFICATION仅三项指纹更新，代码/测试/PDF不变。失败日志保留，没有绕过检查。

Codex主体15文件36d6fe1e39da49e05566d442fe51d262d6db230a、Harness格式补充1c2539ca8455d37ad8eed1c4cd04fd6312a86bb6均已普通推送，Codex直接ls-remote核对一致。最终REVIEW_OUTCOME解释创建时PENDING字段，不改历史记录；此回执和本索引追加并未冒称提前通过Harness审核。

工程PASS限定候选/合成检查/审核/主体同步，科学NOT_VERIFIED，外部PARTIAL，掌握NOT_ASSESSED。正式模型/真实映射/训练/新评价/2025没有新增执行；下一步仅可准备单独的精确科学方案和预算。


## DOTE-DIRECTION-FREEZE-CANDIDATE-20261106.1 / LIVE.7

按总控6115f59a只读源码和已保存元数据推进方向控制冻结候选：绑定8个旧E9身份、确认B6评价JSON与权重指纹对象类型、限制ZERO的128零梯度权重解释，明确DOTE内部风干预点和scene lookup缺口。候选随机旋转/朝东定义、科学门槛、正式接入及预算都仍待批准，execution=false。

SOURCE_BINDINGS/DOTE_FREEZE_CANDIDATE及VERIFICATION见 ../20261106_dote_direction_freeze/。LIVE.7为16页更新版；LIVE.6及既有代码/43测试保留，本阶段没有模型/梯度/新科学计算。工程等待限定方案审核与Git闭环，科学NOT_VERIFIED、外部PARTIAL、知识NOT_ASSESSED。


### DOTE方向候选限定审核与同步回执

Harness已完成14份来源指纹、8个历史E9端点字段及非执行设计的限定审核，结论PASS；正式记录6159B，SHA256 `354DA56B65DD3F34F241F8054492369E866B139487E6D3B526B3C0698888BDEA`。审核者自身提交 `b5b47c3b2dc8241df533b61e7a954ac73d678fd6` 已普通推送，Codex直接ls-remote核对一致，DSH树干净。本阶段未运行模型/梯度/测试，也未把权重元数据核对冒充权重载荷复算或PDF逐页独立视觉复核。

Codex主体8文件 `e50a93ccc8e189468b69f23e7e90a3a545a5f65f` 已普通推送并直接核对远端。详见 [结项回执](../20261106_dote_direction_freeze/REVIEW_OUTCOME.json)。非阻断路径表达已在回执中明确：SOURCE_BINDINGS的actually_matches是说明性定位，真实扁平键为B6/development_09.json，机器JSON Pointer须用 `/sources/B6~1development_09.json/sha256`；精确键查询直接验证，已审来源不改写。

LIVE.7及已审来源/候选/VERIFICATION保持原字节。当前候选仍PROPOSED且executable=false，主指标/效应/退化/推断规则、场景映射/正式wrapper、执行commit/允许路径/预算/研究者实验批准均未落实。工程PASS只限本轮准备/审核/主体同步；科学NOT_VERIFIED，外部Stage4.5 PARTIAL，研究者NOT_ASSESSED。原创建时PENDING状态由本回执解释，不覆盖历史记录；此次回执及索引追加未冒称已提前获得审核。
