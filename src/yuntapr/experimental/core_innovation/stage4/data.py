"""Pinned Stage3 membership/scalers and a bounded, once-only real batch loader."""
from pathlib import Path
from dataclasses import dataclass
from datetime import timedelta
import csv,hashlib,json,sqlite3
import numpy as np
import netCDF4
import torch
from yuntapr.contracts.loader import REPO_ROOT,load_contract
from yuntapr.data.dataset_b1 import H_ROOT,IMERG_ROOT,SCALER_SHA
from yuntapr.data.imerg_v07 import decode_imerg
from yuntapr.spatial.sp04_mapping import load_sp04
from ..grid import GridSpec,frozen_sp04_grid
from ..gfs import ForecastIdentity,VariableRequest,read_gfs_file,combine_environment
from ..multispectral import TrainNormalization,prepare_multispectral
from ..stage2 import CHANNELS,OFFSETS,MEE_V13_KEYS
from ..stage2.environment import EnvironmentScaler,V13_UNITS,prepare_mee
from ..stage2.population import read_seven_band
from ..stage2.coupling import TargetBinding
from ..stage3.planning import digest,utc
from ..stage3.statistics import SourceCache
from ..stage3.metered_io import SourceMeter,path_key
from . import POPULATION_SHA,TRAIN_N,DEV_N


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def read(path):return json.loads(Path(path).read_text(encoding='utf-8'))


class PopulationPlan:
    def __init__(self,run,request,*,root=REPO_ROOT):
        self.root=Path(root);run=Path(run);request=Path(request)
        evidence=read(self.root/'docs/core_stage3/execution_summary/evidence.json')
        for name in ('populations.json','train_statistics.json','statistics.sqlite'):
            if sha(run/name)!=evidence['private_receipt_sha256'][name]:raise ValueError('Stage3 pinned artifact changed: '+name)
        self.pop=read(run/'populations.json');self.fit=read(run/'train_statistics.json');r=read(request)
        if r['request_sha256']!=evidence['request_sha256'] or digest({k:v for k,v in r.items() if k!='request_sha256'})!=r['request_sha256']:raise ValueError('Wrong request')
        self.rows={};self.sat={};self.gfs={};self.sources={}
        db=sqlite3.connect((run/'statistics.sqlite').resolve().as_uri()+'?mode=ro',uri=True)
        indexed={Path(p).name:(p,n,s) for p,state,n,s in db.execute('SELECT path,state,actual_bytes,sha256 FROM file_io') if state=='READ_COMPLETE'};db.close()
        for role,n in (('Train',TRAIN_N),('Development',DEV_N)):
            m=read(request.parent/r['roles'][role]['manifest']);body=dict(m);h=body.pop('manifest_sha256')
            if digest(body)!=h or h!=evidence['candidate_manifest_sha256'][role]:raise ValueError('Wrong candidate manifest')
            ids=tuple(self.pop['populations'][role]['accepted_ids'])
            if len(ids)!=n or len(set(ids))!=n or digest(sorted(ids))!=evidence['populations'][role]['population_sha256']:raise ValueError('Final population mismatch')
            self.rows[role]={row['sample_id']:row for row in m['scene_records'] if row['sample_id'] in ids}
            if len(self.rows[role])!=n:raise ValueError('Missing final scene records')
            for f in m['satellite_files']:
                p=H_ROOT/f['relative_path'];self.sat[f['nominal']]=(str(p),f)
                self.sources[str(p)]=dict(bytes=f['expected_bytes'],sha=f['expected_sha256'],year=m['year'])
            for f in m['gfs_files']:
                name=Path(f['relative_path']).name;p,nbytes,hsh=indexed[name]
                if nbytes!=f['bytes'] or f['lead']!=6:raise ValueError('GFS source identity mismatch')
                self.gfs.setdefault(f['valid'],{})[f['kind']]=p
                self.sources[p]=dict(bytes=nbytes,sha=hsh,year=m['year'])
        if digest({r:sorted(self.rows[r]) for r in self.rows})!=POPULATION_SHA or self.fit['population_sha256']!=POPULATION_SHA:raise ValueError('Joint population SHA mismatch')
        f=self.fit
        if f['fit_years']!=[2023] or f['fit_role']!='Train' or f['B13_refitted'] or tuple(f['environment_order'])!=MEE_V13_KEYS:raise ValueError('Train-only statistics contract')
        self.spectral={k:TrainNormalization(**v) for k,v in f['spectral_scalers'].items()}
        if self.spectral['B13'].population_id!=SCALER_SHA or any(v.population_id!=POPULATION_SHA for k,v in self.spectral.items() if k!='B13'):raise ValueError('Spectral scaler ancestry')
        self.environment={k:EnvironmentScaler(k,f['environment_scalers'][k]['mean'],f['environment_scalers'][k]['std'],u,(2023,),'Train',POPULATION_SHA) for k,u in zip(MEE_V13_KEYS,V13_UNITS)}
        self.identity=dict(population_sha256=POPULATION_SHA,populations_sha256=sha(run/'populations.json'),statistics_sha256=sha(run/'train_statistics.json'),lead=6,mode='retrospective',train=TRAIN_N,dev=DEV_N)
        qc=self.root/'docs/b0_pretraining_closure/runs/run_20260930T095416Z/formal_sample_eligibility_2023_2024.csv'
        with qc.open(encoding='utf-8-sig',newline='') as stream:
            self.strong_scene_ids=tuple(v['window_start'] for v in csv.DictReader(stream) if v['window_start'] in self.rows['Development'] and float(v['imerg_max_yunnan_mmhr'] or 0)>=20)
        if len(self.strong_scene_ids)!=evidence['populations']['Development']['distribution']['scenes_max_ge_20_mm_h']:raise ValueError('Inherited strong-scene QC identity conflict')
        self.identity['target_QC_sha256']=sha(qc)
        self.identity['candidate_manifest_sha256']=evidence['candidate_manifest_sha256']

    def ids(self,role):return tuple(self.rows[role])

    def dry_ids(self):
        # Predeclared calendar subset; no selection by rainfall or model output.
        return {'Train':tuple(x for x in self.ids('Train') if x.startswith('2023-05-01'))[:2],
                'Development':tuple(x for x in self.ids('Development') if x[:10] in ('2024-05-01','2024-05-02'))[:8]}


def variable_requests():
    main=tuple(VariableRequest(q+str(p),q,name,p*100.) for p in (850,700) for q,name in (('u','u-component_of_wind_isobaric'),('v','v-component_of_wind_isobaric')))+(
        VariableRequest('ps','surface_pressure','Pressure_surface'),VariableRequest('pwat','precipitable_water','Precipitable_water_entire_atmosphere_single_layer'),VariableRequest('cape','cape','Convective_available_potential_energy_surface'))
    thermo=tuple(VariableRequest(q+str(p),q,name,p*100.) for p in (850,700,500) for q,name in (('temperature','Temperature_isobaric'),('relative_humidity','Relative_humidity_isobaric')))
    return dict(main=main,thermo=thermo)


def target_memory(raw,index,mapping,expected_time):
    with netCDF4.Dataset('stage4_target.nc',memory=raw) as ds:
        ds.set_auto_maskandscale(False);v=ds['precipitation']
        if ds.source!='GPM_3IMERGHH_07' or 'IMERG Final Run V07' not in ds.title or v.dimensions!=('time','lat','lon') or v.shape!=(48,130,140) or v.units!='mm hr-1':raise ValueError('Inherited IMERG V07 Final contract')
        mapping.assert_axes(mapping.axes['native_lat'],mapping.axes['native_lon'],ds['lat'][10:110],ds['lon'][20:120])
        t=ds['time'];d=netCDF4.num2date(t[index],t.units,calendar=getattr(t,'calendar','standard'),only_use_cftime_datetimes=False)
        if utc(d.isoformat()+'Z')!=utc(expected_time):raise ValueError('Wrong target half-hour')
        return decode_imerg(np.asarray(v[index,10:110,20:120]),{k:v.getncattr(k) for k in v.ncattrs()})


@dataclass
class Batch:
    x:torch.Tensor
    native_valid:torch.Tensor
    environment:torch.Tensor
    environment_valid:torch.Tensor
    rate:torch.Tensor
    valid:torch.Tensor
    region:torch.Tensor
    ids:tuple
    analyses:tuple
    role:str
    identity:dict
    def to(self,device):
        return Batch(*(getattr(self,k).to(device) for k in ('x','native_valid','environment','environment_valid','rate','valid','region')),self.ids,self.analyses,self.role,self.identity)


class BatchReader:
    """Explicit finite read scope; ledger precedes I/O, no retry or resume.

    One reader owns one pass. Further epochs require independently authorized
    fresh scopes; Stage4 CLI only supplies the ten declared dry-run scenes.
    """
    def __init__(self,plan,ids_by_role,folder,*,decision_id,max_files=84,max_bytes=512*1024**2):
        self.plan=plan;self.ids_by_role=ids_by_role;self.folder=Path(folder);self.folder.mkdir(exist_ok=False)
        self.mapping=load_sp04(plan.root);self.grid=frozen_sp04_grid(plan.root);self.native=GridSpec(self.mapping.axes['native_lat'],self.mapping.axes['native_lon'])
        chosen={};self.target_paths={};self.target_buffers={};self.scene_seen=set()
        for role,ids in ids_by_role.items():
            if len(set(ids))!=len(ids) or not set(ids)<=set(plan.ids(role)):raise PermissionError('Unlisted scene')
            for sid in ids:
                row=plan.rows[role][sid]
                for i in range(6):
                    p,_=plan.sat[row[f'slot_{i}_nominal']];chosen[p]=plan.sources[p]
                for p in plan.gfs[row['analysis_time']].values():chosen[p]=plan.sources[p]
                t=utc(sid);p=IMERG_ROOT/str(t.year)/('imerg_'+t.strftime('%Y%m%d')+'.nc')
                self.target_paths[sid]=str(p);chosen[str(p)]=dict(bytes=p.stat().st_size,sha=row['imerg_sha256'],year=t.year)
        ref=read(plan.root/'config/science_v2/phase_a_protocol_frozen_v1.json')['identity']['yunnan_mask']
        self.mask_path=ref['path'];chosen[self.mask_path]=dict(bytes=Path(self.mask_path).stat().st_size,sha=ref['sha256'],year=2023)
        jobs={str(i):dict(year=f['year'],bytes=f['bytes'],files=1,expected_sha256=f['sha']) for i,(p,f) in enumerate(chosen.items())}
        if len(jobs)>max_files or sum(f['bytes'] for f in jobs.values())>max_bytes:raise PermissionError('Small batch read cap exceeded')
        self.path_jobs={path_key(p):str(i) for i,p in enumerate(chosen)}
        files={p:dict(f,job_id=str(i)) for i,(p,f) in enumerate(chosen.items())}
        grant=dict(authorized=True,decision_id=decision_id,manifest_sha=digest(jobs),max_files=max_files,max_bytes=max_bytes)
        self.cache=SourceCache(self.folder/'reads.sqlite',manifest=jobs,manifest_sha=digest(jobs),grant=grant,processor_id='STAGE4_BATCH_ONLY_V1')
        self.meter=SourceMeter(self.cache.db,files,max_files=max_files,max_bytes=max_bytes);self.meter.install()
        self.yunnan=None;self.requests=variable_requests()
    def _read(self,path,decoder):
        key=self.path_jobs[path_key(path)];box=[]
        def load():
            self.meter.active={path_key(path)}
            try:
                box.append(decoder());r=self.meter.receipt(path)
                return dict(year=self.cache.manifest[key]['year'],source_sha256=r['sha256'],raw_bytes_read=r['bytes'])
            finally:self.meter.active=set()
        self.cache.read_once(key,load)
        if not box:raise RuntimeError('Already-read source has no retained decoder object; no automatic reread')
        return box[0]
    def _bytes(self,path):
        def decode():
            with Path(path).open('rb') as f:return f.read()
        return self._read(path,decode)
    def region(self):
        if self.yunnan is None:
            raw=self._bytes(self.mask_path)
            with netCDF4.Dataset('stage4_mask.nc',memory=raw) as ds:
                full=np.asarray(ds['yunnan_mask'][:],dtype=bool)
                self.mapping.assert_axes(self.mapping.axes['native_lat'],self.mapping.axes['native_lon'],ds['lat'][10:110],ds['lon'][20:120])
                if full.shape!=(130,140) or int(full.sum())!=3430:raise ValueError('Frozen mask changed')
                self.yunnan=full[10:110,20:120].copy()
        return self.yunnan
    def batch(self,role,ids):
        if not ids or not set(ids)<=set(self.ids_by_role.get(role,())) or any(s in self.scene_seen for s in ids):raise PermissionError('Unlisted/repeated batch; retain tensor for paired dry-run')
        values=[];masks=[];envs=[];env_valids=[];rates=[];valids=[];analyses=[]
        region=self.region()
        for sid in ids:
            row=self.plan.rows[role][sid];frames=[];frame_masks=[];receipts=[]
            for i in range(6):
                p,f=self.plan.sat[row[f'slot_{i}_nominal']]
                x,m,r=self._read(p,lambda p=p,f=f:read_seven_band(p,nominal=f['nominal'],mapping=self.mapping))
                if r['obs_start']!=f['obs_start'] or r['obs_end']!=f['obs_end']:raise ValueError('Observation identity changed')
                frames.append(x);frame_masks.append(m);receipts.append(r)
            analysis=utc(row['analysis_time'])
            normalized=prepare_multispectral(np.stack(frames)[None],np.stack(frame_masks)[None],source_channels=CHANNELS,selected_channels=CHANNELS,
                units=dict.fromkeys(CHANNELS,'K'),normalization=self.plan.spectral,nominal_times=[[utc(r['nominal']) for r in receipts]],
                obs_start_times=[[utc(r['obs_start']) for r in receipts]],obs_end_times=[[utc(r['obs_end']) for r in receipts]],analysis_times=[analysis],
                expected_offsets_before_analysis_minutes=OFFSETS,source_grid=self.native,expected_grid=self.native,missing_policy='reject')
            v,m=normalized.flatten_time_channels();values.append(v[0]);masks.append(m[0]);del frames,frame_masks,normalized,x
            identity=ForecastIdentity(analysis-timedelta(hours=6),timedelta(hours=6),analysis)
            decoded={k:self._read(p,lambda p=p,k=k:read_gfs_file(p,identity,self.requests[k])) for k,p in self.plan.gfs[row['analysis_time']].items()}
            frame=combine_environment(decoded['main'],decoded['thermo'],target_valid_time=analysis,decision_time=analysis,mode='retrospective')
            TargetBinding(utc(sid),analysis,tuple(utc(r['nominal']) for r in receipts),tuple(utc(r['obs_start']) for r in receipts),tuple(utc(r['obs_end']) for r in receipts)).check_forecast(identity,valid_policy='valid_equals_analysis_retrospective_candidate')
            e,ev,_=prepare_mee(frame,target_grid=self.grid,scalers=self.plan.environment,keys=MEE_V13_KEYS);envs.append(e);env_valids.append(ev)
            p=self.target_paths[sid]
            if p not in self.target_buffers:
                expected=self.cache.manifest[self.path_jobs[path_key(p)]]['bytes']
                if sum(len(v) for v in self.target_buffers.values())+expected>512*1024**2:raise RuntimeError('Bounded target buffer exhausted; no eviction/reread')
                self.target_buffers[p]=self._bytes(p)
            y,valid=target_memory(self.target_buffers[p],int(row['imerg_index']),self.mapping,sid)
            if int((valid&region).sum())!=3430:raise ValueError('Target denominator changed')
            rates.append(y[None]);valids.append(valid[None]);analyses.append(row['analysis_time']);self.scene_seen.add(sid)
        tensor=lambda a:torch.from_numpy(np.stack(a))
        return Batch(tensor(values),tensor(masks),tensor(envs),tensor(env_valids),tensor(rates),tensor(valids),tensor([region[None]]*len(ids)),tuple(ids),tuple(analyses),role,self.plan.identity)
    def close(self):
        self.target_buffers.clear();self.meter.uninstall();self.cache.close()
