"""Pin zero-update v2 failure and same authorized LAST, no historical writes."""
from pathlib import Path
import hashlib,json,os,sys,time
ROOT=Path(__file__).absolute().parents[2];sys.path.insert(0,str(ROOT/'src'))
from yuntapr.training.phase_b_v2_seed2027_b1_epoch7_recovery_v3.ancestor import Pool,load_chain,stopped,SOURCE_PREFIX,SOURCE_CAMPAIGN,COMPLETE_SHA
from yuntapr.training.phase_b_v2_seed2027_b1_epoch7_recovery_v3.protocol import OUT,LAST_SHA
from yuntapr.experimental.phase_b_v2_stability_review import native
def main():
    if (OUT/'FAILED_ANCESTOR.json').exists():raise PermissionError('NO_OVERWRITE_SEALED_SOURCE')
    start=time.monotonic();pool=Pool()
    try:
        load_chain(pool);prior=pool.metadata[SOURCE_PREFIX+'FAILED_ANCESTOR.json'];term=pool.metadata[SOURCE_PREFIX+'.local/sessions/session_0001/termination.json']
        now,boot=native.clock();resources=dict(prior['carried_resources'])
        resources['elapsed_seconds']=max(resources['elapsed_seconds'],term['elapsed_seconds'])
        row=dict(schema='SEED2027_B1_EPOCH7_HUMAN_AUTHORIZED_ANCESTOR_v3',source_campaign=SOURCE_CAMPAIGN,latest_failed_campaign=SOURCE_CAMPAIGN,
            latest_failed_attempts=0,sealed_utc=now,boot_utc_observed=boot,
            prior_reserved=165383,prior_returned_verified=165382,prior_unverified=1,
            source_epoch=7,source_update=36596,adopted_prior_updates=83648,completed_b0_last_sha256=COMPLETE_SHA,last_sha256=LAST_SHA,
            abandoned_epoch8_updates=0,additional_replay_attempts=0,abandoned_old_updates=81735,
            source_ledger_unchanged='FAILED_NO_RETRY_OBSERVED_ONLY',failed_ledger_unchanged='FAILED_NO_RETRY_OBSERVED_ONLY',original_termination_receipt=True,
            record_kind='IMMUTABLE_ZERO_UPDATE_FAILURE_AND_AUTHORIZED_LAST_OBSERVATION',prior_fresh_b0_sha256=prior['prior_fresh_b0_sha256'],
            pins={p:r['sha256'] for p,r in sorted(pool.summaries.items())},audit_summaries=pool.summaries,native_probes=stopped(pool),carried_resources=resources,
            unclosed_read_conservative_charge_bytes=prior['unclosed_read_conservative_charge_bytes'],
            resource_method='Keep all previously charged bytes and time; append zero-update owner termination time. No raw-data Budget was created.',
            restart_kind='EXPLICIT_B1_EPOCH7_RECOVERY_WITH_AUTHORIZED_EPOCH8_REPLAY',historical_cleanup_execution='NOT_VERIFIED',old_ledgers_unchanged=True,
            streamed_audit_seconds=time.monotonic()-start)
        raw=(json.dumps(row,indent=2)+'\n').encode()
        with (OUT/'FAILED_ANCESTOR.json').open('xb') as f:f.write(raw);f.flush();os.fsync(f.fileno())
        print(json.dumps(dict(status='ZERO_UPDATE_FAILURE_SEALED',sha256=hashlib.sha256(raw).hexdigest(),files=len(pool.files),bytes=sum(r['bytes'] for r in pool.summaries.values()),carried_resources=resources)))
    finally:pool.close()
if __name__=='__main__':main()
