# B1 Scientific Freeze v1：设计、样本集合与共享 normalization

本轮完成研究者已批准的科学设计、M1 样本资格、common intersection 与 B1 normalization 冻结。**训练协议仅冻结已批准项，其余参数仍待研究者决定；没有启动 B1 或 B0-Matched-Control training，2025 outcome 继续封存。**

Run：`run_20261003T045139_110133Z`。Baseline：`1fd70ba9a563aa673012fa1b1494b86d72511eb6`。独立决策更新，1941 个 baseline 文件逐个 SHA256 与 Git blob 核对不变；包含历史 B0、旧 B1 审计及其失败记录。旧候选/未冻结状态保留为当时记录，由本轮独立 registry supersede，不回写历史。

## 冻结设计

- B1 只含 B13 × 6 causal historical slots。T 为冻结 IMERG native 30min window start，analysis_time = T+30min。
- Nominal offsets = analysis_time − [60,50,40,30,20,10] min。最旧到最新对应通道 0→5；input `[B,6,501,501]`。B0-Matched-Control 使用 slot 5，即 analysis_time−10min 的单帧。
- 实际逐帧强制 obs_start ≤ obs_end ≤ analysis_time；`[nominal,nominal+10min)` 仅 metadata 诊断，不增加事后剔除标准。date_created 仅记录；不声称 operational availability 或历史实时回放。
- **M1 严格六槽完整政策**：任一 missing、unreadable、partial、all-fill、无完整身份/时间证据或 noncausal，整个监督场景拒绝。不允许 older/nearest fallback、重复帧、零占位或插值。
- 研究窗口起点历史不足直接拒绝，不读取 2 月补齐。2023/2024 均保留 March–October 固定窗口，不根据 availability 改 offsets。
- 保留 B0 四层 residual U-Net 48→96→192→256、decoder、SP04、occurrence/32 quantile heads、target/mask、概率语义和 loss family。只改变最前端输入接口；已核验参数 B0=4,329,361，六槽接口=4,331,761，增加2,400。只改变 enc0 conv1/skip 两个 kernel 的输入维；这是已存在的隔离参数计数证据，本轮未实现或执行正式 B1 模型。
- native lat descending、lon ascending，精确 SP04 坐标逐值核对；无 flip、transpose、coordinate reconstruction。冻结行政区主评价 mask=3430 cells。其它 AHI channels、GFS、DEM、DOTE、DTFM、MEE、ERA5、attention、Transformer/recurrent 均未加入。

## 正式样本集合与公平比较

|样本集合|2023 Train|2024 Validation|
|---|---:|---:|
|固定日历目标|11,760|11,760|
|历史 B0 原资格集合|11,720|11,727|
|正式 B1：M1 六槽完整|10,455|10,501|
|common intersection|10,455|10,501|
|独立 B0-Matched-Control|10,455|10,501|
|日历目标被拒绝|1,305|1,259|
|历史 B0 不在共同集合的场景|1,265|1,226|

对全部23,520日历目标从冻结 QC 独立重算 M1；与旧候选集合和交集的身份、固定顺序逐值一致。B1 与 matched control 的 target/day/index/SHA、原 B0 sample ID 完全相同，control 最新 B13 身份与原 B0 源 ledger 一致。每个正式场景记录六个 nominal，并绑定已冻结 frame identity index（其签名 native CSV 内包含 raw path/bytes/SHA、actual CF 时间与 QC）。Train/Validation manifest 与 exposure plan 的完整路径及 SHA 在 sample_set_freeze.json 登记。

**Primary B0-vs-B1 comparison = 独立 B0-Matched-Control vs B1，使用同一 common intersection。** 历史 B0 不改训练集合、checkpoint 或指标，不把历史 B0 原集合的结果当作 matched control 结果；本轮没有重训练、重算模型结果或宣称对比效果。B0-Matched-Control 的 scaler 和其余训练参数待研究者决定，未自动套用 B1 scaler 或旧 B0 scaler。

Population 在本任务指“样本集合”或“样本总体”；所有新写的报告统一此术语。研究者原话在 provenance 中逐字保留。

## 真实 B1 normalization 拟合与冻结

仅正式2023 B1 Train的10,455场景参与；全部六槽共享一个 mean/std。scene-slot exposure 共62,730，251,001 native pixels / exposure，加权总数 **15,745,292,730**，ddof=0 继承既有 B0 的样本总体方差定义。2024 Validation 和2025不参与拟合；没有打开 raw IMERG。

同一 native frame 被多个场景引用时按实际出现次数重复计权。工程实现只解码每个不同源文件一次，再以整数 multiplicity 累加 packed-code histogram，数学计权与逐场景六槽展开相同，**没有换成 unique-frame weighting**。实际读取33,219个不同2023文件 / 8,338,002,219 B13像元值；实际读数与加权暴露分开记录。

- mean = **271.60515414265217 K**
- std = **19.93959597783802 K**
- version = `B1_2023_M1_COMMON_INTERSECTION_SCENE_SLOT_SHARED_v1`
- normalization SHA256 = `656fe7a929cbd8617b08427e8d1fa7029b26512253efb44faa576796137d4a31`
- transform：`((raw_K_float32.astype(float64)−mean_K)/std_K).astype(float32)`

packed int16按冻结reader的float32 scale=.01 / offset=273.15 解码，未用整数理想化 Kelvin 替代实际float32乘加。int64 histogram 精确累计，float64 centered second moment / count 计算 std；独立测试按另一种 sum 计算重放验证 mean/std。完整 histogram CSV、来源身份、逐帧 copy/read/cleanup log、生成代码 SHA 和样本 manifest SHA 均已保存。

初始 design config 记录拟合前的 rule-frozen/value-pending 状态；最终 authoritative registry 绑定完成的 scaler 文件，解决该状态。两个事件均不覆盖。

## 训练协议：已批准项与待决项

研究者明确回复：**只冻结已批准项，其余参数待研究者决定。** 本轮冻结输入、M1、样本集合、共享B1拟合规则、共同比较集合及历史不可变约束。

以下仍为 NOT_YET_FROZEN / RESEARCHER_DECISION_REQUIRED：

|类别|待研究者决定|
|---|---|
|优化与 loss 数值设置|optimizer / parameter groups / LR / focal alpha,gamma / clipping|
|采样与更新预算|physical batch / accumulation / drop_last / steps / W / U / epochs|
|选择与恢复|early stopping / checkpoint selection / initialization seed,checkpoint policy / resume|
|执行设置|AMP / loader workers / B1内存可行性 preflight|
|Matched control preprocessing|是否使用本轮 B1 shared scaler或独立 latest-slot scaler|

不自动继承 Phase-A 的50epoch、AdamW、LR、seed等具体训练参数；旧 Phase-A protocol只作不可变参考。SP04/heads/loss family 的科学语义保持原冻结合同，数值训练参数审批独立。没有正式 training entrypoint / optimizer / backward / 参数更新 / checkpoint初始化或恢复；未来训练须另行研究者冻结协议并授权，不自动进入下一阶段。

## 实际 I/O、隔离与测试

只读原始H源：66438次 source opens（copy与source SHA各一次/文件）。copy read / temporary write 各 146,487,514,556 bytes（136.427 GiB），额外 source SHA read 146,487,514,556 bytes。copy=462.740s，read/QC/histogram/pinned staging SHA=456.740s，elapsed=1215.896s。按执行代码路径另核算两个staged SHA遍历，共 292,975,029,112 bytes；netCDF物理I/O字节未单独测量。暂存峰值 6,391,406 bytes（6.095 MiB），cap=700MiB，一次一个文件，cleanup_success=true，完成后独立核验自己的 staging child为空。原盘永久只读，旧五个 diagnostic caches 保留。

只允许固定2023 Train白名单，2024/February/2025/H内未登记文件、raw IMERG和checkpoint在打开前拒绝。源大小、original/staged SHA、pinned SHA在decode前核验；真实逐文件坐标和actual CF时间与原审计相符，完整501×501有效；无替代路径、no missing-as-zero。

最终闭环 suite 实际执行 **71项相关测试**，全部通过、零skip：20新synthetic/reader/guard units + 11新真实freeze/scaler artifact tests + 19既有B1 units + 11既有完整审计tests + 10既有data/spatial tests。测试未读取raw source或2025，不创建optimizer、不执行backward；临时NetCDF fixtures已清理。此数量不是全部历史训练suite的声明。另有20项unit preflight及6项sample-set preflight通过，不计入最终suite重复计次。清单preflight最初因TestCase属性run覆盖测试方法而未执行；已改名重跑，失败记录单独保留，未修改真实拟合代码。

## 最终状态

```text
B1_DESIGN_FROZEN=true
B1_MISSING_POLICY_FROZEN=true
B1_SAMPLE_SETS_FROZEN=true
B1_NORMALIZATION_FROZEN=true
B1_FAIRNESS_PRIMARY_SAMPLE_SET_FROZEN=true
B1_TRAINING_PROTOCOL_FULLY_FROZEN=false
B1_TRAINING_AUTHORIZED=false
B1_TRAINING_STARTED=false
B0_MATCHED_CONTROL_TRAINING_AUTHORIZED=false
B0_MATCHED_CONTROL_TRAINING_STARTED=false
2025_FINAL_TEST_EXECUTED=false
2025_MODEL_INFERENCE_SCENES=0
2025_PIXELS_READ=0
MODEL_PARAMETERS_UPDATED=false
MODEL_FORWARD_CALLS=0
MODEL_CHECKPOINT_LOADS=0
OPTIMIZER_STEPS=0
BACKWARD_CALLS=0
```

FROZEN：本轮批准的设计 / M1 / 样本集合 / B1 shared scaler / primary comparison集合。
NOT_YET_FROZEN 与 RESEARCHER_DECISION_REQUIRED：未批准的具体训练参数和 matched-control scaler。完成后STOP，不自动启动训练或Final Test。

完整证据入口：scientific_freeze_manifest.json、sample_set_freeze.json、normalization_execution.json、closure_test_summary.json；SHA256见 delivery_artifact_sha256.json。源码：scripts/freeze_b1_science_v1.py、src/yuntapr/data/b1_scientific_freeze.py、tests/b1_scientific_freeze/。本轮未生成图表。
