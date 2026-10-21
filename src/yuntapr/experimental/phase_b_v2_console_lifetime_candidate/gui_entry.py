"""Fixed GUI task action: artificially exercise a console-free owner/worker.

No command/module selection and no formal runner import. This is a candidate
test bootstrap, not an execution grant. pythonw is only the GUI bootstrap;
the owner uses the unchanged published console interpreter, CREATE_NO_WINDOW.
"""
from pathlib import Path
import os, sys

ROOT = Path(__file__).absolute().parents[4]
sys.path.insert(0, str(ROOT / 'src'))


def main() -> int:
    if len(sys.argv) != 3:
        raise PermissionError('FIXED_ARTIFICIAL_GUI_ARGS')
    folder, nonce = Path(sys.argv[1]), sys.argv[2]
    from yuntapr.experimental.phase_b_v2_console_lifetime_candidate.task_bridge import (
        validate_scope, load, save, fixed_spec)
    validate_scope(folder, nonce)
    spec = fixed_spec(folder, nonce)
    if load(folder / 'request.json') != spec:
        raise PermissionError('EXACT_ARTIFICIAL_GUI_REQUEST')
    # stderr/stdout are None in a GUI interpreter. Bind logs before execution.
    sys.stdout = (folder / 'gui_stdout.txt').open('x', encoding='utf-8', buffering=1)
    sys.stderr = (folder / 'gui_stderr.txt').open('x', encoding='utf-8', buffering=1)
    from yuntapr.experimental.phase_b_v2_console_lifetime_candidate.native_console import require_no_console
    from yuntapr.experimental.phase_b_v2_execution_watchdog_candidate.winjob import (
        Job, K, bind, native_identity, exited, code)
    from ctypes import wintypes as W
    import time
    current = bind(K, 'GetCurrentProcess', [], W.HANDLE)
    save(folder, 'gui.json', dict(**native_identity(current()), nonce=nonce,
         console=require_no_console(), synthetic_only=True))
    # Crucially this environment is fixed BEFORE the scientific interpreter
    # starts. The GUI bootstrap itself never instantiates any scientific code.
    os.environ.update(PYTHONHASHSEED='2026', PYTHONUTF8='1',
        PYTHONPATH=str(ROOT / 'src'), CUBLAS_WORKSPACE_CONFIG=':4096:8',
        YUNTAPR_REPLICATION_SEED='2027')
    job = Job()
    result = 1
    try:
        job.spawn([spec['python'], '-m',
            'yuntapr.experimental.phase_b_v2_console_lifetime_candidate.fixture',
            'owner', str(folder), nonce], ROOT)
        deadline = time.monotonic() + 12
        while not exited(job.root):
            if time.monotonic() >= deadline:
                raise TimeoutError('ARTIFICIAL_GUI_OWNER_DEADLINE')
            job.snapshot()
            time.sleep(.02)
        result = code(job.root)
    finally:
        job.stop()
        deadline = time.monotonic() + 2
        while (job.pids() or any(not exited(h) for h in job.handles.values())) and time.monotonic() < deadline:
            time.sleep(.01)
        empty = not job.pids() and all(exited(h) for h in job.handles.values())
        job.close()
        save(folder, 'gui_termination.json', dict(job_empty=empty, owner_exit_code=result,
             optimizer_steps=0, torch_imported='torch' in sys.modules))
    return result


if __name__ == '__main__':
    try:
        result = main()
    except Exception:
        import traceback
        # If request validation failed before logs could be opened, do not
        # create arbitrary paths. An absent receipt is a failure, never PASS.
        if sys.stderr is not None:
            traceback.print_exc()
        result = 1
    raise SystemExit(result)
