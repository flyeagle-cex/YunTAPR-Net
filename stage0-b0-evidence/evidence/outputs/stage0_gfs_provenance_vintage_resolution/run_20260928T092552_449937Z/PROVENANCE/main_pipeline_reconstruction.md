# main pipeline reconstruction

| 问题 | 结论与证据级别 |
|---|---|
| Provider/product | DIRECT_EVIDENCE：官方 d084001 文档及本地 source/token 指向 NCEP operational GFS family；见 official_documentation_evidence.csv。 |
| 下载位置 | DIRECT_EVIDENCE：AWS noaa-gfs-bdp-pds 与 NCAR NCSS 两种来源在主库字段/日志中出现；provider 与 archive/mirror 角色不同，不构成天然冲突。 |
| 上游格式 | DIRECT_EVIDENCE：官方文档为 GRIB2，本地上游 token/URL 含 .grib2 或 pgrb2；没有重新打开上游载荷证明其内容。 |
| 变量 | DIRECT_EVIDENCE：当前主库包含 PWAT/CAPE/U/V/PS；T/RH 覆盖以既有 variable mapping 为准，不能凭 whitelist 推定每文件具备全部变量。定向实际变量属性保存在 selected_case_raw_metadata.json。 |
| GRIB→NetCDF | DIRECT_EVIDENCE：本地属性声明转换/创建，当前文件确为 NetCDF；NOT_ESTABLISHED：逐文件上游内容到当前载荷的转换证明。 |
| 转换工具 | DIRECT_EVIDENCE：部分 metadata 写有 Netcdf-Java CDM / CFGridCoverageWriter，AWS byte-range subset 属性及模板日志也存在；这只是声明/日志证据。不能把本轮 netCDF4 reader 当历史转换器。 |
| spatial subset | DIRECT_EVIDENCE：实际 53×57、0.25°，95–109°E、19–32°N；日志 NCSS query 明确 north/south/east/west，requested_domain 属性也有记录。区域只是实际覆盖，非 bbox 冻结。 |
| variable subset | DIRECT_EVIDENCE：部分请求 query 列出变量，某些当前文件 metadata 声明排除降水；旧索引仍有 5452 文件 precipitation 字段，不可用文件成员资格替代 predictor whitelist；NOT_ESTABLISHED：所有历史请求参数/版本。 |
| time 改写 | NOT_ESTABLISHED：没有转换赋值代码；当前 CF 与 init+lead 通过不证明历史未改写。 |
| history 改写 | DIRECT_EVIDENCE：存在 legacy_history_before_20260925 与新版 History 的并存，且 History 声明 provenance normalized；NOT_ESTABLISHED：对应脚本/赋值行、执行版本。 |
| auxiliary reference 生成 | NOT_ESTABLISHED：未找到赋值代码，保留原有 CF/udunits 差异。 |
| 可读脚本 | NOT_ESTABLISHED：没有定位到源代码，因此本轮不虚构 INFERRED_FROM_SCRIPT 结论。 |

INFERRED_FROM_FILENAME 仅可用于命名结构；本轮同源判断采用 metadata 内上游 token，不只采用当前 .nc 文件名。DIRECT_EVIDENCE 表示确实看见该记录，不能提升成对其所宣称内容的独立鉴真。
