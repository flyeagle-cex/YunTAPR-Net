"""Fixed ASCII task bootstrap; no dependence on Codex terminal environment."""
from pathlib import Path
import os,sys

def main() -> int:
    if len(sys.argv)!=3:raise PermissionError('FIXED_SYSTEM_TASK_ARGUMENTS')
    n=int(sys.argv[1]);nonce=sys.argv[2]
    if os.environ.get('PYTHONHASHSEED')!='2026':raise PermissionError('HASH_SEED_MUST_BE_SET_BEFORE_PYTHON_START')
    root=Path(__file__).absolute().parents[4]
    os.environ.update(PYTHONPATH=str(root/'src'),PYTHONUTF8='1',PYTHONHASHSEED='2026',
        CUBLAS_WORKSPACE_CONFIG=':4096:8',YUNTAPR_REPLICATION_SEED='2027')
    sys.path.insert(0,str(root/'src'));os.chdir(root)
    from yuntapr.training.phase_b_v2_seed2027_b1_epoch7_recovery_v2.task_owner import validate_owner_request
    from yuntapr.training.phase_b_v2_seed2027_b1_epoch7_recovery_v2.protocol import session_root,atomic_json
    request=validate_owner_request(n,nonce)
    folder=session_root(n)
    sys.stdout=(folder/'supervisor_stdout.txt').open('x',encoding='utf-8',buffering=1)
    sys.stderr=(folder/'supervisor_stderr.txt').open('x',encoding='utf-8',buffering=1)
    from ctypes import wintypes as W
    from yuntapr.experimental.phase_b_v2_execution_watchdog_candidate.winjob import K,native_identity
    from yuntapr.experimental.phase_b_v2_owner_lifetime_candidate.context import current_job_profile
    K.GetCurrentProcess.restype=W.HANDLE
    atomic_json(folder/'task_owner_started.json',dict(**native_identity(K.GetCurrentProcess()),
        task_name=request['task_name'],nonce=nonce,session=n,job_profile=current_job_profile()))
    os.environ['YUNTAPR_SYSTEM_TASK_OWNER_NONCE']=nonce
    sys.argv=[sys.argv[0],str(n)]
    from yuntapr.training.phase_b_v2_seed2027_b1_epoch7_recovery_v2.supervisor import main as supervise
    return supervise()

if __name__=='__main__':raise SystemExit(main())
