param([Parameter(Mandatory=$true)][ValidateSet('start','pause','status','emergency-stop')][string]$Action)
$ErrorActionPreference = 'Stop'
$taskRepo = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..\..'))
$taskRuntime = Join-Path $taskRepo 'docs\phase_b_v2_formal_execution\seed2026_operator_v2\.local\runtime.json'
$taskPython = (Get-Content -LiteralPath $taskRuntime -Raw | ConvertFrom-Json).python
$env:PYTHONPATH = Join-Path $taskRepo 'src'
$env:PYTHONUTF8 = '1'
Push-Location -LiteralPath $taskRepo
try {
    & $taskPython -m yuntapr.training.phase_b_v2_seed2026_operator_v2.control $Action
    if ($LASTEXITCODE -ne 0) { throw "Operator command failed (exit $LASTEXITCODE); do not reset ledger or retry a failed training session." }
} finally { Pop-Location }
