"""Seal the stopped epoch3 observation and exact epoch2 LAST, without old writes."""
from pathlib import Path
from datetime import datetime,timezone
import hashlib,json,os,sys,time
ROOT=Path(__file__).absolute().parents[2];sys.path.insert(0,str(ROOT/'src'))
from yuntapr.training.phase_b_v2_seed2027_epoch2_recovery_v1.ancestor import (
    Pool,load_chain,stopped,SOURCE_PREFIX,SOURCE_CAMPAIGN,SOURCE_CP)
from yuntapr.training.phase_b_v2_seed2027_epoch2_recovery_v1.protocol import OUT,LAST_SHA,LIMITS
from yuntapr.experimental.phase_b_v2_stability_review import native

def main():
    if (OUT/'FAILED_ANCESTOR.json').exists():raise PermissionError('NO_OVERWRITE_SEALED_SOURCE')
    start=time.monotonic();pool=Pool()
    try:
        load_chain(pool)
        prior=pool.metadata[SOURCE_PREFIX+'FAILED_ANCESTOR.json']
        session=SOURCE_PREFIX+'.local/sessions/session_0001/'
        heartbeat=pool.metadata[session+'heartbeat.json'];launch=pool.metadata[session+'launch.json']
        audit=pool.summaries[session+'access_and_events.jsonl']
        now,boot=native.clock();stamp=datetime.fromisoformat(now)
        if datetime.fromisoformat(heartbeat['utc'])>=datetime.fromisoformat(boot):raise ValueError('EXPECTED_PRE_BOOT_HEARTBEAT')
        unknown=LIMITS['max_working_set_bytes'] if audit['trailing_read_reservation'] else 0
        known=prior['carried_resources']['content_bytes']+audit['content_bytes']
        if known+unknown<heartbeat['content_bytes']:raise ValueError('SOURCE_RESOURCE_AUDIT_INCOMPLETE')
        elapsed=max(heartbeat['elapsed_seconds'],prior['carried_resources']['elapsed_seconds']+
            (stamp-datetime.fromisoformat(launch['utc'])).total_seconds())
        row=dict(schema='SEED2027_EPOCH2_LAST_HUMAN_AUTHORIZED_REPLAY_ANCESTOR_v1',
            source_campaign=SOURCE_CAMPAIGN,sealed_utc=now,boot_utc_observed=boot,
            prior_reserved=85783,prior_returned_verified=85782,prior_unverified=1,
            source_epoch=2,source_update=10456,last_sha256=LAST_SHA,
            abandoned_epoch3_updates=5228,additional_replay_attempts=5228,abandoned_old_updates=75327,
            source_ledger_unchanged='ACTIVE_STALE_OBSERVED_ONLY',original_termination_receipt=False,
            record_kind='POSTMORTEM_OBSERVATION_NOT_TERMINATION_RECEIPT',
            prior_fresh_b0_sha256=prior['prior_fresh_b0_sha256'],
            pins={p:r['sha256'] for p,r in sorted(pool.summaries.items())},audit_summaries=pool.summaries,
            native_probes=stopped(pool),carried_resources=dict(content_bytes=known+unknown,elapsed_seconds=elapsed),
            known_charged_content_bytes=known,current_unclosed_read_reservation=audit['trailing_read_reservation'],
            new_unknown_read_conservative_charge_bytes=unknown,
            unclosed_read_conservative_charge_bytes=prior['unclosed_read_conservative_charge_bytes']+unknown,
            resource_method='Preserve previous charged bytes and all completed reads; unknown read charged conservatively. Time includes source-launch-to-observation downtime; not GPU runtime.',
            restart_kind='EXPLICIT_LAST_RECOVERY_WITH_AUTHORIZED_EPOCH3_REPLAY',
            historical_cleanup_execution='NOT_VERIFIED',old_ledgers_unchanged=True,
            streamed_audit_seconds=time.monotonic()-start)
        if pool.summaries[SOURCE_CP+'LAST_epoch_02.pt']['sha256']!=LAST_SHA:raise ValueError('EXACT_AUTHORIZED_LAST_SHA')
        raw=(json.dumps(row,indent=2)+'\n').encode()
        with (OUT/'FAILED_ANCESTOR.json').open('xb') as f:f.write(raw);f.flush();os.fsync(f.fileno())
        print(json.dumps(dict(status='STOPPED_SOURCE_AND_EPOCH2_LAST_SEALED',sha256=hashlib.sha256(raw).hexdigest(),
            files=len(pool.files),streamed_bytes=sum(r['bytes'] for r in pool.summaries.values()),
            audit_seconds=row['streamed_audit_seconds'],carried_resources=row['carried_resources'])))
    finally:pool.close()
if __name__=='__main__':main()
