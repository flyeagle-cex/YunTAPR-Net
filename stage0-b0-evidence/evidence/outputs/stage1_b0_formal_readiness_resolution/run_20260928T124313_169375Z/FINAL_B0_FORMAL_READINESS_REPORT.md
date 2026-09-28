# YunTAPR-Net — B0 Formal Readiness Resolution

**结论：B0_FORMAL_NOT_READY。** 本轮证据与决策包完成，30 项定向测试通过；正式入口仍有 12 项 blocker。旧 B0 Engineering Smoke 仍为 PASS，未重跑或修改。正式训练未开始，完成后停止。

Run：`F:\pytorch\Research\outputs\stage1_b0_formal_readiness_resolution\run_20260928T124313_169375Z`。固定解释器、真实版本、只读边界和完整日志见 README.md 与 logs/。全部候选由脚本实际计算并保存，没有把 NOT_RUN/NOT_AUDITED 当成 PASS。

## 1. 已解决的工程证据

- **时间证据增强**：发现原生命名缓存 122 个，小范围尝试 12 个文件。9 个 Final 原生/Harmony 子集均保存 time_bnds，time 等于下界，时间窗1800秒；与同日 converted CF 时刻相等。完整原生成脚本缺失，逐 granule→slice 身份/顺序未证实；正式绑定仍未冻结。详见 [时间证据](TIME/B0_FORMAL_TIME_SEMANTICS_EVIDENCE.md)。
- **缺口确认**：扩大 C–H 全盘文件名发现，但存在251个访问错误和1959个跳过目录。已知 Final root October 文件数0；发现31个 October Late 日文件，身份明确，未替代 Final；当前仍 MISSING。旧备份 archive 年份2021–2024，仅登记、未解包。不能推出官方当前不可获取该月。详见 [October决策卡](GAPS/IMERG_2025_10_DECISION_CARD.md)。
- **空间候选**：4 个候选使用真实坐标索引，均完整保留3430主评价中心；没有坐标重建、transpose、silent flip 或重采样。见 [空间决策](SPATIAL/B0_INPUT_DOMAIN_DECISION.md)。
- **split 候选**：3 组连续时间块，Train/Val互不重叠，仅2023/24，2025完全隔离；数量只是日历×48上界，未扣缺帧/因果/QC/buffer。见 [Train/Val决策](SPLIT/B0_TRAIN_VAL_DECISION.md)。
- **契约**：明确0!=missing、单帧B13、Train-only normalization范围与版本规则；没有拟合真实统计。正式partial/QC、normalization方法、架构和loss/output仍待批准。

|空间候选|native rows,cols|target rows,cols|主评价 cells|
|---|---|---|---|
|SP01|[408, 435]|[82, 87]|3430|
|SP02|[433, 460]|[86, 92]|3430|
|SP03|[458, 485]|[92, 97]|3430|
|SP04|[501, 501]|[100, 100]|3430|

|split候选|Train名义槽位|Val名义槽位|
|---|---|---|
|TV01_YEAR_HOLDOUT|11760|11760|
|TV02_2024_JUL_OCT|17616|5904|
|TV03_BOTH_OCTOBERS|20544|2976|

以上均无 winner。空间 margin 和 stride 16/32 的假设 padding 数在 CSV，不代表模型层级或padding方案已选择。

## 2. FROZEN

继承而未修改：2023–2025 每年 March–October；Development为2023/24，FinalTest为2025；GADM4.1 Level-1 Yunnan（CHN.30_1，五项身份字段均承接已批准registry）；真实IMERG目标坐标；center-in-polygon主评价mask=(130,140)，3430cells；obs_end<=analysis_time；0雨与missing分开、原始数据只读、不得未来卫星帧。主mask SHA256：`9d921def661fc3e58cd1ed783fcf87abbf493da6ae5e5fea79c28043f73495ef`。intersection mask 保留为非主评价比较。

冻结规则的引用不表示全研究期数据完整，也不表示全部正式入口已就绪。B13 reader接口可复用既有PASS，但其他月份数据资格仍需验证。

## 3. NOT_YET_FROZEN / NOT_ESTABLISHED

正式IMERG–Himawari时间绑定、analysis时刻与单帧选法；model_input_bbox和天气context；Train/Val blocks及buffer/事件隔离；正式partial/missing/QC接受协议；Train-only统计方法/统计域和参数；native-to-target对齐；正式B0层级、概率头是否首版、loss/output/校准/评价与重复设计。原转换链全库映射及联合可用样本数为NOT_ESTABLISHED。除July2024外Himawari研究月资格为NOT_AUDITED，不能视为缺失或通过。

`normalization_rule_defined=true` 仅表示本轮已定义Train-only防泄漏范围规范；`normalization_method_frozen=false`、`normalization_statistics_computed=false`。没有自动把正式B0定义成确定性回归。

The cross-source IMERG-Himawari time binding used in this B0 smoke run is provisional and was used only to test the engineering pipeline. It is not a frozen scientific sample timing convention.

date_created 只记录，未建立 operational availability，未声称完成历史实时回放。

## 4. RESEARCHER_DECISION_REQUIRED

详见 [10张决策卡清单](RESEARCHER_DECISIONS_REQUIRED.md) 与 [16项入口矩阵](B0_FORMAL_ENTRY_MATRIX.csv)。矩阵4项规则/接口已满足、12项仍阻塞；同一科学决策可覆盖多个矩阵项。主要待决：时间绑定、October Final缺口、输入域/context、Train/Val及buffer、missing/QC、normalization方法、正式架构/概率头、loss/output/空间对齐与后续多月数据资格安排。

October三条路径：A批准补齐同版本Final；B显式修订研究期；C研究者另定方案。没有自动下载、缩短研究期或用Late替代。GFS/GFS_thermo/vintage、DEM、DOTE、DTFM、MEE、ERA5 Teacher不属于B0必需输入blocker。

## 5. 验证与可追溯性

最终 pytest：30 passed，0 failed/errors/skipped。测试涵盖候选不冻结、2025隔离、连续块不重叠及反例拒绝、真实坐标/冻结mask、zero/missing、Train-only拟合角色、旧证据完整性、单文件staging与双格式一致性。测试只验证契约与工程证据，未重复Dataset→Tensor→Model链，也未测试模型性能。

首轮29passed/1failed保留：CSV默认解析器对浮点尾数舍入，改用round_trip后严格逐值比较通过，没有改源坐标。第一次构建因discovery脚本字节换行差异中止，也保留原快照与修复说明。12个native尝试中的一个Late缓存报unknown format，失败未掩盖，不纳入9个Final有效证据。见 tests/ 和 logs/recovery_notes.json。

旧smoke manifest的120项、其manifest本身与Stage0冻结/审计锚点共135条保护记录，加新增来源合并162个文件，最终size/mtime/SHA全不变。只读输入只在本轮英文staging复制并清理，所有原始与旧缓存保留。证据hash见 evidence_registry.csv/.parquet，脚本hash见 PROVENANCE/generator_script_hashes.csv/.parquet。输出总清单见 output_manifest.csv/.parquet（不自包含这两个manifest）。

本轮没有正式mean/std、真实split实例分配、模型训练、数据重采样、GFS/DEM处理或DOTE特征；不自动进入下一Stage。

B0 formal-readiness resolution package complete.
The prior B0 engineering smoke remains PASS and unchanged.
No formal B0 training was started.
No provisional timing or spatial convention was silently frozen.
All remaining formal-entry decisions are explicitly assigned to the researcher.
