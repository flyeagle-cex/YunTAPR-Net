"""Two tiny owned process trees; no model, GPU, observations or optimizer."""
import ctypes,hashlib,json,os,sys,time
from pathlib import Path
from unittest.mock import patch
import operate
from yuntapr.experimental.phase_b_v2_execution_watchdog_candidate import winjob as w
from yuntapr.experimental.phase_b_v2_job_identity_race_candidate import job as j
from yuntapr.training.phase_b_v2_seed2027_b1_e1_epoch6_recovery_v2 import protocol as p

REAL=j.native_identity
CONHOST=hashlib.sha256(os.path.normcase(os.environ['WINDIR']+'/System32/conhost.exe').encode()).hexdigest()

def probe(use_fix):
    # The root has no console, exactly as the formal worker does.
    code="import sys,subprocess,time\nfrom pathlib import Path\n"
    code+="sys.dont_write_bytecode=True;sys.path.insert(0,"+repr(str(p.ROOT/'tools/seed2027_b1_e1_epoch6_recovery_v2'))+")\nimport operate\n"
    code+="from yuntapr.training.phase_b_v2_seed2027_b1_e1_epoch6_recovery_v2.metadata_process import no_console_git\nfrom contextlib import nullcontext\n"
    code+="with "+('no_console_git()' if use_fix else 'nullcontext()')+":\n for _ in range(16):\n  subprocess.check_output(['git','rev-parse','HEAD'],cwd="+repr(str(p.LIVE_ROOT))+",stderr=subprocess.DEVNULL)\n  time.sleep(.003)\n"
    errors=[];images=set();failure=None;job=j.IdentitySafeJob();start=time.monotonic();samples=0;clean=False
    def traced(h):
        try:
            identity=REAL(h);images.add(identity['image_path_key']);return identity
        except OSError as exc:
            errors.append(dict(winerror=exc.winerror,pid=w.process_id(h),same_handle_signaled=w.exited(h)));raise
    try:
        with patch.object(j,'native_identity',side_effect=traced):
            gui=p.owned_json(p.LOCAL/'gui_runtime.json')
            job.spawn([gui['wrapper_path'],'-B','-c',code],p.ROOT)
            while not w.exited(job.root):
                if time.monotonic()-start>12:raise TimeoutError('BOUNDED_ARTIFICIAL_METADATA_PROBE')
                job.snapshot();samples+=1;time.sleep(.001)
            exit_code=w.code(job.root)
            if exit_code:raise RuntimeError('ARTIFICIAL_CHILD_FAILED_'+str(exit_code))
    except Exception as exc:failure=dict(type=type(exc).__name__,winerror=getattr(exc,'winerror',None))
    finally:
        job.stop();deadline=time.monotonic()+3
        while time.monotonic()<deadline:
            if not job.pids() and all(w.exited(h) for h in job.handles.values()):clean=True;break
            time.sleep(.01)
        job.close()
    return dict(with_no_window=use_fix,samples=samples,elapsed_seconds=time.monotonic()-start,
        conhost_seen=CONHOST in images,native_errors=errors,failure=failure,owned_job_empty=clean)

if __name__=='__main__':
    rows=[probe(False),probe(True)]
    result=dict(synthetic_only=True,raw_data_reads=0,optimizer_steps=0,torch_imported='torch' in sys.modules,records=rows)
    p.atomic_json(p.OUT/'CONSOLE_GIT_NATIVE_PROBE.json',result)
    print(json.dumps(result))
    if rows[1]['failure'] or rows[1]['conhost_seen'] or not all(r['owned_job_empty'] for r in rows):raise SystemExit(1)
