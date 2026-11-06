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

# YunTAPR-Net

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

> 最新状态（2026-10-29）：ZERO_DOTE/2030、2031完整九轮Train/2024 Dev及固定E9已核验，合计8640更新、零重放/额外重试，未超预算。连同2029完成真实B7−零控制三seed：Brier改善3/3，AUROC/AP仅1/3，20–50强雨收益未复现、q32误差退化2/3。限定验收COMPLETE_WITH_LIMITATIONS，2025冻结。[完成/配对证据](docs/research_readiness/20261025/evidence/dote_control_three_seed_completion_20261029.json) · [全部科学分析](SCIENTIFIC_ANALYSIS.md)。

统一科研交付入口：[阶段验收](STAGE_ACCEPTANCE.md) · [实验矩阵](EXPERIMENT_MATRIX.csv) · [原始指标与配对差值](METRICS.csv) · [科学分析](SCIENTIFIC_ANALYSIS.md) · [证据索引](EVIDENCE_INDEX.md)。以各文件明确的快照时间为准；历史报告和收据保持原状。

> 最新科研状态（2026-10-27）：B5/B6 seed2029各九轮Train/2024 Dev及固定E9配对已核验完成；首轮地形消融为COMPLETE_WITH_LIMITATIONS，收益混合，q32欠覆盖加重。见[完整新收据](docs/research_readiness/20261025/evidence/b5_b6_completion_and_paired_evidence.json)和[统一科学分析](SCIENTIFIC_ANALYSIS.md)。B0–B4限定基线不变；2025与B7/B8继续冻结，无追加训练。

The current authoritative [Scientific Freeze v1.1](docs/scientific_freeze/YUNTAPR_SCIENTIFIC_FREEZE_v1.1.md) and [machine-readable contract](config/science_contract_v1.1.yaml) supersede v1 **only for explicitly updated QC / normalization / quantile numerical implementation / engineering staging rules**. D1–D7 otherwise inherit [historical v1](docs/scientific_freeze/YUNTAPR_SCIENTIFIC_FREEZE_v1.md) unchanged. Formal supervised B0 requires a full-valid B13 expected latest slot, prohibits older-frame fallback, and applies Decision 8 Train-only Z-score. The versioned [SP04 coordinate/index artifacts](config/spatial/sp04_coordinate_manifest_v1.json) remain unchanged. **B0_FORMAL_SCIENTIFIC_CONTRACT=FROZEN; B0_FORMAL_SKELETON_IMPLEMENTED=true; B0_FORMAL_TRAINING_STARTED=false; FORMAL_TRAINING_AUTHORIZED=false.**

The runnable [B0 package](src/yuntapr) uses pinned [engineering configuration v4](config/b0_engineering_v4.yaml); v3 and its evidence remain available. With the fixed project Python `F:\pytorch\Research\.venv\Scripts\python.exe`, set `PYTHONPATH=src` and run `python -m unittest discover -s tests/quantile_numerical_closure -p 'test_*.py' -v` (the [numerical closure report](docs/quantile_numerical_closure/runs/run_20260930T110155Z/QUANTILE_NUMERICAL_CLOSURE_REPORT.md) records all five test suites). Runtime order for the formal-rule path is raw Kelvin → QC → eligibility → pinned normalization → backbone → frozen SP04 → probability heads. Execution remains **ENGINEERING_ONLY**. Focal alpha/gamma remain unestimated; the formal-B0 partial/support choice is resolved by requiring the whole native frame valid. No model fit or formal checkpoint is provided.

The [v1.1 freeze report](docs/scientific_freeze/runs/run_20260930T095416Z_v1_1/SCIENTIFIC_FREEZE_V1_1_REPORT.md) and [B0 pretraining closure report](docs/b0_pretraining_closure/runs/run_20260930T095416Z/B0_PRETRAINING_CLOSURE_REPORT.md) record 11,720 eligible 2023 Train scenes and 11,727 eligible 2024 Validation scenes. Exact final-eligible 2023 statistics are μ=271.7078191073734 K and σ=19.896814653342556 K (population std); 2024 reuses them. Their historical float32 stress conclusion remains preserved: the mixed extreme case lost strict ordering with epsilon=1e-4. The later [v4 engineering numerical closure](docs/quantile_numerical_closure/runs/run_20260930T110155Z/QUANTILE_NUMERICAL_CLOSURE_REPORT.md) uses float64 inside the unchanged softplus/epsilon recurrence, keeps qlog/physical quantiles and conditional pinball in float64, and passes all 14 specified qlog stresses plus 2023/2024 real regressions. Physical overflow raises a separate explicit error. **QUANTILE_NUMERICAL_STABILITY_CLOSED=true for the specified closure gate; B0_FORMAL_TRAINING_STARTED=false; FORMAL_TRAINING_AUTHORIZED=false.**

The [B0 training environment and memory feasibility audit](docs/training_environment_audit/runs/run_20260930T114738Z/TRAINING_ENVIRONMENT_AUDIT_REPORT.md) measures full-shape CPU forward/loss/backward, model parameter and process memory, and 8 real final-eligible 2023 samples through the bounded English staging path with 0/2/4 DataLoader workers. NVIDIA inventory finds a GPU, but the fixed Python currently has CPU-only PyTorch, so CUDA batch, AMP, validation memory, and safe GPU batch remain unmeasured. All throughput, gradient-accumulation, checkpoint, and configuration figures in that run are engineering estimates or candidates only; **TRAINING_ENVIRONMENT_READY=false**, and no formal training or checkpoint was started. The versioned run contains code hashes, per-file evidence, and full test output.

After H: became available, the [2024-07-01 real-sample engineering verification](docs/b0_real_sample_verification/runs/run_20260930T060021Z/REAL_B0_SAMPLE_VERIFICATION_REPORT.md) exercised H: Himawari B13 → converted V07 Final IMERG → frozen Yunnan mask → B0 forward and masked-loss finiteness. It is an offline engineering check, with no formal B0 training or historical operational-availability claim. Its first attempt exposed a float32 monotonicity failure under v1 input-skip initialization; v2 explicitly zero-initializes that trainable projection skip and the successful rerun is recorded separately. The prior skeleton run was not changed.

The [2023–2024 Development Data/QC closure audit](docs/development_qc/runs/run_20260930T075627Z/DEVELOPMENT_DATA_QC_REPORT.md) inventories all March–October B13 slots, audits IMERG V07 Final coverage and explicit causal fallback, compares unfrozen partial-QC candidates at supervised-window grain, and records 2023-only normalization evidence, float32 quantile stress, and two real backward smoke samples. Coverage is **PARTIAL** because some B13 slots are absent. The [audit README](docs/development_qc/README.md) explains the reproducible run and local-only large evidence. Formal training remains unauthorized.

For netCDF4 files under Chinese paths, set `YUNTAPR_B0_STAGING_ROOT` to an explicitly chosen ASCII directory (the previously approved `F:\pytorch\Research\stage0_himawari\cache\staging` is suitable). `configured_staging()` creates one bounded, SHA256-verified temporary English copy at a time; `StagedB13Reader` and `StagedIMERGReader` inject into `B0Dataset`. The frozen private mask must be passed through `read_frozen_yunnan_mask` and supplied with its SHA-verified path. The public repository contains neither the mask payload nor raw satellite or precipitation data. `B0Dataset` accepts an arbitrary mask only when explicitly marked as an engineering fixture, and requires upstream-verified V07 Final provenance before supervised eligibility.

The Stage-0, engineering smoke, and formal-readiness reports below remain immutable historical evidence. Their `NOT_YET_FROZEN` or `RESEARCHER_DECISION_REQUIRED` statements about a rule now explicitly frozen in Scientific Freeze v1 are superseded by that later researcher approval. Earlier observations and unresolved data-availability findings remain historical facts. Do not use 2025 Test results to revise the frozen protocol.

The [Stage-0 and B0 engineering evidence snapshot](stage0-b0-evidence/README.md) contains source code, audit reports, test records, and SHA256 manifests from the current research workflow.

The historical [formal-readiness report](stage0-b0-evidence/evidence/outputs/stage1_b0_formal_readiness_resolution/run_20260928T124313_169375Z/FINAL_B0_FORMAL_READINESS_REPORT.md) recorded **B0_FORMAL_NOT_READY** at that run: the engineering smoke passed, 30 formal-readiness checks passed, and 12 formal-entry items still required resolution. Its data-gap evidence remains relevant; the later Scientific Freeze v1 resolves the listed scientific choices without rewriting that report. No formal B0 training was started.

The new [B0 spatial and probability contract resolution](stage0-b0-evidence/evidence/outputs/b0_spatial_probability_contract_resolution/run_20260928T144303_935304Z/FINAL_B0_SPATIAL_PROBABILITY_CONTRACT_REPORT.md) records actual-coordinate SP04 geometry, five spatial-alignment candidates, probability-output and loss candidates, 40 passing focused tests, and the remaining researcher decisions. It does not start formal training or freeze a projection, τ grid, or loss hyperparameter.

This public repository excludes source satellite/precipitation values, storage benchmark arrays, and restricted boundary/mask payloads. Scientific Freeze v1 adds only coordinate-axis metadata and an explicit index map required to execute the frozen spatial rule. The snapshot README and manifests identify other included files and local artifacts excluded from public distribution.


## 2026-10-24 completed-work review and seed2027 completion

This review branch preserves the [2026-10-21 audit](docs/audits/20261021_completed_work_review/AUDIT_REPORT.md) and the subsequent [seed2027 completion evidence](docs/phase_b_v2_seed2027_completion/20261024/README.md). All six registered runs completed nine epochs (54 committed LAST receipts); the final completion receipt was issued at 2026-10-23 23:20:40 Asia/Shanghai. The source and result provenance, exact-byte manifest, inherited regression evidence, and explicit remaining limitations are linked in that completion record.

The results are exploratory 2024-development evidence. This branch does not authorize seed2028, FinalFit, or 2025 final-test evaluation. Recovery launchers under research_snapshots are archival source snapshots tied to their original isolated workspaces, not a runnable deployment. Historical failures and the one unresolved historical attempt remain preserved.
