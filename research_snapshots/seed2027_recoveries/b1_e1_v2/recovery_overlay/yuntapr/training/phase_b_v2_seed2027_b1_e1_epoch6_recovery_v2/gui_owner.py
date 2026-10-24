"""Fixed GUI bootstrap for the direct human-authorized recovery, never a shell."""
from pathlib import Path
import os,sys
ROOT=Path(__file__).absolute().parents[4]
LIVE_ROOT=ROOT.parent/'YunTAPR-Net-push-chunks'
sys.dont_write_bytecode=True
sys.path.insert(0,str(LIVE_ROOT/'src'))
import yuntapr.training
yuntapr.training.__path__.append(str(ROOT.parent/'YunTAPR-Net-completed-review-20261021/recovery_overlay/yuntapr/training'))
yuntapr.training.__path__.append(str(ROOT.parent/'YunTAPR-Net-seed2027-b1-e1-recovery-20261022/recovery_overlay/yuntapr/training'))
yuntapr.training.__path__.append(str(ROOT/'recovery_overlay/yuntapr/training'))

def main() -> int:
    if len(sys.argv)!=3:raise PermissionError('FIXED_GUI_TASK_ARGUMENTS')
    n=int(sys.argv[1]);nonce=sys.argv[2]
    from yuntapr.training.phase_b_v2_seed2027_b1_e1_epoch6_recovery_v2.task_owner import validate_owner_request,gui_runtime
    from yuntapr.training.phase_b_v2_seed2027_b1_e1_epoch6_recovery_v2.protocol import BOOTSTRAP_PATH,session_root,atomic_json,verify_release,LIMITS,CAMPAIGN
    from yuntapr.training.phase_b_v2_seed2027_b1_e1_epoch6_recovery_v2.console import isolate
    isolation=isolate();request=validate_owner_request(n,nonce);release=verify_release();runtime=gui_runtime(release);folder=session_root(n)
    sys.stdout=(folder/'gui_stdout.txt').open('x',encoding='utf-8',buffering=1)
    sys.stderr=(folder/'gui_stderr.txt').open('x',encoding='utf-8',buffering=1)
    from yuntapr.experimental.phase_b_v2_execution_watchdog_candidate.winjob import K,native_identity,exited,code,memory
    from ctypes import wintypes as W
    K.GetCurrentProcess.restype=W.HANDLE;actual=native_identity(K.GetCurrentProcess())
    if actual['image_path_key'] not in {v['image_path_key'] for v in runtime['binaries'].values()}:raise PermissionError('GUI_BOOTSTRAP_NATIVE_EXECUTABLE_FAMILY')
    from yuntapr.training.phase_b_v2_seed2027_b1_e1_epoch6_recovery_v2.supervisor import FormalJob
    from yuntapr.training.phase_b_v2_seed2027_b1_e1_epoch6_recovery_v2.resources import host_admission
    from yuntapr.training.phase_b_v2_seed2027_b1_e1_epoch6_recovery_v2.quota import carry
    import time
    name=f'Local\\{CAMPAIGN}__GUI__{n}__{nonce}'
    job=FormalJob(name);start=time.monotonic()-carry()['elapsed_seconds'];clean=False;result=1;failure=None
    atomic_json(folder/'gui_bootstrap_identity.json',dict(**actual,nonce=nonce,session=n,campaign=CAMPAIGN,job_name=name,console_isolation=isolation))
    os.environ.update(PYTHONPATH=BOOTSTRAP_PATH,PYTHONUTF8='1',PYTHONHASHSEED='2026',CUBLAS_WORKSPACE_CONFIG=':4096:8',YUNTAPR_REPLICATION_SEED='2027')
    entry=ROOT/'recovery_overlay/yuntapr/training/phase_b_v2_seed2027_b1_e1_epoch6_recovery_v2/task_entry.py'
    try:
        job.spawn([request['interpreter'],'-B',str(entry),str(n),nonce],ROOT)
        while not exited(job.root):
            job.snapshot();host_admission()
            if time.monotonic()-start>LIMITS['max_seconds']:raise TimeoutError('FIXED_SEVEN_DAY_GUI_OWNER_LIMIT')
            for h in job.handles.values():
                if h and not exited(h):
                    m=memory(h)
                    if m['working_set_bytes']>LIMITS['max_working_set_bytes'] or m['private_commit_bytes']>LIMITS['max_process_commit_bytes']:raise MemoryError('GUI_EXTERNAL_PROCESS_RESOURCE_LIMIT')
            time.sleep(1)
        result=code(job.root)
    except BaseException as exc:
        import traceback
        (folder/'gui_failure_private.txt').write_text(traceback.format_exc(),encoding='utf-8',newline='\n')
        failure=dict(type=type(exc).__name__,winerror=getattr(exc,'winerror',None))
    finally:
        job.stop();deadline=time.monotonic()+10
        while time.monotonic()<deadline:
            if not job.pids() and all(exited(h) for h in job.handles.values()):clean=True;break
            time.sleep(.05)
        job.close();atomic_json(folder/'gui_termination.json',dict(campaign=CAMPAIGN,session=n,nonce=nonce,supervisor_exit_code=result,job_empty_and_handles_signaled=clean,failure=failure,automatic_retries=0,refunds=0))
        if result!=0 or not clean:
            from yuntapr.training.phase_b_v2_seed2027_b1_e1_epoch6_recovery_v2.quota import Ledger
            ledger=Ledger()
            try:ledger.fail('GUI_OWNER_FAILED_NO_RETRY')
            finally:ledger.close()
    return 0 if result==0 and clean else 1

if __name__=='__main__':
    try:result=main()
    except BaseException:
        import traceback
        try:
            from yuntapr.training.phase_b_v2_seed2027_b1_e1_epoch6_recovery_v2.protocol import BOOTSTRAP_PATH,session_root,atomic_json,owned_json
            from yuntapr.training.phase_b_v2_seed2027_b1_e1_epoch6_recovery_v2.task_owner import task_name
            n=int(sys.argv[1]);nonce=sys.argv[2];task_name(n,nonce);folder=session_root(n);request=owned_json(folder/'task_request.json')
            if request['nonce']!=nonce:raise PermissionError('GUI_FAILURE_SCOPE')
            with (folder/'gui_bootstrap_failure_private.txt').open('x',encoding='utf-8') as f:f.write(traceback.format_exc());f.flush();os.fsync(f.fileno())
            atomic_json(folder/'gui_failure.json',dict(status='FAILED_NO_RETRY',session=n,nonce=nonce))
        except Exception:pass
        result=1
    raise SystemExit(result)
