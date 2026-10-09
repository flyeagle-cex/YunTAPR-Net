$ErrorActionPreference='Stop'
$repoRoot=Split-Path (Split-Path (Split-Path $PSScriptRoot -Parent) -Parent) -Parent
$deliveryRoot=Join-Path $repoRoot 'docs\v2_scientific_acceptance\runs\run_20261009T112710_013267Z\delivery_v2'
$oldMonitor=Get-CimInstance Win32_Process -Filter 'ProcessId=45420'
if ($oldMonitor) {
  if ($oldMonitor.ParentProcessId -ne 43060 -or $oldMonitor.CommandLine -notmatch 'v2_scientific_acceptance\\analysis_v1\\monitor.py' -or $oldMonitor.CommandLine -notmatch '--port 8772') { throw 'Monitor identity mismatch; no process stopped' }
  Stop-Process -Id 45420
}
$shim=Get-Process -Id 43060 -ErrorAction SilentlyContinue
if ($shim) { Stop-Process -Id 43060 }
$env:PYTHONUTF8='1'
$env:PYTHONDONTWRITEBYTECODE='1'
$monitorCode=Join-Path $PSScriptRoot 'monitor.py'
$pythonPath='F:\pytorch\Research\.venv\Scripts\python.exe'
$monitorProcess=Start-Process -FilePath $pythonPath -ArgumentList @('-B', ('"'+$monitorCode+'"'), '--delivery', ('"'+$deliveryRoot+'"'), '--port', '8772') -WindowStyle Hidden -WorkingDirectory $repoRoot -RedirectStandardOutput (Join-Path $deliveryRoot 'final_monitor.stdout.log') -RedirectStandardError (Join-Path $deliveryRoot 'final_monitor.stderr.log') -PassThru
@{recorded_utc=[DateTime]::UtcNow.ToString('o');PID=$monitorProcess.Id;purpose='Read-only final scientific evidence metadata page only';port=8772;old_process_identity_verified=$true;automatic_work=$false} | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $deliveryRoot 'final_monitor_dispatch.json') -Encoding UTF8
Write-Output ('Final monitor PID: '+$monitorProcess.Id)
