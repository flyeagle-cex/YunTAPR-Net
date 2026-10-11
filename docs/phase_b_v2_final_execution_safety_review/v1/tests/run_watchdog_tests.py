"""Finite isolated process suite. Persisted budget allows at most 40 launches.

No model, data, GPU or old smoke imports. All local fixtures stay in .local.
"""
import json
import os
from pathlib import Path
import sqlite3
import sys
import time
import uuid

ROOT = Path(__file__).absolute().parents[4]
sys.path.insert(0, str(ROOT/'src'))
from yuntapr.experimental.phase_b_v2_execution_watchdog_candidate.watchdog import CASES, run_case, persist
from yuntapr.experimental.phase_b_v2_execution_watchdog_candidate import start_formal

OUT = ROOT/'docs/phase_b_v2_final_execution_safety_review/v1'


def main():
    local = OUT/'.local'; local.mkdir(exist_ok=True)
    con = sqlite3.connect(local/'synthetic_launch_budget.sqlite')
    con.execute('PRAGMA synchronous=FULL')
    con.execute('CREATE TABLE IF NOT EXISTS launches(id INTEGER PRIMARY KEY, case_name TEXT, utc REAL)')
    run = 'run_'+uuid.uuid4().hex[:12]; run_dir = local/run; run_dir.mkdir()
    results = []; started = time.monotonic()
    for case in CASES:
        with con:
            if con.execute('SELECT COUNT(*) FROM launches').fetchone()[0] >= 40:
                raise PermissionError('Artificial process launch budget exhausted; no reset')
            con.execute('INSERT INTO launches(case_name,utc) VALUES(?,?)', (case, time.time()))
        r = run_case(case, run_dir/case)
        positive = case in {'success', 'wrapper_exit'}
        passed = r['cleanup_verified'] and (r['violation'] is None if positive else r['violation'] is not None)
        if case == 'wrapper_exit': passed &= r['root_exited_during_monitor'] and r['worker_identity']['pid'] != r['root_pid']
        if case == 'memory': passed &= r['violation']=='CPU_WORKING_SET_LIMIT' and r.get('allocation',{}).get('controlled_allocation_bytes')==32*1024**2
        if case == 'tree_timeout': passed &= r['violation']=='ELAPSED_TIME_LIMIT' and len(r['observed_process_identities']) >= 3
        if case == 'close_job': passed &= r['kill_on_close_test'] and len(r['member_pids_before_close'])>=2
        if case in {'unexpected_exit', 'worker_exit_tree'}: passed &= r['violation']=='WORKER_UNEXPECTED_EXIT'
        if case == 'before_registration': passed &= r['violation']=='EXIT_BEFORE_IDENTITY'
        if case == 'no_registration': passed &= r['violation']=='REGISTRATION_TIMEOUT'
        if case == 'foreign_pid': passed &= os.getpid() not in [x['pid'] for x in r['observed_process_identities']]
        passed &= r['elapsed_seconds']<15 and r['restarts']==0
        r['test_status'] = 'PASS' if passed else 'FAIL'; results.append(r)
        print(case, r['test_status'], r['violation'], round(r['elapsed_seconds'],3), flush=True)
        # Stop the suite on unresolved termination failure. Never leave an orphan.
        if not r['cleanup_verified']: break
    denied = 0
    for fake in ({'APPROVED':True}, {'authorized':True}, {'git_commit':'approved'}):
        try: start_formal(**fake)
        except PermissionError: denied += 1
    result = dict(run=run, tests=len(results)+3,
                  passed=sum(x['test_status']=='PASS' for x in results)+denied,
                  failed=sum(x['test_status']=='FAIL' for x in results)+3-denied,
                  launch_budget_reserved_total=con.execute('SELECT COUNT(*) FROM launches').fetchone()[0],
                  launch_hard_limit=40, scope='SYNTHETIC_ENGINEERING_ONLY',
                  maximum_case_seconds=15, maximum_controlled_allocation_bytes=64*1024**2,
                  elapsed_seconds=time.monotonic()-started, results=results,
                  science_or_gpu_imports_present=[k for k in sys.modules if k.split('.')[0] in {'torch','numpy','netCDF4','h5py','cupy'}])
    con.close(); persist(OUT/'tests'/f'{run}.json',result)
    print(json.dumps({k:v for k,v in result.items() if k!='results'}))
    if result['failed'] or len(results)!=len(CASES): raise SystemExit(1)


if __name__=='__main__': main()
