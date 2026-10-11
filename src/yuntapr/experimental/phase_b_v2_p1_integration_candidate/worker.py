"""Artificial stdlib-only fixture. No data/model/GPU import is permitted."""
import json
import os
from pathlib import Path
import subprocess
import sys
import time


class RejectScienceImports:
    def find_spec(self,fullname,path=None,target=None):
        if fullname.split('.')[0] in {'torch','numpy','netCDF4','h5py','cupy'}:
            raise PermissionError('NO_DATA_MODEL_OR_GPU_IMPORT')


sys.meta_path.insert(0,RejectScienceImports())
from yuntapr.experimental.phase_b_v2_execution_watchdog_candidate.winjob import K,native_identity
from ctypes import wintypes as W
K.GetCurrentProcess.restype=W.HANDLE


def write(path,value):
    tmp=path.with_suffix('.tmp')
    with tmp.open('xb') as stream:
        stream.write(json.dumps(value).encode());stream.flush();os.fsync(stream.fileno())
    tmp.replace(path)


def main():
    folder,mode,nonce,key=Path(sys.argv[1]),sys.argv[2],sys.argv[3],sys.argv[4]
    monitor_pid=int(sys.argv[5])
    script=str(Path(__file__).absolute())
    if mode=='wrapper':
        subprocess.Popen([sys.executable,script,str(folder),sys.argv[6],nonce,key,str(monitor_pid)])
        return 0
    ident=native_identity(K.GetCurrentProcess())
    if mode=='leaf':
        write(folder/'leaf.json',ident)
        while True:time.sleep(.02)
    if mode=='exit_before':return 7
    row=dict(ident,nonce=nonce,key=key,scope='SYNTHETIC_ENGINEERING_ONLY',
             no_science_imports=not any(m.split('.')[0] in {'torch','numpy','netCDF4','h5py','cupy'} for m in sys.modules))
    if mode=='foreign_pid':row['pid']=monitor_pid
    if mode=='missing_pid':row['pid']=4294967294
    if mode=='wrong_creation':row['creation_filetime']+=1
    if mode=='wrong_image':row['image_path_key']='0'*64
    if mode=='wrong_nonce':row['nonce']='0'*32
    write(folder/'identity.json',row)
    if mode=='normal':
        time.sleep(.25);write(folder/'complete.json',dict(key=key,nonce=nonce,status='ARTIFICIAL_COMPLETE'));return 0
    if mode=='unexpected_exit':time.sleep(.2);return 9
    if mode=='monitor_exit':
        from yuntapr.experimental.phase_b_v2_p1_integration_candidate.launcher import run
        # Test a real monitor os._exit, not a graceful Job.close surrogate.
        import threading
        from yuntapr.experimental.phase_b_v2_p1_integration_candidate.scope import LOCAL
        existing=set(LOCAL.glob('job_*/monitor_crash.json'))
        def forward_leaf():
            for _ in range(400):
                for p in set(LOCAL.glob('job_*/monitor_crash.json'))-existing:
                    r=json.loads(p.read_text())
                    if r['worker_identity']['pid']!=ident['pid']:
                        write(folder/'leaf.json',r['leaf_identity']);return
                time.sleep(.005)
        threading.Thread(target=forward_leaf,daemon=True).start()
        run('crash_inner')
        return 99 # unreachable
    if mode=='timeout_tree':
        subprocess.Popen([sys.executable,script,str(folder),'leaf',nonce,key,str(monitor_pid)])
    if mode=='memory':
        allocated=bytearray(32*1024**2)
        for i in range(0,len(allocated),4096):allocated[i]=1
        write(folder/'allocation.json',dict(bytes=len(allocated)))
    if mode=='cpu':
        while True: sum(range(20000))
    while True:time.sleep(.02)


if __name__=='__main__':raise SystemExit(main())
