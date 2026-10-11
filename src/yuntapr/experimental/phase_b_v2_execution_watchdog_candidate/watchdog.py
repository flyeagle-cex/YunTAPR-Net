"""Closed artificial-process campaign; cannot launch a model or real-data runner."""
from __future__ import annotations
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import secrets
import sys
import time
from . import SCOPE
from .winjob import Job, checked, code, exited, memory, native_identity, close_handle

CASES = ('success', 'wrapper_exit', 'before_registration', 'unexpected_exit', 'memory',
         'tree_timeout', 'foreign_pid', 'missing_pid', 'bad_creation', 'bad_image',
         'bad_nonce', 'bad_campaign', 'no_registration', 'worker_exit_tree',
         'invalid_handle', 'close_job', 'driver_crash')
MAX_CASE_SECONDS = 15
MAX_CONTROLLED_ALLOCATION = 64*1024**2
LOCAL = Path(__file__).absolute().parents[4]/'docs/phase_b_v2_final_execution_safety_review/v1/.local'


def persist(path: Path, data: dict):
    """Exclusive durable receipts; never overwrite an earlier failure/run."""
    with path.open('x', encoding='utf-8', newline='\n') as stream:
        stream.write(json.dumps(data, indent=2, allow_nan=False)+'\n')
        stream.flush(); os.fsync(stream.fileno())


def interpreter_keys() -> set[str]:
    """Exact native executable family from this venv, not worker self-report."""
    paths = {os.path.normcase(sys.executable), os.path.normcase(sys._base_executable)}
    cfg = Path(sys.executable).parent.parent/'pyvenv.cfg'
    if cfg.exists():
        for line in cfg.read_text(encoding='utf-8').splitlines():
            if line.startswith('home = '): paths.add(os.path.normcase(str(Path(line[7:])/'python.exe')))
    return {hashlib.sha256(p.encode('utf-8')).hexdigest() for p in paths}


def run_case(case: str, folder: Path) -> dict:
    """One artificial launch, fixed code path, no retry and no optimizer capability.

    Resource/handle faults are closed enumeration values for synthetic testing;
    they cannot enable formal input. A worker receipt is not human approval.
    """
    if case not in CASES: raise ValueError('Unknown artificial case')
    if not isinstance(folder, Path): raise TypeError('Owned Path required')
    # Lexical checks only, before mkdir/stat/resolve/open of a supplied path.
    raw = str(folder).replace('\\','/')
    if ('2025' in raw or '..' in raw.split('/') or not folder.is_absolute()
            or folder == LOCAL or not folder.is_relative_to(LOCAL)):
        raise PermissionError('Only new owned artificial scratch directories')
    folder.mkdir(exist_ok=False)
    nonce = secrets.token_hex(16); allowed_images = interpreter_keys()
    job = Job(); started = time.monotonic(); worker = None; violation = None
    peak_ws = peak_private = peak_tree_ws = 0; seen_root_exit = False
    mode = 'success' if case == 'wrapper_exit' else case
    wrapper = case in {'wrapper_exit', 'tree_timeout'}
    argv = [sys.executable, str(Path(__file__).with_name('fixture.py')), str(folder),
            'wrapper' if wrapper else mode, nonce, str(os.getpid())]
    if wrapper: argv.append(mode)
    samples = []; worker_ident = None; root_pid = None; cleanup = False; all_exited = False
    err = None; killed_by_close = False; close_job_pids = []; child_dead_before_outer_stop = None
    try:
        root_pid = job.spawn(argv, Path(__file__).absolute().parents[4])
        deadline = 1.8 if case in {'tree_timeout', 'close_job'} else 4
        while True:
            if time.monotonic()-started >= MAX_CASE_SECONDS: raise TimeoutError('CASE_HARD_LIMIT')
            pids = job.snapshot()
            seen_root_exit |= exited(job.root)
            if worker is None and (folder/'identity.json').exists():
                row = json.loads((folder/'identity.json').read_text(encoding='utf-8'))
                if (row.get('nonce') != nonce or row.get('campaign') != 'ARTIFICIAL_WATCHDOG_V1'
                        or row.get('no_science_imports') is not True):
                    raise ValueError('REGISTRATION_SCOPE_MISMATCH')
                worker = job.bind(row['pid']); worker_ident = job.identities[row['pid']]
                if any(row.get(k) != worker_ident[k] for k in worker_ident):
                    raise ValueError('CREATION_OR_IMAGE_MISMATCH')
                if worker_ident['image_path_key'] not in allowed_images:
                    raise ValueError('EXECUTABLE_FAMILY_MISMATCH')
            tree_ws = 0
            for pid in pids:
                h = job.handles.get(pid)
                if h and not exited(h): tree_ws += memory(h)['working_set_bytes']
            peak_tree_ws = max(peak_tree_ws, tree_ws)
            if worker is not None:
                if case == 'invalid_handle':
                    close_handle(worker); job.handles[worker_ident['pid']] = None; worker = None
                    # A closed monitor handle is a failure, never a fallback PID kill.
                    memory(None)
                if not exited(worker):
                    m = memory(worker); peak_ws = max(peak_ws, m['peak_working_set_bytes'])
                    peak_private = max(peak_private, m['private_commit_bytes'])
                    samples.append(dict(elapsed=round(time.monotonic()-started, 4), **m))
                    if case == 'memory' and m['working_set_bytes'] > 24*1024**2:
                        violation = 'CPU_WORKING_SET_LIMIT'; break
                elif code(worker) != 0:
                    if case == 'driver_crash':
                        leaf = json.loads((folder/'leaf.json').read_text(encoding='utf-8'))
                        # Independently retain the inner-job member from outer containment.
                        h = job.handles.get(leaf['pid'])
                        until = time.monotonic()+1
                        while h and not exited(h) and time.monotonic()<until: time.sleep(.01)
                        child_dead_before_outer_stop = bool(h and exited(h))
                    violation = 'WORKER_UNEXPECTED_EXIT'; break
                elif not (folder/'complete.json').exists():
                    violation = 'WORKER_MISSING_COMPLETION_RECEIPT'; break
            if not pids:
                if worker is None: violation = 'EXIT_BEFORE_IDENTITY'
                elif code(worker) != 0: violation = 'WORKER_UNEXPECTED_EXIT'
                else:
                    receipt = json.loads((folder/'complete.json').read_text(encoding='utf-8'))
                    if receipt != dict(nonce=nonce, status='SYNTHETIC_COMPLETE'):
                        violation = 'COMPLETION_IDENTITY_MISMATCH'
                break
            if worker is None and time.monotonic()-started > 2:
                violation = 'REGISTRATION_TIMEOUT'; break
            if case == 'close_job' and (folder/'leaf.json').exists():
                close_job_pids = job.snapshot()
                close_handle(job.handle); job.handle = None; killed_by_close = True
                violation = 'SIMULATED_MONITOR_LOSS_KILL_ON_CLOSE'; break
            if time.monotonic()-started >= deadline:
                violation = 'ELAPSED_TIME_LIMIT'; break
            time.sleep(.02)
    except (OSError, ValueError, KeyError, PermissionError, RuntimeError) as exc:
        violation = 'MONITOR_OR_IDENTITY_FAILURE'; err = type(exc).__name__
    finally:
        identities = list(job.identities.values()); exit_codes = {}
        try:
            if job.handle:
                # Success also cleans an empty job, eliminating late descendant races.
                job.stop()
            end = time.monotonic()+3
            while time.monotonic()<end:
                active = job.pids() if job.handle else []
                all_exited = all(not h or exited(h) for h in job.handles.values())
                if not active and all_exited: cleanup = True; break
                time.sleep(.02)
            exit_codes = {str(pid): code(h) for pid, h in job.handles.items() if h and exited(h)}
        except OSError as exc:
            # Kernel query failure must not skip KILL_ON_JOB_CLOSE cleanup.
            violation = 'CLEANUP_NOT_VERIFIED'; err = type(exc).__name__
        finally:
            job.close()
    result = dict(scope=SCOPE, case=case, utc=datetime.now(timezone.utc).isoformat(),
                  root_pid=root_pid, worker_identity=worker_ident, root_exited_during_monitor=seen_root_exit,
                  observed_process_identities=identities, exit_codes=exit_codes,
                  violation=violation, error_class=err, elapsed_seconds=time.monotonic()-started,
                  peak_worker_working_set_bytes=peak_ws, peak_worker_private_commit_bytes=peak_private,
                  peak_sampled_tree_working_set_bytes=peak_tree_ws, resource_samples=samples,
                  job_empty_after_stop=cleanup if not killed_by_close else None,
                  all_retained_process_handles_signaled=all_exited,
                  cleanup_verified=cleanup, kill_on_close_test=killed_by_close,
                  child_dead_before_outer_job_termination=child_dead_before_outer_stop,
                  member_pids_before_close=close_job_pids, restarts=0,
                  model_imports=0, gpu_operations=0, real_data_reads=0, optimizer_steps=0)
    if (folder/'allocation.json').exists(): result['allocation'] = json.loads((folder/'allocation.json').read_text())
    persist(folder/'watchdog_receipt.json', result)
    return result
