# Researcher decisions required

1. **是否采用 thermo 作为 companion、是否批准未来组合接口。** 24研究月8,820/8,820对在时间、坐标、变量与单位metadata上满足条件；工程总判定 PARTIALLY_COMPATIBLE，尚未批准整合。
2. **主库转换来源证据是否足够，是否需要追溯原始GRIB/下载与转换记录。** 声明的GFS archive和forecast token对应，source lineage=SUPPORTED_WITH_CAVEATS；17,665条udunits历史冲突及其中3,628条History token仍需来源复核。没有证据将它们一律判成实际forecast错误，也没有证据证明转换payload全部正确。
3. **GFS operational availability/vintage规则。** 主库与thermo都没有确立真实发布时间；init+5h不能自动采用为observed release。

本轮不需要改变MEE变量、科研年份或bbox才能完成审计；不提出无必要重下载。其他既有科学closeout事项继续保留在旧Stage-0报告，本轮未擅自解决或改写。
