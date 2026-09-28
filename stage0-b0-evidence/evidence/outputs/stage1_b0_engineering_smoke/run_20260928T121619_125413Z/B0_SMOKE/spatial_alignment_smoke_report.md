# Spatial alignment smoke

**ENGINEERING_SMOKE_CROP_ONLY / PROVISIONAL_SMOKE_ALIGNMENT**。

输入原 shape=[501, 501]，源纬度 [20.0, 30.0]（descending）、经度 [97.0, 107.0]（ascending）。原 IMERG daily field=[48, 130, 140]，真实 target lat/lon 为冻结的 130×140 coordinate anchor，逐值检查通过。

Crop 使用真实 IMERG coordinate 数组的 Python slices lat[44:76]、lon[54:86]，shape=32×32。未用 np.arange 构造坐标。经纬范围为 lat=[23.44999885559082, 26.549999237060547]、lon=[100.44999694824219, 103.54999542236328]，输出 lat/lon ascending。这些范围只描述本轮工程 crop，不是正式 model_input_bbox；model_input_bbox 与 context margin 仍 NOT_YET_FROZEN。

方法：对每个真实 target 中心，按绝对坐标差分别找到源 latitude/longitude 的最近索引，然后 np.ix_ gather。无平均、平滑、双线性插值或域外外推；若距离相等，NumPy argmin 取第一个源索引，未将其定为科学 tie rule。最大实际 latitude 偏移=0.010000228881835938°，longitude 偏移=0.01000213623046875°。

源行索引从 328 到 173，明确将 descending 源坐标取样到 ascending target 坐标；这不是未记录的 flip。全部索引与每个样本原始/输出坐标范围见 reader_actual_metadata.json。

Missing handling：同索引 gather 原 valid mask；invalid 仍 NaN，不做最近有效像元搜索、不插值、不当 0。IMERG label 仅原数组 crop，不作空间重采样。真实 selected crop 均全有效；合成单元测试另覆盖 missing 与方向。

冻结云南主评价 mask（GADM4.1 CHN.30_1、center-in-polygon、3430 cells）只做只读 hash 保护，未生成/修改。训练 loss 和 diagnostic metric 在本小 crop 的 target-valid pixels 上计算，不宣称完整云南主评价。intersection comparison 未改角色。
