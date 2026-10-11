"""One-shot child with external CPU/time watchdog; there is no retry branch."""
import json
import ctypes
from ctypes import wintypes
import os
from pathlib import Path
import subprocess
import sys
import time
from . import ROOT,OUT,LIMITS
from .resources import memory,utcnow

K=ctypes.WinDLL('kernel32',use_last_error=True)
K.OpenProcess.argtypes=[wintypes.DWORD,wintypes.BOOL,wintypes.DWORD]
K.OpenProcess.restype=wintypes.HANDLE
K.CloseHandle.argtypes=[wintypes.HANDLE]
K.CloseHandle.restype=wintypes.BOOL

def open_worker(pid):
    if type(pid) is not int or pid<=0: raise ValueError('INVALID_WORKER_PID')
    handle=K.OpenProcess(0x0410,False,pid)  # QUERY_INFORMATION | VM_READ
    if not handle: raise ctypes.WinError(ctypes.get_last_error())
    return handle

def launch():
    root=OUT/'.local'; root.mkdir(exist_ok=True)
    if (root/'attempt_001').exists() or (root/'driver_status.json').exists():
        raise PermissionError('NO_SMOKE_LAUNCH_RETRY')
    env=os.environ.copy(); env.update(PYTHONPATH=str(ROOT/'src'),PYTHONHASHSEED='2026',CUBLAS_WORKSPACE_CONFIG=':4096:8')
    started=time.monotonic(); peak=0; violation=None; actual_handle=None; worker_pid=None
    with (root/'worker_console.private.log').open('xb') as log:
        process=subprocess.Popen([sys.executable,'-m','yuntapr.experimental.phase_b_v2_real_train_smoke.run'],
            cwd=ROOT,env=env,stdout=log,stderr=subprocess.STDOUT)
        while process.poll() is None:
            try:
                identity=root/'attempt_001/worker_identity.json'
                if actual_handle is None and identity.is_file():
                    data=json.loads(identity.read_bytes())
                    from . import AUTHORIZATION_ID
                    if data['campaign']!=AUTHORIZATION_ID: raise ValueError('WORKER_IDENTITY_MISMATCH')
                    worker_pid=data['worker_pid']; actual_handle=open_worker(worker_pid)
                if actual_handle is not None:
                    peak=max(peak,memory(actual_handle)['working_set_bytes'])
            except OSError:
                if process.poll() is None: violation='CPU_WATCHDOG_UNAVAILABLE'
            except (ValueError,KeyError): violation='CPU_WATCHDOG_IDENTITY_UNAVAILABLE'
            if peak>LIMITS['MAX_CPU_WORKING_SET_BYTES']: violation='CPU_WATCHDOG_LIMIT'
            if time.monotonic()-started>=LIMITS['MAX_ELAPSED_SECONDS']: violation='TIME_WATCHDOG_LIMIT'
            if violation:
                # Kill the actual worker as well as the venv launcher.
                if worker_pid is not None:
                    subprocess.run(['taskkill','/PID',str(worker_pid),'/T','/F'],capture_output=True)
                process.kill(); process.wait(); break
            time.sleep(.1)
    if actual_handle is not None: K.CloseHandle(actual_handle)
    status=dict(finished_at_utc=utcnow(),exit_code=process.returncode,watchdog_violation=violation,
        elapsed_seconds=time.monotonic()-started,peak_sampled_child_working_set_bytes=peak,
        monitor_interval_seconds=.1,retries=0,actual_worker_pid_verified=worker_pid is not None)
    (root/'driver_status.json').write_text(json.dumps(status,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(status))
    return process.returncode

if __name__=='__main__': raise SystemExit(launch())
