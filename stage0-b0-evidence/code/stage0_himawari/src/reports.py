"""Source-grounded final reports; readiness means researcher review, never full-run approval."""
from __future__ import annotations
from datetime import datetime,timezone
from pathlib import Path
import json,logging,subprocess,sys
import numpy as np
import pandas as pd
from config import PROJECT,RAW,CONFIG
from common import write_json,write_table,write_text,sha256

def validate_sources(out):
    before=pd.read_csv(out/"index/raw_file_manifest_202407.csv")
    checks=[]
    for row in before.to_dict("records"):
        p=RAW/row["relative_path"];s=p.stat()
        checks.append({"relative_path":row["relative_path"],"size_unchanged":s.st_size==row["size_bytes"],
                       "mtime_unchanged":s.st_mtime_ns==row["mtime_ns"]})
    frame=pd.DataFrame(checks);write_table(frame,out/"audit/source_integrity_final.csv")
    assert frame.size_unchanged.all() and frame.mtime_unchanged.all(),"Source stat changed during run"
    # Preserve and verify the previous run's exact five cached diagnostic samples.
    old=PROJECT/"outputs/202407/run_20260927T102645_638388Z"
    cache=pd.read_csv(old/"benchmark/cache_benchmark_202407.csv")
    records=[]
    for r in cache.to_dict("records"):
        records.append({"source_path":r["source_path"],"cache_path":r["cache_path"],
                        "source_matches_prior_sha256":sha256(Path(r["source_path"]))==r["source_sha256"],
                        "diagnostic_cache_matches_prior_sha256":sha256(Path(r["cache_path"]))==r["cache_sha256"]})
    preserved=pd.DataFrame(records);write_table(preserved,out/"audit/previous_diagnostic_cache_integrity.csv")
    assert preserved.source_matches_prior_sha256.all() and preserved.diagnostic_cache_matches_prior_sha256.all()
    old_status=json.loads((old/"reports/dry_run_summary_202407.json").read_text(encoding="utf-8"))
    assert old_status["status"]=="DRY_RUN_FAILED"
    return True

def write_reports(out,master,sequences,audit,benchmark,dummy,test_count):
    env=json.loads((out/"reports/environment.json").read_text(encoding="utf-8"))
    monthly=json.loads((out/"reports/monthly_status.json").read_text(encoding="utf-8"))
    io=pd.DataFrame([json.loads(s) for s in (out/"audit/staging_io.jsonl").read_text(encoding="utf-8").splitlines()])
    write_table(io,out/"audit/staging_io_202407.csv")
    stages={"copy_count":len(io),"total_copied_bytes":int(io.temporary_bytes.sum()),
            "peak_per_copy_bytes":int(io.temporary_bytes.max()),"copy_seconds":float(io.copy_seconds.sum()),
            "read_seconds":float(io.read_seconds.sum()),"cleanup_failed":int((~io.cleanup_success).sum()),
            "sha256_verified_copies":int(io.sha256_verified.sum()),
            "current_staging_bytes":sum(p.stat().st_size for p in (PROJECT/"cache/staging"/out.name).glob("*.nc"))}
    write_json(out/"benchmark/staging_io_summary.json",stages)
    comparison=benchmark[benchmark.operation!="create"].groupby(["format","operation"]).seconds_per_operation.median()
    create=benchmark[benchmark.operation=="create"].set_index("format")
    speed={fmt:float(comparison.loc[(fmt,"random_6frame")]) for fmt in ("zarr","netcdf4")}
    recommendation=min(speed,key=speed.get)
    # Decision is explicitly a limited machine/subset recommendation, not a frozen scientific format.
    status=dict(status="READY_FOR_RESEARCHER_REVIEW",resume_from="DRY_RUN_FAILED",
                ended_utc=datetime.now(timezone.utc).isoformat(),**{k:v for k,v in monthly.items() if k!="status"},
                sample_audit_pass_count=int(audit.audit_status.eq("PASS").sum()),
                expected_unloadable_sample_count=int(audit.audit_status.eq("EXPECTED_UNLOADABLE").sum()),
                random_audit_pass_count=int((audit.selection_reason.str.contains("random_seed_42")&audit.audit_status.eq("PASS")).sum()),
                dummy_pass_count=len(dummy),automated_tests_passed=test_count,
                staging=stages,recommended_candidate= recommendation+" for researcher review only",
                raw_h_drive_modified=False,formal_train_mean_std_computed=False,full_processing_started=False,
                covers_yunnan_context="PENDING_RESEARCHER_CONFIRMATION",
                scientific_timing_decision="UNRESOLVED_INTERNAL_TIMES_AFTER_NOMINAL")
    assert status["random_audit_pass_count"]>=50 and status["dummy_pass_count"]>=50
    assert (out/"benchmark/storage_roundtrip_validation_202407.csv").exists()
    if len(master.satellite.unique())!=1:raise RuntimeError("Satellite QC comparison must be implemented before readiness")
    qc=master.quality_class.value_counts().to_dict()
    grid=pd.read_csv(out/"qc/grid_consistency_report_202407.csv")
    lines=[
      "# STORAGE BENCHMARK — 2024-07",
      "Scope: measured representative subset; QC_STAT_ONLY. No permanent storage choice is frozen.",
      f"Environment: {json.dumps(env['packages'],ensure_ascii=False)}",
      f"Machine: {env['os']}; Python: {env['python']}. CPU execution.",
      "Input subset: 50 seeded random complete sequences plus 50 consecutive complete targets; frame manifest deduplicated.",
      "Readable all-fill, partial-valid, grid-variant and coordinate-anomaly samples are added if present. This month none were found.",
      "Time/channel storage: (N,7,H,W), with sequence index reconstructing (6,7,H,W); no flattened channel storage.",
      "Chunk shape: (1,7,128,128); edge chunks smaller. float32 physical brightness temperature.",
      "Zarr library 3.4.0 writes interoperable Zarr format 2; numcodecs Blosc zstd level 3, bitshuffle; bool mask.",
      "NetCDF4/HDF5: zlib level 3, shuffle=True; uint8 mask with explicit boolean decoding.",
      "Both preserve source/global/channel/time/coordinate metadata in per-grid JSONL sidecars; channel labels and K units also in dataset attrs.",
      "Both keep native descending latitude. No normalization, resampling, or fill replacement.",
      "Every candidate frame passed exact x/mask fingerprint comparison against the decoded source.",
      "Write timing is recorded both end-to-end (including source staging and decoding) and storage-write-only.",
      "Sizes include dataset payload, mask, coordinates and metadata sidecars.",
      "Read tests use open handles, one read per frame and np.stack; 3 repetitions with alternating format order.",
      "All read numbers are warm OS/backend cache; no privileged cache flush or cold-disk claim.",
      "Sequential 6-frame test advances through contiguous target times; each sequence remains newest-to-oldest.",
      "Peak memory uses Windows working-set samples every 10 ms; lifetime high-water is separately reported.",
      "Candidate creation is a single measured run per format. Peak RSS includes interpreter/libraries and allocator/cache retention.",
      "",
      "| Format | Write only (s) | End-to-end create (s) | Bytes | Random 1-frame (s) | Sequential 6-frame (s) | Random 6-frame (s) |",
      "|---|---:|---:|---:|---:|---:|---:|"]
    for fmt in ("zarr","netcdf4"):
        c=create.loc[fmt]
        lines.append(f"| {fmt} | {c.write_seconds:.3f} | {c.seconds:.3f} | {int(c.total_bytes)} | {comparison.loc[(fmt,'single_frame_random')]:.6f} | {comparison.loc[(fmt,'sequential_6frame')]:.6f} | {comparison.loc[(fmt,'random_6frame')]:.6f} |")
    lines += ["",f"Recommendation for researcher review: {recommendation}, based on this subset's median random-six-frame time.",
      "Tradeoffs: Zarr exposes bool masks and independently addressable chunks but creates many small files. NetCDF4 keeps each grid in one HDF5 container, requires uint8-to-bool mask decoding, and benefits from backend chunk caching.",
      "Both return NumPy arrays usable with torch.from_numpy. No PyTorch training or GPU benchmark was run.",
      f"Staging cost across the entire resumed workflow: {stages['copy_count']} copies, {stages['total_copied_bytes']} cumulative bytes, {stages['copy_seconds']:.3f} s copying, {stages['read_seconds']:.3f} s reading/decoding.",
      f"Maximum one-file temporary size: {stages['peak_per_copy_bytes']} bytes; retained staging: {stages['current_staging_bytes']} bytes; cleanup failures: {stages['cleanup_failed']}.",
      "The cumulative copied byte count includes repeated reads, not persistent disk usage. Prior five diagnostic cache files remain untouched.",
      "Per-operation measurements, memory and staging details are in CSV/JSON. Do not extrapolate to cold storage or other hardware without measurement."]
    write_text(out/"benchmark/STORAGE_BENCHMARK_202407.md","\n".join(lines))
    start_delta=master.start_time_minus_nominal_seconds
    end_delta=master.end_time_minus_nominal_seconds
    report=[
      "# HIMAWARI STAGE-0 DRY-RUN — 2024-07",
      "Result: READY_FOR_RESEARCHER_REVIEW. This is engineering review readiness, not approval for full processing or a resolved latency convention.",
      "Previous preflight DRY_RUN_FAILED and five diagnostic cache files have been retained and checked.",
      "",
      "## Answers to required questions",
      f"1. Raw files scanned: {len(master)}. All were read from the July source tree; no assumed count.",
      f"2. Monthly successful seven-channel reads: {int(master.read_success.sum())}.",
      f"3. Monthly failed reads: {int((~master.read_success).sum())}.",
      f"4. Primary QC counts: {json.dumps(qc)}. Zero classes are explicit in qc_summary CSV.",
      f"5. Seven fixed-order channels present: {int(master.has_all_7_channels.sum())}/{len(master)}.",
      "6–9. Actual grid summary: "+grid.to_json(orient="records"),
      "Global pixel_number/line_number attributes are not used as scientific shape. Grid fingerprint uses actual coordinates and variable shape.",
      "10. Satellite presence: "+str(monthly["satellites"])+". H08/H09 comparison: NOT_APPLICABLE; comparison_not_available_in_202407.",
      f"11. Complete six-frame sequences: {monthly['complete']}.",
      f"12. Incomplete sequences: {monthly['incomplete']}; total target grid: {monthly['total_targets']}.",
      f"13. Month boundary: {monthly['boundary_files']} exact June 30 historical files audited; no June monthly pass.",
      "14. Chinese path: read-only binary copy to bounded English staging; size checked every time, SHA256 on key samples; cleanup only owned temporary files.",
      "15. Zarr vs NetCDF4/HDF5: both created, all frames roundtrip-validated, three repeated measured read workloads; see STORAGE_BENCHMARK_202407.md.",
      f"16. Sample audit: {status['random_audit_pass_count']} seeded random complete sequences PASS; total loaded PASS={status['sample_audit_pass_count']}; expected incomplete/unloadable cases={status['expected_unloadable_sample_count']}. These incomplete cases are not labeled PASS.",
      f"17. PyTorch dummy loading: {len(dummy)} sequences PASS for (6,7,H,W), (42,H,W), (1,42,H,W), float32 and bool masks.",
      f"18. Sample-audit sampled peak working set: {audit.memory_peak_mb.max():.2f} MiB; dummy: {dummy.memory_peak_mb.max():.2f} MiB; benchmark: {benchmark.memory_peak_mb.max():.2f} MiB. RSS baseline/delta and process-lifetime peaks are separate columns.",
      f"19. Unresolved: all {int(master.time_mismatch.sum())} nominal/internal time mismatches; bbox/context not frozen; warm-cache single-machine benchmark; format not frozen.",
      "20. Engineering recommendation: READY_FOR_RESEARCHER_REVIEW only. Full 2023–2025 processing has NOT started.",
      "",
      "## Time and availability finding requiring researcher interpretation",
      f"Internal start minus nominal range: {start_delta.min():.6f} to {start_delta.max():.6f} seconds.",
      f"Internal end minus nominal range: {end_delta.min():.6f} to {end_delta.max():.6f} seconds.",
      "TIME_MISMATCH means numerical inequality using 1 s tolerance; it does not by itself prove sensor corruption.",
      "The six-frame finder enforces filename nominal sat_time <= target_time, as explicitly allowed for candidate indexing.",
      "Internal scan end and product creation times can be later than that nominal target. This workflow does not claim those observations were operationally available at nominal target time.",
      "No internal time was overwritten and no later nominal frame was loaded. Actual availability/target-time convention must be frozen before training or an operational interpretation.",
      "",
      "## Fixed engineering thresholds and reproducibility",
      "config.json records all thresholds: ALL_FILL exactly 0 valid; PARTIAL_VALID between 0 and 1; almost-empty below 0.01 diagnostic; median-size ratios 0.25/4 only diagnostic; spacing tolerance 0.00002 degrees; time tolerance 1 s.",
      "Most-frequent exact-coordinate fingerprint defines grid reference. Filename tags alone do not disqualify a file.",
      "covers_yunnan_context=PENDING_RESEARCHER_CONFIRMATION. No historical bbox adopted; province evaluation mask remains a later researcher decision.",
      "Missing/invalid pixels remain NaN with an independent mask. No latitude flip, replacement, interpolation or automatic repair.",
      "Parquet engine is pyarrow; CSV and Parquet were both written and read-checked.",
      f"Automated scientific tests passed: {test_count}. Tests do not substitute for 50 real-source audits or storage roundtrips.",
      "Scientific pipelines use only supplied project environment. h5py/psutil/pytest are not required; netCDF4, Windows memory counters and unittest cover this run.",
      "No formal train mean/std, split, model training, GFS/IMERG/DEM, or later stage work performed.",
      "",
      "## Source integrity and staging",
      "All July source file size/mtime pairs unchanged after the run. Prior five source and diagnostic-cache SHA256 values unchanged. This is not a full-month content-hash proof.",
      "No code opens any H-drive file for writing. Only owned, resolved F-drive staging paths are unlinked.",
      json.dumps(stages),
      "",
      "## Output navigation",
      "index/: monthly CSV/Parquet master, sequence, boundary QC, scan manifest and checkpoints.",
      "qc/: primary QC counts, grid report, full source metadata JSONL and explicit non-applicable satellite comparison.",
      "audit/: fixed sample list, audit, tensor loading, source checks, tests, staging records.",
      "benchmark/: candidate datasets, per-frame metadata, manifest, roundtrip evidence and measured timings.",
      "reports/: environment, config, source hashes, final status and rerun commands. resume_202407.log records progression."
    ]
    write_text(out/"reports/README_HIMAWARI_PREPROCESS_202407.md","\n".join(report))
    commands=r"""# Reproducible commands (PowerShell)
Use only F:\pytorch\Research\.venv\Scripts\python.exe. No environment installation is performed.
Optional activation:
& 'F:\pytorch\Research\.venv\Scripts\Activate.ps1'

## New complete July dry-run, creates a NEW resume directory
& 'F:\pytorch\Research\.venv\Scripts\python.exe' -B 'F:\pytorch\Research\stage0_himawari\src\run_stage0_dryrun.py' --year 2024 --month 7 --phase all

## Scan / QC / grid audit / master and sequence indexing
Run the all command with --phase monthly. It creates a new run and executes Steps 4–7.
Or invoke run_monthly.py --run-dir '<new prepared run dir>' --year 2024 --month 7.

## Continue sample audit → benchmark → dummy → tests → reports
& 'F:\pytorch\Research\.venv\Scripts\python.exe' -B 'F:\pytorch\Research\stage0_himawari\src\run_stage0_dryrun.py' --run-dir '<run dir>' --phase remaining

## Individual stages (only if their output does not already exist)
run_stage0_dryrun.py --run-dir '<run dir>' --phase audit
run_stage0_dryrun.py --run-dir '<run dir>' --phase benchmark
run_stage0_dryrun.py --run-dir '<run dir>' --phase dummy
run_stage0_dryrun.py --run-dir '<run dir>' --phase final

## Automated tests
& 'F:\pytorch\Research\.venv\Scripts\python.exe' -B 'F:\pytorch\Research\stage0_himawari\tests\test_stage0.py'

Outputs are exclusive-created. Do not rerun completed stages into the same run.
Previous run_20260927T102645_638388Z is immutable failure history.
This implementation accepts year/month parameters but execution authorization is gated to 2024-07.
Before extending scope, researcher authorization and gate update are required.
"""
    write_text(out/"reports/RUN_COMMANDS_202407.md",commands)
    hashes=[{"path":str(p.relative_to(PROJECT)),"sha256":sha256(p)}
            for folder in ("src","tests") for p in sorted((PROJECT/folder).glob("*.py"))]
    write_table(pd.DataFrame(hashes),out/"reports/code_sha256.csv")
    write_json(out/"reports/final_dry_run_status_202407.json",status)
    logging.info("FINAL_STATUS %s",status)
    return status
