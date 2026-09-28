# Exact IMERG mask alignment: PASS

未合成target坐标。旧processed mask的lat/lon哈希与正式P0 grid audit不同，因此没有复用其坐标；只读读取P0第一行明确对应的一个原始IMERG文件，恢复float32 lat/lon后两个哈希均完全匹配正式审计。整个IMERG库未重扫。

坐标副本imerg_actual_coordinates.npz及来源证据imerg_coordinate_reuse.json保留真实值。输出两种NetCDF mask的维度严格为(lat,lon)=(130,140)，逐元素lat/lon exact match，latitude ascending保留，无flip/transpose/index offset。DEM/GFS descending不影响目标坐标。

center候选为严格内部contains，精确位于polygon boundary的中心排除；本次恰在边界的中心数0。intersection候选为闭合cell polygon相交，包括触边。cell边界从真实相邻中心中点和首尾局部间距外推构造，不硬编码0.05°偏移；这也是候选工程几何语义，不宣称原IMERG文件提供过这些bounds。

center=3430，intersection=3752，difference=322；差异格点逐row/col/lat/lon保存，center为intersection子集。两者均候选，没有自行批准最终规则。
