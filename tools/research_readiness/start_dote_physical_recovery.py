"""One explicitly approved B7_PERP_GRADIENT E5->E9 recovery; no preparation training."""
import argparse
from contextlib import closing
import hashlib
import json
import os
from pathlib import Path
import shutil
import sqlite3
import subprocess
import sys
import time

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'src'));sys.dont_write_bytecode=True
CONTROL='B7_PERP_GRADIENT'
ENTRY='tools/research_readiness/start_dote_physical_recovery.py'
STOP='docs/research_readiness/20261025/evidence/dote_physical_control_failure_20261031.json'
ORIGINAL='docs/research_readiness/20261025/evidence/dote_physical_control_training_proposal_20261030.json'
HOST='tools/research_readiness/start_independent_process.py'

def read(p):return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def sha(p):
    h=hashlib.sha256()
    with Path(p).open('rb') as f:
        for chunk in iter(lambda:f.read(1024**2),b''):h.update(chunk)
    return h.hexdigest()
def digest(x):return hashlib.sha256(json.dumps(x,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()
def write(p,x):
    with Path(p).open('x',encoding='utf-8') as f:json.dump(x,f,indent=2,allow_nan=False)
def query(p,sql):
    with closing(sqlite3.connect(Path(p).resolve().as_uri()+'?mode=ro',uri=True)) as db:return db.execute(sql).fetchall()

def budget(scope,prior,source_bytes):
    weather=4*sum(x['bytes_per_pass'] for x in scope.values());files=4*sum(x['file_count'] for x in scope.values())
    if (weather,files,source_bytes)!=(212254062672,63472,4705249):raise ValueError('Frozen E6-E9/source scope changed')
    return dict(new_updates=1920,replayed_updates=480,prior_returned=2880,saved_updates=2400,cumulative_attempts=4800,
        training_source_bytes=weather,training_source_instances=files,static_bytes=312828,static_instances=1,
        failed_source_verification_bytes=source_bytes,failed_source_verification_instances=1,
        total_source_bytes=weather+312828+source_bytes,total_source_files=files+2,
        cumulative_reserved_source_bytes=prior['reserved_logical_bytes']+weather+312828+source_bytes,
        cumulative_delivered_bytes_if_complete=prior['delivered_logical_bytes']+weather+312828+source_bytes,
        cumulative_source_instances=prior['opened_content_instances']+files+2,
        max_package_seconds=10800,minimum_initial_free_bytes=24*1024**3,minimum_task_free_bytes=24*1024**3,
        checkpoint_deserializations=1,checkpoint_rehashes_at_restore=1,additional_retry_allowance=0,
        clock_rule='Both UTC wall and monotonic; earlier deadline wins, clock rollback stops; wait checks every2s',
        prior_time_acceptance='NOT_VERIFIED_NO_RETROACTIVE_BUDGET_INCREASE',replay_allowance=480)

class Deadline:
    def __init__(self,wall,monotonic,seconds):self.wall=wall;self.monotonic=monotonic;self.seconds=seconds
    def remaining(self):
        wall=time.time()-self.wall;mono=time.monotonic()-self.monotonic
        if wall<0 or mono<0:raise RuntimeError('Clock rollback; stop without retry')
        left=self.seconds-max(wall,mono)
        if left<=0:raise RuntimeError('Recovery wall deadline reached; no retry')
        return left
    def __call__(self):self.remaining()

def wait_bounded(child,deadline):
    while True:
        try:return child.wait(timeout=min(2,deadline.remaining()))
        except subprocess.TimeoutExpired:continue

def validate_approval(a,p,v,commit):
    if p['tasks']!=[dict(model=CONTROL,seed=2029)] or (p['checkpoint']['epoch'],p['checkpoint']['updates'])!=(5,2400):
        raise PermissionError('Only the failed candidate seed2029 E5 recovery')
    expected=dict(approved_by_researcher=True,code_commit=commit,proposal_sha256=p['proposal_sha256'],tasks=p['tasks'],
        scientific_choices=p['scientific_choices'],budget=p['budget'],output_root=v['output_root'],
        approved_checkpoint_sha256=p['checkpoint']['sha256'],approved_replay_updates=480)
    if commit!=p['execution_code_commit'] or any(a.get(k)!=x for k,x in expected.items()) or not a.get('decision_id'):
        raise PermissionError('Explicit E5/480-replay/code/source/time recovery grant required')

def prepare(original_private,output,workspace):
    workspace=workspace.resolve();output=output.resolve();original_private=original_private.resolve()
    private=read(original_private);old=Path(private['output_root']);folder=old/'B7_s2029'
    original=read(ROOT/ORIGINAL);stop=read(ROOT/STOP);diagnostic=read(workspace/'source_metadata_preflight.json')
    checks=read(workspace/'targeted_checks.json')
    if checks.get('status')!='PASS' or checks.get('new_cpu_checks')!=8:raise ValueError('New recovery checks required')
    if stop['status']!='VERIFIED_STOPPED_PHYSICAL_CONTROL_INCOMPLETE_NO_RETRY':raise ValueError('Wrong failed parent')
    if diagnostic['check'].get('open_close') is not True or diagnostic['check'].get('same_path') is not True:raise RuntimeError('Source metadata admission failed')
    if query(folder/'updates.sqlite','SELECT state,COUNT(*),MIN(u),MAX(u) FROM updates GROUP BY state')!=[('RETURNED',2880,1,2880)]:raise ValueError('Later update evidence; do not duplicate')
    if (old/'completion.json').exists() or (folder/'B7_LAST_epoch_06.pt').exists():raise PermissionError('Unexpected later state')
    weight=folder/'B7_LAST_epoch_05.pt';seal=read(weight.with_suffix('.receipt.json'))
    if (seal['epoch'],seal['updates'],seal['code_commit'])!=(5,2400,original['execution_code_commit']) or sha(weight)!=seal['checkpoint_sha256']:raise ValueError('Actual E5 identity differs')
    parent=read(private['inherited_private'])
    from yuntapr.experimental.research_readiness.multiseed import load_inherited
    _,prepared=load_inherited(parent['inherited'])
    if prepared['data']!=original['data']:raise ValueError('Frozen data population differs')
    scope={r:{k:prepared['roles'][r][k] for k in ('file_count','bytes_per_pass')} for r in ('Train','Development')}
    caps=budget(scope,stop['source_accounting'],diagnostic['source_expected_bytes'])
    if output.exists() or output.parent!=old.parent:raise PermissionError('Fresh F-volume sibling required')
    free=shutil.disk_usage(output.parent).free
    if free<caps['minimum_initial_free_bytes']:raise RuntimeError('Need24GiB; preserve originals')
    from yuntapr.experimental.core_innovation.stage4.engine import resources
    admission=resources()
    h={n:sha(ROOT/n) for n in original['code_sha256']}
    if any(s!=original['code_sha256'][n] for n,s in h.items() if n!=HOST):raise ValueError('Frozen model/loss/reader/evaluator changed')
    for n in (ENTRY,'src/yuntapr/experimental/core_innovation/stage4/recovery.py','src/yuntapr/experimental/core_innovation/stage3/metered_io.py'):
        h[n]=sha(ROOT/n)
    names=['failure.json','B7_s2029/failure.json','B7_s2029/updates.sqlite','B7_s2029/paired_initial_identity.json','B7_s2029/paired_orders.json']
    names += [f'B7_s2029/B7_LAST_epoch_{e:02d}.receipt.json' for e in range(1,6)]
    names += [f'B7_s2029/B7_development_{e:02d}.json' for e in range(1,6)]
    pins={n:sha(old/n) for n in names}
    commit=subprocess.check_output(['git','-C',str(ROOT),'rev-parse','HEAD'],text=True).strip()
    p=dict(status='READY_WAITING_EXPLICIT_E5_RECOVERY_AND_480_REPLAY_APPROVAL',authorized=False,execution_code_commit=commit,
        tasks=[dict(model=CONTROL,seed=2029)],data=original['data'],protocol=original['protocol'],scientific_choices=original['scientific_choices'],
        budget=caps,checkpoint=dict(epoch=5,updates=2400,sha256=seal['checkpoint_sha256'],bytes=weight.stat().st_size,
            parent_commit=original['execution_code_commit'],actual_preparation_hash='PASS_ONE_E5_WEIGHT_NO_DESERIALIZATION'),
        parent_pins=pins,original_private_sha256=sha(original_private),original_proposal_sha256=original['proposal_sha256'],
        stop_receipt_sha256=sha(ROOT/STOP),code_sha256=h,source_scope_summary=scope,
        source_verification=dict(year=2024,bytes=diagnostic['source_expected_bytes'],expected_sha256=diagnostic['source_prior_sha256'],
            exact_source_path_sha256=hashlib.sha256(diagnostic['source_path'].encode()).hexdigest(),
            expected_sha_origin='Same source READ_COMPLETE in parent E5 Dev; not partial empty hash',
            metadata_preflight='PASS_RESOLVE_SIZE_OPEN_CLOSE_0_PAYLOAD',full_payload_preflight='WAITING_RECOVERY_GRANT'),
        resources=dict(admission,output_free_bytes=free,minimum_RAM_bytes=8*1024**3,minimum_GPU_free_bytes=5*1024**3,recheck_at_start=True),
        time_estimate=dict(hours=[1.7,2.5],hard_cap_hours=3,basis='4 epochs; first5 historical epochs about24.6min each, no new GPU benchmark'),
        power_diagnostic=dict(system_resumed_utc='2026-10-31T00:05:44.8258268Z',prior_sleep_utc='2026-10-30T19:03:23.6951477Z',
            provider='Microsoft-Windows-Power-Troubleshooter/Event1',raw_receipt_sha256=sha(workspace/'power_events.json'),
            inference='Low-power/resume confirmed; source I/O causal link NOT_VERIFIED'),
        inherited_metrics='19_COMPLETE_NO_RERUN',failure_policy='STOP_PRESERVE_ALL_NO_RETRY_NO_EXTRA_REPLAY',
        new_checks=dict(checks,receipt_sha256=sha(workspace/'targeted_checks.json'),test_code_sha256=sha(ROOT/'tests/research_readiness/test_physical_recovery.py')),
        preparation_activity=dict(weather_payload_bytes=0,checkpoint_deserializations=0,checkpoint_files_hashed=1,optimizer_updates=0),
        final_2025='FROZEN_NO_ACCESS')
    p['proposal_sha256']=digest(p)
    v=dict(output_root=str(output),parent=str(old),original_private=str(original_private),proposal_sha256=p['proposal_sha256'],
        diagnostic_private=str(workspace/'source_metadata_preflight.json'),source=dict(path=diagnostic['source_path'],year=2024,
        bytes=diagnostic['source_expected_bytes'],sha=diagnostic['source_prior_sha256']))
    return p,v

def checked(proposal,private,approval,commit):
    p,v,a=map(read,(proposal,private,approval));validate_approval(a,p,v,commit)
    if digest({k:x for k,x in p.items() if k!='proposal_sha256'})!=p['proposal_sha256'] or v['proposal_sha256']!=p['proposal_sha256']:raise ValueError('Proposal changed')
    if any(sha(ROOT/n)!=s for n,s in p['code_sha256'].items()) or sha(ROOT/STOP)!=p['stop_receipt_sha256']:raise ValueError('Code or stop receipt changed')
    if sha(v['original_private'])!=p['original_private_sha256'] or any(sha(Path(v['parent'])/n)!=s for n,s in p['parent_pins'].items()):raise ValueError('Parent dependencies changed')
    frozen=read(ROOT/ORIGINAL)
    if any(p[k]!=frozen[k] for k in ('data','protocol','scientific_choices')) or p['original_proposal_sha256']!=frozen['proposal_sha256']:raise ValueError('Frozen physical protocol changed')
    original=read(v['original_private']);parent=read(original['inherited_private'])
    from yuntapr.experimental.research_readiness.multiseed import load_inherited
    _,prepared=load_inherited(parent['inherited'])
    if prepared['data']!=p['data']:raise ValueError('Population changed')
    actual_scope={r:{k:prepared['roles'][r][k] for k in ('file_count','bytes_per_pass')} for r in ('Train','Development')}
    if actual_scope!=p['source_scope_summary'] or hashlib.sha256(v['source']['path'].encode()).hexdigest()!=p['source_verification']['exact_source_path_sha256'] or v['source']['sha']!=p['source_verification']['expected_sha256']:raise ValueError('Actual source scope or verification identity changed')
    files=prepared['roles']['Development']['files'];matches=[x for n,x in files.items() if os.path.normcase(n)==os.path.normcase(v['source']['path'])]
    if len(matches)!=1 or matches[0]['year']!=2024 or matches[0]['bytes']!=v['source']['bytes']:raise PermissionError('Only exact failed2024 source may be verified')
    if budget(p['source_scope_summary'],read(ROOT/STOP)['source_accounting'],v['source']['bytes'])!=p['budget']:raise ValueError('Exact recovery caps differ')
    return p,v,a,prepared,parent

class PhysicalResume:
    kinds=('B7',)
    def __init__(self,request):
        from yuntapr.experimental.core_innovation.stage4.recovery import ResumeState
        self.request=request;self.parent=Path(request['parent']);self.base=ResumeState(request)
    def completed_epochs(self,kind):
        if kind!='B7':raise PermissionError('Only the failed physical B7 candidate')
        return 5
    def validate(self,plan,decision):
        if plan.identity!=self.request['data_identity'] or decision.seed!=2029 or decision.decision_id!=self.request['decision_id']:raise PermissionError('Recovery population/decision differs')
    def check_initial(self,value):return self.base.check_initial(value)
    def check_orders(self,value):return self.base.check_orders(value)
    def ledger(self,path,identity):
        from yuntapr.experimental.core_innovation.stage4.recovery import RecoveryLedger
        return RecoveryLedger(path,dict(identity,recovery=self.request),offsets={'B7':2400},segment_cap=1920,prior_updates=2880,cumulative_cap=4800,allowed_models=self.kinds)
    def restore(self,kind,model,optimizer,groups):
        from yuntapr.experimental.core_innovation.stage4.recovery import restore_last
        self.completed_epochs(kind);weight=self.parent/'B7_LAST_epoch_05.pt'
        if sha(weight)!=self.request['checkpoint_sha256']:raise ValueError('Actual E5 changed')
        restore_last(weight,model,optimizer,groups,data_identity=self.request['data_identity'],epoch=5,updates=2400,kind='B7',seed=2029)
        return 2400,[read(self.parent/f'B7_development_{e:02d}.json') for e in range(1,6)]

def close_segment(folder,parent,p,commit):
    if query(folder/'updates.sqlite','SELECT model,state,COUNT(*),MIN(u),MAX(u) FROM updates GROUP BY model,state')!=[('B7','RETURNED',1920,2401,4320)]:raise RuntimeError('New update ledger incomplete')
    seals=[read(parent/f'B7_LAST_epoch_{e:02d}.receipt.json') for e in range(1,6)];total=count=0
    for e in range(6,10):
        train=read(folder/f'B7_train_{e:02d}.json');dev=read(folder/f'B7_development_{e:02d}.json');seal=read(folder/f'B7_LAST_epoch_{e:02d}.receipt.json')
        if (train['updates'],seal['epoch'],seal['updates'],seal['code_commit'])!=(e*480,e,e*480,commit) or seal['validation_receipt_sha256']!=digest(dev) or dev['source_identity']!=p['data']:raise RuntimeError('New epoch identity differs')
        if not (folder/f'B7_LAST_epoch_{e:02d}.pt').stat().st_size:raise RuntimeError('Missing checkpoint')
        read(folder/f'B7_tail_{e:02d}.json');seals.append(seal)
        for role in ('train','dev'):
            r=read(folder/f'B7_{role}_reads_{e:02d}/pass_receipt.json');a=r['actual_reads']
            if r['during_failure'] or a['states']!={'READ_COMPLETE':r['expected_files']} or a['opened_files']!=r['expected_files'] or a['delivered_bytes']!=a['reserved_bytes'] or a['delivered_bytes']!=r['expected_bytes']:raise RuntimeError('New source pass incomplete')
            total+=a['delivered_bytes'];count+=a['opened_files']
    if (total,count)!=(p['budget']['training_source_bytes'],p['budget']['training_source_instances']):raise RuntimeError('Training source closure differs')
    return dict(status='COMPLETE_TRAIN_AND_DEV_EVALUATION',model='B7',control_id=CONTROL,seed=2029,epochs=9,optimizer_updates=4320,
        segment_updates=1920,replay_updates=480,cumulative_attempt_updates=4800,inherited_epochs=5,inherited_code_commit=p['checkpoint']['parent_commit'],
        code_commit=commit,endpoint='FIXED_EPOCH_9_LAST',checkpoints=seals,training_source_bytes=total,training_source_instances=count,
        segment_source_bytes=p['budget']['total_source_bytes'],segment_source_files=p['budget']['total_source_files'])

def worker(p,v,a,prepared,parent,commit):
    from yuntapr.experimental.core_innovation.stage4.recovery import verify_source
    from yuntapr.experimental.core_innovation.stage3.metered_io import SourceMeter,path_key
    from yuntapr.experimental.core_innovation.stage4.data import PopulationPlan
    from yuntapr.experimental.core_innovation.stage4.engine import FormalDecision,PairedExecutor
    from yuntapr.experimental.core_innovation.stage4.launch import ReaderFactory
    from yuntapr.experimental.research_readiness.dynamic_training import TerrainTail
    from yuntapr.experimental.research_readiness.dynamic_terrain import DoteDefinition,model_factory
    from yuntapr.experimental.research_readiness.dote_physical_controls import PerpendicularGradientDote
    from yuntapr.experimental.research_readiness.static_training import unpack
    out=Path(v['output_root']);binding=read(out/'authorization_binding.json')
    if binding['controller_pid']!=os.getppid() or binding['approval']!=a:raise PermissionError('Live once-only parent required')
    if os.environ.get('PYTHONHASHSEED')!='2029' or shutil.disk_usage(out).free<p['budget']['minimum_task_free_bytes']:raise RuntimeError('Seed/storage admission differs')
    deadline=Deadline(binding['wall_started'],binding['monotonic_started'],10800);deadline()
    verification=out/'failed_source_verification';verification.mkdir(exist_ok=False)
    verify_source(dict(source=v['source']),verification,a['decision_id']);deadline()
    path=Path(parent['terrain'])/'B6_static.npz';db=sqlite3.connect(out/'B7_PERP_GRADIENT_static_source.sqlite')
    db.execute('CREATE TABLE jobs(id TEXT PRIMARY KEY,state TEXT)');db.execute("INSERT INTO jobs VALUES ('static','PENDING')");db.commit()
    meter=SourceMeter(db,{str(path):dict(bytes=312828,sha=read(ROOT/ORIGINAL)['static_source_sha256']['B7'],job_id='static')},max_files=1,max_bytes=312828);meter.active={path_key(path)}
    try:
        with meter.open(path,'rb') as f:raw=f.read()
        terrain=read(Path(parent['terrain'])/'production_receipt.json');pack=unpack(raw,'B6',terrain);totals=meter.totals()
        with db:db.execute("UPDATE jobs SET state='COMPLETE'")
    finally:db.close()
    plan=PopulationPlan(prepared['private_inputs']['stage3_run'],prepared['private_inputs']['request'],root=ROOT)
    state=PhysicalResume(dict(parent=str(Path(v['parent'])/'B7_s2029'),decision_id=a['decision_id'],data_identity=p['data'],checkpoint_sha256=p['checkpoint']['sha256'],prior_updates=2880,replayed_updates=480))
    class RemainingReaders(ReaderFactory):
        def __call__(self,role,epoch,ids,folder):
            validate_pass(role,epoch,Path(folder).name)
            return super().__call__(role,epoch,ids,folder)
    folder=out/'B7_s2029'
    PairedExecutor(plan,folder,decision=FormalDecision(a['decision_id'],2029,p['data']['population_sha256'],True,True,True),
        kinds=('B7',),recovery=state,deadline=deadline,tail_factory=lambda:TerrainTail(pack),code_commit=commit,
        pair_reference=state.parent,model_factory=model_factory(pack,terrain['scalers'],modulation_limit=p['scientific_choices']['modulation_limit'])).run(
            RemainingReaders(plan,prepared,a['decision_id'],allowed_models=('B7',),dynamic_transform=PerpendicularGradientDote(pack,DoteDefinition(**p['scientific_choices']['DOTE']))))
    result=close_segment(folder,state.parent,p,commit);result['static_source_reads']=totals;deadline();write(folder/'completion.json',result)

def validate_pass(role,epoch,name):
    expected=f'B7_{"train" if role=="Train" else "dev"}_reads_{epoch:02d}'
    if role not in ('Train','Development') or epoch not in (6,7,8,9) or name!=expected:raise PermissionError('Only failed candidate E6-E9 source passes')

def execute(p,v,a,prepared,parent,commit,proposal,private,approval):
    from yuntapr.experimental.core_innovation.stage4.engine import resources
    from yuntapr.experimental.research_readiness.multiseed import worker_creation_flags
    from yuntapr.experimental.core_innovation.stage4.evaluation import paired_difference
    import importlib.util
    spec=importlib.util.spec_from_file_location('recovery_host',ROOT/HOST);host=importlib.util.module_from_spec(spec);spec.loader.exec_module(host);host.require_independent(host.host_identity())
    out=Path(v['output_root']);active=None
    if out.exists():raise PermissionError('Consumed recovery output; no restart')
    if shutil.disk_usage(out.parent).free<24*1024**3:raise RuntimeError('Need24GiB; preserve originals')
    admission=resources();wall=time.time();mono=time.monotonic();deadline=Deadline(wall,mono,10800)
    out.mkdir(exist_ok=False);write(out/'authorization_binding.json',dict(approval=a,controller_pid=os.getpid(),admission=admission,code_commit=commit,control='PERPENDICULAR_GRADIENT_REAL_MASKS',wall_started=wall,monotonic_started=mono))
    try:
        command=[sys.executable,'-B',str(ROOT/ENTRY),'worker','--proposal',str(proposal.resolve()),'--private-preparation',str(private.resolve()),'--researcher-approval',str(approval.resolve())]
        with (out/'control_console.log').open('xb') as log:
            active=subprocess.Popen(command,cwd=ROOT,env=dict(os.environ),stdout=log,stderr=subprocess.STDOUT,creationflags=worker_creation_flags())
            rc=wait_bounded(active,deadline)
        active=None
        if rc:raise RuntimeError('Recovery worker failed; no retry')
        result=read(out/'B7_s2029/completion.json');deadline()
        new=read(out/'B7_s2029/B7_development_09.json');reference=read(Path(parent['historical_B7'])/'B7_development_09.json')
        difference=paired_difference(new,reference);difference['direction']='B7_REAL_MINUS_B7_PERP_GRADIENT'
        for group in difference['groups'].values():group['rain_strata_conditional_pinball_real_minus_perp']=group.pop('rain_strata_conditional_pinball_B4_minus_B3')
        write(out/'physical_control_paired_summary.json',dict(direction='B7_REAL_MINUS_B7_PERP_GRADIENT',difference=difference,single_seed=True,causal_claim=False))
        result.update(proposal_sha256=p['proposal_sha256'],wall_seconds=time.time()-wall,monotonic_seconds=time.monotonic()-mono)
        write(out/'completion.json',result)
    except BaseException as exc:
        if active is not None and active.poll() is None:active.kill();active.wait()
        write(out/'failure.json',dict(status='STOP_NO_RETRY_OR_REPLAY',error=type(exc).__name__+': '+str(exc),partial_counts='SEE_NEW_AND_OLD_LEDGERS_NOT_ZERO',wall_seconds=time.time()-wall));raise

def main():
    parser=argparse.ArgumentParser(description=__doc__);sub=parser.add_subparsers(dest='mode',required=True)
    q=sub.add_parser('prepare');q.add_argument('--original-private',type=Path,required=True);q.add_argument('--output-root',type=Path,required=True);q.add_argument('--workspace',type=Path,required=True)
    for mode in ('execute','worker'):sub.add_parser(mode).add_argument('--researcher-approval',type=Path,required=True)
    for q in sub.choices.values():q.add_argument('--proposal',type=Path,required=True);q.add_argument('--private-preparation',type=Path,required=True)
    a=parser.parse_args();os.chdir(ROOT)
    if a.mode=='prepare':
        if not a.workspace.resolve().is_relative_to(ROOT/'docs/research_readiness/.local') or not a.private_preparation.resolve().is_relative_to(ROOT/'docs/research_readiness/.local'):raise PermissionError('Keep private paths ignored')
        p,v=prepare(a.original_private,a.output_root,a.workspace);write(a.proposal,p);write(a.private_preparation,v);print(json.dumps(dict(status=p['status'],code=p['execution_code_commit'],proposal_sha256=p['proposal_sha256'],budget=p['budget'])));return
    if subprocess.check_output(['git','-C',str(ROOT),'status','--porcelain'],text=True).strip():raise PermissionError('Clean approved checkout required')
    commit=subprocess.check_output(['git','-C',str(ROOT),'rev-parse','HEAD'],text=True).strip();p,v,grant,prepared,parent=checked(a.proposal,a.private_preparation,a.researcher_approval,commit)
    if a.mode=='worker':worker(p,v,grant,prepared,parent,commit)
    else:execute(p,v,grant,prepared,parent,commit,a.proposal,a.private_preparation,a.researcher_approval)

if __name__=='__main__':main()
