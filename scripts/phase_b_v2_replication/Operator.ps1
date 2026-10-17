param(
    [Parameter(Mandatory=$true)][ValidateSet(2027,2028)][int]$Seed,
    [Parameter(Mandatory=$true)][ValidateSet('start','pause','status','emergency-stop','check')][string]$Action
)
$ErrorActionPreference='Stop'
$taskRepo=[IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..\..'))
$taskRuntime=Join-Path $taskRepo "docs\phase_b_v2_formal_execution\seed${Seed}_v1\.local\runtime.json"
$taskPython=(Get-Content -LiteralPath $taskRuntime -Raw | ConvertFrom-Json).python
$taskOldSeed=$env:YUNTAPR_REPLICATION_SEED
$taskOldPath=$env:PYTHONPATH
$env:YUNTAPR_REPLICATION_SEED=[string]$Seed
$env:PYTHONPATH=Join-Path $taskRepo 'src'
$env:PYTHONUTF8='1'
Push-Location -LiteralPath $taskRepo
try {
    if ($Action -eq 'check') {
        & $taskPython tools/phase_b_v2_replication/check.py --seed $Seed
    } else {
        # The underlying start command denies before host, ledger, Job or data
        # work until a separately reviewed human-authorized release exists.
        & $taskPython -m yuntapr.experimental.phase_b_v2_multiseed_candidate.control $Action
    }
    if ($LASTEXITCODE -ne 0) { throw "Command refused/failed (exit $LASTEXITCODE). No automatic retry or quota reset." }
} finally {
    Pop-Location
    $env:YUNTAPR_REPLICATION_SEED=$taskOldSeed
    $env:PYTHONPATH=$taskOldPath
}
