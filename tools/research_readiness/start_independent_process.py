"""One-shot Windows lifetime isolation; never grants training or retries a task.

WMI creates a hidden supervisor outside the desktop's nested jobs. The supervisor
must prove it has neither a Job nor package identity before starting the target.
All paths, arguments, environment values and process ids stay in ignored storage.
"""
import argparse
import base64
import ctypes
from ctypes import wintypes as w
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[2]
PRIVATE=ROOT/'docs/research_readiness/.local'
ENVIRONMENT={'PYTHONPATH','PYTHONUTF8','PYTHONHASHSEED','CUBLAS_WORKSPACE_CONFIG','OMP_NUM_THREADS','MKL_NUM_THREADS'}


def read(path):return json.loads(Path(path).read_bytes())
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def write(path,value):
    with Path(path).open('x',encoding='utf-8') as f:json.dump(value,f,indent=2,ensure_ascii=False,allow_nan=False)
def now():return datetime.now(timezone.utc).isoformat()


def host_identity():
    if os.name!='nt':raise RuntimeError('Windows lifetime admission required')
    k=ctypes.WinDLL('kernel32',use_last_error=True)
    k.GetCurrentProcess.restype=w.HANDLE
    k.IsProcessInJob.argtypes=[w.HANDLE,w.HANDLE,ctypes.POINTER(w.BOOL)]
    member=w.BOOL()
    if not k.IsProcessInJob(k.GetCurrentProcess(),None,ctypes.byref(member)):raise ctypes.WinError(ctypes.get_last_error())
    n=w.UINT();k.GetCurrentPackageFullName.argtypes=[ctypes.POINTER(w.UINT),w.LPWSTR]
    package_status=k.GetCurrentPackageFullName(ctypes.byref(n),None)
    return dict(pid=os.getpid(),parent_pid=os.getppid(),in_any_job=bool(member.value),package_status=package_status)


def require_independent(identity):
    if identity.get('in_any_job') is not False or identity.get('package_status')!=15700:
        raise PermissionError('Still in a Job/package; target not started, no fallback')


def validate_spec(path):
    path=Path(path).resolve()
    if not path.is_relative_to(PRIVATE.resolve()):raise PermissionError('Private specification required')
    spec=read(path);command=spec['command'];folder=Path(spec['service_dir']).resolve()
    if not folder.is_relative_to(PRIVATE.resolve()) or not folder.is_dir():raise PermissionError('Fresh private service namespace required')
    if not isinstance(command,list) or len(command)<3 or any(not isinstance(s,str) for s in command) or command[1]!='-B':raise ValueError('Explicit Python argv required')
    executable,entry=Path(command[0]),Path(command[2]).resolve()
    if not executable.is_absolute() or not executable.is_file() or not entry.is_file():raise ValueError('Explicit existing executable and entry required')
    if set(spec.get('environment',{}))-ENVIRONMENT:raise PermissionError('Unexpected environment override')
    if spec['kind']=='READ_ONLY_MONITOR':
        if entry!=(ROOT/'tools/b2_monitor/server.py').resolve():raise PermissionError('Only existing read-only monitor')
    elif spec['kind']=='ENGINEERING_PROBE':
        if not entry.is_relative_to(PRIVATE.resolve()):raise PermissionError('Probe must be an ignored local script')
    elif spec['kind'] in ('METRIC_BACKFILL_COMPLETION','METRIC_BACKFILL_CORRECTION'):
        if entry!=(ROOT/'tools/research_readiness/resume_metric_backfill.py').resolve() or command[3]!='execute':raise PermissionError('Only the once-only 2024 metric completion controller')
        private=read(command[command.index('--private')+1])
        if private.get('authorization_basis')!='CURRENT_USER_FINISH_EXISTING_METRIC_BACKFILL_20261030' or Path(private['new_output_root']).exists():raise PermissionError('Consumed or unrequested metric completion')
        if spec['kind']=='METRIC_BACKFILL_CORRECTION':
            if private.get('correction_scope')!='B01_PRECISION_CORRECTION_4_20261030':raise PermissionError('Exact four-pass correction required')
            import importlib.util
            definition=importlib.util.spec_from_file_location('corrective_metric_gate',entry);gate=importlib.util.module_from_spec(definition);definition.loader.exec_module(gate)
            gate.validate(private)  # Reject missing grant before WMI target creation.
    elif spec['kind']=='APPROVAL_BOUND_EXECUTION':
        if entry.name not in ('start_dynamic_multiseed.py','start_dynamic_multiseed_recovery.py','start_dote_numeric_control.py','start_dote_numeric_multiseed.py','start_dote_physical_control.py') or command[3]!='execute':raise PermissionError('Only the approval-bound controller')
        def argument(flag):return Path(command[command.index(flag)+1])
        approval=read(argument('--researcher-approval'));proposal=read(argument('--proposal'));private=read(argument('--private-preparation'))
        if approval.get('approved_by_researcher') is not True or not approval.get('decision_id'):raise PermissionError('Explicit research decision required')
        if any(approval.get(k)!=proposal[k] for k in ('proposal_sha256','tasks','budget','scientific_choices')):raise PermissionError('Exact approved grant required')
        if approval['code_commit']!=proposal['execution_code_commit'] or approval['output_root']!=private['output_root'] or Path(private['output_root']).exists():raise PermissionError('Consumed or mismatched grant; never restart')
        commit=subprocess.check_output(['git','-C',spec['cwd'],'rev-parse','HEAD'],text=True).strip()
        dirty=subprocess.check_output(['git','-C',spec['cwd'],'status','--porcelain'],text=True).strip()
        if commit!=approval['code_commit'] or dirty or entry.parent.parent.parent!=Path(spec['cwd']).resolve():raise PermissionError('Clean approved checkout required')
    else:raise PermissionError('Unknown process scope')
    return spec,folder


def spawn(path):
    spec,folder=validate_spec(path)
    write(folder/'independent_launch_claim.json',dict(at=now(),spec_sha256=sha(path),automatic_retry=False))
    command=subprocess.list2cmdline([sys.executable,'-B',str(Path(__file__).resolve()),'supervise','--spec',str(Path(path).resolve())])
    # Values cross the PowerShell boundary as base64 JSON, never shell code.
    payload=base64.b64encode(json.dumps(dict(command=command,cwd=str(ROOT)),ensure_ascii=False).encode()).decode()
    script='''$ErrorActionPreference='Stop'
$r=[Text.Encoding]::UTF8.GetString([Convert]::FromBase64String([Console]::In.ReadToEnd()))|ConvertFrom-Json
$s=New-CimInstance -ClassName Win32_ProcessStartup -ClientOnly -Property @{ShowWindow=[uint16]0;CreateFlags=[uint32]16777216}
$p=Invoke-CimMethod -ClassName Win32_Process -MethodName Create -Arguments @{CommandLine=$r.command;CurrentDirectory=$r.cwd;ProcessStartupInformation=$s}
@{return_value=$p.ReturnValue;supervisor_pid=$p.ProcessId}|ConvertTo-Json -Compress
'''
    result=subprocess.run(['powershell.exe','-NoProfile','-NonInteractive','-Command',script],input=payload,capture_output=True,text=True,encoding='utf-8',timeout=20,creationflags=subprocess.CREATE_NO_WINDOW,check=True)
    creation=json.loads(result.stdout);write(folder/'wmi_creation.json',creation)
    if creation['return_value']!=0:raise RuntimeError('Independent creation failed; no retry/fallback')
    return creation


def supervise(path):
    spec,folder=validate_spec(path);claim=read(folder/'independent_launch_claim.json')
    if claim['spec_sha256']!=sha(path):raise PermissionError('Specification changed after claim')
    identity=host_identity();write(folder/'independence.json',dict(at=now(),**identity))
    require_independent(identity)  # Before target can open any scientific input.
    environment=dict(os.environ,**spec.get('environment',{}))
    with (folder/'target_stdout.log').open('xb') as stdout,(folder/'target_stderr.log').open('xb') as stderr:
        process=subprocess.Popen(spec['command'],cwd=spec['cwd'],env=environment,stdout=stdout,stderr=stderr,creationflags=subprocess.CREATE_NO_WINDOW)
        write(folder/'target_launch.json',dict(at=now(),pid=process.pid,supervisor_pid=os.getpid(),spec_sha256=sha(path),kind=spec['kind'],automatic_retry=False))
        code=process.wait()
    write(folder/'target_exit.json',dict(at=now(),pid=process.pid,return_code=code,return_code_u32_hex=hex(code&0xffffffff),automatic_retry=False))
    return code


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('mode',choices=('spawn','supervise'));parser.add_argument('--spec',type=Path,required=True);args=parser.parse_args()
    try:
        if args.mode=='spawn':print(json.dumps(spawn(args.spec)))
        else:raise SystemExit(supervise(args.spec))
    except Exception as exc:
        folder=Path(read(args.spec)['service_dir'])
        write(folder/'independent_failure.json',dict(at=now(),error=type(exc).__name__+': '+str(exc),automatic_retry=False))
        raise
