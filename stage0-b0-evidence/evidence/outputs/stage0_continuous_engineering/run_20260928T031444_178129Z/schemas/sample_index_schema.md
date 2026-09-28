# Future pairing index schema — definition only

本轮只定义接口，未生成任何正式模型样本、训练索引或 split。所有时间以 UTC、ISO-8601 或带 UTC 时区的 timestamp 表示；未知时间使用 null 并保留 status/reason，不得用 epoch、文件 mtime 或 init_time 替代。

| 字段 | 类型 | 规则与证据状态 |

|---|---|---|

| sample_id | string | 待配对规则冻结后生成稳定 ID；本轮不实例化 |
| schema_version | string | stage0-provisional-1 |
| imerg_file | string | 原文件只读路径及可选 source hash |
| imerg_start, imerg_end | nullable UTC timestamp | 候选 [T,T+30min)；converted daily coordinate 对 native granule window 的具体含义仍 PROVISIONAL |
| imerg_native_window_evidence_status | enum | PROVISIONAL / RESEARCHER_CONFIRMED / UNKNOWN |
| analysis_time | nullable UTC timestamp | 候选为 imerg_end；未确认窗口语义时不能将候选样本标为正式可用 |
| imerg_grid_hash, imerg_units | string | 保留源坐标 hash 与 mm hr-1；0 是有效零降水，不是 missing |
| imerg_validity_mask_reference | nullable string | 将来指向显式 mask；本轮不生成 |
| himawari_nominal_times | fixed list[6] UTC timestamp | 槽位顺序 analysis_time−[10,20,30,40,50,60] min；该顺序必须显式保留 |
| himawari_paths | fixed list[6] nullable string | 与槽位一一对应；跨日/跨月按真实路径查找；缺帧为 null，禁止未来帧补位 |
| himawari_obs_start, himawari_obs_end | fixed list[6] nullable UTC timestamp | 来自原 metadata；每个 obs_end <= analysis_time，否则物理因果不满足 |
| himawari_date_created | fixed list[6] nullable UTC timestamp | product/file creation timestamp，不等同实际 operational availability |
| himawari_availability_time | fixed list[6] nullable UTC timestamp | 无直接证据保持 null；与 date_created 分列 |
| himawari_availability_evidence | fixed list[6] enum | UNKNOWN / OBSERVED_OPERATIONAL / PROVISIONAL_PROXY |
| sequence_complete | bool | 六个规定槽位均有可读取文件且身份唯一；不能代替 QC 或 availability 审核 |
| channels | fixed list[7] string | 08,09,10,11,13,15,16；保留原始 K 值语义 |
| quality_flags | structured object | 显式区分读取失败、missing、时间逻辑、坐标冲突；未选科学 QC 阈值 |
| creation_delay_seconds | fixed list[6] nullable float | 原 date_created−obs_end 完整保留 |
| latency_tail_review | fixed list[6] nullable bool | 月内全部成功解析 delay 的 p99 分布尾标记；>= p99；不是排除条件 |
| latency_tail_reference_month, latency_p99_seconds | string, nullable float | 保存该标记参考分布；不将 2024-07 p99 自动跨月迁移 |
| temporal_order_error | fixed list[6] nullable bool | date_created < obs_end；独立于 p99 |
| anomaly_type | list enum | TEMPORAL_ORDER_ERROR / LATENCY_TAIL_REVIEW / PARSE_ERROR / MISSING_TIME_METADATA |
| selected_init_time, gfs_valid_time | nullable UTC timestamp | 尚不选具体 forecast vintage；本轮仅定义字段 |
| gfs_lead_time_hours | nullable numeric | valid_time = selected_init_time + lead；未知或冲突不可猜 |
| gfs_release_time_if_known, gfs_operational_availability | nullable UTC timestamp | 不以 init、mtime、conversion_time 或 +5h 假设代替真实发布时间 |
| gfs_vintage_status | enum | NOT_YET_FROZEN / UNKNOWN_RELEASE / RESEARCHER_CONFIRMED |
| gfs_time_evidence, gfs_auxiliary_metadata_conflict | object, bool | 保存当前 CF/filename/global 时间证据及陈旧 udunits/history 冲突 |
| gfs_paths, gfs_primary_root | list string, string | 主 GFS 与 GFS_thermo 分开；不得静默合并 |
| gfs_variable_complete | nullable bool | 13 个必需 variable/level 均有 metadata；另设 per-pixel validity，不混用 |
| gfs_required_variables | list enum | PWAT,CAPE,RH_850,RH_700,RH_500,T_850,T_700,T_500,U_850,U_700,V_850,V_700,PS |
| gfs_predictor_prohibition | invariant | precipitation/APCP/PRATE/降水累积不得进入 predictor；PWAT 是整层水汽，可保留 |
| gfs_surface_pressure_support | enum | PASS / PARTIAL / MISSING，仅表达将来 m_k=I(ps>p_k) 的 metadata 可行性 |
| DEM_status, mask_status | enum | READY / PARTIAL / MISSING / NOT_AUDITED |
| covers_yunnan_context | enum | 当前恒为 PENDING_RESEARCHER_CONFIRMATION |
| model_input_bbox | nullable object | 当前 null；数值公共交集只是候选 |
| source_provenance | structured object | 原文件、audit run、grid hash、规则版本、证据与不足 |

p99 is a distribution-tail review marker only; it is not an exclusion criterion, QC threshold, or scientific threshold.

不在该 schema 中执行归一化、Train/Val/Test 划分、GFS 插值、Himawari 重采样、DOTE/DTFM/MEE 或模型训练。32 quantile levels 尚未冻结。
