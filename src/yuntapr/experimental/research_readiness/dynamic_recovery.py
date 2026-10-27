"""Single approval-bound B8 E6 -> E9 continuation; no training in preparation."""
import math,os,shutil,sqlite3,subprocess,sys,time
from pathlib import Path
from ..core_innovation.stage3.planning import digest
from ..core_innovation.stage3.metered_io import SourceMeter,path_key
from ..core_innovation.stage4.data import PopulationPlan,read,sha
from ..core_innovation.stage4.engine import FormalDecision,PairedExecutor,resources,write
from ..core_innovation.stage4.recovery import ResumeState,RecoveryLedger,restore_last,query
from ..core_innovation.stage4.launch import ReaderFactory
from ..core_innovation.stage4.evaluation import paired_difference
from .dynamic_training import hashes as dynamic_hashes,TerrainTail
from .dynamic_terrain import PhysicalDote,DoteDefinition,model_factory
from .static_training import unpack
from .multiseed import load_inherited,metric_values,worker_creation_flags

ENTRY='tools/research_readiness/start_b8_recovery.py'
MODULE='src/yuntapr/experimental/research_readiness/dynamic_recovery.py'
ORIGINAL='b1f072e45fdd17b80106a774083995c350b28f04'
READY='docs/research_readiness/20261025/evidence/'
STOP=READY+'b7_b8_terminal_20261028.json'
DIAGNOSTIC=READY+'b8_source_diagnostic_20261028.json'
ALLOWED_CHANGES={'src/yuntapr/experimental/core_innovation/stage4/engine.py','src/yuntapr/experimental/core_innovation/stage4/recovery.py'}

def hashes(root):
 h=dynamic_hashes(root);h.update({n:sha(root/n) for n in (ENTRY,MODULE)});return h

def diagnostic_access(d):
 # The first unmodified receipt compared original spelling case-sensitively.
 # Windows canonicalization changed case only: same_path already uses normcase.
 c=d['checks']
 return (len(c)==5 and all(x['status']=='PASS' for x in c) and c[1]['result']['bytes']==d['expected_bytes']
         and c[2]['result']['same_path'] and c[4]['result']['stable_metadata'] and c[4]['result']['delivered_bytes']==4096)

def budget(prepared,stop,diagnostic):
 b=3*sum(x['bytes_per_pass'] for x in prepared['roles'].values());n=3*sum(x['file_count'] for x in prepared['roles'].values())
 if (b,n)!=(159190547004,47604):raise ValueError('Frozen E7-E9 source budget drift')
 prior=stop['budget_closure'];seconds=21600-math.ceil(stop['tasks'][1]['wall_seconds_mtime_proxy'])
 if seconds<=0:raise RuntimeError('No original B8 six-hour time remaining')
 return dict(new_updates=1440,replayed_updates=62,prior_B8_returned=2942,saved_B8_updates=2880,
             cumulative_B8_attempts=4382,cumulative_package_attempts=prior['returned_updates']+1440,
             new_training_source_bytes=b,new_training_source_files=n,new_static_source_bytes=312828,new_static_source_files=1,
             new_source_bytes=b+312828,new_source_files=n+1,diagnostic_bytes_already_spent=diagnostic['actual_payload_bytes'],
             diagnostic_files_already_spent=diagnostic['actual_payload_files'],additional_diagnostic_payload_bytes=0,
             cumulative_source_bytes=prior['actual_source_bytes']+b+312828+diagnostic['actual_payload_bytes'],
             cumulative_source_files=prior['actual_source_files']+n+1+diagnostic['actual_payload_files'],
             max_wall_seconds=seconds,prior_B8_wall_seconds_ceil=21600-seconds,
             minimum_initial_free_bytes=24*1024**3,minimum_task_free_bytes=24*1024**3,
             checkpoint_deserializations=1,checkpoint_SHA_reads=1,additional_retry_allowance=0,
             wall_accounting='B8 prior elapsed ceil plus new controller time <=21600s; approval waiting excluded')

def prepare(root,original_private,output):
 root,output=Path(root),Path(output);v=read(original_private);old=Path(v['output_root'])
 stop=read(root/STOP);original=read(root/(READY+'b7_b8_training_proposal.json'));d=read(root/DIAGNOSTIC)
 if stop['training_commit']!=ORIGINAL or stop['status']!='VERIFIED_B7_COMPLETE_B8_FAILED_PARTIAL_PACKAGE':raise ValueError('Wrong inherited stop')
 if not diagnostic_access(d):raise RuntimeError('Failed source is not currently accessible within bounded diagnostic')
 _,prepared=load_inherited(v['inherited'])
 if prepared['data']!=original['data']:raise ValueError('Frozen population drift')
 if query(old/'B8_s2029/updates.sqlite','SELECT model,state,COUNT(*),MIN(u),MAX(u) FROM updates GROUP BY model,state')!=[('B8','RETURNED',2942,1,2942)]:raise ValueError('Parent update state changed')
 caps=budget(prepared,stop,d);pins={}
 names=['failure.json','B8_s2029/failure.json','B8_s2029/updates.sqlite','B8_s2029/paired_initial_identity.json','B8_s2029/paired_orders.json',
        'B8_s2029/B8_LAST_epoch_06.receipt.json','B7_s2029/completion.json','B7_s2029/B7_development_09.json','B7_s2029/B7_tail_09.json']
 names += [f'B8_s2029/B8_development_{e:02d}.json' for e in range(1,7)]
 for name in names:
  pins[name]=sha(old/name)
  alias=name.replace('_s2029','').replace('B8/B8_','B8/').replace('B7/B7_','B7/')
  if name=='failure.json':alias='PACKAGE/failure.json'
  if alias in stop['sources'] and pins[name]!=stop['sources'][alias]['sha256']:raise ValueError('Inherited dependency changed')
 if (old/'completion.json').exists() or (old/'B8_s2029/completion.json').exists():raise PermissionError('Later completion exists; do not duplicate')
 checkpoint=stop['tasks'][1];weight=old/'B8_s2029/B8_LAST_epoch_06.pt'
 if weight.stat().st_size!=stop['sources']['B8/LAST_epoch_06.pt']['bytes']:raise ValueError('E6 file size changed')
 h=hashes(root)
 if any(h.get(n)!=s for n,s in original['code_sha256'].items() if n not in ALLOWED_CHANGES):raise ValueError('Frozen scientific code changed')
 if output.exists() or output.parent!=old.parent:raise PermissionError('Fresh sibling directory required')
 admission=resources();free=shutil.disk_usage(output.parent).free
 if free<caps['minimum_initial_free_bytes']:raise RuntimeError('Reserve24GiB; do not delete originals')
 proposal=dict(status='READY_WAITING_EXPLICIT_B8_RECOVERY_AND_62_REPLAY_APPROVAL',authorized=False,tasks=[dict(model='B8',seed=2029)],
               data=original['data'],protocol=original['protocol'],scientific_choices=original['scientific_choices'],budget=caps,
               checkpoint=dict(model='B8',seed=2029,epoch=6,updates=2880,sha256=checkpoint['last_saved_sha256'],bytes=weight.stat().st_size,parent_commit=ORIGINAL,
                               preparation='INHERIT_PREVIOUS_ACTUAL_SHA_NO_DESERIALIZATION',execution='ONE_REHASH_AND_ONE_LOAD_BEFORE_E7'),
               stop_receipt_sha256=sha(root/STOP),original_proposal_sha256=original['proposal_sha256'],diagnostic_receipt_sha256=sha(root/DIAGNOSTIC),
               diagnostic_interpretation=dict(current_path_and_4KiB_access='PASS',case_only_resolved_spelling_difference=True,
                                              correction='same_path=true is Windows normcase; raw summary BLOCKED was a case-sensitive diagnostic predicate error',
                                              repeated_source_reads=0,historical_failure_cause='NOT_VERIFIED'),
               original_private_sha256=sha(original_private),inherited_private_sha256=sha(v['inherited']),parent_pins=pins,code_sha256=h,
               resources=dict(admission,output_free_bytes=free,recheck_at_start=True),
               time_estimate=dict(hours=[1.5,2.1],basis='Actual B8 2942-update elapsed, including Dev and I/O; not a new GPU benchmark'),
               preparation_activity=dict(raw_source_files=1,raw_source_bytes=4096,checkpoint_deserializations=0,optimizer_updates=0,inference=0,old_full_audits=0),
               final_2025='FROZEN_NO_ACCESS')
 proposal['proposal_sha256']=digest(proposal)
 private=dict(proposal_sha256=proposal['proposal_sha256'],original_private=str(Path(original_private).resolve()),parent=str(old),output_root=str(output.resolve()))
 return proposal,private

def validate_approval(a,p,v,commit):
 expected=dict(approved_by_researcher=True,code_commit=commit,proposal_sha256=p['proposal_sha256'],tasks=p['tasks'],budget=p['budget'],
               output_root=v['output_root'],approved_checkpoint_sha256=p['checkpoint']['sha256'],approved_replay_updates=62)
 if any(a.get(k)!=x for k,x in expected.items()) or not isinstance(a.get('decision_id'),str) or not a['decision_id'].strip():raise PermissionError('Explicit B8/E6/62-replay/code/budget approval required')

def checked(root,proposal,private,approval,commit):
 p,v,a=map(read,(proposal,private,approval));validate_approval(a,p,v,commit)
 if digest({k:x for k,x in p.items() if k!='proposal_sha256'})!=p['proposal_sha256'] or v['proposal_sha256']!=p['proposal_sha256'] or hashes(root)!=p['code_sha256']:raise ValueError('Frozen recovery code/proposal changed')
 if sha(v['original_private'])!=p['original_private_sha256'] or sha(root/STOP)!=p['stop_receipt_sha256'] or sha(root/DIAGNOSTIC)!=p['diagnostic_receipt_sha256']:raise ValueError('Inherited identity changed')
 original=read(v['original_private'])
 if original['output_root']!=v['parent'] or sha(original['inherited'])!=p['inherited_private_sha256']:raise ValueError('Original scope changed')
 _,prepared=load_inherited(original['inherited'])
 if prepared['data']!=p['data'] or any(sha(Path(v['parent'])/n)!=s for n,s in p['parent_pins'].items()):raise ValueError('Data or parent dependency changed')
 if budget(prepared,read(root/STOP),read(root/DIAGNOSTIC))!=p['budget']:raise ValueError('Exact caps changed')
 return p,v,a,prepared,original

class B8Resume(ResumeState):
 kinds=('B8',)
 def completed_epochs(self,kind):
  if kind!='B8':raise PermissionError('B7 is complete and cannot be retrained')
  return 6
 def validate(self,plan,decision):
  if plan.identity!=self.request['data_identity'] or decision.seed!=2029 or decision.decision_id!=self.request['decision_id']:raise PermissionError('B8 recovery population/decision changed')
 def ledger(self,path,identity):
  return RecoveryLedger(path,dict(identity,recovery=self.request),offsets={'B8':2880},segment_cap=1440,prior_updates=2942,cumulative_cap=4382,allowed_models=self.kinds)
 def restore(self,kind,model,optimizer,groups):
  self.completed_epochs(kind);weight=self.parent/'B8_LAST_epoch_06.pt'
  if sha(weight)!=self.request['checkpoint_sha256']:raise ValueError('E6 changed before load')
  restore_last(weight,model,optimizer,groups,data_identity=self.request['data_identity'],epoch=6,updates=2880,kind='B8',seed=2029)
  reports=[read(self.parent/f'B8_development_{e:02d}.json') for e in range(1,7)]
  return 2880,reports

class RemainingReaders(ReaderFactory):
 def __call__(self,role,epoch,ids,folder):
  if epoch not in (7,8,9) or Path(folder).name.split('_',1)[0]!='B8':raise PermissionError('Only B8 E7-E9 source passes allowed')
  return super().__call__(role,epoch,ids,folder)

def close_segment(root,folder,old,p,commit):
 # Six epoch seals are already verified; do not hash all historical weights again.
 stop=read(root/STOP);seals=[x['checkpoint'] for x in stop['epochs'] if x['model']=='B8'];total=files=0
 if len(seals)!=6:raise ValueError('Six inherited epochs required')
 if query(folder/'updates.sqlite','SELECT model,state,COUNT(*),MIN(u),MAX(u) FROM updates GROUP BY model,state')!=[('B8','RETURNED',1440,2881,4320)]:raise RuntimeError('Recovery update ledger incomplete')
 for e in (7,8,9):
  train=read(folder/f'B8_train_{e:02d}.json');dev=read(folder/f'B8_development_{e:02d}.json');seal=read(folder/f'B8_LAST_epoch_{e:02d}.receipt.json')
  if (train['updates'],seal['model'],seal['epoch'],seal['updates'],seal['code_commit'],seal['population_sha256'])!=(480*e,'B8',e,480*e,commit,p['data']['population_sha256']) or seal['validation_receipt_sha256']!=digest(dev) or sha(folder/f'B8_LAST_epoch_{e:02d}.pt')!=seal['checkpoint_sha256']:raise RuntimeError('New epoch seal mismatch')
  read(folder/f'B8_tail_{e:02d}.json');seals.append(seal)
  for role in ('train','dev'):
   r=read(folder/f'B8_{role}_reads_{e:02d}/pass_receipt.json');a=r['actual_reads']
   if r['during_failure'] or a['delivered_bytes']!=r['expected_bytes'] or a['opened_files']!=r['expected_files'] or a['states']!={'READ_COMPLETE':r['expected_files']}:raise RuntimeError('Unsealed new source pass')
   total+=a['delivered_bytes'];files+=a['opened_files']
 if (total,files)!=(p['budget']['new_training_source_bytes'],p['budget']['new_training_source_files']):raise RuntimeError('New source cap closure differs')
 return dict(status='COMPLETE_TRAIN_AND_DEV_EVALUATION',model='B8',seed=2029,epochs=9,optimizer_updates=4320,segment_updates=1440,replay_updates=62,
             cumulative_attempt_updates=4382,inherited_epochs=6,inherited_code_commit=ORIGINAL,code_commit=commit,endpoint='FIXED_EPOCH_9_LAST',checkpoints=seals,
             segment_source_bytes=total+312828,segment_source_files=files+1,logical_effective_weather_bytes=477571641012)

def worker(root,proposal,private,approval,commit):
 started=time.monotonic();p,v,a,prepared,original=checked(root,proposal,private,approval,commit);package=Path(v['output_root']);old=Path(v['parent'])
 binding=read(package/'authorization_binding.json');claim=read(package/'task_1_claim.json')
 if binding['controller_pid']!=os.getppid() or binding['approval']!=a or claim!=dict(controller_pid=os.getppid(),code_commit=commit):raise PermissionError('Live once-only parent required')
 if os.environ.get('PYTHONHASHSEED')!='2029' or shutil.disk_usage(package).free<p['budget']['minimum_task_free_bytes']:raise RuntimeError('Seed or storage admission differs')
 def deadline():
  if time.monotonic()-started>p['budget']['max_wall_seconds']:raise RuntimeError('B8 recovery wall cap; no retry')
 # One new static read is explicit in the new budget. Weather DOTE uses the same delivered GFS.
 path=Path(original['terrain'])/'B6_static.npz';db=sqlite3.connect(package/'B8_static_source.sqlite');db.execute('CREATE TABLE jobs(id TEXT PRIMARY KEY,state TEXT)');db.execute("INSERT INTO jobs VALUES ('static','PENDING')");db.commit()
 source_sha=read(root/(READY+'b7_b8_training_proposal.json'))['static_source_sha256']['B8']
 meter=SourceMeter(db,{str(path):dict(bytes=312828,sha=source_sha,job_id='static')},max_files=1,max_bytes=312828);meter.active={path_key(path)}
 try:
  with meter.open(path,'rb') as f:raw=f.read()
  terrain=read(Path(original['terrain'])/'production_receipt.json');pack=unpack(raw,'B6',terrain);totals=meter.totals()
  with db:db.execute("UPDATE jobs SET state='COMPLETE'")
 finally:db.close()
 plan=PopulationPlan(prepared['private_inputs']['stage3_run'],prepared['private_inputs']['request'],root=root)
 state=B8Resume(dict(parent=str(old/'B8_s2029'),decision_id=a['decision_id'],data_identity=p['data'],checkpoint_sha256=p['checkpoint']['sha256'],prior_updates=2942,replayed_updates=62,proposal_sha256=p['proposal_sha256']))
 folder=package/'B8_s2029';decision=FormalDecision(a['decision_id'],2029,p['data']['population_sha256'],True,True,True)
 PairedExecutor(plan,folder,decision=decision,kinds=('B8',),recovery=state,deadline=deadline,tail_factory=lambda:TerrainTail(pack),code_commit=commit,
                pair_reference=old/'B8_s2029',model_factory=model_factory(pack,terrain['scalers'],modulation_limit=p['scientific_choices']['modulation_limit'])).run(
                  RemainingReaders(plan,prepared,a['decision_id'],allowed_models=('B8',),dynamic_transform=PhysicalDote(pack,DoteDefinition(**p['scientific_choices']['DOTE']))))
 result=close_segment(root,folder,old,p,commit);result['static_source_reads']=totals;deadline();write(folder/'completion.json',result);return result

def summarize(package,old,original):
 reports={m:read(path) for m,path in original['baseline_paths'].items()}
 reports.update(B7=read(old/'B7_s2029/B7_development_09.json'),B8=read(package/'B8_s2029/B8_development_09.json'))
 pairs={}
 for target,base in (('B7','B6'),('B8','B6'),('B8','B7'),('B7','B4'),('B8','B4')):
  paired_difference(reports[base],reports[target]);t,b=metric_values(reports[target]),metric_values(reports[base]);pairs[target+'_minus_'+base]={k:t[k]-b[k] for k in b}
 write(package/'innovation_paired_summary.json',dict(seed=2029,endpoint='FIXED_EPOCH_9_LAST',values={m:metric_values(r) for m,r in reports.items()},differences=pairs,descriptive_only=True,significance='NOT_CLAIMED'))

def execute(root,proposal,private,approval,commit):
 start=time.monotonic();p,v,a,_,original=checked(root,proposal,private,approval,commit);package=Path(v['output_root']);active=None
 if package.exists():raise PermissionError('Recovery approval consumed; no restart')
 if shutil.disk_usage(package.parent).free<p['budget']['minimum_initial_free_bytes']:raise RuntimeError('Reserve24GiB without deleting history')
 admission=resources();package.mkdir(exist_ok=False);write(package/'authorization_binding.json',dict(approval=a,controller_pid=os.getpid(),admission=admission))
 try:
  write(package/'task_1_claim.json',dict(controller_pid=os.getpid(),code_commit=commit))
  env=dict(os.environ,PYTHONHASHSEED='2029',CUBLAS_WORKSPACE_CONFIG=':4096:8',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1',PYTHONUTF8='1')
  cmd=[sys.executable,'-B',str(root/ENTRY),'worker','--proposal',str(proposal),'--private-preparation',str(private),'--researcher-approval',str(approval)]
  with (package/'B8_console.log').open('xb') as log:
   active=subprocess.Popen(cmd,cwd=root,env=env,stdout=log,stderr=subprocess.STDOUT,creationflags=worker_creation_flags())
   try:rc=active.wait(timeout=max(0.001,p['budget']['max_wall_seconds']-(time.monotonic()-start)))
   except subprocess.TimeoutExpired:active.kill();active.wait();raise RuntimeError('Recovery deadline reached; no retry')
  active=None
  if rc:raise RuntimeError('B8 recovery failed; no automatic restart')
  r=read(package/'B8_s2029/completion.json')
  if (r['status'],r['model'],r['seed'],r['epochs'],r['optimizer_updates'],r['code_commit'])!=('COMPLETE_TRAIN_AND_DEV_EVALUATION','B8',2029,9,4320,commit) or r['segment_updates']!=1440 or r['segment_source_bytes']!=p['budget']['new_source_bytes'] or r['segment_source_files']!=p['budget']['new_source_files']:raise RuntimeError('Recovery closure differs')
  summarize(package,Path(v['parent']),original)
  if time.monotonic()-start>p['budget']['max_wall_seconds']:raise RuntimeError('Recovery closure deadline')
  write(package/'completion.json',dict(status='COMPLETE_TRAIN_AND_DEV_EVALUATION',code_commit=commit,proposal_sha256=p['proposal_sha256'],segment_updates=1440,replayed_updates=62,budget=p['budget']))
 except BaseException as exc:
  if active is not None and active.poll() is None:active.kill();active.wait()
  write(package/'failure.json',dict(status='STOP_NO_AUTOMATIC_RETRY',error=type(exc).__name__+': '+str(exc),partial_counts='SEE_PRESERVED_LEDGERS'));raise
