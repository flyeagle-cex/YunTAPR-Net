"""Artificial process only: no datasets, torch, CUDA or optimizer imports."""
from pathlib import Path
import ctypes as C
import json,os,sys,time
from .receipts import LOCAL
from .classification import scope
from yuntapr.experimental.phase_b_v2_execution_watchdog_candidate.winjob import (
    Job,create_job,close_handle,checked,set_job,ExtendedLimit,native_identity,K)
from ctypes import wintypes as W

CAMPAIGN='ARTIFICIAL_POSTMORTEM_V1'

def write(path,value):
    with path.open('x',encoding='utf-8',newline='\n') as f:json.dump(value,f);f.flush();os.fsync(f.fileno())

def main():
    mode,raw,nonce=sys.argv[1:]
    folder=Path(raw)
    if (mode not in ('child','owner-crash') or not folder.is_absolute() or not folder.is_relative_to(LOCAL/'tests') or
        '..' in folder.parts or '2025' in raw or len(nonce)!=32):raise PermissionError('CLOSED_ARTIFICIAL_FIXTURE')
    K.GetCurrentProcess.restype=W.HANDLE;me=native_identity(K.GetCurrentProcess())
    if mode=='child':
        write(folder/'child.json',dict(**me,campaign=CAMPAIGN,nonce=nonce))
        time.sleep(8);return
    name=f'Local\\{CAMPAIGN}__1__{nonce}'
    owner=dict(**me,campaign=CAMPAIGN,session=1,nonce=nonce,job_name=name)
    job=Job();close_handle(job.handle);job.handle=checked(create_job(None,name))
    limits=ExtendedLimit();limits.basic.flags=0x2000|0x8|0x200;limits.basic.active_limit=8;limits.job_memory=256*1024**2
    checked(set_job(job.handle,9,C.byref(limits),C.sizeof(limits)))
    pid=job.spawn([sys.executable,'-m',__package__+'.fixture','child',str(folder),nonce],Path(__file__).absolute().parents[4])
    deadline=time.monotonic()+4
    while not (folder/'child.json').exists():
        if time.monotonic()>deadline:raise TimeoutError('ARTIFICIAL_CHILD_REGISTRATION')
        job.snapshot();time.sleep(.01)
    worker=json.loads((folder/'child.json').read_bytes());scope(owner,worker,CAMPAIGN,1)
    write(folder/'owner.json',owner)
    # Deliberately bypass finally. OS closing the last Job owner must kill leaf.
    os._exit(19)

if __name__=='__main__':main()
