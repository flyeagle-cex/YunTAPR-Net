# 冻结数据身份审计

依据冻结 v2 Phase-A 协议 a0141f21cfa997d5adb72dff5afb32b17dc7edcf5f3397fc9c4bfe2ea42048be、四份样本 manifest 及 frame_identity_index，未另选数据源、补样本、改变划分或重新搜索磁盘。

原始顺序按 index、唯一 sample_id 与 UTC 严格递增检查；角色按 2023 Train / 2024 Validation 检查，后者科研解释仍是开发验证。B0/B1 比较目标窗口、IMERG 路径引用及 SHA、index、资格、云南有效格点数和最新时相；B0 最新文件大小、SHA、CF 时间还与 B1 slot5 逐项核对。


```json
{
  "status": "PASS",
  "train_scenes": 10455,
  "development_scenes": 10501,
  "original_order_unique_disjoint": true,
  "B0_B1_M1_paired": true
}
```


```json
{
  "unique_files": 67006,
  "by_kind": {
    "B13": 66516,
    "IMERG": 490
  },
  "stat_checks": 67006,
  "failures": 0,
  "status": "PASS",
  "unselected_payload_SHA": "NOT_VERIFIED_LIMITED_READ_SCOPE"
}
```

所有 stat 均针对 manifest 明确引用的路径，不遍历原始目录、不下载。日文件被多个场景引用是正常复用，不等于重复场景。相同路径的不同 SHA/大小/年份直接阻塞。stat 可证明当时路径存在及登记大小符合，不能证明未选中文件完整内容未变化；未读取的 payload SHA 明确 NOT_VERIFIED。


```json
{
  "status": "PASS",
  "prior_public_inventory_files": 402,
  "prior_delivery_manifest_members": 51,
  "tracked_baseline": "e0920d9375e1f351bc30933cd83b4e7ea41a68ae"
}
```
