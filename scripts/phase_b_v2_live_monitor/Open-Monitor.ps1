param([switch]$NoBrowser)
$ErrorActionPreference='Stop'
$taskRepo=[IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..\..'))
$taskUrl='http://127.0.0.1:53078'
$taskExpected='YUNTAPR_READONLY_LIVE_SEED2027_EPOCH1_V1'
$taskHealth=$null
try { $taskHealth=Invoke-RestMethod "$taskUrl/api/health" -TimeoutSec 2 } catch { }
if ($taskHealth -and $taskHealth.app_id -ne $taskExpected) { throw 'Port occupied by another service; no process was stopped.' }
if (-not $taskHealth) {
    $taskPython=(Get-Content -LiteralPath (Join-Path $taskRepo 'docs\phase_b_v2_formal_execution\seed2027_epoch1_recovery_v1\.local\runtime.json') -Raw | ConvertFrom-Json).python
    $taskLog=Join-Path $PSScriptRoot '.local'
    New-Item -ItemType Directory -Force -Path $taskLog | Out-Null
    $taskStamp=Get-Date -Format 'yyyyMMddTHHmmssfff'
    $taskArgs=@('-u',('"'+(Join-Path $PSScriptRoot 'server.py')+'"'),'--port','53078')
    Start-Process -FilePath $taskPython -ArgumentList $taskArgs -WorkingDirectory $taskRepo -WindowStyle Hidden -RedirectStandardOutput (Join-Path $taskLog "$taskStamp.stdout.txt") -RedirectStandardError (Join-Path $taskLog "$taskStamp.stderr.txt") | Out-Null
    for ($taskN=0;$taskN -lt 30;$taskN++) {
        Start-Sleep -Milliseconds 200
        try { $taskHealth=Invoke-RestMethod "$taskUrl/api/health" -TimeoutSec 1; break } catch { }
    }
    if (-not $taskHealth -or $taskHealth.app_id -ne $taskExpected) { throw 'Monitor did not start; inspect .local logs. Training was not touched.' }
}
if (-not $NoBrowser) { Start-Process $taskUrl }
Write-Output "$taskUrl/"
