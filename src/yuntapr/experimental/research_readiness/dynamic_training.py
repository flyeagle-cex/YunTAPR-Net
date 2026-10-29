"""B7/B8 approval-bound serial package; reuses Stage4 optimization/evaluation."""
import os,shutil,sqlite3,subprocess,sys,time
from pathlib import Path
from dataclasses import asdict
import numpy as np
from ..core_innovation.stage3.planning import digest
from ..core_innovation.stage3.metered_io import SourceMeter,path_key
from ..core_innovation.stage4.data import PopulationPlan,read,sha
from ..core_innovation.stage4.engine import FormalDecision,PairedExecutor,resources,write
from ..core_innovation.stage4.launch import ReaderFactory
from ..core_innovation.stage4.evaluation import paired_difference
from .multiseed import load_inherited,code_hashes,endpoint,BatchTail,metric_values,worker_creation_flags
from .static_training import unpack,validate_approval
from .dynamic_terrain import DoteDefinition,PhysicalDote,model_factory
from .tail_diagnostics import TailDiagnostics

ENTRY='tools/research_readiness/start_dynamic_pair.py'
TASKS=(('B7',2029),('B8',2029))
NEW_FILES=(ENTRY,'tools/research_readiness/check_dynamic_cached_real.py',
           'src/yuntapr/experimental/research_readiness/dynamic_terrain.py',
           'src/yuntapr/experimental/research_readiness/dynamic_training.py')


def hashes(root):
    h=code_hashes(root)
    h.update({n:sha(root/n) for n in NEW_FILES})
    return h


def budget(prepared,static_bytes):
    # Compute from each frozen per-pass manifest. DOTE is computed in memory
    # from GFS already delivered to the old MEE reader, never reread/cached here.
    weather_bytes=9*sum(s['bytes_per_pass'] for s in prepared['roles'].values())
    weather_files=9*sum(s['file_count'] for s in prepared['roles'].values())
    total=weather_bytes+static_bytes
    return dict(models=2,updates_per_model=4320,total_updates=8640,
                weather_source_bytes_per_model=weather_bytes,weather_source_files_per_model=weather_files,
                static_source_bytes_per_model={'B7':static_bytes,'B8':static_bytes},static_source_files_per_model=1,
                total_source_bytes_per_model={'B7':total,'B8':total},total_source_bytes=2*total,
                total_source_files=2*(weather_files+1),dynamic_extra_raw_source_bytes=0,dynamic_formal_cache_reads=0,
                max_model_seconds=21600,max_package_seconds=43200,replay_allowance=0,additional_retry_allowance=0,
                initial_free_bytes=48*1024**3,minimum_task_free_bytes=24*1024**3)


class TerrainTail(BatchTail):
    """Supplementary elevation diagnostics; never alter core partitions/loss."""
    def __init__(self,pack):
        super().__init__();z=pack.values[0];valid=pack.valid[0]&pack.region
        self.regions={'elevation_lt_1000m':valid&(z<1000),
                      'elevation_1000_to_2000m':valid&(z>=1000)&(z<2000),
                      'elevation_ge_2000m':valid&(z>=2000)}
        self.diag={k:TailDiagnostics() for k in self.regions};self.brier={k:[0,0.] for k in self.regions}
    def add_batch(self,output,batch):
        super().add_batch(output,batch)
        valid=(batch.valid&batch.region).detach().cpu().numpy()[:,0]
        rate=batch.rate.detach().cpu().numpy()[:,0];q=output.conditional_quantiles_log.detach().double().cpu().numpy()
        prob=output.rain_prob.detach().double().cpu().numpy()[:,0]
        for i,sid in enumerate(batch.ids):
            for name,mask in self.regions.items():
                v=valid[i]&mask;self.diag[name].add(sid,rate[i],q[i],v)
                error=prob[i]-(rate[i]>np.float32(.1))
                self.brier[name][0]+=int(v.sum());self.brier[name][1]+=float((error[v]**2).sum())
    def finish_checked(self,report,ids):
        result=super().finish_checked(report,ids);bins={}
        for name,d in self.diag.items():
            r=d.finish();n=sum(s['n_rain'] for s in r['strata']);covered=sum(s['q32_covered'] for s in r['strata'])
            pin=sum(s['conditional_pinball']*s['n_rain'] for s in r['strata'] if s['n_rain']);nv,bs=self.brier[name]
            bins[name]=dict(n_valid=nv,n_rain=n,brier_sum=bs,brier=bs/nv if nv else None,
                            conditional_pinball=pin/n if n else None,q32_covered=covered,q32_coverage=covered/n if n else None,
                            auroc='NOT_COMPUTED_ADDITIVE_DIAGNOSTIC',average_precision='NOT_COMPUTED_ADDITIVE_DIAGNOSTIC')
        s=report['groups']['all']['summary']
        if sum(v['n_valid'] for v in bins.values())!=s['n_valid'] or sum(v['n_rain'] for v in bins.values())!=s['n_rain']:raise RuntimeError('Supplemental terrain bins changed denominator')
        result['elevation_diagnostics']=dict(scope='SUPPLEMENTARY_ONLY_NOT_FROZEN_CORE_PARTITION',bins=bins,
                                          baseline_B4_B5_B6='NOT_AVAILABLE_NO_EXTRA_INFERENCE',independent_event_count='NOT_ESTIMATED')
        return result


def prepare(root,private_static,output):
    root,output=Path(root),Path(output);s=read(private_static);wrapper,p=load_inherited(s['inherited'])
    if output.exists() or not output.parent.is_dir():raise PermissionError('Fresh output under confirmed parent required')
    physical=read(root/'docs/research_readiness/20261025/evidence/b7_b8_physical_cache_correction.json')
    gpu=read(root/'docs/research_readiness/20261025/evidence/b7_b8_cached_real_check.json')
    if gpu['status']!='PASS_B7_B8_ACTUAL_CACHED_TRAIN_DEV_ZERO_UPDATES' or gpu['data_version']!=p['data']:raise ValueError('New real zero-update check required')
    for n,h in gpu['code_sha256'].items():
        if sha(root/n)!=h:raise ValueError('Numerical path changed after real precheck: '+n)
    prior=read(root/'docs/research_readiness/20261025/evidence/b5_b6_completion_and_paired_evidence.json')
    terrain=Path(s['terrain']);terrain_receipt=read(terrain/'production_receipt.json');static=terrain/'B6_static.npz'
    # Existence/size/known identity only. No DEM/GFS source payload is opened.
    if static.stat().st_size!=312828:raise ValueError('Frozen B6 static size differs')
    definition=gpu['definition'];caps=budget(p,static.stat().st_size)
    if shutil.disk_usage(output.parent).free<caps['initial_free_bytes']:raise RuntimeError('Need48GiB on confirmed output volume')
    choices=dict(DOTE=definition,channels=['O850','O700','W850','W700','L850','L700','M850','M700'],
                 normalization='Physical channels divided by explicit1m/s; no refit, clipping or hidden coefficient',
                 spatial_operator='Inherited native PS mask then conservative bilinear GFS to frozen SP04; use frozen B6 area-mean gradients',
                 scales=['SINGLE_TARGET_SP04_100x100_48_CHANNELS'],condition_channels=dict(GFS_values_and_masks=26,static_and_DOTE_values_and_masks=28),
                 projection_width=16,modulation_limit=.1,modulation_candidates_not_a_sweep=[.05,.1,.2],
                 B7='B6 feature then explicit concat residual',B8='Replace additional B7 concat by matched-active-parameter DTFM branch; not B7 plus a module',
                 initialization=dict(B6='FRESH_SEED2029_NOT_E9_FINETUNING',auxiliary_seed=22029,training_rng='UNCHANGED_B6',condition_projections='SHARED',output='ZERO_RESIDUAL'),
                 condition_mask='Per-channel missing indicators; use any valid DOTE channel plus any GFS channel inside original region; B6 path remains on every supervised pixel',
                 precision='Physical numpyFP64, stored tensorFP32, learned fusionFP32 under disabled AMP, return inheritedBF16; quantile/lossFP64 unchanged',
                 elevation_bins_m=[1000,2000],elevation_metrics='SUPPLEMENTAL_Brier_Pinball_q32_ONLY; no historical baseline bins',
                 static_DEM_release='INHERIT_RESEARCHER_ACCEPTED_NOT_VERIFIED_VENDOR_CHAIN')
    protocol=dict(p['config'],models=['B7','B8'],seed=2029)
    inherited=Path(s['output_root']);baselines={'B6':inherited/'B6_s2029/B6_development_09.json','B5':inherited/'B5_s2029/B5_development_09.json','B4':Path(s['historical_pair'])/'B4_development_09.json'}
    if any(sha(baselines[m])!=prior['sources'][f'{m}/development_09.json']['sha256'] for m in ('B5','B6')):raise ValueError('Completed static reference changed')
    proposal=dict(status='READY_WAITING_EXPLICIT_B7_B8_SCIENCE_AND_TRAINING_BUDGET_APPROVAL',authorized=False,
                  tasks=[dict(model=m,seed=v) for m,v in TASKS],data=p['data'],protocol=protocol,scientific_choices=choices,budget=caps,
                  static_source_sha256={m:prior['static_source_sha256']['B6'] for m,_ in TASKS},
                  parameter_counts={m:gpu['parameter_counts'][m] for m in ('B6','B7','B8')},
                  source_scope_summary={r:{k:s[k] for k in ('file_count','bytes_per_pass','by_kind','source_manifest_sha256')} for r,s in p['roles'].items()},
                  code_sha256=hashes(root),baseline_E9_sha256={m:sha(f) for m,f in baselines.items()},
                  prior_preparation_cost=dict(new_raw_GFS_bytes=901220,new_raw_GFS_files=3,static_source_bytes=312828,static_source_files=1,
                                              total_source_bytes=1214048,total_source_files=4,raw_source_rereads_after_mask_correction=0),
                  new_real_check_sha256=sha(root/'docs/research_readiness/20261025/evidence/b7_b8_cached_real_check.json'),
                  cache_correction_sha256=sha(root/'docs/research_readiness/20261025/evidence/b7_b8_physical_cache_correction.json'),
                  resources=dict(admission=gpu['resource_admission'],new_path_peak_cuda_allocated_bytes=gpu['peak_cuda_allocated_bytes'],
                                 output_volume_free_bytes=shutil.disk_usage(output.parent).free,task_admission_rechecked_at_start=True),
                  time_estimate=dict(reference_B6_actual_seconds=13252.63047838211,estimate_hours_per_model=[3.8,5.5],hard_hours_per_model=6,
                                     basis='Existing B6 elapsed plus small SP04 fusion; no full benchmark or throughput guarantee'),
                  formal_training_started=False)
    proposal['proposal_sha256']=digest(proposal)
    private=dict(proposal_sha256=proposal['proposal_sha256'],inherited=s['inherited'],terrain=s['terrain'],
                 output_root=str(output.resolve()),historical_pair=str((inherited/'B6_s2029').resolve()),
                 baseline_paths={k:str(v.resolve()) for k,v in baselines.items()})
    return proposal,private


def checked(root,proposal_path,private_path,approval_path,commit):
    p,v,a=map(read,(proposal_path,private_path,approval_path));validate_approval(a,p,v,commit)
    if digest({k:x for k,x in p.items() if k!='proposal_sha256'})!=p['proposal_sha256'] or v['proposal_sha256']!=p['proposal_sha256']:raise ValueError('Proposal changed')
    if hashes(root)!=p['code_sha256']:raise ValueError('Exact approved code changed')
    _,prepared=load_inherited(v['inherited'])
    if prepared['data']!=p['data'] or budget(prepared,312828)!=p['budget']:raise ValueError('Frozen data or exact pass budget drift')
    if any(sha(Path(v['baseline_paths'][m]))!=h for m,h in p['baseline_E9_sha256'].items()):raise ValueError('Baseline endpoint changed')
    return p,v,a,prepared


def worker(root,proposal,private,approval,commit,index):
    started=time.monotonic();p,v,a,prepared=checked(root,proposal,private,approval,commit)
    if type(index)!=int or not 0<=index<2:raise PermissionError('Only the two approved tasks')
    package=Path(v['output_root']);binding=read(package/'authorization_binding.json');claim=read(package/f'task_{index+1}_claim.json')
    if binding['controller_pid']!=os.getppid() or binding['approval']!=a or claim!=dict(index=index,controller_pid=os.getppid(),code_commit=commit):raise PermissionError('Live once-only parent binding required')
    kind,seed=TASKS[index]
    return run_task(root,p,v,a,prepared,commit,kind,seed,started=started,pair_reference=Path(v['historical_pair']),static_name=f'{kind}_static_source.sqlite')


def run_task(root,p,v,a,prepared,commit,kind,seed,*,started,pair_reference,static_name,dynamic_transform_factory=PhysicalDote):
    """Internal task wiring shared by approval-checked single/multi-seed dispatchers."""
    package=Path(v['output_root'])
    if kind not in ('B7','B8') or type(seed)!=int:raise PermissionError('Explicit dynamic model/seed required')
    if os.environ.get('PYTHONHASHSEED')!=str(seed) or shutil.disk_usage(package).free<p['budget']['minimum_task_free_bytes']:raise RuntimeError('Seed/storage admission differs')
    db=sqlite3.connect(package/static_name);db.execute('CREATE TABLE jobs(id TEXT PRIMARY KEY,state TEXT)');db.execute("INSERT INTO jobs VALUES ('static','PENDING')");db.commit()
    path=Path(v['terrain'])/'B6_static.npz';meter=SourceMeter(db,{str(path):dict(bytes=312828,sha=p['static_source_sha256'][kind],job_id='static')},max_files=1,max_bytes=312828);meter.active={path_key(path)}
    try:
        with meter.open(path,'rb') as f:raw=f.read()
        pack=unpack(raw,'B6',read(Path(v['terrain'])/'production_receipt.json'));totals=meter.totals()
        with db:db.execute("UPDATE jobs SET state='COMPLETE'")
    finally:db.close()
    plan=PopulationPlan(prepared['private_inputs']['stage3_run'],prepared['private_inputs']['request'],root=root)
    if plan.identity!=p['data']:raise ValueError('Population changed')
    transform=dynamic_transform_factory(pack,DoteDefinition(**p['scientific_choices']['DOTE']))
    def deadline():
        if time.monotonic()-started>p['budget']['max_model_seconds']:raise RuntimeError('Task6h cap; no retry')
    folder=package/f'{kind}_s{seed}'
    PairedExecutor(plan,folder,decision=FormalDecision(a['decision_id'],seed,p['data']['population_sha256'],True,True,True),
                   kinds=(kind,),deadline=deadline,tail_factory=lambda:TerrainTail(pack),code_commit=commit,
                   pair_reference=pair_reference,model_factory=model_factory(pack,read(Path(v['terrain'])/'production_receipt.json')['scalers'],modulation_limit=p['scientific_choices']['modulation_limit'])).run(
                       ReaderFactory(plan,prepared,a['decision_id'],allowed_models=(kind,),dynamic_transform=transform))
    result=endpoint(folder,kind,seed,commit);result.update(static_source_reads=totals,total_logical_source_bytes=result['logical_source_bytes']+312828,total_logical_source_files=result['logical_source_files']+1)
    deadline();write(folder/'completion.json',result);return result


def execute(root,proposal,private,approval,commit):
    started=time.monotonic();p,v,a,prepared=checked(root,proposal,private,approval,commit);out=Path(v['output_root'])
    if out.exists():raise PermissionError('Approval consumed/output exists; no replay or restart')
    if shutil.disk_usage(out.parent).free<p['budget']['initial_free_bytes']:raise RuntimeError('Initial48GiB reserve')
    admission=resources();out.mkdir();write(out/'authorization_binding.json',dict(approval=a,controller_pid=os.getpid(),admission=admission))
    active=None;total_updates=total_bytes=total_files=0
    try:
        for index,(kind,seed) in enumerate(TASKS):
            remaining=p['budget']['max_package_seconds']-(time.monotonic()-started)
            if remaining<=0:raise RuntimeError('Package12h cap')
            write(out/f'task_{index+1}_claim.json',dict(index=index,controller_pid=os.getpid(),code_commit=commit))
            env=dict(os.environ,PYTHONHASHSEED='2029',CUBLAS_WORKSPACE_CONFIG=':4096:8',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1',PYTHONUTF8='1')
            cmd=[sys.executable,'-B',str(root/ENTRY),'worker','--proposal',str(proposal),'--private-preparation',str(private),'--researcher-approval',str(approval),'--task-index',str(index)]
            with (out/f'{kind}_console.log').open('xb') as f:
                active=subprocess.Popen(cmd,cwd=root,env=env,stdout=f,stderr=subprocess.STDOUT,creationflags=worker_creation_flags())
                try:rc=active.wait(timeout=min(remaining,p['budget']['max_model_seconds']))
                except subprocess.TimeoutExpired:active.kill();active.wait();raise RuntimeError('Deadline reached; no retry')
            active=None
            if rc:raise RuntimeError(f'{kind} failed; remaining tasks blocked')
            r=read(out/f'{kind}_s{seed}/completion.json')
            if r['status']!='COMPLETE_TRAIN_AND_DEV_EVALUATION' or r['code_commit']!=commit or r['optimizer_updates']!=4320 or r['total_logical_source_bytes']!=p['budget']['total_source_bytes_per_model'][kind]:raise RuntimeError('Task exact closure differs')
            total_updates+=r['optimizer_updates'];total_bytes+=r['total_logical_source_bytes'];total_files+=r['total_logical_source_files']
        if total_updates!=8640 or total_bytes!=p['budget']['total_source_bytes'] or total_files!=p['budget']['total_source_files']:raise RuntimeError('Package exact closure differs')
        reports={m:read(path) for m,path in v['baseline_paths'].items()}
        reports.update({m:read(out/f'{m}_s2029/{m}_development_09.json') for m,_ in TASKS})
        for m in reports:paired_difference(reports['B6'],reports[m])
        values={m:metric_values(r) for m,r in reports.items()};deltas={}
        for target,base in (('B7','B6'),('B8','B6'),('B8','B7'),('B7','B4'),('B8','B4')):
            deltas[target+'_minus_'+base]={k:values[target][k]-values[base][k] for k in values[base]}
        write(out/'innovation_paired_summary.json',dict(seed=2029,endpoint='FIXED_EPOCH_9_LAST',values=values,differences=deltas,descriptive_only=True,significance='NOT_CLAIMED'))
        if time.monotonic()-started>p['budget']['max_package_seconds']:raise RuntimeError('Closure12h cap')
        write(out/'completion.json',dict(status='COMPLETE_TRAIN_AND_DEV_EVALUATION',updates=total_updates,total_logical_source_bytes=total_bytes,total_logical_source_files=total_files,code_commit=commit))
    except BaseException as exc:
        if active is not None and active.poll() is None:active.kill();active.wait()
        write(out/'failure.json',dict(status='STOP_NO_AUTOMATIC_REPLAY',error=type(exc).__name__+': '+str(exc),partial_counts='SEE_PRESERVED_LEDGERS'));raise
