param([Parameter(Mandatory=$true)][ValidateRange(1,999)][int]$Session,
      [Parameter(Mandatory=$true)][ValidatePattern('^[a-f0-9]{32}$')][string]$Nonce)
$ErrorActionPreference='Stop'
$taskRepo=[IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..\..'))
$taskPython=(Get-Content -LiteralPath (Join-Path $taskRepo 'docs\phase_b_v2_formal_execution\seed2027_b1_epoch7_recovery_v4\.local\runtime.json') -Raw | ConvertFrom-Json).python
# Must precede interpreter creation, not merely set os.environ after import.
$env:PYTHONHASHSEED='2026';$env:PYTHONUTF8='1'
$env:PYTHONPATH=Join-Path $taskRepo 'src'
$env:CUBLAS_WORKSPACE_CONFIG=':4096:8';$env:YUNTAPR_REPLICATION_SEED='2027'
$taskEntry=Join-Path $taskRepo 'src\yuntapr\training\phase_b_v2_seed2027_b1_epoch7_recovery_v4\task_entry.py'
Set-Location -LiteralPath $taskRepo
& $taskPython $taskEntry $Session $Nonce
exit $LASTEXITCODE
