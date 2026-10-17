"""Prepare source-bound plans and runtime paths only; NEVER claim/launch a run."""
from pathlib import Path
import hashlib,json,os,subprocess,sys
ROOT=Path(__file__).absolute().parents[2]
DOC=ROOT/'docs/phase_b_v2_multiseed_preparation/v1'
sys.path.insert(0,str(ROOT/'src'))
from yuntapr.training.phase_b_v2_seed2026_operator_v3.protocol import LIMITS
ORDER=(('B0_MATCHED_V2','E0'),('B1_V2','E0'),('B0_MATCHED_V2','E1'),('B1_V2','E1'),('B0_MATCHED_V2','E2'),('B1_V2','E2'))
def sha(raw):return hashlib.sha256(raw).hexdigest()
def dump(path,value):
    with path.open('xb') as f:f.write((json.dumps(value,ensure_ascii=False,indent=2)+'\n').encode())
def main():
    pin='--pin-release' in sys.argv
    dependency=ROOT/'docs/phase_b_v2_formal_execution/seed2026_v2/dependency_identity.json'
    dep_sha=sha(dependency.read_bytes())
    identity=json.loads((ROOT/'docs/phase_b_v2_formal_execution/seed2026_v2/.local/B0_MATCHED_V2__E0__s2026/identity.json').read_bytes())['data']
    keep=('train_ids_sha','development_ids_sha','protocol_sha','source_inventory_sha','mask_sha','scaler_sha','sp04_sha','unique_payload_files','late_file_creation_references')
    frozen={k:identity[k] for k in keep}
    runtime=(ROOT/'docs/phase_b_v2_formal_execution/seed2026_operator_v3/.local/runtime.json').read_bytes()
    for seed in (2027,2028):
        out=ROOT/f'docs/phase_b_v2_formal_execution/seed{seed}_v1';out.mkdir(exist_ok=True)
        if not pin:
            plan=dict(kind='PREPARATION_NOT_EXECUTION_AUTHORIZATION',campaign=f'YUNTAPR_PHASE_B_V2_SEED{seed}_FRESH_V1',
               seed=seed,initialization_seed=seed,python_hash_seed=2026,bootstrap_seed=2026,order_seed_rule='seed+epoch-1',
               design='D1/Q1/N0/I3/B9/S0/V0',statistics='M-C_EXPLORATORY',data_roles={'2023':'Train','2024':'Development'},
               forbidden_years=[2025],train_scenes=10455,development_scenes=10501,frozen_identity=frozen,
               epochs=9,updates_per_epoch=5228,updates_per_run=47052,attempt_cap=282312,
               training_batch_size=2,validation_batch_size=8,accumulation=1,drop_last=False,gradient_clip=5,
               limits=LIMITS,initial_checkpoint=None,warm_start=False,execution_authorized=False,
               checkpoint_schema=f'FORMAL_PHASE_B_V2_SEED{seed}_FRESH_LAST_v1',
               quota_namespace=f'.git/phase_b_v2_seed{seed}_fresh_v1.sqlite',
               batch_predecessor=None if seed==2027 else 2027,
               runs=[dict(run_id=f'{m}__{a}__s{seed}',model=m,arm=a,alpha=.5,gamma=0 if a=='E1' else 2,
                    lambda_q=2 if a=='E2' else 1,updates=47052,seed=seed) for m,a in ORDER])
            dump(out/'config.json',plan)
            local=out/'.local';local.mkdir(exist_ok=True)
            with (local/'runtime.json').open('xb') as f:f.write(runtime)
        else:
            os.environ['YUNTAPR_REPLICATION_SEED']=str(seed)
            # Use a subprocess for fresh module globals, not an import/reload trick.
            command="from yuntapr.experimental.phase_b_v2_multiseed_candidate.protocol import code_identity;import json;print(json.dumps(code_identity()))"
            env=dict(os.environ,PYTHONPATH=str(ROOT/'src'),PYTHONUTF8='1')
            code=json.loads(subprocess.check_output([sys.executable,'-c',command],cwd=ROOT,env=env))
            dump(out/'prepared_release.json',dict(kind='PREPARED_NOT_AUTHORIZED',seed=seed,
                 campaign=f'YUNTAPR_PHASE_B_V2_SEED{seed}_FRESH_V1',source_commit=code['commit'],source_sha256=code['sha256'],source_pins=code['pins'],
                 config_sha256=sha((out/'config.json').read_bytes()),dependency_manifest_sha256=dep_sha,
                 actual_dependency_revalidation='REQUIRED_AT_FUTURE_AUTHORIZED_LAUNCH',execution_authority='ABSENT',
                 scientific_claims='2024_DEVELOPMENT_EXPLORATORY_ONLY',original_seed2026_quota_reuse=False))
    print('PREPARED_SOURCE_PINS' if pin else 'TWO_FIXED_CONFIGS_NO_LAUNCH_NO_LEDGER_CREATION')
if __name__=='__main__':main()
