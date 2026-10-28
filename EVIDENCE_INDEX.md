# 统一证据索引

出版基线commit：`56aae5bc4568df5d91354805aa5d4cb6d34b62b3`。本五文件的版本由所属Git提交标识，不伪造自引用commit。实际模型代码独立绑定如下。研究者为主体，AI辅助摘录；公开SHA约束原件身份，不等于外部已独立复现未公开数据。

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
|B7|2030|`NOT_AVAILABLE_NO_FIXED_E9_RESULTS`|`56aae5bc4568df5d91354805aa5d4cb6d34b62b3`|
|B8|2030|`NOT_AVAILABLE_NO_FIXED_E9_RESULTS`|`NOT_STARTED_PENDING_SERIAL_QUEUE`|
|B7|2031|`NOT_AVAILABLE_NO_FIXED_E9_RESULTS`|`NOT_STARTED_PENDING_SERIAL_QUEUE`|
|B8|2031|`NOT_AVAILABLE_NO_FIXED_E9_RESULTS`|`NOT_STARTED_PENDING_SERIAL_QUEUE`|

B4/2030矩阵终点commit为943da95，其E1继承52a8e90，E2–9由943da95执行；累计4,710实际尝试含390必要重放，有效轨迹4,320，成本见三seed收口。历史原始失败段仍保留。B5/B6本次纠正批准已消费，不允许额外重试。

## 数据与评价绑定

当前959/963人口SHA256：`2f2cc75cfb6c209fd8195d3419207216c5c3f2a4fc8315b40a1d77cc537dedb8`；populations文件SHA：`ea6abae6a493f2abdf19f938365407a35f0f0be71ba1346241264635318a32d2`；训练统计SHA：`53ab2f07aabb02e66ad237452447a35e0e2896278eae9d2da179336c06fea980`；target QC SHA：`b4bad8ea45a78eddae3832df89cfade00cac3b184fc550eea4f0cf479c29de90`。2023 Train / 2024 Development、四UTC、f006回顾估计；2025冻结。B13保持既有训练集scaler（mean=271.60515414265217 K，std=19.93959597783802 K，源身份656fe7a929cbd8617b08427e8d1fa7029b26512253efb44faa576796137d4a31），不声称它在当前959重新拟合。

核心评价脚本：[src/yuntapr/experimental/core_innovation/stage4/evaluation.py](src/yuntapr/experimental/core_innovation/stage4/evaluation.py)，执行版SHA256 `fd4cb37bb62675601cf685eb1d656f4fd8b88e2ba52d6019652114035908e9ce`；精确AUROC/AP及冻结float32阈值>0.1 mm/h口径继承[metrics.py](src/yuntapr/experimental/phase_b_v2_formal_integration_candidate/metrics.py)。Dev有效像元3,303,090、有雨407,820；不同人口和旧终点逐行保留。脚本链接指工作分支，重现执行身份必须同时使用矩阵中的执行commit及上述SHA。

## 本轮输入身份与交付校验

本轮新增宿主更新/容器时间线与独立启动修复证据；不重复模型测试或改写原中断账本，不重复历史129来源/126轮审查；历史收据本身不被改为本轮重新核验。以下为直接采用的公开输入字节身份：

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

五个统一文件及[生成器](tools/research_readiness/build_unified_delivery.py)不读取原始气象、权重或2025。运行`python tools/research_readiness/build_unified_delivery.py`可按本页嵌入快照重建四个表/报告及本索引；它继承源收据，检查35个唯一实验ID、原值一致性、人口/组ID配对和三seed均值/样本标准差。它不是训练或全量实验复核命令。

导出构成：`{"MISSING_OR_NULL": 949, "PAIRED_DELTA": 4247, "PAIRED_MEAN": 427, "PAIRED_SAMPLE_SD": 427, "RAW_ENDPOINT": 17062, "RAW_EPOCH": 11563}`。存在完整指标的每个源数值叶子都保留；旧逐轮摘要数值仅转录。缺失结果不补零，q32缺失分层不反推。公开输入与本索引嵌入快照足以重建本交付，不需要公开私有目录。

|统一交付|SHA256|
|---|---|
|[STAGE_ACCEPTANCE.md](STAGE_ACCEPTANCE.md)|`1883e6e9e01f9a6ef3f720bfbea85dfcf591ed44dbfc9cd28eac2533a402951d`|
|[EXPERIMENT_MATRIX.csv](EXPERIMENT_MATRIX.csv)|`3f498e4d13112aa14993bf4b59e0ecdfc895482e25fbd6b4ece26daef947b0fd`|
|[METRICS.csv](METRICS.csv)|`933913a3298b8484cff74a6c91d406fc68e01a4c48d363fe7ecfb142492fe1c3`|
|[SCIENTIFIC_ANALYSIS.md](SCIENTIFIC_ANALYSIS.md)|`ec76288c5a3279fb0ddb5e9cf89006daf06225aee7566ae8ad591eccdd9cd863`|

本索引自身身份由Git标识，不写自引用文件哈希。旧索引、历史PUBLICATION_MANIFEST与已批准实验收据保持原字节。当前工作分支提交/推送不构成main合并或新训练批准。
