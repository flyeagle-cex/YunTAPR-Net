"""Read-only streaming ancestry seal; no training, ledger change or bulk raw data."""
from pathlib import Path
from datetime import datetime,timezone
import hashlib,json,os,sys,time
ROOT=Path(__file__).absolute().parents[2];sys.path.insert(0,str(ROOT/'src'))
from yuntapr.training.phase_b_v2_seed2027_epoch1_recovery_v1.ancestor import Pool,load_chain,stopped,PREFIX,CP
from yuntapr.training.phase_b_v2_seed2027_epoch1_recovery_v1.protocol import OUT,LAST_SHA,LIMITS

def main():
    if (OUT/'FAILED_ANCESTOR.json').exists():raise PermissionError('NO_OVERWRITE_SEALED_ANCESTOR')
    started=time.monotonic();pool=Pool()
    try:
        load_chain(pool)
        prior=pool.metadata[PREFIX+'FAILED_ANCESTOR.json']
        term=pool.metadata[PREFIX+'.local/sessions/session_0001/termination.json']
        hb=pool.metadata[PREFIX+'.local/sessions/session_0001/heartbeat.json']
        if not term['job_empty_and_handles_signaled']:raise ValueError('PREDECESSOR_JOB_NOT_EMPTY')
        own=pool.summaries[PREFIX+'.local/sessions/session_0001/access_and_events.jsonl']
        known_bytes=prior['carried_resources']['content_bytes']+own['content_bytes']
        if known_bytes<hb['content_bytes']:raise ValueError('AUDIT_BYTES_BELOW_HEARTBEAT')
        pending={p:r['trailing_read_reservation'] for p,r in pool.summaries.items() if r['trailing_read_reservation']}
        # A stopped read cannot be treated as zero. Charge a conservative per-file
        # upper bound equal to the unchanged memory bound; actual bytes remain unknown.
        uncertainty=len(pending)*LIMITS['max_working_set_bytes']
        resources=dict(content_bytes=known_bytes+uncertainty,
            elapsed_seconds=max(term['elapsed_seconds'],hb['elapsed_seconds'],prior['carried_resources']['elapsed_seconds']))
        row=dict(schema='SEED2027_EXPLICIT_EPOCH1_RECOVERY_ANCESTOR_v1',
            sealed_utc=datetime.now(timezone.utc).isoformat(),prior_reserved=75327,prior_returned_verified=75326,
            source_epoch=1,source_update=5228,last_sha256=LAST_SHA,abandoned_old_updates=70099,
            prior_unverified=1,prior_fresh_b0_sha256=prior['prior_fresh_b0_sha256'],
            pins={p:r['sha256'] for p,r in sorted(pool.summaries.items())},
            audit_summaries=pool.summaries,native_probes=stopped(pool),
            carried_resources=resources,known_charged_content_bytes=known_bytes,
            prior_unclosed_read_reservations=pending,unclosed_read_conservative_charge_bytes=uncertainty,
            resource_method='Preserve previous charged bytes plus current audit; unclosed reads conservatively charged, never refunded. Elapsed includes predecessor downtime already charged.',
            restart_kind='EXPLICIT_LAST_RECOVERY_NO_REPLAY',old_ledgers_unchanged=True,
            streamed_audit_seconds=time.monotonic()-started)
        if pool.summaries[CP+'LAST_epoch_01.pt']['sha256']!=LAST_SHA:raise ValueError('APPROVED_PAYLOAD_SHA')
        raw=(json.dumps(row,indent=2)+'\n').encode()
        with (OUT/'FAILED_ANCESTOR.json').open('xb') as f:f.write(raw);f.flush();os.fsync(f.fileno())
        print(json.dumps(dict(status='ANCESTORS_STREAM_VERIFIED',sha256=hashlib.sha256(raw).hexdigest(),
            files=len(pool.files),streamed_bytes=sum(x['bytes'] for x in pool.summaries.values()),
            audit_seconds=row['streamed_audit_seconds'],carried_resources=resources)))
    finally:pool.close()
if __name__=='__main__':main()
