"""Pin this human-authorized activation once. Does not launch or issue authority."""
from pathlib import Path
import hashlib,json,os,subprocess,sys
ROOT=Path(__file__).absolute().parents[2]
sys.path.insert(0,str(ROOT/'src'))
os.environ['YUNTAPR_REPLICATION_SEED']='2027'
from yuntapr.training.phase_b_v2_seed2027.protocol import OUT,DB,CAMPAIGN,LIMITS,TOTAL,code_identity,digest,validate_plan
from yuntapr.training.phase_b_v2_seed2027.authority import execution_instruction,EXECUTION_SCOPE

def main():
    # This version may only publish a fresh, never-consumed planned campaign.
    if DB.exists() or DB.with_suffix('.once').exists() or (OUT/'.local/sessions').exists():
        raise PermissionError('ACTIVATION_CANNOT_REPUBLISH_CONSUMED_CAMPAIGN')
    paths=['src/yuntapr','config/science_v2','scripts/phase_b_v2_replication',
        'tools/phase_b_v2_replication','scripts/phase_b_v2_seed2027','tools/phase_b_v2_seed2027_release']
    if subprocess.run(['git','diff','--quiet','HEAD','--',*paths],cwd=ROOT).returncode:
        raise PermissionError('COMMIT_ACTUAL_EXECUTION_CODE_BEFORE_PINNING')
    source=code_identity()
    held=ROOT/'docs/phase_b_v2_formal_execution/seed2027_release_v1'
    config=(OUT/'config.json').read_bytes()
    if config!=(held/'config.json').read_bytes():raise ValueError('NO_SCIENTIFIC_CONFIG_CHANGE')
    validate_plan(json.loads(config))
    old=(held/'release.json').read_bytes()
    release=dict(schema='SEED2027_HUMAN_AUTHORIZED_EXECUTION_v1',seed=2027,campaign=CAMPAIGN,
        human_instruction=execution_instruction(),human_instruction_sha256=digest(execution_instruction()),
        execution_scope=EXECUTION_SCOPE,launch_authorized=True,planned_attempt_cap=TOTAL,
        original_resource_limits=LIMITS,source_commit=source['commit'],source_sha256=source['sha256'],
        source_pins=source['pins'],config_sha256=hashlib.sha256(config).hexdigest(),
        dependency_manifest_sha256=json.loads(old)['dependency_manifest_sha256'],
        dependency_revalidation='REQUIRED_IN_OWNED_WORKER_BEFORE_FIRST_UPDATE',
        held_publication_commit='ed45c6c817b9c5ab47b1e3f30ce30e99ddb9e38c',
        held_publication_sha256=hashlib.sha256(old).hexdigest(),
        other_seeds_covered=[],automatic_retry=False,automatic_failure_recovery=False,
        provenance_note='Records a real direct human instruction; not a cryptographic human signature or an authority service.')
    raw=(json.dumps(release,ensure_ascii=False,indent=2)+'\n').encode()
    with (OUT/'release.json').open('xb') as f:
        f.write(raw);f.flush();os.fsync(f.fileno())
    print(json.dumps(dict(status='ACTIVATION_PINNED_NOT_YET_STARTED',source_commit=source['commit'],
        source_sha256=source['sha256'],release_sha256=hashlib.sha256(raw).hexdigest())))
if __name__=='__main__':main()
