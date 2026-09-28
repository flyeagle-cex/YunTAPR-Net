# GFS discovery report

状态：MULTIPLE_GFS_ROOTS_RESEARCHER_REVIEW。

主目录：F:\云南极端降水数据\raw\GFS。按用户优先路径直接找到；没有扫描系统盘或无关大目录。
对 raw 下名称以 GFS 开头的兄弟目录做受限发现和文件名清单统计。

| root | selected_main | file_count | extensions |
| --- | --- | --- | --- |
| F:\云南极端降水数据\raw\GFS | True | 24388 | {'.nc': 24388} |
| F:\云南极端降水数据\raw\GFS_thermo | False | 12960 | {'.nc': 12960} |

MULTIPLE_GFS_ROOTS_RESEARCHER_REVIEW：主目录 GFS 进入全库只读 metadata 审计；GFS_thermo 只发现/计数，没有读取其科学变量，也未自动补充主目录。不能依据 thermo 名称直接认定它可以合并。

实际主库 2019–2025，24,388 个 .nc；magic 为 NetCDF/HDF5，netCDF4 data_model=NETCDF4，全部可读。
