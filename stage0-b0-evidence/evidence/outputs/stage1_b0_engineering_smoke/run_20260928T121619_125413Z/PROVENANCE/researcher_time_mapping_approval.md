# Explicit researcher approval for this smoke only

研究者本轮明确确认：T 为 IMERG converted CF coordinate；candidate analysis_time=T+30min；selected nominal=analysis_time−10min。实际保存 nominal/obs_start/obs_end/date_created，强制 obs_end<=analysis_time；失败拒绝，不修改时间或选择未来帧。每条记录保留 imerg_converted_time、candidate_analysis_time、selected_himawari_nominal_time、obs_start、obs_end、date_created、causality_pass、mapping_status。mapping_status=ENGINEERING_SMOKE_TIME_MAPPING_ONLY。date_created 仅记录，不是 availability。本轮为 offline smoke，未证明 native window start 或 [T,T+30min) 科学语义，未冻结正式单帧绑定。正式 B0 仍需后续明确科学批准。

The cross-source IMERG-Himawari time binding used in this
B0 smoke run is provisional and was used only to test the
engineering pipeline. It is not a frozen scientific sample
timing convention.
