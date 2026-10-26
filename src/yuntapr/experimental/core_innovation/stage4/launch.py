"""Manifest-only I/O budget and one explicitly started seed2029 experiment."""
from pathlib import Path
import csv,json,sqlite3,sys
from yuntapr.data.dataset_b1 import IMERG_ROOT
from ..stage3.planning import digest,utc
from ..stage3.metered_io import path_key
from .data import PopulationPlan,read,sha
from . import POPULATION_SHA,EPOCHS,PAIR_CAP

SEED=2029
INVENTORY='stage0-b0-evidence/evidence/outputs/stage0_p0_audit/run_20260927T161311_417313Z/IMERG/imerg_inventory.csv'
CONFIG=dict(seed=SEED,models=['B3','B4'],lead=6,mode='retrospective',MEE_variables=13,MEE_width=16,
    fusion='TARGET_SP04_RESIDUAL',population_sha256=POPULATION_SHA,train=959,development=963,
    loss='E0',epochs=9,batch=2,validation_batch=8,updates_per_epoch=480,updates_per_model=4320,
    paired_attempt_cap=8640,replay_allowance=0,endpoint='FIXED_EPOCH_9',BEST_selection=False)


def code_hashes(root):
    paths=sorted((root/'src/yuntapr/experimental/core_innovation/stage4').glob('*.py'))+[root/'tools/core_stage4/start_pair.py']
    return {p.relative_to(root).as_posix():sha(p) for p in paths}


def target_index(plan):
    wanted={s[:10] for role in ('Train','Development') for s in plan.ids(role)};found={}
    with (plan.root/INVENTORY).open(encoding='utf-8-sig',newline='') as f:
        for row in csv.DictReader(f):
            if row['date'] not in wanted:continue
            day=row['date']
            if row['year'] not in ('2023','2024') or day in found or int(row['size_bytes'])<=0:raise ValueError('Missing/duplicate/forbidden target inventory identity')
            expected=f"{row['year']}\\imerg_{day.replace('-','')}.nc"
            if row['relative_path'].replace('/','\\')!=expected:raise ValueError('Target inventory path/date conflict')
            found[day]=int(row['size_bytes'])
    if set(found)!=wanted:raise ValueError('Exact target byte evidence unavailable; raw estimation forbidden')
    return found


def mask_evidence(plan,ledger):
    ref=read(plan.root/'config/science_v2/phase_a_protocol_frozen_v1.json')['identity']['yunnan_mask']
    old=read(plan.root/'docs/core_stage4/evidence.json')['receipt_sha256']['reads/reads.sqlite']
    if sha(ledger)!=old:raise ValueError('Wrong prior mask read ledger')
    db=sqlite3.connect(Path(ledger).resolve().as_uri()+'?mode=ro',uri=True)
    row=db.execute('SELECT state,expected_bytes,actual_bytes,sha256 FROM file_io WHERE path=?',(path_key(ref['path']),)).fetchone();db.close()
    if row is None or row[0]!='READ_COMPLETE' or row[1]!=row[2] or row[3]!=ref['sha256']:raise ValueError('Mask indexed bytes/hash not established')
    return ref['path'],dict(bytes=row[2],sha=row[3],year=2023,kind='static_mask')


def source_scope(plan,role,index,mask):
    files={}
    def add(path,value):
        key=path_key(path)
        if key in files and files[key]!=value:raise ValueError('Conflicting duplicate source identity')
        files[key]=value
    for sid,row in plan.rows[role].items():
        t=utc(sid)
        if t.year not in (2023,2024):raise PermissionError('2025 forbidden')
        for i in range(6):
            p,_=plan.sat[row[f'slot_{i}_nominal']];add(p,dict(plan.sources[p],kind='satellite'))
        for kind,p in plan.gfs[row['analysis_time']].items():add(p,dict(plan.sources[p],kind='GFS_'+kind))
        p=IMERG_ROOT/str(t.year)/('imerg_'+t.strftime('%Y%m%d')+'.nc')
        add(p,dict(bytes=index[sid[:10]],sha=row['imerg_sha256'],year=t.year,kind='IMERG'))
    add(*mask)
    by_kind={}
    for f in files.values():
        c=by_kind.setdefault(f['kind'],dict(files=0,bytes=0));c['files']+=1;c['bytes']+=f['bytes']
    return dict(ids=plan.ids(role),files=files,source_manifest_sha256=digest(files),file_count=len(files),
        bytes_per_pass=sum(f['bytes'] for f in files.values()),by_kind=by_kind)


def summarize_scopes(roles):
    per_role={r:{k:v[k] for k in ('file_count','bytes_per_pass','by_kind','source_manifest_sha256')} for r,v in roles.items()}
    target_sum=sum(v['by_kind']['IMERG']['bytes'] for v in roles.values())
    unique={p for v in roles.values() for p in v['files']}
    return dict(roles=per_role,passes_per_role=2*EPOCHS,total_passes=4*EPOCHS,
        logical_source_read_instances=2*EPOCHS*sum(v['file_count'] for v in roles.values()),
        logical_raw_bytes=2*EPOCHS*sum(v['bytes_per_pass'] for v in roles.values()),unique_source_files=len(unique),
        IMERG_combined_unique_bytes=target_sum,IMERG_cache_limit_bytes=512*1024**2,
        cache_over_limit=target_sum>512*1024**2,
        byte_definition='Full source payload delivered to Python; includes per-pass frozen mask, excludes metadata/checkpoints/OS sectors',
        loader_rule='Existing common batch loader reads GFS for both arms; B3 model does not consume GFS',replay_allowance=0)


def preparation(plan,run,request,mask_ledger):
    index=target_index(plan);mask=mask_evidence(plan,mask_ledger)
    roles={r:source_scope(plan,r,index,mask) for r in ('Train','Development')};budget=summarize_scopes(roles)
    if budget['cache_over_limit']:raise RuntimeError('IMERG exceeds buffer; implement sparse decoded-label cache before preparing launch')
    p=dict(status='PREPARED_WAITING_FINAL_START',config=CONFIG,data=plan.identity,roles=roles,budget=budget,
        private_inputs=dict(stage3_run=str(Path(run).resolve()),request=str(Path(request).resolve()),mask_read_ledger=str(Path(mask_ledger).resolve())),
        metadata_sha256={INVENTORY:sha(plan.root/INVENTORY)},code_sha256=code_hashes(plan.root),
        raw_source_opens_during_preparation=0,optimizer_updates=0,final_start_authorized=False)
    p['preparation_sha256']=digest(p);return p


class PassReader:
    def __init__(self,reader,scope):self.reader=reader;self.scope=scope
    def batch(self,*a,**kw):return self.reader.batch(*a,**kw)
    def close(self):
        failing=sys.exc_info()[0] is not None;actual=self.reader.meter.totals()
        path=self.reader.folder/'pass_receipt.json'
        with path.open('x',encoding='utf-8') as f:json.dump(dict(actual_reads=actual,expected_files=self.scope['file_count'],expected_bytes=self.scope['bytes_per_pass'],source_manifest_sha256=self.scope['source_manifest_sha256'],during_failure=failing),f,indent=2)
        self.reader.close()
        if not failing and (actual['opened_files']!=self.scope['file_count'] or actual['delivered_bytes']!=self.scope['bytes_per_pass'] or actual['states']!={'READ_COMPLETE':self.scope['file_count']}):raise RuntimeError('Full pass I/O receipt mismatch; no retry')


class ReaderFactory:
    def __init__(self,plan,prepared,start_id,*,allowed_models=('B3','B4')):
        if tuple(allowed_models) not in (('B3','B4'),('B5',),('B6',)):raise ValueError('Explicit supported reader arms required')
        self.plan=plan;self.prepared=prepared;self.start_id=start_id;self.seen=set();self.allowed_models=tuple(allowed_models)
    def __call__(self,role,epoch,ids,folder):
        from .data import BatchReader
        kind=Path(folder).name.split('_',1)[0];key=(kind,role,epoch);scope=self.prepared['roles'][role]
        if kind not in self.allowed_models or type(epoch)!=int or not 1<=epoch<=9 or key in self.seen or len(ids)!=len(scope['ids']) or set(ids)!=set(scope['ids']):raise PermissionError('Unlisted/repeated model-role-epoch pass')
        self.seen.add(key)
        reader=BatchReader(self.plan,{role:ids},folder,decision_id=self.start_id,max_files=scope['file_count'],max_bytes=scope['bytes_per_pass'],source_bytes={p:f['bytes'] for p,f in scope['files'].items()})
        if {p:{k:f[k] for k in ('bytes','sha')} for p,f in reader.meter.files.items()}!={p:{k:f[k] for k in ('bytes','sha')} for p,f in scope['files'].items()}:
            reader.close();raise PermissionError('Reader scope differs from prepared manifest')
        return PassReader(reader,scope)


def execute(prepared_path,output,*,start_authorization_id):
    # Caller must receive the human's final start command; --prepare never calls here.
    if not start_authorization_id:raise PermissionError('Explicit final researcher start authorization required')
    from .engine import FormalDecision,PairedExecutor,write
    p=read(prepared_path);body=dict(p);h=body.pop('preparation_sha256')
    if digest(body)!=h or p['status']!='PREPARED_WAITING_FINAL_START' or p['config']!=CONFIG:raise ValueError('Prepared launch/config changed')
    # Use the package repository root, never a private raw-source root.
    from yuntapr.contracts.loader import REPO_ROOT
    root=REPO_ROOT
    if code_hashes(root)!=p['code_sha256']:raise ValueError('Launch code changed since preparation')
    inputs=p['private_inputs'];plan=PopulationPlan(inputs['stage3_run'],inputs['request'],root=root)
    if plan.identity!=p['data'] or any(sha(root/name)!=h for name,h in p['metadata_sha256'].items()):raise ValueError('Data/metadata identity changed')
    # JSON IDs are lists; reader factory only compares exact membership.
    for role,scope in p['roles'].items():
        if digest(scope['files'])!=scope['source_manifest_sha256'] or set(scope['ids'])!=set(plan.ids(role)):raise ValueError('Prepared scope changed')
    if summarize_scopes(p['roles'])!=p['budget']:raise ValueError('Prepared I/O budget changed')
    decision=FormalDecision(start_authorization_id,SEED,POPULATION_SHA,True,True,True,PAIR_CAP)
    result=PairedExecutor(plan,output,decision=decision).run(ReaderFactory(plan,p,start_authorization_id))
    write(Path(output)/'completion.json',dict(**result,preparation_sha256=p['preparation_sha256'],I_O_budget=p['budget']))
    return result
