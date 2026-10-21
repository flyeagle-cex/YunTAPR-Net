"""Exact current-session read-only observation; never repairs SQLite in place."""
from pathlib import Path
from contextlib import closing
import hashlib,json,sqlite3
from yuntapr.experimental.phase_b_v2_stability_review import native
from yuntapr.experimental.phase_b_v2_stability_review.classification import scope,classify,DEAD
from yuntapr.experimental.phase_b_v2_status_snapshot_io.reader import read_json_snapshot
from yuntapr.experimental.phase_b_v2_full_payload_integrity.winio import ReadHandle

ROOT=Path(__file__).absolute().parents[4]
OUT=ROOT/'docs/phase_b_v2_formal_execution/seed2027_b1_epoch7_recovery_v1'
DB=ROOT/'.git/phase_b_v2_seed2027_b1_epoch7_recovery_v1.sqlite'
SESSION=OUT/'.local/sessions/session_0001'
CAMPAIGN='YUNTAPR_PHASE_B_V2_SEED2027_B1_EPOCH7_RECOVERY_V1'

def inspect() -> dict:
    owner=read_json_snapshot(SESSION/'supervisor_identity.json',OUT)
    worker=read_json_snapshot(SESSION/'worker_identity.json',OUT)
    expected=scope(owner,worker,CAMPAIGN,1)
    probes=dict(owner=native.process(expected['owner']),worker=native.process(expected['worker']),job=native.job(expected['job_name']))
    hb=read_json_snapshot(SESSION/'heartbeat.json',OUT)
    now,boot=native.clock()
    with closing(sqlite3.connect(DB.as_uri()+'?mode=ro',uri=True)) as c:
        c.execute('PRAGMA query_only=ON');c.execute('BEGIN')
        campaign=c.execute('SELECT id,status,reason FROM campaign').fetchone()
        if campaign[0]!=CAMPAIGN:raise PermissionError('EXACT_STOPPED_SESSION_ONLY')
        counts=dict(c.execute('SELECT status,count(*) FROM attempts GROUP BY status'))
        runs=[dict(zip(('id','status','epoch','updates','last_sha'),r)) for r in c.execute('SELECT id,status,epoch,updates,last_sha FROM runs ORDER BY ordinal')]
        epochs=c.execute("SELECT run,epoch,phase FROM epochs WHERE phase!='LAST_COMMITTED'").fetchall()
        integrity=c.execute('PRAGMA integrity_check').fetchone()
        if integrity!=('ok',):raise ValueError('SQLITE_INTEGRITY')
    facts=dict(ledger_state=campaign[1],heartbeat_utc=hb['utc'],termination_receipt_present=(SESSION/'termination.json').exists(),last_claimed=any(r['last_sha'] for r in runs))
    decision=classify(facts,probes,now,boot)
    row=dict(observed_utc=now,campaign=CAMPAIGN,native_probes=probes,observation=decision,runs=runs,
        incomplete_epochs=epochs,counts=counts,new_reserved=sum(counts.values()),new_verified=counts.get('RETURNED_VERIFIED',0),
        cumulative_reserved=164835+sum(counts.values()),cumulative_verified=164834+counts.get('RETURNED_VERIFIED',0),
        current_hard_cap=363499,historical_unknown_still_charged=1,heartbeat=hb,
        researcher_reported_codex_closed=True,original_ledger_modified=False,actual_termination_receipt_generated=False,
        model_or_raw_data_reads=0,new_optimizer_updates=0,HISTORICAL_2025_PATH_ATTRIBUTE_ACCESS='NOT_INSTRUMENTED')
    # Hash only after native absence, so auditing never blocks a live writer.
    if decision['observed_process_tree_empty']:
        with ReadHandle(str(DB),payload=True) as h:
            digest=hashlib.sha256();buf=bytearray(1024**2)
            while n:=h.readinto(buf):digest.update(memoryview(buf)[:n])
            if h.snapshot()!=h.before:raise ValueError('STOPPED_LEDGER_CHANGED')
            row['stopped_ledger_sha256']=digest.hexdigest()
    return row

if __name__=='__main__':print(json.dumps(inspect(),ensure_ascii=False,indent=2))
