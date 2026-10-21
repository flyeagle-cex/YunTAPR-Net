param()
$ErrorActionPreference='Stop'
$taskRepo=[IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..\..'))
$taskPython=(Get-Content -LiteralPath (Join-Path $taskRepo 'docs\phase_b_v2_formal_execution\seed2027_b1_epoch7_recovery_v1\.local\runtime.json') -Raw | ConvertFrom-Json).python
$taskPreviousPath=$env:PYTHONPATH;$taskPreviousUtf8=$env:PYTHONUTF8
$env:PYTHONPATH=Join-Path $taskRepo 'src';$env:PYTHONUTF8='1'
Push-Location -LiteralPath $taskRepo
try { & $taskPython -m yuntapr.experimental.phase_b_v2_owner_lifetime_candidate.audit; if ($LASTEXITCODE -ne 0) { throw 'Read-only native status could not be verified.' } }
finally { Pop-Location; $env:PYTHONPATH=$taskPreviousPath;$env:PYTHONUTF8=$taskPreviousUtf8 }
