param([switch]$NoBrowser)
$ErrorActionPreference='Stop'
$taskRepo=[IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..\..'))
$taskUrl='http://127.0.0.1:53087'
$taskExpected='YUNTAPR_READONLY_LIVE_SEED2027_B1_EPOCH7_V6'
$taskHealth=$null
try { $taskHealth=Invoke-RestMethod "$taskUrl/api/health" -TimeoutSec 2 } catch { }
if ($taskHealth -and $taskHealth.app_id -ne $taskExpected) { throw 'Port occupied by another service; no process was stopped.' }
if (-not $taskHealth) {
    # A separate read-only OS task survives closing Codex as well.
    $taskName='YunTAPR_Readonly_Seed2027_B1E7V6'
    $taskRuntime=Join-Path $taskRepo 'docs\phase_b_v2_formal_execution\seed2027_b1_epoch7_recovery_v4\.local\gui_runtime.json'
    $taskExe=(Get-Content -LiteralPath $taskRuntime -Raw | ConvertFrom-Json).wrapper_path
    $taskArguments='"'+(Join-Path $PSScriptRoot 'Task-View.py')+'"'
    $task=Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue
    if(-not $task){
        $taskAction=New-ScheduledTaskAction -Execute $taskExe -Argument $taskArguments -WorkingDirectory $taskRepo
        $taskPrincipal=New-ScheduledTaskPrincipal -UserId ([Security.Principal.WindowsIdentity]::GetCurrent().Name) -LogonType Interactive -RunLevel Limited
        $taskSettings=New-ScheduledTaskSettingsSet -ExecutionTimeLimit (New-TimeSpan -Days 7) -MultipleInstances IgnoreNew -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries
        Register-ScheduledTask -TaskName $taskName -InputObject (New-ScheduledTask -Action $taskAction -Principal $taskPrincipal -Settings $taskSettings) | Out-Null
        $task=Get-ScheduledTask -TaskName $taskName
    }
    if($task.Actions.Count -ne 1 -or $task.Actions[0].Execute -ne $taskExe -or $task.Actions[0].Arguments -ne $taskArguments -or $task.Triggers.Count -ne 0 -or $task.Settings.RestartCount -ne 0 -or $task.Principal.RunLevel -ne 'Limited'){
        throw 'Read-only monitor task source/policy mismatch; no process stopped.'
    }
    if($task.State -ne 'Running'){Start-ScheduledTask -TaskName $taskName}
    for ($taskN=0;$taskN -lt 30;$taskN++) {
        Start-Sleep -Milliseconds 200
        try { $taskHealth=Invoke-RestMethod "$taskUrl/api/health" -TimeoutSec 1; break } catch { }
    }
    if (-not $taskHealth -or $taskHealth.app_id -ne $taskExpected) { throw 'Monitor did not start; inspect .local logs. Training was not touched.' }
}
if (-not $NoBrowser) { Start-Process $taskUrl }
Write-Output "$taskUrl/"
