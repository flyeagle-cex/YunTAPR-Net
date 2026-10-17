param([switch]$Record)
$ErrorActionPreference='Stop'
$taskRepo=[IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..\..'))
$taskRuntime=Join-Path $taskRepo 'docs\phase_b_v2_formal_execution\seed2027_restart_v1\.local\runtime.json'
$taskPython=(Get-Content -LiteralPath $taskRuntime -Raw | ConvertFrom-Json).python
$taskOldPath=$env:PYTHONPATH; $taskOldUtf8=$env:PYTHONUTF8
$env:PYTHONPATH=Join-Path $taskRepo 'src';$env:PYTHONUTF8='1'
Push-Location -LiteralPath $taskRepo
try {
    if ($Record) { & $taskPython -m yuntapr.experimental.phase_b_v2_stability_review --record }
    else { & $taskPython -m yuntapr.experimental.phase_b_v2_stability_review }
    if ($LASTEXITCODE -ne 0) { throw 'Review NOT_VERIFIED. No training or ledger changes performed.' }
} finally {
    Pop-Location; $env:PYTHONPATH=$taskOldPath; $env:PYTHONUTF8=$taskOldUtf8
}
