"""Pin the exact new restart instruction and source; never starts training."""
from pathlib import Path
import hashlib,json,os,subprocess,sys
ROOT=Path(__file__).absolute().parents[2];sys.path.insert(0,str(ROOT/'src'))
from yuntapr.training.phase_b_v2_seed2027_restart_v1.protocol import (
    OUT,DB,CAMPAIGN,LIMITS,TOTAL,MAX_NEW,OLD_RESERVED,OLD_VERIFIED,code_identity,digest,validate_plan)
from yuntapr.training.phase_b_v2_seed2027_restart_v1.authority import execution_instruction,EXECUTION_SCOPE
from yuntapr.training.phase_b_v2_seed2027_restart_v1.ancestor import Guard

def main():
    if DB.exists() or DB.with_suffix('.once').exists() or (OUT/'.local/sessions').exists():
        raise PermissionError('NO_REPUBLISH_AFTER_A_LAUNCH_ATTEMPT')
    paths=['src/yuntapr','config/science_v2','scripts/phase_b_v2_seed2027_restart_v1',
           'tools/phase_b_v2_seed2027_restart']
    if subprocess.run(['git','diff','--quiet','HEAD','--',*paths],cwd=ROOT).returncode:
        raise PermissionError('COMMIT_EXECUTION_CODE_BEFORE_RELEASE')
    config=(OUT/'config.json').read_bytes();validate_plan(json.loads(config))
    old=ROOT/'docs/phase_b_v2_formal_execution/seed2027_execution_v1'
    if config!=(old/'config.json').read_bytes():raise ValueError('SCIENTIFIC_CONFIGURATION_BYTES_UNCHANGED')
    ancestor=(OUT/'FAILED_ANCESTOR.json').read_bytes();ancestor_sha=hashlib.sha256(ancestor).hexdigest()
    with Guard(ancestor_sha) as guard:prior_initial=guard.receipt['prior_fresh_b0_sha256']
    source=code_identity();release=dict(schema='SEED2027_HUMAN_AUTHORIZED_FRESH_RESTART_v1',seed=2027,campaign=CAMPAIGN,
        human_instruction=execution_instruction(),human_instruction_sha256=digest(execution_instruction()),
        execution_scope=EXECUTION_SCOPE,launch_authorized=True,planned_attempt_cap=TOTAL,new_attempt_cap=MAX_NEW,
        prior_reserved=OLD_RESERVED,prior_returned_verified=OLD_VERIFIED,original_resource_limits=LIMITS,
        failed_ancestor_sha256=ancestor_sha,prior_fresh_b0_sha256=prior_initial,
        original_execution_commit='125e42b66477ba0ceb9f3905c0d0464cdc202bb9',
        held_publication_commit='ed45c6c817b9c5ab47b1e3f30ce30e99ddb9e38c',
        dependency_manifest_sha256='2d02c5757f9da5fc1fef8b82168ffd689b96c07056d1cc13acf354a3fd88e780',
        source_commit=source['commit'],source_sha256=source['sha256'],source_pins=source['pins'],
        config_sha256=hashlib.sha256(config).hexdigest(),automatic_retry=False,
        automatic_failure_recovery=False,restart_kind='FRESH_NO_LAST_NO_WARM_START')
    raw=(json.dumps(release,ensure_ascii=False,indent=2)+'\n').encode()
    with (OUT/'release.json').open('xb') as f:f.write(raw);f.flush();os.fsync(f.fileno())
    print(json.dumps(dict(status='RESTART_PINNED_NOT_LAUNCHED',source_commit=source['commit'],
        source_sha256=source['sha256'],release_sha256=hashlib.sha256(raw).hexdigest())))
if __name__=='__main__':main()
