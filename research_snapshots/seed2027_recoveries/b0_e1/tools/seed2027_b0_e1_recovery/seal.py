"""Seal new read-only adoption evidence and local release; never launch."""
import hashlib, json
from datetime import datetime, timezone
import operate
from yuntapr.training.phase_b_v2_seed2027_b0_e1_recovery_v1 import protocol as p
from yuntapr.training.phase_b_v2_seed2027_b0_e1_recovery_v1.authority import execution_instruction,EXECUTION_SCOPE
from yuntapr.training.phase_b_v2_seed2027_b0_e1_recovery_v1.ancestor import Pool,REGISTERED,validate_pool,SOURCE_PREFIX,SESSION,COMPLETE_LAST
from yuntapr.training.phase_b_v2_seed2027_b0_e1_recovery_v1.accounting import ADOPTED

def main():
    if p.DB.exists() or p.DB.with_suffix('.once').exists() or (p.OUT/'release.json').exists():raise PermissionError('NO_RESEAL_OR_RETRY')
    from yuntapr.training.phase_b_v2_seed2027_b0_e1_recovery_v1.admission import require_launch_headroom
    headroom=require_launch_headroom()
    with_pool=Pool()
    try:
        for name in sorted(REGISTERED):with_pool.read(name)
        old,probes=validate_pool(with_pool);now=datetime.now(timezone.utc)
        content=old['carried_resources']['content_bytes']+with_pool.summaries[SESSION+'access_and_events.jsonl']['content_bytes']
        heartbeat=with_pool.metadata[SESSION+'heartbeat.json']
        if content<heartbeat['content_bytes']:raise ValueError('AUDITED_BYTES_BELOW_HEARTBEAT')
        elapsed=old['carried_resources']['elapsed_seconds']+(now-datetime.fromisoformat(old['sealed_utc'])).total_seconds()
        if elapsed<heartbeat['elapsed_seconds'] or elapsed>=p.LIMITS['max_seconds'] or content>=p.LIMITS['max_read_bytes']:raise ValueError('INHERITED_TIME_OR_READ_BUDGET')
        receipt=dict(schema='V7_B0_E1_EPOCH1_FAILED_ANCESTOR_v1',source_campaign=probes and 'YUNTAPR_PHASE_B_V2_SEED2027_B1_EPOCH7_RECOVERY_V7',
            sealed_utc=now.isoformat(),source_epoch=1,source_update=5228,last_sha256=p.LAST_SHA,
            prior_reserved=p.OLD_RESERVED,prior_returned_verified=p.OLD_VERIFIED,prior_unverified=1,
            adopted_prior_updates=ADOPTED,abandoned_old_updates=p.ABANDONED,additional_replay_attempts=5228,
            source_ledger_unchanged=True,original_supervisor_termination_receipt=False,
            failure_evidence='GUI_MEMORYERROR_EXIT1_EMPTY_JOB_AND_NATIVE_TREE_ABSENT;SOURCE_CAMPAIGN_FAILED_NO_RETRY',
            prior_fresh_b0_sha256=old['prior_fresh_b0_sha256'],
            older_ancestry='INHERITED_FROM_UNCHANGED_V7_RELEASE_AND_FAILED_ANCESTOR_SHA;NOT_RESCANNED',
            pins={name:row['sha256'] for name,row in sorted(with_pool.summaries.items())},
            native_probes=probes,carried_resources=dict(content_bytes=content,elapsed_seconds=elapsed),
            read_log_complete=True,trailing_read_reservation=None,preparation_headroom=headroom)
        p.atomic_json(p.OUT/'FAILED_ANCESTOR.json',receipt)
        code=p.code_identity();config=(p.OUT/'config.json').read_bytes();p.validate_plan(json.loads(config))
        release=dict(schema='ISOLATED_SEED2027_B0_E1_EPOCH1_RECOVERY_v1',campaign=p.CAMPAIGN,
            human_instruction=execution_instruction(),human_instruction_sha256=p.digest(execution_instruction()),
            execution_scope=EXECUTION_SCOPE,launch_authorized=True,planned_attempt_cap=p.TOTAL,new_attempt_cap=p.MAX_NEW,
            prior_reserved=p.OLD_RESERVED,prior_returned_verified=p.OLD_VERIFIED,recovery_last_sha256=p.LAST_SHA,
            recovery_epoch=1,recovery_update=5228,additional_replay_attempts=5228,original_resource_limits=p.LIMITS,
            source_commit=code['commit'],source_sha256=code['sha256'],source_pins=code['pins'],
            config_sha256=hashlib.sha256(config).hexdigest(),legacy_release_sha256=code['legacy_release_sha256'],
            gui_runtime_sha256=p.digest(p.owned_json(p.LOCAL/'gui_runtime.json')),
            dependency_manifest_sha256='2d02c5757f9da5fc1fef8b82168ffd689b96c07056d1cc13acf354a3fd88e780',
            failed_ancestor_sha256=hashlib.sha256((p.OUT/'FAILED_ANCESTOR.json').read_bytes()).hexdigest(),
            prior_fresh_b0_sha256=receipt['prior_fresh_b0_sha256'],completed_last_sha256=COMPLETE_LAST,
            publication_kind='LOCAL_ISOLATED_RELEASE_EXACT_HUMAN_APPROVAL_NO_MAIN_DEPLOYMENT')
        p.atomic_json(p.OUT/'release.json',release)
        p.verify_release()
        print(json.dumps(dict(sealed=True,source_commit=code['commit'],original_repository_writes=0,training_launched=False,
            carried_resources=receipt['carried_resources'],pinned_objects=len(receipt['pins']))))
    finally:with_pool.close()

if __name__=='__main__':main()
