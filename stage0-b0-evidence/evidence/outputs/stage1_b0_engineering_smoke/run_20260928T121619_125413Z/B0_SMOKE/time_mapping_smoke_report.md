# Offline time mapping smoke

研究者在本轮明确批准候选用于工程 smoke（PROVENANCE/researcher_time_mapping_approval.md）。IMERG converted CF coordinate=T；candidate_analysis_time=T+30min；selected_himawari_nominal_time=analysis_time−10min。只取该 exact slot，不以未来帧替代。

16 个样本均从真实文件重读时间，核对旧 P0 metadata，并强制 obs_end<=analysis_time；future 帧或扫描结束晚于 analysis_time 立即拒绝。date_created 原值记录；不要求 date_created<=analysis_time，不据此声称真实时刻可获取。未使用 Himawari availability 或 GFS vintage。

每个实际样本保存 imerg_converted_time、candidate_analysis_time、selected_himawari_nominal_time、obs_start、obs_end、date_created、causality_pass 和 mapping_status=ENGINEERING_SMOKE_TIME_MAPPING_ONLY。还保留原接口别名 imerg_target_time、analysis_time、nominal_time。CSV/JSON 记录 UTC 与来源路径。

本轮没有把 T 定义为 native precipitation window start，也没有声称 [T,T+30min) 为科学标签区间。B0 formal 不能沿用此候选作为正式规则，除非后续获得科学证据及显式批准。

The cross-source IMERG-Himawari time binding used in this
B0 smoke run is provisional and was used only to test the
engineering pipeline. It is not a frozen scientific sample
timing convention.
