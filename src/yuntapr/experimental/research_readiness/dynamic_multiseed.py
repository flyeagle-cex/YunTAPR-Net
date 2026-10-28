"""B7/B8 2030/2031 only: reuse frozen models, Stage4 task loop and read meters."""
import copy,os,shutil,statistics,subprocess,sys,time
from pathlib import Path
from ..core_innovation.stage3.planning import digest
from ..core_innovation.stage4.data import read,sha
from ..core_innovation.stage4.engine import resources,write
from ..core_innovation.stage4.evaluation import paired_difference
from .dynamic_training import run_task,hashes as original_hashes
from .multiseed import load_inherited,metric_values,worker_creation_flags

TASKS=(('B7',2030),('B8',2030),('B7',2031),('B8',2031))
ENTRY='tools/research_readiness/start_dynamic_multiseed.py'
MODULE='src/yuntapr/experimental/research_readiness/dynamic_multiseed.py'
EVIDENCE='docs/research_readiness/20261025/evidence/'
CHECKS=EVIDENCE+'b7_b8_multiseed_checks_20261028.json'

def hashes(root):
    h=original_hashes(root);h.update({n:sha(root/n) for n in (ENTRY,MODULE)});return h

def budget(prepared):
    weather=9*sum(s['bytes_per_pass'] for s in prepared['roles'].values())
    files=9*sum(s['file_count'] for s in prepared['roles'].values())
    return dict(models=4,updates_per_model=4320,total_updates=17280,
                weather_source_bytes_per_model=weather,weather_source_files_per_model=files,
                static_source_bytes_per_model={k:312828 for k in ('B7','B8')},static_source_files_per_model=1,
                total_source_bytes_per_model={k:weather+312828 for k in ('B7','B8')},source_files_per_model=files+1,
                total_source_bytes=4*(weather+312828),total_source_files=4*(files+1),
                dynamic_extra_raw_source_bytes=0,dynamic_formal_cache_reads=0,normalization_refits=0,
                startup_source_metadata_checks=1,startup_source_payload_bytes=0,startup_metadata_seconds_cap=15,
                max_model_seconds=21600,max_package_seconds=86400,replay_allowance=0,additional_retry_allowance=0,
                initial_free_bytes=96*1024**3,minimum_task_free_bytes=24*1024**3)

def choices(original):
    c=copy.deepcopy(original['scientific_choices'])
    c['initialization']=dict(B6='FRESH_TASK_SEED_NOT_E9_FINETUNING',static_auxiliary_seed_rule='seed+10000',
                             fusion_auxiliary_seed_rule='seed+20000',training_rng='UNCHANGED_MATCHING_SEED_B6',
                             condition_projections='SHARED_WITHIN_SEED',output='ZERO_RESIDUAL')
    return c

def task_configs(original):
    out={}
    for kind,seed in TASKS:
        cfg=dict(original['protocol'],models=[kind],seed=seed,endpoint='FIXED_EPOCH_9_LAST')
        out[f'{kind}_s{seed}']=dict(config=cfg,sha256=digest(cfg),static_auxiliary_seed=seed+10000,fusion_auxiliary_seed=seed+20000)
    return out

def prepare(root,original_private,seed_references,output):
    root,output,refs=Path(root),Path(output),Path(seed_references)
    old=read(root/(EVIDENCE+'b7_b8_training_proposal.json'));completed=read(root/(EVIDENCE+'b8_recovery_completion_20261028.json'))
    checked=read(root/CHECKS);v=read(original_private);_,prepared=load_inherited(v['inherited'])
    if checked['status']!='PASS_NEW_MULTI_SEED_PREPARATION_ONLY' or checked['formal_optimizer_updates']!=0:raise ValueError('New seed checks required')
    if any(sha(root/n)!=h for n,h in checked['code_sha256'].items()):raise ValueError('Code changed after targeted checks')
    if completed['status']!='VERIFIED_COMPLETE_B7_B8_FIXED_E9_TRAIN_AND_DEV' or prepared['data']!=old['data']:raise ValueError('Inherited completion/data identity differs')
    caps=budget(prepared)
    if caps['total_source_bytes']!=1910287815360 or caps['total_source_files']!=571252:raise ValueError('Frozen four-task budget differs')
    if output.exists() or not output.parent.is_dir():raise PermissionError('Fresh independent directory required')
    free=shutil.disk_usage(output.parent).free
    if free<caps['initial_free_bytes']:raise RuntimeError('Output volume below96GiB; do not delete originals')
    pins={};private_refs={}
    for seed in (2030,2031):
        folder=refs/f's{seed}';private_refs[str(seed)]=str(folder.resolve())
        for name in ('paired_initial_identity.json','paired_orders.json'):
            pins[f's{seed}/{name}']=sha(folder/name)
            if pins[f's{seed}/{name}']!=checked['seed_references'][str(seed)][name]:raise ValueError('Prepared new seed identity changed')
    protocol=dict(old['protocol']);protocol.pop('seed');protocol['seeds']=[2030,2031]
    code_commit=subprocess.check_output(['git','-C',str(root),'rev-parse','HEAD'],text=True).strip()
    if subprocess.check_output(['git','-C',str(root),'status','--porcelain'],text=True).strip():raise PermissionError('Commit checked engineering before freezing proposal')
    p=dict(status='READY_WAITING_EXPLICIT_FOUR_MODEL_TRAINING_APPROVAL',authorized=False,execution_code_commit=code_commit,
           tasks=[dict(model=k,seed=s) for k,s in TASKS],training_configs=task_configs(old),protocol=protocol,
           data=old['data'],scientific_choices=choices(old),frozen_science_source_sha256=old['proposal_sha256'],
           allowed_scientific_change='ONLY_TASK_SEED_AND_DERIVED_INITIALIZATION_STREAMS; architecture/loss/inputs/scales unchanged',
           budget=caps,static_source_sha256=old['static_source_sha256'],parameter_counts={'B7':4411058,'B8':4411058},
           preparation_checks_sha256=sha(root/CHECKS),source_admission_sha256=checked['source_admission_sha256'],
           original_private_sha256=sha(original_private),inherited_private_sha256=sha(v['inherited']),
           seed_reference_pins=pins,seed_initialization=checked['initialization'],order_overlap=checked['order_overlap'],
           code_sha256=hashes(root),seed2029_completion_sha256=sha(root/(EVIDENCE+'b8_recovery_completion_20261028.json')),
           historical_seed2029=dict(B7=completed['B7_fixed_E9_sha256'],B8=completed['B8_fixed_E9_sha256'],B8_replay=62,B8_original_commit=completed['inherited_training_commit'],B8_recovery_commit=completed['training_commit']),
           source_scope_summary=old['source_scope_summary'],
           resources=dict(checked['resource_admission'],output_volume_free_bytes=free,minimum_initial_free_bytes=caps['initial_free_bytes'],recheck_at_start=True),
           output=dict(volume_alias='NEW_D_VOLUME_NAMESPACE',directory_alias=output.name,scope='NEW_DIRECTORY_ONLY; exact private path bound in researcher approval'),
           time_estimate=dict(reference_B7_seconds=13430.258143663406,reference_B8_combined_seconds=completed['budget_closure']['combined_B8_wall_seconds_proxy'],
                              estimated_hours_per_model=[3.8,5.5],estimated_serial_hours=[15.2,22.0],hard_serial_hours=24,basis='Completed seed2029; no new GPU benchmark'),
           preparation_activity=dict(raw_weather_payload_bytes=0,original_DEM_tile_reads=0,formal_optimizer_updates=0,checkpoint_loads=0,normalization_refits=0),
           scientific_analysis=dict(paired_difference='B8_MINUS_B7',seeds=[2029,2030,2031],sample_sd_ddof=1,q32_nominal=.984375,
                                    q32_direction='DISTANCE_TO_NOMINAL_NOT_SIMPLY_HIGHER',independent_weather_years=1,significance='NOT_CLAIMED'),
           final_2025='FROZEN_NO_ACCESS',B6_extra_training='NOT_INCLUDED')
    private=dict(original_private=str(Path(original_private).resolve()),inherited=v['inherited'],terrain=v['terrain'],
                 output_root=str(output.resolve()),seed_references=private_refs,
                 historical_B7=str(Path(v['output_root'])/'B7_s2029'),historical_B8=str(Path(read(root/'docs/research_readiness/.local/b8_recovery_preparation_20261028.json')['output_root'])/'B8_s2029'))
    private['historical_E9_pins']={f'{k}/{stem}':sha(Path(private['historical_'+k])/f'{k}_{stem}_09.json') for k in ('B7','B8') for stem in ('development','tail')}
    p['historical_E9_metadata_sha256']=private['historical_E9_pins'];p['private_locator_sha256']=digest(private)
    p['proposal_sha256']=digest(p);private['proposal_sha256']=p['proposal_sha256']
    return p,private

def validate_approval(a,p,v,commit):
    expected=dict(approved_by_researcher=True,code_commit=commit,proposal_sha256=p['proposal_sha256'],tasks=p['tasks'],budget=p['budget'],
                  scientific_choices=p['scientific_choices'],output_root=v['output_root'])
    if commit!=p['execution_code_commit'] or any(a.get(k)!=x for k,x in expected.items()) or not isinstance(a.get('decision_id'),str) or not a['decision_id'].strip():raise PermissionError('Explicit exact four-model/seed/science/output/budget approval required')

def checked(root,proposal,private,approval,commit):
    p,v,a=map(read,(proposal,private,approval));validate_approval(a,p,v,commit)
    if digest({k:x for k,x in p.items() if k!='proposal_sha256'})!=p['proposal_sha256'] or v['proposal_sha256']!=p['proposal_sha256'] or hashes(root)!=p['code_sha256']:raise ValueError('Approved code/proposal binding changed')
    if digest({k:x for k,x in v.items() if k!='proposal_sha256'})!=p['private_locator_sha256'] or sha(v['original_private'])!=p['original_private_sha256'] or sha(v['inherited'])!=p['inherited_private_sha256']:raise ValueError('Private scope binding changed')
    old=read(root/(EVIDENCE+'b7_b8_training_proposal.json'));_,prepared=load_inherited(v['inherited'])
    if p['tasks']!=[dict(model=k,seed=s) for k,s in TASKS] or choices(old)!=p['scientific_choices'] or task_configs(old)!=p['training_configs'] or budget(prepared)!=p['budget'] or prepared['data']!=p['data']:raise ValueError('Frozen science/config/scope changed')
    if any(prepared['roles'][role]['source_manifest_sha256']!=scope['source_manifest_sha256'] for role,scope in p['source_scope_summary'].items()):raise ValueError('Source file set changed')
    for seed in (2030,2031):
        for name in ('paired_initial_identity.json','paired_orders.json'):
            if sha(Path(v['seed_references'][str(seed)])/name)!=p['seed_reference_pins'][f's{seed}/{name}']:raise ValueError('Seed reference changed')
    for key,h in p['historical_E9_metadata_sha256'].items():
        kind,stem=key.split('/')
        if sha(Path(v['historical_'+kind])/f'{kind}_{stem}_09.json')!=h:raise ValueError('Inherited seed2029 E9 metadata changed')
    return p,v,a,prepared

def worker(root,proposal,private,approval,commit,index):
    started=time.monotonic();p,v,a,prepared=checked(root,proposal,private,approval,commit)
    if type(index)!=int or not 0<=index<4:raise PermissionError('Only four listed tasks')
    package=Path(v['output_root']);binding=read(package/'authorization_binding.json');claim=read(package/f'task_{index+1}_claim.json')
    if binding['controller_pid']!=os.getppid() or binding['approval']!=a or claim!=dict(index=index,controller_pid=os.getppid(),code_commit=commit):raise PermissionError('Live once-only parent required')
    kind,seed=TASKS[index];reference=Path(v['seed_references'][str(seed)]) if kind=='B7' else package/f'B7_s{seed}'
    return run_task(root,p,v,a,prepared,commit,kind,seed,started=started,pair_reference=reference,static_name=f'{kind}_s{seed}_static_source.sqlite')

def differences(a,b):return {k:a[k]-b[k] for k in b}

def admit_source(prepared,out):
    """One named former-failure source, metadata/open-only, never a payload read."""
    name='NC_H09_20231025_2300_R21_FLDK.06001_06001.nc'
    matches=[(p,x) for p,x in prepared['roles']['Train']['files'].items() if Path(p).name.casefold()==name.casefold()]
    if len(matches)!=1 or matches[0][1]['year']!=2023:raise ValueError('Exact Train source scope required')
    path,source=matches[0]
    code='''import json,os,sys\nfrom pathlib import Path\np=Path(sys.argv[1])\ntry:\n s=p.stat();r=p.resolve(strict=True)\n with p.open("rb"):pass\n print(json.dumps(dict(status="PASS",bytes=s.st_size,same_path=os.path.normcase(str(p))==os.path.normcase(str(r)),payload_bytes=0)))\nexcept OSError as e:print(json.dumps(dict(status="OS_ERROR",winerror=getattr(e,"winerror",None),errno=e.errno)))\n'''
    try:
        r=subprocess.run([sys.executable,'-B','-c',code,path],capture_output=True,text=True,timeout=15,creationflags=worker_creation_flags(),check=True)
        result=__import__('json').loads(r.stdout)
    except subprocess.TimeoutExpired:result=dict(status='TIMEOUT_STOP',payload_bytes=0)
    write(out/'source_admission.json',dict(source_basename=name,**result))
    if result['status']!='PASS' or result['bytes']!=source['bytes'] or not result['same_path']:raise RuntimeError('Bounded source admission failed; preserved receipt, no retry')

def aggregate(values):
    if set(values)!={2029,2030,2031}:raise ValueError('All three real independent training seeds required')
    return {k:dict(by_seed={str(s):values[s][k] for s in (2029,2030,2031)},mean=statistics.mean(values[s][k] for s in values),sample_sd=statistics.stdev(values[s][k] for s in values),
                   improvement='LOWER' if k in ('brier','conditional_pinball','q32_absolute_error') else 'CLOSER_TO_NOMINAL' if k.startswith('q32') else 'HIGHER') for k in values[2029]}

def summarize(out,v):
    endpoints={};tails={};by_group={};rain={};elevation={};group_values={}
    for seed in (2029,2030,2031):
        reports={};tails[seed]={}
        for kind in ('B7','B8'):
            base=Path(v['historical_'+kind]) if seed==2029 else out/f'{kind}_s{seed}'
            reports[kind]=read(base/f'{kind}_development_09.json');tails[seed][kind]=read(base/f'{kind}_tail_09.json')
        paired_difference(reports['B7'],reports['B8']);endpoints[str(seed)]={k:metric_values(r) for k,r in reports.items()}
        group_values[str(seed)]={name:{k:metric_values({'groups':{'all':r['groups'][name]}}) for k,r in reports.items()} for name in reports['B7']['groups']}
        for name,a in reports['B7']['groups'].items():
            b=reports['B8']['groups'][name]
            if a['ids_sha']!=b['ids_sha']:raise ValueError('Group population differs')
            by_group.setdefault(name,{})[seed]=differences(metric_values({'groups':{'all':b}}),metric_values({'groups':{'all':a}}))
        for i,(a,b) in enumerate(zip(tails[seed]['B7']['strata'],tails[seed]['B8']['strata'])):
            if (a['lower'],a['upper'],a['n_rain'])!=(b['lower'],b['upper'],b['n_rain']):raise ValueError('Rain strata changed')
            rain.setdefault(str(i),{})[seed]={k:b[k]-a[k] for k in ('conditional_pinball','q32_coverage')}
        for name,a in tails[seed]['B7']['elevation_diagnostics']['bins'].items():
            b=tails[seed]['B8']['elevation_diagnostics']['bins'][name]
            if (a['n_valid'],a['n_rain'])!=(b['n_valid'],b['n_rain']):raise ValueError('Elevation populations differ')
            elevation.setdefault(name,{})[seed]={k:b[k]-a[k] for k in ('brier','conditional_pinball','q32_coverage')}
    rain_summary={k:aggregate(x) for k,x in rain.items()}
    for value in rain_summary.values():value['q32_coverage']['improvement']='DESCRIPTIVE_OUTCOME_CONDITIONED_COVERAGE_NO_PER_STRATUM_NOMINAL_TARGET'
    write(out/'three_seed_innovation_summary.json',dict(seeds=[2029,2030,2031],endpoints=endpoints,metrics=aggregate(by_group['all']),
          group_endpoints=group_values,groups={k:aggregate(x) for k,x in by_group.items()},rain_strata=rain_summary,
          tail_endpoints={str(s):{k:{'strata':t['strata'],'elevation_diagnostics':t['elevation_diagnostics']} for k,t in items.items()} for s,items in tails.items()},
          elevation={k:aggregate(x) for k,x in elevation.items()},descriptive_only=True,independent_weather_years=1,significance='NOT_CLAIMED',
          limitations=['Adjacent seed+epoch-1 orders overlap by shifts','Pixels are not independent storm events','Outcome-conditioned coverage is descriptive, not a per-stratum nominal target','B6 only seed2029; no independent DOTE causality claim']))

def execute(root,proposal,private,approval,commit):
    started=time.monotonic();p,v,a,prepared=checked(root,proposal,private,approval,commit);out=Path(v['output_root']);active=None;updates=bytes_=files=0
    if out.exists():raise PermissionError('Consumed output; no automatic retry/replay')
    if shutil.disk_usage(out.parent).free<p['budget']['initial_free_bytes']:raise RuntimeError('Need96GiB initial reserve; no cleanup')
    admission=resources();out.mkdir(exist_ok=False);write(out/'authorization_binding.json',dict(approval=a,controller_pid=os.getpid(),admission=admission))
    try:
        admit_source(prepared,out)
        for index,(kind,seed) in enumerate(TASKS):
            remaining=p['budget']['max_package_seconds']-(time.monotonic()-started)
            if remaining<=0:raise RuntimeError('24h package cap')
            write(out/f'task_{index+1}_claim.json',dict(index=index,controller_pid=os.getpid(),code_commit=commit))
            env=dict(os.environ,PYTHONHASHSEED=str(seed),CUBLAS_WORKSPACE_CONFIG=':4096:8',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1',PYTHONUTF8='1')
            cmd=[sys.executable,'-B',str(root/ENTRY),'worker','--proposal',str(proposal),'--private-preparation',str(private),'--researcher-approval',str(approval),'--task-index',str(index)]
            with (out/f'{kind}_s{seed}_console.log').open('xb') as log:
                active=subprocess.Popen(cmd,cwd=root,env=env,stdout=log,stderr=subprocess.STDOUT,creationflags=worker_creation_flags())
                try:rc=active.wait(timeout=min(remaining,p['budget']['max_model_seconds']))
                except subprocess.TimeoutExpired:active.kill();active.wait();raise RuntimeError('Hard deadline; no retry')
            active=None
            if rc:raise RuntimeError(f'{kind}/{seed} failed; later tasks NOT_STARTED')
            r=read(out/f'{kind}_s{seed}/completion.json')
            if (r['status'],r['model'],r['seed'],r['optimizer_updates'],r['code_commit'],r['total_logical_source_bytes'],r['total_logical_source_files'])!=('COMPLETE_TRAIN_AND_DEV_EVALUATION',kind,seed,4320,commit,p['budget']['total_source_bytes_per_model'][kind],p['budget']['source_files_per_model']):raise RuntimeError('Task endpoint/identity/budget differs')
            updates+=r['optimizer_updates'];bytes_+=r['total_logical_source_bytes'];files+=r['total_logical_source_files']
            if kind=='B8':
                for name in ('paired_initial_identity.json','paired_orders.json'):
                    if read(out/f'B7_s{seed}'/name)!=read(out/f'B8_s{seed}'/name):raise RuntimeError('Within-seed pairing differs')
                write(out/f'paired_difference_s{seed}.json',paired_difference(read(out/f'B7_s{seed}/B7_development_09.json'),read(out/f'B8_s{seed}/B8_development_09.json')))
        if (updates,bytes_,files)!=(p['budget']['total_updates'],p['budget']['total_source_bytes'],p['budget']['total_source_files']):raise RuntimeError('Exact four-task cap closure differs')
        summarize(out,v)
        if time.monotonic()-started>p['budget']['max_package_seconds']:raise RuntimeError('24h closure cap')
        result=dict(status='COMPLETE_FOUR_MODELS_THREE_SEED_INNOVATION_SUMMARY',updates=updates,logical_source_bytes=bytes_,logical_source_files=files,code_commit=commit,replay=0)
        write(out/'completion.json',result);return result
    except BaseException as exc:
        if active is not None and active.poll() is None:active.kill();active.wait()
        write(out/'failure.json',dict(status='STOP_NO_AUTOMATIC_RETRY',error=type(exc).__name__+': '+str(exc),completed_updates=updates,completed_source_bytes=bytes_,partial_counts='SEE_PRESERVED_LEDGERS_NOT_ZERO'));raise
