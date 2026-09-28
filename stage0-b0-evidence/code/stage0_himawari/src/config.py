"""Frozen engineering choices for this run; no scientific bbox or train statistics."""
from pathlib import Path
CHANNELS = ("tbb_08","tbb_09","tbb_10","tbb_11","tbb_13","tbb_15","tbb_16")
PROJECT = Path("F:/pytorch/Research/stage0_himawari")
RAW = Path("H:/\u8475\u82b1202303_202510")
PYTHON = Path("F:/pytorch/Research/.venv/Scripts/python.exe")
CONFIG = {
 "channels":list(CHANNELS), "history_minutes":[0,10,20,30,40,50], "seed":42,
 "covers_yunnan_context":"PENDING_RESEARCHER_CONFIRMATION", "bbox":None,
 "all_fill_fraction":0.0, "partial_valid_upper":1.0, "almost_empty_fraction":0.01,
 "coordinate_spacing_atol_degrees":0.00002, "time_mismatch_tolerance_seconds":1.0,
 "size_anomaly_median_ratio_low":0.25,"size_anomaly_median_ratio_high":4.0,
 "grid_reference_rule":"most frequent exact coordinate fingerprint; ties retained as variants",
 "staging_max_bytes":268435456, "min_disk_free_bytes":1073741824,
 "audit_random_complete_targets":50,"benchmark_contiguous_target_count":50,
 "benchmark_random_single_frames":50,"benchmark_repeats":3,
 "chunk_shape":[1,7,128,128], "zarr_format":2,
 "zarr_compressor":{"id":"blosc","cname":"zstd","clevel":3,"shuffle":"bitshuffle"},
 "netcdf_compression":{"compression":"zlib","complevel":3,"shuffle":True},
 "memory_sample_interval_seconds":0.01,
 "target_time_semantics":"filename_nominal_utc; internal start/end audited separately",
 "qc_priority":["READ_ERROR","MISSING_CHANNEL","COORD_ANOMALY","ALL_FILL","PARTIAL_VALID",
                "TIME_MISMATCH","GRID_VARIANT","OTHER","OK"]
}
