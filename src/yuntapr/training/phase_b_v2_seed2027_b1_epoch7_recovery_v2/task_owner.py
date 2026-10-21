"""Fixed human-authorized recovery owner, launched once by Windows Scheduler.

No arbitrary executable/module input, triggers, retries or permission switches.
The worker remains inside the original resource-limited kill-on-close Job.
"""
from __future__ import annotations
import hashlib,json,os,sys
from pathlib import Path
from .protocol import ROOT,LOCAL,LIMITS,CAMPAIGN,session_root,owned_json,atomic_json,verify_release,digest
from yuntapr.experimental.phase_b_v2_owner_lifetime_candidate.task_bridge import quote,ps

def task_name(n: int,nonce: str) -> str:
    if type(n) is not int or not 1<=n<=999 or type(nonce) is not str or len(nonce)!=32 or any(c not in '0123456789abcdef' for c in nonce):
        raise PermissionError('EXACT_SYSTEM_TASK_SESSION_NONCE')
    return f'YunTAPR_Seed2027_B1E7V2_{n:04d}_{nonce}'

def fixed_spec(n: int,nonce: str,release: dict) -> dict:
    """Derive commands solely from the fixed namespace and published runtime."""
    name=task_name(n,nonce)
    runtime=owned_json(LOCAL/'runtime.json')
    if os.path.normcase(sys.executable)!=os.path.normcase(runtime['python']):
        raise PermissionError('FROZEN_OPERATOR_INTERPRETER_REQUIRED')
    entry=ROOT/'scripts/phase_b_v2_seed2027_b1_epoch7_recovery_v2/Task-Owner.ps1'
    rel=entry.relative_to(ROOT).as_posix()
    if hashlib.sha256(entry.read_bytes()).hexdigest()!=release['source_pins'].get(rel):raise ValueError('TASK_BOOTSTRAP_NOT_PUBLISHED_SOURCE')
    import subprocess
    return dict(task_name=name,campaign=CAMPAIGN,session=n,nonce=nonce,
        interpreter=runtime['python'],entry=rel,
        execute=str(Path(os.environ['SystemRoot'])/'System32/WindowsPowerShell/v1.0/powershell.exe'),
        arguments=subprocess.list2cmdline(['-NoProfile','-NonInteractive','-File',str(entry),'-Session',str(n),'-Nonce',nonce]),
        release_sha256=digest(release),source_sha256=release['source_sha256'],
        automatic_retries=0,triggers=0,run_level='Limited',multiple_instances='IgnoreNew',
        execution_time_limit_seconds=LIMITS['max_seconds'])

def validate_owner_request(n: int,nonce: str) -> dict:
    """Recheck the actual durable claim, not an environment authorization bit."""
    from .quota import ro
    task_name(n,nonce)
    release=verify_release()
    request=owned_json(session_root(n)/'task_request.json')
    if request!=fixed_spec(n,nonce,release):raise PermissionError('SYSTEM_TASK_REQUEST_SOURCE_SCOPE')
    con=ro()
    try:
        if con.execute('SELECT status,nonce FROM sessions WHERE n=?',(n,)).fetchone()!=('CLAIMED',nonce):
            raise PermissionError('TASK_OWNER_REQUIRES_EXACT_UNCONSUMED_CLAIM')
        if con.execute('SELECT id,status FROM campaign').fetchone()!=(CAMPAIGN,'ACTIVE'):
            raise PermissionError('SYSTEM_TASK_CAMPAIGN_NOT_ACTIVE')
    finally:con.close()
    return request

def start_owner(n: int,nonce: str,release: dict) -> dict:
    """One OS task invocation after durable claim. Any uncertainty is fatal."""
    spec=fixed_spec(n,nonce,release);folder=session_root(n)
    # Never overwrite a prior attempt or reusable launch authorization.
    if (folder/'task_request.json').exists():raise PermissionError('NO_SYSTEM_TASK_LAUNCH_RETRY')
    atomic_json(folder/'task_request.json',spec)
    script="$ErrorActionPreference='Stop';[Console]::OutputEncoding=[Text.Encoding]::UTF8;"
    script+=f"$name={quote(spec['task_name'])};if(Get-ScheduledTask -TaskName $name -ErrorAction SilentlyContinue){{throw 'No existing task overwrite or retry'}};"
    script+=f"$a=New-ScheduledTaskAction -Execute {quote(spec['execute'])} -Argument {quote(spec['arguments'])} -WorkingDirectory {quote(ROOT)};"
    script+="$p=New-ScheduledTaskPrincipal -UserId ([Security.Principal.WindowsIdentity]::GetCurrent().Name) -LogonType Interactive -RunLevel Limited;"
    script+=f"$s=New-ScheduledTaskSettingsSet -ExecutionTimeLimit (New-TimeSpan -Seconds {LIMITS['max_seconds']}) -MultipleInstances IgnoreNew -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries;"
    script+="Register-ScheduledTask -TaskName $name -InputObject (New-ScheduledTask -Action $a -Principal $p -Settings $s)|Out-Null;"
    script+="$t=Get-ScheduledTask -TaskName $name;"
    script+=f"if($t.Triggers.Count -ne 0 -or $t.Settings.RestartCount -ne 0 -or $t.Principal.RunLevel -ne 'Limited' -or $t.Settings.MultipleInstances -ne 'IgnoreNew' -or $t.Actions.Count -ne 1 -or $t.Actions[0].Execute -ne {quote(spec['execute'])} -or $t.Actions[0].Arguments -ne {quote(spec['arguments'])}){{throw 'Fixed task source or policy mismatch'}};"
    script+="Start-ScheduledTask -TaskName $name;[pscustomobject]@{registered=$true;triggers=0;automatic_retries=0;run_level='Limited';multiple_instances='IgnoreNew'}|ConvertTo-Json -Compress"
    result=json.loads(ps(script))
    atomic_json(folder/'task_registration.json',dict(**spec,registration=result))
    return dict(task_name=spec['task_name'],os_owned=True,registration=result)
