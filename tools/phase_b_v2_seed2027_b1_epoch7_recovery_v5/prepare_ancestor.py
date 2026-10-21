"""Seal the zero-update v4 failed launch on top of the 922-update ancestry."""
from pathlib import Path
from datetime import datetime,timezone
import hashlib,json,os,sys,time
ROOT=Path(__file__).absolute().parents[2];sys.path.insert(0,str(ROOT/'src'))
from yuntapr.training.phase_b_v2_seed2027_b1_epoch7_recovery_v5.ancestor import (
    Pool,load_chain,stopped,SOURCE_PREFIX,SOURCE_CAMPAIGN,SOURCE_TASK,COMPLETE_SHA)
from yuntapr.training.phase_b_v2_seed2027_b1_epoch7_recovery_v5.protocol import OUT,LAST_SHA
from yuntapr.experimental.phase_b_v2_stability_review import native

def main():
    if (OUT/'FAILED_ANCESTOR.json').exists():raise PermissionError('NO_OVERWRITE_SEALED_SOURCE')
    start=time.monotonic();pool=Pool()
    try:
        load_chain(pool)
        prior_receipt=pool.metadata[SOURCE_PREFIX+'FAILED_ANCESTOR.json']
        task=stopped(pool)
        now,boot=native.clock()
        stamp=datetime.now(timezone.utc)
        elapsed=prior_receipt['carried_resources']['elapsed_seconds']+max(0.,(stamp-datetime.fromisoformat(prior_receipt['sealed_utc'])).total_seconds())
        content=prior_receipt['carried_resources']['content_bytes']
        row=dict(schema='SEED2027_B1_EPOCH7_ZERO_UPDATE_REISSUE_ANCESTOR_v5',source_campaign=SOURCE_CAMPAIGN,latest_failed_campaign=SOURCE_CAMPAIGN,
            zero_update_failed_launch=True,zero_update_consumed_attempts=0,sealed_utc=stamp.isoformat(),boot_utc_observed=boot,
            prior_reserved=166305,prior_returned_verified=166304,prior_unverified=1,source_epoch=7,source_update=36596,
            adopted_prior_updates=83648,completed_b0_last_sha256=COMPLETE_SHA,last_sha256=LAST_SHA,
            abandoned_epoch8_updates=922,additional_replay_attempts=922,abandoned_old_updates=82657,
            source_ledger_unchanged='FAILED_NO_RETRY_OPERATOR_SPAWN_FAILED_OR_UNCERTAIN',
            original_termination_receipt=False,
            source_scheduled_task=task['scheduled_task'],
            record_kind='IMMUTABLE_ZERO_UPDATE_REISSUE_ANCESTOR',
            prior_fresh_b0_sha256=prior_receipt['prior_fresh_b0_sha256'],
            pins={p:r['sha256'] for p,r in sorted(pool.summaries.items())},
            carried_resources=dict(content_bytes=content,elapsed_seconds=elapsed),
            resource_method='Zero new reads or updates in the failed launch; wall clock continues from the prior seal, not GPU runtime.',
            restart_kind='EXPLICIT_B1_EPOCH7_RECOVERY_WITH_AUTHORIZED_EPOCH8_REPLAY',
            historical_cleanup_execution='NOT_VERIFIED',old_ledgers_unchanged=True,
            streamed_audit_seconds=time.monotonic()-start)
        raw=(json.dumps(row,indent=2)+'\n').encode()
        with (OUT/'FAILED_ANCESTOR.json').open('xb') as f:f.write(raw);f.flush();os.fsync(f.fileno())
        print(json.dumps(dict(status='ZERO_UPDATE_FAILED_LAUNCH_SEALED',sha256=hashlib.sha256(raw).hexdigest(),files=len(pool.files),
            streamed_bytes=sum(r['bytes'] for r in pool.summaries.values()),carried_resources=row['carried_resources'])))
    finally:pool.close()

if __name__=='__main__':main()
