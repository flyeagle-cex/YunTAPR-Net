# Stage-0 Final Gate / Researcher Decision Package

| Gate | 当前结论 |
|---|---|
| Stage-0 engineering | PASS：已授权审计交付及本轮证据汇总完成 |
| Stage-0 scientific full closeout | NEEDS_RESEARCHER_DECISIONS |
| B0 engineering smoke entry | READY：仅限非科研工程实现入口，B0 本身未运行 |
| B0 formal experiment entry | NOT_READY |

本包：`F:\pytorch\Research\outputs\stage0_final_gate_package\run_20260928T113745_449683Z`。当前批准仅覆盖 Final Gate package，完成即停止。

## 1. Engineering 是否完成

是，在既有授权任务范围内完成。9 个 run 登记（含早期 continuous 与 Himawari DRY_RUN_FAILED 历史）；95 项关键 fingerprint 检查一致。PASS 不外推成全部研究月或全部变量像元的有效性。Himawari 仅 2024-07 有完整月工程证据；其余 23 研究月 NOT_AUDITED。主库/thermo 的 metadata presence 不等于全像元 QC。

## 2. Scientific closeout 是否完成

否。当前 full scientific closeout 相关未决依赖共 7 项：D01, D02, D03, D04, D08, D09, D10。Stage-0 工程不再循环等待未来 B8 超参数；B0 专属实验协议和地形生产细节按其阶段处理。

## 3. B0 engineering smoke 是否可以开始

具备进入工程实现的证据：已审计 Himawari 七通道 reader、50 个真实 dummy loading 通过记录，以及已冻结目标 grid/mask 可供接口复用。B0 只取 B13 单时次。未来验证 Dataset → Tensor → forward → loss → metric → checkpoint → inference，所有中间检查须真实执行。**这条完整 B0 链路本轮 NOT_RUN**。

READY 限非科学 fixture 接口验证；空间/标签规则未定时，可在未来工程任务声明临时数组域和 synthetic/非科学 targets，不能伪装成真实监督配对或论文结果。如果要求立即用正式真实监督标签，须先满足相应 formal gate。本包没有创建 fixture、Dataset 或模型，也没有授权自动进入下一阶段。

## 4. B0 formal experiment 是否可以开始

否。正式 Train/Validation/Final Test 与论文实验需要满足 B0_ENTRY_REQUIREMENTS.md。2025 final test、2023–2024 development pool 与候选每年 March–October 保持；精确 Train/Val 块未冻结，2025-10 没有被自动删除。

## 5. 真正的当前 blocker

Smoke：在上述非科学工程范围内，无剩余科学入口 blocker；未来每个工程环节仍需实现和测试。Formal：10 个独立依赖：D01, D02, D03, D04, D05, D06, D07, D08, D13, E15。包括 October gap、native window/analysis_time、输入域/context、精确时间块、缺测/QC、Train-only 统计协议、Himawari availability 声明范围、正式概率实验协议及其他研究月工程证据。D03/D04 可联合 review 但记录为两个显式决定。此计数不是所有 category A 的简单总和：D01 主类 B 也阻塞 formal。

## 6. 与 B0 无关或可后置事项

GFS integration/vintage、DEM aggregation/terrain 参数、DOTE/DTFM/MEE 不属于 B13 单帧 B0 输入。44 LATENCY_TAIL_REVIEW 仅 INFORMATIONAL_REVIEW_ONLY。独立外部数据不要求在 B0 开始前全部下载。永久存储格式尚未冻结，但不是阻止一个小规模 smoke 的科学门槛。

## 7. B4 前必须解决

D09 main+thermo adoption 与来源局限处置、D10 release/vintage 规则；再在相应工程阶段验证 predictor 像元有效性和明确取样接口。当前 SUPPORTED_WITH_CAVEATS、PARTIALLY_COMPATIBLE、NOT_ESTABLISHED 原样保留。禁止 GFS precipitation predictor。init+5h、mtime、conversion/download time 均未自动作为 official release。

## 8. B5–B8 前必须解决

分阶段处理 D11：B5 elevation 聚合；B6 terrain 参数；B7/B8 gradient/DOTE 生产流程。SRTM 主来源与真实物理距离原则已冻结，AWS_Skadi 未拼接。没有要求现在冻结全部后期参数，没有生成正式地形特征。

## 9. 最终论文结论前必须解决

D12 独立观测数据选择、审计、独立性和匹配协议。当前 NOT_AUDITED，不等同 MISSING 或 READY。B0 可先规划相对 IMERG 的 baseline，但未有独立证据不能宣称全面改善真实降水；NRT operational 结论还须满足相应 availability/vintage 证据与获批解释。

## 10. 已冻结约定

16 条详见 FROZEN_CONVENTIONS.md：云南全境行政评价、GADM4.1 CHN.30_1、3430 中心格、真实 IMERG 130×140 坐标、源身份/频率、0!=missing、七通道/六因果槽及 obs_end、禁用 GFS precipitation、PS feasibility、SRTM、物理地形梯度、原始只读、p99 仅 review、2025 test 框架、QI 仅 QC_STAT_ONLY。冻结版本 `YunTAPR_STAGE0_SPATIAL_v1_run_20260928T102636_513428Z`。本轮没有新 freeze。

## 11. 数据缺口

7 项已确认的 data/metadata/provenance gap，见 DATA_GAPS.md；另 2 个未审计范围不计成已证明缺失。主库 T/RH 缺口有完整 companion candidate，不能描述成所有来源均无 T/RH。bbox/context 是决策，未混入 data gap。

## 12. Researcher decisions / schema

13 张卡，每张仅包含要求的 8 个栏目。分类 A/B/C/D 与 NOW、BEFORE_B0_FORMAL、BEFORE_B4、BEFORE_B5_B8、BEFORE_FINAL_PAPER 明确分列。R14 为 informational，E15 为工程证据。Formal sample schema：NEEDS_UPDATE，主要缺少分阶段 B0 profile、正式 spatial freeze/hash 引用、规则版本与 split/normalization/protocol provenance；仅描述字段空缺，未实例化任何样本。

## 13. Evidence conflict

95 项关键检查 CONSISTENT，0 个 EVIDENCE_CONFLICT_RESEARCHER_REVIEW。旧 candidate → 后续显式冻结、主库缺变量 → 辅库候选补齐、dry-run nominal/internal mismatch → P0 物理因果核验均按各自时点和判据解释，不改写历史。旧 tests/tmp 有访问限制，但所有必需状态/报告/manifest 和关键产物均已定向读取；未改 ACL。全量原始数据没有重新核验。

## 14. Tests and serialization

pytest：40 passed；failures=0，errors=0，skipped=0。真实输出 tests/pytest_final_output.txt 和 tests/pytest_final.xml。核验冻结证据、状态不升级、B0 两层依赖、实际 mask 指纹、历史失败保留、只读约束和 CSV/Parquet 精确回读。数据表使用 pyarrow CSV+Parquet 双格式；schema 明确采用字符串保存 CSV 原表示，类型化逻辑保存在 gate_assessment.json。未来 B0 未执行事项没有写成 PASS。

## 15. Raw and prior-run integrity

本轮 raw 文件读取/写入/目录扫描均 0；未执行旧脚本，未重生成 mask。48 个登记关键输入 size/mtime/SHA256 前后及测试后均一致；所有写入限新 run。此范围不是全 raw 或全部旧文件的逐字节证明。没有下载、安装/升级、归一化、split、插值、resampling、训练。旧 DRY_RUN_FAILED 与其他历史报告保留。输出 manifest 覆盖本包，不给自身作循环 hash。

Stage-0 final gate package complete.
Engineering completion and scientific readiness were evaluated separately.
No unresolved scientific decision was auto-frozen.
No Stage-1/B0 execution was started automatically.
All prior Stage-0 evidence runs remain unchanged.
