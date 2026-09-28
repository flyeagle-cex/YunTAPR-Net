# YunTAPR-Net GFS_thermo compatibility engineering report

1. **engineering_status=PASS；researcher_review_status=NEEDS_REVIEW。** 所有本轮独立工程任务已执行；总兼容性判定 **PARTIALLY_COMPATIBLE**，来源转换环节仍有保留条件。

2. **Thermo root：** F:\云南极端降水数据\raw\GFS_thermo。
3. **文件数：** 12,960；逻辑大小 1,185,769,108 bytes；全部读取成功，0零字节、0重复文件名。文件大小统计仅QC_STAT_ONLY，不是训练mean/std或异常阈值。
4. **年份/月覆盖：** {'2021': 1236, '2022': 1460, '2023': 3420, '2024': 3424, '2025': 3420}；全月清单见 THERMO/gfs_thermo_month_inventory.csv，研究24月见下表。
5. **格式/结构：** 全部NetCDF/HDF5 signature、NETCDF4；1种内部结构。逐文件dimensions、coordinate/pressure变量、dtype、原global attrs均保留。
6. **Grid：** 53×57，0.25°；lat32→19递减、lon95→109递增；float32，一种grid。
7. **与主库比较：** 全12,960文件实际坐标逐值相等，lat/lon hash相等，shape和resolution一致；max_abs_lat_diff=0，max_abs_lon_diff=0。没有只比bbox、近似接受或插值。
8. **T/RH：** 六个必需variable/level均12,960/12,960存在；field shape=(1,3,53,57)。原Temperature_isobaric与Relative_humidity_isobaric保留；Specific_humidity_isobaric单列，未代替RH。未检查所有气象像元数值有效性，metadata presence不是像元QC通过。
9. **单位：** T=K，RH=%；与主库已有T/RH metadata相同。未转degC或0–1，未改原数组。
10. **Pressure：** pressure_level原值[50000,70000,85000]Pa，即500/700/850hPa的metadata对应关系。主库Pressure_surface原单位Pa；未来可比较ps>p_k，feasibility=PASS。thermo自身无PS，未用MSLP替代；未算above-ground mask、DOTE或W/L/M。
11. **时间：** init UTC [0, 6, 12, 18]，lead [0, 3, 6]h、间隔3h、最大6h；12,960/12,960满足valid=init+lead，thermo辅助冲突0。
12. **主库/thermo配对：** MATCHED_COMPLETE=12,960，MAIN_ONLY=11,428；THERMO_ONLY=0；TIME/GRID/METADATA配对冲突0。
13. **一对一比例：** 相对thermo为100%（12,960/12,960），相对全部历史主库约53.140889%（12,960/24,388）；一对多、多对一、歧义均0。记录了10,019个同valid_time多forecast组，它们由不同init/lead区分，不能当作重复配对错误。
14. **研究期月覆盖：**

| month | expected_main_forecast_pairs | main_present | thermo_present | matched_pairs | complete_T_RH_pairs | coverage_fraction | status |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 2023-03 | 372 | 372 | 372 | 372 | 372 | 1.0 | READY |
| 2023-04 | 360 | 360 | 360 | 360 | 360 | 1.0 | READY |
| 2023-05 | 372 | 372 | 372 | 372 | 372 | 1.0 | READY |
| 2023-06 | 360 | 360 | 360 | 360 | 360 | 1.0 | READY |
| 2023-07 | 372 | 372 | 372 | 372 | 372 | 1.0 | READY |
| 2023-08 | 372 | 372 | 372 | 372 | 372 | 1.0 | READY |
| 2023-09 | 360 | 360 | 360 | 360 | 360 | 1.0 | READY |
| 2023-10 | 372 | 372 | 372 | 372 | 372 | 1.0 | READY |
| 2024-03 | 372 | 372 | 372 | 372 | 372 | 1.0 | READY |
| 2024-04 | 360 | 360 | 360 | 360 | 360 | 1.0 | READY |
| 2024-05 | 372 | 372 | 372 | 372 | 372 | 1.0 | READY |
| 2024-06 | 360 | 360 | 360 | 360 | 360 | 1.0 | READY |
| 2024-07 | 372 | 372 | 372 | 372 | 372 | 1.0 | READY |
| 2024-08 | 372 | 372 | 372 | 372 | 372 | 1.0 | READY |
| 2024-09 | 360 | 360 | 360 | 360 | 360 | 1.0 | READY |
| 2024-10 | 372 | 372 | 372 | 372 | 372 | 1.0 | READY |
| 2025-03 | 372 | 372 | 372 | 372 | 372 | 1.0 | READY |
| 2025-04 | 360 | 360 | 360 | 360 | 360 | 1.0 | READY |
| 2025-05 | 372 | 372 | 372 | 372 | 372 | 1.0 | READY |
| 2025-06 | 360 | 360 | 360 | 360 | 360 | 1.0 | READY |
| 2025-07 | 372 | 372 | 372 | 372 | 372 | 1.0 | READY |
| 2025-08 | 372 | 372 | 372 | 372 | 372 | 1.0 | READY |
| 2025-09 | 360 | 360 | 360 | 360 | 360 | 1.0 | READY |
| 2025-10 | 372 | 372 | 372 | 372 | 372 | 1.0 | READY |

15. **关键问题：能否补齐2023–2025 March–October六个T/RH？** 从当前文件级时间、坐标和变量metadata看，**可以作为完整补齐候选**：24个月均100%，共8,820/8,820；每月missing init cycles、lead pairs、missing variables均0。
年度证据：

| year | expected_pairs | complete_pairs | minimum_month_fraction |
| --- | --- | --- | --- |
| 2023 | 2940 | 2940 | 1.0 |
| 2024 | 2940 | 2940 | 1.0 |
| 2025 | 2940 | 2940 | 1.0 |

16. **Source lineage：SUPPORTED_WITH_CAVEATS。** 每个配对有具体GFS archive/product与当前forecast文件token证据，不只靠目录、时间或grid；matched主库声明来源包括NCAR与NOAA AWS，thermo声明NCAR RDA d084001。未独立验证原始GRIB内容、转换代码或下载日志，不能保证所有转换payload来源，详见 source_lineage_comparison.md。
17. **主库auxiliary time：** 复用已验证旧run，对24,388旧记录分类：17,665为ALTERNATIVE_REFERENCE_TIME，重叠3,628为STALE_HISTORY_TOKEN；真实主时间算术冲突检测0。仅定向读取9个主库样本，覆盖2019/2021/2023/2024/2025及可用冲突/非冲突层，原init/valid/lead未改写。
18. **Release/availability：NOT ESTABLISHED FROM CURRENT FILE METADATA。** thermo全部12,960个+5h字段明确是保守假设；creation/conversion/archive文本不等于observed publication，未冻结vintage规则。
19. **原始完整性：** thermo全库读取前后size/mtime_ns一致；5个分散thermo hash样本一致，6个结构probe读时hash一致；9个主库样本size/mtime/hash一致；复用旧报告hash一致。**size/mtime verification is not full content hash proof.** raw及所有旧run只读，仅清理本run创建的staging副本。
20. **pytest：** 33 passed，failures=0，errors=0，skipped=0；cwd/rootdir/test path/confcutdir显式限制。实际stdout与XML见tests/pytest_final_output.txt、pytest_final.xml。
21. **依赖：** 没有新增/升级；固定Python F:\pytorch\Research\.venv\Scripts\python.exe，前后环境清单保存。
22. **Cache I/O：** copy_count=12975（thermo12,960全审+6probe，main9个），累计1,188,743,376 bytes，最大单副本288,601 bytes；copy=17.110s，read=64.301s，cleanup failures=0，remaining staged bytes=0。没有永久复制完整库。
23. **兼容性判定：PARTIALLY_COMPATIBLE。** A–K逐项表见兼容性assessment；结构、grid、时间、变量、单位、压力、研究期覆盖和一对一配对PASS；来源lineage为PARTIAL。保留条件不是研究月T/RH缺文件。
24. **研究者决策：** 是否采纳/允许模型数据层组合、是否追溯原始来源与转换记录、如何冻结availability/vintage。普通工程问题均已处理；初始化NumPy bool日志序列化修复记录保留。
25. **Stage-0 closeout impact：** 本轮消除了研究期T/RH“文件/metadata不可得”的工程缺口，支持 **READY candidate（仅结构覆盖意义）**；没有改写正式predictor readiness或旧run。来源复核、release/vintage及其他既有Stage-0科学项仍待研究者处理，stage0_closeout_ready=false。未启动B0，也未构造Dataset、正式sample pairing database或merged files。

主库证据复用：F:\pytorch\Research\outputs\stage0_continuous_engineering\run_20260928T041855_828904Z，已核验engineering_status=PASS、24388 files、53×57与指定root fingerprint。main_present主要来自该不可变审计快照，仅9个样本本轮重开；不声称对全部主库做了当前原文件重读。
THERMO/COMPATIBILITY/TIME_LINEAGE表是审计证据；配对表不含目标降水、训练split或模型tensor。完整清单见output_manifest.csv。


CSV/Parquet工程恢复：首次回读有1张配对表因NaN/None可空布尔表示差异而失败；已明确BooleanDtype并通过新增回归测试。缺失未填False，原失败summary/Parquet和前次测试XML保留；最终恢复见logs/parquet_final_summary.json。未新增依赖。

GFS_thermo compatibility engineering audit complete.
No GFS main/thermo merge was performed.
Researcher approval is required before any dataset integration.
No frozen scientific convention was changed automatically.
