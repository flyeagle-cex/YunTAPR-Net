"""Single contained worker. Native registration precedes scientific imports."""
from __future__ import annotations
import json
import os
import sys
import traceback
from ctypes import wintypes as W
from .protocol import LOCAL,OUT,CAMPAIGN,verify_release,atomic_json
from yuntapr.experimental.phase_b_v2_execution_watchdog_candidate.winjob import K,native_identity
K.GetCurrentProcess.restype=W.HANDLE

def main() -> int:
    if len(sys.argv)!=2 or len(sys.argv[1])!=32:raise PermissionError('ONLY_OWNER_NONCE_WORKER_LAUNCH')
    nonce=sys.argv[1]
    atomic_json(LOCAL/'worker_identity.json',dict(**native_identity(K.GetCurrentProcess()),nonce=nonce,campaign=CAMPAIGN))
    # Approval is the direct researcher instruction pinned in the release, not
    # a boolean/CLI switch upgrading any previous always-deny candidate.
    from .resources import Budget,host_admission,utcnow
    from .quota import Ledger
    from .data import Plan,Adapter
    from .engine import Engine,boundary_flags
    from .ancestor import Guard
    from .dependencies import verify as verify_dependencies
    budget=ledger=adapter=ancestor_guard=None
    try:
        release=verify_release();host=host_admission()
        # Retain no-write/no-delete native handles through the entire campaign.
        # Old attempts stay zero; the new independent cap is not an extra grant.
        ancestor_guard=Guard(release['old_ancestor_receipt_sha256'])
        ledger=Ledger(release);budget=Budget();cuda=budget.cuda_admission()
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
        atomic_json(LOCAL/'preflight.json',dict(status='PASS',host=host,cuda=cuda,metadata=metadata,
            data_identity=plan.identity,first_step_not_yet_called=True,release=release))
        atomic_json(OUT/'execution_status.json',dict(status='RUNNING',current_run='B0_MATCHED_V2__E0__s2026',
            phase='FULL_DATA_PREFLIGHT_PASS',quota=ledger.snapshot(),updated_utc=utcnow(),**boundary_flags()))
        engine=Engine(adapter,budget,ledger,release);result=engine.run()
        if verify_release()!=release:raise ValueError('SOURCE_RELEASE_CHANGED_DURING_TRAINING')
        final=dict(status='SIX_RUNS_COMPLETE',runs=[r['run_id'] for r in result],quota=ledger.snapshot(),
            finished_utc=utcnow(),actual_content_bytes=budget.bytes,elapsed_seconds=__import__('time').monotonic()-budget.start,
            cuda_peak_allocated_bytes=budget.cuda_peak_allocated,cuda_peak_reserved_bytes=budget.cuda_peak_reserved,**boundary_flags())
        atomic_json(OUT/'execution_status.json',final)
        atomic_json(LOCAL/'complete.json',dict(nonce=nonce,campaign=CAMPAIGN,status='SIX_RUNS_COMPLETE'))
        return 0
    except BaseException as exc:
        (LOCAL/'failure_private.txt').write_text(traceback.format_exc(),encoding='utf-8',newline='\n')
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
