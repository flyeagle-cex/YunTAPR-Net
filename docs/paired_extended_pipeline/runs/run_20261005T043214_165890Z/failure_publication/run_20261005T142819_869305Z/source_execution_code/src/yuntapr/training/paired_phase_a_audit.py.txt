"""Approved governance adapter; frozen numerical implementations remain untouched."""
from contextlib import contextmanager
from dataclasses import dataclass, asdict
from pathlib import Path
import datetime, hashlib, json, os, re, sys, traceback
import torch
from yuntapr.contracts.loader import REPO_ROOT, sha256
from yuntapr.training import paired_phase_a as frozen
from yuntapr.training.formal_phase_a import atomic_json
from yuntapr.training.phase_a_protocol import state_digest, lr_for_update
from yuntapr.data import dataset_b1 as data

BASELINE = '6c7d436cfbab70f3d9ef181c59c938ca14bb3afa'
PROTOCOL_SHA = '284f71ca6677f23c018ed9ee3e8d8b298fe3e472735689953cd42d73f4ea57b6'
INITIAL = {'B0_MATCHED':'57a4d103a31aa7be1a52af079cdf7fb81bc73c51ba3e0e97d395513d21d9023d',
           'B1':'9aa5dad0456e8d78862fb485d4c37f172aa1360e1d350ac9df101a953799718e'}
SCOPES = {'B0_MATCHED':'B0_MATCHED_PHASE_A_FORMAL_TRAINING_ONLY',
          'B1':'B1_PHASE_A_FORMAL_TRAINING_ONLY'}
SLOT_PATH = 'config/b1/b1_six_slot_audit_definition_v1.json'
SLOT_SHA = 'b6887a59900aa2f736cec4ab0d8727511e59eb9fc4e0418ebcb7d71778cd66d4'
ADAPTERS = ('scripts/authorized_paired_phase_a_entry.py','scripts/launch_authorized_paired_phase_a_v1.py')

def utc_now():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()

def code_hashes(root=REPO_ROOT):
    return {**frozen.implementation_hashes(root), **{p:sha256(Path(root)/p) for p in ADAPTERS}}

def code_digest(hashes):
    return hashlib.sha256(json.dumps(hashes,sort_keys=True,separators=(',',':')).encode()).hexdigest()

def repository_json_path(path, root=REPO_ROOT):
    # Reject raw paths before resolve/stat/open, including deliberately disguised paths.
    text=os.fsdecode(path).replace('/','\\').lower()
    if re.match(r'^[hf]:\\',text):
        raise PermissionError('Raw/checkpoint paths cannot be authorization or governance JSON')
    p=Path(path).resolve()
    if p.suffix!='.json' or not p.is_relative_to(Path(root).resolve()):
        raise PermissionError('Governance identity must be a repository JSON')
    return p

def verify_history(snapshot_path, expected_sha, root=REPO_ROOT):
    p=repository_json_path(snapshot_path,root)
    if sha256(p)!=expected_sha:raise ValueError('Historical snapshot identity mismatch')
    snapshot=json.loads(p.read_text(encoding='utf8'))
    if snapshot['baseline_commit']!=BASELINE or snapshot['file_count']!=2061 or len(snapshot['files'])!=2061:
        raise ValueError('Complete baseline snapshot required')
    for rel,digest in snapshot['files'].items():
        target=Path(root)/rel
        if not target.resolve().is_relative_to(Path(root).resolve()) or sha256(target)!=digest:
            raise ValueError('Historical file changed: '+rel)
    return {'file_count':2061,'all_byte_identical':True,'baseline_commit':BASELINE}

def authorization_fields(contract, kind):
    if kind not in SCOPES:raise PermissionError('Unapproved model kind')
    hashes=code_hashes(contract.root)
    return {'scope':SCOPES[kind],'model':kind,'AUTHORIZED':True,'baseline_commit':BASELINE,
            'protocol_sha256':PROTOCOL_SHA,'code_hashes':hashes,'implementation_sha256':code_digest(hashes),
            'normalization_sha256':data.SCALER_SHA,'train_manifest_sha256':data.PINS[kind,2023],
            'validation_manifest_sha256':data.PINS[kind,2024], 'initial_model_sha256':INITIAL[kind],
            'checkpoint_root':str(frozen.ROOTS[kind]),'seed':2026,'physical_batch':2,'accumulation':1,
            'validation_batch':8,'W':5228,'U':261400,'max_epochs':50,'2025_raw_access':False,
            'Phase_B_authorized':False,'B2_to_B8_authorized':False,'2025_Final_Test_authorized':False,
            'initialization':'FRESH_INDEPENDENT_RESEED_2026_COPY_SAME_NAME_SAME_SHAPE_ONLY',
            'six_slot_definition_sha256':SLOT_SHA}

@dataclass(frozen=True)
class AuditedAuthorization:
    value:dict
    sha256:str

    @classmethod
    def load(cls,path,expected_sha,contract,kind):
        if not path or not expected_sha:raise PermissionError('Authorization required before source/model/optimizer')
        p=repository_json_path(path,contract.root)
        if sha256(p)!=expected_sha:raise PermissionError('Authorization SHA mismatch')
        value=json.loads(p.read_text(encoding='utf8'))
        if contract.protocol_sha256!=PROTOCOL_SHA or contract.protocol['validation']['batch']!=8:
            raise PermissionError('Protocol identity changed')
        for key,want in authorization_fields(contract,kind).items():
            if value.get(key)!=want:raise PermissionError('Authorization binding mismatch: '+key)
        if not value.get('researcher_approval_reference'):raise PermissionError('Researcher approval reference missing')
        gate=repository_json_path(value['pretraining_gate_path'],contract.root)
        if sha256(gate)!=value['pretraining_gate_sha256']:raise PermissionError('Pre-training gate identity mismatch')
        proof=json.loads(gate.read_text(encoding='utf8'))
        required={'status':'PASS','FORMAL_OPTIMIZER_STEPS':0,'2025_RAW_ACCESS':0,'2025_PIXELS_READ':0,
                  'protocol_sha256':PROTOCOL_SHA,'normalization_sha256':data.SCALER_SHA,
                  'implementation_sha256':value['implementation_sha256'],'initial_model_sha256':INITIAL,
                  'parameter_counts':frozen.COUNTS,'all_related_tests_passed':True,'historical_files_byte_identical':True,
                  'scheduler_boundaries_pass':True,'optimizer_groups_pass':True}
        if any(proof.get(k)!=v for k,v in required.items()):raise PermissionError('Pre-training evidence incomplete')
        if proof.get('paired_initialization_provenance')!=value.get('paired_initialization_provenance'):
            raise PermissionError('Paired initialization provenance mismatch')
        verify_history(value['historical_snapshot_path'],value['historical_snapshot_sha256'],contract.root)
        if sha256(Path(contract.root)/SLOT_PATH)!=SLOT_SHA:raise PermissionError('Six-slot definition changed')
        if value.get('resume_authorized',False):
            parent_path=repository_json_path(value['origin_authorization_path'],contract.root)
            parent=cls.load(parent_path,value['origin_authorization_sha256'],contract,kind)
            if parent.value.get('resume_authorized',False):raise PermissionError('Resume must bind the original fresh authorization')
            if parent.value['planned_run_id']!=value['planned_run_id']:raise PermissionError('Resume origin run mismatch')
        return cls(value,expected_sha)

def verify_initialization(anchor, temporal, proof):
    actual={'B0_MATCHED':state_digest(anchor.state_dict()),'B1':state_digest(temporal.state_dict())}
    if actual!=INITIAL or any(proof[k]!=INITIAL[m] for m,k in
        [('B0_MATCHED','B0_MATCHED_INITIAL_MODEL_SHA256'),('B1','B1_INITIAL_MODEL_SHA256')]):
        raise ValueError('Pinned fresh initialization SHA mismatch')
    if (proof['same_shape_tensor_count']!=72 or not proof['all_shared_tensors_bit_identical']
        or not proof['independent_reseed_before_each_model'] or proof['historical_checkpoint_loaded']
        or proof['optimizer_state_transferred'] or not proof['native_zero_skip_preserved']):
        raise ValueError('Fresh paired initialization provenance failed')
    return actual

def checkpoint_provenance(contract,auth,kind,runid,env,groups,initial):
    p=frozen.checkpoint_expected(contract,auth,kind,runid,env,groups,initial)
    config=contract.protocol
    p.update(scope=SCOPES[kind],baseline_commit=BASELINE,code_hashes=auth.value['code_hashes'],
             implementation_sha256=auth.value['implementation_sha256'],initial_model_sha256=INITIAL[kind],
             train_manifest_sha256=data.PINS[kind,2023],validation_manifest_sha256=data.PINS[kind,2024],
             scientific_contract_sha256=config['identity']['scientific_contract_v1.1']['sha256'],
             SP04_identity={k:v for k,v in config['identity'].items() if k.startswith('SP04')},
             Yunnan_mask_identity=config['identity']['yunnan_mask'],
             slot_definition_identity={'path':SLOT_PATH,'sha256':SLOT_SHA,'offset_minutes':[60,50,40,30,20,10],
                                      'ordering':'OLDEST_TO_LATEST','selected_slots':list(range(6)) if kind=='B1' else [5]},
             parameter_counts=frozen.COUNTS[kind],checkpoint_root=str(frozen.ROOTS[kind]),
             loss_settings=config['loss'],optimizer_settings=config['optimizer'],scheduler_settings=config['scheduler'],
             training_settings=config['training'],validation_settings=config['validation'],
             precision_settings=config['precision'],loader_settings=config['loader'],
             seed=2026,physical_batch=2,accumulation=1,**{'2025_RAW_ACCESS':0,'2025_PIXELS_READ':0})
    if auth.value.get('resume_authorized',False):
        p['authorization_sha256']=auth.value['origin_authorization_sha256']
    return p

def validate_resume_ancestry(auth,kind,runid,registry):
    if not auth.value.get('resume_authorized',False):raise PermissionError('Interrupted runs require explicit resume authorization')
    for name in ('BEST','LAST'):
        identity=registry[name]
        path=Path(identity['absolute_local_path'])
        if identity.get('model')!=kind or path.parent!=frozen.ROOTS[kind]/runid:
            raise ValueError('Cross-model/run resume rejected before checkpoint open')
        if type(identity.get('epoch'))!=int or not 1<=identity['epoch']<=50 or identity['global_update']!=identity['epoch']*5228:
            raise ValueError('Mid-epoch resume rejected')
    if registry['BEST']['epoch']>registry['LAST']['epoch']:raise ValueError('BEST ancestry invalid')
    lineage=auth.value.get('resume_ancestry',{})
    if lineage.get('run_id')!=runid or lineage.get('LAST_sha256')!=registry['LAST']['sha256']:
        raise ValueError('Resume ancestry authorization mismatch')

class RawFirewall:
    """Per-process authorization/date firewall, before open and netCDF decode."""
    def __init__(self,authorized=False,allowed_paths=(),log_path=None):
        self.authorized=authorized;self.allowed={self.key(p) for p in allowed_paths}
        self.log_path=Path(log_path) if log_path else None
        self.raw_opens=0;self.forbidden_attempts=0
    @staticmethod
    def key(p):return os.fsdecode(p).replace('/','\\').lower()
    def raw_kind(self,p):
        if not isinstance(p,(str,bytes,os.PathLike)):return None
        text=self.key(p)
        for root,kind in ((data.H_ROOT,'B13'),(data.IMERG_ROOT,'IMERG')):
            if text.startswith(self.key(root)+'\\'):return kind
        return None
    def check(self,path,mode='r'):
        kind=self.raw_kind(path)
        if not kind:return
        text=self.key(path)
        root=data.H_ROOT if kind=='B13' else data.IMERG_ROOT
        relative=text[len(self.key(root))+1:]
        tokens=re.findall(r'(?<!\d)(202[345])(\d{2})(?:\d{2})?',relative)
        if not tokens or any(int(y) not in (2023,2024) or not 3<=int(m)<=10 for y,m in tokens):
            self.forbidden_attempts+=1;raise PermissionError('2025/February/out-of-scope raw path rejected before I/O')
        if not self.authorized:raise PermissionError('Formal raw source read before authorization rejected')
        if self.allowed and text not in self.allowed:raise PermissionError('Raw source outside exact frozen sample identities')
        if isinstance(mode,str) and any(c in mode for c in 'wa+') or isinstance(mode,int) and mode&(os.O_WRONLY|os.O_RDWR|os.O_CREAT|os.O_TRUNC):
            raise PermissionError('Raw source is permanently read-only')
    def install(self):
        def audit(event,args):
            if event=='open' and self.raw_kind(args[0]):
                mode=args[1] if args[1] is not None else args[2];self.check(args[0],mode)
                self.raw_opens+=1
                if self.log_path:append_jsonl(self.log_path,{'utc':utc_now(),'pid':os.getpid(),'event':'RAW_READ_ONLY_OPEN','path':os.fsdecode(args[0]),'model_scope_authorized':True},sync=False)
            if event in ('os.remove','os.rename','os.rmdir') and any(self.raw_kind(p) for p in args[:2]):
                raise PermissionError('Raw source mutation forbidden')
        sys.addaudithook(audit)
        data.install_source_guard()
        # Outer guard rejects forbidden paths before the older wrapper's resolve/stat.
        original_dataset=data.netCDF4.Dataset
        def dataset(path,*args,**kwargs):
            self.check(path,kwargs.get('mode',args[0] if args else 'r'))
            return original_dataset(path,*args,**kwargs)
        data.netCDF4.Dataset=dataset

def append_jsonl(path,value,*,sync=True):
    with Path(path).open('a',encoding='utf8',newline='\n') as f:
        f.write(json.dumps(value,ensure_ascii=False,allow_nan=False,default=str)+'\n');f.flush()
        if sync:os.fsync(f.fileno())

@dataclass
class Counters:
    FORMAL_OPTIMIZER_STEPS:int=0
    OPTIMIZER_STEPS_COMPLETED:int=0
    BACKWARD_CALLS:int=0
    TRAIN_FORWARD_CALLS:int=0
    VALIDATION_FORWARD_CALLS:int=0
    CHECKPOINT_LOADS:int=0
    ENGINEERING_OPTIMIZER_STEPS:int=0
    TEST_FIXTURE_OPTIMIZER_STEPS:int=0
    PIXELS_2025_READ:int=0
    RAW_ACCESS_2025:int=0
    MODEL_INFERENCE_SCENES_2025:int=0

class RunAudit:
    def __init__(self,public,kind):
        self.public=Path(public);self.kind=kind;self.counters=Counters();self.phase='PREFLIGHT';self.epoch=0
        self.completed_epoch=0;self.verified_last=None;self.last_completed_metrics=None
    def event(self,event,**values):
        detailed=event in ('BACKWARD_CALL','OPTIMIZER_STEP_CALLED','OPTIMIZER_STEP_RETURNED','TRAIN_UPDATE_AUDITED','CHECKPOINT_DESERIALIZATION_CALL')
        path=self.public/'logs'/f'epoch_{self.epoch:03d}'/'step_events.jsonl' if detailed else self.public/'partial_training_log.jsonl'
        path.parent.mkdir(parents=True,exist_ok=True)
        append_jsonl(path,{'utc':utc_now(),'event':event,'model':self.kind,
            'phase':self.phase,'epoch':self.epoch,**asdict(self.counters),**values})
    def snapshot(self,**values):
        atomic_json(self.public/'execution_counters.json',{'scope':SCOPES[self.kind],**asdict(self.counters),
                    'completed_epoch':self.completed_epoch,'phase':self.phase,'epoch':self.epoch,**values})
    @contextmanager
    def instrument(self,model,optimizer):
        original_backward=torch.Tensor.backward
        original_load=torch.load
        def load(*args,**kwargs):
            self.counters.CHECKPOINT_LOADS+=1;self.event('CHECKPOINT_DESERIALIZATION_CALL')
            return original_load(*args,**kwargs)
        def backward(tensor,*args,**kwargs):
            if self.phase!='TRAIN':raise PermissionError('Backward outside formal Train rejected')
            self.counters.BACKWARD_CALLS+=1;self.event('BACKWARD_CALL')
            return original_backward(tensor,*args,**kwargs)
        def forward(module,args):
            attr='TRAIN_FORWARD_CALLS' if self.phase=='TRAIN' else 'VALIDATION_FORWARD_CALLS'
            setattr(self.counters,attr,getattr(self.counters,attr)+1)
        def before(opt,args,kwargs):
            if self.phase!='TRAIN':raise PermissionError('Optimizer update outside Train rejected')
            self.counters.FORMAL_OPTIMIZER_STEPS+=1;self.event('OPTIMIZER_STEP_CALLED')
        def after(opt,args,kwargs):
            self.counters.OPTIMIZER_STEPS_COMPLETED+=1;self.event('OPTIMIZER_STEP_RETURNED')
        fh=model.register_forward_pre_hook(forward);pre=optimizer.register_step_pre_hook(before);post=optimizer.register_step_post_hook(after)
        torch.Tensor.backward=backward;torch.load=load
        try:yield
        finally:
            torch.Tensor.backward=original_backward;torch.load=original_load;fh.remove();pre.remove();post.remove()
    def preserve_failure(self,error,registry,staging):
        self.event('FORMAL_EXECUTION_FAILED',error=repr(error))
        self.snapshot(status='FAILED_IMMUTABLE_HISTORY')
        failure={'status':'FORMAL_EXECUTION_FAILED','error':repr(error),'traceback':traceback.format_exc(),
                 'utc':utc_now(),'model':self.kind,'completed_epoch':self.completed_epoch,
                 **asdict(self.counters),'completed_epoch_identities':registry,'last_verified_checkpoint':self.verified_last,
                 'source_cleanup_state':staging,'automatic_restart':False,'B1_start_allowed':False}
        p=self.public/'failure.json'
        if p.exists():p=self.public/('failure_'+datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%S_%fZ')+'.json')
        with p.open('x',encoding='utf8',newline='\n') as f:json.dump(failure,f,indent=2,ensure_ascii=False,allow_nan=False);f.write('\n')
        atomic_json(self.public/'final_status.json',failure)
        return failure

def allowed_sources(contract,kind,frames):
    sources=set();nominals=set()
    for year in (2023,2024):
        for r in contract.records[kind,year]:
            sources.add(r['imerg_day_path'])
            if kind=='B1':nominals.update(r[f'slot_{s}_nominal'] for s in range(6))
            else:nominals.add(r['expected_nominal'])
    for nominal in nominals:sources.add(str(data.H_ROOT/frames[nominal]['relative_path']))
    return sorted(sources)

class AuditedTemporalDataset(data.TemporalDataset):
    """Same frozen decoding; only append governance records around __getitem__."""
    def __getitem__(self,index):
        try:
            item=super().__getitem__(index)
            append_jsonl(Path(self.audit_context['public'])/f'staging_worker_{os.getpid()}.jsonl',
                         {'sample_id':item['sample_id'],'index':index,'year':int(item['sample_id'][:4]),'staging':item['staging']},sync=False)
            return item
        except BaseException as error:
            if self.staging is not None:
                append_jsonl(Path(self.audit_context['public'])/f'staging_worker_{os.getpid()}.jsonl',
                    {'index':index,'error':repr(error),'staging':[asdict(x) for x in self.staging.records]},sync=True)
            raise

def audited_worker_init(worker_id):
    info=torch.utils.data.get_worker_info();context=info.dataset.audit_context
    authpath=Path(context['authorization_path'])
    if sha256(authpath)!=context['authorization_sha256']:raise PermissionError('Worker authorization SHA mismatch')
    value=json.loads(authpath.read_text(encoding='utf8'))
    if value['scope']!=SCOPES[info.dataset.model] or not value['AUTHORIZED'] or value['2025_raw_access']:
        raise PermissionError('Worker model-specific authorization mismatch')
    firewall=RawFirewall(True,context['allowed_sources'],Path(context['public'])/f'raw_access_worker_{os.getpid()}.jsonl')
    firewall.install();info.dataset.audit_firewall=firewall
    data.worker_init(worker_id)
    append_jsonl(Path(context['public'])/f'worker_identity_{os.getpid()}.jsonl',{'pid':os.getpid(),'worker_id':worker_id,
        'scope':value['scope'],'staging_root':str(info.dataset.staging.root),'temporary_byte_cap':734003200,'2025_firewall_active':True})

def staging_state(stage_root):
    p=Path(stage_root).resolve()
    if p.parent!=data.STAGE_ROOT.resolve() or not p.name.startswith('authorized_paired_run_'):
        raise ValueError('Only exact owned staging subtree can be audited')
    remaining=[{'path':str(q),'bytes':q.stat().st_size} for q in p.rglob('*') if q.is_file()] if p.exists() else []
    return {'owned_root':str(p),'remaining_temporary_files':remaining,'cleanup_success':not remaining,
            'raw_source_deleted':False,'old_diagnostic_cache_touched':False}

@contextmanager
def loader_items(loader):
    iterator=iter(loader)
    try:yield iterator
    finally:
        shutdown=getattr(iterator,'_shutdown_workers',None)
        if shutdown:shutdown()

def validate_boundary_audit(audit,epoch,coverage,train,val,order_digest):
    if audit.counters.FORMAL_OPTIMIZER_STEPS!=epoch*5228 or audit.counters.OPTIMIZER_STEPS_COMPLETED!=epoch*5228 or audit.counters.BACKWARD_CALLS!=epoch*5228:
        raise ValueError('Formal actual step/backward boundary count mismatch')
    if coverage['samples']!=10455 or val['N_valid']!=10501*3430 or val['validation_scenes']!=10501:
        raise ValueError('Full population boundary mismatch')
    if train['optimizer_steps']!=5228 or train['LR_start']!=lr_for_update((epoch-1)*5228+1,steps_per_epoch=5228) or train['LR_end']!=lr_for_update(epoch*5228,steps_per_epoch=5228):
        raise ValueError('Recorded schedule boundary mismatch')
    if train['ordered_sample_identity_sha256']!=order_digest:raise ValueError('Sample identity order mismatch')
    for field in ('strict_crossing_count','nonfinite_count','support_violation_count'):
        if val[field]!=0:raise ValueError('Numerical invariant failed: '+field)
