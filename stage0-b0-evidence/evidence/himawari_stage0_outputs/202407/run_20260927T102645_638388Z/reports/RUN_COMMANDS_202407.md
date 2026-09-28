# Commands — 2024-07 preflight only
Run from PowerShell. Each run creates a new timestamped output and cache directory.
No existing output or cache is overwritten or deleted.

## Activation (optional)
& 'F:\pytorch\Research\.venv\Scripts\Activate.ps1'

## Actual environment / scan / compatibility / cache diagnostic
& 'F:\pytorch\Research\.venv\Scripts\python.exe' -B 'F:\pytorch\Research\stage0_himawari\src\preflight.py' --year 2024 --month 7

## Preflight guard tests (not the requested scientific test suite)
& 'F:\pytorch\Research\.venv\Scripts\python.exe' -B 'F:\pytorch\Research\stage0_himawari\tests\test_preflight.py'

## Dependency proposal — NOT executed; researcher approval required by no-environment-change instruction
First inspect resolver plan:
& 'F:\pytorch\Research\.venv\Scripts\python.exe' -m pip install h5py pyarrow zarr numcodecs psutil pytest --dry-run
Then review every planned change. Do not upgrade/downgrade Python, PyTorch, CUDA, or existing packages.
Only after approval, install a compatible pinned set in this exact environment.
h5py enables h5netcdf/HDF5; pyarrow enables Parquet; zarr/numcodecs enable Zarr.
psutil and pytest are optional engineering conveniences, not scientific requirements.
The preliminary command above is unpinned and is NOT a validated installation prescription.

## QC / index / benchmark / dummy / full dry-run
BLOCKED_NOT_IMPLEMENTED. No executable commands claimed for unfinished pipeline stages.
Resume from dependency verification, rerun backend compatibility, then implement and test Step 4.
