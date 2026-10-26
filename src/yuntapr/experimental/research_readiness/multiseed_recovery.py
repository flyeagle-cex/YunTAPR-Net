"""Bounded B4/2030 E1 recovery, then the two untouched2031 models.

Uses the original restoration, read meter, offset ledger and training engine.
Preparation never deserializes historical weights or opens weather payloads.
"""
from pathlib import Path
import math
import os
import shutil
import sqlite3
import subprocess
import sys
import time

from ..core_innovation.stage3.planning import digest
from ..core_innovation.stage4.data import PopulationPlan,read,sha
from ..core_innovation.stage4.engine import PairedExecutor,FormalDecision,resources,write
from ..core_innovation.stage4.launch import ReaderFactory
from ..core_innovation.stage4.recovery import ResumeState,RecoveryLedger,restore_last,verify_source
from ..core_innovation.stage4.evaluation import paired_difference
from .multiseed import BUDGET,GIB,ENTRY,POPULATION_SHA,code_hashes,load_inherited,worker_creation_flags,BatchTail,endpoint,metric_values,aggregate_pairs

TASKS=(('B4',2030),('B3',2031),('B4',2031))
PARENT_COMMIT='52a8e90dcea156382d7f2c510c5891c78e610329'


def budget(prior,source_bytes,prior_seconds,b4_seconds):
    if (prior['returned_updates'],prior['reserved_source_bytes'],prior['source_files'])!=(5190,552318045013,165179):
        raise ValueError('Only this stopped package is covered')
    b4_cap=21600-b4_seconds
    if b4_cap<=0:raise RuntimeError('No remaining B4 wall-time allowance')
    source=26*(26424262556+26639253112)+source_bytes
    return dict(new_updates=12480,new_task_updates=[3840,4320,4320],replay_allowance=390,
        cumulative_updates=17670,prior_updates=5190,new_source_bytes=source,
        cumulative_source_bytes=prior['reserved_source_bytes']+source,
        new_source_files=26*(7918+7950)+1,cumulative_source_files=165179+26*(7918+7950)+1,
        verification_bytes=source_bytes,verification_files=1,checkpoint_loads=1,
        task_wall_seconds=[b4_cap,21600,21600],max_wall_seconds=min(b4_cap+43200,86400-prior_seconds),
        prior_wall_seconds=prior_seconds,prior_B4_wall_seconds=b4_seconds,
        minimum_initial_free_bytes=72*GIB,minimum_task_free_bytes=24*GIB,
        additional_retry_allowance=0,wall_accounting='Prior executed interval plus new recovery wall time; approval waiting excluded')


def prepare(root,original_private,output_root):
    root,output_root=Path(root),Path(output_root)
    v=read(original_private);old=Path(v['output_root'])
    stop_path=root/'docs/research_readiness/20261025/evidence/b3_b4_multiseed_stop.json';stop=read(stop_path)
    _,p=load_inherited(v['inherited_path'])
    if stop['training_commit']!=PARENT_COMMIT or stop['actual_totals']['returned_updates']!=5190:
        raise ValueError('Wrong stopped package evidence')
    # Inherit54 already audited metadata sources. Pin just the resume dependencies.
    pins={}
    names=['failure.json','B3_s2030/completion.json','B3_s2030/B3_development_09.json',
           'B3_s2030/paired_initial_identity.json','B3_s2030/paired_orders.json',
           'B4_s2030/updates.sqlite','B4_s2030/paired_initial_identity.json','B4_s2030/paired_orders.json',
           'B4_s2030/B4_LAST_epoch_01.receipt.json','B4_s2030/B4_train_01.json',
           'B4_s2030/B4_development_01.json','B4_s2030/B4_tail_01.json',
           'B4_s2030/B4_train_reads_02/reads.sqlite']
    for name in names:
        pins[name]=sha(old/name)
        key='package/failure.json' if name=='failure.json' else name
        if key in stop['sources'] and stop['sources'][key]!=pins[name]:raise ValueError('Previously verified parent changed')
    if read(old/'B3_s2030/completion.json')['status']!='COMPLETE_TRAIN_AND_DEV_EVALUATION':raise ValueError('B3 must stay completed')
    if (old/'B4_s2030/completion.json').exists() or any((old/f'{k}_s2031').exists() for k in ('B3','B4')):
        raise ValueError('Unexpected later progress; do not prepare duplicate work')
    db=sqlite3.connect((old/'B4_s2030/updates.sqlite').as_uri()+'?mode=ro',uri=True)
    rows=db.execute('SELECT model,state,COUNT(*),MIN(u),MAX(u) FROM updates GROUP BY model,state').fetchall();db.close()
    if rows!=[('B4','RETURNED',870,1,870)]:raise ValueError('Parent update state changed')
    db=sqlite3.connect((old/'B4_s2030/B4_train_reads_02/reads.sqlite').as_uri()+'?mode=ro',uri=True)
    bad=db.execute("SELECT path,expected_bytes,actual_bytes,sha256,state FROM file_io WHERE state!='READ_COMPLETE'").fetchall();db.close()
    if len(bad)!=1 or bad[0][4]!='INTENT':raise ValueError('Exact interrupted source required')
    path,n,actual,h,_=bad[0];source=dict(p['roles']['Train']['files'][path],path=path)
    if source['year']!=2023 or source['bytes']!=n or not Path(path).is_file() or Path(path).stat().st_size!=n:
        raise ValueError('Interrupted source outside pinned Train scope or missing')
    old_wall=math.ceil((old/'failure.json').stat().st_mtime-(old/'authorization_binding.json').stat().st_mtime)
    b4_wall=math.ceil((old/'failure.json').stat().st_mtime-(old/'task_2_claim.json').stat().st_mtime)
    caps=budget(stop['actual_totals'],n,old_wall,b4_wall)
    if output_root.exists() or not output_root.parent.is_dir():raise PermissionError('Fresh sibling output required')
    admission=resources();free=shutil.disk_usage(output_root.parent).free
    if free<caps['minimum_initial_free_bytes']:raise RuntimeError('Reserve72GiB without deleting history')
    original=read(root/'docs/research_readiness/20261025/evidence/b3_b4_multiseed_proposal.json')
    hashes=code_hashes(root)
    allowed={'src/yuntapr/experimental/research_readiness/multiseed.py',
             'src/yuntapr/experimental/core_innovation/stage4/engine.py',
             'src/yuntapr/experimental/core_innovation/stage4/recovery.py',ENTRY}
    if any(hashes.get(name)!=h for name,h in original['code_sha256'].items() if name not in allowed):
        raise ValueError('Unapproved scientific dependency changed')
    receipt=read(old/'B4_s2030/B4_LAST_epoch_01.receipt.json')
    if receipt['checkpoint_sha256']!=stop['tasks'][1]['latest_checkpoint_file_sha256_verified'] or receipt['updates']!=480:
        raise ValueError('Not the already verified E1 LAST')
    proposal=dict(status='READY_WAITING_LIMITED_RECOVERY_APPROVAL',tasks=[dict(model=k,seed=s) for k,s in TASKS],
        data=p['data'],budget=caps,checkpoint=dict(model='B4',seed=2030,epoch=1,updates=480,sha256=receipt['checkpoint_sha256'],
            parent_commit=PARENT_COMMIT,verification='INHERITED_PREVIOUS_ACTUAL_FILE_SHA; REHASH_BEFORE_FORMAL_LOAD'),
        source_verification={k:source[k] for k in ('bytes','sha','year','kind')},parent_pins=pins,
        original_private_file_sha256=sha(original_private),original_inherited_file_sha256=sha(v['inherited_path']),
        original_proposal_sha256=original['proposal_sha256'],stop_receipt_sha256=sha(stop_path),code_sha256=hashes,
        historical_endpoint_sha256=original['historical_endpoint_sha256'],
        inherited_unchanged_science_dependencies=len(original['code_sha256'])-len(allowed),
        admission=dict(admission,output_volume_free_bytes=free),raw_payload_reads=0,checkpoint_loads=0,optimizer_updates=0,authorized=False)
    proposal['proposal_sha256']=digest(proposal)
    private=dict(proposal_sha256=proposal['proposal_sha256'],original_private=str(Path(original_private).resolve()),
        parent=str(old),output_root=str(output_root.resolve()),source=source,historical_pair=v['historical_pair'])
    return proposal,private


def validate_approval(a,p,v,commit):
    expected=dict(approved_by_researcher=True,code_commit=commit,proposal_sha256=p['proposal_sha256'],
                  tasks=p['tasks'],budget=p['budget'],output_root=v['output_root'],
                  approved_checkpoint_sha256=p['checkpoint']['sha256'],approved_replay_updates=390)
    if any(a.get(k)!=x for k,x in expected.items()) or not isinstance(a.get('decision_id'),str) or not a['decision_id'].strip():
        raise PermissionError('Explicit new390-replay recovery/code/checkpoint/source budget approval required')


def checked(root,proposal_path,private_path,approval_path,commit):
    p,v,a=map(read,(proposal_path,private_path,approval_path))
    if digest({k:x for k,x in p.items() if k!='proposal_sha256'})!=p['proposal_sha256']:raise ValueError('Recovery proposal digest changed')
    validate_approval(a,p,v,commit)
    if v['proposal_sha256']!=p['proposal_sha256'] or code_hashes(root)!=p['code_sha256']:raise ValueError('Recovery code/private identity changed')
    if sha(v['original_private'])!=p['original_private_file_sha256']:raise ValueError('Original private binding changed')
    original=read(v['original_private'])
    if Path(original['output_root']).resolve()!=Path(v['parent']).resolve():raise ValueError('Recovery parent location changed')
    if sha(original['inherited_path'])!=p['original_inherited_file_sha256']:raise ValueError('Frozen scope binding changed')
    _,prepared=load_inherited(original['inherited_path'])
    if prepared['data']!=p['data'] or any(sha(Path(v['parent'])/n)!=h for n,h in p['parent_pins'].items()):
        raise ValueError('Frozen data or parent receipt changed')
    source=v['source'];expected=prepared['roles']['Train']['files'].get(source['path'])
    if expected is None or any(source[k]!=expected[k] for k in expected) or any(source[k]!=p['source_verification'][k] for k in p['source_verification']):
        raise ValueError('Single-source verification scope changed')
    if any(sha(Path(v['historical_pair'])/name)!=h for name,h in p['historical_endpoint_sha256'].items()):
        raise ValueError('Historical seed2029 endpoint changed')
    return p,v,a,prepared


class B4Resume(ResumeState):
    kinds=('B4',)
    def completed_epochs(self,kind):return 1 if kind=='B4' else 0
    def validate(self,plan,decision):
        if decision.seed!=2030 or decision.decision_id!=self.request['decision_id'] or plan.identity!=self.request['data_identity']:
            raise PermissionError('B4 recovery seed/decision/population changed')
    def ledger(self,path,identity):
        return RecoveryLedger(path,dict(identity,recovery=self.request),offsets={'B4':480},segment_cap=3840,prior_updates=870,cumulative_cap=4710)
    def restore(self,kind,model,optimizer,groups):
        if kind!='B4':raise PermissionError('Completed B3 cannot enter recovery')
        weight=self.parent/'B4_LAST_epoch_01.pt'
        if sha(weight)!=self.request['checkpoint_sha256']:raise ValueError('Historical LAST changed before load')
        restore_last(weight,model,optimizer,groups,data_identity=self.request['data_identity'],epoch=1,updates=480,kind='B4',seed=2030)
        report=read(self.parent/'B4_development_01.json')
        if digest(report)!=read(self.parent/'B4_LAST_epoch_01.receipt.json')['validation_receipt_sha256']:raise ValueError('Inherited Dev seal changed')
        return 480,[report]


def run_worker(root,proposal_path,private_path,approval_path,commit,index):
    start=time.monotonic();p,v,a,prepared=checked(root,proposal_path,private_path,approval_path,commit)
    if type(index)!=int or not 0<=index<3:raise PermissionError('Unlisted recovery task')
    package=Path(v['output_root']);old=Path(v['parent']);binding=read(package/'authorization_binding.json')
    if binding['controller_pid']!=os.getppid() or binding['approval']!=a or read(package/f'task_{index+1}_claim.json')!=dict(index=index,controller_pid=os.getppid(),code_commit=commit):
        raise PermissionError('Recovery must be dispatched once by its serial controller')
    kind,seed=TASKS[index]
    if os.environ.get('PYTHONHASHSEED')!=str(seed):raise PermissionError('Hash seed not set before startup')
    if shutil.disk_usage(package).free<p['budget']['minimum_task_free_bytes']:raise RuntimeError('Reserve24GiB per task')
    def deadline():
        if time.monotonic()-start>p['budget']['task_wall_seconds'][index]:raise RuntimeError('Approved recovery task deadline reached')
    if index==0:
        verification=package/'interrupted_source_verification';verification.mkdir(exist_ok=False)
        verify_source(dict(source=v['source']),verification,a['decision_id']);deadline()
    inputs=prepared['private_inputs'];plan=PopulationPlan(inputs['stage3_run'],inputs['request'],root=root)
    if plan.identity!=p['data']:raise ValueError('Frozen data population changed')
    decision=FormalDecision(a['decision_id'],seed,POPULATION_SHA,True,True,True)
    folder=package/f'{kind}_s{seed}';state=None
    if index==0:
        state=B4Resume(dict(parent=str(old/'B4_s2030'),data_identity=p['data'],decision_id=a['decision_id'],
            checkpoint_sha256=p['checkpoint']['sha256'],prior_updates=870,replayed_updates=390,
            parent_request_sha256=p['proposal_sha256']))
    class RemainingReaders(ReaderFactory):
        def __call__(self,role,epoch,ids,folder):
            if index==0 and epoch==1:raise PermissionError('Inherited E1 cannot be reread or retrained')
            return super().__call__(role,epoch,ids,folder)
    pair_ref=old/'B3_s2030' if index==0 else package/'B3_s2031' if kind=='B4' else None
    PairedExecutor(plan,folder,decision=decision,kinds=(kind,),recovery=state,deadline=deadline,
        tail_factory=BatchTail,code_commit=commit,pair_reference=pair_ref).run(RemainingReaders(plan,prepared,a['decision_id']))
    result=endpoint(folder,kind,seed,commit,inherited=old/'B4_s2030' if index==0 else None,
                    inherited_commit=PARENT_COMMIT if index==0 else None)
    result.update(segment_updates=p['budget']['new_task_updates'][index],replay_updates=390 if index==0 else 0,
        cumulative_attempt_updates=4710 if index==0 else 4320,
        cumulative_actual_source_bytes=499257862058 if index==0 else 477571641012,
        segment_source_bytes=(8 if index==0 else 9)*53063515668,
        segment_source_files=(8 if index==0 else 9)*15868,
        inherited_epochs=1 if index==0 else 0,inherited_code_commit=PARENT_COMMIT if index==0 else None)
    deadline();write(folder/'completion.json',result);return result


def summarize(package,old,historical):
    pairs={};endpoints={}
    for seed in (2029,2030,2031):
        bases={k:Path(historical) if seed==2029 else old/'B3_s2030' if seed==2030 and k=='B3' else package/f'{k}_s{seed}' for k in ('B3','B4')}
        reports={k:read(bases[k]/f'{k}_development_09.json') for k in ('B3','B4')}
        paired_difference(reports['B3'],reports['B4'])
        endpoints[str(seed)]={k:metric_values(r) for k,r in reports.items()}
        pairs[seed]={k:endpoints[str(seed)]['B4'][k]-endpoints[str(seed)]['B3'][k] for k in endpoints[str(seed)]['B3']}
    write(package/'three_seed_summary.json',dict(**aggregate_pairs(pairs),endpoints=endpoints))


def execute(root,proposal_path,private_path,approval_path,commit):
    start=time.monotonic();p,v,a,prepared=checked(root,proposal_path,private_path,approval_path,commit)
    package=Path(v['output_root']);old=Path(v['parent']);caps=p['budget']
    if package.exists():raise PermissionError('Recovery grant consumed; no further retry')
    if shutil.disk_usage(package.parent).free<caps['minimum_initial_free_bytes']:raise RuntimeError('Initial72GiB reserve unavailable')
    admission=resources();package.mkdir(exist_ok=False)
    write(package/'authorization_binding.json',dict(approval=a,controller_pid=os.getpid(),admission=admission,recovery_parent=str(old)))
    updates=files=bytes_=0;active=None
    try:
        for index,(kind,seed) in enumerate(TASKS):
            remaining=caps['max_wall_seconds']-(time.monotonic()-start)
            if remaining<=0:raise RuntimeError('Recovery package deadline reached')
            write(package/f'task_{index+1}_claim.json',dict(index=index,controller_pid=os.getpid(),code_commit=commit))
            env=dict(os.environ,PYTHONHASHSEED=str(seed),CUBLAS_WORKSPACE_CONFIG=':4096:8',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1',PYTHONUTF8='1')
            command=[sys.executable,'-B',str(root/ENTRY),'recovery-worker','--proposal',str(proposal_path),
                '--private-preparation',str(private_path),'--researcher-approval',str(approval_path),'--task-index',str(index)]
            with (package/f'{kind}_s{seed}_console.log').open('xb') as log:
                active=subprocess.Popen(command,cwd=root,env=env,stdout=log,stderr=subprocess.STDOUT,creationflags=worker_creation_flags())
                try:rc=active.wait(timeout=min(remaining,caps['task_wall_seconds'][index]))
                except subprocess.TimeoutExpired:
                    active.kill();active.wait();raise RuntimeError('Recovery wall-time limit; stop without retry')
            active=None
            if rc!=0:raise RuntimeError(f'{kind}/{seed} exited{rc}; later tasks NOT_STARTED')
            r=read(package/f'{kind}_s{seed}'/'completion.json')
            if (r['status']!='COMPLETE_TRAIN_AND_DEV_EVALUATION' or r['code_commit']!=commit
                    or r['segment_updates']!=caps['new_task_updates'][index]):raise RuntimeError('Recovery task seal differs')
            updates+=r['segment_updates'];files+=r['segment_source_files'];bytes_+=r['segment_source_bytes']
        verification=read(package/'interrupted_source_verification/source_verification_receipt.json')
        if verification['states']!={'READ_COMPLETE':1} or verification['delivered_bytes']!=caps['verification_bytes']:
            raise RuntimeError('Single-source verification seal differs')
        files+=1;bytes_+=verification['delivered_bytes']
        if (updates,files,bytes_)!=(caps['new_updates'],caps['new_source_files'],caps['new_source_bytes']):raise RuntimeError('Exact recovery budget closure differs')
        summarize(package,old,v['historical_pair'])
        if time.monotonic()-start>caps['max_wall_seconds']:raise RuntimeError('Recovery closure deadline reached')
        result=dict(status='COMPLETE_RECOVERED_PACKAGE_THREE_SEEDS',new_updates=updates,cumulative_updates=5190+updates,
            replay_updates=390,new_source_bytes=bytes_,cumulative_source_bytes=552318045013+bytes_,code_commit=commit)
        write(package/'completion.json',result);return result
    except BaseException as exc:
        if active is not None and active.poll() is None:active.kill();active.wait()
        write(package/'failure.json',dict(status='STOP_NO_FURTHER_AUTOMATIC_RETRY',error=type(exc).__name__+': '+str(exc),
            completed_segment_updates=updates,partial_task_counters='SEE_PRESERVED_TASK_LEDGERS_NOT_ZERO'))
        raise
