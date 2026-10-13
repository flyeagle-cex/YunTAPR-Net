"""Single contained worker. Native registration precedes scientific imports."""
from __future__ import annotations
import json
import os
import sys
import traceback
from ctypes import wintypes as W
from .protocol import LOCAL,OUT,CAMPAIGN,verify_release,atomic_json,session_root
from yuntapr.experimental.phase_b_v2_execution_watchdog_candidate.winjob import K,native_identity
K.GetCurrentProcess.restype=W.HANDLE

def main() -> int:
    if len(sys.argv)!=3 or len(sys.argv[2])!=32:raise PermissionError('ONLY_OWNER_NONCE_WORKER_LAUNCH')
    n=int(sys.argv[1]);os.environ['YUNTAPR_OPERATOR_SESSION']=str(n)
    local=session_root();nonce=sys.argv[2]
    atomic_json(local/'worker_identity.json',dict(**native_identity(K.GetCurrentProcess()),nonce=nonce,campaign=CAMPAIGN))
    # Approval is the direct researcher instruction pinned in the release, not
    # a boolean/CLI switch upgrading any previous always-deny candidate.
    from .resources import Budget,host_admission,utcnow
    from .quota import Ledger,PauseAtBoundary
    from yuntapr.training.phase_b_v2_seed2026_v2.data import Plan,Adapter
    from .engine import Engine,boundary_flags
    from .recovery import Guard
    from yuntapr.training.phase_b_v2_seed2026_v2.dependencies import verify as verify_dependencies
    budget=ledger=adapter=ancestor_guard=None
    try:
        release=verify_release();host=host_admission()
        # Retain no-write/no-delete native handles through the entire campaign.
        # Both stopped campaigns remain immutable; all 186891 attempts stay spent.
        ancestor_guard=Guard(release['ancestor_receipt_sha256'])
        ledger=Ledger();ledger.verify_session(n,nonce);budget=Budget();cuda=budget.cuda_admission()
        dependencies=verify_dependencies(release['dependency_manifest_sha256'])
        budget.emit('ACTUAL_DEPENDENCIES_VERIFIED',**dependencies)
        budget.emit('FORMAL_CAMPAIGN_STARTED',host=host,cuda=cuda,release=release)
        plan=Plan(budget);adapter=Adapter(plan,budget)
        # Hold real directory identities before checking exact registered files.
        adapter.reader.lock_parents();metadata=adapter.reader.full_metadata_gate()
        # initialize_geometry() reuses the original frozen geographic reader.
        # Avoid a second set of directory locks by temporarily reusing held locks.
        from unittest.mock import patch
        with patch.object(adapter.reader,'lock_parents',lambda:None):adapter.initialize_geometry()
        atomic_json(local/'preflight.json',dict(status='PASS',host=host,cuda=cuda,metadata=metadata,
            data_identity=plan.identity,first_step_not_yet_called=True,release=release))
        current=next(r['id'] for r in ledger.snapshot()['runs'] if r['status']!='COMPLETE')
        atomic_json(OUT/'execution_status.json',dict(status='RUNNING',current_run=current,
            phase='FULL_DATA_PREFLIGHT_PASS',quota=ledger.snapshot(),updated_utc=utcnow(),**boundary_flags()))
        engine=Engine(adapter,budget,ledger,release);result=engine.run()
        if verify_release()!=release:raise ValueError('SOURCE_RELEASE_CHANGED_DURING_TRAINING')
        final=dict(status='SIX_RUNS_COMPLETE',runs=[r['run_id'] for r in result],quota=ledger.snapshot(),
            finished_utc=utcnow(),actual_content_bytes=budget.bytes,elapsed_seconds=__import__('time').monotonic()-budget.start,
            cuda_peak_allocated_bytes=budget.cuda_peak_allocated,cuda_peak_reserved_bytes=budget.cuda_peak_reserved,**boundary_flags())
        atomic_json(OUT/'execution_status.json',final)
        atomic_json(local/'complete.json',dict(nonce=nonce,campaign=CAMPAIGN,status='SIX_RUNS_COMPLETE'))
        return 0
    except PauseAtBoundary:
        import time
        resources=dict(elapsed_seconds=time.monotonic()-budget.start,content_bytes=budget.bytes)
        row=ledger.pause_boundary(n,nonce,resources)
        atomic_json(local/'paused.json',row)
        atomic_json(OUT/'execution_status.json',dict(status='PAUSED',session=n,quota=ledger.snapshot(),updated_utc=utcnow(),**boundary_flags()))
        budget.emit('SAFE_PAUSE_COMPLETE',**row)
        return 0
    except BaseException as exc:
        (local/'failure_private.txt').write_text(traceback.format_exc(),encoding='utf-8',newline='\n')
        reason=str(exc) if str(exc).replace('_','').isalnum() and '/' not in str(exc) and '\\' not in str(exc) else type(exc).__name__
        if ledger is not None:ledger.fail(reason)
        status=dict(status='STOPPED_NO_RETRY',error_type=type(exc).__name__,error_code=reason,
            quota=ledger.snapshot() if ledger else None,failed_utc=utcnow(),**boundary_flags())
        atomic_json(OUT/'execution_status.json',status)
        if budget is not None:budget.emit('FAILED',**status)
        return 1
    finally:
        if adapter is not None:adapter.reader.close()
        if budget is not None:budget.close()
        if ledger is not None:ledger.close()
        if ancestor_guard is not None:ancestor_guard.close()

if __name__=='__main__':raise SystemExit(main())
