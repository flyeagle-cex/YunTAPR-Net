"""Small paired executor using existing V2/E0/AdamW; CLI exposes dry-run only."""
from dataclasses import dataclass,asdict
from pathlib import Path
import ctypes,gc,json,os,random,sqlite3
import numpy as np
import torch
from yuntapr.training.phase_a_protocol import state_digest,parameter_groups,lr_for_update
from yuntapr.experimental.phase_b_v2_runner_candidate.optimizer import new_adamw,clip_and_check,check_finite
from yuntapr.experimental.phase_b_v2_ablations.config import get_config
from yuntapr.experimental.phase_b_v2_ablations.total import candidate_loss
from yuntapr.experimental.phase_b_v2_integration.resources import resource_snapshot,require_resources
from yuntapr.models.quantile_v2.parameterization import CandidateNumerics
from ..stage2 import CHANNELS,MEE_V13_KEYS
from ..stage2.models import paired_spectral_candidates
from ..stage3.planning import digest
from . import *
from .evaluation import Evaluation,paired_difference


def cpu_tree(value):
    # Same tensor-copy semantics; importing the old engine would execute its
    # unrelated seed2027/2028 campaign environment gate during module import.
    if isinstance(value,torch.Tensor):return value.detach().cpu().clone()
    if isinstance(value,dict):return {k:cpu_tree(v) for k,v in value.items()}
    if isinstance(value,list):return [cpu_tree(v) for v in value]
    if isinstance(value,tuple):return tuple(cpu_tree(v) for v in value)
    return value


def write(path,value):
    with Path(path).open('x',encoding='utf-8') as f:json.dump(value,f,indent=2,allow_nan=False)


def resources(*,backward=True):
    r=resource_snapshot(full_backward=backward);require_resources(r)
    r['scope']='STAGE4_ENGINEERING_RESOURCE_CHECK'
    if os.name=='nt':
        class Memory(ctypes.Structure):
            _fields_=[('length',ctypes.c_ulong),('load',ctypes.c_ulong)]+[(k,ctypes.c_ulonglong) for k in ('total_phys','avail_phys','total_page','avail_page','total_virtual','avail_virtual','extended')]
        m=Memory();m.length=ctypes.sizeof(m)
        if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(m)) or m.avail_page<2*1024**3:raise RuntimeError('Insufficient available system commit')
        r['available_commit_bytes']=m.avail_page
    return r


def seed_all(seed):
    if type(seed)!=int or not 0<=seed<2**32:raise ValueError('Explicit seed required')
    if os.environ.get('CUBLAS_WORKSPACE_CONFIG')!=':4096:8':raise RuntimeError('Set cuBLAS workspace before Python startup')
    if os.environ.get('PYTHONHASHSEED')!=str(seed):raise RuntimeError('Set the selected hash seed before Python startup')
    random.seed(seed);np.random.seed(seed);torch.manual_seed(seed);torch.cuda.manual_seed_all(seed)
    torch.use_deterministic_algorithms(True);torch.backends.cudnn.benchmark=False;torch.backends.cudnn.deterministic=True
    torch.backends.cuda.matmul.allow_tf32=False;torch.backends.cudnn.allow_tf32=False;torch.set_float32_matmul_precision('highest')


def paired_models(seed,root):
    seed_all(seed)
    return dict(zip(('B3','B4'),paired_spectral_candidates(numerics=CandidateNumerics(1e-4,1e-4),mee_width=16,mee_keys=MEE_V13_KEYS,root=root)))


def forward(model,batch):
    if batch.identity['population_sha256']!=POPULATION_SHA:raise ValueError('Wrong population tensor binding')
    extra=dict(environment=batch.environment,environment_valid=batch.environment_valid,environment_grid=model.grid,environment_keys=MEE_V13_KEYS) if model.kind in ('B4','B5','B6','B7','B8') else {}
    if model.kind in ('B7','B8'):
        if batch.dynamic is None or batch.dynamic_valid is None:raise ValueError('DOTE physical transform was not connected to the reader')
        extra.update(dynamic=batch.dynamic,dynamic_valid=batch.dynamic_valid,dynamic_grid=model.grid)
    output=model(batch.x,batch.native_valid,channel_order=CHANNELS,**extra)
    loss=candidate_loss(output.rain_logit,output.conditional_quantiles_log,batch.rate,batch.valid,batch.region,config=get_config('E0'))
    if loss.n_valid!=len(batch.ids)*3430:raise ValueError('Frozen supervision denominator')
    return output,loss


def epoch_order(ids,seed,epoch):
    if type(epoch)!=int or not 1<=epoch<=EPOCHS or len(ids)!=TRAIN_N or len(set(ids))!=TRAIN_N:raise ValueError('One final Train pass required')
    order=torch.randperm(len(ids),generator=torch.Generator().manual_seed(seed+epoch-1)).tolist()
    return tuple(ids[i] for i in order)


@dataclass(frozen=True)
class FormalDecision:
    decision_id:str
    seed:int
    population_sha256:str
    mee13_confirmed:bool
    train_statistics_confirmed:bool
    fixed_f006_coverage_accepted:bool
    cap:int=PAIR_CAP
    def validate(self):
        if not self.decision_id or type(self.seed)!=int or not 0<=self.seed<2**32-EPOCHS or self.seed in (2026,2027,2028,DRY_SEED):raise PermissionError('Independent researcher-confirmed formal seed required')
        if self.population_sha256!=POPULATION_SHA or self.cap!=PAIR_CAP or not all(v is True for v in (self.mee13_confirmed,self.train_statistics_confirmed,self.fixed_f006_coverage_accepted)):raise PermissionError('Formal science/budget decision incomplete')


class UpdateLedger:
    def __init__(self,path,identity,*,allowed_models=('B3','B4')):
        if tuple(allowed_models) not in (('B3','B4'),('B5',),('B6',),('B7',),('B8',)):raise ValueError('Explicit supported ledger arms required')
        self.allowed_models=tuple(allowed_models)
        if Path(path).exists():raise PermissionError('No update ledger overwrite/resume/retry')
        self.db=sqlite3.connect(path);self.db.execute('PRAGMA synchronous=FULL')
        self.db.execute('CREATE TABLE identity(value TEXT)');self.db.execute('INSERT INTO identity VALUES (?)',(json.dumps(identity,sort_keys=True),))
        self.db.execute('CREATE TABLE updates(model TEXT,u INTEGER,state TEXT,PRIMARY KEY(model,u))');self.db.commit()
    def reserve(self,model,u):
        self.db.execute('BEGIN IMMEDIATE')
        try:
            total=self.db.execute('SELECT COUNT(*) FROM updates').fetchone()[0]
            n,returned=self.db.execute("SELECT COUNT(*),COALESCE(SUM(state='RETURNED'),0) FROM updates WHERE model=?",(model,)).fetchone()
            if model not in self.allowed_models or type(u)!=int or total>=PAIR_CAP or u!=n+1 or n!=returned or u>EPOCHS*STEPS:raise PermissionError('Cap/order/uncertain-update boundary')
            self.db.execute('INSERT INTO updates VALUES (?,?,?)',(model,u,'INTENT'));self.db.commit()
        except BaseException:self.db.rollback();raise
    def returned(self,model,u):
        with self.db:
            c=self.db.execute("UPDATE updates SET state='RETURNED' WHERE model=? AND u=? AND state='INTENT'",(model,u))
            if c.rowcount!=1:raise RuntimeError('Missing durable update intent')
    def close(self):self.db.close()


class PairedExecutor:
    def __init__(self,plan,folder,*,decision=None,strong_scene_ids=(),altitude=None,recovery=None,
                 kinds=('B3','B4'),deadline=None,tail_factory=None,code_commit=None,pair_reference=None,model_factory=None):
        self.plan=plan;self.folder=Path(folder);self.decision=decision;self.strong=strong_scene_ids or (plan.strong_scene_ids if plan is not None else ());self.altitude=altitude
        self.recovery=recovery
        self.kinds=tuple(kinds);self.deadline=deadline or (lambda:None)
        self.tail_factory=tail_factory;self.code_commit=code_commit
        self.pair_reference=Path(pair_reference) if pair_reference is not None else None
        self.model_factory=model_factory
    def run(self,reader_factory):
        # No optimizer or output experiment exists before all explicit decisions.
        if type(self.decision) is not FormalDecision:raise PermissionError('Formal training not authorized; dry-run only')
        self.decision.validate()
        static=self.kinds in (('B5',),('B6',),('B7',),('B8',)) and self.model_factory is not None
        if (self.kinds not in (('B3','B4'),('B3',),('B4',)) and not static) or (self.recovery is not None and self.kinds!=getattr(self.recovery,'kinds',('B3','B4'))):
            raise PermissionError('Explicit supported arms; recovery cannot use single-arm entry')
        self.deadline()
        if self.recovery is not None:self.recovery.validate(self.plan,self.decision)
        resources();self.folder.mkdir(exist_ok=False)
        if len(self.plan.ids('Train'))!=TRAIN_N or len(self.plan.ids('Development'))!=DEV_N:raise ValueError('Wrong population')
        models=(self.model_factory or paired_models)(self.decision.seed,self.plan.root);identity=dict(decision=asdict(self.decision),data=self.plan.identity)
        ledger=UpdateLedger(self.folder/'updates.sqlite',identity,allowed_models=self.kinds if static else ('B3','B4')) if self.recovery is None else self.recovery.ledger(self.folder/'updates.sqlite',identity)
        initial_identity={k:dict(full_state_sha256=state_digest(m.state_dict()),common_sha256=state_digest(dict(backbone=m.backbone.state_dict(),heads=m.heads.state_dict()))) for k,m in models.items()}
        if self.recovery is not None:self.recovery.check_initial(initial_identity)
        write(self.folder/'paired_initial_identity.json',initial_identity)
        if initial_identity['B3']['common_sha256']!=initial_identity['B4']['common_sha256']:
            raise RuntimeError('Paired common initialization differs')
        if static and any(initial_identity[k]['common_sha256']!=initial_identity['B4']['common_sha256'] for k in self.kinds):
            raise RuntimeError('Static arm changed common backbone/heads initialization')
        models={k:v for k,v in models.items() if k in self.kinds}
        orders={e:epoch_order(self.plan.ids('Train'),self.decision.seed,e) for e in range(1,EPOCHS+1)}
        if self.recovery is not None:self.recovery.check_orders(orders)
        write(self.folder/'paired_orders.json',{str(e):dict(ids=o,sha256=digest(o)) for e,o in orders.items()})
        if self.pair_reference is not None:
            for name in ('paired_initial_identity.json','paired_orders.json'):
                actual=json.loads((self.folder/name).read_text(encoding='utf-8'));reference=json.loads((self.pair_reference/name).read_text(encoding='utf-8'))
                if static and name=='paired_initial_identity.json':actual={k:actual[k] for k in reference}
                if actual!=reference:
                    raise RuntimeError('B4 initialization/order differs from its completed B3 pair')
        results={};self.poisoned=False
        try:
            for kind in self.kinds:
                model=models.pop(kind).cuda();initial=state_digest(model.state_dict());buffer_sha=state_digest(dict(model.named_buffers()))
                optimizer,groups=new_adamw(model);u=0;epochs=[]
                if self.recovery is not None:
                    u,epochs=self.recovery.restore(kind,model,optimizer,groups)
                for epoch,order in orders.items():
                    self.deadline()
                    if self.recovery is not None and epoch<=self.recovery.completed_epochs(kind):continue
                    resources(backward=False)
                    reader=reader_factory('Train',epoch,order,self.folder/f'{kind}_train_reads_{epoch:02d}')
                    visited=[];model.train();nvalid=nrain=0;socc=sqr=0.
                    try:
                        for pos in range(0,TRAIN_N,BATCH):
                            self.deadline()
                            b=reader.batch('Train',order[pos:pos+BATCH]).to('cuda');optimizer.zero_grad(set_to_none=True)
                            if b.identity!=self.plan.identity or b.role!='Train' or b.ids!=order[pos:pos+BATCH]:raise ValueError('Training batch identity/order differs')
                            lr=lr_for_update(u+1,steps_per_epoch=STEPS)
                            for group in optimizer.param_groups:group['lr']=lr
                            with torch.autocast('cuda',dtype=torch.bfloat16):out,loss=forward(model,b)
                            loss.training_objective.backward();clip_and_check(model)
                            self.deadline();ledger.reserve(kind,u+1);optimizer.step();u+=1;ledger.returned(kind,u)
                            check_finite(model.state_dict());check_finite(optimizer.state_dict());visited.extend(b.ids)
                            nvalid+=loss.n_valid;nrain+=loss.n_rain;socc+=float(loss.s_occ.detach());sqr+=float(loss.s_qr.detach())
                            if u%50==0:resources(backward=False)
                            del b,out,loss
                    finally:reader.close()
                    if tuple(visited)!=order or u!=epoch*STEPS or nvalid!=TRAIN_N*3430 or state_digest(dict(model.named_buffers()))!=buffer_sha:raise RuntimeError('Epoch coverage/state mismatch')
                    training=dict(scenes=TRAIN_N,batches=STEPS,updates=u,n_valid=nvalid,n_rain=nrain,s_occ_unweighted=socc,s_qr_unweighted=sqr,
                        weighted_mean=(socc+sqr)/nvalid,loss_arm='E0',train_order_sha256=digest(order))
                    write(self.folder/f'{kind}_train_{epoch:02d}.json',training)
                    optimizer.zero_grad(set_to_none=True);gc.collect();torch.cuda.empty_cache()
                    self.deadline()
                    ids=self.plan.ids('Development');reader=reader_factory('Development',epoch,ids,self.folder/f'{kind}_dev_reads_{epoch:02d}')
                    ev=Evaluation(ids,[self.plan.rows['Development'][s]['analysis_time'] for s in ids],self.plan.identity,self.folder/f'{kind}_evaluation_{epoch:02d}',strong_scene_ids=self.strong,altitude=self.altitude)
                    model.eval()
                    tail=self.tail_factory() if self.tail_factory is not None else None
                    try:
                        with torch.no_grad():
                            for pos in range(0,DEV_N,VAL_BATCH):
                                self.deadline()
                                b=reader.batch('Development',ids[pos:pos+VAL_BATCH]).to('cuda')
                                if b.identity!=self.plan.identity or b.role!='Development' or b.ids!=ids[pos:pos+VAL_BATCH]:raise ValueError('Development batch identity/order differs')
                                with torch.autocast('cuda',dtype=torch.bfloat16):out,_=forward(model,b)
                                ev.add(out,b)
                                if tail is not None:tail.add_batch(out,b)
                                del b,out
                        report=ev.finish()
                    finally:ev.close();reader.close()
                    write(self.folder/f'{kind}_development_{epoch:02d}.json',report)
                    if tail is not None:write(self.folder/f'{kind}_tail_{epoch:02d}.json',tail.finish_checked(report,ids))
                    self.deadline()
                    payload=dict(identity=dict(decision=asdict(self.decision),data=self.plan.identity,model=kind),initial_sha256=initial,epoch=epoch,updates=u,
                        model=cpu_tree(model.state_dict()),optimizer=cpu_tree(optimizer.state_dict()),scheduler=dict(completed=u,steps_per_epoch=STEPS,original_horizon=50*STEPS),
                        rng=dict(python=random.getstate(),numpy=np.random.get_state(),torch_cpu=torch.get_rng_state(),torch_cuda=torch.cuda.get_rng_state_all()),
                        train_order_sha256=digest(order),training=training,validation=report,optimizer_groups=groups)
                    path=self.folder/f'{kind}_LAST_epoch_{epoch:02d}.pt'
                    with path.open('xb') as f:torch.save(payload,f);f.flush();os.fsync(f.fileno())
                    from .data import sha
                    receipt=dict(model=kind,epoch=epoch,updates=u,checkpoint_sha256=sha(path),population_sha256=POPULATION_SHA,validation_receipt_sha256=digest(report))
                    if self.code_commit is not None:receipt['code_commit']=self.code_commit
                    write(path.with_suffix('.receipt.json'),receipt)
                    self.deadline()
                    epochs.append(report);del payload
                results[kind]=epochs;del optimizer,model;gc.collect();torch.cuda.empty_cache()
            if self.kinds==('B3','B4'):
                for epoch in range(EPOCHS):write(self.folder/f'paired_difference_{epoch+1:02d}.json',paired_difference(results['B3'][epoch],results['B4'][epoch]))
            actual=ledger.db.execute("SELECT COUNT(*) FROM updates WHERE state='RETURNED'").fetchone()[0]
            expected=len(self.kinds)*EPOCHS*STEPS
            if actual!=getattr(ledger,'expected_returned',expected):raise RuntimeError('Endpoint ledger incomplete')
            self.deadline()
            result=dict(status='COMPLETE',updates=expected)
            if self.recovery is not None:result.update(segment_updates=actual,cumulative_attempts=self.recovery.request['prior_updates']+actual,replayed_updates=self.recovery.request.get('replayed_updates',480))
            return result
        except BaseException as exc:
            self.poisoned=True;write(self.folder/'failure.json',dict(status='STOP_NO_AUTOMATIC_RETRY',error=type(exc).__name__+': '+str(exc)));raise
        finally:ledger.close()
