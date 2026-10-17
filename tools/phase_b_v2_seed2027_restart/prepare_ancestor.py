"""Seal predecessor evidence read-only. No data, weights, model or ledger writes."""
from pathlib import Path
import hashlib,json,os,sqlite3,sys
ROOT=Path(__file__).absolute().parents[2];sys.path.insert(0,str(ROOT/'src'))
from yuntapr.training.phase_b_v2_seed2027_restart_v1.protocol import OUT,OLD_CAMPAIGN
from yuntapr.training.phase_b_v2_seed2027_restart_v1.ancestor import PREFIX,OLD_DB,evidence_path,verify_old_rows,Guard
from yuntapr.experimental.phase_b_v2_full_payload_integrity.winio import ReadHandle
from yuntapr.training.phase_b_v2_seed2027_restart_v1.accounting import prior_content_bytes

def main():
    names=[OLD_DB,'.git/phase_b_v2_seed2027_fresh_v1.once',PREFIX+'release.json',
        PREFIX+'execution_status.json',PREFIX+'watchdog_failure.json',
        PREFIX+'.local/B0_MATCHED_V2__E0__s2027/identity.json']
    names += [PREFIX+'.local/sessions/session_0001/'+n for n in
        ('termination.json','supervisor_identity.json','worker_identity.json','bound_identity.json',
         'failure_private.txt','access_and_events.jsonl','launch.json','launch.once','operator_launch.json','heartbeat.json')]
    pins={};raws={};handles=[]
    try:
        for relative in names:
            path=evidence_path(relative);h=ReadHandle(str(path),payload=True);handles.append(h)
            if os.path.normcase(h.final_path)!=os.path.normcase(str(path)) or not 0<h.before['size']<=64*1024**2:
                raise PermissionError('SEALED_EVIDENCE_SIZE_OR_NATIVE_OBJECT')
            parts=[];n=0;buf=bytearray(1024**2)
            while count:=h.readinto(buf):parts.append(bytes(buf[:count]));n+=count
            if n!=h.before['size'] or h.snapshot()!=h.before:raise ValueError('PREDECESSOR_CHANGED_WHILE_SEALING')
            raws[relative]=b''.join(parts);pins[relative]=hashlib.sha256(raws[relative]).hexdigest()
        with sqlite3.connect((ROOT/OLD_DB).as_uri()+'?mode=ro',uri=True) as con:
            con.execute('PRAGMA query_only=ON');verify_old_rows(con)
        term=json.loads(raws[PREFIX+'.local/sessions/session_0001/termination.json'])
        heartbeat=json.loads(raws[PREFIX+'.local/sessions/session_0001/heartbeat.json'])
        events=[json.loads(line) for line in raws[PREFIX+'.local/sessions/session_0001/access_and_events.jsonl'].splitlines()]
        consumed=prior_content_bytes(events,heartbeat['content_bytes'])
        initial=json.loads(raws[PREFIX+'.local/B0_MATCHED_V2__E0__s2027/identity.json'])['initial_sha256']
        row=dict(schema='SEED2027_FAILED_386_FRESH_RESTART_ANCESTOR_v1',old_campaign=OLD_CAMPAIGN,
            prior_reserved=386,prior_returned_verified=385,prior_unverified=1,completed_epochs=0,
            adopted_last=None,job_empty_and_handles_signaled=term['job_empty_and_handles_signaled'],
            failure_code='AVAILABLE_COMMIT_LIMIT',prior_fresh_b0_sha256=initial,pins=pins,
            carried_resources=dict(elapsed_seconds=term['elapsed_seconds'],content_bytes=consumed),
            retained_uncertainty='Attempt 386 failed after the optimizer call but before returned verification; charged, not promoted to verified.',
            restart_kind='FRESH_NO_LAST_NO_WARM_START')
        raw=(json.dumps(row,indent=2)+'\n').encode();digest=hashlib.sha256(raw).hexdigest()
        with (OUT/'FAILED_ANCESTOR.json').open('xb') as f:f.write(raw);f.flush();os.fsync(f.fileno())
        with Guard(digest) as guard:
            print(json.dumps(dict(status='FAILED_ANCESTOR_SEALED_AND_NATIVE_JOB_GONE',receipt_sha256=digest,
                prior_reserved=386,prior_returned_verified=385,carried_resources=guard.receipt['carried_resources'])))
    finally:
        for h in reversed(handles):h.close()
if __name__=='__main__':main()
