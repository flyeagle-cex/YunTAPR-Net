"""One explicitly approved f006 campaign: pilot then serial QC/statistics, no training."""
from pathlib import Path
from datetime import timedelta
from collections import Counter
import argparse,ctypes,hashlib,json,os,shutil,sys,time,traceback,warnings
ROOT=Path(__file__).resolve().parents[2];sys.dont_write_bytecode=True;sys.path.insert(0,str(ROOT/'src'))
os.environ['CUDA_VISIBLE_DEVICES']='';os.environ['OMP_NUM_THREADS']='1';os.environ['MKL_NUM_THREADS']='1'
import numpy as np
import torch,netCDF4
torch.set_num_threads(1)
from yuntapr.experimental.core_innovation.stage3.planning import digest,utc,training_budget,rainfall_summary
from yuntapr.experimental.core_innovation.stage3.statistics import SourceCache,satellite_statistics,environment_statistics,finalize_statistics,V13_KEYS
from yuntapr.experimental.core_innovation.stage3.metered_io import SourceMeter,IdentityConflict,path_key
from yuntapr.experimental.core_innovation.stage2.population import read_seven_band,joint_population
from yuntapr.experimental.core_innovation.multispectral import TrainNormalization
from yuntapr.experimental.core_innovation.gfs import ForecastIdentity,VariableRequest,read_gfs_file,combine_environment
from yuntapr.experimental.core_innovation.grid import frozen_sp04_grid,GridSpec
from yuntapr.spatial.sp04_mapping import load_sp04
from yuntapr.data.dataset_b1 import H_ROOT,FREEZE,SCALER_SHA,pinned

APPROVED_SHA='32b1802a0058627f67ba46d8dffe9c24619404149bd5837618fe0236383d4481'
MAX_FILES=15375;MAX_BYTES=52683603968


def write(path,value):
    with path.open('x',encoding='utf-8') as f:json.dump(value,f,ensure_ascii=False,indent=2,allow_nan=False)


def resources():
    class Memory(ctypes.Structure):
        _fields_=[('length',ctypes.c_ulong),('load',ctypes.c_ulong)]+[(s,ctypes.c_ulonglong) for s in ('total_phys','avail_phys','total_page','avail_page','total_virtual','avail_virtual','extended')]
    m=Memory();m.length=ctypes.sizeof(m)
    if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(m)):raise RuntimeError('Cannot measure host memory/commit')
    result=dict(available_physical_bytes=m.avail_phys,available_commit_bytes=m.avail_page,workspace_disk_free_bytes=shutil.disk_usage(ROOT).free)
    if min(m.avail_phys,m.avail_page)<2*1024**3 or result['workspace_disk_free_bytes']<1024**3:raise RuntimeError('Insufficient memory/commit/disk headroom')
    return result


def requests():
    main=tuple(VariableRequest(q+str(p),q,name,p*100.) for p in (850,700) for q,name in (('u','u-component_of_wind_isobaric'),('v','v-component_of_wind_isobaric')))+(
        VariableRequest('ps','surface_pressure','Pressure_surface'),VariableRequest('pwat','precipitable_water','Precipitable_water_entire_atmosphere_single_layer'),VariableRequest('cape','cape','Convective_available_potential_energy_surface'))
    thermo=tuple(VariableRequest(q+str(p),q,name,p*100.) for p in (850,700,500) for q,name in (('temperature','Temperature_isobaric'),('relative_humidity','Relative_humidity_isobaric')))
    return {'main':main,'thermo':thermo}


def main(args):
    out=args.output.resolve()
    if not out.is_relative_to(ROOT/'docs/core_stage3/.local') or out.exists():raise PermissionError('New isolated private run directory required; no automatic resumption')
    request_path=args.request.resolve();r=json.loads(request_path.read_text(encoding='utf-8'));body=dict(r);sha=body.pop('request_sha256')
    if sha!=APPROVED_SHA or digest(body)!=sha:raise IdentityConflict('Approved request identity mismatch')
    if (r['total_new_source_files'],r['budget_round_up_bytes'])!=(MAX_FILES,MAX_BYTES):raise IdentityConflict('Approved limits mismatch')
    prior=json.loads(args.stage2_evidence.read_text(encoding='utf-8'));schema=json.loads(args.schema.read_text(encoding='utf-8'))
    roots={}
    for rec in schema['records']:
        root=Path(rec['path']).parents[2];old=roots.setdefault(rec['kind'],root)
        if old!=root:raise IdentityConflict('Conflicting prior source roots')
    known={}
    for rec in prior['GFS_checks']:
        if rec.get('source_provenance'):
            for kind,prov in zip(('main','thermo'),rec['source_provenance'][:2]):known[(utc(rec['identity']['init']).isoformat(),int(rec['identity']['lead_hours']),kind)]=prov['input_sha256']
    reused={x['evidence']['nominal']:x['evidence'] for x in prior['seven_band_checks'] if x['status']=='PASS_ONE_FRAME_ONLY'}
    manifests={};jobs={};file_map={};sat_ids={};env_ids={};scene_rows={}
    for role,info in r['roles'].items():
        m=json.loads((request_path.parent/info['manifest']).read_text(encoding='utf-8'));check=dict(m);msha=check.pop('manifest_sha256')
        if msha!=info['manifest_sha256'] or digest(check)!=msha:raise IdentityConflict('Candidate manifest SHA mismatch')
        year=m['year'];manifests[role]=m;scene_rows[role]=m['scene_records']
        if year not in (2023,2024) or m['lead_policy']!='fixed_f006':raise IdentityConflict('Manifest scope mismatch')
        for f in m['satellite_files']:
            if not f['new_read_needed']:
                if role!='Development' or f['nominal'] not in reused or reused[f['nominal']]['source_sha256']!=f['expected_sha256']:raise IdentityConflict('Unproven inherited QC reuse')
                continue
            path=H_ROOT/f['relative_path'];key='sat:'+f['expected_sha256']+':'+f['nominal']
            if utc(f['nominal']).year!=year or year==2025:raise IdentityConflict('Forbidden source year')
            jobs[key]=dict(kind='satellite',year=year,bytes=f['expected_bytes'],files=1,expected_sha256=f['expected_sha256'],frame=f,paths=[str(path)])
            sat_ids[f['nominal']]=key
            if path_key(path) in file_map:raise IdentityConflict('Duplicate approved source file')
            file_map[path_key(path)]=dict(bytes=f['expected_bytes'],sha=f['expected_sha256'],job_id=key)
        by_identity={}
        for f in m['gfs_files']:
            if f['lead']!=6 or utc(f['init']).year not in (2023,2024):raise IdentityConflict('Wrong forecast vintage/year')
            by_identity.setdefault((f['init'],f['valid']),{})[f['kind']]=f
        for (init,valid),pair in by_identity.items():
            if set(pair)!=set(('main','thermo')) or utc(init)+timedelta(hours=6)!=utc(valid):raise IdentityConflict('Incomplete or inconsistent GFS pair')
            key='gfs:'+str(year)+':'+valid;paths=[str(roots[k]/pair[k]['relative_path']) for k in ('main','thermo')]
            jobs[key]=dict(kind='environment',year=year,bytes=sum(f['bytes'] for f in pair.values()),files=2,expected_sha256=None,init=init,valid=valid,paths=paths)
            env_ids[valid]=key
            for kind,path in zip(('main','thermo'),paths):
                if path_key(path) in file_map:raise IdentityConflict('Duplicate approved GFS file')
                file_map[path_key(path)]=dict(bytes=pair[kind]['bytes'],sha=known.get((utc(init).isoformat(),6,kind)),job_id=key)
        for row in scene_rows[role]:
            if utc(row['window_start']).year!=year or utc(row['analysis_time']).isoformat() not in env_ids:raise IdentityConflict('Target/input scope conflict')
    if len(file_map)!=MAX_FILES or sum(f['bytes'] for f in file_map.values())!=r['total_indexed_read_bytes']:raise IdentityConflict('Deduplication/count/byte totals mismatch')
    admission=resources()
    lock=request_path.parent/(sha+'_execution_lock.json')
    write(lock,dict(request_sha=sha,output=str(out),policy='ONE_CAMPAIGN_ONLY_NO_AUTOMATIC_RETRY_OR_RESET'))
    out.mkdir(parents=True)
    grant=dict(authorized=True,decision_id='RESEARCHER_STAGE3_CONDITIONAL_F006_20261024',request_sha=sha,manifest_sha=digest(jobs),max_bytes=MAX_BYTES,max_files=MAX_FILES)
    write(out/'authorization.json',dict(grant=grant,request_file_sha256=hashlib.sha256(request_path.read_bytes()).hexdigest(),candidate_manifests={k:v['manifest_sha256'] for k,v in manifests.items()},admission=admission,scope='QC_AND_CANDIDATE_STATISTICS_ONLY_NO_TRAINING'))
    cache=SourceCache(out/'statistics.sqlite',manifest=jobs,manifest_sha=digest(jobs),grant=grant,processor_id=digest(dict(driver=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),keys=V13_KEYS,request=sha)))
    meter=SourceMeter(cache.db,file_map,max_files=MAX_FILES,max_bytes=MAX_BYTES);meter.install()
    dataset_original=netCDF4.Dataset
    def memory_dataset(path,*a,**kw):
        if kw.get('memory') is None:raise PermissionError('Direct NetCDF filesystem access prohibited')
        return dataset_original(path,*a,**kw)
    netCDF4.Dataset=memory_dataset
    mapping=load_sp04();target=frozen_sp04_grid();req=requests();native_id=GridSpec(mapping.axes['native_lat'],mapping.axes['native_lon']).identity
    warnings.filterwarnings('once',message='Setting the shape on a NumPy array has been deprecated.*',category=DeprecationWarning)
    def loader(key):
        j=jobs[key];meter.active={path_key(p) for p in j['paths']};errors=[];payload={};decoded={}
        try:
            if j['kind']=='satellite':
                f=j['frame']
                try:
                    x,mask,receipt=read_seven_band(j['paths'][0],nominal=f['nominal'],mapping=mapping)
                    if receipt['source_sha256']!=f['expected_sha256'] or receipt['native_grid_id']!=native_id or receipt['obs_start']!=f['obs_start'] or receipt['obs_end']!=f['obs_end']:raise IdentityConflict('Satellite source/CF/grid identity conflict')
                    payload=satellite_statistics(x,mask,year=j['year'],receipt=receipt);del x,mask
                except ValueError as exc:errors.append(str(exc))
            else:
                identity=ForecastIdentity(utc(j['init']),timedelta(hours=6),utc(j['valid']))
                for kind,path in zip(('main','thermo'),j['paths']):
                    try:decoded[kind]=read_gfs_file(path,identity,req[kind])
                    except ValueError as exc:
                        if any(t in str(exc).lower() for t in ('identity','forecast time','lead conflict')):raise IdentityConflict(str(exc))
                        errors.append(kind+': '+str(exc))
                if not errors:
                    frame=combine_environment(decoded['main'],decoded['thermo'],target_valid_time=identity.valid,decision_time=identity.valid,mode='retrospective')
                    mapped=frame.on_grid(target,operator='bilinear_point_candidate');v,mask=mapped.stack(V13_KEYS)
                    if not np.isfinite(v[mask]).all() or not np.isnan(v[~mask]).all():raise ValueError('Environment finite/missing mask inconsistency')
                    base=dict(forecast_identity=dict(init=j['init'],valid=j['valid'],lead_hours=6),grid_id=target.identity,keys=V13_KEYS,
                        valid_counts={k:int(f.valid.sum()) for k,f in mapped.fields.items()},source_provenance=frame.provenance,
                        all_variables_have_valid_support=bool(mask.reshape(13,-1).any(1).all()),above_ground_mask_verified=True,unit_check_passed=True)
                    if j['year']==2023:payload=environment_statistics(frame,keys=V13_KEYS,target_grid=target)
                    payload.update(base);del frame,mapped,v,mask,decoded
            receipts=[meter.receipt(p) for p in j['paths']]
            payload.update(year=j['year'],source_sha256=receipts[0]['sha256'] if j['kind']=='satellite' else digest([v['sha256'] for v in receipts]),
                raw_bytes_read=sum(v['bytes'] for v in receipts),file_receipts=receipts,QC_status='PASS' if not errors else 'QC_REJECTED',QC_errors=errors)
            if j['kind']=='satellite' and payload.get('all_seven_valid') is False:payload['QC_status']='QC_REJECTED';payload['QC_errors'].append('SOME_REQUIRED_BAND_PIXELS_INVALID')
            return payload
        finally:meter.active=set()
    # Exact previously checked f006 May-1 06Z pairs + their six-slot scenes.
    pilot=[]
    for role,m in manifests.items():
        row=next(row for row in m['scene_records'] if utc(row['analysis_time']).strftime('%m%d%H%M')=='05010600')
        for i in range(6):
            nominal=row[f'slot_{i}_nominal']
            if nominal in sat_ids:pilot.append(sat_ids[nominal])
        pilot.append(env_ids[utc(row['analysis_time']).isoformat()])
    pilot=list(dict.fromkeys(pilot))
    if sum(jobs[k]['files'] for k in pilot)>32 or sum(jobs[k]['bytes'] for k in pilot)>256*1024**2:raise IdentityConflict('Pilot exceeds sub-cap')
    for k in pilot:cache.read_once(k,lambda k=k:loader(k))
    pilot_before=meter.totals()
    for k in pilot:
        if cache[k]['QC_status']!='PASS':raise RuntimeError('Pilot QC failed; full campaign not launched')
        cache.read_once(k,lambda:(_ for _ in ()).throw(RuntimeError('Completed source decoded twice')))
    if meter.totals()!=pilot_before:raise AssertionError('Cache reuse changed raw counters')
    write(out/'pilot_receipt.json',dict(status='PASS',files=pilot_before['opened_files'],bytes=pilot_before['delivered_bytes'],cache_reuse_no_reads=True,
        all_prior_hashes_matched=all(f.get('sha') is not None for p,f in file_map.items() if f['job_id'] in pilot),metadata_masks_checked=True,resources=resources()))
    print(json.dumps(dict(event='PILOT_PASS',**pilot_before)),flush=True)
    started=time.perf_counter();done=0
    for key in jobs:
        cache.read_once(key,lambda key=key:loader(key));done+=1
        if done%100==0:
            snapshot=resources();print(json.dumps(dict(event='PROGRESS',jobs_complete=done,total_jobs=len(jobs),**meter.totals(),elapsed_seconds=time.perf_counter()-started)),flush=True)
    totals=meter.totals()
    if totals['opened_files']!=MAX_FILES or totals['delivered_bytes']!=r['total_indexed_read_bytes'] or totals['states']!={'READ_COMPLETE':MAX_FILES}:raise IdentityConflict('Final raw counters do not match approved source plan')
    all_frames=dict(reused)
    for nominal,key in sat_ids.items():
        p=cache[key]
        if p['QC_status']=='PASS':all_frames[nominal]=p['frame_receipt']
    populations={};train_stats_rows=[];accepted_records={}
    for role,rows in scene_rows.items():
        spectral=joint_population(rows,all_frames,native_grid_id=native_id);accepted=[];excluded=dict(spectral['rejected'])
        for row in rows:
            sid=row['sample_id'];key=env_ids[utc(row['analysis_time']).isoformat()];e=cache[key]
            if sid in spectral['accepted_ids'] and e['QC_status']=='PASS' and e.get('all_variables_have_valid_support'):
                accepted.append(sid)
                if role=='Train':train_stats_rows.append(dict(sample_id=sid,frame_ids=[sat_ids[row[f'slot_{i}_nominal']] for i in range(6)],environment_id=key))
            else:
                if e['QC_status']!='PASS':excluded.setdefault(sid,[]).extend(e['QC_errors'])
                elif not e.get('all_variables_have_valid_support'):excluded.setdefault(sid,[]).append('ONE_OR_MORE_GFS_VARIABLES_HAVE_NO_VALID_TARGET_SUPPORT')
        accepted_records[role]=[row for row in rows if row['sample_id'] in set(accepted)]
        populations[role]=dict(accepted_ids=accepted,excluded=excluded,population_sha256=digest(sorted(accepted)),candidate_scenes=len(rows),accepted_scenes=len(accepted),status='ACTUAL_QC_COMMON_POPULATION_CANDIDATE_NOT_SCIENTIFIC_FREEZE')
    joint_sha=digest(dict(Train=sorted(populations['Train']['accepted_ids']),Development=sorted(populations['Development']['accepted_ids'])))
    write(out/'populations.json',dict(populations=populations,joint_population_sha256=joint_sha))
    scaler=json.loads(pinned(ROOT/FREEZE/'normalization_b1_2023_shared_v1.json',SCALER_SHA).read_text(encoding='utf-8'))
    b13=TrainNormalization.from_b1_artifact(scaler,artifact_sha256=SCALER_SHA)
    fitted=finalize_statistics(train_stats_rows,cache,final_train_ids=populations['Train']['accepted_ids'],final_dev_ids=populations['Development']['accepted_ids'],
        final_population_sha=joint_sha,source_manifest_sha=digest(jobs),frozen_b13=b13,environment_keys=V13_KEYS,forecast_lead_hours=6)
    write(out/'train_statistics.json',fitted)
    target_csv=ROOT/'docs/b0_pretraining_closure/runs/run_20260930T095416Z/formal_sample_eligibility_2023_2024.csv'
    import csv
    with target_csv.open(encoding='utf-8-sig',newline='') as f:labels={row['window_start']:row for row in csv.DictReader(f)}
    distributions={role:rainfall_summary([dict(record=row) for row in rows],labels) for role,rows in accepted_records.items()}
    budget=training_budget(final_train_ids=populations['Train']['accepted_ids'],final_dev_ids=populations['Development']['accepted_ids'],final_population_sha=joint_sha)
    result=dict(status='COMPLETED_QC_AND_CANDIDATE_STATISTICS_STOP_BEFORE_TRAINING',actual_reads=totals,request_sha256=sha,joint_population_sha256=joint_sha,
        populations={k:v['accepted_scenes'] for k,v in populations.items()},distributions=distributions,PWAT_reference_kg_m2=fitted['positive_PWAT_reference_kg_m2'],
        statistics_complete=True,environment_variables=V13_KEYS,T500_RH500_QC='PASS_IN_APPROVED_F006_POPULATION_MODEL_ADAPTER_STILL_PENDING',training_budget=budget,
        source_hash_limitation='Satellite hashes and available prior GFS hashes matched. Other GFS hashes established on first authorized read; prior file-level hashes absent from original inventory.',
        baseline_descriptive_high_intensity={role:r['roles'][role]['rainfall_evidence']['scenes_max_ge_20_mm_h']+r['roles'][role]['loss_from_inherited_B1']['scenes_max_ge_20_mm_h'] for role in manifests},formal_training_launched=False,optimizer_updates=0,raw_2025_reads=0,
        operational_release_established=False,final_resources=resources())
    write(out/'completion.json',result);print(json.dumps(dict(event='COMPLETED',populations=result['populations'],actual_reads=totals,PWAT_reference_kg_m2=result['PWAT_reference_kg_m2'],budget=budget)),flush=True)
    cache.close()


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--request',type=Path,required=True);p.add_argument('--stage2-evidence',type=Path,required=True);p.add_argument('--schema',type=Path,required=True);p.add_argument('--output',type=Path,required=True);args=p.parse_args()
    try:main(args)
    except BaseException as exc:
        if args.output.exists():
            file=args.output/'failure.json'
            if not file.exists():write(file,dict(status='STOPPED_NO_AUTOMATIC_RETRY',error=type(exc).__name__+': '+str(exc),traceback=traceback.format_exc()))
        traceback.print_exc();raise SystemExit(1)
