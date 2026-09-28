# Researcher decisions required

已冻结且不变：最终评价必须使用云南省全境行政区mask。

1. 哪个行政区边界文件/来源版本作为正式版本，包括本轮GADM4.1候选是否可采用。
2. 最终center或intersection边界像元规则及触边处理。
3. 模型输入bbox。
4. 省界外围天气系统context margin。
5. DEM正式聚合方法与来源组合口径。
6. 正式terrain feature算法、物理坐标处理、尺度及参数。

本轮未把普通读取、修复依赖或测试问题交给研究者决定。
