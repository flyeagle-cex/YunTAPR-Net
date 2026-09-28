# IMERG 全库审计总结

IMERG 文件级审计需复核数量：0。所有数值统计仅为 QC_STAT_ONLY。

1. 实际文件数：**2465**。成功打开 2465，失败 0。
2. 实际覆盖日期：2019-01-01 至 2025-09-30，年份为 [2019, 2020, 2021, 2022, 2023, 2024, 2025]。
3. 各年份文件数：

| year | file_count | unique_date_count | first_date | last_date | days_within_observed_span | missing_days_within_observed_span | calendar_year_days | outside_observed_span_days |
|---|---|---|---|---|---|---|---|---|
| 2019 | 365 | 365 | 2019-01-01 | 2019-12-31 | 365 | 0 | 365 | 0 |
| 2020 | 366 | 366 | 2020-01-01 | 2020-12-31 | 366 | 0 | 366 | 0 |
| 2021 | 365 | 365 | 2021-01-01 | 2021-12-31 | 365 | 0 | 365 | 0 |
| 2022 | 365 | 365 | 2022-01-01 | 2022-12-31 | 365 | 0 | 365 | 0 |
| 2023 | 365 | 365 | 2023-01-01 | 2023-12-31 | 365 | 0 | 365 | 0 |
| 2024 | 366 | 366 | 2024-01-01 | 2024-12-31 | 366 | 0 | 366 | 0 |
| 2025 | 273 | 273 | 2025-01-01 | 2025-09-30 | 273 | 0 | 365 | 92 |

4. title 完全等于 GPM IMERG Final Run V07B regional subset 的文件：2465/2465。版本结论基于文件实际提供的 metadata，不伪造上游原生 granule 验证。
5. source 完全等于 GPM_3IMERGHH_07：2465/2465。
6. 全部 48 帧检查：2465/2465。
7. 严格相邻 30 min：2465/2465；同时满足文件名日期、当日 00:00–23:30 完整序列：2465/2465。
8. 最早至最晚实际库存日期之间缺日：0。日期区间之外不计缺日；2025 年实际部分年度覆盖不自动视作库内缺失。
9. 重复日期关联文件：0。完整表见 imerg_duplicate_dates.csv。
10. unique grid / lat hash / lon hash：1 / 1 / 1。实际 precipitation shape 集合：['(48, 130, 140)']。既逐值比较坐标，又计算稳定 SHA256，未只比较范围和 shape。
11. precipitation units 实际集合：['mm hr-1']；没有自动换算。
12. NaN/FillValue 等无效降水像元总数：0；QI 无效像元总数：0。原始 NaN、FillValue 命中数另行保留，两者可能重叠，不相加。**0 mm/hr 是有效无雨，缺失没有转换为 0。**
13. 有效降水全库范围：0.000000–116.290001 mm hr-1；有效负值像元数：0。最高 20 个文件极值列于 imerg_precip_extreme_examples.csv；排名不是错误标签，未自行设定极值剔除阈值，其科学含义需要研究者判断。
14. needs_review 文件及完整原因见 imerg_needs_review.csv。没有删除、排除、替换或覆盖任何文件。
15. 对 YunTAPR-Net 的影响：库存时间跨度、实际网格和时间一致性提供工程证据；正式年份、空间范围及降水极值的科学解释仍由研究者决定。没有生成配对库、Dataset 或执行重采样。
16. “库存数据更多”、2025 部分年度、转换 history 的时间差异属于数据库存/生产记录现象，不自动改变科研设计。

实际参考坐标：lat=19.049999237060547 至 31.94999885559082（ascending），lon=95.04999542236328 至 108.9499969482422（ascending）；mean dlat=0.0999999970428703，mean dlon=0.100000010977546。未自动 flip 纬度、未冻结或修改 bbox。

time 审计只使用当前 daily subset 的坐标、units、calendar；全库 metadata 中发现 time-bound 变量/属性文件数：0。未推测或写入 native granule start/end。

R_eq_0_fraction 和 R_gt_*_fraction 分母为每文件有效像元数，另附 *_total_fraction 以全部像元为分母。无有效像元时比例留空。precip_nan_fraction 指应用文件所带 missing/FillValue/有效范围与非有限值检查之后的缺失比例；raw_nan_count 单独保留。

QI 中位数逐文件精确计算，保留原数据中有效的 0；QI 全库描述范围 0.132000–0.953000。没有设定 QI 阈值、删除像元、作为模型输入或计算训练 normalization。
