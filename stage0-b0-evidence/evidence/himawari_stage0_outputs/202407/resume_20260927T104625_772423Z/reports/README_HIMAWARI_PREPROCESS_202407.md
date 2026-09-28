# HIMAWARI STAGE-0 DRY-RUN — 2024-07
Result: READY_FOR_RESEARCHER_REVIEW. This is engineering review readiness, not approval for full processing or a resolved latency convention.
Previous preflight DRY_RUN_FAILED and five diagnostic cache files have been retained and checked.

## Answers to required questions
1. Raw files scanned: 4390. All were read from the July source tree; no assumed count.
2. Monthly successful seven-channel reads: 4390.
3. Monthly failed reads: 0.
4. Primary QC counts: {"TIME_MISMATCH": 4390}. Zero classes are explicit in qc_summary CSV.
5. Seven fixed-order channels present: 4390/4390.
6–9. Actual grid summary: [{"grid_tag":"06001_06001","grid_signature":"e930fc8377b0d158b4b22834869896bcc5047b44e38b4c34f63b0b1103e4c255","file_count":4390,"shape":"(501,501)","lat_min":20.0,"lat_max":30.0,"lon_min":97.0,"lon_max":107.0,"lat_direction":"descending","lon_direction":"ascending","median_dlat":0.0200004578,"median_dlon":0.0199966431,"covers_yunnan_context":"PENDING_RESEARCHER_CONFIRMATION","anomaly_count":4390,"notes":"Exact coordinates hashed; no bbox criterion and no automatic latitude flip."}]
Global pixel_number/line_number attributes are not used as scientific shape. Grid fingerprint uses actual coordinates and variable shape.
10. Satellite presence: ['H09']. H08/H09 comparison: NOT_APPLICABLE; comparison_not_available_in_202407.
11. Complete six-frame sequences: 4020.
12. Incomplete sequences: 444; total target grid: 4464.
13. Month boundary: 5 exact June 30 historical files audited; no June monthly pass.
14. Chinese path: read-only binary copy to bounded English staging; size checked every time, SHA256 on key samples; cleanup only owned temporary files.
15. Zarr vs NetCDF4/HDF5: both created, all frames roundtrip-validated, three repeated measured read workloads; see STORAGE_BENCHMARK_202407.md.
16. Sample audit: 50 seeded random complete sequences PASS; total loaded PASS=56; expected incomplete/unloadable cases=3. These incomplete cases are not labeled PASS.
17. PyTorch dummy loading: 50 sequences PASS for (6,7,H,W), (42,H,W), (1,42,H,W), float32 and bool masks.
18. Sample-audit sampled peak working set: 418.90 MiB; dummy: 541.54 MiB; benchmark: 614.69 MiB. RSS baseline/delta and process-lifetime peaks are separate columns.
19. Unresolved: all 4390 nominal/internal time mismatches; bbox/context not frozen; warm-cache single-machine benchmark; format not frozen.
20. Engineering recommendation: READY_FOR_RESEARCHER_REVIEW only. Full 2023–2025 processing has NOT started.

## Time and availability finding requiring researcher interpretation
Internal start minus nominal range: 39.598106 to 41.915538 seconds.
Internal end minus nominal range: 577.463661 to 579.560364 seconds.
TIME_MISMATCH means numerical inequality using 1 s tolerance; it does not by itself prove sensor corruption.
The six-frame finder enforces filename nominal sat_time <= target_time, as explicitly allowed for candidate indexing.
Internal scan end and product creation times can be later than that nominal target. This workflow does not claim those observations were operationally available at nominal target time.
No internal time was overwritten and no later nominal frame was loaded. Actual availability/target-time convention must be frozen before training or an operational interpretation.

## Fixed engineering thresholds and reproducibility
config.json records all thresholds: ALL_FILL exactly 0 valid; PARTIAL_VALID between 0 and 1; almost-empty below 0.01 diagnostic; median-size ratios 0.25/4 only diagnostic; spacing tolerance 0.00002 degrees; time tolerance 1 s.
Most-frequent exact-coordinate fingerprint defines grid reference. Filename tags alone do not disqualify a file.
covers_yunnan_context=PENDING_RESEARCHER_CONFIRMATION. No historical bbox adopted; province evaluation mask remains a later researcher decision.
Missing/invalid pixels remain NaN with an independent mask. No latitude flip, replacement, interpolation or automatic repair.
Parquet engine is pyarrow; CSV and Parquet were both written and read-checked.
Automated scientific tests passed: 22. Tests do not substitute for 50 real-source audits or storage roundtrips.
Scientific pipelines use only supplied project environment. h5py/psutil/pytest are not required; netCDF4, Windows memory counters and unittest cover this run.
No formal train mean/std, split, model training, GFS/IMERG/DEM, or later stage work performed.

## Source integrity and staging
All July source file size/mtime pairs unchanged after the run. Prior five source and diagnostic-cache SHA256 values unchanged. This is not a full-month content-hash proof.
No code opens any H-drive file for writing. Only owned, resolved F-drive staging paths are unlinked.
{"copy_count": 5736, "total_copied_bytes": 26856686346, "peak_per_copy_bytes": 5935249, "copy_seconds": 71.2629659001177, "read_seconds": 157.85821770012262, "cleanup_failed": 0, "sha256_verified_copies": 29, "current_staging_bytes": 0}

## Output navigation
index/: monthly CSV/Parquet master, sequence, boundary QC, scan manifest and checkpoints.
qc/: primary QC counts, grid report, full source metadata JSONL and explicit non-applicable satellite comparison.
audit/: fixed sample list, audit, tensor loading, source checks, tests, staging records.
benchmark/: candidate datasets, per-frame metadata, manifest, roundtrip evidence and measured timings.
reports/: environment, config, source hashes, final status and rerun commands. resume_202407.log records progression.