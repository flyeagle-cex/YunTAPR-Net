# GFS time semantics summary

24,388/24,388 文件的当前 filename、CF reference/valid time 及可用 global cycle/lead metadata 一致，valid_time = init_time + lead_time 全部 PASS；没有重复 init/lead 对。时间均按 UTC 输出。

init hours：[0, 6, 12, 18] UTC；lead hours：[0, 3, 6]；lead 间隔 [3, 3] 小时，maximum lead=6 小时。跨年 valid time 可延伸至 2026-01-01T00:00Z，不自动改写研究年份。
accumulation_time 是降水累积时段相关坐标，不替代 predictor 的 instantaneous valid_time。

但 17,665 文件存在陈旧辅助 udunits 与当前 CF units 冲突，其中 3,628 文件还包含与当前 cycle/lead 不同的 History Original Dataset token。见 gfs_auxiliary_time_metadata_needs_review.csv。
本轮以当前 CF units 和相互一致的 filename/global cycle 重建索引，同时完整保留冲突。算术一致不能证明实际数组来自正确 forecast；需要原始转换来源追溯。没有改写任何 raw metadata。

11,968 文件包含 conservative_available_time_utc；其 availability_note 明示 +5h 是 conservative assumption，而非 observed per-file publication timestamp。
其他 source archive URL、history、conversion_time 等原文保存在每文件时间审计与 global_metadata_patterns.jsonl 中；不把下载、转换或文件 mtime 视为业务可用时间。

**GFS operational release/availability: NOT ESTABLISHED FROM CURRENT FILE METADATA.**
release_time 和 operational_availability_time 为空值；GFS vintage rule=NOT_YET_FROZEN。该证据不足不阻塞其余工程审计。

日历月缺口表使用观测到的四个 init hour 与 lead union [0,3,6] 作为诊断参考，不是新的科学要求。
2019–2020 主要只有 f000，所以相对该 union 会出现 f003/f006 缺口；不自动将这些文件判坏。
2023–2025 年研究月没有该参考下的缺失 cycle/lead 对，但主目录必需 T/RH 缺失，数据准备状态仍 PARTIAL。


本轮额外global lead_time_hours交叉核验：{'UNKNOWN_NOT_PRESENT': 15568, 'PASS': 8820}。字段总览见 gfs_time_metadata_field_inventory.csv；分类证据见 gfs_distinct_time_evidence.csv。生成中心/过程标识不是生成timestamp。
