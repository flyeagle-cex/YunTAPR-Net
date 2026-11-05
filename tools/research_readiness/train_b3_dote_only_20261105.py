"""A single, proposal-bound B3_DOTE_ONLY experiment; no automatic retry.

The existing Stage4 optimizer, loss, sample order, evaluation and source reader
are reused. No old model, reader whitelist or training campaign is modified.
"""
import argparse,gc,hashlib,io,json,math,os,random,shutil,sqlite3,sys,time
from datetime import datetime,timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'src'));sys.dont_write_bytecode=True
KIND='B3_DOTE_ONLY'


def read(p):return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def digest(x):return hashlib.sha256(json.dumps(x,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()
def now():return datetime.now(timezone.utc).isoformat()
def write(p,x):
    with Path(p).open('x',encoding='utf-8') as h:json.dump(x,h,ensure_ascii=False,indent=2,allow_nan=False)
def status(p,x):Path(p).write_text(json.dumps(x,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8')


def working_set_bytes():
    """Native Windows RSS monitor; no optional environment/package dependency."""
    import ctypes
    from ctypes import wintypes
    class Counters(ctypes.Structure):
        _fields_=[('cb',wintypes.DWORD),('PageFaultCount',wintypes.DWORD)]+[(name,ctypes.c_size_t) for name in (
            'PeakWorkingSetSize','WorkingSetSize','QuotaPeakPagedPoolUsage','QuotaPagedPoolUsage',
            'QuotaPeakNonPagedPoolUsage','QuotaNonPagedPoolUsage','PagefileUsage','PeakPagefileUsage')]
    kernel=ctypes.WinDLL('kernel32',use_last_error=True);api=ctypes.WinDLL('psapi',use_last_error=True)
    kernel.GetCurrentProcess.restype=wintypes.HANDLE
    api.GetProcessMemoryInfo.argtypes=[wintypes.HANDLE,ctypes.POINTER(Counters),wintypes.DWORD]
    api.GetProcessMemoryInfo.restype=wintypes.BOOL
    value=Counters();value.cb=ctypes.sizeof(value)
    if not api.GetProcessMemoryInfo(kernel.GetCurrentProcess(),ctypes.byref(value),value.cb):raise ctypes.WinError(ctypes.get_last_error())
    return int(value.WorkingSetSize)


def validate_proposal(path,approval):
    p=read(path);a=read(approval)
    if digest({k:v for k,v in p.items() if k!='proposal_sha256'})!=p['proposal_sha256']:raise ValueError('Proposal identity changed')
    if a.get('approved_by_researcher') is not True or not a.get('actual_researcher_reply') or a.get('proposal_sha256')!=p['proposal_sha256'] or a.get('budget')!=p['budget']:
        raise PermissionError('Explicit current new-training budget approval required')
    for name,expected in p['code_sha256'].items():
        if sha(ROOT/name)!=expected:raise ValueError('Bound code changed: '+name)
    for name,item in p['metadata'].items():
        if sha(item['path'])!=item['sha256']:raise ValueError('Bound metadata changed: '+name)
    if p['protocol']['seed']!=2029 or p['protocol']['epochs']!=9 or p['budget']['optimizer_updates']!=4320:raise PermissionError('Only one declared full experiment')
    return p,a


class PointMetrics:
    def __init__(self):
        self.n=0;self.squared_sum=0.;self.bias_sum=0.;self.counts={str(t):dict(TP=0,FP=0,FN=0,TN=0) for t in (.1,1.,5.,10.,20.)}
    def add(self,out,b):
        import numpy as np
        mask=(b.valid&b.region).detach().cpu().numpy()[:,0]
        y=b.rate.detach().cpu().numpy()[:,0][mask].astype(np.float64)
        p=out.rain_prob.detach().double().cpu().numpy()[:,0][mask]
        q=out.conditional_quantiles_log.detach().double().cpu().numpy().transpose(0,2,3,1)[mask]
        point=p*np.expm1(q).mean(axis=-1)
        if not np.isfinite(point).all():raise FloatingPointError('Nonfinite approximate expected rainfall')
        error=point-y;self.n+=len(y);self.squared_sum+=float(np.dot(error,error));self.bias_sum+=float(error.sum())
        for key,c in self.counts.items():
            t=np.float32(float(key));a=y.astype(np.float32)>t;z=point.astype(np.float32)>t
            for k,n in dict(TP=np.count_nonzero(a&z),FP=np.count_nonzero(~a&z),FN=np.count_nonzero(a&~z),TN=np.count_nonzero(~a&~z)).items():c[k]+=int(n)
    def finish(self):
        from stage_evaluation_20261105 import rates
        return dict(n_valid=self.n,rmse_mm_h=math.sqrt(self.squared_sum/self.n),bias_mm_h=self.bias_sum/self.n,
            squared_sum=self.squared_sum,bias_sum=self.bias_sum,counts=self.counts,metrics={t:rates(c) for t,c in self.counts.items()},
            point_rule='RESEARCHER_CONFIRMED_PROBABILITY_TIMES_MEAN_PHYSICAL_32_QUANTILES_APPROXIMATION',classification='FLOAT32_STRICT_GREATER')


def train(p,a,out):
    import numpy as np
    import torch
    from yuntapr.experimental.core_innovation.stage4.data import PopulationPlan,BatchReader
    from yuntapr.experimental.core_innovation.stage4.launch import PassReader
    from yuntapr.experimental.core_innovation.stage4.engine import epoch_order,lr_for_update,cpu_tree,state_digest
    from yuntapr.experimental.core_innovation.stage4.evaluation import Evaluation,paired_difference
    from yuntapr.experimental.core_innovation.stage3.metered_io import SourceMeter,path_key
    from yuntapr.experimental.research_readiness.static_training import unpack
    from yuntapr.experimental.research_readiness.dynamic_terrain import PhysicalDote,DoteDefinition
    from yuntapr.experimental.research_readiness.dote_without_mee import create
    from yuntapr.experimental.research_readiness.multiseed import BatchTail
    from yuntapr.experimental.phase_b_v2_runner_candidate.optimizer import new_adamw,clip_and_check,check_finite
    from yuntapr.experimental.phase_b_v2_ablations.config import get_config
    from yuntapr.experimental.phase_b_v2_ablations.total import candidate_loss
    from yuntapr.experimental.core_innovation.stage2 import CHANNELS
    budget=p['budget'];started=time.monotonic();used_bytes=used_files=0
    if not torch.cuda.is_available() or not torch.cuda.is_bf16_supported():raise RuntimeError('Pinned CUDA BF16 required')
    torch.set_num_threads(2)
    torch.cuda.set_per_process_memory_fraction(budget['max_gpu_memory_bytes']/torch.cuda.get_device_properties(0).total_memory,0)
    def check():
        if time.monotonic()-started>budget['max_wall_seconds']:raise TimeoutError('Six-hour cap')
        if working_set_bytes()>budget['max_host_memory_bytes']:raise MemoryError('Host RAM cap')
        if torch.cuda.memory_reserved()>budget['max_gpu_memory_bytes']:raise MemoryError('GPU cap')
        if shutil.disk_usage(out).free<budget['minimum_free_disk_bytes']:raise OSError('Minimum free disk cap')
    check()
    # Reserve128MiB for bootstrap/module/approval verification; meter remaining
    # frozen metadata archives before every open (including SQLite connects).
    metadata_usage=dict(bytes=128*1024**2,opens=2048)
    from urllib.parse import urlsplit,unquote
    exclusions=(Path(p['runtime']['torch_site']).resolve(),Path(sys.base_prefix).resolve(),out.resolve())
    def metadata_guard(event,args):
        if event not in ('open','sqlite3.connect') or not isinstance(args[0],(str,bytes,os.PathLike)):return
        name=os.fsdecode(args[0])
        if name.startswith('file:'):
            name=unquote(urlsplit(name).path)
            if len(name)>2 and name[0]=='/' and name[2]==':':name=name[1:]
        path=Path(name).resolve()
        if any(path.is_relative_to(root) for root in exclusions):return
        mode=args[1] if event=='open' and len(args)>1 else 'r'
        if isinstance(mode,str) and any(c in mode for c in 'wa+'):return
        if path.suffix.lower() not in ('.py','.json','.csv','.yaml','.yml','.npy','.sqlite') or not path.is_file():return
        n=path.stat().st_size
        if metadata_usage['bytes']+n>budget['max_metadata_bytes'] or metadata_usage['opens']+1>budget['max_metadata_opens']:raise PermissionError('Frozen metadata cap')
        metadata_usage['bytes']+=n;metadata_usage['opens']+=1
    sys.addaudithook(metadata_guard)
    frozen=read(p['inputs']['inherited_preparation'])['prepared']
    plan=PopulationPlan(frozen['private_inputs']['stage3_run'],frozen['private_inputs']['request'],root=ROOT)
    if plan.identity!=p['data']:raise ValueError('Frozen Train/Dev population changed')
    static=p['inputs']['static']
    db=sqlite3.connect(out/'static_reads.sqlite');db.execute('CREATE TABLE jobs(id TEXT PRIMARY KEY,state TEXT)');db.execute("INSERT INTO jobs VALUES ('static','PENDING')");db.commit()
    meter=SourceMeter(db,{static['path']:dict(bytes=static['bytes'],sha=static['sha256'],job_id='static')},max_files=1,max_bytes=static['bytes'])
    meter.install();meter.active={path_key(static['path'])}
    try:
        with meter.open(static['path'],'rb') as h:raw=h.read()
        pack=unpack(raw,'B6',read(p['inputs']['terrain_receipt']));totals=meter.totals()
    finally:meter.uninstall();db.close()
    used_bytes+=totals['delivered_bytes'];used_files+=totals['opened_files']
    transform=PhysicalDote(pack,DoteDefinition(**p['scientific_choices']['DOTE']))
    base,model=create(2029,ROOT,pack.region)
    initial=read(p['inputs']['baseline_initial'])
    if state_digest(base.state_dict())!=initial['B3']['full_state_sha256'] or state_digest(model.base.state_dict())!=initial['B3']['full_state_sha256']:
        raise ValueError('Historical B3 initialization changed')
    del base;gc.collect()
    orders={e:epoch_order(plan.ids('Train'),2029,e) for e in range(1,10)}
    serialized={str(e):dict(ids=list(ids),sha256=digest(ids)) for e,ids in orders.items()}
    if serialized!=read(p['inputs']['baseline_orders']):raise ValueError('Historical training order changed')
    write(out/'paired_orders.json',serialized)
    write(out/'initial_identity.json',dict(base_b3_sha256=initial['B3']['full_state_sha256'],candidate_sha256=state_digest(model.state_dict()),
        parameters=sum(x.numel() for x in model.parameters()),no_direct_gfs_branch=True,no_direct_static_branch=True))
    model=model.cuda();buffers=state_digest(dict(model.named_buffers()));optimizer,groups=new_adamw(model)
    ledger=sqlite3.connect(out/'updates.sqlite');ledger.execute('PRAGMA synchronous=FULL')
    ledger.execute('CREATE TABLE updates(u INTEGER PRIMARY KEY,state TEXT)');ledger.commit()
    seen=set();u=0;last=None;point_last=None
    def reader(role,epoch,ids):
        nonlocal used_bytes,used_files
        if (role,epoch) in seen:raise PermissionError('No repeated role/epoch pass')
        seen.add((role,epoch));scope=frozen['roles'][role]
        if len(ids)!=len(scope['ids']) or set(ids)!=set(scope['ids']):raise ValueError('Exact frozen pass only')
        r=BatchReader(plan,{role:ids},out/f'{role.lower()}_reads_{epoch:02d}',decision_id='CURRENT_CHAT_B3_DOTE_ONLY_EXACT_APPROVAL',
            max_files=scope['file_count'],max_bytes=scope['bytes_per_pass'],source_bytes={f:v['bytes'] for f,v in scope['files'].items()},dynamic_transform=transform)
        if {k:{q:v[q] for q in ('bytes','sha')} for k,v in r.meter.files.items()}!={path_key(k):{q:v[q] for q in ('bytes','sha')} for k,v in scope['files'].items()}:
            r.close();raise ValueError('Reader/source proposal mismatch')
        class Counted(PassReader):
            def close(self):
                nonlocal used_bytes,used_files
                actual=self.reader.meter.totals();used_bytes+=actual['delivered_bytes'];used_files+=actual['opened_files']
                super().close()
        return Counted(r,scope)
    def forward(b):
        if b.identity!=plan.identity or b.dynamic is None:raise ValueError('Frozen batch identity and physical DOTE required')
        result=model(b.x,b.native_valid,channel_order=CHANNELS,dynamic=b.dynamic,dynamic_valid=b.dynamic_valid,dynamic_grid=model.grid)
        loss=candidate_loss(result.rain_logit,result.conditional_quantiles_log,b.rate,b.valid,b.region,config=get_config('E0'))
        if loss.n_valid!=len(b.ids)*3430:raise ValueError('Supervision denominator changed')
        return result,loss
    try:
        for epoch,order in orders.items():
            check();r=reader('Train',epoch,order);visited=[];model.train();nv=nr=0;so=sq=0.
            try:
                for pos in range(0,959,2):
                    check();b=r.batch('Train',order[pos:pos+2]).to('cuda');optimizer.zero_grad(set_to_none=True)
                    for group in optimizer.param_groups:group['lr']=lr_for_update(u+1,steps_per_epoch=480)
                    with torch.autocast('cuda',dtype=torch.bfloat16):result,loss=forward(b)
                    loss.training_objective.backward();clip_and_check(model);check()
                    if u>=4320:raise PermissionError('Update cap')
                    with ledger:ledger.execute('INSERT INTO updates VALUES (?,?)',(u+1,'INTENT'))
                    optimizer.step();u+=1
                    with ledger:ledger.execute("UPDATE updates SET state='RETURNED' WHERE u=?",(u,))
                    check_finite(model.state_dict());check_finite(optimizer.state_dict());visited.extend(b.ids)
                    nv+=loss.n_valid;nr+=loss.n_rain;so+=float(loss.s_occ.detach());sq+=float(loss.s_qr.detach())
                    if u%20==0:status(out/'status.json',dict(state='TRAINING',epoch=epoch,updates=u,target_updates=4320,source_bytes=used_bytes,elapsed_seconds=time.monotonic()-started))
                    del b,result,loss
            finally:r.close()
            if tuple(visited)!=order or u!=epoch*480 or nv!=959*3430 or state_digest(dict(model.named_buffers()))!=buffers:raise ValueError('Training coverage/state mismatch')
            training=dict(scenes=959,batches=480,updates=u,n_valid=nv,n_rain=nr,s_occ_unweighted=so,s_qr_unweighted=sq,weighted_mean=(so+sq)/nv,train_order_sha256=digest(order),loss='E0')
            write(out/f'{KIND}_train_{epoch:02d}.json',training)
            optimizer.zero_grad(set_to_none=True);gc.collect();torch.cuda.empty_cache();ids=plan.ids('Development')
            r=reader('Development',epoch,ids);ev=Evaluation(ids,[plan.rows['Development'][s]['analysis_time'] for s in ids],plan.identity,out/f'evaluation_{epoch:02d}',strong_scene_ids=plan.strong_scene_ids)
            tail=BatchTail();point=PointMetrics();model.eval()
            try:
                with torch.no_grad():
                    for pos in range(0,963,8):
                        check();b=r.batch('Development',ids[pos:pos+8]).to('cuda')
                        with torch.autocast('cuda',dtype=torch.bfloat16):result,_=forward(b)
                        ev.add(result,b);tail.add_batch(result,b);point.add(result,b);del result,b
                last=ev.finish();tail_result=tail.finish_checked(last,ids);point_last=point.finish()
            finally:ev.close();r.close()
            reference_path=p['inputs']['baseline_epoch_reports'].get(str(epoch))
            delta=paired_difference(read(reference_path),last) if reference_path else dict(status='HISTORICAL_EPOCH_RECEIPT_NOT_IN_RECOVERY_DIRECTORY',epoch=epoch,required_fixed_E9_available=True)
            write(out/f'{KIND}_development_{epoch:02d}.json',last);write(out/f'{KIND}_point_{epoch:02d}.json',point_last)
            write(out/f'{KIND}_tail_{epoch:02d}.json',tail_result);write(out/f'paired_difference_{epoch:02d}.json',delta)
            payload=dict(identity=dict(model=KIND,seed=2029,data=plan.identity,proposal_sha256=p['proposal_sha256']),epoch=epoch,updates=u,
                model=cpu_tree(model.state_dict()),optimizer=cpu_tree(optimizer.state_dict()),optimizer_groups=groups,
                scheduler=dict(completed=u,steps_per_epoch=480,original_horizon=24000),training=training,validation=last,
                rng=dict(python=random.getstate(),numpy=np.random.get_state(),torch_cpu=torch.get_rng_state(),torch_cuda=torch.cuda.get_rng_state_all()))
            checkpoint=out/f'{KIND}_LAST_epoch_{epoch:02d}.pt'
            with checkpoint.open('xb') as h:torch.save(payload,h);h.flush();os.fsync(h.fileno())
            write(checkpoint.with_suffix('.receipt.json'),dict(model=KIND,epoch=epoch,updates=u,checkpoint_sha256=sha(checkpoint),validation_receipt_sha256=digest(last),code_content_sha256=p['code_content_sha256']))
            del payload;check()
            if sum(f.stat().st_size for f in out.rglob('*') if f.is_file())>budget['max_output_bytes']:raise OSError('Output cap')
            status(out/'status.json',dict(state='EPOCH_SEALED',epoch=epoch,updates=u,target_updates=4320,source_bytes=used_bytes,elapsed_seconds=time.monotonic()-started))
        if (u,used_bytes,used_files)!=(4320,budget['max_source_bytes'],budget['max_source_opens']):raise ValueError('Exact completed update/source accounting mismatch')
        if ledger.execute("SELECT count(*) FROM updates WHERE state='RETURNED'").fetchone()[0]!=4320:raise ValueError('Incomplete durable update ledger')
        old=read(p['inputs']['baseline_metric']);old_point=next(r for r in old['new_metrics']['point_estimates'] if r['candidate']=='A')
        summary=last['groups']['all']['summary'];baseline=read(Path(p['inputs']['baseline_run'])/'B3_development_09.json')['groups']['all']['summary']
        comparisons={k:dict(baseline=baseline[k],candidate=summary[k],difference=summary[k]-baseline[k]) for k in ('brier','auroc','average_precision','conditional_pinball')}
        comparisons['rmse_mm_h']=dict(baseline=old_point['RMSE_mm_h'],candidate=point_last['rmse_mm_h'],difference=point_last['rmse_mm_h']-old_point['RMSE_mm_h'])
        write(out/'experiment_comparison.json',dict(status='COMPLETE_FIXED_E9_SINGLE_SEED_COMPARISON',seed=2029,models=['B3',KIND],metrics=comparisons,
            candidate_point_metrics=point_last,baseline_contingency=old['new_metrics']['contingency']['A']['rows'],
            baseline_q32_coverage=baseline['coverage'][-1],candidate_q32_coverage=summary['coverage'][-1],
            description='No direct GFS/MEE or static branch; GFS still drives physical DOTE. Added representation and3136 parameters are jointly tested.',
            limitation='Single seed and same2024 Development year; no significance, physical-causality or final-test generalization claim.'))
        write(out/'completion.json',dict(status='COMPLETE_TRAIN_AND_DEV_EVALUATION',at=now(),model=KIND,seed=2029,epochs=9,optimizer_updates=u,
            source_bytes=used_bytes,source_opens=used_files,wall_seconds=time.monotonic()-started,metadata_usage=metadata_usage,proposal_sha256=p['proposal_sha256'],final_2025='FROZEN_NO_ACCESS'))
    except BaseException as error:
        write(out/'failure.json',dict(status='STOP_NO_AUTOMATIC_RETRY',at=now(),error_type=type(error).__name__,error=str(error),updates_returned=u,
            sealed_or_closed_source_bytes=used_bytes,sealed_or_closed_source_opens=used_files,wall_seconds=time.monotonic()-started))
        raise
    finally:ledger.close()


def execute(plan,approval):
    p,a=validate_proposal(plan,approval);out=Path(p['output_root'])
    if out.exists():raise PermissionError('Consumed output namespace; no retry/replay')
    if os.path.normcase(str(Path(sys.executable).resolve()))!=os.path.normcase(str(Path(p['runtime']['python']).resolve())) or sha(sys.executable)!=p['runtime']['python_sha256']:raise PermissionError('Pinned native runtime only')
    for k,v in p['runtime']['environment'].items():
        if os.environ.get(k)!=v:raise PermissionError('Pinned process environment differs: '+k)
    sys.path.insert(1,p['runtime']['torch_site'])
    out.mkdir(parents=True);write(out/'execution_claim.json',dict(at=now(),pid=os.getpid(),proposal_sha256=p['proposal_sha256'],approval_basis=a['actual_researcher_reply']))
    try:train(p,a,out)
    except BaseException as error:
        if not (out/'failure.json').exists():write(out/'failure.json',dict(status='STOP_NO_AUTOMATIC_RETRY',at=now(),error_type=type(error).__name__,error=str(error)))
        raise


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--proposal',type=Path,required=True);parser.add_argument('--approval',type=Path,required=True);args=parser.parse_args()
    execute(args.proposal,args.approval)
