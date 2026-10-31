# 统一证据索引

2026-10-31最新展示入口：[31条实际配置的阶段增量表](outputs/01a17251-29bb-7172-89f8-380b42c4d290/YunTAPR-Net_V1.3_逐阶段逐seed全方案对比_20261031.xlsx)及[脱敏交付核验](docs/research_readiness/20261025/evidence/compact_stage_comparison_delivery_20261031.json)。文件SHA256 `8cd976aa6e458e6f55b17dada9e7546a945260eeede39038341c6cacb142af86`；1工作表/1表、31配置、40列，20条有效配对和120个已核对缓存公式。E0/E1/E2全部实际结果保留；19条已有点估计、12条未补算明确区分。表下附模型解释及配对统计，来源ID和E9 SHA逐行绑定。旧完整明细SHA `b77469a441e36feeb55b5fea282ae5bcc0760481e5c7b3209a8d1d587151b4b4`未改变。未重新读取权重、推理或访问原始气象/2025。以下既有收据和历史状态保留。

2026-10-31本轮交付完成：19/19项获批固定E9指标补算及B7_PERP_GRADIENT/2029九轮Train/Dev均已封口；一份Excel仅含“完整指标”一个工作表、一张4718行×42列的大表，覆盖31条模型/seed/损失臂记录、全部可得分组、992条分位覆盖记录及配对/seed均值与样本标准差。B0–B9和两类控制说明位于表下方，B9明确未启动。导出文件结构、数字类型、分类分母、配对源值、单seed无伪造SD、公式缓存/重算、左右/底部版面及脱敏检查通过。原19项范围外的B0/B1 E1/E2、ZERO及探针点估计缺口明确n.a.，没有追加推理或补零。该交付是获批范围与现存证据的完整版本，不代表所有方法均已计算或独立年份科学验收通过。原失败、480重放及旧时间NOT_VERIFIED全部保留，2025继续冻结。 [完整单表](outputs/01a17251-29bb-7172-89f8-380b42c4d290/YunTAPR-Net_V1.3_完整指标与消融对照_20261031.xlsx) · [交付核验](docs/research_readiness/20261025/evidence/complete_metric_workbook_delivery_20261031.json)。下方进行中/停止条目是历史记录。

2026-10-31终态核验：B7_PERP_GRADIENT seed2029已完成固定E9及九轮2024 Dev。继承E1–E5，新E6–E9四轮全部Train/Dev、8天气账本、1静态与1失败源校验均封口；恢复1920更新含480必要重放，新源212,259,080,749字节/63,474次，新段6364.619秒，小于10800秒。有效更新4320，累计尝试4800；累计交付509,171,050,013字节、预约509,175,755,262字节/152,398次，旧失败、不确定源与旧时间验收NOT_VERIFIED不清零。实际E9 SHA5406e20e241a3697b867ba4f44519397c2943b2381bc047d938c4eb141ce34e6已单次复核。19项指标补算完整保留，未新推理或读取2025。训练/评价为COMPLETE_TRAIN_AND_DEV_EVALUATION；科学结论仅COMPLETE_WITH_LIMITATIONS，真实B7相对探针总体Brier/AP较好、AUROC/Pinball/q32绝对误差较差，20–50强雨Pinball退化。最终单张大表正在完成导出核对。 [终态证据](docs/research_readiness/20261025/evidence/dote_physical_control_completion_20261030.json)。以下运行/停止/待批准条目保留为历史时点。

2026-10-31恢复已获准确批准并单次启动：研究者对完整限额申请回复“好”，7d4970d/ebd2391e已在独立WMI固定副本运行。出错2024源一次4,705,249字节完整SHA校验通过，E5模型/AdamW/学习率及RNG恢复成功，本次快照新增157次RETURNED（有效训练位置2557，累计尝试3037，本段已重放157）；E1–E5继承，E6–E9进行中，尚无E9，不算训练完成。只读页面已切换并分列有效位置、本段和累计尝试，原480未保存及旧失败保留；19项指标不重算。仍限新增1920更新含480重放、212259080749字节/63474次、3小时/24GiB，额外重试及额外重放0，批准已消费不得重复启动。按批准每30分钟最多8次/4小时静默跟进，已取消的资源保护不恢复。2025冻结，最终单大表等待E9封口。 见[真实批准及恢复启动收据](docs/research_readiness/20261025/evidence/dote_physical_recovery_started_20261031.json)。下方失败/待批准描述为历史时点。

2026-10-31恢复准备已完成，正式恢复仍未启动：唯一候选B7_PERP_GRADIENT seed2029从真实E5/2400检查点恢复E6–E9；新增1920次更新，其中480次必要重放，累计4800次尝试仍为同一seed。新增源读取上限212,259,080,749字节/63,474次（四轮训练/Dev 212,254,062,672字节/63,472次，另加失败源一次4,705,249字节校验及静态312,828字节一次读取）；新段限时3小时，至少24GiB，额外重试及额外重放0。代码7d4970d，规范化提案SHA ebd2391e0d6e95b1aa0a573df21416822f5173e1a6a11a8eafd6b74679e1f0d6。8项新增CPU检查通过，实际E5 SHA验证通过；失败源元数据/打开检查通过，0气象载荷读取、0优化器更新。系统Event1确认00:05:44Z低功耗恢复，紧接读取异常，但I/O因果仍未核实；新入口按UTC挂钟和单调时钟中较早截止值保护，旧超时验收不追认。19项指标不重算、旧失败/480未保存更新完整保留。原零重放批准已消费，须一次明确批准该恢复提案及新增资源后才运行；2025冻结。 见[唯一限额恢复提案](docs/research_readiness/20261025/evidence/dote_physical_recovery_proposal_20261031.json)。

2026-10-31终态：B7_PERP_GRADIENT/2029在E6 Dev的Himawari实际内容读取抛出OSError [Errno22] Invalid argument，按失败即停退出，未自动重试。已执行2880更新、6轮Train/5轮Dev，最新完整检查点E5/2400（原收据SHA9330e71c…），480次更新未保存，E9不存在。实际记录交付296,911,969,264逻辑字节、保留296,916,674,513字节预约/88,924实例，含1份4,705,249字节PARTIAL_UNCERTAIN源；不能将其物理读取当作零。启动至退出挂钟跨度约10小时22分44秒，超过6小时批准值；活动GPU时长和休眠/时钟原因未核实，时间预算不能宣称验收通过。底层源/存储故障未确定，不等同此前WinError121。19/19指标结果完整保留不重算；最终完整单表因候选E9缺失而BLOCKED，不用E5代替E9，不形成新的公平性能结论。原批准已消费，任何恢复和至少480次必要重放须新的限额批准，本轮未启动恢复。2025继续冻结。 见[真实失败与保留账本](docs/research_readiness/20261025/evidence/dote_physical_control_failure_20261031.json)。下方运行快照为历史时点。

2026-10-30最新核对：19/19份固定E9指标补算已完成，冻结概率指标与整数计数gate全部通过；四项修正实际读取389,975,899,096字节/88,692内容实例、0优化器更新，用时4441.9秒，继承15项。原自动衔接在模型加载前因跨副本相对配置路径找不到文件而退出，0训练更新/0气象读取，历史失败保留。配置改为绝对路径后，原9b4046a/0444d92e已于北京时间21:43:11由独立WMI完成首次正式启动，当前B7_PERP_GRADIENT/2029为IN_PROGRESS（本次快照68次RETURNED），尚无E9，不算训练完成。原4320更新/477571953840字节/142813次/6小时/24GiB、零重放/额外训练重试额度不变；2025冻结。最终一工作表一大表等待该候选封口，未导出冒充完整。 见[指标完成与首次训练启动收据](docs/research_readiness/20261025/evidence/metric_completion_candidate_started_20261030.json)。下方排队、待批准与早期进度为历史时点。

出版基线commit：`9b4046a655e2ec91633104eaa64bd507cca81aad`。本五文件的版本由所属Git提交标识，不伪造自引用commit。实际模型代码独立绑定如下。研究者为主体，AI辅助摘录；公开SHA约束原件身份，不等于外部已独立复现未公开数据。

## 当前训练状态快照

此嵌入快照仅记录既有B5/B6收口时点，供继承和确定性重建；B7/B8最新终态见下方独立收据。状态时点是UTC（北京时间加8小时），不是页面实时值。B5/B6均COMPLETE_TRAIN_AND_DEV_EVALUATION，18轮完整收据、账本及实际E9文件SHA沿用既有收口，不从checkpoint存在或部分轮次判完成。

<!-- STATUS_SNAPSHOT -->
```json
{
  "state": "COMPLETE",
  "snapshot_utc": "2026-10-27T07:30:47.980516+00:00",
  "source_commit": "b251fd9ea06c0c90f48d2ac0decba0454114669d",
  "returned": 8640,
  "sealed_epochs": 18,
  "completed_models": 2,
  "runs": [
    {
      "model": "B5",
      "seed": 2029,
      "state": "COMPLETE",
      "returned": 4320,
      "sealed_epochs": 9
    },
    {
      "model": "B6",
      "seed": 2029,
      "state": "COMPLETE",
      "returned": 4320,
      "sealed_epochs": 9
    }
  ]
}
```

## 训练日志与本地原件定位

公开脱敏ID与原件的映射沿用既有索引；不公开私人绝对路径、原始数据、权重或未脱敏账本。

|范围|训练日志/逐轮收据|模型、评价与本地原件身份|
|---|---|---|
|B0/B1，2026/2027及历史失败|[原实验摘录](docs/research_progress/evidence/experiments.json)、[逐轮日志索引](docs/research_progress/evidence/epoch_receipts.json)、[历史campaign](docs/research_progress/evidence/historical_campaigns.json)|[原件source_id、bytes、SHA及可公开URL](docs/research_progress/evidence/source_manifest.json)；每实验source_ids连接原结果，矩阵保留历史执行commit NOT_VERIFIED|
|B2/2029|[完成证据](docs/research_readiness/20261025/evidence/b2_completion_and_paired_evidence.json)的epochs、checkpoint_metadata、ledger、actual_io|sources中B2_COMPLETION、B2_DEV_E*、B2_IO_*等脱敏ID/字节SHA；全部9轮原始JSON/SQLite/权重LOCAL_ONLY；E9文件曾实际重哈希|
|B3/B4，2029|[保留执行收据](docs/research_progress/evidence/seed2029_execution.json)、[原件清单](docs/research_progress/evidence/source_manifest.json)|[总体及分组指标](docs/research_progress/evidence/seed2029_groups.json)、[三seed完成收据](docs/research_readiness/20261025/evidence/b3_b4_three_seed_completion.json)的s2029/B3或B4/development_09.json字节SHA；继承既有权重核验|
|B3/B4，2030/2031|[原中止事实](docs/research_readiness/20261025/evidence/b3_b4_multiseed_stop.json)、[三seed收口](docs/research_readiness/20261025/evidence/b3_b4_three_seed_completion.json)的epochs/tasks/budget_closure|sources中s2030/s2031/{model}/development_09.json、训练日志、LAST receipt、updates.sqlite、读取账本分别有SHA；每个epoch/模型/seed定位，不把恢复段计为新seed|
|2030/2031完整终点字段|[本轮4份既有E9数值摘录](docs/research_readiness/20261025/evidence/b3_b4_full_endpoint_metrics_20261027.json)|groups包含六评价分组的完整summary，sources字节SHA与既有三seed收口一致；仅补足数值出版，不重新推理或读取原始气象|
|B5/B6，2029|[一次纠正启动](docs/research_readiness/20261025/evidence/b5_b6_corrected_start_launch.json)、[原失败](docs/research_readiness/20261025/evidence/b5_b6_initial_start_stop.json)|[冻结纠正提案](docs/research_readiness/20261025/evidence/b5_b6_corrected_start_proposal.json)、[地形源/网格/静态包SHA](docs/research_readiness/20261025/evidence/b5_b6_terrain_production.json)；E9及18轮完整收据见下一行|
|B5/B6本轮完整收口|[18轮、36读取账本、2静态账本及E9](docs/research_readiness/20261025/evidence/b5_b6_completion_and_paired_evidence.json)|sources中B5或B6/train、development、tail、LAST receipt、reads.sqlite、updates.sqlite均有字节SHA；完整endpoint_groups和epochs仅公开脱敏统计，原件及权重LOCAL_ONLY|
|B7/B8历史准备时点|[科学协议](docs/research_readiness/20261025/B7_B8_INNOVATION_PROTOCOL.md)、[精确提案](docs/research_readiness/20261025/evidence/b7_b8_training_proposal.json)、[真实零更新](docs/research_readiness/20261025/evidence/b7_b8_cached_real_check.json)|code/data SHA、3份新GFS原件身份及缓存纠正均已记录；准备时无正式批准或E9结果，实际新批准另列，不复用B6授权|
|B7/B8历史启动快照|[新批准、真实更新和资源入场](docs/research_readiness/20261025/evidence/b7_b8_approved_launch.json)|b1f072e/64e8单次启动；当时B7 RUNNING、B8 PENDING，固定E9尚无；不把该快照当当前状态|
|B7完成/B8停止的历史终态|[15轮、31气象账本、2静态账本与权重身份](docs/research_readiness/20261025/evidence/b7_b8_terminal_20261028.json)|B7固定E9完成，B8源路径WinError121停止；B8最新E6 SHA d4b20c3e486cdf89c763c642d36ef0527b36342f19a30883aefd1c9b1c774f24，E9缺失；不重试原始源或训练|
|B8恢复准备（未获批准）|[精确限额提案](docs/research_readiness/20261025/evidence/b8_recovery_proposal_20261028.json)、[一次有界源诊断](docs/research_readiness/20261025/evidence/b8_source_diagnostic_20261028.json)、[新增检查](docs/research_readiness/20261025/evidence/b8_recovery_checks_20261028.json)|当前路径/4KiB可读，历史故障原因未验证；E6恢复入口就绪，1440新更新含62重放待新批准，0次正式恢复|
|B8历史获批恢复启动|[明确批准与真实更新](docs/research_readiness/20261025/evidence/b8_recovery_approved_launch_20261028.json)|实际执行ef11531，E1–E6指标仍绑定b1f072e；本轮恢复IN_PROGRESS，E9未完成；前一行仅历史准备时点|
|B8恢复完成的最新收口|[三轮、六气象账本、静态账本与实际E9 SHA](docs/research_readiness/20261025/evidence/b8_recovery_completion_20261028.json)|B8九轮Train/Dev及固定E9已验证；4382实际尝试含62必要重放，旧E1–E6不复核；前面停止/启动状态为历史时点|
|B7/B8追加两seed准备时点|[唯一四模型提案](docs/research_readiness/20261025/evidence/b7_b8_multiseed_proposal_20261028.json)、[新初始化/顺序及检查](docs/research_readiness/20261025/evidence/b7_b8_multiseed_checks_20261028.json)、[0载荷源入场](docs/research_readiness/20261025/evidence/b7_b8_multiseed_source_admission_20261028.json)|执行代码56aae5b；准备时2030/2031四任务均NOT_STARTED；实际新批准/启动另列，不改写旧提案|
|B7/B8追加两seed最新获批启动|[新批准、24次RETURNED快照与资源入场](docs/research_readiness/20261025/evidence/b7_b8_multiseed_approved_launch_20261028.json)|整包IN_PROGRESS，B7/2030运行、其余三任务排队；零重放/额外重试，无新增E9或三seed结果；只读页面身份已核实|
|B7/B8追加两seed最新中断|[进程退出、部分账本、E6及页面修复](docs/research_readiness/20261025/evidence/b7_b8_multiseed_interruption_20261028.json)|上一行仅历史启动；当前B7/2030为3,321 RETURNED/E6保存2,880/441未保存，后三项未启动。无终态收据、原因未验证；原账本SHA不变，0新训练或重放|
|中断原因的后续追踪与工程修复|[宿主日志/事件SHA、研究者更新确认、Job探针与独立监督器](docs/research_readiness/20261025/evidence/b7_b8_multiseed_exit_cause_20261028.json)|高置信归因为更新期间宿主生命周期耦合；实际监督器/页面均已核验无Job/包身份。具体历史PID终止调用未捕获，旧初核收据不改写，未恢复训练|
|B7/2030恢复及后三任务准备|[唯一限额提案](docs/research_readiness/20261025/evidence/b7_b8_multiseed_recovery_proposal_20261028.json)、[10项针对性检查](docs/research_readiness/20261025/evidence/b7_b8_multiseed_recovery_checks_20261028.json)|拟执行e81c6e1，尚未执行；E6记录SHA仍84dbedbc2e0af537355aca71c6ad60c763a19821e7712fabb10aa45753399e11，正式恢复前重哈希/加载各1次；新14,400更新含441重放待新批准，原E1–E6及失败段保留|
|当前准确限额恢复已批准并启动|[新研究者批准、实际RETURNED与四角色无Job/包身份](docs/research_readiness/20261025/evidence/b7_b8_multiseed_recovery_approved_launch_20261028.json)|e81c6e1/3314231a已单次启动；上一行只记录历史准备。B7/2030恢复IN_PROGRESS，后三项PENDING，旧E1–E6和441未保存历史不变，没有新E9或三seed结果|
|最新B7/B8三seed全部完成|[新增30轮、64读取账本、四份E9实际SHA及三seed原值/差值](docs/research_readiness/20261025/evidence/b7_b8_three_seed_completion_20261029.json)|前述中断/排队是历史时点；新增四任务已九轮完成，新段14400更新含441必要重放，三seed分析完成但收益混合，带局限验收；2025冻结|
|本轮科学归因与论文级验收|[主张矩阵及2025预注册草案](docs/research_readiness/20261025/evidence/paper_acceptance_20261029.json)、[27终点离线诊断](docs/research_readiness/20261025/evidence/scientific_attribution_diagnostics_20261029.json)、[精确经验Brier分解](docs/research_readiness/20261025/evidence/brier_exact_score_decomposition_20261029.json)、[7项检查与真实初值](docs/research_readiness/20261025/evidence/dote_control_checks_20261029.json)|从a2ffa75已保存统计计算；35周块不等于独立天气事件，未新增训练或2025访问；零数值控制NOT_STARTED。可编辑[LaTeX](docs/research_readiness/20261029/paper_acceptance/main.tex)与[PDF](docs/research_readiness/20261029/paper_acceptance/YunTAPR_Scientific_Acceptance_20261029.pdf)|
|DOTE单模型获批启动（历史快照）|[明确批准、130实际更新、资源/独立宿主与页面身份](docs/research_readiness/20261025/evidence/dote_control_approved_launch_20261029.json)|仅记录09:22:01启动时点，IN_PROGRESS和0完整轮不是当前终态；固定0c91ff0/d7604c03，2025冻结|
|最新DOTE主对照已完成|[九轮Train/Dev、18气象/1静态账本、E9实际SHA及同人口对照](docs/research_readiness/20261025/evidence/dote_control_completion_20261029.json)|B7_ZERO_DOTE/2029为COMPLETE_TRAIN_AND_DEV_EVALUATION；4320更新、477571953840字节/142813次、零重放重试。原B7不重训，真实B7总体四指标更好但q32更差；单seed限定结论，2025冻结|
|DOTE控制2030/2031集中准备|[精确提案](docs/research_readiness/20261025/evidence/dote_control_multiseed_proposal_20261029.json)、[新入口/两seed初始化与梯度检查](docs/research_readiness/20261025/evidence/dote_control_multiseed_checks_20261029.json)|两控制NOT_STARTED，正式批准尚无；真实B7三seed和ZERO/2029均不重训，不预填E9或指标，2025冻结|
|最新DOTE两控制已批准并启动|[真实批准、89更新及独立宿主/页面身份](docs/research_readiness/20261025/evidence/dote_control_multiseed_approved_launch_20261029.json)|前一行仅为历史准备；固定8a46683/a53d3829已单次启动，2030 IN_PROGRESS、2031 PENDING；新E9及三seed控制结果尚无。批准已消费、零重放重试，无新周期自动化；2025冻结|
|最新DOTE三seed已完整收口|[新增18轮Train/18轮Dev、38读取账本、两份实际E9及完整三seed原值/差值](docs/research_readiness/20261025/evidence/dote_control_three_seed_completion_20261029.json)|前述待批准/运行状态均为历史；新两控制均COMPLETE_TRAIN_AND_DEV_EVALUATION。Brier改善3/3，AUROC/AP仅1/3，20–50未稳定改善、q32误差退化2/3；三seed带局限验收，不证明物理因果或最终泛化，2025冻结|

本地原件由研究者保存，公开源ID不是可下载原件的承诺。旧缺口保留：seed2027历史未核验尝试、旧恢复授权边界，以及未直接绑定的B0/B1历史执行commit。原始validation规范化digest、文件字节SHA和权重SHA互不替代。旧记录中的状态是当时快照，由此统一入口给出当前判断；原件未改写。

## 当前核心模型的固定E9身份

|模型|seed|固定E9权重SHA256|实际执行commit或分段|
|---|---|---|---|
|B3|2029|`c7780bc6e45992639c90339c88553fe3a722f6d9681bd247a82ad2dce0c08283`|`5b5298f41025db5b7b718fd736fc3fe6de516875_E1_3;7fa609e89bdb8b744bb0e7eebc9e7b5c3a703e35_E4_9`|
|B4|2029|`7c74eb80ab7d754e3262781d85ac370b2319c3bf27d37ac362860c104acfb34d`|`7fa609e89bdb8b744bb0e7eebc9e7b5c3a703e35`|
|B2|2029|`9d79a11f223473e8d06b873f2a4f46bb12ae44b9b9cddebe358f2901858657e0`|`a35302186b4b5d3d7ec735885a8d93762e6d3567`|
|B3|2030|`8e757e5a360a7780e32a87b6433174f25e2dd026b62a54c7d7450ee6e250f058`|`52a8e90dcea156382d7f2c510c5891c78e610329`|
|B4|2030|`7fb2c3714586634dfcee763d7eccdf4d746972044d7c0b9ac8827bca35db414c`|`943da957a3af846746c21b52d05a148bcb135064`|
|B3|2031|`bc096c45b9b1d8fcd1b22ed50231487cdb16d9653e77254fdfc7dcb79d513543`|`943da957a3af846746c21b52d05a148bcb135064`|
|B4|2031|`17cdf28b1b3032bbe1735f1203bd1cbf6993f78fb3d21e85f6b6a0cfef6fafea`|`943da957a3af846746c21b52d05a148bcb135064`|
|B5|2029|`1103d380519e96f64efd8ea577fc1fc514e8b20c52690e7f5a38b03d8d4a500f`|`b251fd9ea06c0c90f48d2ac0decba0454114669d`|
|B6|2029|`3b3ec78e22931f3c48184cd15bcbf75fb6303abe930aeb9fc2bdda61fdab1d98`|`b251fd9ea06c0c90f48d2ac0decba0454114669d`|
|B7|2029|`019a6dfabf2eef8eeb48bce993eaed64d86b78ea2da3e413e324f22f347f2e35`|`b1f072e45fdd17b80106a774083995c350b28f04`|
|B8|2029|`8abcf2082176bdbff54426649fe7a0125779873808e72e00197746f86a7f04f0`|`ef11531a7cdeb35b767caebdb61e0e81c6123187`|
|B7|2030|`820796601fa0d0be5c11125171116c7548483b0e3e5ac45c102e5ca5d6ffc15d`|`e81c6e1e0306e2a1e31103f1cc632be3c0d84d8c`|
|B8|2030|`f20d81858e8a61e78778da846b970e75914609f3ed05069bbebdcec459ff246e`|`e81c6e1e0306e2a1e31103f1cc632be3c0d84d8c`|
|B7|2031|`4537be7af702efd96d357a64099eb9c55f5cd9d2a4018677908e989c4a730fc7`|`e81c6e1e0306e2a1e31103f1cc632be3c0d84d8c`|
|B8|2031|`bc324e74209076613ae3ed9a2e20bab42e81456afd315728948ef5e2c5112f07`|`e81c6e1e0306e2a1e31103f1cc632be3c0d84d8c`|
|B7_ZERO_DOTE|2029|`445e4be5f49cba10057d90d16b82827b2c125964fd9bf4811d1e819fb3954a21`|`0c91ff0f36d5cce3f4516d38663482650f61b03a`|
|B7_ZERO_DOTE|2030|`b03ee41cd190dc7579a1fb993afb1f5598997fca91af3b1c2addc6eed430f0ba`|`8a4668377dbd40013245b54550c0963d10c286fb`|
|B7_ZERO_DOTE|2031|`f99952905157d8e649e567af671d0ee3ff02f11530a9996b80306ef758acdac0`|`8a4668377dbd40013245b54550c0963d10c286fb`|
|B7_PERP_GRADIENT|2029|`NOT_AVAILABLE_NO_TRAINING`|`NOT_EXECUTED`|

B4/2030矩阵终点commit为943da95，其E1继承52a8e90，E2–9由943da95执行；累计4,710实际尝试含390必要重放，有效轨迹4,320，成本见三seed收口。历史原始失败段仍保留。B5/B6本次纠正批准已消费，不允许额外重试。

## 数据与评价绑定

当前959/963人口SHA256：`2f2cc75cfb6c209fd8195d3419207216c5c3f2a4fc8315b40a1d77cc537dedb8`；populations文件SHA：`ea6abae6a493f2abdf19f938365407a35f0f0be71ba1346241264635318a32d2`；训练统计SHA：`53ab2f07aabb02e66ad237452447a35e0e2896278eae9d2da179336c06fea980`；target QC SHA：`b4bad8ea45a78eddae3832df89cfade00cac3b184fc550eea4f0cf479c29de90`。2023 Train / 2024 Development、四UTC、f006回顾估计；2025冻结。B13保持既有训练集scaler（mean=271.60515414265217 K，std=19.93959597783802 K，源身份656fe7a929cbd8617b08427e8d1fa7029b26512253efb44faa576796137d4a31），不声称它在当前959重新拟合。

核心评价脚本：[src/yuntapr/experimental/core_innovation/stage4/evaluation.py](src/yuntapr/experimental/core_innovation/stage4/evaluation.py)，执行版SHA256 `fd4cb37bb62675601cf685eb1d656f4fd8b88e2ba52d6019652114035908e9ce`；精确AUROC/AP及冻结float32阈值>0.1 mm/h口径继承[metrics.py](src/yuntapr/experimental/phase_b_v2_formal_integration_candidate/metrics.py)。Dev有效像元3,303,090、有雨407,820；不同人口和旧终点逐行保留。脚本链接指工作分支，重现执行身份必须同时使用矩阵中的执行commit及上述SHA。

## 本轮输入身份与交付校验

本轮ZERO三seed经验Brier分解、非零负对照Train特征诊断与受阻的整模缓存检查、非执行最终测试草案；原18轮两控制收口等历史有效证据均继承，不重复历史129来源/126轮审查；历史收据本身不被改为本轮重新核验。以下为直接采用的公开输入字节身份：

|公开输入|SHA256|
|---|---|
|[docs/research_readiness/20261025/B0_B4_EXPERIMENT_MATRIX.csv](docs/research_readiness/20261025/B0_B4_EXPERIMENT_MATRIX.csv)|`133ff673ab506a2d21385289072ac57fc263f8756282678b2ba74a0412a3a19e`|
|[docs/research_progress/evidence/experiments.json](docs/research_progress/evidence/experiments.json)|`828a10fa01b013a3d48416c86a599b0179d9252d2b91e0fe3a5dbf1287c4e119`|
|[docs/research_progress/evidence/seed2029_groups.json](docs/research_progress/evidence/seed2029_groups.json)|`4241b2a1148c921363737150a088f080a991b3e4553469fd5a05aea7cbc3852d`|
|[docs/research_readiness/20261025/evidence/b2_completion_and_paired_evidence.json](docs/research_readiness/20261025/evidence/b2_completion_and_paired_evidence.json)|`96738035c5e3f6b32ce4bf7e2a4f656313ea742ad53eb9ac38eb627f8dc8b3e1`|
|[docs/research_readiness/20261025/evidence/b3_b4_three_seed_completion.json](docs/research_readiness/20261025/evidence/b3_b4_three_seed_completion.json)|`e101ebd17b267d4fc0d93b53afe0ab432ce3e7a54f226f9058eac54237eecde4`|
|[docs/research_readiness/20261025/evidence/b3_b4_full_endpoint_metrics_20261027.json](docs/research_readiness/20261025/evidence/b3_b4_full_endpoint_metrics_20261027.json)|`8300a312b64f6cd2440cdf560bc07e3d5d0aa3d1d35cba33173963b75b1b1666`|
|[docs/research_progress/epoch_metrics.csv](docs/research_progress/epoch_metrics.csv)|`a79119bc5c2b37602949ec55c33171ae9f3d2093166688dfa3ad2c652abdf524`|
|[docs/research_readiness/20261025/evidence/b5_b6_corrected_start_launch.json](docs/research_readiness/20261025/evidence/b5_b6_corrected_start_launch.json)|`7c564f7c5349900c6fa1f5f2e814a8504612a8231d42f8b8008e0f0ba0bb29f4`|
|[docs/research_readiness/20261025/evidence/b5_b6_initial_start_stop.json](docs/research_readiness/20261025/evidence/b5_b6_initial_start_stop.json)|`e0dc6834aa7297293b4d5801741f86b449810feb9317936ae0feb179d932bc96`|
|[docs/research_readiness/20261025/evidence/b5_b6_terrain_production.json](docs/research_readiness/20261025/evidence/b5_b6_terrain_production.json)|`75204e2d8fd0eb37e9a13012fb7c74c523f23ffe436ec5b0446e8c4d134ead03`|
|[docs/research_readiness/20261025/evidence/b5_b6_completion_and_paired_evidence.json](docs/research_readiness/20261025/evidence/b5_b6_completion_and_paired_evidence.json)|`a2ca0b49ec59e16ce295f3f8533e10533aa9e2c44d2fe746838c1a381e8f5161`|
|[docs/research_readiness/20261025/evidence/b7_b8_training_proposal.json](docs/research_readiness/20261025/evidence/b7_b8_training_proposal.json)|`1e3eb1f34df503344984532d0f9cc5416373bf74504ff3368e6ab9c28c56bc0e`|
|[docs/research_readiness/20261025/evidence/b7_b8_physical_cache_preparation.json](docs/research_readiness/20261025/evidence/b7_b8_physical_cache_preparation.json)|`c8d2daef47c12badaf9f49cdfc7151169bc8938215eb53a124750e6c16b2b25b`|
|[docs/research_readiness/20261025/evidence/b7_b8_physical_cache_correction.json](docs/research_readiness/20261025/evidence/b7_b8_physical_cache_correction.json)|`e0bb6bfb6fb4e10d5ee5cfd18ff83d41860f6ec4895a49a0933a99d142b49d33`|
|[docs/research_readiness/20261025/evidence/b7_b8_cached_real_check.json](docs/research_readiness/20261025/evidence/b7_b8_cached_real_check.json)|`243b614aa67c4a8070b51775afb29218050ff3decaa3b1cd11168b5819dafd11`|
|[docs/research_readiness/20261025/evidence/b7_b8_preparation_checks.json](docs/research_readiness/20261025/evidence/b7_b8_preparation_checks.json)|`fb420982ea8bff0f4eb874dec1c798265d9733b35c558300c3ac2286579a4cf5`|
|[docs/research_readiness/20261025/evidence/b7_b8_approved_launch.json](docs/research_readiness/20261025/evidence/b7_b8_approved_launch.json)|`d49e507703b27edfe3064358c113c02946646f39b9c72484e4dd9aa1180fc896`|
|[docs/research_readiness/20261025/evidence/b7_b8_terminal_20261028.json](docs/research_readiness/20261025/evidence/b7_b8_terminal_20261028.json)|`196b5efb6008cb0590ed73acf91e3daa1037851e49d1d433bc1e576f6f3d2729`|
|[docs/research_readiness/20261025/evidence/b8_recovery_proposal_20261028.json](docs/research_readiness/20261025/evidence/b8_recovery_proposal_20261028.json)|`d45e725eb611e5ba168be66b854c282c0618c938ffe46c0f1ee33c7fc96ce16c`|
|[docs/research_readiness/20261025/evidence/b8_source_diagnostic_20261028.json](docs/research_readiness/20261025/evidence/b8_source_diagnostic_20261028.json)|`2a25b82804104eb1f973ac6707815869ec5d8169a7ac20f942e230f15b7a32a6`|
|[docs/research_readiness/20261025/evidence/b8_recovery_checks_20261028.json](docs/research_readiness/20261025/evidence/b8_recovery_checks_20261028.json)|`f449f93df124aa19487dd404866d45e246313135ffb6c85283a540aebebffa6f`|
|[docs/research_readiness/20261025/evidence/b8_recovery_approved_launch_20261028.json](docs/research_readiness/20261025/evidence/b8_recovery_approved_launch_20261028.json)|`d04e9f32a2d68c05cbdf3ff96114a3453eea33ada32c33bedcb94342eef781a7`|
|[docs/research_readiness/20261025/evidence/b8_recovery_completion_20261028.json](docs/research_readiness/20261025/evidence/b8_recovery_completion_20261028.json)|`3fb57ebd6301d57598bca0f1bdf903160bb0f54acb3b82225616dd8a47fe0ab3`|
|[docs/research_readiness/20261025/evidence/b7_b8_multiseed_proposal_20261028.json](docs/research_readiness/20261025/evidence/b7_b8_multiseed_proposal_20261028.json)|`250aa997767b771059e14682cd5e031bf5dc3f5020d28a7f65c5cf715c0fe0e5`|
|[docs/research_readiness/20261025/evidence/b7_b8_multiseed_checks_20261028.json](docs/research_readiness/20261025/evidence/b7_b8_multiseed_checks_20261028.json)|`e858701311bf00e35edaf3ec1affe4ee4ccdec82adef328d3215fc840b9710ef`|
|[docs/research_readiness/20261025/evidence/b7_b8_multiseed_source_admission_20261028.json](docs/research_readiness/20261025/evidence/b7_b8_multiseed_source_admission_20261028.json)|`b53a210f8c23ea2d81135ace4b7ed1e84ceafa45cfbf716d3aa3fd061d33c4ea`|
|[docs/research_readiness/20261025/evidence/b7_b8_multiseed_approved_launch_20261028.json](docs/research_readiness/20261025/evidence/b7_b8_multiseed_approved_launch_20261028.json)|`5e31b40c283f3707edde756b133063bfc1ddd5e0a9f87143cf7ffe755e5ae8f6`|
|[docs/research_readiness/20261025/evidence/b7_b8_multiseed_interruption_20261028.json](docs/research_readiness/20261025/evidence/b7_b8_multiseed_interruption_20261028.json)|`6a1abef5a63f691b8e34401496bb3e5b2f7e34f8c13222b1b91401864017151a`|
|[docs/research_readiness/20261025/evidence/b7_b8_multiseed_exit_cause_20261028.json](docs/research_readiness/20261025/evidence/b7_b8_multiseed_exit_cause_20261028.json)|`8469581557c8e84189b398248b97f9ea1a2c88ce02c172af83a325500f034b69`|
|[docs/research_readiness/20261025/evidence/b7_b8_multiseed_recovery_proposal_20261028.json](docs/research_readiness/20261025/evidence/b7_b8_multiseed_recovery_proposal_20261028.json)|`7715f455e6bfb3d603fddc1b77228bf25f4d64e63fd5b296f6c04c5d5a711549`|
|[docs/research_readiness/20261025/evidence/b7_b8_multiseed_recovery_checks_20261028.json](docs/research_readiness/20261025/evidence/b7_b8_multiseed_recovery_checks_20261028.json)|`61639fae54534a4c33f6eefa7d93730dd4e602b3b607ea5edd7fc9d0fb7b8840`|
|[docs/research_readiness/20261025/evidence/b7_b8_multiseed_recovery_approved_launch_20261028.json](docs/research_readiness/20261025/evidence/b7_b8_multiseed_recovery_approved_launch_20261028.json)|`135628ffd596b4d44ef0fe72584f14f0d3664ae9a009bb19d99382125dd4b504`|
|[docs/research_readiness/20261025/evidence/b7_b8_three_seed_completion_20261029.json](docs/research_readiness/20261025/evidence/b7_b8_three_seed_completion_20261029.json)|`d12a7919da8aac7775300204a2f12d4dfe938e5efbd68f52118ae0bab9edd3f3`|
|[docs/research_readiness/20261025/evidence/paper_acceptance_20261029.json](docs/research_readiness/20261025/evidence/paper_acceptance_20261029.json)|`e73e68052b15a29165f6a745aa09b004dba8273f22c475e4bcb91163294b6f10`|
|[docs/research_readiness/20261025/evidence/scientific_attribution_diagnostics_20261029.json](docs/research_readiness/20261025/evidence/scientific_attribution_diagnostics_20261029.json)|`d2ca1c4f8ab385303631cd1656457ff1426cecb6616ceed0fbfb0471e63954b8`|
|[docs/research_readiness/20261025/evidence/brier_exact_score_decomposition_20261029.json](docs/research_readiness/20261025/evidence/brier_exact_score_decomposition_20261029.json)|`527ba7121b04727faab376d90e1692095fed77b88b58c84a37a2346226640c0c`|
|[docs/research_readiness/20261025/evidence/dote_control_checks_20261029.json](docs/research_readiness/20261025/evidence/dote_control_checks_20261029.json)|`db89994d6cb50a30bf6d474ffd75e0e0d503bd7d0bdb7f51e9c9485d4900c772`|
|[docs/research_readiness/20261025/evidence/dote_control_proposal_20261029.json](docs/research_readiness/20261025/evidence/dote_control_proposal_20261029.json)|`a2a86f0611f9c5f805d9929788179deb13d2daa399ba4e4a831cdbaf70c7379d`|
|[docs/research_readiness/20261025/evidence/dote_control_approved_launch_20261029.json](docs/research_readiness/20261025/evidence/dote_control_approved_launch_20261029.json)|`b830940b501804a21c2958161c3534b5feca41bfda7ba73b37db9cd88dd937dd`|
|[docs/research_readiness/20261025/evidence/dote_control_completion_20261029.json](docs/research_readiness/20261025/evidence/dote_control_completion_20261029.json)|`063501c8b563f0c8bb9dd46662ec3ddec3ad4c60bfc004f83f0ffde4c807c611`|
|[docs/research_readiness/20261025/evidence/dote_control_multiseed_proposal_20261029.json](docs/research_readiness/20261025/evidence/dote_control_multiseed_proposal_20261029.json)|`31decb3796f806b591d2fee87132b55590a03e8939294b11e730ad337d9ce46c`|
|[docs/research_readiness/20261025/evidence/dote_control_multiseed_checks_20261029.json](docs/research_readiness/20261025/evidence/dote_control_multiseed_checks_20261029.json)|`a13d812ef62c0cf96540b338bbf351021fd3f1e52bce67229d9c156f38affc54`|
|[docs/research_readiness/20261025/evidence/dote_control_multiseed_approved_launch_20261029.json](docs/research_readiness/20261025/evidence/dote_control_multiseed_approved_launch_20261029.json)|`203943775e61bcff4e027391b8e0139fceea2d983585aa6c53c1d641bebcf3c7`|
|[docs/research_readiness/20261025/evidence/dote_control_three_seed_completion_20261029.json](docs/research_readiness/20261025/evidence/dote_control_three_seed_completion_20261029.json)|`188f0305ec0faa7bd0077cc950dd0d5ec50e104bb54978bcdf8a2878ce2d5adf`|
|[docs/research_readiness/20261025/evidence/physical_attribution_decision_20261030.json](docs/research_readiness/20261025/evidence/physical_attribution_decision_20261030.json)|`50dfa8ff25bf481a13b709330201ebe58bf79270453133b378c7abce0653d796`|
|[docs/research_readiness/20261025/evidence/dote_physical_negative_protocol_20261030.json](docs/research_readiness/20261025/evidence/dote_physical_negative_protocol_20261030.json)|`d1fc6df50d7fe0c0a3adc7fb477182c1d559a6c210d46c5d351452956e891f90`|
|[docs/research_readiness/20261025/evidence/dote_reliability_increment_20261030.json](docs/research_readiness/20261025/evidence/dote_reliability_increment_20261030.json)|`ae10d7cdf9e519531dad2e9e8bb7a7c8374e130e74d67a2347d374922371c005`|
|[docs/research_readiness/20261025/evidence/final_test_preregistration_increment_20261030.json](docs/research_readiness/20261025/evidence/final_test_preregistration_increment_20261030.json)|`d887fc502f70b8c4dd68090586f7c83e20557cd56c8ebd4b3260d4dc6dc38eb9`|
|[docs/research_readiness/20261025/evidence/physical_negative_train_diagnostics_20261030.json](docs/research_readiness/20261025/evidence/physical_negative_train_diagnostics_20261030.json)|`55f20b918c7ca6ab342a0101bf5576b0de211cf319c7e0d2d8e0363ed1869830`|
|[docs/research_readiness/20261025/evidence/physical_negative_cached_train_check_20261030.json](docs/research_readiness/20261025/evidence/physical_negative_cached_train_check_20261030.json)|`b918b4b65d10753484c93f76be32941196131f4aa7b3c59a69b0e7a84ae29817`|
|[docs/research_readiness/20261025/evidence/physical_attribution_publication_20261030.json](docs/research_readiness/20261025/evidence/physical_attribution_publication_20261030.json)|`d71eaea9fcc11d7484c1fcb4fad3041559336eb9792b7428f5ef16847e098b2d`|
|[docs/research_readiness/20261025/evidence/dote_physical_control_training_proposal_20261030.json](docs/research_readiness/20261025/evidence/dote_physical_control_training_proposal_20261030.json)|`be00f3f7da32e622b98e9d1838a17f051316766b1329f661fcff590c062cc8a2`|
|[docs/research_readiness/20261025/evidence/dote_physical_control_queued_start_20261030.json](docs/research_readiness/20261025/evidence/dote_physical_control_queued_start_20261030.json)|`c44f50130c8b9d0ad863856151edb5525ed58e5a872063f048a8e7ade67143d5`|
|[docs/research_readiness/20261025/evidence/physical_negative_cached_train_pass_20261030.json](docs/research_readiness/20261025/evidence/physical_negative_cached_train_pass_20261030.json)|`8466b5839d9afb8a2b38bd60a9375723fad9daf9993ab462dd86dc19f766ac08`|
|[docs/research_readiness/20261025/evidence/metric_backfill_completion_preparation_20261030.json](docs/research_readiness/20261025/evidence/metric_backfill_completion_preparation_20261030.json)|`a430c48f064614262cd00b5b66a59aa1ab6a520a9ec624d8be540cc838ca04c4`|
|[docs/research_readiness/20261025/evidence/metric_backfill_completion_started_20261030.json](docs/research_readiness/20261025/evidence/metric_backfill_completion_started_20261030.json)|`53de7a1bc8b1f712fb142db805959c99377255ae725ebce6864c48933576a10d`|
|[docs/research_readiness/20261025/evidence/single_metric_table_preparation_20261030.json](docs/research_readiness/20261025/evidence/single_metric_table_preparation_20261030.json)|`f00c93bb3e0c83dc79637c9ac55dfeb96fbd49881a93d9ab2abe8f3b7ddc4b8e`|

五个统一文件及[生成器](tools/research_readiness/build_unified_delivery.py)不读取原始气象、权重或2025。运行`python tools/research_readiness/build_unified_delivery.py`可按本页嵌入快照重建四个表/报告及本索引；它继承源收据，检查39个唯一实验ID、原值一致性、人口/组ID配对和三seed均值/样本标准差。它不是训练或全量实验复核命令。

导出构成：`{"MISSING_OR_NULL": 2205, "OFFLINE_DERIVED": 2589, "PAIRED_DELTA": 5737, "PAIRED_MEAN": 1023, "PAIRED_SAMPLE_SD": 1023, "RAW_ENDPOINT": 26669, "RAW_EPOCH": 25515}`。存在完整指标的每个源数值叶子都保留；旧逐轮摘要数值仅转录。缺失结果不补零，q32缺失分层不反推。公开输入与本索引嵌入快照足以重建本交付，不需要公开私有目录。

|统一交付|SHA256|
|---|---|
|[STAGE_ACCEPTANCE.md](STAGE_ACCEPTANCE.md)|`901a02a47672fcb55a3c8badafcae519bdff769859b31a430de1d09967fea8c0`|
|[EXPERIMENT_MATRIX.csv](EXPERIMENT_MATRIX.csv)|`1991718fa15fa2213b8e3ec8df325e4dd6c3a1b13832fa16a3c986a0e7690577`|
|[METRICS.csv](METRICS.csv)|`e820ed9cbb9887ac85ddbc5ceed30b072d26ae892edf8c6e1a6d624717dcf191`|
|[SCIENTIFIC_ANALYSIS.md](SCIENTIFIC_ANALYSIS.md)|`fced0284c35ca58bed6cdbc6cfc9c9044e87deaf6930880ee6d07ffc3472df83`|

本索引自身身份由Git标识，不写自引用文件哈希。旧索引、历史PUBLICATION_MANIFEST与已批准实验收据保持原字节。当前工作分支提交/推送不构成main合并或新训练批准。

## 2026-10-30增量定位

[候选科学协议](docs/research_readiness/20261025/evidence/dote_physical_negative_protocol_20261030.json)绑定准备代码`6c26c9eb3f9b3452a10b62649774a1f617b2efc3`及规范化协议SHA，不是可执行训练批准包。[ZERO三seed经验分解](docs/research_readiness/20261025/evidence/dote_reliability_increment_20261030.json)新增3份既有score计数表，真实B7/B8分解直接继承。[2023 Train特征诊断](docs/research_readiness/20261025/evidence/physical_negative_train_diagnostics_20261030.json)记录959 GFS主文件272,589,016字节、真实mask/全部分布和地理相关；不读取卫星、降水标签、Dev或2025。[整模缓存检查](docs/research_readiness/20261025/evidence/physical_negative_cached_train_check_20261030.json)在RAM门槛停止，NOT_VERIFIED而非PASS，无模型/缓存加载。失败初始缺少psutil发生在原始读取前，原命名空间保留，已改原生RSS，仅完成特征诊断。

[最终测试增量草案](docs/research_readiness/20261025/evidence/final_test_preregistration_increment_20261030.json)登记12份既有E9/执行身份；新增ZERO范围、主比较及共同指标尚待研究者冻结。真实2025适配器未实现，元数据检查仅使用2001合成记录，原年份保护未放开。没有2025新增访问。

[可编辑LaTeX](docs/research_readiness/20261030/research_decision/main.tex) / [科研决策PDF](docs/research_readiness/20261030/research_decision/YunTAPR_Physical_Attribution_Decision_20261030.pdf)。原20261029冻结PDF/TeX及已批准提案均保留原字节。新增候选未训练，所有现有完成模型状态不变。

## 后续缓存通过与真实启动队列

此前RAM受阻是历史时点；[后续缓存通过](docs/research_readiness/20261025/evidence/physical_negative_cached_train_pass_20261030.json)记录两场景6860有效像元、0优化器更新及128列梯度探针响应。[研究者直接启动指令及队列](docs/research_readiness/20261025/evidence/dote_physical_control_queued_start_20261030.json)与[精确执行包](docs/research_readiness/20261025/evidence/dote_physical_control_training_proposal_20261030.json)绑定新代码9b4046a和单模型限额；先19项指标回填全部通过，再一次启动，当前未训练完成。新增[指标续算启动收据](docs/research_readiness/20261025/evidence/metric_backfill_completion_started_20261030.json)只记录一次启动时点，旧6项完成及旧部分读取账本保留。最终交付按最新要求为一个工作表的一张大表，不覆盖原Excel。

## 2026-10-30已有指标直接复用

[保存统计复用收据](docs/research_readiness/20261025/evidence/saved_metric_reuse_20261030.json)（SHA256 `3d9006d048eca0176b2145b03ae6bdc67e3a94a44ab1cda78b88cdcd4e3dd868`）绑定6份既有CSV/JSON输出身份：28总体、96分组、20配对及2旧版代理。继承原Tier0有效检查；新增2项复用边界检查、全部6项当前汇总CPU检查与JS语法通过，80项已保存配对主指标身份核对一致，不重做模型推理。旧BEST代理明确排除当前E9主比较；已有分类率和配对值直接用保存值。冻结概率gate在所需新指标的同次前向中完成，不增加单独推理轮次。新单表最终布局仍NOT_VERIFIED、未导出；不以当前15/19快照冒充全部交付。训练代码9b4046a及已绑定单模型提案不变，未控制当前进程、读取权重或访问2025。

## 2026-10-30当前监测面板与补算停止

[只读面板及停止事实](docs/research_readiness/20261025/evidence/metric_pipeline_monitor_20261030.json)（SHA256 `6e640698917588595203415f88953e6cbdd56eb05455e412fa36c0ab070241a9`）绑定本轮页面代码、失败元数据和B0门控结果的字节身份。15/19有效完成，B0/2026 E0的条件Pinball差3.36897248223722e−7、q32覆盖差8.006049014852579e−6、覆盖计数少36；严格gate未通过，底层数值原因尚未查明。46,758,323,515字节/22,838次失败段读取不清零，原B4部分账本保留。候选训练0次更新/未调用，页面仅查看，WMI独立服务不控制计算；已取消的资源保护自动化没有重新启用。

## B0/B1补算上下文错误的增量定位

[代码作用域与最小修复](docs/research_readiness/20261025/evidence/b01_metric_context_diagnosis_20261030.json)（SHA256 `8dade9603fc48defd457356e2943b54ad6ac134f9808bee70b79c4dff8e4c5f9`）以两份原Engine的AST调用位置证明历史评估未退出seeded_environment。外部补算器误置确定性且未继承TF32/FP32策略，包装层现已修正并恢复inference_mode；3项新CPU边界检查通过，15项有效结果不重算。观察时外部脚本SHA0ca882ba…与旧包pin0c279786…不同，mtime在B0运行期间，修改来源未验证；保留观察副本，不覆盖外部更改。真实B0数值是否恢复一致仍NOT_VERIFIED；未加载模型、读取原始气象、复算或恢复训练，2025冻结。

## 四项指标修正的唯一审批对象

[修正提案](docs/research_readiness/20261025/evidence/metric_b01_correction_proposal_20261030.json)（文件字节SHA256`dba3aebc4466e8605795d41a7bbc500ef1cf11729b0ab16a687f06dcacbbdf17`；规范化SHA`daa745a02e8e51ff25155dddd1b65721c958a649277787d4fe53a11b563381b2`；执行代码`3d632954e37a6003d77babd06172922d63b0c77a`）绑定15项继承、四项次序、四个E9和858232b9…的2024人口、外部脚本冻结快照、原LRU预算及资源上限。B0完整内容账本10775次/46758323515字节，与旧日志read_events22838严格区分；早先旧收据的“源实例22838”标注有误，原件保留，此处纠正解释。六项新增CPU检查通过，三项上下文/125项未变公式检查继承；缺少真实批准时入口已拒绝，研究者批准文件及新计算输出均未创建。现有只读面板已重载为区分已知内容实例与旧日志事件，未控制训练/评价或重开资源保护任务。

## 修正包实际批准与单次派发

[启动收据](docs/research_readiness/20261025/evidence/metric_b01_correction_started_20261030.json)（SHA256`b27b18d3f708ee7fb0782e94d91e055a8b89344a792751eb5581cf92b531bdb1`）关联真实研究者回复、精确3d632954/daa745a0、15项继承SHA、WMI监督器与控制器脱离Job/包身份、资源入场和真实内容读取快照。首次B0/2026完整10501场景Dev已实际通过严格gate：五项指标差值均0、q32计数4305233一致，source46758323515字节/10775次，result SHA1a510619…；16/19及后续B1派发已记录。仅首项通过，不能把整包或候选训练标为COMPLETE。新终态跟进30分钟一次、最多48次/24小时至2026-10-31T12:06:35.099586Z；原资源保护不恢复。原候选9b4046a/0444d92e等待19项全通过自动一次启动，最终单大表源已改新包，不读取原失败B0作为成功结果。
