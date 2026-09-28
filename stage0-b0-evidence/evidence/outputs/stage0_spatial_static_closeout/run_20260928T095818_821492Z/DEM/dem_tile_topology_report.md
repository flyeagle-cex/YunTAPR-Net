# DEM tile topology

每 root 的 footprint、分辨率、CRS、shape、nodata 与 gap 分别列在 dem_inventory.csv、dem_tile_coverage.csv 和 dem_audit_summary.json。所有读取结果为 SRTMHGT、3601×3601、1 band int16、1/3600°、EPSG:4326、nodata=-32768，无 CRS/分辨率不一致。

SRTM 名义中心 footprint 包络为94–110E、18–33N；该包络内缺3个1° tile：N18E107、N19E107、N20E108；缺口总面积约3 degree²，不将整个bbox误报为有效覆盖。AWS_Skadi只有这3个独立tile，不能单独覆盖云南。未合并两root。

HGT为 Point 样点，邻tile复制一行/列边界样点。GDAL pixel-support bounds向外伸半样点，与名义中心 footprint不同。名义tile无面积重叠、无duplicate footprint；像元support存在窄重叠，属于共享边缘表达，不是自动重复数据。439对SRTM邻接边、1对Skadi邻接边逐样点完全一致，unequal=0。

对本轮GADM云南polygon：SRTM FULL，Skadi MISSING。候选共同坐标包络97–107E、20–30N内SRTM实际footprint和有效像元均完整；更大的root包络不能整体宣称context-ready。任何科学context宽度仍待决定。

[GDAL HGT格式说明](https://gdal.org/en/stable/drivers/raster/srtmhgt.html)解释命名HGT压缩档的读取与georeferencing支持；[geotransform说明](https://gdal.org/en/stable/tutorials/geotransforms_tut.html)区分像元corner与center。
