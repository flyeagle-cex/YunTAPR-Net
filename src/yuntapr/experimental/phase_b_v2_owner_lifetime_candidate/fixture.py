"""Bounded artificial owner/worker; no model, GPU, data, ledger or optimizer."""
from pathlib import Path
from datetime import datetime,timezone
from ctypes import wintypes as W
import json,os,subprocess,sys,time
from .context import current_job_profile
from yuntapr.experimental.phase_b_v2_execution_watchdog_candidate.winjob import Job,K,native_identity,exited
K.GetCurrentProcess.restype=W.HANDLE

def save(folder,name,value):
    with (folder/name).open('x',encoding='utf-8') as f:json.dump(value,f);f.flush();os.fsync(f.fileno())

def main():
    mode,folder,nonce,kind=sys.argv[1:];folder=Path(folder)
    if len(nonce)!=32 or 'artificial_' not in folder.name:raise PermissionError('ARTIFICIAL_FIXTURE_ONLY')
    if mode=='launcher':
        save(folder,'launcher_identity.json',dict(**native_identity(K.GetCurrentProcess()),nonce=nonce))
        argv=[sys.executable,'-m',__package__+'.fixture','owner',str(folder),nonce,kind]
        try:
            if kind=='legacy':
                child=subprocess.Popen(argv,creationflags=subprocess.CREATE_NO_WINDOW,close_fds=True)
                result=dict(wrapper_pid=child.pid,parent_job=current_job_profile())
            else:raise PermissionError('RETIRED_DIRECT_INDEPENDENT_LAUNCH_USE_SYSTEM_TASK')
            save(folder,'launch_result.json',result)
        except BaseException as e:
            save(folder,'launch_error.json',dict(type=type(e).__name__,code=str(e)))
        time.sleep(12);return
    if mode=='worker':
        save(folder,'worker.json',dict(**native_identity(K.GetCurrentProcess()),nonce=nonce))
        time.sleep(12);return
    if mode=='client':
        save(folder,'client.json',dict(**native_identity(K.GetCurrentProcess()),nonce=nonce))
        time.sleep(12);return
    if mode!='owner':raise ValueError('FIXED_FIXTURE_MODE')
    profile=current_job_profile()
    if kind not in ('legacy','task-owned'):raise PermissionError('ARTIFICIAL_FIXED_MODE')
    save(folder,'owner.json',dict(**native_identity(K.GetCurrentProcess()),nonce=nonce,profile=profile))
    job=Job();normal=False
    try:
        job.spawn([sys.executable,'-m',__package__+'.fixture','worker',str(folder),nonce,kind],Path.cwd())
        end=time.monotonic()+10
        while not (folder/'worker.json').exists():
            if time.monotonic()>end:raise TimeoutError('ARTIFICIAL_WORKER_REGISTRATION')
            time.sleep(.01)
        save(folder,'ready.json',dict(nonce=nonce,utc=datetime.now(timezone.utc).isoformat()))
        while time.monotonic()<end:
            if (folder/'stop.request').exists():normal=True;break
            time.sleep(.01)
    finally:
        job.stop();deadline=time.monotonic()+3
        while (job.pids() or any(not exited(h) for h in job.handles.values())) and time.monotonic()<deadline:time.sleep(.01)
        empty=not job.pids() and all(exited(h) for h in job.handles.values());job.close()
        save(folder,'termination.json',dict(artificial=True,normal_request=normal,job_empty=empty,torch_imported='torch' in sys.modules))

if __name__=='__main__':main()
