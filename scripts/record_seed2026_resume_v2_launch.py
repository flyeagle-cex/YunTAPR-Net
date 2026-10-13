"""Metadata-only snapshot of the genuinely resumed worker, never a control API."""
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
import sqlite3
ROOT=Path(__file__).absolute().parents[1]
OUT=ROOT/'docs/phase_b_v2_formal_execution/seed2026_resume_v2'

def main():
    release=json.loads((OUT/'release.json').read_bytes())
    preflight=json.loads((OUT/'.local/preflight.json').read_bytes())
    restored=json.loads((OUT/'.local/B1_V2__E1__s2026/recovery_receipt.json').read_bytes())
    bound=json.loads((OUT/'.local/bound_identity.json').read_bytes())
    heartbeat=json.loads((OUT/'.local/heartbeat.json').read_bytes())
    db=ROOT/'.git/phase_b_v2_seed2026_epoch3_recovery_20261013_v2.sqlite'
    with sqlite3.connect(db.as_uri()+'?mode=ro',uri=True) as con:
        con.execute('PRAGMA query_only=ON');con.execute('BEGIN')
        campaign=con.execute('SELECT status FROM campaign').fetchone()[0]
        attempts=dict(con.execute('SELECT status,count(*) FROM attempts GROUP BY status').fetchall())
        first=con.execute('SELECT status FROM attempts WHERE run=? AND update_no=15685',('B1_V2__E1__s2026',)).fetchone()
        run=con.execute('SELECT epoch,updates,last_sha FROM runs WHERE id=?',('B1_V2__E1__s2026',)).fetchone()
        con.rollback()
    if (campaign!='ACTIVE' or first!=('RETURNED_VERIFIED',) or preflight['status']!='PASS'
            or not restored['all_state_verified_before_first_resumed_step'] or not restored['same_bytes_deserialized']):
        raise ValueError('NO_CONFIRMED_LIVE_RECOVERY_SUCCESS')
    ancestor=json.loads((OUT/'ancestor.json').read_bytes())
    intact=all(hashlib.sha256((ROOT/p).read_bytes()).hexdigest()==s for p,s in ancestor['pins'].items())
    if not intact:raise ValueError('IMMUTABLE_ANCESTOR_CHANGED')
    reserved=sum(attempts.values());verified=attempts.get('RETURNED_VERIFIED',0)
    row=dict(status='RECOVERY_REPUBLICATION_AND_FIRST_REAL_UPDATE_PASS_TRAINING_IN_PROGRESS',
        snapshot_utc=datetime.now(timezone.utc).isoformat(),campaign=release['campaign'],source_commit=release['source_commit'],
        source_sha256=release['source_sha256'],old_reserved=162068,failed_v1_reserved=0,
        new_reserved=reserved,new_returned_verified=verified,combined_reserved=162068+reserved,
        combined_returned_verified=162068+verified,unconfirmed=reserved-verified,combined_attempt_cap=287540,
        current_run='B1_V2__E1__s2026',current_epoch=4,complete_epoch=run[0],logical_run_updates=run[1],
        epoch4_returned_updates=run[1]-15684,first_resumed_update_no=15685,
        first_resumed_optimizer_returned_verified=True,restoration=restored,
        complete_remaining_runs=False,old_evidence_sha_unchanged=True,
        worker_native_identity=bound['worker'],preflight_metadata=preflight['metadata'],
        resource_snapshot=heartbeat,resource_hard_limits=release['original_resource_limits'],
        remaining_sequence=['B1/E1 epoch4-9','B0/E2 epoch1-9','B1/E2 epoch1-9'],
        statistics='2024_DEVELOPMENT_M_C_EXPLORATORY',scientific_performance_conclusion='NOT_MADE',
        automatic_retries=0,refunds=0,PIXELS_2025_READ=0,HISTORICAL_2025_PATH_ATTRIBUTE_ACCESS='NOT_INSTRUMENTED')
    raw=(json.dumps(row,indent=2,ensure_ascii=False,allow_nan=False)+'\n').encode('utf-8')
    with (OUT/'launch_receipt.json').open('xb') as f:f.write(raw)
    with (OUT/'prelaunch_status.json').open('xb') as f:f.write((OUT/'final_status.json').read_bytes())
    (OUT/'final_status.json').write_bytes(raw)
    print(json.dumps({k:row[k] for k in ('snapshot_utc','status','new_reserved','new_returned_verified',
        'combined_reserved','combined_returned_verified','epoch4_returned_updates','logical_run_updates')}))

if __name__=='__main__':main()
