# 2024-07 Himawari latency 审计总结

1. 实际重新扫描 4390 个文件；四个 UTC 时间全部成功解析 4390。范围仅为 202407。
2–4. nominal→obs_start、扫描时长、obs_end→date_created 分布如下；额外保留 nominal→date_created。单位为秒，std 使用样本标准差 ddof=1；每行 count 对应该指标实际可计算样本。

| metric | count | min | mean | median | p90 | p95 | p99 | max | std |
|---|---|---|---|---|---|---|---|---|---|
| start_offset_seconds | 4390 | 39.598106 | 40.788264 | 40.783609 | 41.34767 | 41.498015 | 41.783888 | 41.915538 | 0.419444 |
| scan_duration_seconds | 4390 | 537.47529 | 537.788741 | 537.733836 | 538.046514 | 538.06447 | 538.102764 | 538.153382 | 0.155731 |
| creation_delay_seconds | 4390 | 307.89294 | 538.042585 | 542.975124 | 619.714995 | 668.443275 | 844.685371 | 3594.341787 | 110.368288 |
| nominal_to_created_seconds | 4390 | 886 | 1116.61959 | 1122 | 1198 | 1247 | 1423 | 4173 | 110.346595 |

5. creation delay：p50=542.975124 s，p95=668.443275 s，p99=844.685371 s，max=3594.341787 s。最大值文件：18\NC_H09_20240718_0440_R21_FLDK.06001_06001.nc。
6. causal_as_latest 检查 obs_end <= nominal_time + 10min：True=4390，False=0，不可计算=0；可计算样本通过比例=100.00000000%。
7. obs_end 超过 nominal+10min 文件数：0。反例表 causal_as_latest_false_examples.csv 即使为空也保留列结构。
8. date_created < obs_end 文件数：0。这是独立的 TEMPORAL_ORDER_ERROR，不依赖 p99。
9. date_created 只能称为 product/file creation timestamp 或 metadata creation timestamp，不能直接等同于业务链路中的可下载/可读取时间。
10. operational availability 的证据结论：**Not established from current metadata alone.**

## 尾部标记与错误分类

按全部 4390 个成功解析样本计算 creation_delay p99=844.685371 s；用 >= 比较，共 44 个 LATENCY_TAIL_REVIEW 文件。原始 delay 数值完整保留。

**p99 is a distribution-tail review marker only; it is not an exclusion criterion, QC threshold, or scientific threshold.**

尾部样本只供研究者查看，不表示错误，不删除、不剔除、不修改。TEMPORAL_ORDER_ERROR、PARSE_ERROR、MISSING_TIME_METADATA 等则单独分类。每文件可对应多个原因；异常表行数不应等同于唯一文件数。

实际 anomaly_type 计数：{"LATENCY_TAIL_REVIEW": 44}。

nominal 来自文件名，start/end 的原始值、units、calendar 和 UTC 解析值全部保留，date_created 原字符串也保留。因果性仅判断观测是否结束，不要求 date_created <= analysis_time；未建立 operational availability_time，未重建 IMERG–Himawari 配对库。
