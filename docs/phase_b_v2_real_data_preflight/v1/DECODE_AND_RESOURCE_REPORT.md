# 限定解码与资源

取样在任何参考降水像元读取前固定：冻结各月顺序的索引 0、floor(n/2)、n−1。冻结仅有3–10月，2023/2024共16月，最多48实际场景；72是研究者同意的总上限。没有用降水值或模型输出筛样本，不足3场景的月份停止、不补选。


```json
{
  "status": "PASS",
  "selected_scenes": 48,
  "decoded_scenes": 48,
  "full_raw_dataset_decoded": false
}
```


```json
{
  "selected_scenes": 48,
  "elapsed_seconds": 329.37256999999954,
  "resources": {
    "working_set_bytes": 1449922560,
    "peak_working_set_bytes": 1459916800,
    "private_bytes": 2651881472,
    "peak_pagefile_bytes": 2662313984
  },
  "limits": {
    "max_scenes": 72,
    "max_payload_file_bytes": 734003200,
    "max_total_data_bytes": 2147483648,
    "max_working_set_bytes": 2147483648,
    "max_elapsed_seconds": 900
  }
}
```

每个成功场景的形状、dtype、有效性、CF 时间及耗时见 audit_results.json。只公开工程检查，不公开降水数组、图像、雨强分布或任何模型性能指标。限定解码不是全量数据 QC；受阻项目不会被标成通过。

读取先做完整文件 SHA，再以同一已计数 bytes buffer 调用 frozen netCDF readers。未创建原始数据的磁盘暂存副本。CPU 峰值由 Windows GetProcessMemoryInfo 的进程生命期 PeakWorkingSetSize 提供；不是GPU显存，也不是每场景独立峰值。耗时包含来源审计、stat、解码等预检工作，不能外推训练时长。

账本统计受控 Python application read 的成功/尝试次数及 read 返回字节，内存 netCDF view 不另记物理读取；不是操作系统底层打开次数或物理磁盘流量。前期一次已授权 PowerShell scaler 查看发生在计数器安装前，底层字节/打开数 NOT_INSTRUMENTED，单独披露，未伪装成全部已测量。


```json
{
  "controlled_read_open_attempts": 816,
  "controlled_read_open_successes": 816,
  "controlled_application_bytes_returned": 1495116273,
  "groups": {
    "PUBLIC_METADATA": {
      "read_open_attempts": 478,
      "read_open_successes": 478,
      "bytes_returned": 70335386,
      "sha_pass_reads": 478,
      "unique_files": 472
    },
    "SCALER": {
      "read_open_attempts": 1,
      "read_open_successes": 1,
      "bytes_returned": 1918,
      "sha_pass_reads": 1,
      "unique_files": 1
    },
    "YUNNAN_MASK": {
      "read_open_attempts": 1,
      "read_open_successes": 1,
      "bytes_returned": 20916,
      "sha_pass_reads": 1,
      "unique_files": 1
    },
    "B13_2023": {
      "read_open_attempts": 144,
      "read_open_successes": 144,
      "bytes_returned": 706100659,
      "sha_pass_reads": 144,
      "unique_files": 123
    },
    "IMERG_2023": {
      "read_open_attempts": 24,
      "read_open_successes": 24,
      "bytes_returned": 14820344,
      "sha_pass_reads": 24,
      "unique_files": 24
    },
    "B13_2024": {
      "read_open_attempts": 144,
      "read_open_successes": 144,
      "bytes_returned": 684196088,
      "sha_pass_reads": 144,
      "unique_files": 123
    },
    "IMERG_2024": {
      "read_open_attempts": 24,
      "read_open_successes": 24,
      "bytes_returned": 19640962,
      "sha_pass_reads": 24,
      "unique_files": 24
    }
  },
  "in_memory_netcdf_views": 386
}
```

## 独立汇总核验

```json
{
  "status": "PASS",
  "verified_at_utc": "2026-10-10T10:51:59.709270+00:00",
  "readonly_unit_tests_passed": 36,
  "frozen_public_inventory_SHA_recheck": 402,
  "prior_delivery_manifest_members_SHA_recheck": 51,
  "raw_data_read_opens": 336,
  "raw_data_unique_files": 294,
  "raw_data_bytes_returned": 1424758053,
  "scaler_and_mask_read_opens": 2,
  "all_controlled_read_opens": 816,
  "selected_scenes": 48,
  "sample_selection_before_first_reference_bytes": true,
  "decode_read_normalization_seconds_sum": 8.12875219999114,
  "decode_scene_seconds_min": 0.13367470000230242,
  "decode_scene_seconds_max": 0.21087089999491582,
  "unselected_raw_files_full_SHA_NOT_VERIFIED": 66712,
  "peak_working_set_MiB": 1392.28515625,
  "peak_committed_pagefile_MiB": 2538.98046875,
  "limits_applied": "Working set, payload bytes and elapsed time caps; private commit measured separately",
  "model_forwards": 0,
  "optimizer_steps": 0,
  "2025_raw_reads": 0,
  "private_checkpoint_reads": 0,
  "initial_launcher_failure_retained": true,
  "overall_readiness_status_unchanged": "NOT_VERIFIED"
}
```

收尾保护修正后最终44项工具测试通过。前期负面测试路径属性查询未计数，公开零2025计数仅指内容读取；详细限制见READONLY_GUARD_HARDENING.md。
