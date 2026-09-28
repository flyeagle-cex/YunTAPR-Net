# Multi-source spatial coverage

**CANDIDATE ONLY.** covers_yunnan_context=PENDING_RESEARCHER_CONFIRMATION；model_input_bbox=null。

| source | lat_min | lat_max | lon_min | lon_max | shape | resolution_lat | resolution_lon | lat_direction | lon_direction |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Himawari | 20.0 | 30.0 | 97.0 | 107.0 | (501,501) | 0.0200004577636718 | 0.0199966430664062 | descending | ascending |
| IMERG | 19.049999237060547 | 31.94999885559082 | 95.04999542236328 | 108.9499969482422 | (130, 140) | 0.0999999970428703 | 0.100000010977546 | ascending | ascending |
| GFS | 19.0 | 32.0 | 95.0 | 109.0 | (53, 57) | 0.25 | 0.25 | descending | ascending |
| SRTM | 18.0 | 33.0 | 94.0 | 110.0 | 3601x3601 per tile (ZIP size evidence) | 0.0002777777777777 | 0.0002777777777777 | NOT_READ | NOT_READ |

数值包络交集：lat 20–30°N，lon 97–107°E，仅为 CANDIDATE ONLY。
没有据此设置 model_input_bbox，也没有采用历史 96–108°E、20–31°N 建议范围。
Himawari 范围仅由已完成 2024-07 grid audit 支持；其他年份/月 grid 未在本轮审计。IMERG 复用前次全库坐标审计；GFS 为本轮全库逐文件坐标 hash。
GFS 唯一 grid：53×57，纬度 32→19 递减，经度 95→109 递增，0.25°。没有自动 flip 或重采样。

SRTM：237 个 SRTMGL1 zip，文件名推定包络 lat18–33、lon94–110。只读 ZIP central directory，检查 HGT 成员大小，不解压或读取 DEM 像元。
矩形包络缺 N18E107、N19E107、N20E108 三个瓦片；它们与候选交集内部不相交。包络内没有瓦片缺口不等于 DEM 无 void 或共同像元有效。
按 [USGS SRTM User Guide](https://lpdaac.usgs.gov/documents/179/SRTM_User_Guide_V3.pdf) 的西南角命名与 1°/1 arcsecond 网格约定解释；3601×3601 还得到每个 HGT 成员字节数的目录证据支持。
实际 raster coordinate direction、void、数据有效性与垂直 datum 本轮 NOT_AUDITED，SRTM 准备状态 PARTIAL。

云南边界：GADM41 CHN level1 中唯一 NAME_1=Yunnan/GID_1=CHN.30_1，MultiPolygon、4,418 坐标点。
几何包络 lat 21.1394–29.2511，lon 97.5341–106.1942；CRS84 元数据。该多边形源存在，但评价 mask 的栅格化、边界像元与对齐尚未定义/验证；状态 PARTIAL。
数值交集包络包含该云南多边形包络，不能据此声称足够天气系统上下文或最终 mask 已就绪。

共同有效覆盖需后续结合每源有效性 mask、行政评价范围与省界外天气上下文，由研究者决定。没有插值、裁剪、行政 mask 生成或科学 bbox 冻结。
