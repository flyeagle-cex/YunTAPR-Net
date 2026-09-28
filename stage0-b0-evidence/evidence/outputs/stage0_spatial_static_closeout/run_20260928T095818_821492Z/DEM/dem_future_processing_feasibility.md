# Future processing feasibility — no formal resampling

raw DEM为1弧秒Point样点；IMERG真实target约0.1°、130×140；已审计Himawari网格约0.02°、501×501。分辨率差异已明确，但未来model-input grid未冻结，不能因此生成正式网格或正式DEM。

未来可比较average elevation、median、bilinear、area-weighted、min/max及terrain-feature-before-aggregation；本轮不选择。平均/median代表不同区域摘要，bilinear描述点值插值，min/max是极值；area-weighted需要真实cell面积与边界规则；先派生再聚合与先聚合再派生通常不同。Point DEM转cell support的语义、空值权重、海陆/边界与跨root处理需明确后再实现。

DOTE未来所需dh/dx、dh/dy必须以物理距离（米）为水平坐标，不能直接对经纬度索引求gradient。当前GDAL band units=m；本地HGT无完整垂直datum头信息，vertical datum仍NOT_ESTABLISHED_FROM_LOCAL_HEADER；须按选定来源的可靠产品metadata核实，不能从文件名补造。没有正式重采样、特征算法或DOTE。
