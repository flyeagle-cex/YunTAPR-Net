# thermo pipeline reconstruction

| 问题 | 结论与证据级别 |
|---|---|
| Provider/product | DIRECT_EVIDENCE：官方 d084001 文档及本地 source/token 指向 NCEP operational GFS family；见 official_documentation_evidence.csv。 |
| 下载位置 | DIRECT_EVIDENCE：source URL 是 NCAR THREDDS NCSS 的 d084001 路径；本地 thermo manifest 记录获取事件。 |
| 上游格式 | DIRECT_EVIDENCE：官方文档为 GRIB2，本地上游 token/URL 含 .grib2 或 pgrb2；没有重新打开上游载荷证明其内容。 |
| 变量 | DIRECT_EVIDENCE：当前 thermo 具备 T/RH 的 850/700/500 hPa，T=K、RH=%；q 不代替 RH。定向实际变量属性保存在 selected_case_raw_metadata.json。 |
| GRIB→NetCDF | DIRECT_EVIDENCE：本地属性声明转换/创建，当前文件确为 NetCDF；NOT_ESTABLISHED：逐文件上游内容到当前载荷的转换证明。 |
| 转换工具 | NOT_ESTABLISHED：创建 history 与 NCSS URL 不足以确定本地写盘库、版本及代码。不能把本轮 netCDF4 reader 当历史转换器。 |
| spatial subset | DIRECT_EVIDENCE：实际 53×57、0.25°，95–109°E、19–32°N；source 为 NCSS 服务路径，当前区域坐标确定，但未找到完整原始 query/转换代码。区域只是实际覆盖，非 bbox 冻结。 |
| variable subset | DIRECT_EVIDENCE：实际 T/RH/q 变量集合及 pressure_level 可核查；NOT_ESTABLISHED：所有历史请求参数/版本。 |
| time 改写 | NOT_ESTABLISHED：没有转换赋值代码；当前 CF 与 init+lead 通过不证明历史未改写。 |
| history 改写 | DIRECT_EVIDENCE：history 保存 2026 创建文本；NOT_ESTABLISHED：生成该字段的源代码。 |
| auxiliary reference 生成 | NOT_ESTABLISHED：未找到赋值代码，保留原有 CF/udunits 差异。 |
| 可读脚本 | NOT_ESTABLISHED：没有定位到源代码，因此本轮不虚构 INFERRED_FROM_SCRIPT 结论。 |

INFERRED_FROM_FILENAME 仅可用于命名结构；本轮同源判断采用 metadata 内上游 token，不只采用当前 .nc 文件名。DIRECT_EVIDENCE 表示确实看见该记录，不能提升成对其所宣称内容的独立鉴真。
