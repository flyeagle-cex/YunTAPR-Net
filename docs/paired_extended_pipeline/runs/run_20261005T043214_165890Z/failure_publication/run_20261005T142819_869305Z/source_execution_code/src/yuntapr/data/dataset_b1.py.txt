"""Pinned M1 sample sets and bounded per-worker staging, shared frozen scaler."""
from dataclasses import dataclass,asdict
from datetime import timedelta
from pathlib import Path
import csv,json,os,re,sys
import netCDF4
import numpy as np
import torch
from torch.utils.data import Dataset,get_worker_info
from yuntapr.contracts.loader import REPO_ROOT,sha256
from yuntapr.data.himawari_b13 import read_b13_local
from yuntapr.data.imerg_v07 import read_imerg_local
from yuntapr.data.sample_schema import utc
from yuntapr.data.staging import BoundedEnglishStaging

FREEZE=Path('docs/b1_scientific_freeze/runs/run_20261003T045139_110133Z')
AUDIT=Path('docs/b1_temporal_audit/runs/run_20261003T035724_142784Z')
SCALER_SHA='656fe7a929cbd8617b08427e8d1fa7029b26512253efb44faa576796137d4a31'
FRAME_SHA='a5054200d6bde11f2342c292ca72428d0558d5b5c5c640017844f0b4ed8c540e'
PINS={('B1',2023):'f2e84d15496dc0cace72647124323a060a94bebf5ceba3718024a00240f71219',
      ('B1',2024):'eba8f8177ad113baaa0db015a2d2f34fd8b814e5cd5c698a6881e426c5f3d84c',
      ('B0_MATCHED',2023):'05e760529a77fd141e68655308a00fa8f30d8db2591a8e22652de5c3b64432bc',
      ('B0_MATCHED',2024):'5bd26743d7a9a135733553790ccca226433e7495c220f8df9aacfad628a9690a'}
H_ROOT=Path(r'H:\葵花202303_202510')
IMERG_ROOT=Path(r'F:\云南极端降水数据\raw\IMERG')
STAGE_ROOT=Path(r'F:\pytorch\Research\stage0_himawari\cache\staging')
OFFSETS=(60,50,40,30,20,10)


def pinned(path,digest):
    if sha256(path)!=digest: raise ValueError('Pinned identity mismatch: '+str(path))
    return path


def allowed_time(value):
    t=utc(value)
    if t.year not in (2023,2024) or not 3<=t.month<=10: raise ValueError('2023/2024 March-October only; February/2025 hard reject')
    return t


def guard_source(path,kind):
    p=Path(path).resolve();root=(H_ROOT if kind=='B13' else IMERG_ROOT).resolve()
    if not p.is_relative_to(root): raise ValueError('Frozen source root required')
    match=re.search(r'(202[345])(\d{2})\d{2}',p.name) if kind!='B13' else re.search(r'(202[345])(\d{2})',str(p.relative_to(root)))
    if not match or int(match[1]) not in (2023,2024) or not 3<=int(match[2])<=10:
        raise ValueError('Forbidden raw date including 2025/February')
    return p


_guard_installed=False
def install_source_guard():
    """Installed independently in parent and spawned workers, before raw I/O."""
    global _guard_installed
    if _guard_installed:return
    def check(path,mode='r'):
        if not isinstance(path,(str,bytes,os.PathLike)):return
        text=os.fsdecode(path).replace('/','\\').lower()
        roots=((str(H_ROOT).lower(),'B13'),(str(IMERG_ROOT).lower(),'IMERG'))
        for prefix,kind in roots:
            if text.startswith(prefix+'\\'):
                guard_source(path,kind)
                if isinstance(mode,str) and any(c in mode for c in 'wa+'):raise PermissionError('Raw sources permanently read-only')
                if isinstance(mode,int) and mode&(os.O_WRONLY|os.O_RDWR|os.O_CREAT|os.O_TRUNC):raise PermissionError('Raw write forbidden')
    def audit(event,args):
        if event=='open':check(args[0],args[1] if args[1] is not None else args[2])
        if event in ('os.remove','os.rename','os.rmdir'):
            for p in args[:2]:
                if isinstance(p,(str,bytes)) and os.fsdecode(p).lower().startswith(str(H_ROOT).lower()):raise PermissionError('H raw mutation forbidden')
    sys.addaudithook(audit)
    original=netCDF4.Dataset
    def dataset(path,*args,**kwargs):
        check(path,kwargs.get('mode',args[0] if args else 'r'))
        # Unicode raw sources must pass through verified ASCII staging.
        text=str(path).replace('/','\\').lower()
        if text.startswith(str(H_ROOT).lower()) or text.startswith(str(IMERG_ROOT).lower()):raise PermissionError('Direct raw netCDF access forbidden; stage first')
        return original(path,*args,**kwargs)
    netCDF4.Dataset=dataset; _guard_installed=True


def load_records(model,year,root=REPO_ROOT):
    if (model,year) not in PINS:raise ValueError('Unapproved model/year')
    name='b1' if model=='B1' else 'b0_matched_control'
    p=pinned(Path(root)/FREEZE/f'{name}_{year}_formal_manifest.csv',PINS[model,year])
    with p.open(encoding='utf-8',newline='') as f: rows=list(csv.DictReader(f))
    if len(rows)!=(10455 if year==2023 else 10501):raise ValueError('Frozen sample count mismatch')
    if len({r['sample_id'] for r in rows})!=len(rows):raise ValueError('Duplicate sample IDs')
    for i,r in enumerate(rows):
        t=allowed_time(r['window_start']); a=utc(r['analysis_time'])
        if int(r['index'])!=i or t.year!=year or r['sample_id']!=r['window_start'] or a!=t+timedelta(minutes=30):raise ValueError('Sample identity/time mismatch')
        if int(r['target_valid_yunnan_cells'])!=3430 or r['frame_identity_index_sha256']!=FRAME_SHA:raise ValueError('Eligibility evidence mismatch')
        guard_source(r['imerg_day_path'],'IMERG')
        if model=='B1':
            for s,offset in enumerate(OFFSETS):
                if allowed_time(r[f'slot_{s}_nominal'])!=a-timedelta(minutes=offset):raise ValueError('Slot ordering changed')
        elif r['selected_slot']!='5' or allowed_time(r['expected_nominal'])!=a-timedelta(minutes=10):raise ValueError('Matched latest slot changed')
    return rows


def load_frames(root=REPO_ROOT):
    base=Path(root)/AUDIT; p=pinned(base/'frame_identity_index.json',FRAME_SHA)
    frames={}
    for rel,digest in json.loads(p.read_text())['files'].items():
        with pinned(base/rel,digest).open(encoding='utf-8',newline='') as f:
            for row in csv.DictReader(f):
                if row['nominal'] in frames:raise ValueError('Duplicate native nominal')
                frames[row['nominal']]=row
    return frames


def normalize(kelvin,root=REPO_ROOT):
    p=pinned(Path(root)/FREEZE/'normalization_b1_2023_shared_v1.json',SCALER_SHA)
    s=json.loads(p.read_text()); x=np.asarray(kelvin)
    if x.dtype!=np.float32 or not np.isfinite(x).all():raise ValueError('Full-valid decoded FP32 Kelvin required')
    return ((x.astype(np.float64)-s['mean_K'])/s['std_K']).astype(np.float32)


def check_frame(row,analysis):
    allowed_time(row['nominal'])
    if any(row[k]!='True' for k in ('present','readable','decoded','full_valid','metadata_valid')) or int(row['valid_count'])!=251001:raise ValueError('M1 frame rejected')
    if not utc(row['obs_start'])<=utc(row['obs_end'])<=utc(analysis):raise ValueError('Actual CF causality failed')


class TemporalDataset(Dataset):
    def __init__(self,model,records,frames,mapping,yunnan,staging_root,root=REPO_ROOT):
        if model not in ('B1','B0_MATCHED'):raise ValueError('Unknown model')
        self.model=model;self.records=records;self.frames=frames;self.mapping=mapping
        self.yunnan=np.asarray(yunnan,dtype=bool);self.stage_base=Path(staging_root);self.root=Path(root);self.staging=None
        if self.yunnan.shape!=(100,100) or int(self.yunnan.sum())!=3430:raise ValueError('Frozen Yunnan mask required')
        if not self.stage_base.resolve().is_relative_to(STAGE_ROOT.resolve()):raise ValueError('Bounded English staging root required')

    def __len__(self):return len(self.records)

    def set_worker(self,suffix):
        install_source_guard()
        self.staging=BoundedEnglishStaging(self.stage_base/str(suffix),734003200,True,True)

    def __getitem__(self,index):
        if self.staging is None:self.set_worker('parent_'+str(os.getpid()))
        r=self.records[index]; t=allowed_time(r['window_start']); a=utc(r['analysis_time'])
        if a!=t+timedelta(minutes=30):raise ValueError('Frozen analysis-time binding changed')
        slots=range(6) if self.model=='B1' else (5,)
        values=[]; details=[]; before=len(self.staging.records)
        for s in slots:
            nominal=(a-timedelta(minutes=OFFSETS[s])).isoformat();allowed_time(nominal)
            fr=self.frames[nominal];check_frame(fr,a)
            source=guard_source(H_ROOT/fr['relative_path'],'B13')
            if source.stat().st_size!=int(fr['source_bytes']):raise ValueError('Native source size changed')
            with self.staging.local(source) as local:
                pinned(local,fr['source_sha256'])
                x,v,actual=read_b13_local(local,self.mapping,nominal)
                if not v.all() or not np.isfinite(x).all():raise ValueError('M1 actual partial/all-fill/nonfinite rejection')
                if actual.obs_start!=utc(fr['obs_start']) or actual.obs_end!=utc(fr['obs_end']) or actual.date_created!=utc(fr['date_created']):raise ValueError('Actual CF identity changed')
                if not actual.obs_start<=actual.obs_end<=a:raise ValueError('Future frame rejected')
                values.append(normalize(x,self.root));details.append({'slot':s,'nominal_time':nominal,'obs_start':actual.obs_start.isoformat(),'obs_end':actual.obs_end.isoformat(),'date_created':actual.date_created.isoformat(),'causality_pass':True,'source_sha256':fr['source_sha256']})
        source=guard_source(r['imerg_day_path'],'IMERG')
        with self.staging.local(source) as local:
            pinned(local,r['imerg_sha256'])
            with netCDF4.Dataset(str(local)) as ds:
                if ds.source!='GPM_3IMERGHH_07' or 'IMERG Final Run V07' not in ds.title:raise ValueError('IMERG V07 Final metadata mismatch')
            y,v,t=read_imerg_local(local,int(r['imerg_index']),self.mapping)
            if t!=utc(r['window_start']) or int((v&self.yunnan).sum())!=3430:raise ValueError('Target identity/eligibility changed')
        staging=[asdict(item) for item in self.staging.records[before:]]
        if not all(q['cleanup_success'] and q['sha256_match'] and q['size_match'] and not q['error'] for q in staging):raise IOError('Staging verification/cleanup failed')
        # Do not accumulate unbounded worker logs over a complete epoch.
        del self.staging.records[:]
        return {'x':np.stack(values),'y':y[None],'valid':v[None],'yunnan':self.yunnan[None],
                'index':index,'sample_id':r['sample_id'],'frames':details,'staging':staging,'worker_pid':os.getpid(),
                'target_sha256':r['imerg_sha256'],'normalization_sha256':SCALER_SHA}


def worker_init(worker_id):
    info=get_worker_info();info.dataset.set_worker(f'worker_{worker_id}_{os.getpid()}');torch.set_num_threads(1)


def collate(items):return items


@dataclass
class TemporalBatch:
    x_b13:torch.Tensor
    b13_valid_mask:torch.Tensor
    y_imerg:torch.Tensor
    imerg_valid_mask:torch.Tensor
    yunnan_eval_mask:torch.Tensor
    sample_ids:list
    indices:list


def make_batch(items,device='cuda'):
    if not items:raise ValueError('Empty batch')
    def stack(name):return torch.as_tensor(np.stack([r[name] for r in items]),device=device)
    x=stack('x');y=stack('y');valid=stack('valid');mask=stack('yunnan')
    if x.dtype!=torch.float32 or not torch.isfinite(x).all() or x.shape[1:] not in ((1,501,501),(6,501,501)):raise ValueError('M1 tensor contract failed')
    if int((valid&mask).sum())!=len(items)*3430:raise ValueError('Actual denominator must be B*3430')
    return TemporalBatch(x,torch.ones_like(x,dtype=torch.bool),y,valid,mask,[r['sample_id'] for r in items],[r['index'] for r in items])
