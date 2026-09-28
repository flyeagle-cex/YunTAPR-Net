# Reproducible commands (PowerShell)
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
