# Yunnan polygon audit

6个候选共选出284条云南相关feature（1、16、125及对应processed副本）；全部SOURCE_GEOMETRY_VALID，无empty、无文件内duplicate geometry。具体geometry type、multipart、holes、native面积、bounds、validity reason和完整行政属性见yunnan_polygon_features.csv。native面积是degree²，不能标成km²。

原始文件明确CRS84（WGS84经纬度，x=longitude/y=latitude），与raster EPSG:4326进行工程转换时使用always_xy=True；本次省界无需重投影。没有使用make_valid/buffer(0)替代源几何，本次全部源几何已valid。代码对潜在invalid只允许内存修复试验。

身份由NAME_1=Yunnan、NL_NAME_1含云南、GID_1=CHN.30_1、HASC_1=CN.YN、ISO_1=CN-YN、ENGTYPE_1=Province共同支持，状态ATTRIBUTE_SUPPORTED_YUNNAN。source/版本身份与“最终科研选用”分开记录。

**已冻结原则：最终评价必须使用云南省全境行政区mask。** 具体文件、版本、center/intersection边界语义未冻结。
