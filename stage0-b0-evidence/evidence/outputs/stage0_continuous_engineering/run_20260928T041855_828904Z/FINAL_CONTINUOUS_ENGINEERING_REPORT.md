# YunTAPR-Net Stage-0 continuous engineering report

1. **总状态：NEEDS_REVIEW。** TASK A–P 独立工程执行完成；没有把未知 release 或未审计数据写成 PASS。科研可用性受核心变量缺口、辅助时间来源冲突及待冻结规则约束。

2. **IMERG boundary sanity check：已完成。** 同一最近像元 (lat24.9499988556, lon95.4499969482)，时间按 converted CF coordinate 原值：

| time_utc | precipitation | units | missing |
| --- | --- | --- | --- |
| 2025-06-23T23:30:00Z | 3.1999998092651367 | mm hr-1 | False |
| 2025-06-24T00:00:00Z | 91.02999877929688 | mm hr-1 | False |
| 2025-06-24T00:30:00Z | 8.59999942779541 | mm hr-1 | False |

00:00 的 5×5 patch 已保存于 IMERG/imerg_20250624_boundary_extreme_check.txt 与 CSV/Parquet；这是邻时次/空间数值证据，不能单独证明极值真伪。未设阈值、删样本或改训练规则；两份文件 SHA256 前后一致。

3. **GFS 根目录：** F:\云南极端降水数据\raw\GFS。另发现 F:\云南极端降水数据\raw\GFS_thermo，共 12,960 文件，只盘点不合并；标记 MULTIPLE_GFS_ROOTS_RESEARCHER_REVIEW。

4. **GFS 文件数：** 24,388，6,908,064,258 bytes，24,388 成功读取，0 读取失败。审计 metadata、坐标和时间，不宣称所有 predictor 像元值都已 QC。

5. **年份覆盖：** 真实磁盘为 2019–2025，不能沿用“仅 2021–2024”的旧推测。

| year | file_count | core_complete_files | RH_850_count | T_850_count | PS_count |
| --- | --- | --- | --- | --- | --- |
| 2019 | 1460 | 1460 | 1460 | 1460 | 1460 |
| 2020 | 1464 | 1464 | 1464 | 1464 | 1464 |
| 2021 | 3932 | 224 | 224 | 224 | 3932 |
| 2022 | 4380 | 0 | 0 | 0 | 4380 |
| 2023 | 4380 | 0 | 0 | 0 | 4380 |
| 2024 | 4392 | 0 | 0 | 0 | 4392 |
| 2025 | 4380 | 0 | 0 | 0 | 4380 |

6. **文件格式：** 24,388 NetCDF/HDF5 signature + NETCDF4 data_model；没有 GRIB1/2 或 other 文件，不需要安装 cfgrib/eccodes。

7. **Grid：** 唯一 grid，53×57，0.25°；纬度32→19递减，经度95→109递增。全部坐标与首文件相等，hash 保留在 gfs_grid_audit.csv。无 flip、插值或重采样。

8. **核心变量实际覆盖：**

| canonical_name | file_count | total_files | availability_fraction |
| --- | --- | --- | --- |
| PWAT | 24388 | 24388 | 1.0 |
| CAPE | 24388 | 24388 | 1.0 |
| RH_850 | 3148 | 24388 | 0.129079875348532 |
| RH_700 | 3148 | 24388 | 0.129079875348532 |
| RH_500 | 3148 | 24388 | 0.129079875348532 |
| T_850 | 3148 | 24388 | 0.129079875348532 |
| T_700 | 3148 | 24388 | 0.129079875348532 |
| T_500 | 3148 | 24388 | 0.129079875348532 |
| U_850 | 24388 | 24388 | 1.0 |
| U_700 | 24388 | 24388 | 1.0 |
| V_850 | 24388 | 24388 | 1.0 |
| V_700 | 24388 | 24388 | 1.0 |
| PS | 24388 | 24388 | 1.0 |

这是 metadata presence fraction，不是像元有效比例。T/RH 全层仅 3,148 文件存在（2019、2020、2021年部分）；2022–2025 主库均无所需 T/RH。研究候选期2023–2025年3–10月因此全部 GFS_available=PARTIAL。
Pressure_surface 在全部文件真实存在，未用 MSLP 替代；pressure coordinate 与 surface pressure 单位可比较，surface_pressure_support_status=PASS，表示未来 m_k=I(ps>p_k) metadata 可行。未计算 mask 或 DOTE，未做地下层像元 QC。

9. **禁用 precipitation predictors：** 13,732 文件检测到降水累积等变量，逐项登记，全部 model_predictor_allowed=False。PWAT 是整层水汽，保留为允许变量；禁用变量存在不意味着文件坏。

10. **init/valid/lead：** 当前 filename/CF/global 可一致重建，24,388 条均满足 valid=init+lead。init UTC [0,6,12,18]，lead [0,3,6]h，间隔3h，最大6h，重复init/lead=0。
但 17,665 条 auxiliary metadata 冲突，含 3,628 条陈旧 History 原始数据 token，必须来源追溯；时间算术 PASS 不等于真实数组来源已确认。

11. **Release/availability：NOT ESTABLISHED FROM CURRENT FILE METADATA。** 11,968 个上游 +5h conservative 字段不是 observed publication；本轮未采用。release/operational availability 保持 null，vintage NOT_YET_FROZEN。

12. **2025 GFS 缺口：** 全年4,380文件；3–10月共 2,940 文件，观测调度参考下 missing cycle=0，missing init/lead pair=0。文件调度齐全，但 T/RH 核心变量缺失；二者分开报告。

13. **2025-10 IMERG：MISSING。** 前次全库2,465日文件止于2025-09-30，本轮定向 imerg_202510*.nc 仍0文件。未重扫全库，未修改研究时间范围。

14. **跨源矩阵：已生成24行。** 2023–2025每年3–10月，包含Himawari、IMERG、GFS、SRTM、mask、external validation。Himawari仅2024-07有旧月审计证据为PARTIAL（4390/4464时次）；其他月仅查目录，NOT_AUDITED。IMERG除2025-10为MISSING外为READY（复用前次审计）。GFS研究月均PARTIAL；SRTM/mask为PARTIAL；external为NOT_AUDITED。READY列含义限于相应工程审计证据，非正式训练许可。

15. **空间数值共同包络：lat20–30，lon97–107，CANDIDATE ONLY。** model_input_bbox=null；covers_yunnan_context=PENDING_RESEARCHER_CONFIRMATION。SRTM仅瓦片目录证据、尚无像元有效性；云南 polygon 存在但评价mask未验证，详见空间报告。

16. **测试：33 passed，0 failures/errors/skipped。** 覆盖filename、跨年init/valid/lead、未知/冲突时间、坐标hash、变量/层映射、surface pressure、降水禁入、主辅目录、raw只读/staging清理、完整日历月、跨源矩阵与2025-10缺口。CSV/Parquet 36/36 表回读一致，另含验证表自身一对。

17. **依赖：新增0、升级0。** 解释器 F:\pytorch\Research\.venv\Scripts\python.exe。zarr3.4.0、numcodecs0.17.0、pyarrow25.0.1、xarray2026.7.0、netCDF4 1.7.4 均实测可import；全部环境包前后快照无差异。

18. **完整性/只读：** 全部24,388 GFS大小与mtime_ns复核一致；5个分散GFS样本、2个IMERG文件及GADM边界SHA256前后一致。完整库未做全字节hash，不能把stat一致说成全库逐字节证明。全部raw以只读打开，未修改/移动/删除F/H科研原件；仅清理由流程创建的本轮英文cache副本。旧失败记录、报告和5个diagnostic cache未覆盖/删除。
本轮GFS+IMERG staging共24,390次，累计临时复制 6,910,634,531 bytes，copy累计 34.176s，read累计 180.298s；清理失败0，原始stat变化0，遗留生产nc副本0。不是永久复制整库，耗时是调用累计值，不等于整体wall time或新storage benchmark。

19. **研究者决策清单：** RESEARCHER_DECISIONS_REQUIRED.md；decision log五类状态与未来配对schema均已完成。Himawari既有p99只保留review marker：p99 is a distribution-tail review marker only; it is not an exclusion criterion, QC threshold, or scientific threshold.

20. **下一阶段仅建议：** 复核GFS转换来源/辅助时间冲突，批准后另行审计thermo补充可行性，明确availability/vintage与native IMERG窗口，再决定bbox/mask及缺月处理。本轮未运行训练、normalization、split、正式样本构建、DOTE/DTFM/MEE、GFS插值或Himawari重采样。

证据目录与重现步骤见 README.md；完整输出清单见 output_manifest.csv。所有报告结论均限定于本轮实际执行及明确标注的前次审计证据。


21. **工程状态与科研复核状态分离：** engineering_status=PASS；researcher_review_status=NEEDS_REVIEW；gfs_status=PARTIAL。本轮执行 TASK A–P；audit_final_status.json 为本轮正式状态入口。

22. **新增库存/grid/时间证据：** inventory 含 month/init_time/valid_time/lead_time；全年/月分布和大小分位数见 GFS/gfs_inventory_summary.md。零字节=0，重复文件名行数=0；最大文件清单为 QC_STAT_ONLY，未设“大文件异常阈值”。
坐标 dtype：latitude=['float32']，longitude=['float32']；grid表含lat_shape/lon_shape/field_shape/grid_id/mean_dlat/mean_dlon。
时间类metadata字段清单与distinct evidence表分开保存。额外global lead_time_hours核验：{'UNKNOWN_NOT_PRESENT': 15568, 'PASS': 8820}；UNKNOWN_NOT_PRESENT表示该属性不存在，不是forecast主时间未知。conversion_time、history与生成中心/过程ID均未当作release。

23. **Stage-0 closeout：** 工程交付收口满足，stage0_engineering_closeout_ready=true；科学与数据就绪收口尚未满足，stage0_closeout_ready=false。
PASS items：TASK A–P 工程交付、33 tests通过、全库只读记录、原始完整性和历史基线引用hash校验、CSV/Parquet回读一致。
REVIEW items：GFS T/RH缺口及辅库使用、辅助时间metadata来源冲突、availability/vintage、native IMERG窗口、bbox/行政mask/DEM有效性、2025-10缺月及独立外部验证。
BLOCKED items：无剩余工程阻塞；科研未冻结项归REVIEW而非伪称工程失败。
初次pytest因本轮cache父目录不存在出现27 passed/6 setup errors；已修复，失败XML原样保留。最终真实执行33 tests，failures=0，errors=0，skipped=0；stdout与XML为 tests/pytest_final_output.txt、tests/pytest_final.xml。

24. **禁用变量、cache与边界约束确认：** 检测到的GFS precipitation变量及行数：{'Total_precipitation_surface_6_Hour_Accumulation': 6867, 'Total_precipitation_surface_3_Hour_Accumulation': 6865}。
**CONFIRMED NOT USED AS PREDICTOR. NO_GFS_PRECIPITATION_USED_AS_MODEL_INPUT.**
cache copy_count=24390，cumulative_copied_bytes=6910634531，max_single_copy_bytes=1371753，copy_seconds=34.175732，cleanup_failures=0，remaining_staged_bytes=0。
只清理由本轮创建的副本；全库size+mtime基线在第一个raw数据读取前保存；size+mtime verification不是full content hash proof。
空间共同范围 **CANDIDATE ONLY; NOT A FROZEN MODEL BBOX**。
IMERG QI仅QC_STAT_ONLY，不设阈值、不筛像元、不作predictor；2025-10是候选研究期缺月，非当前2019-01-01至2025-09-30库存内部missing-day。
下一阶段仅建议见第20项和研究者清单；未启动Stage1/B0、ERA5 Teacher、模型checkpoint、正式预测、Dataset或全量配对。

Stage-0 continuous engineering run complete.
Waiting for researcher scientific review.
No frozen scientific convention was changed automatically.
