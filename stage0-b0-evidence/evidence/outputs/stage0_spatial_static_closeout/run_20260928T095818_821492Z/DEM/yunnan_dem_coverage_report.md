# Yunnan DEM coverage

SRTM状态：**FULL（针对本轮工程验证的GADM level-1云南polygon）**。省界bounds为97.5341–106.1942E、21.1394–29.2511N。

判据不是bbox包含：SRTM全部237个真实raster footprint的union覆盖polygon，逐tile完整读取3073226637个样点，valid同数，NoData=0、nonfinite=0；all-touched云南区域与省界线像元中invalid均为0。因此省界附近未检测到NoData gap。原生Point采样的像元support用于此工程覆盖检验，不表示高程精度/地形细节完整性已获科学认证。

AWS_Skadi状态：MISSING（对云南本体）。3tile位于外围，不能单独作为云南DEM。SRTM包络中缺少的3tile均不侵入本轮云南polygon或97–107E、20–30N共同候选区域；没有自动用Skadi填补。

所有统计QC_STAT_ONLY。SRTM min=-468m/max=7439m；Skadi min=-94m/max=-18m。负值保留，不截断、不删除、不定义异常阈值。tile总像元计数包含共享边缘重复样点，不是去重地表面积。

最终边界文件版本仍待研究者批准；最终评价使用云南省全境行政区mask这一原则不变。
