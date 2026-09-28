# ENGINEERING_SMOKE_TEST_ONLY

实际读取N25E102的33×33原生窗口，保留纬度descending，不重采样。以WGS84椭球Geod.inv计算相邻点的物理距离，再构造带方向的行/列距离轴，计算dh/dx、dh/dy（m/m）。坡度采用atan(hypot)转度；aspect暂以顺时针自北的下坡方位表示，平坦处NaN，保留sin/cos。临时工程约定仅用于验证代码与单位，不是正式算法批准。

1089个高程和gradient结果有限；坡度0–72.72081073915831°仅QC_STAT_ONLY，无阈值判定或截断。记录于terrain_smoke_result.json及小型terrain_smoke_arrays.npz，未构造全域特征、训练数据、normalization或正式DOTE。pytest另用已知物理斜率验证量纲和纬度降序时的符号。
