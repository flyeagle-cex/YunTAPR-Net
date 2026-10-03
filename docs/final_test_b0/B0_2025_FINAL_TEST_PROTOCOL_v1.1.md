# B0 2025 Final Test protocol v1.1

本版本只修正样本目录 schema、两阶段授权顺序和测试结果泄漏防护。科学基线为 `299d3f1080840b24db3ba6fe39684a1e6bca530a`；经研究者批准，从当前 main `65e1086bc2f0d830a6f45e01253b4ccffcae1130` 继续，保留术语修订。v1 YAML、报告和 preflight 证据全部保持原字节。

## 冻结身份与科学继承

权威文件：`config/evaluation/b0_2025_final_test_protocol_v1.1.yaml`。

v1.1 SHA256：`b1be82d5bc03293c35ddc793faa1187e97fa48c537039181c0eb68a689f15eb8`。

父协议 SHA256：`6d08def2602dda3d931937c68cadeae86b5c16b60f9f7132c9e134b962cdbe3b`。

程序逐项比较十个科学定义子树与 v1：`FINAL`、`identity`、`normalization`、`population`、`primary_metrics`、`metric_definitions`、`inherited_diagnostics`、`diagnostic_declarations`、`inference`、`prohibitions`。任何差异均拒绝；全部沿用 v1，绝不根据 2025 结果调整。

| 项目 | 原样继承的定义 |
| --- | --- |
| FINAL | Phase-B epoch 011；11 epoch / 128964 updates；仅只读，不选择 epoch |
| FINAL 本地位置 | `F:\pytorch\Research\outputs\formal_training\b0_phase_b_finalfit\run_20261002T035929_487644Z\epoch_011.pt` |
| FINAL SHA256 | `05359d2fee2ae61daf654ae5a59b7977cb65247fd46d97a69a690a0133da7f65` |
| normalization | mean=270.5900486586461 K，std=20.368583874067266 K；不得 refit |
| normalization SHA256 | `c7042beac2412594ca9fc264d7df10981755b393158c539cb48c9b56cd314327` |
| 测试时间 | UTC `[2025-03-01 00:00, 2025-10-01 00:00)`，30 分钟，共 10272 个计划槽位 |
| 资格 | expected latest B13=T+20min；obs_start≤obs_end≤T+30min；B13 501×501 全有效且有限；IMERG V07 Final 时间、网格与独立 provenance 通过；云南监督有效像元数>0；不允许 older fallback |
| 部分有效监督 | 不要求每景 3430 个像元全部有效；使用有效 IMERG 与冻结云南 mask 的交集 |
| 评价边界 | GADM 4.1 云南 center-in-polygon，精确 SP04 目标坐标，无 transpose/flip |
| 顺序 | 固定时间和 sample_id 顺序；每身份一次，无 shuffle/drop/padding/replacement |
| 数值 | float32 降水与 float32(0.1) 比较后再转 FP64；32 τ=(i−0.5)/32；数值违规 STOP，无修复 |
| 全样本指标 | global core loss、occurrence loss、quantile loss、Brier、AUROC、Average Precision、conditional mean pinball、per-tau pinball、32 tau coverage、coverage error、crossing/nonfinite/support counts |
| 汇总 | 按全体有效像元累加分子/分母，禁止平均 batch loss；同分概率精确分组 AUROC/AP；未定义指标为 null 并附原因 |
| 诊断 | 原样继承 2024 monthly/spatial/case/reliability、rain-rate descriptive bins、quantile groups 和 DIAGNOSTIC_PROXY |
| 描述区间 | (0.1,1]、(1,5]、(5,10]、(10,20]、(20,30]、(30,50]、(50,∞)；10/20/30/50 exceedances 仅描述用途 |
| reliability | 固定 0.1 间隔 bins；边界进右箱，最终箱含 1；不做 recalibration |
| case | 三类冻结规则各 top10；固定 scene 顺序及 row-major cell index 打破并列 |
| POD/FAR/CSI | `THRESHOLD_NOT_FROZEN`，不得在 2025 选择阈值 |

禁止训练、backward、optimizer、参数更新、normalization refit、temperature scaling、isotonic/Platt calibration、threshold tuning、checkpoint/epoch selection、architecture/loss/LR 修改、2025 October、B1-B8。9 月 30 日 23:30 的窗口允许；窗口结束为 10 月 1 日 00:00，来源仍只能为 9 月。

## 无结果信息的 catalogue

候选 CSV 固定 28 列、固定列顺序，拒绝缺列、额外列、重复 header、嵌套值、非法元数据值。产品字段只能是验证后的枚举或空值；观测时间必须为空或合法 UTC 时间；path/time/size/hash/count 逐项校验。拒绝行同样受严格白名单约束，rejection_reason 只来自冻结的资格枚举，禁止原始异常文本。

```text
candidate_index,window_start,analysis_time,sample_id,expected_nominal,
b13_relative_path,b13_bytes,b13_sha256,expected_latest_available,b13_readable,
b13_metadata_valid,full_valid_native_pixels,b13_finite,obs_start,obs_end,
selected_nominal,used_older_causal_frame,imerg_day_path,imerg_bytes,imerg_sha256,
imerg_product,imerg_version,imerg_run_type,imerg_time_grid_provenance_pass,
imerg_index,imerg_valid_yunnan_count,eligible,rejection_reason
```

`b0_2025_final_test_population_manifest_v1.csv` 只包含 eligible 行的下列 12 个身份字段，且必须逐值等于候选目录 eligible filter 的固定顺序投影：

```text
candidate_index,sample_id,window_start,analysis_time,expected_nominal,
b13_relative_path,b13_bytes,b13_sha256,imerg_day_path,imerg_bytes,imerg_sha256,imerg_index
```

禁止 `imerg_rain_yunnan_count`、rain occurrence/prevalence/intensity/bin/exceedance 统计、loss、Brier、AUROC、AP、pinball、coverage、probability、quantiles、DIAGNOSTIC_PROXY 和任何预测结果或未知别名。IMERG 解码值仅在 validity 检查的局部作用域存在，不返回降水值或结果统计。`date_created` 仅检查可解析性，不作为 operational availability；不进入 catalogue。

## 第一阶段：独立 catalogue-only 授权

scope 必须为 `B0_2025_FINAL_TEST_CATALOGUE_ONLY`。本次发布没有给予该授权。

研究者授权文件必须绑定 v1.1 协议 SHA、当前实现 SHA 映射、冻结 H/IMERG 原始 roots、独立 completion manifest 路径和 SHA、创建 UTC；明确 `FINAL_TEST_CATALOGUE_AUTHORIZED=true` 且 `FINAL_TEST_2025_AUTHORIZED=false`。精确 schema 见 `CatalogueAuthority.load`。授权元数据不能指向 raw/checkpoint；completion manifest 限制在 IMERG root 或其 manifests 目录的 JSON/JSONL，拒绝 raw NC、月份目录与重定向。

授权后仅允许逐槽 existence/size/SHA/time/causality/full-valid/provenance/valid-mask QC。English staging 只复制一个文件，验证 size/SHA，并仅清理自己创建的临时副本；IMERG 日缓存仅保留 48 个 validity counts 和来源身份。重复 expected nominal 文件会 STOP，不挑选替代文件。正式模型加载、实例化、forward、loss、metrics 均在此 scope 被阻断，包括已导入 aliases。

未来实际执行应生成全 10272 行 candidate CSV、eligible identity CSV 和独立 `catalogue_freeze_record.json`；登记两个 CSV SHA、实际 eligible/rejected counts、固定 reason counts、实现/协议/授权 SHA、freeze UTC 和受控 raw-access telemetry。失败保留实际访问事实，禁止将失败访问重置为零。输出目录必须为新建目录，不向旧目录写失败记录。

## 第二阶段：freeze 后另行 Final Test 授权

scope 为 `B0_2025_MAR_SEP_FINAL_TEST_ONLY`。单独研究者授权必须在真实 catalogue freeze 完成之后创建，绑定：protocol SHA、implementation SHA 映射、FINAL SHA、normalization SHA、candidate CSV SHA、eligible identity CSV SHA，以及额外的 freeze-record SHA。fixture freeze、目录计数不一致、非零 inference/metrics/outcome exposure、SHA/日期/字段错误均拒绝。

runner 先核验同一字节快照，再解析并冻结授权和两份 CSV；之后不重新读取路径来替换样本集合。dataset 必须等于授权快照的 eligible 集合。两阶段均不得相互替代；旧 v1 formal action 和旧 authorization loader 已永久拒绝，历史文档和证据原样保留。

正式授权后，才允许读取 FINAL、真实固定顺序推理和冻结的全样本评价。runtime rainy count 仅在授权 inference dataset 内生成，用于 runtime ledger/reconciliation，永远不回填 pre-authorization CSV。formal 读取、SHA/QC、因果或数值错误必须 STOP，不跳过或替换。

## 访问语义与本轮停止点

分别记录 `2025_CATALOGUE_QC_ACCESS`、`2025_FINAL_TEST_EXECUTED`、`2025_MODEL_INFERENCE_SCENES`、`2025_FINAL_TEST_METRICS_COMPUTED`、`2025_TARGET_OUTCOME_SUMMARIES_EXPOSED`。`2025_PIXELS_READ` 若出现，仅是 raw pixel-value telemetry，不能代替执行状态。未来 formal runner 对未完成读取报告实际 source-open events 和 completed-sample 下界，不冒充精确零读取。

本轮仅 synthetic schema/NetCDF fixtures；没有真实 catalogue、raw discovery/read、FINAL loading、model forward 或 metrics。真实 eligible/rejected 数量为 NOT_INSPECTED。完成 fixture preflight、报告与 GitHub main 提交后停止，等待独立 catalogue-only 研究者授权。

当前入口：`scripts/build_b0_2025_final_test_catalogue_v1.py preflight`；未来受授权 QC action 为 `catalogue`。第二阶段入口为 `scripts/test_b0_2025_final_v1_1.py run`；所有授权与两份 CSV/freeze-record 参数均须由后续研究者授权提供。本协议文件不是执行授权。
