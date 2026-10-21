param()
$ErrorActionPreference='Stop'
$taskRepo=[IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..\..'))
$taskPython=(Get-Content -LiteralPath (Join-Path $taskRepo 'docs\phase_b_v2_formal_execution\seed2027_b1_epoch7_recovery_v1\.local\runtime.json') -Raw | ConvertFrom-Json).python
$taskPreviousPath=$env:PYTHONPATH
$taskPreviousUtf8=$env:PYTHONUTF8
$env:PYTHONPATH=Join-Path $taskRepo 'src';$env:PYTHONUTF8='1'
Push-Location -LiteralPath $taskRepo
try {
    $taskLogs=Join-Path $taskRepo 'docs\phase_b_v2_owner_lifetime_repair\v1\.local'
    $taskStamp=Get-Date -Format 'yyyyMMddTHHmmssfff'
    # Three separate interpreters preserve each suite's final cleanup checks.
    # Four read-only audit cases + one inheritance case + three OS-task cases.
    foreach ($taskSuite in @('test_audit','test_inheritance','test_task_owner')) {
        $taskArgument='"tools\phase_b_v2_owner_lifetime_candidate\'+$taskSuite+'.py"'
        $taskPrefix="$taskStamp.$taskSuite"
        $taskProcess=Start-Process -FilePath $taskPython -ArgumentList @($taskArgument) -WorkingDirectory $taskRepo -WindowStyle Hidden -Wait -PassThru -RedirectStandardOutput (Join-Path $taskLogs "$taskPrefix.stdout.log") -RedirectStandardError (Join-Path $taskLogs "$taskPrefix.stderr.log")
        Get-Content -LiteralPath (Join-Path $taskLogs "$taskPrefix.stderr.log")
        Get-Content -LiteralPath (Join-Path $taskLogs "$taskPrefix.stdout.log")
        if ($taskProcess.ExitCode -ne 0) { throw 'Artificial owner lifetime suite failed; inspect receipts. No training or automatic retry occurred.' }
    }
} finally {
    Pop-Location
    $env:PYTHONPATH=$taskPreviousPath;$env:PYTHONUTF8=$taskPreviousUtf8
}
