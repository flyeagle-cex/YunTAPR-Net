# B0/B1 接口兼容性

实际来源为quantile_v2/models.py、heads.py、parameterization.py、outputs.py；backbone_b0.py、b1.py、blocks.py及spatial/projection.py、sp04_mapping.py。来源字节见source_identity.json。正式forward_loss仅只读核对，未调用。

|控制|实际检查|
|---|---|
|B0输入|[2,1,501,501]，取B1人工输入最后一槽|
|B1输入|[2,6,501,501]，60/50/40/30/20/10分钟、最旧到最新|
|M1|独立bool native mask全有效，缺测拒绝|
|中间特征|[2,48,501,501]→冻结SP04→[2,48,100,100]|
|双头|发生raw1；quantile raw33（allocation32+span1）→q32|
|目标/分位数|原FP32[2,1,100,100]；FP64[2,32,100,100]|
|精度|参数FP32、backbone/发生头BF16、raw quantile FP32、变换/Pinball FP64|
|阈值和分母|先float32>float32(0.1)再升精度；训练N_valid、科学CPB N_rain|
|support|SP04全1；原生invalid0；严格q顺序/支撑沿用原守卫|
|候选参数|E0=(.5,2,1)、E1=(.5,0,1)、E2=(.5,2,2)，来自既有get_config|

人工参考包含0、float32阈值、阈值向上相邻数及正雨强。当前N_valid=6860、N_rain=4900只是fixture属性。人工mask在每场景平铺前3430格点为True，不能检验真实云南地理配准。

SP04仍用原公开坐标轴和成员映射，每个目标单元25个原生中心取算术均值；没有重建或替换。shared scaler的身份与N0角色被核验；人工输入直接处于归一化数值空间，没有拟合scaler或对真实Kelvin观测应用它。实际解码、normalization和真实mask对应尚未验证。

CPU用例验证完整目标网格接口与负面条件，不运行CPU完整backbone backward；完整双模型forward/backward在CUDA执行，无CPU或精度降级。
