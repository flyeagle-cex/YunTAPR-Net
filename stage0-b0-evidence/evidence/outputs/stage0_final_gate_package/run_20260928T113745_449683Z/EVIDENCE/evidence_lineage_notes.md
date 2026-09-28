# Evidence lineage and conflicts

当前定向 fingerprint 检查无冲突。早期状态按来源时点保留，不自行覆盖：

- 早期 continuous run 与 later continuous run 均注册；本包使用有正式 audit_final_status 的较晚 run 作为 expanded engineering baseline，并保留早期30 tests历史。
- GFS 主库缺 T/RH 与 thermo 有补充候选可同时成立。
- 旧 spatial audit 为 candidate；后续 researcher approval + freeze 明确更新其科学地位。
- Himawari DRY_RUN_FAILED 为依赖 Gate 历史；resume v1/v2 原样保留，v2 为明示 revision，字段一致性已核查。
- nominal/internal TIME_MISMATCH 与 obs_end physical causality 是不同判据；本包不把前者转为坏数据或删除条件。
- 旧 manifest 无 SHA 时仅可比较登记 size；本轮额外保存当前关键文件 SHA 和前后完整性，不声称补出了历史 hash。
- 本轮初始文件名定位遇到旧 tests/tmp 访问限制，改为指定正式证据读取，未改权限，未遗漏任何本包必需状态/报告。
