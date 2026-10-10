# Shared scaler、真实云南 mask 与 SP04

本轮读取冻结 scaler 和真实 mask 文件字节；不使用人工 3430 格点排列。scaler JSON 数值由 Python binary64 解析，原始 Kelvin 是 FP32，计算为 ((x.astype(float64)-mean_K)/std_K).astype(float32)。未拟合、裁剪或替换统计量。B0 与 B1 的固定预处理共用同一 artifact。

mask 使用冻结正式 read_frozen_yunnan_mask；SP04 使用原 load_sp04。原始 mask 为 130×140，裁切 [10:110,20:120] 成 100×100，必须仍有3430中心入界格点；经纬度以原始 FP32 位模式比较，禁止翻转、重建或换掩膜。SP04 10000×25 成员映射须覆盖250000唯一原生中心。

观测/参考有效掩膜表示数据有效性；云南评价 mask 表示地理范围。二者分别构造，监督交集计数，不以相互赋值替代。


```json
{
  "status": "PASS",
  "scaler_sha256": "656fe7a929cbd8617b08427e8d1fa7029b26512253efb44faa576796137d4a31",
  "mean_K": 271.60515414265217,
  "std_K": 19.93959597783802,
  "scaler_storage": "JSON number, parsed Python binary64",
  "normalization_calculation_dtype": "float64",
  "normalization_output_dtype": "float32",
  "B0_B1_shared_scaler": true,
  "refit": false,
  "mask_sha256": "9d921def661fc3e58cd1ed783fcf87abbf493da6ae5e5fea79c28043f73495ef",
  "mask_native_shape": [
    130,
    140
  ],
  "mask_target_shape": [
    100,
    100
  ],
  "mask_native_dtype": "uint8",
  "mask_dimensions": [
    "lat",
    "lon"
  ],
  "mask_true_count": 3430,
  "mask_distinct_from_observation_validity": true,
  "axes": {
    "native_lat": {
      "length": 501,
      "dtype": "float32",
      "direction": "DESCENDING",
      "first": 30.0,
      "last": 20.0,
      "raw_bytes_sha256": "dc82ee6d54c12e796ec2b9751ef388441d22a877d4e73aa1ba4702cdada72c52"
    },
    "native_lon": {
      "length": 501,
      "dtype": "float32",
      "direction": "ASCENDING",
      "first": 97.0,
      "last": 107.0,
      "raw_bytes_sha256": "9303bfb46b0873cf35008ab1860445af9811f05a5b60f8eb9e30aaff95d2968b"
    },
    "target_lat": {
      "length": 100,
      "dtype": "float32",
      "direction": "ASCENDING",
      "first": 20.049999237060547,
      "last": 29.94999885559082,
      "raw_bytes_sha256": "2c12a5b12969ddc2625686eae7ca561286b467b72e56a06493fe34800fb5aa5e"
    },
    "target_lon": {
      "length": 100,
      "dtype": "float32",
      "direction": "ASCENDING",
      "first": 97.04999542236328,
      "last": 106.94999694824219,
      "raw_bytes_sha256": "07cc72b46ff87949b32c5c265af48211a28331055ed25166d499647a2b02ad07"
    }
  },
  "sp04_indices_shape": [
    10000,
    25
  ],
  "sp04_unique_native_members": 250000
}
```

scaler 原始较早 JSON 中的 B0 adoption 待决文字未改写；本次使用同一 scaler 的依据是后续冻结 v2 协议 USE_FROZEN_B1_SHARED_SCALER，不生成新的研究者批准。
