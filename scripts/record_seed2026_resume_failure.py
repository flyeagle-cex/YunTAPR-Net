"""Read-only accounting reconciliation and public failure receipt; no launch."""
import hashlib
import json
from pathlib import Path
import sqlite3
ROOT=Path(__file__).absolute().parents[1]
OUT=ROOT/'docs/phase_b_v2_formal_execution/seed2026_resume_v1'

def main():
    status=json.loads((OUT/'execution_status.json').read_bytes())
    stop=json.loads((OUT/'.local/termination.json').read_bytes())
    ancestor=json.loads((OUT/'ancestor.json').read_bytes())
    db=ROOT/'.git/phase_b_v2_seed2026_epoch3_recovery_20261013_v1.sqlite'
    with sqlite3.connect(db.as_uri()+'?mode=ro',uri=True) as c:
        c.execute('PRAGMA query_only=ON')
        if c.execute('SELECT count(*) FROM attempts').fetchone()[0]!=0:raise ValueError('NOT_ZERO_NEW_ATTEMPTS')
    unchanged=all(hashlib.sha256((ROOT/p).read_bytes()).hexdigest()==sha for p,sha in ancestor['pins'].items())
    if not unchanged or not stop['job_empty_and_handles_signaled']:raise ValueError('EVIDENCE_OR_JOB_NOT_SAFE')
    events=[json.loads(r) for r in (OUT/'.local/access_and_events.jsonl').read_text(encoding='utf-8').splitlines()]
    raw_reads=[e for e in events if e['event'] in ('READ_RESERVED','READ_FINISHED','READ_CHUNK_RESERVED')]
    if raw_reads:raise ValueError('UNEXPECTED_RAW_CONTENT_ATTEMPT')
    public_bytes=sum(e['bytes'] for e in events if e['event']=='PUBLIC_METADATA_READ')
    prior=(OUT/'final_status.json').read_bytes()
    with (OUT/'prelaunch_status.json').open('xb') as f:f.write(prior)
    row=dict(status='STOPPED_NO_RETRY_FROZEN_H_DRIVE_UNAVAILABLE',failed_utc=status['failed_utc'],
        source_commit=json.loads((OUT/'release.json').read_bytes())['source_commit'],
        new_optimizer_reserved=0,new_optimizer_returned=0,old_reserved=162068,combined_reserved=162068,
        combined_authorized_attempt_cap=287540,new_remaining_attempt_cap=125472,
        old_evidence_sha_unchanged=unchanged,job_empty=stop['job_empty_and_handles_signaled'],
        raw_content_read_bytes=0,raw_content_open_attempts=0,public_metadata_content_bytes=public_bytes,
        software_dependency_hashed_bytes=next(e['hashed_software_bytes'] for e in events if e['event']=='ACTUAL_DEPENDENCIES_VERIFIED'),
        actual_last_restore='NOT_EXECUTED',real_model_forward='NOT_EXECUTED',real_model_backward='NOT_EXECUTED',
        peak_working_set_bytes=stop['peak_process_working_set_bytes'],peak_private_commit_bytes=stop['peak_process_private_commit_bytes'],
        elapsed_new_process_seconds=stop['elapsed_seconds']-ancestor['elapsed_seconds'],
        automatic_retries=0,refunds=0,PIXELS_2025_READ=0,HISTORICAL_2025_PATH_ATTRIBUTE_ACCESS='NOT_INSTRUMENTED',
        failure=dict(file='src/yuntapr/training/phase_b_v2_seed2026_v2/data.py',function='Reader.lock_parents',winerror=3,
                     frozen_source_drive='H:',minimal_remedy='Restore original frozen H drive; new release/launch requires direct researcher decision'))
    for name in ('failure_receipt.json','final_status.json'):
        (OUT/name).write_bytes((json.dumps(row,indent=2,ensure_ascii=False)+'\n').encode('utf-8'))
    print(json.dumps(row))

if __name__=='__main__':main()
