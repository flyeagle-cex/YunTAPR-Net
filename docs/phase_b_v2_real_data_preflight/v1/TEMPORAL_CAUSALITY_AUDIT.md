# 时间因果性审计

分析时刻为 IMERG 目标窗口开始后 30 分钟。B1 oldest→latest 为分析前 60/50/40/30/20/10 分钟，B0 取同一 slot5；检查 nominal、obs_start≤obs_end≤analysis_time。IMERG 日路径和半小时 index 必须与窗口绑定。


```json
{
  "status": "PASS",
  "scene_slot_checks": 125736,
  "nominals_in_index": 70560,
  "minimum_obs_end_slack_seconds": 20.387558,
  "offset_minutes": [
    60,
    50,
    40,
    30,
    20,
    10
  ],
  "future_observation_count": 0,
  "file_created_after_analysis_scene_slot_exposures": 27880,
  "operational_realtime_availability": "NOT_VERIFIED_BY_OBSERVATION_CAUSALITY"
}
```

限定实际解码还核对 CF obs_start、obs_end、date_created 与冻结帧记录一致，并再次检查截止时刻。date_created 晚于分析时刻不被误写为观测时间越界；它说明观测完成的因果性与文件生产/传输/入库可用性不同。文件生成与业务延迟没有获得近实时可用性证明。

实际解码只接受 GPM_3IMERGHH_07、IMERG Final Run V07、48 个半小时片段及 mm hr-1。Final 参考用于回顾性监督与开发验证；不能把其事后可用性写成业务实时参考已到达，也不能把 2024 写成新的独立确认集。
