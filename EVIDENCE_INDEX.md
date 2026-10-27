# 统一证据索引

出版基线commit：`2ea3c9ce87f4e26c36ed7529c99122bea7cb3f54`。本五文件的版本由所属Git提交标识，不伪造自引用commit。实际模型代码独立绑定如下。研究者为主体，AI辅助摘录；公开SHA约束原件身份，不等于外部已独立复现未公开数据。

## 当前训练状态快照

仅摘录现有只读进度服务元数据；状态时点是UTC（北京时间加8小时），不是页面实时值。B5/B6阶段均IN_PROGRESS，B6执行PENDING。终态须依据完整新收据另行收口，不从checkpoint存在或部分轮次判完成。

<!-- STATUS_SNAPSHOT -->
```json
{
  "state": "RUNNING",
  "snapshot_utc": "2026-10-27T00:20:47.985885+00:00",
  "source_commit": "b251fd9ea06c0c90f48d2ac0decba0454114669d",
  "completed_models": 0,
  "runs": [
    {
      "model": "B5",
      "seed": 2029,
      "state": "RUNNING",
      "returned": 707,
      "sealed_epochs": 1
    },
    {
      "model": "B6",
      "seed": 2029,
      "state": "PENDING",
      "returned": 0,
      "sealed_epochs": 0
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
|B5/B6，2029|[一次纠正启动](docs/research_readiness/20261025/evidence/b5_b6_corrected_start_launch.json)、[原失败](docs/research_readiness/20261025/evidence/b5_b6_initial_start_stop.json)|[冻结纠正提案](docs/research_readiness/20261025/evidence/b5_b6_corrected_start_proposal.json)、[地形源/网格/静态包SHA](docs/research_readiness/20261025/evidence/b5_b6_terrain_production.json)；当前E9身份NOT_AVAILABLE|

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
|B5|2029|`NOT_AVAILABLE_FIXED_E9`|`b251fd9ea06c0c90f48d2ac0decba0454114669d`|
|B6|2029|`NOT_AVAILABLE_FIXED_E9`|`b251fd9ea06c0c90f48d2ac0decba0454114669d`|

B4/2030矩阵终点commit为943da95，其E1继承52a8e90，E2–9由943da95执行；累计4,710实际尝试含390必要重放，有效轨迹4,320，成本见三seed收口。历史原始失败段仍保留。B5/B6本次纠正批准已消费，不允许额外重试。

## 数据与评价绑定

当前959/963人口SHA256：`2f2cc75cfb6c209fd8195d3419207216c5c3f2a4fc8315b40a1d77cc537dedb8`；populations文件SHA：`ea6abae6a493f2abdf19f938365407a35f0f0be71ba1346241264635318a32d2`；训练统计SHA：`53ab2f07aabb02e66ad237452447a35e0e2896278eae9d2da179336c06fea980`；target QC SHA：`b4bad8ea45a78eddae3832df89cfade00cac3b184fc550eea4f0cf479c29de90`。2023 Train / 2024 Development、四UTC、f006回顾估计；2025冻结。B13保持既有训练集scaler（mean=271.60515414265217 K，std=19.93959597783802 K，源身份656fe7a929cbd8617b08427e8d1fa7029b26512253efb44faa576796137d4a31），不声称它在当前959重新拟合。

核心评价脚本：[src/yuntapr/experimental/core_innovation/stage4/evaluation.py](src/yuntapr/experimental/core_innovation/stage4/evaluation.py)，执行版SHA256 `fd4cb37bb62675601cf685eb1d656f4fd8b88e2ba52d6019652114035908e9ce`；精确AUROC/AP及冻结float32阈值>0.1 mm/h口径继承[metrics.py](src/yuntapr/experimental/phase_b_v2_formal_integration_candidate/metrics.py)。Dev有效像元3,303,090、有雨407,820；不同人口和旧终点逐行保留。脚本链接指工作分支，重现执行身份必须同时使用矩阵中的执行commit及上述SHA。

## 本轮输入身份与交付校验

本轮仅校验新增导出及差值，不重复历史129来源/126轮审查；历史收据本身不被改为本轮重新核验。以下为直接采用的公开输入字节身份：

|公开输入|SHA256|
|---|---|
|[docs/research_readiness/20261025/B0_B4_EXPERIMENT_MATRIX.csv](docs/research_readiness/20261025/B0_B4_EXPERIMENT_MATRIX.csv)|`34849b370f68cdc95392c4421d541c3eb768636691514ba01d3353f2f019f95e`|
|[docs/research_progress/evidence/experiments.json](docs/research_progress/evidence/experiments.json)|`828a10fa01b013a3d48416c86a599b0179d9252d2b91e0fe3a5dbf1287c4e119`|
|[docs/research_progress/evidence/seed2029_groups.json](docs/research_progress/evidence/seed2029_groups.json)|`4241b2a1148c921363737150a088f080a991b3e4553469fd5a05aea7cbc3852d`|
|[docs/research_readiness/20261025/evidence/b2_completion_and_paired_evidence.json](docs/research_readiness/20261025/evidence/b2_completion_and_paired_evidence.json)|`96738035c5e3f6b32ce4bf7e2a4f656313ea742ad53eb9ac38eb627f8dc8b3e1`|
|[docs/research_readiness/20261025/evidence/b3_b4_three_seed_completion.json](docs/research_readiness/20261025/evidence/b3_b4_three_seed_completion.json)|`e101ebd17b267d4fc0d93b53afe0ab432ce3e7a54f226f9058eac54237eecde4`|
|[docs/research_readiness/20261025/evidence/b3_b4_full_endpoint_metrics_20261027.json](docs/research_readiness/20261025/evidence/b3_b4_full_endpoint_metrics_20261027.json)|`8300a312b64f6cd2440cdf560bc07e3d5d0aa3d1d35cba33173963b75b1b1666`|
|[docs/research_progress/epoch_metrics.csv](docs/research_progress/epoch_metrics.csv)|`a79119bc5c2b37602949ec55c33171ae9f3d2093166688dfa3ad2c652abdf524`|
|[docs/research_readiness/20261025/evidence/b5_b6_corrected_start_launch.json](docs/research_readiness/20261025/evidence/b5_b6_corrected_start_launch.json)|`7c564f7c5349900c6fa1f5f2e814a8504612a8231d42f8b8008e0f0ba0bb29f4`|
|[docs/research_readiness/20261025/evidence/b5_b6_initial_start_stop.json](docs/research_readiness/20261025/evidence/b5_b6_initial_start_stop.json)|`e0dc6834aa7297293b4d5801741f86b449810feb9317936ae0feb179d932bc96`|
|[docs/research_readiness/20261025/evidence/b5_b6_terrain_production.json](docs/research_readiness/20261025/evidence/b5_b6_terrain_production.json)|`75204e2d8fd0eb37e9a13012fb7c74c523f23ffe436ec5b0446e8c4d134ead03`|

五个统一文件及[生成器](tools/research_readiness/build_unified_delivery.py)不读取原始气象、权重或2025。运行`python tools/research_readiness/build_unified_delivery.py`可按本页嵌入快照重建四个表/报告及本索引；它继承源收据，检查29个唯一实验ID、原值一致性、人口/组ID配对和三seed均值/样本标准差。它不是训练或全量实验复核命令。

导出构成：`{"MISSING_OR_NULL": 405, "PAIRED_DELTA": 1404, "PAIRED_MEAN": 427, "PAIRED_SAMPLE_SD": 427, "RAW_ENDPOINT": 11610, "RAW_EPOCH": 3141}`。存在完整指标的每个源数值叶子都保留；旧逐轮摘要数值仅转录。缺失结果不补零，q32缺失分层不反推。公开输入与本索引嵌入快照足以重建本交付，不需要公开私有目录。

|统一交付|SHA256|
|---|---|
|[STAGE_ACCEPTANCE.md](STAGE_ACCEPTANCE.md)|`66a419abb843ef3fead99f1a8f4cad664a4f40fbae79dcbbc2db95530d5d225a`|
|[EXPERIMENT_MATRIX.csv](EXPERIMENT_MATRIX.csv)|`b23764b5f0c9704679fc99ff80937ed1edace6acf4228467a8af7e49de9bf0fb`|
|[METRICS.csv](METRICS.csv)|`e9ff89e2d71d956383c42e771990f59aa5e0e79275a4ba8405f4d92b31e27122`|
|[SCIENTIFIC_ANALYSIS.md](SCIENTIFIC_ANALYSIS.md)|`8fbc165c93673405c68fd1ceb63e3d08c936517a117b1534542f9cfe2d7423e6`|

本索引自身身份由Git标识，不写自引用文件哈希。旧索引、历史PUBLICATION_MANIFEST与已批准实验收据保持原字节。当前工作分支提交/推送不构成main合并或新训练批准。
