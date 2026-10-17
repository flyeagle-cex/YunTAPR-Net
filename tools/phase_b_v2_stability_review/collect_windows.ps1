$ErrorActionPreference='Stop'
$taskRepo=[IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..\..'))
$taskOut=Join-Path $taskRepo 'docs\phase_b_v2_stability_review\v1\.local\windows_diagnostics.json'
if ([IO.File]::Exists($taskOut)) { throw 'Existing diagnostic receipt must not be overwritten.' }
$taskOS=Get-CimInstance Win32_OperatingSystem
$taskComputer=Get-CimInstance Win32_ComputerSystem
$taskDriver=@(Get-CimInstance Win32_PnPSignedDriver | Where-Object { $_.DeviceName -match 'NVIDIA.*5060' } | Select-Object DeviceName,DriverVersion,DriverDate,Manufacturer)
$taskPage=@(Get-CimInstance Win32_PageFileUsage | Select-Object AllocatedBaseSize,CurrentUsage,PeakUsage)
$taskGPU=& nvidia-smi --query-gpu=name,temperature.gpu,utilization.gpu,memory.total,memory.free,power.draw,power.limit --format=csv,noheader,nounits
if ($LASTEXITCODE -ne 0) { throw 'Read-only nvidia-smi query failed.' }
$taskGPUEvents=@(Get-WinEvent -FilterHashtable @{LogName='System';ProviderName='nvlddmkm';Id=153;StartTime=[datetime]'2026-10-14T00:00:00'} -MaxEvents 12 -ErrorAction SilentlyContinue | ForEach-Object {
    [pscustomobject]@{UTC=$_.TimeCreated.ToUniversalTime().ToString('o');Provider=$_.ProviderName;Id=$_.Id}
})
$taskPower=@(Get-WinEvent -FilterHashtable @{LogName='System';StartTime=[datetime]'2026-10-17T20:45:00';Id=41,6008,1074,12,13} -ErrorAction SilentlyContinue | Where-Object {$_.ProviderName -match 'Kernel-Power|EventLog|USER32|Kernel-General'} | Select-Object -First 20 @{N='UTC';E={$_.TimeCreated.ToUniversalTime().ToString('o')}},ProviderName,Id)
$taskWER=@(Get-WinEvent -FilterHashtable @{LogName='Application';Id=1001;StartTime=[datetime]'2026-10-17T20:45:00'} -MaxEvents 150 -ErrorAction SilentlyContinue | Where-Object {$_.Message -match 'LiveKernelEvent'} | Select-Object -First 8 | ForEach-Object {
    $taskCode=[regex]::Match($_.Message,'P1:\s*([^\r\n]+)').Groups[1].Value
    $taskDump=[regex]::Match($_.Message,'LiveKernelReports\\([^\\]+)\\[^\r\n]*?([0-9]{8})').Groups
    [pscustomobject]@{UTC=$_.TimeCreated.ToUniversalTime().ToString('o');Event='LiveKernelEvent';Code=$taskCode;DumpFamily=$taskDump[1].Value;EmbeddedDumpDate=$taskDump[2].Value;DumpOpened=$false}
})
$taskResult=[ordered]@{ObservedUTC=[datetime]::UtcNow.ToString('o');OS=[ordered]@{Version=$taskOS.Version;Build=$taskOS.BuildNumber;LastBootUTC=$taskOS.LastBootUpTime.ToUniversalTime().ToString('o')};AutomaticManagedPagefile=$taskComputer.AutomaticManagedPagefile;PagefileMiB=$taskPage;Drivers=$taskDriver;GPUQuery=$taskGPU;NVidia153=$taskGPUEvents;ShutdownBootEvents=$taskPower;WERMetadata=$taskWER;SystemSettingsChanged=$false;DriverChanged=$false;MemoryDumpsOpened=0;ModelsInstantiated=0;OptimizerUpdates=0}
$taskJSON=$taskResult | ConvertTo-Json -Depth 6
$taskBytes=[Text.Encoding]::UTF8.GetBytes($taskJSON)
$taskStream=[IO.File]::Open($taskOut,[IO.FileMode]::CreateNew,[IO.FileAccess]::Write,[IO.FileShare]::Read)
try { $taskStream.Write($taskBytes,0,$taskBytes.Length);$taskStream.Flush($true) } finally { $taskStream.Dispose() }
Write-Output 'READ_ONLY_WINDOWS_DIAGNOSTICS_RECORDED; no dump files opened or settings modified.'
