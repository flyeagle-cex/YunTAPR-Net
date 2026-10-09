param([int]$Port = 8771)
$ErrorActionPreference = 'Stop'
$taskRepo = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..\..'))
$taskPython = 'F:\pytorch\Research\.venv-cuda\Scripts\python.exe'
$taskAuthority = Join-Path $taskRepo 'docs\v2_phase_a_authorized\pair_20261007T070503_825794Z\resume_20261009T003216_479921Z\authorization.json'
$taskAuthoritySha = '73d8e76649ac1310ff1a541cb7f0e7518c4ad527c8571113726b56312c7115a2'
if ((Get-FileHash -LiteralPath $taskAuthority -Algorithm SHA256).Hash.ToLowerInvariant() -ne $taskAuthoritySha) {
    throw 'Frozen completion authority changed'
}
$taskExisting = @(Get-CimInstance Win32_Process | Where-Object {
    $_.CommandLine -match 'python.*(run_read_only_closeout_v2\.py|review_paired_best_v2\.py|serve_completed_phase_a_v2\.py)'
})
if ($taskExisting.Count -ne 0) { throw 'An existing read-only closeout process is live; no duplicate launch' }
$taskDispatch = Join-Path $taskRepo ('docs\v2_phase_a_review\completed_monitor_dispatch\run_' + [DateTime]::UtcNow.ToString('yyyyMMddTHHmmss_ffffffZ'))
New-Item -ItemType Directory -Path $taskDispatch -ErrorAction Stop | Out-Null
$env:PYTHONUTF8 = '1'
$env:PYTHONDONTWRITEBYTECODE = '1'
$env:PYTHONHASHSEED = '2026'
$env:CUBLAS_WORKSPACE_CONFIG = ':4096:8'
try {
    $taskScript = Join-Path $PSScriptRoot 'serve_completed_phase_a_v2.py'
    $taskFinalAudit = Join-Path $taskRepo 'docs\v2_phase_a_review\final_completion\run_20261009T083217_518899Z\FINAL_COMPLETION_AUDIT.json'
    $taskPdfAudit = Join-Path $taskRepo 'docs\v2_phase_a_review\paired_packets\run_20261009T072307_459014Z\pdf_delivery_v2\real_visual_audit.json'
    $taskArgs = @('-B', ('"' + $taskScript + '"'), '--final-audit', ('"' + $taskFinalAudit + '"'),
        '--completion-commit', '0cc41c660dfa3ec83f604413cc7b4663289e973b',
        '--pdf-audit', ('"' + $taskPdfAudit + '"'), '--port', [string]$Port)
    $taskProcess = Start-Process -FilePath $taskPython -ArgumentList $taskArgs -WorkingDirectory $taskRepo -WindowStyle Hidden `
        -RedirectStandardOutput (Join-Path $taskDispatch 'monitor.stdout.log') `
        -RedirectStandardError (Join-Path $taskDispatch 'monitor.stderr.log') -PassThru
    $taskProof = [ordered]@{
        status = 'DETACHED_COMPLETED_MONITOR_DISPATCHED'
        pid = $taskProcess.Id
        started_utc = [DateTime]::UtcNow.ToString('o')
        executable = $taskPython
        arguments = $taskArgs
        publication_commit = '0cc41c660dfa3ec83f604413cc7b4663289e973b'
        monitor_url = ('http://127.0.0.1:' + $Port + '/')
        DISPATCH_STARTS_FORMAL_TRAINING = $false
        OPTIMIZER_STEPS = 0
        '2025_RAW_ACCESS' = 0
        predecessor_interruption = 'docs/v2_phase_a_review/review_interruptions/run_20261009T071920_152639Z/interrupted_review_closeout.json'
    }
    $taskProof | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath (Join-Path $taskDispatch 'dispatch.json') -Encoding utf8
    @{pid=$taskProcess.Id; dispatch=$taskDispatch; status=$taskProof.status} | ConvertTo-Json -Compress
} catch {
    @{status='DETACHED_DISPATCH_FAILED';error=[string]$_;started_utc=[DateTime]::UtcNow.ToString('o');automatic_retry=$false} |
        ConvertTo-Json | Set-Content -LiteralPath (Join-Path $taskDispatch 'dispatch_failure.json') -Encoding utf8
    throw
}
