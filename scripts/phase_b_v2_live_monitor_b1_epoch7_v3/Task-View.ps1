param()
if($args.Count){throw 'Fixed read-only monitor only'}
$ErrorActionPreference='Stop'
$taskRepo=[IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..\..'))
$taskPython=(Get-Content -LiteralPath (Join-Path $taskRepo 'docs\phase_b_v2_formal_execution\seed2027_b1_epoch7_recovery_v3\.local\runtime.json') -Raw | ConvertFrom-Json).python
$env:PYTHONUTF8='1';$env:PYTHONPATH=Join-Path $taskRepo 'src'
$taskLog=Join-Path $PSScriptRoot '.local'
New-Item -ItemType Directory -Force -Path $taskLog | Out-Null
$taskStamp=Get-Date -Format 'yyyyMMddTHHmmssfff'
Set-Location -LiteralPath $taskRepo
& $taskPython -u (Join-Path $PSScriptRoot 'server.py') --port 53084 1> (Join-Path $taskLog "$taskStamp.stdout.txt") 2> (Join-Path $taskLog "$taskStamp.stderr.txt")
exit $LASTEXITCODE
