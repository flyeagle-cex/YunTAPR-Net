<#
  Monitor-Training.ps1 — YunTAPR-Net Phase-B v2 operator 可视化监控模板

  用法（在仓库根目录的 PowerShell 中）：
    .\scripts\phase_b_v2_operator\Monitor-Training.ps1                  # 每 60 秒刷新
    .\scripts\phase_b_v2_operator\Monitor-Training.ps1 -IntervalSeconds 30
    .\scripts\phase_b_v2_operator\Monitor-Training.ps1 -Once            # 只生成一次 HTML 快照
    .\scripts\phase_b_v2_operator\Monitor-Training.ps1 -SecondsPerUpdate 0.764   # 手动指定速率估算 ETA

  输出：
    1) 控制台摘要（每次刷新一行）
    2) scripts\phase_b_v2_operator\monitor.html —— 用浏览器打开，自动刷新
       包含：总进度、每个 run 的进度条、配额、心跳新鲜度（进程死亡告警）、GPU 状态、ETA

  说明：本脚本只读状态（Status-Training.ps1 / Operator.ps1 status）与 nvidia-smi，
        不写账本、不动任何训练文件。Ctrl+C 停止监控不影响后台训练进程。
#>
[CmdletBinding()]
param(
    [int]$IntervalSeconds = 60,
    [switch]$Once,
    [double]$SecondsPerUpdate = 0,
    [switch]$Open
)

$ErrorActionPreference = 'Continue'
$repo     = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..\..'))
$operator = Join-Path $PSScriptRoot 'Operator.ps1'
$htmlPath = Join-Path $PSScriptRoot 'monitor.html'
$TARGET   = 6 * 47052   # 282312：6 个 run × 每 run 47052 次更新的科学计划

function To-Int($v) { $r = 0; if ([int]::TryParse("$v", [ref]$r)) { return $r }; return 0 }

function Get-Status {
    $raw = $null
    try { $raw = & $operator -Action status 2>$null | Out-String } catch { return $null }
    if ($LASTEXITCODE -ne 0 -or -not $raw) { return $null }
    try { return ($raw | ConvertFrom-Json) } catch { return $null }
}

function Get-Gpu {
    if (-not (Get-Command nvidia-smi -ErrorAction SilentlyContinue)) { return $null }
    $line = (& nvidia-smi --query-gpu=utilization.gpu,memory.used,memory.total,temperature.gpu,power.draw --format=csv,noheader,nounits 2>$null | Select-Object -First 1)
    if (-not $line) { return $null }
    $p = @($line -split '\s*,\s*')
    if ($p.Count -lt 5) { return $null }
    return @{ util = (To-Int $p[0]); usedMB = (To-Int $p[1]); totalMB = (To-Int $p[2]); temp = (To-Int $p[3]); watt = $p[4] }
}

function Get-PythonAlive { return (@(Get-Process -Name 'python*' -ErrorAction SilentlyContinue).Count -gt 0) }

function Html-Escape([string]$s) {
    if (-not $s) { return '' }
    return $s.Replace('&', '&amp;').Replace('<', '&lt;').Replace('>', '&gt;')
}

function Format-Duration([double]$sec) {
    if ($sec -lt 0) { return '-' }
    $h = [math]::Floor($sec / 3600); $m = [math]::Floor(($sec % 3600) / 60)
    if ($h -ge 24) { return ('{0} 天 {1} 小时' -f [math]::Floor($h / 24), ($h % 24)) }
    if ($h -gt 0)  { return ('{0} 小时 {1} 分' -f $h, $m) }
    return ('{0} 分' -f $m)
}

function Bar-Html([double]$pct, [string]$color) {
    $p = [math]::Max(0, [math]::Min(100, [math]::Round($pct, 1)))
    return ('<div class="bar"><div class="fill" style="width:{0}%;background:{1}"></div></div><span class="pct">{0}%</span>' -f $p, $color)
}

$CSS = @'
body{margin:0;background:#0d1117;color:#c9d1d9;font-family:"Segoe UI","Microsoft YaHei",sans-serif;font-size:14px}
.wrap{max-width:1080px;margin:0 auto;padding:16px}
h1{font-size:20px;margin:0 0 2px} .sub{color:#8b949e;font-size:12px;margin-bottom:12px}
.banner{padding:12px 14px;border-radius:8px;margin-bottom:14px;font-size:14px;font-weight:600;border:1px solid}
.banner.red{background:#3d1117;border-color:#f85149;color:#ff7b72}
.banner.yellow{background:#2b2a10;border-color:#d29922;color:#e3b341}
.banner.green{background:#0f2d1c;border-color:#2ea043;color:#56d364}
.banner.gray{background:#161b22;border-color:#30363d;color:#8b949e}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(230px,1fr));gap:12px;margin-bottom:14px}
.card{background:#161b22;border:1px solid #30363d;border-radius:8px;padding:12px}
.card h3{margin:0 0 8px;font-size:12px;color:#8b949e;text-transform:uppercase;letter-spacing:.5px}
.big{font-size:26px;font-weight:700} .dim{color:#8b949e;font-size:12px}
.bar{background:#21262d;border-radius:6px;height:12px;overflow:hidden;margin:6px 0 2px}
.fill{height:100%;border-radius:6px}
.pct{color:#8b949e;font-size:12px}
table{width:100%;border-collapse:collapse;background:#161b22;border:1px solid #30363d;border-radius:8px;overflow:hidden}
th,td{padding:8px 10px;text-align:left;border-bottom:1px solid #21262d;font-size:13px}
th{background:#1c2129;color:#8b949e;font-size:12px}
td.bar-td{min-width:200px}
.badge{display:inline-block;padding:2px 8px;border-radius:10px;font-size:11px;font-weight:700}
.footer{color:#6e7681;font-size:12px;margin-top:14px;line-height:1.7}
code{background:#161b22;border:1px solid #30363d;border-radius:4px;padding:1px 5px}
'@

function Build-Html($st, $gpu, $py, $hbAge, $hbLocal, $done, $remaining, $rate, $etaSec, $runsHtml, $alertClass, $alertText, $updatedLocal) {
    $totalPct = if ($TARGET -gt 0) { $done * 100 / $TARGET } else { 0 }
    $etaText = if ($alertClass -eq 'green') { ('约 ' + (Format-Duration $etaSec)) } else { '已停止（恢复后重新计时）' }
    $rateText = if ($rate -gt 0) { ('{0:N3} 秒/更新' -f $rate) } else { '-' }
    $hbText = if ($hbLocal) { $hbLocal } else { '-' }
    $hbAgeText = if ($null -ne $hbAge) { (Format-Duration $hbAge) } else { '-' }
    $gpuHtml = if ($gpu) {
        "<div class=`"big`">$($gpu.util)%</div><div class=`"dim`">利用率 · $($gpu.usedMB)/$($gpu.totalMB) MiB · $($gpu.temp)°C · $($gpu.watt)W</div>"
    } else { '<div class="big">-</div><div class="dim">nvidia-smi 不可用</div>' }
    $quotaHtml = ''
    if ($st) {
        $res = To-Int $st.reserved; $cap = To-Int $st.hard_cap
        $qp = if ($cap -gt 0) { $res * 100 / $cap } else { 0 }
        $pause = if ($st.pause_requested) { ' · 已请求暂停' } else { '' }
        $quotaHtml = "<div class=`"big`">$res<span class=`"dim`"> / $cap</span></div><div class=`"dim`">已记账配额$pause</div>" + (Bar-Html $qp '#a371f7')
    }
    $sessionHtml = '-'
    if ($st -and $st.session) { $sessionHtml = "session $($st.session.number) · $($st.session.status)" }
    $contentTb = '-'
    if ($st -and $st.heartbeat -and $st.heartbeat.content_bytes) {
        $contentTb = '{0:N2} TiB' -f ($st.heartbeat.content_bytes / 1TB)
    }
    $statusText = if ($st) { Html-Escape "$($st.status)" } else { '状态读取失败' }
    return @"
<!DOCTYPE html>
<html lang="zh"><head><meta charset="utf-8">
<meta http-equiv="refresh" content="60">
<title>YunTAPR-Net 训练监控</title>
<style>$CSS</style></head>
<body><div class="wrap">
<h1>YunTAPR-Net · Phase-B v2 训练监控</h1>
<div class="sub">campaign: %%CAMPAIGN%% · 快照生成于 %%GENERATED%% · 状态更新时间 %%UPDATED%%</div>
<div class="banner $alertClass">$alertText</div>
<div class="grid">
  <div class="card"><h3>总进度</h3><div class="big">%%TOTALPCT%%</div>%%TOTALBAR%%<div class="dim">已完成 %%DONE%% / %%TARGET%% · 剩余 %%REMAINING%% 次更新</div></div>
  <div class="card"><h3>预计完成</h3><div class="big">$etaText</div><div class="dim">按 $rateText 估算</div></div>
  <div class="card"><h3>配额</h3>$quotaHtml</div>
  <div class="card"><h3>心跳</h3><div class="big">$hbAgeText</div><div class="dim">最后心跳 $hbText</div></div>
  <div class="card"><h3>GPU</h3>$gpuHtml</div>
  <div class="card"><h3>会话 / 累计</h3><div class="big" style="font-size:16px">$sessionHtml</div><div class="dim">累计执行 %%ELAPSED%% · 读取 $contentTb</div></div>
</div>
<table><tr><th>Run</th><th>状态</th><th>Epoch</th><th>更新数</th><th>进度</th></tr>%%RUNS%%</table>
<div class="footer">
  页面每 60 秒自动刷新；也可手动 <code>Monitor-Training.ps1</code> 刷新。<br>
  红色横幅 = 心跳长时间未更新或 python 进程消失（训练已停/已死）；黄色 = 心跳滞后需留意；绿色 = 训练进行中。<br>
  启动并监控：<code>.\scripts\phase_b_v2_operator\Start-Training-Monitored.ps1</code> ·
  仅监控：<code>.\scripts\phase_b_v2_operator\Monitor-Training.ps1</code><br>
  Ctrl+C 只停止本监控，不影响后台训练进程。监控只读状态与 GPU，不写账本。
</div>
</div></body></html>
"@
}

function Update {
    $st = Get-Status
    $gpu = Get-Gpu
    $py = Get-PythonAlive
    $now = Get-Date

    $hbAge = $null; $hbLocal = $null
    if ($st -and $st.heartbeat -and $st.heartbeat.utc) {
        try {
            $hbUtc = ([datetimeoffset]::Parse($st.heartbeat.utc)).UtcDateTime.ToLocalTime()
            $hbLocal = $hbUtc.ToString('yyyy-MM-dd HH:mm:ss')
            $hbAge = ($now - $hbUtc).TotalSeconds
        } catch { }
    }
    $updatedLocal = '-'
    if ($st -and $st.updated_utc) {
        try { $updatedLocal = ([datetimeoffset]::Parse($st.updated_utc)).UtcDateTime.ToLocalTime().ToString('yyyy-MM-dd HH:mm:ss') } catch { }
    }

    $done = 0; $runsHtml = ''
    if ($st -and $st.runs) {
        foreach ($r in $st.runs) {
            $upd = To-Int $r.logical_updates
            $done += $upd
            $pct = if (47052 -gt 0) { $upd * 100 / 47052 } else { 0 }
            $color = switch ($r.status) { 'COMPLETE' { '#2ea043' } 'RUNNING' { '#388bfd' } 'PENDING' { '#6e7681' } default { '#f85149' } }
            $badge = switch ($r.status) { 'COMPLETE' { '#2ea043' } 'RUNNING' { '#388bfd' } 'PENDING' { '#6e7681' } default { '#f85149' } }
            $ep = if ($r.complete_epoch) { $r.complete_epoch } else { 0 }
            $runsHtml += "<tr><td>" + (Html-Escape $r.id) + "</td><td><span class=`"badge`" style=`"background:$badge;color:#fff`">$($r.status)</span></td><td>$ep / 9</td><td>$upd / 47052</td><td class=`"bar-td`">" + (Bar-Html $pct $color) + "</td></tr>"
        }
    }
    $remaining = $TARGET - $done

    $rate = 0.764
    if ($SecondsPerUpdate -gt 0) { $rate = $SecondsPerUpdate }
    elseif ($st -and $st.heartbeat -and $st.heartbeat.elapsed_seconds -and $done -gt 0) {
        $rate = [double]$st.heartbeat.elapsed_seconds / $done
    }
    $etaSec = $remaining * $rate

    $alertClass = 'gray'; $alertText = '状态未知'
    if (-not $st) {
        $alertClass = 'red'; $alertText = '无法读取训练状态（Operator.ps1 status 执行失败）。'
    } elseif ($st.status -eq 'ACTIVE') {
        if (($null -ne $hbAge -and $hbAge -ge 300) -or (-not $py)) {
            $alertClass = 'red'
            $ageTxt = if ($null -ne $hbAge) { (Format-Duration $hbAge) } else { '?' }
            $alertText = "⚠ 训练进程已停止或已死：心跳 $ageTxt 未更新" + $(if (-not $py) { '，且未发现 python 进程。' } else { '。' }) + " 账本仍显示 ACTIVE 是僵尸状态 —— 检查 GPU 驱动事件，按协议做恢复决定后再重启。"
        } elseif ($null -ne $hbAge -and $hbAge -ge 90) {
            $alertClass = 'yellow'
            $alertText = "心跳滞后 " + (Format-Duration $hbAge) + "，请留意进程是否卡住。"
        } else {
            $alertClass = 'green'; $alertText = '进程活跃，训练进行中。'
        }
    } else {
        $alertClass = 'gray'; $alertText = "campaign 状态：" + (Html-Escape "$($st.status)") + "（无训练在跑）。"
    }

    $elapsedTxt = if ($st -and $st.heartbeat -and $st.heartbeat.elapsed_seconds) { Format-Duration ([double]$st.heartbeat.elapsed_seconds) } else { '-' }
    $campaign = if ($st -and $st.campaign) { Html-Escape "$($st.campaign)" } else { '-' }
    $totalPct = if ($TARGET -gt 0) { [math]::Round($done * 100 / $TARGET, 1) } else { 0 }

    $html = (Build-Html $st $gpu $py $hbAge $hbLocal $done $remaining $rate $etaSec $runsHtml $alertClass $alertText $updatedLocal)
    $html = $html.Replace('%%CAMPAIGN%%', $campaign).Replace('%%GENERATED%%', $now.ToString('yyyy-MM-dd HH:mm:ss'))
    $html = $html.Replace('%%UPDATED%%', $updatedLocal).Replace('%%TOTALPCT%%', "$totalPct%")
    $html = $html.Replace('%%TOTALBAR%%', (Bar-Html $totalPct '#2ea043')).Replace('%%DONE%%', "$done").Replace('%%TARGET%%', "$TARGET")
    $html = $html.Replace('%%REMAINING%%', "$remaining").Replace('%%RUNS%%', $runsHtml).Replace('%%ELAPSED%%', $elapsedTxt)
    try { $html | Out-File -LiteralPath $htmlPath -Encoding utf8 } catch { Write-Host "HTML 写入失败: $($_.Exception.Message)" -ForegroundColor Yellow }

    $gpuTxt = if ($gpu) { "$($gpu.util)%/$($gpu.usedMB)MiB/$($gpu.temp)C" } else { 'n/a' }
    $hbTxt = if ($null -ne $hbAge) { (Format-Duration $hbAge) + ' 前' } else { '无心跳' }
    $etaText = if ($alertClass -eq 'green') { ('约 ' + (Format-Duration $etaSec)) } else { '已停止' }
    $stTxt = if ($st) { "$($st.status) $totalPct% 剩余 $remaining" } else { '读取失败' }
    Write-Host ("{0}  {1}  ETA {2}  GPU {3}  心跳 {4}" -f $now.ToString('HH:mm:ss'), $stTxt, $etaText, $gpuTxt, $hbTxt)
}

if ($Once) { Update; if ($Open) { Start-Process $htmlPath }; return }

Write-Host "监控启动（每 $IntervalSeconds 秒刷新）… Ctrl+C 停止监控（不影响训练）。HTML: $htmlPath" -ForegroundColor Cyan
Update
if ($Open) { Start-Process $htmlPath }
try {
    while ($true) { Start-Sleep -Seconds $IntervalSeconds; Update }
} finally {
    Write-Host "监控已停止。训练进程不受影响；最近快照保留在 $htmlPath" -ForegroundColor Cyan
}
