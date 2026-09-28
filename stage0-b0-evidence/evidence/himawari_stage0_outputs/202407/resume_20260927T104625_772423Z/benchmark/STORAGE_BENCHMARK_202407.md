# STORAGE BENCHMARK — 2024-07
Scope: measured representative subset; QC_STAT_ONLY. No permanent storage choice is frozen.
Environment: {"numpy": "2.5.3", "pandas": "3.0.6", "xarray": "2026.7.0", "netCDF4": "1.7.4", "zarr": "3.4.0", "numcodecs": "0.17.0", "pyarrow": "25.0.1", "h5py": {"error": "No module named 'h5py'"}, "h5netcdf": "1.8.1", "torch": "2.14.0+cpu"}
Machine: Windows-11-10.0.26100-SP0; Python: F:\pytorch\Research\.venv\Scripts\python.exe. CPU execution.
Input subset: 50 seeded random complete sequences plus 50 consecutive complete targets; frame manifest deduplicated.
Readable all-fill, partial-valid, grid-variant and coordinate-anomaly samples are added if present. This month none were found.
Time/channel storage: (N,7,H,W), with sequence index reconstructing (6,7,H,W); no flattened channel storage.
Chunk shape: (1,7,128,128); edge chunks smaller. float32 physical brightness temperature.
Zarr library 3.4.0 writes interoperable Zarr format 2; numcodecs Blosc zstd level 3, bitshuffle; bool mask.
NetCDF4/HDF5: zlib level 3, shuffle=True; uint8 mask with explicit boolean decoding.
Both preserve source/global/channel/time/coordinate metadata in per-grid JSONL sidecars; channel labels and K units also in dataset attrs.
Both keep native descending latitude. No normalization, resampling, or fill replacement.
Every candidate frame passed exact x/mask fingerprint comparison against the decoded source.
Write timing is recorded both end-to-end (including source staging and decoding) and storage-write-only.
Sizes include dataset payload, mask, coordinates and metadata sidecars.
Read tests use open handles, one read per frame and np.stack; 3 repetitions with alternating format order.
All read numbers are warm OS/backend cache; no privileged cache flush or cold-disk claim.
Sequential 6-frame test advances through contiguous target times; each sequence remains newest-to-oldest.
Peak memory uses Windows working-set samples every 10 ms; lifetime high-water is separately reported.
Candidate creation is a single measured run per format. Peak RSS includes interpreter/libraries and allocator/cache retention.

| Format | Write only (s) | End-to-end create (s) | Bytes | Random 1-frame (s) | Sequential 6-frame (s) | Random 6-frame (s) |
|---|---:|---:|---:|---:|---:|---:|
| zarr | 22.415 | 38.076 | 1421023838 | 0.022779 | 0.137353 | 0.135087 |
| netcdf4 | 38.284 | 53.180 | 1078980336 | 0.026146 | 0.115146 | 0.158233 |

Recommendation for researcher review: zarr, based on this subset's median random-six-frame time.
Tradeoffs: Zarr exposes bool masks and independently addressable chunks but creates many small files. NetCDF4 keeps each grid in one HDF5 container, requires uint8-to-bool mask decoding, and benefits from backend chunk caching.
Both return NumPy arrays usable with torch.from_numpy. No PyTorch training or GPU benchmark was run.
Staging cost across the entire resumed workflow: 5736 copies, 26856686346 cumulative bytes, 71.263 s copying, 157.858 s reading/decoding.
Maximum one-file temporary size: 5935249 bytes; retained staging: 0 bytes; cleanup failures: 0.
The cumulative copied byte count includes repeated reads, not persistent disk usage. Prior five diagnostic cache files remain untouched.
Per-operation measurements, memory and staging details are in CSV/JSON. Do not extrapolate to cold storage or other hardware without measurement.