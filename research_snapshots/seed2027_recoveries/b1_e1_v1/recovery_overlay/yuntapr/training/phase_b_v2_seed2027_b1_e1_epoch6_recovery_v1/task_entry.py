"""Fixed ASCII task bootstrap; no dependence on Codex terminal environment."""
from pathlib import Path
import os,sys

def main() -> int:
    if len(sys.argv)!=3:raise PermissionError('FIXED_SYSTEM_TASK_ARGUMENTS')
    n=int(sys.argv[1]);nonce=sys.argv[2]
    if os.environ.get('PYTHONHASHSEED')!='2026':raise PermissionError('HASH_SEED_MUST_BE_SET_BEFORE_PYTHON_START')
    root=Path(__file__).absolute().parents[4]
    os.environ.update(PYTHONPATH=os.pathsep.join([str(root/'tools/seed2027_b1_e1_epoch6_recovery/bootstrap'),str(root.parent/'YunTAPR-Net-push-chunks'/'src')]),PYTHONUTF8='1',PYTHONHASHSEED='2026',
        CUBLAS_WORKSPACE_CONFIG=':4096:8',YUNTAPR_REPLICATION_SEED='2027')
    sys.dont_write_bytecode=True;sys.path.insert(0,str(root.parent/'YunTAPR-Net-push-chunks'/'src'));os.chdir(root)
    import yuntapr.training
    yuntapr.training.__path__.append(str(root.parent/'YunTAPR-Net-completed-review-20261021/recovery_overlay/yuntapr/training'))
    yuntapr.training.__path__.append(str(root/'recovery_overlay/yuntapr/training'))
    from yuntapr.training.phase_b_v2_seed2027_b1_e1_epoch6_recovery_v1.console import isolate
    isolation=isolate()
    from yuntapr.training.phase_b_v2_seed2027_b1_e1_epoch6_recovery_v1.task_owner import validate_owner_request
    from yuntapr.training.phase_b_v2_seed2027_b1_e1_epoch6_recovery_v1.protocol import session_root,atomic_json
    request=validate_owner_request(n,nonce)
    from yuntapr.training.phase_b_v2_seed2027_b1_e1_epoch6_recovery_v1.task_owner import validate_gui_parent
    validate_gui_parent(n,nonce)
    folder=session_root(n)
    sys.stdout=(folder/'supervisor_stdout.txt').open('x',encoding='utf-8',buffering=1)
    sys.stderr=(folder/'supervisor_stderr.txt').open('x',encoding='utf-8',buffering=1)
    from ctypes import wintypes as W
    from yuntapr.experimental.phase_b_v2_execution_watchdog_candidate.winjob import K,native_identity
    from yuntapr.experimental.phase_b_v2_owner_lifetime_candidate.context import current_job_profile
    K.GetCurrentProcess.restype=W.HANDLE
    atomic_json(folder/'task_owner_started.json',dict(**native_identity(K.GetCurrentProcess()),
        task_name=request['task_name'],nonce=nonce,session=n,job_profile=current_job_profile(),console_isolation=isolation))
    os.environ['YUNTAPR_SYSTEM_TASK_OWNER_NONCE']=nonce
    sys.argv=[sys.argv[0],str(n)]
    from yuntapr.training.phase_b_v2_seed2027_b1_e1_epoch6_recovery_v1.supervisor import main as supervise
    return supervise()

if __name__=='__main__':
    original_args=tuple(sys.argv[1:])
    try:result=main()
    except Exception as exc:
        # Early bootstrap failures must not disappear before the monitor exists.
        import traceback
        try:
            n=int(original_args[0]);nonce=original_args[1]
            from yuntapr.training.phase_b_v2_seed2027_b1_e1_epoch6_recovery_v1.task_owner import task_name
            from yuntapr.training.phase_b_v2_seed2027_b1_e1_epoch6_recovery_v1.protocol import session_root,owned_json,atomic_json,CAMPAIGN
            task_name(n,nonce);folder=session_root(n);request=owned_json(folder/'task_request.json')
            if request['nonce']!=nonce or request['campaign']!=CAMPAIGN or request['session']!=n:raise PermissionError('BOOTSTRAP_FAILURE_SCOPE')
            with (folder/'task_failure_private.txt').open('x',encoding='utf-8') as f:f.write(traceback.format_exc());f.flush();os.fsync(f.fileno())
            atomic_json(folder/'task_failure.json',dict(type=type(exc).__name__,winerror=getattr(exc,'winerror',None),session=n,nonce=nonce))
        except Exception:traceback.print_exc()
        raise
    raise SystemExit(result)
