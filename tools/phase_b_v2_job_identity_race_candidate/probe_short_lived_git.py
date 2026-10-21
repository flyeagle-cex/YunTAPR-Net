"""Two bounded artificial jobs, at most 40 Git metadata subprocesses each."""
from pathlib import Path
from unittest.mock import patch
import ctypes as C
from ctypes import wintypes as W
import json,sys,time
ROOT=Path(__file__).absolute().parents[2];sys.path.insert(0,str(ROOT/'src'))
from yuntapr.experimental.phase_b_v2_execution_watchdog_candidate import winjob as original
from yuntapr.experimental.phase_b_v2_job_identity_race_candidate import job as candidate
REAL_IDENTITY=original.native_identity
REAL_QUERY=original.query_job

def run(label,cls):
    errors=[];failure=None;job=cls();started=time.monotonic();samples=0;clean=False;counts={}
    runtime=json.loads((ROOT/'docs/phase_b_v2_formal_execution/seed2027_b1_epoch7_recovery_v6/.local/runtime.json').read_text(encoding='utf-8'))
    code="import subprocess\nfor _ in range(40): subprocess.run(['F:/git/Git/cmd/git.exe','rev-parse','HEAD'],check=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)\n"
    def traced(handle):
        try:return REAL_IDENTITY(handle)
        except OSError as exc:
            try:signaled=original.exited(handle)
            except OSError:signaled='UNKNOWN'
            errors.append(dict(pid=original.process_id(handle),winerror=exc.winerror,held_handle_signaled=signaled))
            raise
    def traced_query(handle,kind,buf,size,returned):
        ok=REAL_QUERY(handle,kind,buf,size,returned)
        if kind==3 and ok:
            entry=C.cast(buf,C.POINTER(original.Pids)).contents
            key=(int(entry.assigned),int(entry.count))
            counts[key]=counts.get(key,0)+1
        return ok
    try:
        with patch.object(original,'native_identity',side_effect=traced),patch.object(candidate,'native_identity',side_effect=traced),patch.object(original,'query_job',side_effect=traced_query),patch.object(candidate,'query_job',side_effect=traced_query):
            job.spawn([runtime['python'],'-c',code],ROOT)
            while not original.exited(job.root):
                if time.monotonic()-started>10:raise TimeoutError('BOUNDED_ARTIFICIAL_GIT_PROBE')
                samples+=1;job.snapshot();time.sleep(.001)
    except Exception as exc:
        failure=dict(type=type(exc).__name__,winerror=getattr(exc,'winerror',None),reason=str(exc))
    finally:
        job.stop();deadline=time.monotonic()+3
        while time.monotonic()<deadline:
            if not job.pids() and all(original.exited(h) for h in job.handles.values()):clean=True;break
            time.sleep(.01)
        receipts=getattr(job,'identity_exit_receipts',[])
        resized=getattr(job,'enumeration_resize_receipts',[]);job.close()
    return dict(case=label,samples=samples,elapsed_seconds=time.monotonic()-started,
                failure=failure,native_identity_errors=errors,verified_exit_receipts=receipts,job_empty=clean,
                enumeration_resize_receipts=resized,
                native_job_counts=[dict(assigned=a,returned=b,samples=n) for (a,b),n in sorted(counts.items())])

if __name__=='__main__':
    result=dict(records=[run('original_job',original.Job),run('held_handle_exit_candidate',candidate.IdentitySafeJob)],
        synthetic_only=True,raw_data_reads=0,optimizer_steps=0,torch_imported='torch' in sys.modules)
    print(json.dumps(result,indent=2))
