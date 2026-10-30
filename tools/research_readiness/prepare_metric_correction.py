"""Prepare exactly four corrective 2024 Dev passes; never dispatch or read weather.

Uses the failed B0 accounting journal plus frozen metadata/LRU order to calculate
all-content caps. Does not manufacture the mandatory researcher decision file.
"""
import argparse
import ast
from collections import OrderedDict
from datetime import datetime,timezone
import hashlib
import importlib.util
import json
from pathlib import Path
import csv
import subprocess

ROOT=Path(__file__).resolve().parents[2]
LOCAL=ROOT/'docs/research_readiness/.local'
EVIDENCE=ROOT/'docs/research_readiness/20261025/evidence'
TASKS=['B0_s2026_E0','B1_s2026_E0','B0_s2027_E0','B1_s2027_E0']
def read(p):return json.loads(Path(p).read_bytes())
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def digest(x):return hashlib.sha256(json.dumps(x,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()
def write(p,x):
    with Path(p).open('x',encoding='utf-8',newline='\n') as f:json.dump(x,f,indent=2,ensure_ascii=False,allow_nan=False);f.write('\n')


def prepare(previous_path,workspace):
    workspace=workspace.resolve()  # Follow-on runs from a different frozen checkout.
    previous=read(previous_path);old=Path(previous['new_output_root']);registry=read(previous['registry'])
    failure=read(old/'failure.json')
    if 'B0_s2026_E0' not in failure['error']:raise ValueError('Wrong failed package')
    expected={r['run_id']:r for r in registry['runs']};inherited=dict(previous['inherited'])
    for key in previous['remaining']:
        p=old/'runs'/key/'result.json'
        if p.exists():
            r=read(p)
            if r['status']=='COMPLETE' and r['gate']['passed'] is True:
                sealed=read(old/(key+'_verified.json'))
                if sealed['gate_passed'] is not True or sealed['result_sha256']!=sha(p):raise ValueError('Previously sealed metric result changed')
                inherited[key]=dict(result=str(p),sha256=sealed['result_sha256'])
    if len(inherited)!=15 or set(inherited)&set(TASKS) or set(inherited)|set(TASKS)!=set(expected):raise ValueError('Must inherit exactly15 successes')
    # Only these15 small saved results are checked. No historical weights/data audit.
    for key,info in inherited.items():
        if sha(info['result'])!=info['sha256']:raise ValueError('Inherited saved result changed')
        r=read(info['result']);identity=r['checkpoint_identity']
        if r['status']!='COMPLETE' or r['gate']['passed'] is not True or identity['sha256_actual']!=expected[key]['checkpoint_sha256']:raise ValueError('Invalid inherited endpoint')
    admitted=delivered=instances=0
    journal=old/'B0_s2026_E0_source_accounting.jsonl'
    with journal.open(encoding='utf-8') as stream:
        for line in stream:
            row=json.loads(line)
            if row['state']=='ADMITTED_BEFORE_READ':admitted+=row['size'];instances+=1
            elif row['state']=='DELIVERED':delivered+=row['size']
    if admitted!=delivered or delivered!=read(old/'runs/B0_s2026_E0/result.json')['read_scope_actual']['content_bytes_read']:raise ValueError('Failed pass content ledger not closed')
    backfill=Path(previous['engine']).parents[1]
    volumes=read(backfill/'phaseB_inference/outputs/probe_b01_read_volume.json')
    manifest=ROOT/'docs/b1_scientific_freeze/runs/run_20261003T045139_110133Z/b1_2024_formal_manifest.csv'
    with manifest.open(encoding='utf-8-sig',newline='') as stream:rows=list(csv.DictReader(stream))
    if len(rows)!=10501 or any(r['year']!='2024' for r in rows):raise ValueError('2024 frozen population only')
    overhead=delivered-volumes['B0_dev_2024']['total_unique_bytes']
    overhead_reads=instances-volumes['B0_dev_2024']['unique_frames']-volumes['B0_dev_2024']['imerg_days']
    plans={}
    for model,slots in [('B0',(5,)),('B1',range(6))]:
        cache=OrderedDict();misses=[];size=501*501*4
        for row in rows:
            for slot in slots:
                key=row[f'slot_{slot}_nominal']
                if key in cache:cache.move_to_end(key)
                else:
                    while (len(cache)+1)*size>256*1024**2:cache.popitem(last=False)
                    cache[key]=None;misses.append(key)
        days=[r['imerg_day_path'] for r in rows];day_runs=[day for i,day in enumerate(days) if i==0 or day!=days[i-1]]
        v=volumes[model+'_dev_2024']
        if len(misses)!=len(set(misses)) or len(misses)!=v['unique_frames'] or len(day_runs)!=len(set(day_runs)) or len(day_runs)!=v['imerg_days']:raise ValueError('Cache eviction requires another read plan')
        plans[model]=dict(source_bytes=v['total_unique_bytes']+overhead,content_reads=len(misses)+len(day_runs)+overhead_reads,seconds=7200 if model=='B0' else 14400)
    caps={t:plans[t[:2]] for t in TASKS}
    workspace.mkdir(exist_ok=False)
    engine_source=LOCAL/'b01_context_diagnosis_20261030_v1/inference_engine_observed.py'
    diagnosis=read(EVIDENCE/'b01_metric_context_diagnosis_20261030.json')
    if sha(engine_source)!=diagnosis['additional_code_identity_blocker']['observed_engine_sha256']:raise ValueError('Observed source snapshot changed')
    engine=workspace/'infer_eval_frozen.py';raw=engine_source.read_bytes()
    with engine.open('xb') as f:f.write(raw)
    # Verify only changed adapter references: all numeric/gate definitions match
    # the archived, already tested public export. Batch size is forced to8.
    archived=backfill/'public_export/phaseB_inference/infer_eval.py'
    def definitions(path):return {n.name:ast.dump(n,include_attributes=False) for n in ast.parse(path.read_text(encoding='utf-8-sig')).body if isinstance(n,(ast.FunctionDef,ast.ClassDef))}
    before,after=definitions(archived),definitions(engine)
    numeric=['point_candidates_log','conditional_cdf_at','conditional_exceedance_prob','PointAccumulator','gate_summary']
    if any(before.get(k)!=after.get(k) for k in numeric):raise ValueError('Do not inherit tests for changed numeric formulas')
    class FrozenBatch(ast.NodeTransformer):
        def visit_Name(self,node):return ast.copy_location(ast.Constant(8),node) if node.id=='BATCH_SIZE' else node
    fixed=FrozenBatch().visit(ast.parse(engine.read_text(encoding='utf-8-sig')))
    normalized={n.name:ast.dump(n,include_attributes=False) for n in fixed.body if isinstance(n,(ast.FunctionDef,ast.ClassDef))}
    if normalized!=before:raise ValueError('Unreviewed executable definition differs from tested archive')
    commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
    output=LOCAL/'metric_b01_correction_20261030_v1'
    service=LOCAL/'metric_b01_correction_service_20261030_v1';service.mkdir(exist_ok=False)
    follow=LOCAL/'perp_after_b01_correction_20261030_v1';follow.mkdir(exist_ok=False)
    old_spec=read(previous['after_completion_training_spec'])
    if (Path(old_spec['service_dir'])/'independent_launch_claim.json').exists():raise PermissionError('Original follow-on already consumed')
    command=old_spec['command'];original_training=read(command[command.index('--private-preparation')+1])
    if Path(original_training['output_root']).exists():raise PermissionError('Never duplicate the candidate')
    training=dict(original_training,metric_completion=str(output/'completion.json'));training_private=workspace/'perp_private.json';write(training_private,training)
    command=list(command);command[command.index('--private-preparation')+1]=str(training_private)
    follow_spec=dict(old_spec,service_dir=str(follow),command=command);write(follow/'armed_training_spec.json',follow_spec)
    budget=dict(caps=caps,total_content_bytes=sum(v['source_bytes'] for v in caps.values()),total_content_reads=sum(v['content_reads'] for v in caps.values()),maximum_seconds=43200,
        optimizer_updates=0,repeated_inference_tasks=['B0_s2026_E0'],automatic_retries=0,further_repeat_allowance=0,minimum_output_free_bytes=2*1024**3,minimum_host_available_at_start_bytes=8*1024**3,minimum_gpu_free_MiB=5120,
        runtime_working_set_cap_bytes=6*1024**3,runtime_private_commit_cap_bytes=12*1024**3,runtime_gpu_reserved_cap_bytes=6*1024**3)
    code=['tools/research_readiness/resume_metric_backfill.py','tools/research_readiness/prepare_metric_correction.py','tools/research_readiness/start_independent_process.py','tools/core_stage4/monitor/server.py']
    proposal=dict(status='PREPARED_NOT_APPROVED_NOT_STARTED',execution_code_commit=commit,tasks=TASKS,budget=budget,engine_sha256=sha(engine),registry_sha256=sha(previous['registry']),inherited_complete=15,inherited_metrics_sha256={key:info['sha256'] for key,info in inherited.items()},
        public_output_id='metric_b01_correction_20261030_v1',ordering='B0/2026 -> B1/2026 -> B0/2027 -> B1/2027; serial; stop on any failed gate',
        evaluation=dict(year=2024,batch=8,checkpoint='FIXED_E9_LAST',population='10455/10501_B0_B1',process_hash_seed=2026,precision='Historical deterministic=True, TF32=False, highest, inference_mode',gate='UNCHANGED_ABS_REL_1E-12_AND_EXACT_COUNTS',scientific_metric_formulas='UNCHANGED_AST_IDENTICAL_TO_TESTED_ARCHIVE'),
        compatibility=dict(all_executable_definitions_match_tested_archive_at_batch8=True,matched_definition_count=len(normalized),legacy_formula_tests='INHERITED_NOT_RERUN_UNCHANGED_AST',new_cpu_approval_resource_checks=5,new_counter_semantics_check=1,previous_context_checks='INHERITED3_PASS'),
        content_accounting=dict(weather_only_bytes=sum(volumes[m+'_dev_2024']['total_unique_bytes']*2 for m in ('B0','B1')),metadata_and_mask_bytes=overhead*4,metadata_and_mask_instances=overhead_reads*4,failed_B0_delivered_bytes_preserved=delivered,failed_B0_actual_content_instances=instances,failed_B0_legacy_read_events=read(old/'runs/B0_s2026_E0/result.json')['read_scope_actual']['read_events'],read_events_meaning='Budget.emit log events, NOT file reads'),
        data_identity={key:dict(checkpoint_sha256=expected[key]['checkpoint_sha256'],population=expected[key]['population_detail']) for key in TASKS},
        source_sha256=dict(frozen_2024_manifest=sha(manifest),existing_read_volume_metadata=sha(backfill/'phaseB_inference/outputs/probe_b01_read_volume.json'),failed_B0_journal=sha(journal),archived_public_engine=sha(archived)),
        follow_on=dict(model='B7_PERP_GRADIENT',seed=2029,execution_code_commit='9b4046a655e2ec91633104eaa64bd507cca81aad',proposal_sha256='0444d92ef9b10afa2b661c58b32fe57782c3ab5750879bec675f04967c68ce67',authorization='EXISTING_UNCONSUMED_GRANT_NOT_A_NEW_TRAINING_REQUEST',dependency='Only after19 exact COMPLETE gates'),
        resource_preflight=dict(status='PASS_METADATA_ONLY_START_MUST_RECHECK',source_sha256=sha(LOCAL/'metric_correction_resource_preflight_20261030_v1.json'),snapshot_not_future_guarantee=True),
        final_2025='FROZEN_NO_ACCESS',code_sha256={n:sha(ROOT/n) for n in code})
    proposal['proposal_sha256']=digest(proposal)
    public=EVIDENCE/'metric_b01_correction_proposal_20261030.json';write(public,proposal)
    private=dict(previous,engine=str(engine),engine_sha256=sha(engine),inherited=inherited,remaining=TASKS,caps=caps,maximum_seconds=43200,new_output_root=str(output),after_completion_training_spec=str(follow/'armed_training_spec.json'),correction_scope='B01_PRECISION_CORRECTION_4_20261030',correction_proposal=str(public),researcher_approval=str(workspace/'researcher_metric_correction_approval.json'),old_partial_io=dict(prior=previous['old_partial_io'],failed_B0_bytes=delivered,failed_B0_content_instances=instances))
    private_path=workspace/'private.json';write(private_path,private)
    spec=dict(kind='METRIC_BACKFILL_CORRECTION',service_dir=str(service),cwd=str(ROOT),command=[read(previous['after_completion_training_spec'])['command'][0],'-B',str(ROOT/'tools/research_readiness/resume_metric_backfill.py'),'execute','--private',str(private_path)],environment=dict(PYTHONUTF8='1'))
    write(service/'spec.json',spec)
    return dict(status=proposal['status'],execution_code_commit=commit,proposal_sha256=proposal['proposal_sha256'],budget=budget,approval_file_created=False,metric_output_created=output.exists(),original_candidate_output_created=Path(training['output_root']).exists())


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--previous',type=Path,required=True);p.add_argument('--workspace',type=Path,required=True);a=p.parse_args()
    print(json.dumps(prepare(a.previous,a.workspace),ensure_ascii=False))
