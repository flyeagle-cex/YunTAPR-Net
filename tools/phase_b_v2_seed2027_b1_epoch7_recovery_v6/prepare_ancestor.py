"""Seal the fully terminated zero-update v5 failure, with no resource refunds."""
from pathlib import Path
from datetime import datetime,timezone
import hashlib,json,os,sys,time
ROOT=Path(__file__).absolute().parents[2];sys.path.insert(0,str(ROOT/'src'))
from yuntapr.training.phase_b_v2_seed2027_b1_epoch7_recovery_v6.ancestor import Pool,load_chain,stopped,SOURCE_PREFIX,SOURCE_CAMPAIGN,COMPLETE_SHA
from yuntapr.training.phase_b_v2_seed2027_b1_epoch7_recovery_v6.protocol import OUT,LAST_SHA,LIMITS
from yuntapr.experimental.phase_b_v2_stability_review import native

def main():
    if (OUT/'FAILED_ANCESTOR.json').exists():raise PermissionError('NO_OVERWRITE_SEALED_SOURCE')
    start=time.monotonic();pool=Pool()
    try:
        load_chain(pool);prior=pool.metadata[SOURCE_PREFIX+'FAILED_ANCESTOR.json'];folder=SOURCE_PREFIX+'.local/sessions/session_0001/'
        heartbeat=pool.metadata[folder+'heartbeat.json'];term=pool.metadata[folder+'termination.json'];audit=pool.summaries[folder+'access_and_events.jsonl']
        unknown=LIMITS['max_working_set_bytes'] if audit['trailing_read_reservation'] else 0
        content=prior['carried_resources']['content_bytes']+audit['content_bytes']+unknown
        if content<heartbeat['content_bytes']:raise ValueError('SOURCE_RESOURCE_AUDIT_INCOMPLETE')
        stamp=datetime.now(timezone.utc);now,boot=native.clock()
        elapsed=max(term['elapsed_seconds'],heartbeat['elapsed_seconds'],
            prior['carried_resources']['elapsed_seconds']+max(0.,(stamp-datetime.fromisoformat(prior['sealed_utc'])).total_seconds()))
        row=dict(schema='SEED2027_B1_EPOCH7_ZERO_UPDATE_INTERFACE_REISSUE_ANCESTOR_v6',source_campaign=SOURCE_CAMPAIGN,latest_failed_campaign=SOURCE_CAMPAIGN,
            zero_update_failed_launch=True,zero_update_consumed_attempts=0,sealed_utc=stamp.isoformat(),boot_utc_observed=boot,
            prior_reserved=166305,prior_returned_verified=166304,prior_unverified=1,source_epoch=7,source_update=36596,
            adopted_prior_updates=83648,completed_b0_last_sha256=COMPLETE_SHA,last_sha256=LAST_SHA,
            abandoned_epoch8_updates=922,additional_replay_attempts=922,abandoned_old_updates=82657,
            source_ledger_unchanged='FAILED_NO_RETRY_GUI_OWNER_FAILED_NO_RETRY',original_termination_receipt=True,
            record_kind='IMMUTABLE_ZERO_UPDATE_INTERFACE_FAILURE_AND_NEW_DIRECT_HUMAN_REISSUE',prior_fresh_b0_sha256=prior['prior_fresh_b0_sha256'],
            pins={p:r['sha256'] for p,r in sorted(pool.summaries.items())},audit_summaries=pool.summaries,native_probes=stopped(pool),
            carried_resources=dict(content_bytes=content,elapsed_seconds=elapsed),current_unclosed_read_reservation=audit['trailing_read_reservation'],
            new_unknown_read_conservative_charge_bytes=unknown,resource_method='Append all completed reads and unfinished-read reserve; preserve prior wall-clock charging, without increasing limits.',
            restart_kind='EXPLICIT_B1_EPOCH7_RECOVERY_WITH_AUTHORIZED_EPOCH8_REPLAY',historical_cleanup_execution='NOT_VERIFIED',old_ledgers_unchanged=True,
            streamed_audit_seconds=time.monotonic()-start)
        raw=(json.dumps(row,indent=2)+'\n').encode()
        with (OUT/'FAILED_ANCESTOR.json').open('xb') as f:f.write(raw);f.flush();os.fsync(f.fileno())
        print(json.dumps(dict(status='ZERO_UPDATE_INTERFACE_FAILURE_SEALED',sha256=hashlib.sha256(raw).hexdigest(),files=len(pool.files),
            streamed_bytes=sum(r['bytes'] for r in pool.summaries.values()),carried_resources=row['carried_resources'])))
    finally:pool.close()

if __name__=='__main__':main()
