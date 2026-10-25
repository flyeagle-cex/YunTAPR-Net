"""One researcher-approved LAST recovery; parent evidence stays read-only."""
from pathlib import Path
import hashlib,json,os,sqlite3
from contextlib import closing
from ..stage3.planning import digest
from . import POPULATION_SHA,STEPS,PAIR_CAP

BASE='5b5298f41025db5b7b718fd736fc3fe6de516875'
LAST_SHA='9d4c8a4d3035c0b8327812466dc111afa72c074afb8612bf30f32a25bed7fc8e'
READ_CAP=1003568959114
FILE_CAP=299968
UPDATE_CAP=9120
AUTH='RESEARCHER_B3B4_SEED2029_F006_E0_RECOVERY1_20261024'


def read(path):return json.loads(Path(path).read_text(encoding='utf-8'))
def sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for chunk in iter(lambda:f.read(1024**2),b''):h.update(chunk)
    return h.hexdigest()
def query(path,sql):
    with closing(sqlite3.connect(Path(path).resolve().as_uri()+'?mode=ro',uri=True)) as db:return db.execute(sql).fetchall()
def write(path,value):
    with Path(path).open('x',encoding='utf-8') as f:
        json.dump(value,f,indent=2,allow_nan=False);f.flush();os.fsync(f.fileno())


def current_code(root):
    names=[p.relative_to(root).as_posix() for p in (root/'src/yuntapr/experimental/core_innovation/stage4').glob('*.py')]
    names+=['src/yuntapr/experimental/core_innovation/stage3/metered_io.py','tools/core_stage4/resume_pair.py']
    return {name:sha(root/name) for name in sorted(names)}


def build_request(parent,preparation,root):
    parent=Path(parent).resolve();preparation=Path(preparation).resolve();root=Path(root).resolve()
    p=read(preparation);body=dict(p);h=body.pop('preparation_sha256')
    if digest(body)!=h or p['config']['seed']!=2029 or p['config']['paired_attempt_cap']!=8640:raise ValueError('Original preparation changed')
    if read(parent/'failure.json')['status']!='STOP_NO_AUTOMATIC_RETRY':raise ValueError('Failed parent required')
    states=query(parent/'updates.sqlite','SELECT model,state,COUNT(*),MAX(u) FROM updates GROUP BY model,state')
    if states!=[('B3','RETURNED',1920,1920)]:raise ValueError('Recovery is limited to this 1920-update failure')
    receipt=read(parent/'B3_LAST_epoch_03.receipt.json')
    if receipt['checkpoint_sha256']!=LAST_SHA or sha(parent/'B3_LAST_epoch_03.pt')!=LAST_SHA:raise ValueError('Approved LAST identity differs')
    if receipt['updates']!=1440 or receipt['epoch']!=3 or receipt['population_sha256']!=POPULATION_SHA:raise ValueError('Wrong LAST endpoint')
    if (parent/'B3_LAST_epoch_04.receipt.json').exists() or (parent/'B4_train_01.json').exists():raise ValueError('Unexpected later formal evidence')
    bad=query(parent/'B3_dev_reads_04/reads.sqlite',"SELECT path,expected_bytes,actual_bytes,sha256 FROM file_io WHERE state!='READ_COMPLETE'")
    if len(bad)!=1 or bad[0][2]!=0 or bad[0][3]!=hashlib.sha256(b'').hexdigest():raise ValueError('Not the declared zero-byte interrupted source')
    source,n,_,_=bad[0];matches=[(k,v) for k,v in p['roles']['Development']['files'].items() if os.path.normcase(k)==os.path.normcase(source)]
    if len(matches)!=1 or matches[0][1]['bytes']!=n or matches[0][1]['year']!=2024:raise ValueError('Verification outside original scope')
    files=delivered=reserved=0;pins={}
    for name in ('updates.sqlite','failure.json','paired_initial_identity.json','paired_orders.json','B3_LAST_epoch_03.pt'):
        pins[name]=sha(parent/name)
    for epoch in range(1,5):
        pins[f'B3_train_{epoch:02d}.json']=sha(parent/f'B3_train_{epoch:02d}.json')
        if epoch<=3:
            for stem in ('development','LAST_epoch'):
                name=f'B3_{stem}_{epoch:02d}'+('.receipt.json' if stem=='LAST_epoch' else '.json');pins[name]=sha(parent/name)
        for role in ('train','dev'):
            name=f'B3_{role}_reads_{epoch:02d}/pass_receipt.json';r=read(parent/name);a=r['actual_reads'];pins[name]=sha(parent/name)
            files+=a['opened_files'];delivered+=a['delivered_bytes'];reserved+=a['reserved_bytes']
    if (files,delivered,reserved)!=(61947,207606187564,207611205829):raise ValueError('Parent I/O totals differ')
    for name,h in p['code_sha256'].items():
        original=preparation.parents[4]/name
        if sha(original)!=h:raise ValueError('Original execution source changed')
    future_bytes=15*sum(s['bytes_per_pass'] for s in p['budget']['roles'].values())
    future_files=15*sum(s['file_count'] for s in p['budget']['roles'].values())
    # Fifteen model-epochs remain (B3 E4..9, B4 E1..9), two role passes each.
    if (reserved+future_bytes+n,files+future_files+1)!=(READ_CAP,FILE_CAP):raise ValueError('Exact cumulative recovery budget differs')
    request=dict(status='PREPARED_WAITING_LIMITED_RECOVERY_APPROVAL',parent=str(parent),preparation=str(preparation),
        parent_pins=pins,preparation_sha256=p['preparation_sha256'],code_sha256=current_code(root),
        source=dict(path=matches[0][0],**matches[0][1]),prior_updates=1920,inherited_updates=1440,
        new_updates=7200,replayed_updates=480,cumulative_update_cap=UPDATE_CAP,
        prior_delivered_bytes=delivered,prior_reserved_bytes=reserved,prior_file_instances=files,
        new_training_bytes=future_bytes,new_training_file_instances=future_files,
        source_verification_bytes=n,source_verification_file_instances=1,
        cumulative_read_cap=READ_CAP,cumulative_file_cap=FILE_CAP,
        data_identity=json.loads(query(parent/'updates.sqlite','SELECT value FROM identity')[0][0])['data'],
        scientific_endpoint='B3_E9_B4_E9_NO_BEST',next_B3_update=1441,formal_seed=2029,
        automatic_retry=False,source_verification_completed=False,real_source_reads_during_preparation=0)
    request['request_sha256']=digest(request)
    return request


def validate_request(request,root):
    body=dict(request);h=body.pop('request_sha256')
    if digest(body)!=h or request['code_sha256']!=current_code(Path(root)):raise ValueError('Prepared recovery code/request changed')
    fresh=build_request(request['parent'],request['preparation'],root)
    if fresh!=request:raise ValueError('Recovery parent identity changed')


def verify_source(request,folder,decision_id):
    from ..stage3.statistics import SourceCache
    from ..stage3.metered_io import SourceMeter,path_key
    source=request['source'];manifest={'failed_source':dict(year=source['year'],bytes=source['bytes'],files=1,expected_sha256=source['sha'])}
    grant=dict(authorized=True,decision_id=decision_id,manifest_sha=digest(manifest),max_files=1,max_bytes=source['bytes'])
    cache=SourceCache(Path(folder)/'source_verification.sqlite',manifest=manifest,manifest_sha=digest(manifest),grant=grant,processor_id='SINGLE_FAILED_SOURCE_SHA_V1')
    path=path_key(source['path']);meter=SourceMeter(cache.db,{path:dict(source,job_id='failed_source')},max_files=1,max_bytes=source['bytes'])
    meter.install()
    try:
        def load():
            meter.active.add(path)
            try:
                with Path(source['path']).open('rb') as f:
                    while f.read(1024**2):pass
            finally:meter.active.discard(path)
            r=meter.receipt(path)
            return dict(year=source['year'],source_sha256=r['sha256'],raw_bytes_read=r['bytes'])
        result=cache.read_once('failed_source',load)
        return result
    finally:
        try:write(Path(folder)/'source_verification_receipt.json',meter.totals())
        finally:meter.uninstall();cache.close()


class ResumeState:
    def __init__(self,request):self.request=request;self.parent=Path(request['parent'])
    def completed_epochs(self,kind):return 3 if kind=='B3' else 0
    def validate(self,plan,decision):
        if plan.identity!=self.request['data_identity'] or decision.seed!=2029 or decision.decision_id!=AUTH:raise PermissionError('Recovery population/decision differs')
    def ledger(self,path,identity):return RecoveryLedger(path,dict(identity,recovery=dict(
        parent=str(self.parent),request_sha256=self.request['request_sha256'],prior_updates=1920,inherited_B3_updates=1440,
        cumulative_attempt_cap=UPDATE_CAP,new_segment_cap=7200)))
    def check_initial(self,value):
        if value!=read(self.parent/'paired_initial_identity.json'):raise ValueError('B3/B4 initial model or common weights changed')
    def check_orders(self,orders):
        old=read(self.parent/'paired_orders.json')
        if {str(e):dict(ids=list(o),sha256=digest(o)) for e,o in orders.items()}!=old:raise ValueError('Paired Train order changed')
    def restore(self,kind,model,optimizer,groups):
        if kind=='B4':return 0,[]
        import random,numpy as np,torch
        from yuntapr.training.phase_a_protocol import state_digest
        payload=torch.load(self.parent/'B3_LAST_epoch_03.pt',map_location='cpu',weights_only=False)
        if payload['identity']['data']!=self.request['data_identity'] or payload['optimizer_groups']!=groups or payload['epoch']!=3 or payload['updates']!=1440:raise ValueError('Checkpoint state/grouping identity differs')
        if payload['scheduler']!=dict(completed=1440,steps_per_epoch=480,original_horizon=24000):raise ValueError('Original schedule differs')
        model.load_state_dict(payload['model'],strict=True);optimizer.load_state_dict(payload['optimizer'])
        if state_digest(model.state_dict())!=state_digest(payload['model']):raise ValueError('Restored model tensors differ')
        if state_digest(optimizer.state_dict())!=state_digest(payload['optimizer']):raise ValueError('Restored optimizer tensors differ')
        rng=payload['rng'];random.setstate(rng['python']);np.random.set_state(rng['numpy']);torch.set_rng_state(rng['torch_cpu'])
        torch.cuda.set_rng_state_all(rng['torch_cuda'])
        reports=[read(self.parent/f'B3_development_{e:02d}.json') for e in range(1,4)]
        for e,report in enumerate(reports,1):
            if digest(report)!=read(self.parent/f'B3_LAST_epoch_{e:02d}.receipt.json')['validation_receipt_sha256']:raise ValueError('Inherited Dev report identity differs')
        return 1440,reports


class RecoveryLedger:
    expected_returned=7200
    def __init__(self,path,identity):
        from .engine import UpdateLedger
        self.base=UpdateLedger(path,identity);self.db=self.base.db
    def reserve(self,model,u):
        self.db.execute('BEGIN IMMEDIATE')
        try:
            n,total_returned=self.db.execute("SELECT COUNT(*),COALESCE(SUM(state='RETURNED'),0) FROM updates").fetchone()
            count,returned=self.db.execute("SELECT COUNT(*),COALESCE(SUM(state='RETURNED'),0) FROM updates WHERE model=?",(model,)).fetchone()
            offset=1440 if model=='B3' else 0
            if model not in ('B3','B4') or type(u)!=int or u!=offset+count+1 or u>4320 or count!=returned or n!=total_returned or n>=7200 or 1920+n>=UPDATE_CAP:raise PermissionError('Recovery cap/order/uncertain-update boundary')
            self.db.execute('INSERT INTO updates VALUES (?,?,?)',(model,u,'INTENT'));self.db.commit()
        except BaseException:self.db.rollback();raise
    def returned(self,*a):return self.base.returned(*a)
    def close(self):self.base.close()


def execute(request_path,output,*,authorization_id,approved_update_cap,approved_read_cap,approved_file_cap,root):
    if (authorization_id,approved_update_cap,approved_read_cap,approved_file_cap)!=(AUTH,UPDATE_CAP,READ_CAP,FILE_CAP):raise PermissionError('Explicit bounded replay/I/O approval required')
    request=read(request_path);validate_request(request,root);output=Path(output).resolve()
    if not output.is_relative_to(Path(root)/'docs/core_stage4/.local') or output.exists():raise PermissionError('Fresh isolated recovery output required')
    from .engine import resources,FormalDecision,PairedExecutor
    from .data import PopulationPlan
    from .launch import ReaderFactory
    resources()
    write(Path(request_path).with_name('launch_once.json'),dict(request_sha256=request['request_sha256'],authorization_id=authorization_id,output=str(output)))
    # Verification has its own durable once-only source intent and cannot retry.
    verification=output.with_name(output.name+'_source_verification');verification.mkdir(exist_ok=False)
    try:verify_source(request,verification,authorization_id)
    except BaseException as exc:
        write(verification/'failure.json',dict(status='STOP_NO_AUTOMATIC_RETRY',error=type(exc).__name__+': '+str(exc)));raise
    p=read(request['preparation']);inputs=p['private_inputs'];plan=PopulationPlan(inputs['stage3_run'],inputs['request'],root=root)
    decision=FormalDecision(authorization_id,2029,POPULATION_SHA,True,True,True)
    state=ResumeState(request)
    class RemainingReaders(ReaderFactory):
        def __call__(self,role,epoch,ids,folder):
            kind=Path(folder).name.split('_',1)[0]
            if kind=='B3' and epoch<=3:raise PermissionError('Already sealed B3 epoch cannot be reread')
            return super().__call__(role,epoch,ids,folder)
    try:result=PairedExecutor(plan,output,decision=decision,recovery=state).run(RemainingReaders(plan,p,authorization_id))
    except BaseException as exc:
        if output.exists() and not (output/'failure.json').exists():write(output/'failure.json',dict(status='STOP_NO_AUTOMATIC_RETRY',error=type(exc).__name__+': '+str(exc)))
        raise
    write(output/'completion.json',dict(**result,recovery_request_sha256=request['request_sha256'],parent=str(state.parent),cumulative_read_cap=READ_CAP,cumulative_file_cap=FILE_CAP))
    return result
