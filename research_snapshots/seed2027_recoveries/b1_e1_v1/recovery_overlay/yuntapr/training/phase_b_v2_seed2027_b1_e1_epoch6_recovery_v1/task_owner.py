"""One fixed GUI OS-task action; no console PowerShell owns the training tree."""
from __future__ import annotations
import hashlib,json,os,subprocess,sys
from pathlib import Path
from .protocol import ROOT,LOCAL,LIMITS,CAMPAIGN,session_root,owned_json,atomic_json,verify_release,digest
from yuntapr.experimental.phase_b_v2_owner_lifetime_candidate.task_bridge import quote,ps

def task_name(n: int,nonce: str) -> str:
    if type(n) is not int or not 1<=n<=999 or type(nonce) is not str or len(nonce)!=32 or any(c not in '0123456789abcdef' for c in nonce):
        raise PermissionError('EXACT_SYSTEM_TASK_SESSION_NONCE')
    return f'YunTAPR_Seed2027_B1E1E6R1_{n:04d}_{nonce}'

def gui_runtime(release: dict) -> dict:
    row=owned_json(LOCAL/'gui_runtime.json')
    if digest(row)!=release['gui_runtime_sha256']:raise PermissionError('PUBLISHED_GUI_RUNTIME_SHA')
    if set(row)!= {'wrapper_path','native_path','binaries','venv_config_sha256'}:raise PermissionError('GUI_RUNTIME_SCHEMA')
    for key in ('wrapper_path','native_path'):
        path=Path(row[key])
        if not path.is_absolute() or '..' in path.parts or '2025' in str(path) or path.name.lower()!='pythonw.exe':raise PermissionError('REGISTERED_GUI_BINARY_LEXICAL_SCOPE')
        if hashlib.sha256(path.read_bytes()).hexdigest()!=row['binaries'][key]['sha256']:raise PermissionError('GUI_INTERPRETER_PAYLOAD_CHANGED')
        if hashlib.sha256(os.path.normcase(str(path)).encode('utf-8')).hexdigest()!=row['binaries'][key]['image_path_key']:raise PermissionError('GUI_NATIVE_PATH_KEY')
    return row

def fixed_spec(n: int,nonce: str,release: dict) -> dict:
    name=task_name(n,nonce);runtime=owned_json(LOCAL/'runtime.json');gui=gui_runtime(release)
    allowed={os.path.normcase(runtime['python']),os.path.normcase(gui['wrapper_path']),os.path.normcase(gui['native_path'])}
    if os.path.normcase(sys.executable) not in allowed:raise PermissionError('FROZEN_OPERATOR_OR_GUI_INTERPRETER_REQUIRED')
    entry=ROOT/'recovery_overlay/yuntapr/training/phase_b_v2_seed2027_b1_e1_epoch6_recovery_v1/gui_owner.py';relative=entry.relative_to(ROOT).as_posix()
    if hashlib.sha256(entry.read_bytes()).hexdigest()!=release['source_pins'].get(relative):raise PermissionError('GUI_BOOTSTRAP_NOT_PUBLISHED_SOURCE')
    return dict(task_name=name,campaign=CAMPAIGN,session=n,nonce=nonce,interpreter=runtime['python'],entry=relative,execute=gui['wrapper_path'],
        arguments=subprocess.list2cmdline(['-B',str(entry),str(n),nonce]),gui_runtime_sha256=release['gui_runtime_sha256'],
        release_sha256=digest(release),source_sha256=release['source_sha256'],automatic_retries=0,triggers=0,run_level='Limited',multiple_instances='IgnoreNew',
        execution_time_limit_seconds=LIMITS['max_seconds'])

def validate_owner_request(n: int,nonce: str) -> dict:
    from .quota import ro
    task_name(n,nonce);release=verify_release();request=owned_json(session_root(n)/'task_request.json')
    if request!=fixed_spec(n,nonce,release):raise PermissionError('SYSTEM_TASK_REQUEST_SOURCE_SCOPE')
    con=ro()
    try:
        if con.execute('SELECT status,nonce FROM sessions WHERE n=?',(n,)).fetchone()!=('CLAIMED',nonce):raise PermissionError('TASK_OWNER_REQUIRES_EXACT_UNCONSUMED_CLAIM')
        if con.execute('SELECT id,status FROM campaign').fetchone()!=(CAMPAIGN,'ACTIVE'):raise PermissionError('SYSTEM_TASK_CAMPAIGN_NOT_ACTIVE')
    finally:con.close()
    return request

def start_owner(n: int,nonce: str,release: dict) -> dict:
    if os.path.normcase(sys.executable)!=os.path.normcase(owned_json(LOCAL/'runtime.json')['python']):raise PermissionError('FROZEN_OPERATOR_INTERPRETER_REQUIRED')
    spec=fixed_spec(n,nonce,release);folder=session_root(n)
    if (folder/'task_request.json').exists():raise PermissionError('NO_SYSTEM_TASK_LAUNCH_RETRY')
    atomic_json(folder/'task_request.json',spec)
    script="$ErrorActionPreference='Stop';[Console]::OutputEncoding=[Text.Encoding]::UTF8;"
    script+=f"$name={quote(spec['task_name'])};if(Get-ScheduledTask -TaskName $name -ErrorAction SilentlyContinue){{throw 'No existing task overwrite or retry'}};"
    script+=f"$a=New-ScheduledTaskAction -Execute {quote(spec['execute'])} -Argument {quote(spec['arguments'])} -WorkingDirectory {quote(ROOT)};"
    script+="$p=New-ScheduledTaskPrincipal -UserId ([Security.Principal.WindowsIdentity]::GetCurrent().Name) -LogonType Interactive -RunLevel Limited;"
    script+=f"$s=New-ScheduledTaskSettingsSet -ExecutionTimeLimit (New-TimeSpan -Seconds {LIMITS['max_seconds']}) -MultipleInstances IgnoreNew -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries;"
    script+="Register-ScheduledTask -TaskName $name -InputObject (New-ScheduledTask -Action $a -Principal $p -Settings $s)|Out-Null;"
    script+="$t=Get-ScheduledTask -TaskName $name;"
    script+=f"if($t.Triggers.Count -ne 0 -or $t.Settings.RestartCount -ne 0 -or $t.Principal.RunLevel -ne 'Limited' -or $t.Settings.MultipleInstances -ne 'IgnoreNew' -or $t.Actions.Count -ne 1 -or $t.Actions[0].Execute -ne {quote(spec['execute'])} -or $t.Actions[0].Arguments -ne {quote(spec['arguments'])}){{throw 'Fixed GUI task source or policy mismatch'}};"
    script+="Start-ScheduledTask -TaskName $name;[pscustomobject]@{registered=$true;gui=$true;triggers=0;automatic_retries=0;run_level='Limited';multiple_instances='IgnoreNew'}|ConvertTo-Json -Compress"
    result=json.loads(ps(script));atomic_json(folder/'task_registration.json',dict(**spec,registration=result))
    return dict(task_name=spec['task_name'],os_owned=True,console_free=True,registration=result)

def validate_gui_parent(n: int,nonce: str) -> None:
    """Bind the live GUI native identity AND this owner's actual Job membership."""
    import ctypes as C
    from ctypes import wintypes as W
    from yuntapr.experimental.phase_b_v2_execution_watchdog_candidate.winjob import (
        K,bind,checked,open_process,native_identity,close_handle,exited,in_job)
    release=verify_release();runtime=gui_runtime(release)
    row=owned_json(session_root(n)/'gui_bootstrap_identity.json')
    name=f'Local\\{CAMPAIGN}__GUI__{n}__{nonce}'
    if row['nonce']!=nonce or row['campaign']!=CAMPAIGN or row['session']!=n or row['job_name']!=name:
        raise PermissionError('GUI_NATIVE_PARENT_SCOPE')
    handle=checked(open_process(0x00100000|0x1000,False,row['pid']));job=None
    try:
        actual=native_identity(handle)
        if exited(handle) or any(row[k]!=v for k,v in actual.items()) or actual['image_path_key'] not in {v['image_path_key'] for v in runtime['binaries'].values()}:
            raise PermissionError('GUI_NATIVE_PARENT_IDENTITY')
        opened=bind(K,'OpenJobObjectW',[W.DWORD,W.BOOL,W.LPCWSTR],W.HANDLE)
        job=checked(opened(4,False,name));K.GetCurrentProcess.restype=W.HANDLE
        member=W.BOOL();checked(in_job(K.GetCurrentProcess(),job,C.byref(member)))
        if not member.value:raise PermissionError('OWNER_OUTSIDE_GUI_OWNED_JOB')
    finally:
        if job:close_handle(job)
        close_handle(handle)
