"""Receipt/content verification only; no observation or checkpoint path access."""
import ast
from collections import Counter
import hashlib
import json
from pathlib import Path
import re
import statistics
import subprocess
HERE=Path(__file__).absolute().parent; ROOT=HERE.parents[2]
status=json.loads((HERE/'final_status.json').read_bytes())
ledger=json.loads((HERE/'DATA_ACCESS_LEDGER.json').read_bytes())
scenes=json.loads((HERE/'SCENE_PROVENANCE_RECEIPTS.json').read_bytes())['scenes']
forwards=json.loads((HERE/'FORWARD_RECEIPTS.json').read_bytes())['forwards']
checks={}
def check(name,value):
    checks[name]=bool(value)
    if not value: raise AssertionError(name)

check('actual_pass',status['overall_status']=='BOUNDED_REAL_FORWARD_PILOT_PASS')
check('original_order', [s['position'] for s in scenes]==list(range(48)))
check('unique_48',len({s['scene_key'] for s in scenes})==48)
check('roles_24_24',Counter(s['year'] for s in scenes)=={2023:24,2024:24})
check('model_batch_24_24',Counter(f['model'] for f in forwards)=={'B0_MATCHED_V2':24,'B1_V2':24})
for pair in range(24):
    a,b=forwards[pair*2:pair*2+2]
    check(f'pair_{pair:02d}', a['model']=='B0_MATCHED_V2' and b['model']=='B1_V2'
        and a['pair']==b['pair']==pair and a['scene_keys']==b['scene_keys']
        and a['scene_keys']==[scenes[2*pair]['scene_key'],scenes[2*pair+1]['scene_key']]
        and a['supervision_sha256']==b['supervision_sha256'])
check('native_opens_337',len(ledger['reads'])==337 and all(r['open_success'] for r in ledger['reads']))
check('same_bytes_sha_337',all(r['status']=='SHA_PASS' and r['actual_sha256']==r['expected_sha256'] for r in ledger['reads']))
check('distinct_295',len({r['file_key'] for r in ledger['reads']})==295)
check('read_bytes_exact',sum(r['bytes'] for r in ledger['reads'])==status['raw_payload_content_bytes']==1424778969)
check('content_cap',status['conservative_all_logged_content_bytes']<=4*1024**3)
check('memory_cap',status['resource_peaks']['worker_peak_working_set_bytes']<=3*1024**3)
check('time_cap_no_reset',status['supervisor']['original_budget_elapsed_seconds']<1800)
check('gpu_admitted',status['cuda_admission']['free_bytes']>=5*1024**3)
check('state_all_batches_unchanged', all(f['state_sha256_after']==status['state_sha256_before'][f['model']] for f in forwards)
    and status['state_sha256_after']==status['state_sha256_before'])
check('output_checks',all(f['checks']['finite'] and f['checks']['strictly_monotone']
    and f['checks']['quantile_dtype']=='float64' and f['checks']['probability_dtype']=='bfloat16'
    and f['checks']['inference_mode_enabled'] and not f['checks']['outputs_require_grad'] for f in forwards))
check('no_scientific_performance_claim',not status['scientific_performance_evidence'])
check('approvals_not_upgraded',not status['V2_PHASE_B_AUTHORIZED'] and not status['FORMAL_SCIENTIFIC_EXECUTION_AUTHORIZED']
    and status['HISTORICAL_RECOVERY_RATIFICATION']=='NOT_GRANTED')
check('no_training',status['FORMAL_OPTIMIZER_STEPS']==0 and status['BACKWARDS']==0)
check('2025_disclosure',status['2025_PIXELS_READ']==0 and status['historical_2025_path_attributes']=='NOT_INSTRUMENTED'
    and not status['system_wide_zero_access_proven'])
check('no_tracked_changes',subprocess.check_output(['git','diff','--name-only'],cwd=ROOT)==b'')
for pin in status['public_source_pins']:
    check('pin:'+pin['path'],hashlib.sha256((ROOT/pin['path']).read_bytes()).hexdigest()==pin['sha256'])
src=ROOT/'src/yuntapr/experimental/phase_b_v2_real_forward_pilot'
source_pins=[]
for p in sorted(src.glob('*.py')):
    raw=p.read_bytes(); ast.parse(raw,filename=p.name)
    source_pins.append(dict(path=p.relative_to(ROOT).as_posix(),sha256=hashlib.sha256(raw).hexdigest()))
    tree=ast.parse(raw)
    forbidden=[n for n in ast.walk(tree) if isinstance(n,ast.Call) and isinstance(n.func,ast.Attribute)
               and n.func.attr in ('backward','step','fit','load_state_dict')]
    check('no_updates_ast:'+p.name,not forbidden)
for p in HERE.rglob('*'):
    if not p.is_file() or '.local' in p.parts or '__pycache__' in p.parts or p.suffix in ('.pdf','.png'): continue
    text=p.read_bytes().decode('utf-8-sig')
    # No machine/user paths in reports. Purely synthetic fixture paths are explicit.
    check('public_paths:'+p.relative_to(HERE).as_posix(), Path.home().name.lower() not in text.lower()
          and re.search(r'[A-Za-z]:[\\/](?!synthetic)',text) is None)

source=json.loads((HERE/'source_identity.json').read_bytes())
source['candidate_python_sources']=source_pins
source['candidate_identity_capture']='Post-execution hashes; delivered runtime source content preserved; protected baseline checked by git diff and frozen source pins.'
(HERE/'source_identity.json').write_bytes((json.dumps(source,indent=2)+'\n').encode())
timings={kind:{'count':len(values),'mean_forward_and_checks_seconds':statistics.mean(values),
    'min_seconds':min(values),'max_seconds':max(values)} for kind in ('B0_MATCHED_V2','B1_V2')
    if (values:=[f['forward_and_checks_seconds'] for f in forwards if f['model']==kind])}
result=dict(status='DELIVERY_RECEIPTS_AND_STATIC_PASS', passed_checks=len(checks),failed_checks=0,
            checks=checks,forward_timings=timings,raw_file_reads_by_this_check=0,model_forwards_by_this_check=0)
(HERE/'tests/delivery_verification.json').write_bytes((json.dumps(result,indent=2)+'\n').encode())
print(json.dumps({k:v for k,v in result.items() if k!='checks'}))
