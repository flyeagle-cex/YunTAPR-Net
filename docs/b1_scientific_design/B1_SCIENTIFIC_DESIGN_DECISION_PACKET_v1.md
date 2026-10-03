# B1 Scientific Design Decision Packet v1

**六时相、顺序、tensor 和本轮审计定义已获研究者批准；完整 2023/2024 时相审计已执行。B1 整体科学设计仍未冻结：缺帧政策、normalization、公平比较样本集合必须由研究者决定。**

Baseline `4286f8151fea2185c99b3cea0c8e532e8cd90070`；独立 run `run_20261003T035724_142784Z`。1802 个历史文件保持原字节；未改写 B0 证据。2025 outcome 继续封存：本轮 2025 raw 像元、模型推理 scene、Final Test 均为 0/false。未打开任何 raw IMERG、checkpoint 或 2 月卫星源文件。

原始 B13 读取 run `run_20261003T024550_523841Z` 在完整读取及生成所有 QC/集合文件后，最终状态登记遇到 CLI string/Path 类型错误。本轮独立 closure `run_20261003T035724_142784Z` 对原 run 作完整 hash 快照并保存执行代码，复制的是 QC/身份 metadata，复算所有集合后关闭；原失败记录没有覆盖，未重读任何原始像元。修正的 CLI 明确将 definition 解析为 Path。原 audit-hook 终态 counter 因登记错误未写出；staging 实测 source read counter 完整保留，独立 closure 原始源读取为零。

## FROZEN：研究者批准的时相与输入合同

研究者原答复：**批准该时相与审计定义；其余决策保持待定（推荐）**。批准记录保存于 `candidates/run_20261003T035724_142784Z/researcher_slot_approval.json`。此批准固定本轮 audit，不授权 B1 training，不能使尚未决定的政策自动生效。

T 为已有科学合同冻结的 IMERG 窗口起点；A=T+30min。每帧唯一 expected nominal 固定为 A−[60,50,40,30,20,10]min，最旧→最新，对应通道 0→5。

|输入通道|精确 nominal|预期扫描桶（仅诊断）|
|---:|---|---|
| 0 | A−60 min = T-30 min | [A−60 min, A−50 min) |
| 1 | A−50 min = T-20 min | [A−50 min, A−40 min) |
| 2 | A−40 min = T-10 min | [A−40 min, A−30 min) |
| 3 | A−30 min = T+0 min | [A−30 min, A−20 min) |
| 4 | A−20 min = T+10 min | [A−20 min, A−10 min) |
| 5 | A−10 min = T+20 min | [A−10 min, A) |

输入合同 `[B,6,501,501]`：axis 1 是六个有序 B13 时相，不是六个 AHI 波段；不使用第五维 time axis。native latitude 仍降序、longitude 升序，继承精确 SP04 坐标；没有 transpose、silent flip 或重新生成坐标。normalized dtype/数值尚需 normalization 决策后在正式实现中明确，本轮不创建训练 tensor。

逐帧记录 nominal、真实 CF `obs_start`、`obs_end`、`date_created`。硬因果约束是实际 `obs_start <= obs_end <= A`。nominal 本身不能证明因果；date_created 只登记，不作为 operational availability。预期扫描桶是 metadata 对照，不产生新增自动剔除标准，也不声称本轮完成实时回放。

范围首端：每年 3 月 1 日 00:00 target 的前三槽落在 2 月，均单列 `OUTSIDE_AUDIT_SCOPE`；两年共 6 个槽、2 个 target。未读 2 月，不把它当作已证实 missing，也不擅自冻结正式拒绝政策。10 月 31 日最后 target 的 analysis_time 可到 11 月 1 日 00:00，但全部六槽 nominal 仍在允许的 10 月范围内。offsets 不依可用率改变。

定义 SHA256：`b6887a59900aa2f736cec4ab0d8727511e59eb9fc4e0418ebcb7d71778cd66d4`。

## 本轮真实 audit 结果；集合均未升格为正式 B1 supervision

这次重新只读读取当前 H 盘 B13：70,560 个预期原生 nominal、23,520 个日历 target、141,120 个 scene-slot 记录。每个可用文件复制到独立 English staging，逐文件核对原始/staged 大小与 SHA256，读取 B13 的 packed validity 和真实 CF 时间，输出标量 QC 后清理副本。每个原生帧只读一次 B13 解码；共享帧可以被多个 scene-slot 引用。

|角色|日历 targets|B0 原始 eligible|六槽文件均 present|六槽 full-valid 且 causal|B1 候选 eligible|与 B0 交集候选|不满足或未解决候选条件|
|---|---:|---:|---:|---:|---:|---:|---:|
| 2023_TRAIN | 11760 | 11720 | 10502 | 10455 | 10455 | 10455 | 1305 |
| 2024_VALIDATION | 11760 | 11727 | 10545 | 10501 | 10501 | 10501 | 1259 |

`all_6_slots_present` 只表示文件存在，不表示 readable/full-valid/causal。六槽 full-valid causal 集合再结合已固定 2023/2024 target-validity 证据中 `valid_yunnan_count>0`，得到 B1 **候选** eligible。target 部分有效时继承既有逐像元 mask；本轮不新增目标全有效要求。B0 原始 eligible 集合使用原 manifest 的逐值身份，不受这次候选筛选改写。

新 CSV 以规范 UTC window_start 作为 sample_id；原 manifest 的全部原始字段、SHA 和文件保持不变。day_path、IMERG index 和 analysis_time 的跨表联结另作逐值测试。

缺帧政策未冻结时，完整六槽/full-valid/causal 是审计分类条件，**不是已批准的 Formal B1 rejection rule**。候选集与交集 CSV 明确带 NOT_FORMAL / NOT_PRIMARY_FROZEN 标签。


### 2023_TRAIN

| slot | lag min | missing | unreadable | partial | all-fill | metadata | noncausal | outside-scope | bucket deviation (diagnostic) |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 0 | 60 | 66 | 1 | 17 | 7 | 0 | 0 | 1 | 0 |
| 1 | 50 | 543 | 0 | 14 | 11 | 0 | 0 | 1 | 0 |
| 2 | 40 | 26 | 0 | 14 | 0 | 0 | 0 | 1 | 0 |
| 3 | 30 | 66 | 1 | 17 | 7 | 0 | 0 | 0 | 0 |
| 4 | 20 | 543 | 0 | 14 | 11 | 0 | 0 | 0 | 0 |
| 5 | 10 | 26 | 0 | 14 | 0 | 0 | 0 | 0 | 0 |

### 2024_VALIDATION

| slot | lag min | missing | unreadable | partial | all-fill | metadata | noncausal | outside-scope | bucket deviation (diagnostic) |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 0 | 60 | 51 | 0 | 16 | 7 | 0 | 0 | 1 | 0 |
| 1 | 50 | 541 | 0 | 14 | 10 | 0 | 0 | 1 | 0 |
| 2 | 40 | 20 | 0 | 13 | 0 | 0 | 0 | 1 | 0 |
| 3 | 30 | 51 | 0 | 16 | 7 | 0 | 0 | 0 | 0 |
| 4 | 20 | 541 | 0 | 14 | 10 | 0 | 0 | 0 | 0 |
| 5 | 10 | 20 | 0 | 13 | 0 | 0 | 0 | 0 | 0 |


multi-reason 不采用单一优先级覆盖：逐 target 保留各槽独立原因；完整组合和 incidence 列表见 [真实审计报告](../b1_temporal_audit/runs/run_20261003T035724_142784Z/B1_TEMPORAL_DATA_AUDIT_REPORT_v1.md) 和 `temporal_availability_summary.json`。bucket deviation 只作诊断；outside-scope 与 missing 严格分开。

## 固定 B0 继承范围与参数公平性

B1 唯一主要信息增量：single-time B13 → multi-temporal B13。继承 4-level residual U-Net 48→96→192→256、decoder、SP04 feature projection、target、云南行政区 mask、occurrence head、32 conditional quantile head、probability semantics 与 loss family。不得加入其它 AHI 通道、GFS、DEM、DOTE、DTFM、MEE、ERA5 teacher、attention、Transformer 或 recurrent 模块。

实际隔离 CPU fixture 参数计数：B0 **4,329,361**；仅修改输入残差块的六通道候选 **4,331,761**；增加 **2,400（0.055435%）**。仅 `enc0.conv1.weight` 增加 48×5×3×3=2160，`enc0.skip.weight` 增加 48×5×1×1=240；其它 72 个参数张量名称、shape、数量不变，bias/GroupNorm/decoder/heads 不变，skip 零初始化继承。

已用 `scripts/count_b1_frontend_candidate_v1.py` 独立重放计数。fixture 无 checkpoint、forward、backward、optimizer，结束后销毁并恢复 RNG。没有提供 callable Formal B1 model 或 training runner，也没有复制/恢复 B0 模型参数。

## RESEARCHER_DECISION_REQUIRED：缺帧与无效帧政策

候选 **M1（未选择）**：任一 required slot missing / unreadable / partial / all-fill / metadata/time/grid invalid / noncausal，则整 scene 不进入 Formal B1 supervision，保留全部 slot-level 原因。M1 延续 B0 full-scene-required 输入语义，便于控制信息增量，但不能由本轮 audit 自动决定。

若研究者选择保留 partial，必须在另一次明确批准中定义输入有效性 mask、feature 处理和公平性控制；本轮没有实现该路线。首端 OUTSIDE_AUDIT_SCOPE 也需明确覆盖边界政策，不能把未读 2 月伪称 missing。

所有路线都禁止代码静默 older fallback、nearest frame、duplicate、zero placeholder、interpolation；缺测不代表物理零值。正式输入有效性政策未决定前，不启动 B1 supervision/training。

## RESEARCHER_DECISION_REQUIRED：Normalization A/B

|候选（均未选择）|科研公平性、物理意义与 B0/B1 可比性|必须明确的子决策|
|---|---|---|
|A：所有六 slot 共享 2023 Train-only B13 mean/std|相同 Kelvin 共用零点和尺度，跨时相 normalized 差值保持物理温差比例，较少引入 lag-specific preprocessing 因素|复用既有 B0 Phase-A scaler，还是最终 B1 Train 集合上的 pooled scaler；unique-frame 或重复 scene-slot 计权|
|B：逐 slot 独立 2023 Train-only mean/std|允许各 lag 样本分布各自中心化；同一 Kelvin 在不同 slot 得到不同 z-score，可能混入尺度/中心差异，给 B0→B1 比较增加处理因素|每个 slot 的拟合集合、计权、保存六组 scaler 身份，以及公平比较中的说明|

禁止使用 2024 Validation 或 2025 拟合。B0 Phase-A 2023-only mean=271.7078191073734 K、std=19.896814653342556 K 仅可作为 A 的复用候选；未自动选用。Phase-B normalization 包含 2024，不可用于 B1 development。实际候选 availability 不用于事后选择 A/B。本轮未计算任何新的 mean/std、histogram 或 normalization fit。

## RESEARCHER_DECISION_REQUIRED：公平比较集合

已保存每年三个 identity-only CSV：`b0_original_eligible_YYYY.csv`、`b1_candidate_eligible_YYYY.csv`、`intersection_candidate_YYYY.csv`。I_y=E_B0,y∩E_B1-candidate,y。原 B0 manifest 与历史指标不变；E_B1-candidate 仍待缺帧政策批准后才可正式化。

候选 **F1（未选择）**：primary B0-vs-B1 comparison 使用 common 2024 intersection，未来另获授权后只读重算 B0/B1 并保存独立结果；各自原 eligible 集合结果保留为次要描述。共同评价集合控制评价样本组成，**不能自动消除训练集合不同的 confounding**。是否另外建立 common 2023 Train 的匹配训练控制需研究者决定。

候选 **F2（未选择）**：primary 使用各自 eligible 集合，必须说明不同评价集合不能视为严格 paired 信息增量比较。不得依据后续 2025 结果挑选 F1/F2。本轮没有 B0 重新推理、checkpoint load、重训练或 B1 训练。

## 证据、测试与 I/O 成本

历史 1802 个文件逐字节 SHA256 和 Git blob identity 全部核验不变。原 target-validity 和 B0 original manifest 来源：

- `docs/b0_pretraining_closure/runs/run_20260930T095416Z/formal_sample_eligibility_2023_2024.csv`: `b4bad8ea45a78eddae3832df89cfade00cac3b184fc550eea4f0cf479c29de90`
- `docs/b0_pretraining_closure/runs/run_20260930T095416Z/normalization_phaseA_sample_manifest.csv`: `dc0559f12f02817f8ec74916d03dd20e40ec0584ec58c59b34b5e02cc9a60e68`
- `docs/phase_a_protocol_prefreeze/runs/run_20261001T014523Z/eligible_validation_manifest.csv`: `ac5405d8185d6760acc15a4ab364804c1d8ec8de84064737d0757f6688aeb410`

新 native frame identity index SHA256：`a5054200d6bde11f2342c292ca72428d0558d5b5c5c640017844f0b4ed8c540e`。它绑定 16 个逐月 native QC CSV；每个 present 源文件登记 bytes/SHA，六槽表通过 expected_nominal 联结。population 行绑定同一 frame-index SHA；final_status 另登记六槽和集合 CSV SHA。

原盘 source-copy read / staging write 各 306,101,365,884 bytes（285.079 GiB）；额外原盘 SHA read 306,101,365,884 bytes。copy_seconds=967.487，read/QC_seconds=649.401；staging peak=636,106,619 bytes（606.639 MiB），cleanup_success=true。staged SHA 读取和文件系统开销也包含在总 elapsed=2250.931 秒；这不是只计 native netCDF read 的性能数字。没有持久复制整月/全量原 nc；只删除本流程自己的暂存文件。

closure 实际 40 tests，全通过、无 skip：19 B1 synthetic/guard/reader、11 full audit artifact、10 相关既有 data/spatial regression。没有宣称执行全部历史训练 suites。首次测试异常类型断言和 Temp ACL fixture 失败记录保留；修正测试工程问题后重测通过，失败 fixture 已清理。测试本身不打开原始源，closure raw opens=0，2025 pixels=0，optimizer/backward=0。

## NOT_YET_FROZEN 与最终状态

缺帧政策、normalization 和 primary fairness population 均 **RESEARCHER_DECISION_REQUIRED**；整体 `B1_DESIGN_FROZEN=false`。本包没有授权下一个阶段。

```text
B1_DESIGN_FROZEN=false
B1_SLOT_DEFINITION_FROZEN=true
B1_TENSOR_CONTRACT_FROZEN=true
B1_TEMPORAL_AUDIT_EXECUTED=true
B1_MISSING_POLICY_FROZEN=false
B1_NORMALIZATION_FROZEN=false
B1_FAIRNESS_PRIMARY_POPULATION_FROZEN=false
B1_FORMAL_MODEL_IMPLEMENTED=false
B1_TRAINING_STARTED=false
B1_NORMALIZATION_FITTED=false
2025_FINAL_TEST_EXECUTED=false
2025_MODEL_INFERENCE_SCENES=0
2025_RAW_PIXELS_READ=0
MODEL_CHECKPOINT_LOADS=0
MODEL_FORWARD_CALLS=0
OPTIMIZER_STEPS=0
BACKWARD_CALLS=0
```

完成本轮审计后停止；不开始 B1 training，不执行 B0 2025 Final Test。附同名 editable `.tex` 与 `.pdf`；这是最终审计数据支持的决策包，不是训练协议。
