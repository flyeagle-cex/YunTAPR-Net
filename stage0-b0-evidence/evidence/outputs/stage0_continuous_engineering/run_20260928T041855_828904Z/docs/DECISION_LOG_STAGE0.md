# Stage-0 decision log

本记录区分研究者规则、工程观测事实、候选方案和缺口。FROZEN / engineering-evidence supported 表示以下指定工程规则与已审计来源事实，不宣称未来所有数据产品永远相同。

## FROZEN / engineering-evidence supported

- 已审计 IMERG 为 V07B Final，GPM_3IMERGHH_07；每文件 48 帧、30 min 间隔；实际坐标约 0.1°，作为目标网格的现有证据。
- 0 != missing；缺测须显式 mask/标记，不填 0，不插值。
- Himawari 固定 IR 08/09/10/11/13/15/16 七通道。
- six causal nominal slots：相对于 analysis_time 的 −10/−20/−30/−40/−50/−60 min；不得引入未来帧；窗口与 analysis_time 的具体绑定仍需下述 PROVISIONAL 语义确认。
- obs_end <= analysis_time 是物理观测因果约束。nominal_time、obs_start、obs_end、date_created、availability_time 分列。
- F/H 原始数据只读。旧 P0、Himawari dry-run（包括 DRY_RUN_FAILED 历史）、manual lesson、diagnostic cache 不覆盖。
- GFS 降水相关变量禁止作为 predictor；不以 MSLP 替换 surface pressure，不以 specific humidity 自动替换 RH。
- p99 is a distribution-tail review marker only; it is not an exclusion criterion, QC threshold, or scientific threshold.
- date_created < obs_end 为独立 TEMPORAL_ORDER_ERROR；creation_delay >= p99 仅 LATENCY_TAIL_REVIEW。原始 delay 保留，尾部样本不删除、排除或修改。

## PROVISIONAL

- converted daily IMERG time coordinate 对 native 半小时窗口的具体语义；当前 [T,T+30min)、analysis_time=T+30min 是候选绑定。
- date_created 作为 availability proxy 仅为待研究者评估的候选；事实身份是 product/file creation timestamp。本轮未采用它筛选正式样本。
- 部分 GFS 文件中的 conservative_available_time_utc=init+5h 是上游写入的保守假设，availability_note 明示不是 observed per-file publication。本轮保留原值，不把它作为本项目已批准规则。
- 以磁盘上观测到的 init hours/lead union 构建日历月缺口表，是工程诊断参考，并非冻结的 required forecast schedule。

## NOT_YET_FROZEN

- model_input_bbox；covers_yunnan_context=PENDING_RESEARCHER_CONFIRMATION。
- Himawari/GFS actual operational availability time。
- GFS vintage rule，包括来源、发布延迟、选取与时间对齐。
- 正式 Train/Val/Test 精确块；32 quantile levels。
- SRTM 值域/void mask 与行政评价 mask 的网格化及边界处理规范。

## DATA_GAP / evidence limitations

- IMERG 2025-10：旧全库截止 2025-09-30，本轮定向文件名检查仍为 0；保持研究候选 2023–2025 年 3–10 月，不自动缩短。
- GFS 2025-03~10 是否缺失以本轮磁盘 inventory 与月矩阵为准，不能沿用“仅到 2024”的文档假设。文件覆盖与 T/RH 等变量覆盖分开。
- 主目录部分文件缺少必需 T/RH，实际数量见 GFS/gfs_variable_coverage.csv；补充 GFS_thermo 未自动合并。
- 已找到 GADM41 云南多边形，但模型网格上的云南评价 mask 尚未建立/验证；状态 PARTIAL，不把 polygon 文件存在写成 mask READY。
- SRTM 237 个瓦片目录证据存在，包络内缺 3 瓦片；实际 DEM 像元/空洞未审计，详见空间报告。
- independent external validation：NOT_AUDITED；本轮没有证明它已准备，也不因未审计而断言原始文件不存在。
- H 全库月内容未重扫；2024-07 复用已完成证据，其他研究月目录存在性不等于 READY。

## RESEARCHER_DECISION_REQUIRED

详见根目录 RESEARCHER_DECISIONS_REQUIRED.md。主要包括 native IMERG 窗口、availability/vintage、GFS 主辅目录与核心变量缺口、陈旧辅助时间 metadata 的来源追溯、bbox/行政 mask、2025-10 IMERG 与独立验证准备。工程审计完成不意味着这些科学约定已冻结。

## 本轮补充约束

IMERG QI 仅 QC_STAT_ONLY；不设 QI threshold、不筛像元、不作为 predictor、不据此作科研结论。极值排名不是异常标签。2025-10 不属于当前 IMERG 库存区间内部 missing-day，但属于候选研究期缺月。

本轮 TASK A–P 证据已更新。engineering_status=PASS 与 researcher_review_status=NEEDS_REVIEW 分列；工程交付完成不自动解锁科研 closeout 或 Stage1/B0。
