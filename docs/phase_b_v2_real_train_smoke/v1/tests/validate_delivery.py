"""Existing receipts/public source only; never run the smoke or open weights."""
from pathlib import Path
import hashlib
import json
import re
import subprocess

ROOT=Path(__file__).absolute().parents[4]
OUT=ROOT/'docs/phase_b_v2_real_train_smoke/v1'
SRC=ROOT/'src/yuntapr/experimental/phase_b_v2_real_train_smoke'
checks=[]
def check(name,condition):
    checks.append({'check':name,'passed':bool(condition)})
    assert condition,name
def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()
s=json.loads((OUT/'final_status.json').read_bytes())
identity=json.loads((OUT/'source_identity.json').read_bytes())
check('actual_smoke_pass',s['overall_status']=='BOUNDED_REAL_TRAIN_SMOKE_PASS')
check('only_two_scenes',s['decoded_scenes']==2 and len(s['frozen_scene_ids'])==2)
q=s['quota']; check('durable_two_updates_complete',q['state']=='COMPLETE_SEALED' and
    q['reserved_step_attempts']==q['entered_optimizer_calls']==q['returned_optimizer_calls']==2)
for model in s['models']:
    check(model['model']+'_one_step',model['real_optimizer_calls']==1 and model['scheduler']['completed']==1)
    check(model['model']+'_denominator',model['loss']['n_valid']==6860 and model['loss']['n_rain']==45)
    check(model['model']+'_clip',model['clipping']['post_clip_norm']<=5.00001)
    check(model['model']+'_parameters_changed',model['parameter_sha256_before']!=model['parameter_sha256_after'])
    check(model['model']+'_checkpoint_safe',model['checkpoint']['same_verified_bytes_deserialized'] and model['checkpoint']['weights_only'])
    check(model['model']+'_cuda_budget',model['cuda_peak_reserved_bytes']<=s['limits']['MAX_TORCH_CUDA_RESERVED_BYTES'])
check('raw_all_sha_match',all(r['actual_sha256']==r['expected_sha256'] and r['status']=='SHA_PASS' for r in s['raw_reads']))
check('bytes_receipts',sum(r['bytes'] for r in s['raw_reads'])==53320892)
check('content_budget',s['accounted_content_bytes']<=s['limits']['MAX_REAL_CONTENT_BYTES'])
check('cpu_budget',s['cpu_resources']['peak_working_set_bytes']<=s['limits']['MAX_CPU_WORKING_SET_BYTES'])
check('elapsed_budget',s['driver']['elapsed_seconds']<=s['limits']['MAX_ELAPSED_SECONDS'])
for key in ('V2_PHASE_B_AUTHORIZED','FORMAL_SCIENTIFIC_EXECUTION_AUTHORIZED'):
    check(key,s[key] is False)
check('formal_updates_zero',s['FORMAL_PHASE_B_OPTIMIZER_STEPS']==0)
check('historic_2025_limit_preserved',s['historical_2025_path_attributes']=='NOT_INSTRUMENTED' and s['2025_PIXELS_READ']==0)
check('external_watchdog_limit_disclosed',s['post_execution_watchdog_end_to_end_status']=='NOT_VERIFIED_NO_REAL_RERUN')
check('updated_code_matches_inventory',all(sha(ROOT/p)==h for p,h in identity['delivered_smoke_source_pins'].items()))
for name in ('run.py','launch.py'):
    relative=(SRC/name).relative_to(ROOT).as_posix()
    check('exact_execution_snapshot_'+name,sha(OUT/'execution_source_snapshot'/(name+'.txt'))==identity['executed_source_pins'][relative])
inherited={p:h for p,h in identity['executed_source_pins'].items() if not p.startswith('src/yuntapr/experimental/phase_b_v2_real_train_smoke/')}
check('all_inherited_source_bytes_unchanged',all(sha(ROOT/p)==h for p,h in inherited.items()))
changes=subprocess.check_output(['git','diff','--name-status','HEAD'],cwd=ROOT).decode().splitlines()
check('tracked_diff_only_new_smoke_files',all(r.startswith('A\t') and r.split('\t',1)[1].startswith(
    ('docs/phase_b_v2_real_train_smoke/v1/','src/yuntapr/experimental/phase_b_v2_real_train_smoke/')) for r in changes))
for p in list(OUT.glob('*.md'))+list(OUT.glob('*.json'))+list(OUT.glob('*.jsonl'))+list((OUT/'tests').glob('*.redacted.log')):
    check('no_private_absolute_path_'+p.name,not re.search(r'[A-Za-z]:[\\/]',p.read_text(encoding='utf-8')))
    if p.suffix=='.json': json.loads(p.read_bytes())
for name in ('README.md','REAL_TRAINING_SMOKE_AUDIT.md','GRADIENT_AND_OPTIMIZER_REPORT.md',
             'CHECKPOINT_TRANSACTION_REPORT.md','DATA_IDENTITY_AND_ACCESS_REPORT.md','RESOURCE_REPORT.md','FAILURES_AND_BLOCKERS.md'):
    check('required_'+name,(OUT/name).is_file())
result={'status':'DELIVERY_STATIC_PASS','passed':len(checks),'failed':0,
    'inherited_source_files_sha_verified':len(inherited),'optimizer_updates_during_validation':0,
    'raw_observation_reads_during_validation':0,'checks':checks}
(OUT/'tests/delivery_validation.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
print(json.dumps({k:v for k,v in result.items() if k!='checks'}))
