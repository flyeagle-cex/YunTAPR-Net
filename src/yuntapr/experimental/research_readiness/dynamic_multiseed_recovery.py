"""Bounded B7/2030 E6 continuation, then the three untouched paired tasks.

Reuse the existing LAST restorer, optimizer/reader/engine and three-seed export.
Preparation opens metadata only; neither a training grant nor replay is inferred.
"""
from datetime import datetime
import math,os,shutil,sqlite3,subprocess,sys,time
from pathlib import Path
from ..core_innovation.stage3.planning import digest
from ..core_innovation.stage3.metered_io import SourceMeter,path_key
from ..core_innovation.stage4.data import PopulationPlan,read,sha
from ..core_innovation.stage4.engine import FormalDecision,PairedExecutor,resources,write
from ..core_innovation.stage4.recovery import ResumeState,RecoveryLedger,restore_last,query
from ..core_innovation.stage4.launch import ReaderFactory
from ..core_innovation.stage4.evaluation import paired_difference
from . import dynamic_multiseed as original
from .dynamic_training import run_task,TerrainTail
from .dynamic_terrain import PhysicalDote,DoteDefinition,model_factory
from .static_training import unpack
from .multiseed import load_inherited,worker_creation_flags

ENTRY='tools/research_readiness/start_dynamic_multiseed_recovery.py'
MODULE='src/yuntapr/experimental/research_readiness/dynamic_multiseed_recovery.py'
HOST='tools/research_readiness/start_independent_process.py'
READY=original.EVIDENCE
STOP=READY+'b7_b8_multiseed_interruption_20261028.json'
OLD=READY+'b7_b8_multiseed_proposal_20261028.json'
LAUNCH=READY+'b7_b8_multiseed_approved_launch_20261028.json'
CAUSE=READY+'b7_b8_multiseed_exit_cause_20261028.json'
PARENT_COMMIT='56aae5bc4568df5d91354805aa5d4cb6d34b62b3'
TASKS=original.TASKS


def hashes(root):
    result=original.hashes(root)
    result.update({name:sha(root/name) for name in (ENTRY,MODULE,HOST)})
    return result


def budget(prepared,stop,launch,weight_bytes):
    pair_bytes=sum(s['bytes_per_pass'] for s in prepared['roles'].values())
    pair_files=sum(s['file_count'] for s in prepared['roles'].values())
    if (pair_bytes,pair_files)!=(53063515668,15868):raise ValueError('Frozen pass scope changed')
    prior=stop['optimizer_ledger']
    if (prior['returned'],prior['reserved'],prior['last_saved'],prior['unsaved_returned'])!=(3321,3321,2880,441):raise ValueError('Wrong interrupted trajectory')
    # Conservatively charge through the first confirmed-gone observation, not
    # the earlier last-write/host-teardown time. Approval waiting is excluded.
    elapsed=math.ceil((datetime.fromisoformat(stop['first_process_observation_beijing'])-datetime.fromisoformat(launch['started_at'])).total_seconds())
    remaining=21600-elapsed
    if remaining<=0:raise RuntimeError('No B7 six-hour allocation remains')
    steps=[1440,4320,4320,4320];bytes_=[3*pair_bytes+312828]+[9*pair_bytes+312828]*3;files=[3*pair_files+1]+[9*pair_files+1]*3
    io=stop['logical_io_committed_snapshot']
    if io['bytes']!=io['reserved_bytes']:raise ValueError('Uncertain original source bytes need a new conservative bound')
    return dict(updates_per_model=4320,new_task_updates=steps,total_updates=sum(steps),replay_allowance=441,
        prior_updates=3321,saved_updates=2880,cumulative_B7_attempts=4761,cumulative_updates=3321+sum(steps),
        new_source_bytes_per_task=bytes_,new_source_files_per_task=files,total_source_bytes=sum(bytes_),total_source_files=sum(files),
        total_source_bytes_per_model={'B7':9*pair_bytes+312828,'B8':9*pair_bytes+312828},source_files_per_model=9*pair_files+1,
        prior_source_bytes=io['bytes'],prior_source_files=io['files'],cumulative_source_bytes=io['bytes']+sum(bytes_),cumulative_source_files=io['files']+sum(files),
        static_source_bytes_per_task=312828,static_source_files_per_task=1,dynamic_extra_raw_source_bytes=0,normalization_refits=0,
        startup_source_metadata_checks=1,startup_source_payload_bytes=0,startup_metadata_seconds_cap=15,
        prior_wall_seconds_ceil=elapsed,task_wall_seconds=[remaining,21600,21600,21600],max_model_seconds=21600,max_package_seconds=remaining+64800,
        cumulative_wall_seconds=86400,initial_free_bytes=96*1024**3,minimum_task_free_bytes=24*1024**3,
        checkpoint_SHA_reads=1,checkpoint_deserializations=1,checkpoint_source_bytes=weight_bytes,checkpoint_read_byte_cap=2*weight_bytes,
        additional_retry_allowance=0,additional_replay_allowance=0,wall_accounting='Prior elapsed charged through first confirmed-gone observation; new+prior<=24h, B7<=6h; approval waiting excluded')


def prepare(root,original_private,output):
    root,output=Path(root),Path(output);v=read(original_private);parent=Path(v['output_root'])
    old,stop,launch=read(root/OLD),read(root/STOP),read(root/LAUNCH)
    if stop['training_commit']!=PARENT_COMMIT or stop['status']!='STOPPED_WITHOUT_TERMINAL_RECEIPT':raise ValueError('Wrong interrupted package')
    for name,h in old['code_sha256'].items():
        if sha(root/name)!=h:raise ValueError('Frozen scientific dependency changed: '+name)
    if query(parent/'B7_s2030/updates.sqlite','SELECT model,state,COUNT(*),MIN(u),MAX(u) FROM updates GROUP BY model,state')!=[('B7','RETURNED',3321,1,3321)]:raise ValueError('Parent update ledger changed')
    if (parent/'completion.json').exists() or any((parent/f'{k}_s{s}/completion.json').exists() for k,s in TASKS):raise PermissionError('Unexpected later completion; do not duplicate')
    if any((parent/f'{k}_s{s}').exists() for k,s in TASKS[1:]):raise PermissionError('Untouched task was started')
    pins={item['source_id']:item['sha256'] for item in stop['source_metadata']}
    for name,h in pins.items():
        if sha(parent/name)!=h:raise ValueError('Original stopped ledger/journal changed')
    seals=[]
    for name in ('paired_initial_identity.json','paired_orders.json'):
        pins['B7_s2030/'+name]=sha(parent/'B7_s2030'/name)
    for e in range(1,7):
        base=parent/'B7_s2030';seal=read(base/f'B7_LAST_epoch_{e:02d}.receipt.json');dev=read(base/f'B7_development_{e:02d}.json')
        if (seal['epoch'],seal['updates'],seal['code_commit'],seal['validation_receipt_sha256'])!=(e,e*480,PARENT_COMMIT,digest(dev)):raise ValueError('Inherited epoch seal changed')
        seals.append(seal)
        names=[f'B7_{stem}_{e:02d}.json' for stem in ('train','development','tail')]+[f'B7_LAST_epoch_{e:02d}.receipt.json']
        names+=[f'B7_{role}_reads_{e:02d}/pass_receipt.json' for role in ('train','dev')]
        for name in names:pins['B7_s2030/'+name]=sha(base/name)
    weight=parent/'B7_s2030/B7_LAST_epoch_06.pt';size=weight.stat().st_size
    if seals[-1]!=stop['last_saved_E6']:raise ValueError('E6 identity differs from stopped receipt')
    _,prepared=load_inherited(v['inherited']);caps=budget(prepared,stop,launch,size)
    if prepared['data']!=old['data']:raise ValueError('Population changed')
    if output.exists() or output.parent!=parent.parent:raise PermissionError('Fresh independent sibling output required')
    free=shutil.disk_usage(output.parent).free
    if free<caps['initial_free_bytes']:raise RuntimeError('Need96GiB without deleting history')
    admission=resources();commit=subprocess.check_output(['git','-C',str(root),'rev-parse','HEAD'],text=True).strip()
    if subprocess.check_output(['git','-C',str(root),'status','--porcelain'],text=True).strip():raise PermissionError('Commit tested code before proposal freeze')
    p=dict(status='READY_WAITING_EXACT_RECOVERY_AND_441_REPLAY_APPROVAL',authorized=False,execution_code_commit=commit,
        tasks=old['tasks'],training_configs=old['training_configs'],protocol=old['protocol'],scientific_choices=old['scientific_choices'],data=old['data'],budget=caps,
        checkpoint=dict(model='B7',seed=2030,epoch=6,updates=2880,sha256=seals[-1]['checkpoint_sha256'],bytes=size,parent_commit=PARENT_COMMIT,preparation='METADATA_ONLY_NO_WEIGHT_LOAD_OR_REHASH',execution='ONE_SHA_CHECK_AND_ONE_DESERIALIZATION'),
        inherited_checkpoints=seals,parent_pins=pins,parent_commit=PARENT_COMMIT,static_source_sha256=old['static_source_sha256'],
        inherited_proposal_sha256=old['proposal_sha256'],original_proposal_file_sha256=sha(root/OLD),original_private_sha256=sha(original_private),inherited_private_sha256=sha(v['inherited']),
        seed_reference_pins=old['seed_reference_pins'],historical_E9_metadata_sha256=old['historical_E9_metadata_sha256'],
        stop_receipt_sha256=sha(root/STOP),launch_receipt_sha256=sha(root/LAUNCH),cause_receipt_sha256=sha(root/CAUSE),code_sha256=hashes(root),
        resources=dict(admission,output_free_bytes=free,recheck_at_start=True),output=dict(volume_alias='APPROVED_D_PARENT_NEW_DIRECTORY',directory_alias=output.name),
        startup='REQUIRE_INDEPENDENT_WMI_SUPERVISOR_AND_NO_JOB_NO_PACKAGE_BEFORE_CONTROLLER_WORK',
        preparation_activity=dict(raw_weather_payload_bytes=0,checkpoint_deserializations=0,checkpoint_payload_SHA_reads=0,formal_optimizer_updates=0),
        time_estimate_hours=[12.7,18.4],scientific_endpoint='ALL_FOUR_FIXED_E9_AND_THREE_REAL_SEED_PAIRS; NO_BEST',final_2025='FROZEN_NO_ACCESS')
    private=dict(original_private=str(Path(original_private).resolve()),parent=str(parent.resolve()),output_root=str(output.resolve()))
    p['private_locator_sha256']=digest(private);p['proposal_sha256']=digest(p);private['proposal_sha256']=p['proposal_sha256']
    return p,private


def validate_approval(a,p,v,commit):
    expected=dict(approved_by_researcher=True,code_commit=commit,proposal_sha256=p['proposal_sha256'],tasks=p['tasks'],budget=p['budget'],scientific_choices=p['scientific_choices'],output_root=v['output_root'],approved_checkpoint_sha256=p['checkpoint']['sha256'],approved_replay_updates=441)
    if commit!=p['execution_code_commit'] or any(a.get(k)!=value for k,value in expected.items()) or not a.get('decision_id'):raise PermissionError('Exact new recovery/code/E6/441 replay/budget decision required')


def checked(root,proposal,private,approval,commit):
    p,v,a=map(read,(proposal,private,approval));validate_approval(a,p,v,commit)
    if digest({k:x for k,x in p.items() if k!='proposal_sha256'})!=p['proposal_sha256'] or v['proposal_sha256']!=p['proposal_sha256'] or hashes(root)!=p['code_sha256']:raise ValueError('Recovery code/proposal changed')
    if digest({k:x for k,x in v.items() if k!='proposal_sha256'})!=p['private_locator_sha256'] or sha(v['original_private'])!=p['original_private_sha256']:raise ValueError('Private scope changed')
    inherited=read(v['original_private']);_,prepared=load_inherited(inherited['inherited'])
    if inherited['output_root']!=v['parent'] or sha(inherited['inherited'])!=p['inherited_private_sha256'] or prepared['data']!=p['data']:raise ValueError('Original scope changed')
    if any(sha(Path(v['parent'])/n)!=h for n,h in p['parent_pins'].items()):raise ValueError('Parent evidence changed')
    if any(sha(root/n)!=p[key] for n,key in ((STOP,'stop_receipt_sha256'),(LAUNCH,'launch_receipt_sha256'),(CAUSE,'cause_receipt_sha256'))):raise ValueError('Stop/budget evidence changed')
    if budget(prepared,read(root/STOP),read(root/LAUNCH),p['checkpoint']['bytes'])!=p['budget']:raise ValueError('Exact budget changed')
    old=read(root/OLD)
    if sha(root/OLD)!=p['original_proposal_file_sha256']:raise ValueError('Original frozen proposal changed')
    if any(p[k]!=old[k] for k in ('tasks','training_configs','protocol','scientific_choices','data','static_source_sha256')):raise ValueError('Frozen science/config changed')
    for seed in (2030,2031):
        for name in ('paired_initial_identity.json','paired_orders.json'):
            if sha(Path(inherited['seed_references'][str(seed)])/name)!=p['seed_reference_pins'][f's{seed}/{name}']:raise ValueError('Seed reference changed')
    for key,h in p['historical_E9_metadata_sha256'].items():
        kind,stem=key.split('/')
        if sha(Path(inherited['historical_'+kind])/f'{kind}_{stem}_09.json')!=h:raise ValueError('Inherited seed2029 E9 metadata changed')
    return p,v,a,prepared,inherited


class B7Resume(ResumeState):
    kinds=('B7',)
    def completed_epochs(self,kind):
        if kind!='B7':raise PermissionError('Only interrupted B7/2030')
        return 6
    def validate(self,plan,decision):
        if plan.identity!=self.request['data_identity'] or decision.seed!=2030 or decision.decision_id!=self.request['decision_id']:raise PermissionError('Recovery population/seed/decision changed')
    def ledger(self,path,identity):
        return RecoveryLedger(path,dict(identity,recovery=self.request),offsets={'B7':2880},segment_cap=1440,prior_updates=3321,cumulative_cap=4761,allowed_models=self.kinds)
    def restore(self,kind,model,optimizer,groups):
        self.completed_epochs(kind);weight=self.parent/'B7_LAST_epoch_06.pt'
        if sha(weight)!=self.request['checkpoint_sha256']:raise ValueError('E6 changed before load')
        restore_last(weight,model,optimizer,groups,data_identity=self.request['data_identity'],epoch=6,updates=2880,kind='B7',seed=2030)
        return 2880,[read(self.parent/f'B7_development_{e:02d}.json') for e in range(1,7)]


class RemainingReaders(ReaderFactory):
    def __call__(self,role,epoch,ids,folder):
        if epoch not in (7,8,9) or Path(folder).name.split('_',1)[0]!='B7':raise PermissionError('Only B7 E7-E9 passes allowed')
        return super().__call__(role,epoch,ids,folder)


def close_b7(folder,p,commit):
    if query(folder/'updates.sqlite','SELECT model,state,COUNT(*),MIN(u),MAX(u) FROM updates GROUP BY model,state')!=[('B7','RETURNED',1440,2881,4320)]:raise RuntimeError('Recovery update ledger incomplete')
    seals=list(p['inherited_checkpoints']);total=files=0
    for e in (7,8,9):
        train=read(folder/f'B7_train_{e:02d}.json');dev=read(folder/f'B7_development_{e:02d}.json');seal=read(folder/f'B7_LAST_epoch_{e:02d}.receipt.json')
        if (train['updates'],seal['model'],seal['epoch'],seal['updates'],seal['code_commit'],seal['population_sha256'])!=(480*e,'B7',e,480*e,commit,p['data']['population_sha256']) or seal['validation_receipt_sha256']!=digest(dev) or sha(folder/f'B7_LAST_epoch_{e:02d}.pt')!=seal['checkpoint_sha256']:raise RuntimeError('New epoch seal differs')
        read(folder/f'B7_tail_{e:02d}.json');seals.append(seal)
        for role in ('train','dev'):
            r=read(folder/f'B7_{role}_reads_{e:02d}/pass_receipt.json');a=r['actual_reads']
            if r['during_failure'] or a['delivered_bytes']!=r['expected_bytes'] or a['opened_files']!=r['expected_files'] or a['states']!={'READ_COMPLETE':r['expected_files']}:raise RuntimeError('Incomplete new source pass')
            total+=a['delivered_bytes'];files+=a['opened_files']
    if (total+312828,files+1)!=(p['budget']['new_source_bytes_per_task'][0],p['budget']['new_source_files_per_task'][0]):raise RuntimeError('Recovery source closure differs')
    return dict(status='COMPLETE_TRAIN_AND_DEV_EVALUATION',model='B7',seed=2030,epochs=9,optimizer_updates=4320,segment_updates=1440,replay_updates=441,cumulative_attempt_updates=4761,inherited_epochs=6,inherited_code_commit=PARENT_COMMIT,code_commit=commit,endpoint='FIXED_EPOCH_9_LAST',checkpoints=seals,segment_source_bytes=total+312828,segment_source_files=files+1)


def worker(root,proposal,private,approval,commit,index):
    started=time.monotonic();p,v,a,prepared,inherited=checked(root,proposal,private,approval,commit);out=Path(v['output_root'])
    if type(index)!=int or not 0<=index<4:raise PermissionError('Only four listed tasks')
    binding=read(out/'authorization_binding.json')
    if binding['controller_pid']!=os.getppid() or binding['approval']!=a or read(out/f'task_{index+1}_claim.json')!=dict(index=index,controller_pid=os.getppid(),code_commit=commit):raise PermissionError('Live once-only parent required')
    kind,seed=TASKS[index]
    if os.environ.get('PYTHONHASHSEED')!=str(seed) or shutil.disk_usage(out).free<p['budget']['minimum_task_free_bytes']:raise RuntimeError('Seed/storage admission differs')
    if index:
        reference=out/f'B7_s{seed}' if kind=='B8' else Path(inherited['seed_references'][str(seed)])
        result=run_task(root,p,dict(inherited,output_root=str(out)),a,prepared,commit,kind,seed,started=started,pair_reference=reference,static_name=f'{kind}_s{seed}_static_source.sqlite')
        result.update(segment_updates=4320,replay_updates=0,segment_source_bytes=result['total_logical_source_bytes'],segment_source_files=result['total_logical_source_files'])
        write(out/f'{kind}_s{seed}/segment_completion.json',result);return result
    def deadline():
        if time.monotonic()-started>p['budget']['task_wall_seconds'][0]:raise RuntimeError('B7 remaining time cap; no retry')
    db=sqlite3.connect(out/'B7_s2030_static_source.sqlite');db.execute('CREATE TABLE jobs(id TEXT PRIMARY KEY,state TEXT)');db.execute("INSERT INTO jobs VALUES ('static','PENDING')");db.commit()
    source=Path(inherited['terrain'])/'B6_static.npz';meter=SourceMeter(db,{str(source):dict(bytes=312828,sha=p['static_source_sha256']['B7'],job_id='static')},max_files=1,max_bytes=312828);meter.active={path_key(source)}
    try:
        with meter.open(source,'rb') as stream:raw=stream.read()
        terrain=read(Path(inherited['terrain'])/'production_receipt.json');pack=unpack(raw,'B6',terrain);totals=meter.totals()
        with db:db.execute("UPDATE jobs SET state='COMPLETE'")
    finally:db.close()
    plan=PopulationPlan(prepared['private_inputs']['stage3_run'],prepared['private_inputs']['request'],root=root)
    state=B7Resume(dict(parent=str(Path(v['parent'])/'B7_s2030'),decision_id=a['decision_id'],data_identity=p['data'],checkpoint_sha256=p['checkpoint']['sha256'],prior_updates=3321,replayed_updates=441,proposal_sha256=p['proposal_sha256']))
    folder=out/'B7_s2030'
    PairedExecutor(plan,folder,decision=FormalDecision(a['decision_id'],2030,p['data']['population_sha256'],True,True,True),kinds=('B7',),recovery=state,deadline=deadline,tail_factory=lambda:TerrainTail(pack),code_commit=commit,pair_reference=state.parent,model_factory=model_factory(pack,terrain['scalers'],modulation_limit=p['scientific_choices']['modulation_limit'])).run(RemainingReaders(plan,prepared,a['decision_id'],allowed_models=('B7',),dynamic_transform=PhysicalDote(pack,DoteDefinition(**p['scientific_choices']['DOTE']))))
    result=close_b7(folder,p,commit);result['static_source_reads']=totals;deadline();write(folder/'completion.json',result);return result


def independent_admission(root):
    import importlib.util
    spec=importlib.util.spec_from_file_location('independent_host',root/HOST);host=importlib.util.module_from_spec(spec);spec.loader.exec_module(host);host.require_independent(host.host_identity())


def execute(root,proposal,private,approval,commit):
    # An invocation from the desktop's Job must stop before scope/source work.
    independent_admission(root)
    started=time.monotonic();p,v,a,prepared,inherited=checked(root,proposal,private,approval,commit);out=Path(v['output_root']);active=None;updates=bytes_=files=0
    if out.exists():raise PermissionError('Consumed recovery output; no restart')
    if shutil.disk_usage(out.parent).free<p['budget']['initial_free_bytes']:raise RuntimeError('Reserve96GiB without deleting history')
    admission=resources();out.mkdir(exist_ok=False);write(out/'authorization_binding.json',dict(approval=a,controller_pid=os.getpid(),admission=admission,recovery_parent=v['parent'],independent_host_verified=True))
    try:
        original.admit_source(prepared,out)
        for index,(kind,seed) in enumerate(TASKS):
            remaining=p['budget']['max_package_seconds']-(time.monotonic()-started)
            if remaining<=0:raise RuntimeError('Recovery package deadline')
            write(out/f'task_{index+1}_claim.json',dict(index=index,controller_pid=os.getpid(),code_commit=commit))
            env=dict(os.environ,PYTHONHASHSEED=str(seed),CUBLAS_WORKSPACE_CONFIG=':4096:8',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1',PYTHONUTF8='1')
            command=[sys.executable,'-B',str(root/ENTRY),'worker','--proposal',str(proposal),'--private-preparation',str(private),'--researcher-approval',str(approval),'--task-index',str(index)]
            with (out/f'{kind}_s{seed}_console.log').open('xb') as log:
                active=subprocess.Popen(command,cwd=root,env=env,stdout=log,stderr=subprocess.STDOUT,creationflags=worker_creation_flags())
                try:rc=active.wait(timeout=min(remaining,p['budget']['task_wall_seconds'][index]))
                except subprocess.TimeoutExpired:active.kill();active.wait();raise RuntimeError('Recovery deadline reached; no retry')
            active=None
            if rc:raise RuntimeError(f'{kind}/{seed} failed; later tasks NOT_STARTED')
            r=read(out/f'{kind}_s{seed}'/('completion.json' if index==0 else 'segment_completion.json'))
            if (r['status'],r['model'],r['seed'],r['optimizer_updates'],r['code_commit'],r['segment_updates'],r['segment_source_bytes'],r['segment_source_files'])!=('COMPLETE_TRAIN_AND_DEV_EVALUATION',kind,seed,4320,commit,p['budget']['new_task_updates'][index],p['budget']['new_source_bytes_per_task'][index],p['budget']['new_source_files_per_task'][index]):raise RuntimeError('Task closure identity or budget differs')
            updates+=r['segment_updates'];bytes_+=r['segment_source_bytes'];files+=r['segment_source_files']
            if kind=='B8':
                for name in ('paired_initial_identity.json','paired_orders.json'):
                    if read(out/f'B7_s{seed}'/name)!=read(out/f'B8_s{seed}'/name):raise RuntimeError('Within-seed pairing differs')
                write(out/f'paired_difference_s{seed}.json',paired_difference(read(out/f'B7_s{seed}/B7_development_09.json'),read(out/f'B8_s{seed}/B8_development_09.json')))
        if (updates,bytes_,files)!=(p['budget']['total_updates'],p['budget']['total_source_bytes'],p['budget']['total_source_files']):raise RuntimeError('Exact recovery package closure differs')
        original.summarize(out,inherited)
        if time.monotonic()-started>p['budget']['max_package_seconds']:raise RuntimeError('Recovery summary deadline')
        result=dict(status='COMPLETE_FOUR_MODELS_THREE_SEED_INNOVATION_SUMMARY',segment_updates=updates,cumulative_updates=3321+updates,logical_source_bytes=bytes_,logical_source_files=files,code_commit=commit,replay=441,proposal_sha256=p['proposal_sha256'])
        write(out/'completion.json',result);return result
    except BaseException as exc:
        if active is not None and active.poll() is None:active.kill();active.wait()
        write(out/'failure.json',dict(status='STOP_NO_FURTHER_AUTOMATIC_RETRY',error=type(exc).__name__+': '+str(exc),completed_segment_updates=updates,completed_source_bytes=bytes_,partial_task_counts='SEE_PRESERVED_LEDGERS_NOT_ZERO'));raise
