param([Parameter(Mandatory=$true)][ValidateSet('check','start','pause','status','emergency-stop')][string]$Action)
$ErrorActionPreference='Stop'
$taskRepo=[IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..\..'))
$taskRuntime=Join-Path $taskRepo 'docs\phase_b_v2_formal_execution\seed2027_b1_epoch7_recovery_v5\.local\runtime.json'
$taskPython=(Get-Content -LiteralPath $taskRuntime -Raw | ConvertFrom-Json).python
$taskOldSeed=$env:YUNTAPR_REPLICATION_SEED
$taskOldPath=$env:PYTHONPATH
$taskOldUtf8=$env:PYTHONUTF8
$env:YUNTAPR_REPLICATION_SEED='2027'
$env:PYTHONPATH=Join-Path $taskRepo 'src'
$env:PYTHONUTF8='1'
Push-Location -LiteralPath $taskRepo
try {
    if ($Action -eq 'check') { & $taskPython -m yuntapr.training.phase_b_v2_seed2027_b1_epoch7_recovery_v5.release_check }
    else { & $taskPython -m yuntapr.training.phase_b_v2_seed2027_b1_epoch7_recovery_v5.control $Action }
    if ($LASTEXITCODE -ne 0) { throw "Command refused/failed (exit $LASTEXITCODE). No automatic retry or recovery." }
} finally {
    Pop-Location
    $env:YUNTAPR_REPLICATION_SEED=$taskOldSeed
    $env:PYTHONPATH=$taskOldPath
    $env:PYTHONUTF8=$taskOldUtf8
}
