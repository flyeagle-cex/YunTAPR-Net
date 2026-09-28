# Final reproducibility commands — revision 2
Use this supplement together with RUN_COMMANDS_202407.md. No packages are installed by these commands.
The original benchmark traverses the randomly sampled targets chronologically. The finalizer below is REQUIRED for the final shuffled random-access measurements and version-2 report.

## This run: successful stage commands (PowerShell)
& 'F:\pytorch\Research\.venv\Scripts\python.exe' -B 'F:\pytorch\Research\stage0_himawari\tests\test_stage0.py'
& 'F:\pytorch\Research\.venv\Scripts\python.exe' -B 'F:\pytorch\Research\stage0_himawari\src\run_monthly.py' --run-dir 'F:\pytorch\Research\stage0_himawari\outputs\202407\resume_20260927T104625_772423Z' --year 2024 --month 7
& 'F:\pytorch\Research\.venv\Scripts\python.exe' -B 'F:\pytorch\Research\stage0_himawari\src\run_stage0_dryrun.py' --run-dir 'F:\pytorch\Research\stage0_himawari\outputs\202407\resume_20260927T104625_772423Z' --phase remaining
& 'F:\pytorch\Research\.venv\Scripts\python.exe' -B 'F:\pytorch\Research\stage0_himawari\src\finalize_validation.py' 'F:\pytorch\Research\stage0_himawari\outputs\202407\resume_20260927T104625_772423Z'

Do not rerun completed stages into this same directory: outputs use exclusive creation.
The flags-column failure and original benchmark measurements remain in the historical records.

## Independent reproduction with new output directory
& 'F:\pytorch\Research\.venv\Scripts\python.exe' -B 'F:\pytorch\Research\stage0_himawari\src\run_stage0_dryrun.py' --year 2024 --month 7 --phase all
Then use the NEW generated output directory as the single argument to finalize_validation.py.
The finalizer writes *_v2 files without replacing original reports.

## Canonical result files
reports/final_dry_run_status_202407_v2.json
reports/README_HIMAWARI_PREPROCESS_202407_v2.md
benchmark/storage_benchmark_202407_v2.csv
benchmark/STORAGE_BENCHMARK_202407_v2.md
reports/code_sha256_v2.csv

No full-year processing is authorized. All source data remain read-only.
