"""Seal 922 nonrefundable updates, exact epoch7 LAST and original hard resources."""
from pathlib import Path
from datetime import datetime
import hashlib,json,os,sys,time
ROOT=Path(__file__).absolute().parents[2];sys.path.insert(0,str(ROOT/'src'))
from yuntapr.training.phase_b_v2_seed2027_b1_epoch7_recovery_v4.ancestor import Pool,load_chain,stopped,SOURCE_PREFIX,SOURCE_CAMPAIGN,COMPLETE_SHA,OBSERVATION
from yuntapr.training.phase_b_v2_seed2027_b1_epoch7_recovery_v4.protocol import OUT,LAST_SHA,LIMITS,digest
from yuntapr.experimental.phase_b_v2_stability_review import native

def main():
    if (OUT/'FAILED_ANCESTOR.json').exists():raise PermissionError('NO_OVERWRITE_SEALED_SOURCE')
    start=time.monotonic();pool=Pool()
    try:
        load_chain(pool);prior=pool.metadata[SOURCE_PREFIX+'FAILED_ANCESTOR.json'];folder=SOURCE_PREFIX+'.local/sessions/session_0001/'
        heartbeat=pool.metadata[folder+'heartbeat.json'];audit=pool.summaries[folder+'access_and_events.jsonl'];observation=pool.metadata[OBSERVATION]
        unknown=LIMITS['max_working_set_bytes'] if audit['trailing_read_reservation'] else 0
        known=prior['carried_resources']['content_bytes']+audit['content_bytes']
        if known+unknown<heartbeat['content_bytes']:raise ValueError('SOURCE_RESOURCE_AUDIT_INCOMPLETE')
        gap=max(0.,(datetime.fromisoformat(observation['utc'])-datetime.fromisoformat(heartbeat['utc'])).total_seconds())
        elapsed=max(heartbeat['elapsed_seconds']+gap,prior['carried_resources']['elapsed_seconds'])
        now,boot=native.clock()
        row=dict(schema='SEED2027_B1_EPOCH7_HUMAN_AUTHORIZED_ANCESTOR_v4',source_campaign=SOURCE_CAMPAIGN,latest_failed_campaign=SOURCE_CAMPAIGN,
            latest_failed_attempts=922,sealed_utc=now,boot_utc_observed=boot,prior_reserved=166305,prior_returned_verified=166304,prior_unverified=1,
            source_epoch=7,source_update=36596,adopted_prior_updates=83648,completed_b0_last_sha256=COMPLETE_SHA,last_sha256=LAST_SHA,
            abandoned_epoch8_updates=922,additional_replay_attempts=922,abandoned_old_updates=82657,
            source_ledger_unchanged='ACTIVE_BUT_NATIVE_OWNER_WORKER_JOB_ABSENT',failed_ledger_unchanged='ACTIVE_OBSERVED_ONLY_NO_TERMINATION_RECEIPT',
            original_termination_receipt=False,record_kind='IMMUTABLE_POSTMORTEM_OBSERVATION_AND_DIRECT_HUMAN_LAST_RECOVERY',
            prior_fresh_b0_sha256=prior['prior_fresh_b0_sha256'],pins={p:r['sha256'] for p,r in sorted(pool.summaries.items())},audit_summaries=pool.summaries,
            native_probes=stopped(pool),carried_resources=dict(content_bytes=known+unknown,elapsed_seconds=elapsed),known_charged_content_bytes=known,
            current_unclosed_read_reservation=audit['trailing_read_reservation'],new_unknown_read_conservative_charge_bytes=unknown,
            unclosed_read_conservative_charge_bytes=prior['unclosed_read_conservative_charge_bytes']+unknown,
            resource_method='Preserve all prior charges; append completed reads and conservatively charge unfinished read. Unknown stop time charged through proven-empty observation, not GPU runtime.',
            restart_kind='EXPLICIT_B1_EPOCH7_RECOVERY_WITH_AUTHORIZED_EPOCH8_REPLAY',historical_cleanup_execution='NOT_VERIFIED',old_ledgers_unchanged=True,
            streamed_audit_seconds=time.monotonic()-start)
        raw=(json.dumps(row,indent=2)+'\n').encode()
        with (OUT/'FAILED_ANCESTOR.json').open('xb') as f:f.write(raw);f.flush();os.fsync(f.fileno())
        print(json.dumps(dict(status='UNCLEAN_922_AND_EXACT_LAST_SEALED',sha256=hashlib.sha256(raw).hexdigest(),files=len(pool.files),
            streamed_bytes=sum(r['bytes'] for r in pool.summaries.values()),carried_resources=row['carried_resources'])))
    finally:pool.close()

if __name__=='__main__':main()
