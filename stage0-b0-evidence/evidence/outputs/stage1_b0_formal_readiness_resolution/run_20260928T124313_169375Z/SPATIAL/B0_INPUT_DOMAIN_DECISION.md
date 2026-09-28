# B0 input domain / context decision

**NOT_YET_FROZEN；四个候选均未选择。** 唯一正式评价 mask 仍为 GADM 4.1 Yunnan center-in-polygon，(130,140)，3430 true cells。intersection 3752 保留为非主评价敏感性比较，未替换或修改。

候选先定义 polygon envelope、对称 0.25°、对称 0.50° 或当前全部共同范围，再用**实际 Himawari 坐标向外包围**请求边界。没有 np.arange，没有数组翻转/转置，没有生成降水/温度裁剪数据，没有重采样。目标索引来自已冻结真实 IMERG 坐标，并重新逐值核对 2024-07-01 日文件。源纬度降序，目标纬度升序，需要未来明确的坐标映射；不能把轴方向差异隐式处理掉。

|候选|native 中心坐标包络 E; N|native 行列|target 行列|保留评价 cells|
|---|---|---|---|---|
|SP01|97.520004–106.199997; 21.120003–29.260000|[408, 435]|[82, 87]|3430|
|SP02|97.279999–106.459999; 20.880001–29.520000|[433, 460]|[86, 92]|3430|
|SP03|97.020004–106.699997; 20.620003–29.760000|[458, 485]|[92, 97]|3430|
|SP04|97.000000–107.000000; 20.000000–30.000000|[501, 501]|[100, 100]|3430|

pixel shape 指当前坐标中心筛选所得维度，不代表正式模型输入分辨率/插值方案已定。四向 margin 在 CSV 中按 polygon bounds 到实际 native 中心范围计算，单位 degree；经纬度角度 margin 不是相同物理距离，0.25/0.50 只是比较参数，不是天气系统科学尺度。

SP01 基本无额外上下文，边界可受卷积支持不足影响；SP02/03 加入逐级上下文，增加计算量；SP04 使用所有已审计共同范围，四向 margin 不对称，不能把它写成正式 bbox。所有候选均覆盖 3430 个主评价中心。目标子网格不是对正式 (130,140) mask 的替换，未来输出应按记录索引映射回冻结 canvas，仅在主 mask ∩ target-valid 上评价，不能把域外/无效像元记成 0 雨。

输入 native crop 可用连续原始索引切片完成；源整幅为 (501,501)，97–107E / 20–30N。正式对齐方法、缺测传播和边缘支持仍需批准。按中心取点不自动证明目标 cell footprint 完整被输入框覆盖；若日后采用面积聚合/保守重映射，必须检查额外 footprint 支持。

CSV 分别给 stride=16、32 假设下补齐行列数。这里没有选择 U-Net 深度、padding 位置/值/方式或正式分辨率，也没有执行 padding。未来 padding 必须有独立有效性 mask，不能以补零冒充观测。正式架构确认后重算实际尺寸约束。

数据覆盖结论仅沿用已审计 July 2024 Himawari 网格与 IMERG 目标坐标，不声称其余 Himawari 月已通过 QC。`covers_yunnan_context` 的科学充分性仍为 PENDING_RESEARCHER_CONFIRMATION；能覆盖 polygon 不等于足够天气上下文。

生成脚本/坐标/冻结 registry hashes 见 evidence_registry.csv、candidate_coordinate_indices.json 和 frozen_spatial_anchor_verification.json。
