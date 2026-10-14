<#
  Start-Training-Monitored.ps1 — 启动训练并进入可视化监控循环
  用法（在仓库根目录的 PowerShell 中）:
    .\scripts\phase_b_v2_operator\Start-Training-Monitored.ps1
    .\scripts\phase_b_v2_operator\Start-Training-Monitored.ps1 -IntervalSeconds 30
  说明: 先调用 Start-Training.ps1 启动训练，成功后进入 Monitor-Training.ps1 循环；
        Ctrl+C 只停止监控，训练进程在后台继续。
#>
[CmdletBinding()]
param([int]$IntervalSeconds = 60)
$ErrorActionPreference = 'Stop'
& (Join-Path $PSScriptRoot 'Start-Training.ps1')
if ($LASTEXITCODE -ne 0) { throw "Start-Training.ps1 失败 (exit $LASTEXITCODE)；按协议不要重置账本或重试失败的训练会话。" }
& (Join-Path $PSScriptRoot 'Monitor-Training.ps1') -IntervalSeconds $IntervalSeconds
