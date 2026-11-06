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
