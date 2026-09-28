# Stage-0 spatial scientific decision update

Decision authority: researcher explicit approval. Freeze ID: `YunTAPR_STAGE0_SPATIAL_v1_run_20260928T102636_513428Z`. This log adds a new approved state; the prior audit's PROVISIONAL/NOT_YET_FROZEN statements remain immutable historical records.

## FROZEN

- 最终主评价范围为云南省全境行政区mask。
- 当前正式边界：GADM4.1 China Level1、云南feature CHN.30_1；全部五项身份字段同时匹配。
- 正式evaluation mask：center-in-polygon，实际IMERG130×140 grid，true=3430，lat ascending，lat/lon exact match；承接获批候选的strict interior语义，当前恰在边界的中心数0。
- 当前正式DEM主来源：F:/云南极端降水数据/raw/SRTM；对冻结polygon为FULL，无云南NoData gap。此处冻结source，不冻结DEM生产方法。
- DOTE地形梯度必须基于真实物理距离；不得把经纬度索引gradient当物理梯度。

## NOT_YET_FROZEN

model_input_bbox；省界外weather-system context margin；DEM聚合/重采样方法；slope/aspect/relief/curvature参数；dh/dx、dh/dy正式生产流程。

97–107°E、20–30°N继续标记CANDIDATE COMMON NUMERICAL OVERLAP，不能当正式model-input bbox。intersection mask是非主评价敏感性对照；AWS_Skadi保留独立辅助地位。

## RESEARCHER_DECISION_REQUIRED

未来具体bbox/context宽度、DEM聚合方式、正式地形特征参数与gradient生产流程，由研究者另行决定。已获批的当前边界版本、中心mask及SRTM主来源无需再次批准；如将来替换，必须显式决策并建立新版本，不覆盖本run。

## Validation and stop

21项pytest通过；原始输入及旧run无写入，保护范围及哈希见logs/integrity_summary.json。未生成正式DEM/model-input grid/DOTE特征，未开始B0，未改变GFS provenance/vintage或研究年份。当前决策完成后停止。
