param(
    [Parameter(Mandatory=$true)][string]$Repository,
    [Parameter(Mandatory=$true)][string]$TestRun,
    [Parameter(Mandatory=$true)][string]$PreflightRun
)
$ErrorActionPreference = 'Stop'
$repoPath = (Resolve-Path -LiteralPath $Repository).Path
Set-Location -LiteralPath $repoPath
$testPath = Join-Path $repoPath $TestRun
$preflightPath = Join-Path $repoPath $PreflightRun
if (-not $testPath.StartsWith($repoPath + '\') -or -not $preflightPath.StartsWith($repoPath + '\')) {
    throw 'Engineering evidence must remain inside the repository'
}
$pythonPath = 'F:\pytorch\Research\.venv-cuda\Scripts\python.exe'
$env:PYTHONUTF8 = '1'
$env:PYTHONHASHSEED = '2026'
$env:CUBLAS_WORKSPACE_CONFIG = ':4096:8'
$env:TEMP = 'C:\Users\chenerxiao\.codex\visualizations\2026\09\27\01a0e260-daf4-7292-a541-ec5e83b0661d\v2_fixture_tmp'
$env:TMP = $env:TEMP

# This continuation can only launch the ENGINEERING_ONLY preflight subcommand.
# It contains no train/resume command and never writes formal authorization.
while (-not (Test-Path -LiteralPath (Join-Path $testPath 'test_summary.json'))) {
    if (Test-Path -LiteralPath (Join-Path $testPath 'failure.json')) {
        throw 'Regression gate failed; no source/GPU preflight will be launched'
    }
    Start-Sleep -Seconds 5
}
$summary = Get-Content -LiteralPath (Join-Path $testPath 'test_summary.json') -Raw -Encoding UTF8 | ConvertFrom-Json
if ($summary.status -ne 'PASS' -or $summary.FORMAL_OPTIMIZER_STEPS -ne 0) {
    throw 'Invalid engineering test gate'
}

# Only our exact read-only viewer on port 8769 is replaced. Test/training
# processes are never selected by this command line filter.
$viewers = @(Get-CimInstance Win32_Process | Where-Object {
    $_.Name -like '*python*' -and
    $_.CommandLine -like '*scripts/run_paired_phase_a_v2.py monitor --run docs/v2_phase_a_execution/test_runs/* --port 8769*'
})
foreach ($viewer in ($viewers | Sort-Object ParentProcessId -Descending)) {
    Stop-Process -Id $viewer.ProcessId -ErrorAction SilentlyContinue
}
$monitor = Start-Process -FilePath $pythonPath -ArgumentList @('-B','scripts/run_paired_phase_a_v2.py','monitor','--run',$PreflightRun,'--port','8769') -WorkingDirectory $repoPath -WindowStyle Hidden -RedirectStandardOutput 'docs/v2_phase_a_execution/preflight_monitor_stdout.log' -RedirectStandardError 'docs/v2_phase_a_execution/preflight_monitor_stderr.log' -PassThru
$manifest = [ordered]@{
    status='ENGINEERING_PREFLIGHT_LAUNCHING'
    test_run=$TestRun
    preflight_run=$PreflightRun
    monitor_pid=$monitor.Id
    FORMAL_TRAINING_AUTHORIZED=$false
    V2_PHASE_A_AUTHORIZED=$false
    V2_PHASE_A_STARTED=$false
    V2_PHASE_B_AUTHORIZED=$false
    FORMAL_OPTIMIZER_STEPS=0
}
$manifest | ConvertTo-Json | Set-Content -LiteralPath 'docs/v2_phase_a_execution/engineering_continuation_status.json' -Encoding UTF8
& $pythonPath -B scripts/run_paired_phase_a_v2.py preflight --run $PreflightRun --tests-summary (Join-Path $TestRun 'test_summary.json') *> 'docs/v2_phase_a_execution/preflight_console.log'
$exitCode = $LASTEXITCODE
$manifest.status = if ($exitCode -eq 0) { 'ENGINEERING_PREFLIGHT_COMPLETE_WAITING_RESEARCHER' } else { 'ENGINEERING_PREFLIGHT_FAILED_STOP' }
$manifest.exit_code = $exitCode
$manifest | ConvertTo-Json | Set-Content -LiteralPath 'docs/v2_phase_a_execution/engineering_continuation_status.json' -Encoding UTF8
exit $exitCode
