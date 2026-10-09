$ErrorActionPreference='Stop'
$env:PYTHONUTF8='1'
$env:PYTHONDONTWRITEBYTECODE='1'
$analysisPackageRoot=$PSScriptRoot
$analysisRepositoryRoot=Split-Path (Split-Path (Split-Path $analysisPackageRoot -Parent) -Parent) -Parent
$analysisRunRoot=(Get-Content -LiteralPath (Join-Path $analysisPackageRoot 'current_run.json') -Raw | ConvertFrom-Json).run
$observedMonitor=Get-CimInstance Win32_Process -Filter 'ProcessId = 31460'
if ($observedMonitor -and $observedMonitor.ParentProcessId -eq 34644 -and $observedMonitor.CommandLine -like '*v2_scientific_acceptance*monitor.py*--port 8772*') {
    Stop-Process -Id 31460 -Force
} else {
    throw 'Monitor identity mismatch; no process stopped'
}
$analysisCloseoutScript=Join-Path $analysisPackageRoot 'closeout_worker.py'
$analysisMonitorScript=Join-Path $analysisPackageRoot 'monitor.py'
$closeoutProcess=Start-Process -FilePath 'F:\pytorch\Research\.venv-cuda\Scripts\python.exe' -ArgumentList @('"'+$analysisCloseoutScript+'"') -WorkingDirectory $analysisRepositoryRoot -WindowStyle Hidden -RedirectStandardOutput (Join-Path $analysisPackageRoot 'closeout_stdout.log') -RedirectStandardError (Join-Path $analysisPackageRoot 'closeout_stderr.log') -PassThru
$monitorProcess=Start-Process -FilePath 'F:\pytorch\Research\.venv-cuda\Scripts\python.exe' -ArgumentList @('"'+$analysisMonitorScript+'"','--run','"'+$analysisRunRoot+'"','--port','8772') -WorkingDirectory $analysisRepositoryRoot -WindowStyle Hidden -RedirectStandardOutput (Join-Path $analysisPackageRoot 'monitor_v2_stdout.log') -RedirectStandardError (Join-Path $analysisPackageRoot 'monitor_v2_stderr.log') -PassThru
@{closeout_pid=$closeoutProcess.Id;monitor_pid=$monitorProcess.Id;run=$analysisRunRoot;training_or_resume_launch=$false} | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $analysisPackageRoot 'closeout_dispatch.json') -Encoding utf8
