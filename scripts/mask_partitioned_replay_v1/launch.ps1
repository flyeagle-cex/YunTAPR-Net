param([Parameter(Mandatory=$true)][string]$Run)
$ErrorActionPreference = 'Stop'
$taskRepo = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..\..'))
$taskRun = [IO.Path]::GetFullPath($Run)
$taskRunRoot = [IO.Path]::GetFullPath((Join-Path $taskRepo 'docs\mask_partitioned_quantile_replay\runs'))
if ([IO.Path]::GetDirectoryName($taskRun) -ne $taskRunRoot) { throw 'Exact independent diagnostic run required' }
if (Test-Path -LiteralPath (Join-Path $taskRun 'launch_identity.json')) { throw 'No duplicate launch or automatic replay retry' }
$taskPython = 'F:\pytorch\Research\.venv-cuda\Scripts\python.exe'
# Required frozen protocol startup values, applied before Python/CUDA starts.
$env:PYTHONHASHSEED = '2026'
$env:CUBLAS_WORKSPACE_CONFIG = ':4096:8'
$taskPrelaunch = @'
from pathlib import Path
import sys,json
root=Path.cwd();sys.path.insert(0,str(root/'scripts'))
from mask_partitioned_replay_v1 import common as c
run=Path(sys.argv[1]);gate=c.read(run/'observer_test_result.json');cap=c.read(run/'execution_scope.json')
if gate['status']!='PASS' or cap['operation']!=c.SCOPE or cap['formal_resume_authorized'] or cap['B1_authorized']:
 raise PermissionError('Exact tested diagnostic authority required')
for relative,wanted in {**gate['diagnostic_source_hashes'],**gate['test_source_hashes']}.items():
 if c.digest(root/relative)!=wanted:raise ValueError('Tested source changed: '+relative)
c.verify_snapshot(run)
archive=run/'executed_sources';archive.mkdir(exist_ok=False)
sources=list((root/'scripts/mask_partitioned_replay_v1').iterdir())
sources+=list((root/'tests/mask_partitioned_replay').glob('*.py'))
pins=[]
for p in sources:
 if p.is_file() and p.suffix in ('.py','.ps1','.html','.txt'):
  target=archive/(p.name+'.txt');target.write_bytes(p.read_bytes());pins.append({'source':p.relative_to(root).as_posix(),'snapshot':c.pin(target)})
c.write(run/'executed_source_archive.json',{'utc':c.now(),'sources':pins,'startup_environment':{'PYTHONHASHSEED':'2026','CUBLAS_WORKSPACE_CONFIG':':4096:8'}})
print(json.dumps({'source_identity_gate':'PASS','files':len(pins)}))
'@
Push-Location -LiteralPath $taskRepo
try {
    $taskPrelaunch | & $taskPython -B - $taskRun
    if ($LASTEXITCODE -ne 0) { throw 'Prelaunch source identity gate failed' }
    $taskListener = [Net.Sockets.TcpListener]::new([Net.IPAddress]::Loopback, 8767)
    try { $taskListener.Start() } finally { $taskListener.Stop() }
    $taskQuotedRun = '"' + $taskRun + '"'
    $taskMonitor = Start-Process -FilePath $taskPython -ArgumentList @('-B','-u','scripts\mask_partitioned_replay_v1\monitor.py','--run',$taskQuotedRun,'--port','8767') -WorkingDirectory $taskRepo -WindowStyle Hidden -RedirectStandardOutput (Join-Path $taskRun 'monitor_stdout.txt') -RedirectStandardError (Join-Path $taskRun 'monitor_stderr.txt') -PassThru
    $taskReplay = Start-Process -FilePath $taskPython -ArgumentList @('-B','-u','scripts\mask_partitioned_replay_v1\replay.py','--run',$taskQuotedRun) -WorkingDirectory $taskRepo -WindowStyle Hidden -RedirectStandardOutput (Join-Path $taskRun 'replay_stdout.txt') -RedirectStandardError (Join-Path $taskRun 'replay_stderr.txt') -PassThru
    $taskIdentity = [ordered]@{
        utc=[DateTime]::UtcNow.ToString('o'); scope='ENGINEERING_DIAGNOSTIC_REPLAY_ONLY'; python=$taskPython
        run=$taskRun; replay_launcher_pid=$taskReplay.Id; monitor_launcher_pid=$taskMonitor.Id
        monitor_url='http://127.0.0.1:8767/'; formal_resume_authorized=$false
        formal_optimizer_steps=50537; '2025_RAW_ACCESS'=0; github_push_after_completion=$true
        startup_environment=@{ PYTHONHASHSEED='2026'; CUBLAS_WORKSPACE_CONFIG=':4096:8' }
    }
    $taskIdentity | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath (Join-Path $taskRun 'launch_identity.json') -Encoding utf8
    $taskIdentity | ConvertTo-Json -Depth 8
} finally { Pop-Location }
