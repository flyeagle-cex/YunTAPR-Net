# Spatial coverage closeout — CANDIDATE ONLY

复用正式IMERG/GFS/Himawari grid审计，加入独立SRTM footprint和全像元valid QC及云南polygon。详细lat/lon/resolution/orientation/evidence_source见spatial_coverage_closeout.csv。

numerical common overlap candidate：97–107°E、20–30°N。这是各source坐标中心包络的保守数值交集，SRTM有效像元也覆盖该区域，云南polygon处于其中。AWS_Skadi单独列出，不通过悄悄合并扩展覆盖。

这不是model_input_bbox。IMERG、GFS、Himawari的polygon inclusion是坐标空间包络结论；没有本轮逐时逐变量复核所有有效像元，所以all-time/all-variable common validity仍NOT_ESTABLISHED。本轮static检查不能替代原数据QC、未来regridding或科学外部验证定义。

云南最终评价行政区mask原则保持冻结；共同候选包络仅用于说明可能的输入上下文余量。
