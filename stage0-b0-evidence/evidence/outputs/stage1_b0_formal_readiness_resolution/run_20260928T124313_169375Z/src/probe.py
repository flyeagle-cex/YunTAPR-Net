"""Read-only, metadata/coordinates-only evidence collection; no science arrays."""
from pathlib import Path
import contextlib, csv, hashlib, importlib.metadata, json, re, shutil, sys, time, uuid
from datetime import datetime, timezone
import numpy as np
import netCDF4

RUN = Path(r'F:\pytorch\Research\outputs\stage1_b0_formal_readiness_resolution\run_20260928T124313_169375Z')
SMOKE = Path(r'F:\pytorch\Research\outputs\stage1_b0_engineering_smoke\run_20260928T121619_125413Z')
FREEZE = Path(r'F:\pytorch\Research\outputs\stage0_spatial_decision_update\run_20260928T102636_513428Z')
P0 = Path(r'F:\pytorch\Research\outputs\stage0_p0_audit\run_20260927T161311_417313Z')
CONT = Path(r'F:\pytorch\Research\outputs\stage0_continuous_engineering\run_20260928T041855_828904Z')
RAW = Path(r'F:\云南极端降水数据')
def clean(x):
    if isinstance(x, bytes): return x.decode('utf-8', errors='replace')
    if isinstance(x, np.ndarray): return clean(x.tolist())
    if isinstance(x, np.generic): return clean(x.item())
    if isinstance(x, float) and not np.isfinite(x): return str(x)
    if isinstance(x, dict): return {str(k):clean(v) for k,v in x.items()}
    if isinstance(x, (tuple,list)): return [clean(v) for v in x]
    if isinstance(x, Path): return str(x)
    return x
def writej(rel,obj):
    p=RUN/rel; p.parent.mkdir(parents=True,exist_ok=True)
    with p.open('x',encoding='utf-8') as f: json.dump(clean(obj),f,ensure_ascii=False,indent=2,allow_nan=False)
def sha(p):
    h=hashlib.sha256()
    with Path(p).open('rb') as f:
        for b in iter(lambda:f.read(4*1024*1024),b''): h.update(b)
    return h.hexdigest()
def fp(p):
    p=Path(p); s=p.stat(); return dict(path=str(p),sha256=sha(p),size_bytes=s.st_size,mtime_ns=s.st_mtime_ns)
def attrs(o): return {a:clean(o.getncattr(a)) for a in o.ncattrs()}

@contextlib.contextmanager
def staged(source):
    """Only process-owned copies in THIS run; one file at a time."""
    source=Path(source); base=(RUN/'cache/staging').resolve(); base.mkdir(parents=True,exist_ok=True)
    dst=base/(uuid.uuid4().hex+source.suffix); before=fp(source)
    assert dst.parent.resolve()==base and not dst.exists() and str(base).isascii()
    record={'source':str(source),'temporary_path':str(dst),'before':before,'cleanup_success':False}
    created=False
    try:
        t=time.perf_counter()
        with source.open('rb') as sf, dst.open('xb') as df:
            created=True; shutil.copyfileobj(sf,df,1024*1024)
        record.update(copy_seconds=time.perf_counter()-t,temporary_bytes=dst.stat().st_size,
                      size_verified=dst.stat().st_size==before['size_bytes'],sha256_verified=sha(dst)==before['sha256'])
        assert record['size_verified'] and record['sha256_verified']
        t=time.perf_counter()
        try: yield dst
        finally: record['read_seconds']=time.perf_counter()-t
    finally:
        if created:
            try:
                assert dst.resolve().parent==base
                dst.unlink(); record['cleanup_success']=True
            except OSError as exc: record['cleanup_error']=repr(exc)
        record['after']=fp(source); record['source_unchanged']=record['before']==record['after']
        with (RUN/'logs/staging.jsonl').open('a',encoding='utf-8') as f: f.write(json.dumps(record,ensure_ascii=False)+'\n')
        assert record['source_unchanged']

def inspect_nc(source, include_coords=False):
    result={'source':str(source),'source_fingerprint':fp(source),'groups':{}}
    with staged(source) as local:
        with netCDF4.Dataset(str(local),'r') as nc:
            def walk(g,path):
                rec={'attributes':attrs(g),'dimensions':{k:len(v) for k,v in g.dimensions.items()},'variables':{}}
                for k,v in g.variables.items():
                    vr={'shape':list(v.shape),'dimensions':list(v.dimensions),'dtype':str(v.dtype),'attributes':attrs(v)}
                    # Explicitly exclude precipitation/brightness-temperature arrays.
                    if k.lower() in ('time','time_bnds','time_bounds') or (include_coords and k.lower() in ('lat','lon','latitude','longitude')):
                        assert v.size<=10000
                        v.set_auto_maskandscale(False); a=np.asarray(v[:]); vr['raw_values']=clean(a)
                        u=getattr(v,'units',None); cal=getattr(v,'calendar','standard')
                        if u and 'since' in u:
                            vr['decoded_values']=[str(x) for x in np.asarray(netCDF4.num2date(a,u,calendar=cal)).flat]
                    rec['variables'][k]=vr
                result['groups'][path]=rec
                for k,child in g.groups.items(): walk(child,path.rstrip('/')+'/'+k)
            walk(nc,'/')
    return result

def main():
    env={'sys_executable':sys.executable,'python':sys.version,'utc':datetime.now(timezone.utc).isoformat(),'versions':{}}
    for name in ['numpy','pandas','netCDF4','pyarrow','h5py','h5netcdf','pytest','xarray','numcodecs','zarr','shapely','pyproj']:
        try: env['versions'][name]=importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError: env['versions'][name]='NOT_INSTALLED_NO_INSTALL_ATTEMPT'
    assert Path(sys.executable)==Path(r'F:\pytorch\Research\.venv\Scripts\python.exe')
    writej('logs/environment.json',env)
    # Preserve all prior registered smoke artifacts, plus manifest files themselves.
    old=[]
    for row in csv.DictReader((SMOKE/'output_manifest.csv').open(encoding='utf-8-sig')):
        p=SMOKE/row['relative_path']; actual=fp(p)
        assert actual['sha256']==row['sha256'] and actual['size_bytes']==int(row['size_bytes']), str(p)
        old.append(actual)
    for p in [SMOKE/'output_manifest.csv',SMOKE/'output_manifest.parquet',FREEZE/'freeze_registry.json']:
        old.append(fp(p))
    registry=json.loads((FREEZE/'freeze_registry.json').read_text(encoding='utf-8'))
    for a in registry['artifacts'].values():
        item=fp(FREEZE/a['relative_path']); assert item['sha256']==a['sha256']; old.append(item)
    for rel in ['IMERG/imerg_inventory.csv','IMERG/imerg_time_audit.csv','IMERG/imerg_original_metadata.jsonl','IMERG/imerg_time_bounds_metadata_presence.csv']:
        old.append(fp(P0/rel))
    old.append(fp(CONT/'CROSS_SOURCE/research_period_data_matrix.csv'))
    writej('logs/immutable_inputs_before.json',old)
    rows=list(csv.DictReader((RUN/'DISCOVERY/file_name_candidates.csv').open(encoding='utf-8-sig')))
    natives=[Path(x['path']) for x in rows if x['kind']=='NATIVE_GRANULE_NAME']
    selected=[]
    for group in sorted({p.parent for p in natives}):
        files=sorted(p for p in natives if p.parent==group)
        selected.extend(files[i] for i in sorted({0,len(files)//2,len(files)-1}))
    records=[]
    for p in selected:
        try:
            meta=inspect_nc(p); records.append(meta)
            print('NATIVE_METADATA',p.name, 'groups',list(meta['groups']),flush=True)
        except Exception as exc: records.append({'source':str(p),'error':repr(exc)}); print('PROBE_ERROR',repr(exc),flush=True)
    writej('TIME/native_metadata_probes.json',records)
    conversions=[]
    for day in ['20210825','20240501','20240527','20240701']:
        p=RAW/'raw/IMERG'/day[:4]/('imerg_'+day+'.nc')
        if p.exists(): conversions.append(inspect_nc(p,True))
    late=RAW/'raw/IMERG_LATE/2025/imerg_late_20251001.nc'
    conversions.append(inspect_nc(late,True))
    writej('TIME/converted_metadata_probes.json',conversions)
    smoke=json.loads((SMOKE/'B0_SMOKE/smoke_sample_metadata.json').read_text(encoding='utf-8'))
    hm=inspect_nc(Path(smoke[0]['himawari_path']),True)
    writej('SPATIAL/himawari_coordinate_metadata.json',hm)
    av=hm['groups']['/']['variables']
    (RUN/'SPATIAL').mkdir(exist_ok=True)
    np.savez(RUN/'SPATIAL/himawari_actual_coordinates.npz',latitude=np.array(av['latitude']['raw_values'],dtype=av['latitude']['dtype']),longitude=np.array(av['longitude']['raw_values'],dtype=av['longitude']['dtype']))
    manifests=[]
    for name in ['imerg_manifest.jsonl','imerg_completion_manifest.jsonl','imerg_late_completion_manifest.jsonl','backup_manifest.jsonl','pipeline_manifest.jsonl']:
        p=RAW/'manifests'/name; entries=[json.loads(l) for l in p.read_text(encoding='utf-8-sig').splitlines() if l.strip()]
        hits=[x for x in entries if any(d in str(x.get('date','')) for d in ['2021-08-25','2024-05-01','2024-05-27','2024-07-01','2025-10'])]
        manifests.append({'source':str(p),'fingerprint':fp(p),'row_count':len(entries),'first':entries[:1],'last':entries[-1:],'selected_rows':hits})
    writej('TIME/local_manifest_evidence.json',manifests)
    gap={'status':'MISSING','product_required':'IMERG V07 Final','known_final_october_files':[str(p) for p in (RAW/'raw/IMERG/2025').glob('*202510*')],
         'late_october_files':[str(p) for p in (RAW/'raw/IMERG_LATE/2025').glob('*202510*')],
         'scope':'Known root targeted October lookup plus authorized C-H filename discovery; skips/errors are not absence proof',
         'science_data_downloaded':False,'late_substitution':False,'research_period_changed':False}
    assert not gap['known_final_october_files']
    writej('GAPS/october_presence.json',gap)
    checks=[{'path':x['path'],'unchanged':fp(x['path'])==x} for x in old]
    assert all(x['unchanged'] for x in checks)
    writej('logs/probe_integrity.json',{'passed':True,'checked':len(checks),'checks':checks})
    print('PROBE_COMPLETE',len(selected),'native',len(conversions),'converted; old protected',len(old))

if __name__=='__main__': main()
