"""Read-only July 2024 preflight. No package installation or month processing."""
from __future__ import annotations
import argparse
import csv
import hashlib
import importlib
import json
import logging
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone
from typing import Any

PROJECT = Path("F:/pytorch/Research")
SOURCE = Path("H:/\u8475\u82b1202303_202510")
CHANNELS = ("tbb_08", "tbb_09", "tbb_10", "tbb_11", "tbb_13", "tbb_15", "tbb_16")
PACKAGES = ("numpy", "xarray", "netCDF4", "h5netcdf", "h5py", "pandas", "pyarrow",
            "fastparquet", "zarr", "numcodecs", "torch", "psutil", "pytest")

def guard_output(path: Path) -> Path:
    """All outputs must remain under the F-drive project, including resolved links."""
    resolved = path.resolve()
    if not resolved.is_relative_to(PROJECT.resolve()):
        raise ValueError(f"Output outside F project: {resolved}")
    return resolved

def guard_source(path: Path, year: int, month: int) -> Path:
    """Preflight reads only the requested month, never a neighbouring directory."""
    resolved = path.resolve()
    if not resolved.is_relative_to((SOURCE / f"{year:04d}{month:02d}").resolve()):
        raise ValueError(f"Source outside permitted month: {resolved}")
    return resolved

def write_json(path: Path, value: Any) -> None:
    with guard_output(path).open("x", encoding="utf-8") as f:
        json.dump(value, f, ensure_ascii=False, indent=2)

def write_text(path: Path, value: str) -> None:
    with guard_output(path).open("x", encoding="utf-8") as f:
        f.write(value)

def write_csv(path: Path, rows: list[dict], fields: list[str] | None = None) -> None:
    columns = fields or list(dict.fromkeys(k for row in rows for k in row))
    with guard_output(path).open("x", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)

def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()

def probe(path: Path, source: Path, backend: str, strategy: str) -> dict:
    """Materialize all seven packed channels; this is a backend test, not scientific QC."""
    started = time.perf_counter()
    row = dict(backend=backend, source_path=str(source), read_path=str(path),
               strategy=strategy, success=False, error_type="", error_message="")
    try:
        if backend == "h5py":
            import h5py
            with h5py.File(path, "r") as ds:
                shapes = {ch: list(ds[ch][...].shape) for ch in CHANNELS}
        else:
            import xarray as xr
            with xr.open_dataset(path, engine=backend, mask_and_scale=False,
                                 decode_times=False) as ds:
                shapes = {ch: list(ds[ch].values.shape) for ch in CHANNELS}
        row.update(success=True, channel_shapes=json.dumps(shapes))
    except Exception as error:
        row.update(error_type=type(error).__name__, error_message=str(error))
    row["read_seconds"] = time.perf_counter() - started
    return row

def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--year", type=int, default=2024)
    parser.add_argument("--month", type=int, default=7)
    args = parser.parse_args()
    # Explicit run authorization is narrower than parameterized implementation.
    if (args.year, args.month) != (2024, 7):
        parser.error("Only 2024-07 is authorized for this dry-run.")
    expected_python = PROJECT / ".venv/Scripts/python.exe"
    if Path(sys.executable).resolve() != expected_python.resolve():
        raise RuntimeError("Must use the project virtual environment.")
    start = datetime.now(timezone.utc)
    tag = f"{args.year:04d}{args.month:02d}"
    root = guard_output(PROJECT / "stage0_himawari")
    run_id = start.strftime("run_%Y%m%dT%H%M%S_%fZ")
    output = guard_output(root / "outputs" / tag / run_id)
    output.mkdir(parents=True, exist_ok=False)
    for folder in ("index", "qc", "benchmark", "audit", "reports"):
        (output / folder).mkdir()
    log_path = output / f"preprocess_{tag}.log"
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s",
                        handlers=[logging.FileHandler(log_path, mode="x", encoding="utf-8"),
                                  logging.StreamHandler(sys.stdout)])
    log = logging.getLogger("preflight")
    log.info("Started %s; Python=%s; outputs=%s", start.isoformat(), sys.executable, output)
    deps = []
    for name in PACKAGES:
        try:
            module = importlib.import_module(name)
            deps.append(dict(package=name, import_success=True,
                             version=getattr(module, "__version__", ""), error=""))
        except Exception as error:
            deps.append(dict(package=name, import_success=False, version="",
                             error=f"{type(error).__name__}: {error}"))
    available = {d["package"] for d in deps if d["import_success"]}
    missing_required = sorted({"numpy","xarray","netCDF4","pandas","zarr","numcodecs","torch"} - available)
    if not ({"pyarrow", "fastparquet"} & available):
        missing_required.append("pyarrow OR fastparquet")
    environment = dict(start_time_utc=start.isoformat(), executable=sys.executable,
                       python=sys.version, os=platform.platform(), packages=deps,
                       source_root=str(SOURCE / tag), output_dir=str(output),
                       seed=42, f_drive_free_bytes=shutil.disk_usage(PROJECT).free)
    git = subprocess.run(["git", "-C", str(PROJECT), "rev-parse", "HEAD"],
                         capture_output=True, text=True, check=False)
    environment["git_commit"] = git.stdout.strip() if git.returncode == 0 else "NOT_A_GIT_REPOSITORY"
    config = dict(year=args.year, month=args.month, channels=CHANNELS, seed=42,
                  compatibility_sample_count=5, cache_allowed=True,
                  covers_yunnan_context="PENDING_RESEARCHER_CONFIRMATION",
                  formal_bbox=None, qc_thresholds="NOT_IMPLEMENTED_PREFLIGHT_ONLY",
                  h_drive_write_allowed=False, package_install_allowed=False)
    write_json(output / "reports/environment.json", environment)
    write_json(output / "reports/config.json", config)
    write_csv(output / "reports/dependency_report.csv", deps)
    log.info("Missing required dependencies: %s", missing_required)
    files = sorted((SOURCE / tag).rglob("*.nc"))
    manifest = []
    for p in files:
        guard_source(p, args.year, args.month)
        st = p.stat()
        manifest.append(dict(relative_path=str(p.relative_to(SOURCE)), filename=p.name,
                             size_bytes=st.st_size, mtime_ns=st.st_mtime_ns))
    write_csv(output / "index" / f"raw_file_manifest_{tag}.csv", manifest,
              ["relative_path","filename","size_bytes","mtime_ns"])
    total_bytes = sum(row["size_bytes"] for row in manifest)
    log.info("Scanned files=%d bytes=%d", len(files), total_bytes)
    indices = sorted({round(i * (len(files)-1) / 4) for i in range(5)}) if files else []
    samples = [files[i] for i in indices]
    before = {str(p): sha256(p) for p in samples}
    rows = []
    for p in samples:
        for backend in ("netcdf4", "h5netcdf", "h5py"):
            row = probe(p, p, backend, "direct")
            rows.append(row)
            log.info("Backend=%s strategy=direct success=%s file=%s error=%s",
                     backend, row["success"], p.name, row["error_message"])
    direct = [b for b in ("h5netcdf","netcdf4") if samples and
              all(r["success"] for r in rows if r["backend"] == b)]
    copies = []
    strategy = direct[0] + "_direct" if direct else "NONE"
    # Only five files copied with exclusive creation. Source bytes are never opened for writing.
    if not direct and samples and "netCDF4" in available:
        cache = guard_output(root / "cache" / tag / run_id)
        cache.mkdir(parents=True, exist_ok=False)
        for i, p in enumerate(samples):
            dest = guard_output(cache / f"{i:02d}_{p.name}")
            t0 = time.perf_counter()
            with p.open("rb") as src, dest.open("xb") as dst:
                shutil.copyfileobj(src, dst, length=1024 * 1024)
            copy_seconds = time.perf_counter() - t0
            copied_hash = sha256(dest)
            if before[str(p)] != copied_hash:
                raise RuntimeError(f"Cache checksum mismatch: {p}")
            row = probe(dest, p, "netcdf4", "english_cache")
            rows.append(row)
            copies.append(dict(source_path=str(p), cache_path=str(dest), size_bytes=dest.stat().st_size,
                               copy_seconds=copy_seconds, source_sha256=before[str(p)],
                               cache_sha256=copied_hash, hash_match=True,
                               read_seconds=row["read_seconds"], read_success=row["success"]))
            log.info("Cache sample=%s success=%s bytes=%d", p.name, row["success"], dest.stat().st_size)
        if all(c["read_success"] for c in copies):
            strategy = "netcdf4_english_cache_5_sample_verified"
    write_csv(output / "qc/backend_compatibility_report.csv", rows)
    write_csv(output / "benchmark/cache_benchmark_202407.csv", copies,
              ["source_path","cache_path","size_bytes","copy_seconds","source_sha256",
               "cache_sha256","hash_match","read_seconds","read_success"])
    checks = []
    for row, p in zip(manifest, files):
        st = p.stat()
        checks.append(dict(source_path=str(p), size_unchanged=st.st_size == row["size_bytes"],
                           mtime_unchanged=st.st_mtime_ns == row["mtime_ns"],
                           sampled_sha256_unchanged=sha256(p) == before[str(p)] if str(p) in before else "NOT_HASHED"))
    write_csv(output / "audit/source_integrity_check.csv", checks)
    integrity = all(r["size_unchanged"] and r["mtime_unchanged"] and
                    r["sampled_sha256_unchanged"] is not False for r in checks)
    blocks = missing_required.copy()
    if strategy == "NONE":
        blocks.append("NO_VERIFIED_BACKEND")
    if not integrity:
        blocks.append("SOURCE_INTEGRITY_CHANGED")
    # Preflight cannot certify the downstream science, QC, audit, or loading pipeline.
    summary = dict(status="DRY_RUN_FAILED", execution_scope="PREFLIGHT_ONLY",
                   raw_files_scanned=len(files), source_bytes=total_bytes,
                   backend_sample_files=len(samples), selected_strategy=strategy,
                   cache_bytes=sum(c["size_bytes"] for c in copies),
                   blockers=blocks, source_integrity_check_pass=integrity,
                   full_month_read_success=None, full_month_read_failed=None,
                   qc="NOT_RUN", sequences="NOT_RUN", sample_audit="NOT_RUN",
                   storage_benchmark="NOT_RUN", pytorch_dummy_loading="NOT_RUN",
                   scientific_automated_tests="NOT_RUN", raw_h_drive_modified=False,
                   formal_train_statistics_computed=False, full_processing_started=False)
    write_json(output / "reports/dry_run_summary_202407.json", summary)
    planned = [
        "himawari_master_index_202407.parquet","himawari_master_index_202407.csv",
        "himawari_sequence_index_202407.parquet","himawari_sequence_index_202407.csv",
        "grid_consistency_report_202407.csv","h08_h09_channel_comparison_202407.csv",
        "qc_summary_202407.csv","storage_benchmark_202407.csv",
        "STORAGE_BENCHMARK_202407.md","pytorch_dummy_loading_report_202407.csv",
        "sample_audit_202407.csv"]
    write_csv(output / "reports/output_status_202407.csv",
              [dict(filename=n,status="BLOCKED_NOT_GENERATED",reason="Required dependencies missing; stopped before Step 4")
               for n in planned])
    python_command = "& 'F:\\pytorch\\Research\\.venv\\Scripts\\python.exe'"
    install = python_command + " -m pip install h5py pyarrow zarr numcodecs psutil pytest"
    commands = f"""# Commands — 2024-07 preflight only
Run from PowerShell. Each run creates a new timestamped output and cache directory.
No existing output or cache is overwritten or deleted.

## Activation (optional)
& 'F:\\pytorch\\Research\\.venv\\Scripts\\Activate.ps1'

## Actual environment / scan / compatibility / cache diagnostic
{python_command} -B 'F:\\pytorch\\Research\\stage0_himawari\\src\\preflight.py' --year 2024 --month 7

## Preflight guard tests (not the requested scientific test suite)
{python_command} -B 'F:\\pytorch\\Research\\stage0_himawari\\tests\\test_preflight.py'

## Dependency proposal — NOT executed; researcher approval required by no-environment-change instruction
First inspect resolver plan:
{install} --dry-run
Then review every planned change. Do not upgrade/downgrade Python, PyTorch, CUDA, or existing packages.
Only after approval, install a compatible pinned set in this exact environment.
h5py enables h5netcdf/HDF5; pyarrow enables Parquet; zarr/numcodecs enable Zarr.
psutil and pytest are optional engineering conveniences, not scientific requirements.
The preliminary command above is unpinned and is NOT a validated installation prescription.

## QC / index / benchmark / dummy / full dry-run
BLOCKED_NOT_IMPLEMENTED. No executable commands claimed for unfinished pipeline stages.
Resume from dependency verification, rerun backend compatibility, then implement and test Step 4.
"""
    write_text(output / "reports/RUN_COMMANDS_202407.md", commands)
    readme = f"""# HIMAWARI STAGE-0 DRY-RUN — 2024-07
Overall: DRY_RUN_FAILED (dependency gate; no scientific result claimed).

## Verified evidence
- Actual recursive scan: {len(files)} .nc files; {total_bytes} bytes ({total_bytes / 2**30:.4f} GiB).
- Required Python: {sys.executable}; version: {platform.python_version()}.
- All three backend strategies attempted on {len(samples)} files across the month.
- Selected diagnostic strategy: {strategy}.
- Added English-cache storage: {summary['cache_bytes']} bytes. Cache retained.
- Missing mandatory capabilities: {', '.join(blocks)}.
- H source writes issued: NO. All {len(files)} source size/mtime pairs checked again; five SHA256 values checked.
- Integrity verification: {integrity}. This is not a full-month content hash proof.
- Seed: 42 (reserved for later random sample audit; compatibility sample is deterministic spread).
- Config: reports/config.json. Logs: preprocess_202407.log.

## Required research questions
1. Raw file count: {len(files)}.
2. Monthly successful reads: NOT_RUN; five compatibility reads do not establish this count.
3. Monthly failed reads: NOT_RUN; direct-backend errors are not declarations of corrupt data.
4. Quality class counts: NOT_RUN.
5. Seven channels: see backend report for sample materialization; monthly assertion NOT_RUN.
6. Scientific grid shape: NOT_AUDITED; compatibility shape strings are diagnostic only.
7. Latitude/longitude directions: NOT_RUN.
8. Grid tag count: NOT_AUDITED.
9. Grid consistency within tags: NOT_RUN.
10. H08/H09 monthly scientific comparison: NOT_RUN; no fabricated comparison.
11. Complete sequences: NOT_RUN.
12. Incomplete sequences: NOT_RUN.
13. Cross-month sequence validation: NOT_RUN; no June files read during preflight.
14. Chinese-path workaround: {strategy}; see direct failures and cache hash verification.
15. Zarr vs NetCDF/HDF5: BLOCKED; cache diagnostic is not the requested storage benchmark.
16. Random 50-sample check: NOT_RUN.
17. PyTorch dummy loading: NOT_RUN; importing torch does not count as a loading test.
18. Peak memory: NOT_MEASURED.
19. Unresolved: mandatory dependencies; unimplemented downstream stages; scientific QC unverified.
20. Engineering readiness: DRY_RUN_FAILED. No full processing recommendation.

## Scientific constraints retained
covers_yunnan_context = PENDING_RESEARCHER_CONFIRMATION.
No historical bbox adopted. Final administrative mask/context extent is a researcher decision.
No channel reorder, latitude flip, temporal interpolation, future frame, or source repair performed.
Missing values are not valid zero; packed decoding and masks require the later tested reader.
No training, train mean/std, data splits, other datasets, or later stages executed.

## Stop and resume
Environment gate is incomplete. Steps 2–3 were read-only/small-cache diagnostics.
Stopped before Step 4 and monthly processing. Full src/tests pipeline is NOT claimed complete.
See output_status_202407.csv for all blocked required artifacts. Blocked is not NOT_APPLICABLE.
See RUN_COMMANDS_202407.md for repeatable executed commands and unexecuted dependency proposal.
No dependency installation or environment upgrade performed.
"""
    write_text(output / "reports/README_HIMAWARI_PREPROCESS_202407.md", readme)
    end = datetime.now(timezone.utc)
    log.info("End=%s overall=DRY_RUN_FAILED blockers=%s integrity=%s", end.isoformat(), blocks, integrity)
    log.info("Month reads/QC/sequences/benchmark/dummy=NOT_RUN; config=%s", output / "reports/config.json")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print("OUTPUT_DIR=" + str(output))
    return 2

if __name__ == "__main__":
    raise SystemExit(main())
