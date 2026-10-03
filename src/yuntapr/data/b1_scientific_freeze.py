"""Researcher-approved B1 sample identities and exposure-weighted B13 scaler.

No model/training/IMERG reader exists here. Published B0 artifacts are immutable.
"""
from collections import Counter
from datetime import timedelta
import csv,json,math,os
from pathlib import Path,PureWindowsPath
import subprocess,time
import netCDF4
import numpy as np
from yuntapr.contracts.loader import REPO_ROOT,sha256
from yuntapr.data import b1_temporal_audit as audit
from yuntapr.data.himawari_b13 import decode_b13,_cf_time
from yuntapr.evaluation.catalogue_backend_b0 import CatalogueEnglishStaging
from yuntapr.spatial.sp04_mapping import load_sp04

BASE='1fd70ba9a563aa673012fa1b1494b86d72511eb6'
PRIOR='docs/b1_temporal_audit/runs/run_20261003T035724_142784Z'
FRAME_INDEX_SHA='a5054200d6bde11f2342c292ca72428d0558d5b5c5c640017844f0b4ed8c540e'
COUNTS={2023:10455,2024:10501}
DESIGN='config/b1/b1_scientific_design_freeze_v1.json'
PROTOCOL='config/training/b1_matched_control_protocol_decisions_v1.json'
LEDGER='docs/phase_b_finalfit_preparation/runs/run_20261002T014649_144967Z/phase_b_finalfit_manifest.csv'
LEDGER_SHA='00e6bd018eae6aeb05be0740b55a92b7a5cc9a44b9ab2b80affbad3e3282ccff'
CODE=('src/yuntapr/data/b1_scientific_freeze.py','scripts/freeze_b1_science_v1.py')

def read(path):return json.loads(Path(path).read_text(encoding='utf-8'))
def save(path,value):
    with Path(path).open('x',encoding='utf-8',newline='\n') as f:
        json.dump(value,f,ensure_ascii=False,indent=2,allow_nan=False);f.write('\n')
def rows(path):
    with Path(path).open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))
def table(path,values,fields=None):
    with Path(path).open('x',encoding='utf-8',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=fields or list(values[0]),lineterminator='\n')
        writer.writeheader();writer.writerows(values)
def pin(path):return {'path':Path(path).relative_to(REPO_ROOT).as_posix(),'sha256':sha256(Path(path))}
def verify_history(run):return audit.verify_history(read(run/'history_before.json'))
def verify_refs(refs):
    for ref in refs:
        if sha256(REPO_ROOT/ref['path'])!=ref['sha256']:raise ValueError('PINNED_ARTIFACT_CHANGED:'+ref['path'])

def strict_scene_frames(t,frames):
    """M1 rejects whole scene; expected scan bucket is diagnostic only."""
    times=audit.slot_nominals(t);analysis=audit.utc(t)+timedelta(minutes=30);out=[]
    for nominal in times:
        if not audit.in_scope(nominal):raise ValueError('OUTSIDE_RESEARCH_WINDOW_NO_FEBRUARY_FILL')
        f=frames[nominal.isoformat()]
        if (f['status']!='FULL_VALID' or f['reasons'] or int(f['valid_count'])!=251001 or
                any(f[k]!='True' for k in ('present','readable','decoded','full_valid','metadata_valid'))):
            raise ValueError('M1_INCOMPLETE_OR_INVALID_FRAME')
        if not audit.utc(f['obs_start'])<=audit.utc(f['obs_end'])<=analysis:
            raise ValueError('NONCAUSAL_FRAME')
        if not f['relative_path'] or len(f['source_sha256'])!=64 or int(f['source_bytes'])<=0:
            raise ValueError('MISSING_FRAME_IDENTITY')
        out.append(f)
    return out

def exposure_plan(scenes,frames):
    counts=Counter();minimum={}
    for row in scenes:
        if audit.utc(row['window_start']).year!=2023:raise ValueError('TRAIN_2023_ONLY')
        for f in strict_scene_frames(row['window_start'],frames):
            n=f['nominal'];counts[n]+=1;minimum[n]=min(minimum.get(n,row['analysis_time']),row['analysis_time'])
    return [{**{k:frames[n][k] for k in ('nominal','relative_path','source_bytes','source_sha256','obs_start','obs_end','date_created')},
             'scene_slot_exposures':counts[n],'minimum_analysis_time':minimum[n]} for n in sorted(counts)]

def prepare(run):
    run=Path(run);verify_history(run)
    if subprocess.check_output(['git','rev-parse','HEAD'],cwd=REPO_ROOT,text=True).strip()!=BASE:raise ValueError('WRONG_BASELINE')
    previous=REPO_ROOT/PRIOR;status=read(previous/'final_status.json')
    if not status['B1_TEMPORAL_AUDIT_EXECUTED'] or status['closure_status']!='PASS_INDEPENDENT_ARTIFACT_TESTS_COMPLETE':
        raise ValueError('REAL_AUDIT_CLOSURE_REQUIRED')
    if sha256(previous/'frame_identity_index.json')!=FRAME_INDEX_SHA:raise ValueError('FRAME_INDEX_CHANGED')
    refs=[pin(run/'researcher_decisions.json'),pin(previous/'final_status.json'),pin(previous/'frame_identity_index.json')]
    index=read(previous/'frame_identity_index.json');frames={}
    for relative,digest in index['files'].items():
        ref={'path':PRIOR+'/'+relative,'sha256':digest};verify_refs([ref]);refs.append(ref)
        for frame in rows(REPO_ROOT/ref['path']):
            if frame['nominal'] in frames:raise ValueError('DUPLICATE_FRAME_NOMINAL')
            frames[frame['nominal']]=frame
    for group in ('six_slot_csv_sha256','population_csv_sha256'):
        for relative,digest in status[group].items():
            ref={'path':PRIOR+'/'+relative,'sha256':digest};verify_refs([ref]);refs.append(ref)
    targets,original,target_refs=audit.load_targets();refs.extend(target_refs.values())
    target_by_time={r['window_start']:r for r in targets}
    verify_refs([{'path':LEDGER,'sha256':LEDGER_SHA}]);refs.append({'path':LEDGER,'sha256':LEDGER_SHA})
    ledger={r['window_start']:r for r in rows(REPO_ROOT/LEDGER)}
    counts={};manifests={};formal_train=[];summary={}
    for year in COUNTS:
        candidates=rows(previous/f'b1_candidate_eligible_{year}.csv')
        intersection=rows(previous/f'intersection_candidate_{year}.csv')
        keys=[r['window_start'] for r in candidates]
        if len(keys)!=COUNTS[year] or len(set(keys))!=len(keys) or keys!=sorted(keys):raise ValueError('SCENE_COUNT_ORDER_CHANGED')
        if keys!=[r['window_start'] for r in intersection] or not set(keys)<=original[year]:raise ValueError('COMMON_INTERSECTION_CHANGED')
        # Independently recompute M1 on all calendar targets using pinned QC, not just candidate row counts.
        recomputed=[]
        for t in audit.times(year,30):
            target=target_by_time[t.isoformat()]
            if int(target['imerg_valid_yunnan_count'])!=3430:raise ValueError('PINNED_TARGET_VALIDITY_CHANGED')
            try:strict_scene_frames(t,frames)
            except (ValueError,KeyError):continue
            recomputed.append(t.isoformat())
        if recomputed!=keys:raise ValueError('M1_RECOMPUTATION_DISAGREES')
        b1=[];control=[]
        for i,row in enumerate(candidates):
            t=audit.utc(row['window_start']);a=t+timedelta(minutes=30)
            if t.year!=year or row['sample_id']!=t.isoformat() or audit.utc(row['analysis_time'])!=a:raise ValueError('SCENE_TIME_ROLE_CHANGED')
            fs=strict_scene_frames(t,frames);identity=ledger[t.isoformat()];target=target_by_time[t.isoformat()]
            if (identity['b13_relative_path']!=fs[-1]['relative_path'] or identity['b13_sha256']!=fs[-1]['source_sha256']
                or int(identity['b13_bytes'])!=int(fs[-1]['source_bytes']) or identity['imerg_day_path']!=row['imerg_day_path']
                or identity['imerg_index']!=row['imerg_index'] or target['selected_nominal']!=fs[-1]['nominal']):
                raise ValueError('B0_LATEST_OR_TARGET_IDENTITY_CHANGED')
            common={'index':i,'sample_id':t.isoformat(),'original_b0_sample_id':identity['sample_id'],
                'role':'Train' if year==2023 else 'Validation','year':year,'window_start':t.isoformat(),'analysis_time':a.isoformat(),
                'imerg_day_path':row['imerg_day_path'],'imerg_index':int(row['imerg_index']),
                'imerg_sha256':identity['imerg_sha256'],'target_valid_yunnan_cells':3430,
                'frame_identity_index_sha256':FRAME_INDEX_SHA,'eligibility':'FORMAL_M1_COMMON_INTERSECTION'}
            b1.append({**common,**{f'slot_{s}_nominal':f['nominal'] for s,f in enumerate(fs)}})
            control.append({**common,'selected_slot':5,'expected_nominal':fs[-1]['nominal'],
                'b13_relative_path':fs[-1]['relative_path'],'b13_bytes':int(fs[-1]['source_bytes']),
                'b13_sha256':fs[-1]['source_sha256'],'obs_start':fs[-1]['obs_start'],
                'obs_end':fs[-1]['obs_end'],'date_created':fs[-1]['date_created']})
        for label,values in (('b1',b1),('b0_matched_control',control)):
            p=run/f'{label}_{year}_formal_manifest.csv';table(p,values);manifests[p.name]=pin(p)
        if year==2023:formal_train=b1
        counts[str(year)]=len(b1)
        summary[str(year)]={'role':'Train' if year==2023 else 'Validation','calendar_targets':11760,
            'historical_b0_eligible':len(original[year]),'b1_formal_eligible':len(b1),
            'common_intersection':len(b1),'independent_b0_matched_control':len(control),
            'calendar_rejected':11760-len(b1),'historical_b0_not_in_intersection':len(original[year])-len(b1)}
    exposures=exposure_plan(formal_train,frames);table(run/'normalization_train_exposure_plan.csv',exposures)
    weighted=sum(int(r['scene_slot_exposures']) for r in exposures)
    if weighted!=10455*6:raise ValueError('WRONG_EXPOSURE_TOTAL')
    norm={'status':'FIT_RULE_FROZEN_VALUES_PENDING_REAL_2023_FIT','shared_across_all_six_slots':True,
        'fit_role':'Train','fit_years':[2023],'fit_months':list(range(3,11)),'fit_scene_count':10455,
        'weighting':'SCENE_SLOT_EXPOSURE_EACH_NATIVE_PIXEL','scene_slot_exposures':weighted,
        'weighted_native_pixel_count':weighted*251001,'unique_frames_to_read':len(exposures),'ddof':0,
        'ddof_provenance':'Inherited population-variance definition of pinned B0 Phase-A normalizer; not a new fitted parameter',
        'decode_semantics':'Inherited float32 packed B13 reader; moments in float64; transform float64 then cast float32',
        'no_validation_or_2025_fitting':True,'no_imerg_value_reads':True,
        'b0_matched_control_normalization':'RESEARCHER_DECISION_REQUIRED_NO_SILENT_REUSE'}
    design={'version':'v1','authority':'EXPLICIT_RESEARCHER_APPROVAL','baseline':BASE,
        'researcher_decisions':pin(run/'researcher_decisions.json'),'slot_definition':pin(REPO_ROOT/audit.SLOT_PATH),
        'missing_policy':'M1_STRICT_SIX_SLOT_FULL_VALID_CAUSAL','window_start_history':'REJECT_NO_FEBRUARY_READ',
        'substitution_prohibited':['older fallback','nearest','duplicate','zero','interpolation'],
        'input':{'shape':'[B,6,501,501]','channels':['B13'],'ordering':'OLDEST_TO_LATEST',
                 'nominal_offsets_before_analysis_minutes':[60,50,40,30,20,10],'native_lat':'descending','native_lon':'ascending',
                 'no_flip_transpose_or_coordinate_reconstruction':True},
        'backbone':{'inherit':'B0 residual U-Net four levels 48/96/192/256 + decoder + SP04 + frozen heads/loss family',
                    'only_frontend_input_channels_change':True,'parameter_count_verified':4331761,
                    'historical_b0_parameter_count':4329361,'parameter_delta':2400,
                    'parameter_evidence':pin(REPO_ROOT/'docs/b1_scientific_design/candidates/run_20261003T024550_523841Z/candidate_parameter_inventory.json')},
        'normalization':norm,'primary_comparison':'COMMON_INTERSECTION_WITH_INDEPENDENT_B0_MATCHED_CONTROL',
        'formal_scene_counts':counts,'historical_b0_immutable':True,'2025_outcomes_sealed':True,
        'additional_sources_or_temporal_modules_authorized':False,'B1_TRAINING_AUTHORIZED':False,
        'B0_MATCHED_CONTROL_TRAINING_AUTHORIZED':False,'created_utc':audit.old_gate.now()}
    save(REPO_ROOT/DESIGN,design)
    pending=['optimizer','optimizer_groups','base_lr','lr_schedule','physical_batch','accumulation','drop_last',
        'steps_per_epoch','warmup_updates','cosine_horizon_updates','epoch_budget','early_stopping',
        'checkpoint_selection','initialization_seed','initialization_checkpoint_policy','resume_policy',
        'AMP_mode','loader_workers','gradient_clipping','focal_alpha_gamma','b0_matched_control_normalization']
    protocol={'version':'v1','status':'APPROVED_ITEMS_ONLY_OTHER_PARAMETERS_PENDING','researcher_clarification':
        '只冻结已批准项，其余参数待研究者决定（推荐）','design':pin(REPO_ROOT/DESIGN),
        'approved_items':{'b1_input':'B13 SIX CAUSAL SLOTS','b0_matched_control_input':'B13 LATEST SLOT 5',
            'Train_scenes':10455,'Validation_scenes':10501,'eligibility':'M1_COMMON_INTERSECTION',
            'b1_normalization':'2023_B1_TRAIN_SCENE_SLOT_EXPOSURE_SHARED',
            'historical_b0_immutable':True,'2025_outcomes_sealed':True},
        'RESEARCHER_DECISION_REQUIRED':{key:'NOT_YET_FROZEN' for key in pending},
        'inherited_science_contract':pin(REPO_ROOT/'config/science_contract_v1.1.yaml'),
        'b0_phase_a_protocol_reference_only':pin(REPO_ROOT/'config/training/phase_a_training_protocol_v1.yaml'),
        'automatic_phase_a_protocol_inheritance_approved':False,'TRAINING_PROTOCOL_FULLY_FROZEN':False,
        'B1_TRAINING_AUTHORIZED':False,'B0_MATCHED_CONTROL_TRAINING_AUTHORIZED':False,
        'formal_train_entrypoint_provided':False,'created_utc':audit.old_gate.now()}
    save(REPO_ROOT/PROTOCOL,protocol)
    save(run/'sample_set_freeze.json',{'status':'FROZEN','counts':summary,'manifests':manifests,
        'normalization_exposure_plan':pin(run/'normalization_train_exposure_plan.csv'),
        'scene_slot_exposures':weighted,'weighted_pixel_count':weighted*251001,'unique_train_frames':len(exposures),
        'source_evidence_refs':refs,'normalization_rule':norm,'design':pin(REPO_ROOT/DESIGN),
        'training_protocol':pin(REPO_ROOT/PROTOCOL),'historical_files_preserved':verify_history(run),
        'raw_source_opens_in_metadata_formalization':0,'2025_PIXELS_READ':0})
    return {'status':'PASS_M1_RECOMPUTED_AND_SETS_FROZEN','counts':counts,'unique_train_frames':len(exposures),
            'scene_slot_exposures':weighted,'weighted_pixel_count':weighted*251001}

class NormalizationGuard(audit.AuditGuard):
    """Only allow whitelisted formal 2023 Train B13 sources, before any open."""
    def __init__(self,exposures):
        super().__init__();self.allowed={audit.HROOT/PureWindowsPath(r['relative_path']) for r in exposures}
        if not self.allowed or any(p.relative_to(audit.HROOT).parts[0][:4]!='2023' for p in self.allowed):
            raise ValueError('2023_TRAIN_WHITELIST_REQUIRED')
    def check(self,path,mode='r',flags=0,*,directory=False):
        if isinstance(path,(str,bytes,os.PathLike)):
            p=PureWindowsPath(os.fsdecode(path))
            if p.is_relative_to(audit.HROOT) and (directory or p not in self.allowed):
                self.prohibited_attempts+=1;raise PermissionError('NOT_AN_APPROVED_2023_TRAIN_EXPOSURE_SOURCE')
        return super().check(path,mode,flags,directory=directory)

def accumulate_packed(histogram,packed,multiplicity):
    if (packed.dtype!=np.int16 or not isinstance(multiplicity,int) or isinstance(multiplicity,bool) or multiplicity<1
        or histogram.shape!=(65536,) or histogram.dtype!=np.int64):raise ValueError('EXACT_INT16_POSITIVE_EXPOSURE_REQUIRED')
    histogram+=np.bincount(packed.astype(np.int32).ravel()+32768,minlength=65536)*multiplicity

def histogram_summary(hist):
    if hist.shape!=(65536,) or hist.dtype!=np.int64 or np.any(hist<0) or not np.any(hist):raise ValueError('VALID_HISTOGRAM_REQUIRED')
    # Identical float32 multiply/add semantics to decode_b13, without refitting packing constants.
    support=(np.arange(-32768,32768,dtype=np.float32)*np.float32(.01)+np.float32(273.15)).astype(np.float64)
    count=int(hist.sum());weights=hist.astype(np.float64);mean=float(np.dot(weights,support)/count)
    variance=float(np.dot(weights,(support-mean)**2)/count)
    if not math.isfinite(mean) or not math.isfinite(variance) or variance<=0:raise ValueError('DEGENERATE_SCALER')
    return {'mean_K':mean,'std_K':math.sqrt(variance),'ddof':0,'valid_pixel_count':count}

def read_packed_frame(local,mapping,identity,telemetry):
    with netCDF4.Dataset(str(local),'r') as ds:
        ds.set_auto_maskandscale(False);var=ds['tbb_13']
        if var.shape!=(501,501) or var.dimensions!=('latitude','longitude') or var.units!='K':raise ValueError('NATIVE_B13_GRID_CHANGED')
        mapping.assert_axes(np.asarray(ds['latitude'][:]),np.asarray(ds['longitude'][:]),mapping.axes['target_lat'],mapping.axes['target_lon'])
        attrs={k:var.getncattr(k) for k in ('scale_factor','add_offset','valid_min','valid_max','_FillValue','missing_value') if k in var.ncattrs()}
        if np.float32(attrs['scale_factor'])!=np.float32(.01) or np.float32(attrs['add_offset'])!=np.float32(273.15):
            raise ValueError('FROZEN_B13_PACKING_CHANGED')
        start,end=_cf_time(ds,'start_time'),_cf_time(ds,'end_time');created=str(ds.getncattr('date_created'))
        if (start!=audit.utc(identity['obs_start']) or end!=audit.utc(identity['obs_end']) or created!=identity['date_created']
                or not start<=end<=audit.utc(identity['minimum_analysis_time'])):raise ValueError('FROZEN_TIME_OR_CAUSALITY_CHANGED')
        raw=np.asarray(var[:]);telemetry['b13_pixel_values_read']+=int(raw.size)
        decoded,valid=decode_b13(raw,attrs)
        if raw.dtype!=np.int16 or int(valid.sum())!=251001 or not np.isfinite(decoded).all():raise ValueError('M1_REAL_FRAME_NO_LONGER_FULL_VALID')
        return raw

def fit(run,staging_root):
    run=Path(run);verify_history(run);freeze=read(run/'sample_set_freeze.json')
    verify_refs(freeze['source_evidence_refs']+list(freeze['manifests'].values())+
        [freeze['normalization_exposure_plan'],freeze['design'],freeze['training_protocol']])
    plan=rows(run/'normalization_train_exposure_plan.csv')
    if (len(plan)!=freeze['unique_train_frames'] or sum(int(r['scene_slot_exposures']) for r in plan)!=62730
        or any(audit.utc(r['nominal']).year!=2023 or not audit.in_scope(r['nominal']) for r in plan)):
        raise ValueError('FROZEN_TRAIN_EXPOSURE_PLAN_CHANGED')
    stagepath=Path(staging_root);expected=Path(str(audit.STAGING_PARENT/('b1_normalization_'+run.name)))
    if stagepath!=expected or stagepath.resolve()!=stagepath or stagepath.exists():raise PermissionError('NEW_EXACT_OWNED_STAGING_CHILD_REQUIRED')
    if (run/'normalization_start.json').exists():raise PermissionError('NO_RUN_OVERWRITE_OR_PARTIAL_RESUME')
    began=time.perf_counter();telemetry={'raw_source_open_events':0,'source_hash_bytes_read':0,
        'source_copy_bytes_read':0,'source_copy_bytes_written':0,'b13_pixel_values_read':0,
        'copy_seconds':0.0,'read_seconds':0.0,'temporary_bytes_peak':0,'cleanup_success':True}
    save(run/'normalization_start.json',{'created_utc':audit.old_gate.now(),'scope':'APPROVED_2023_TRAIN_B13_FIT_ONLY',
        'code_sha256':{n:sha256(REPO_ROOT/n) for n in CODE},'staging_root':str(stagepath),
        'exposure_plan':freeze['normalization_exposure_plan'],'normalization_rule':freeze['normalization_rule']})
    guard=NormalizationGuard(plan);hist=np.zeros(65536,dtype=np.int64);stage=None;completed=0
    try:
        with guard:
            mapping=load_sp04();stage=CatalogueEnglishStaging(stagepath,telemetry)
            output=run/'normalization_frame_read_log.csv'
            with output.open('x',encoding='utf-8',newline='') as stream:
                fields=['nominal','source_sha256','source_bytes','scene_slot_exposures','copy_seconds','read_seconds','temporary_bytes','cleanup_success']
                writer=csv.DictWriter(stream,fieldnames=fields,lineterminator='\n');writer.writeheader()
                for i,identity in enumerate(plan,1):
                    source=Path(str(audit.HROOT/PureWindowsPath(identity['relative_path'])))
                    if source.resolve(strict=True)!=source or source.stat().st_size!=int(identity['source_bytes']):raise OSError('RAW_IDENTITY_PATH_OR_SIZE_CHANGED')
                    with stage.local(source) as local:
                        if stage._owned!={local.resolve()}:raise OSError('CACHE_NOT_ONE_FILE_BOUNDED')
                        # SHA verified by staging before any netCDF payload read; frozen identity checked before decode.
                        # Catalogue staging record is committed at exit, so hash local now against the pinned identity.
                        if sha256(local)!=identity['source_sha256']:raise OSError('FROZEN_FRAME_SHA_CHANGED_BEFORE_DECODE')
                        packed=read_packed_frame(local,mapping,identity,telemetry)
                        accumulate_packed(hist,packed,int(identity['scene_slot_exposures']));del packed
                    rec=stage.records[-1]
                    if (rec.source_sha256!=identity['source_sha256'] or not rec.sha256_match or not rec.size_match
                        or not rec.cleanup_success or stage._owned):raise OSError('FROZEN_SOURCE_OR_STAGING_CLEANUP_FAILURE')
                    telemetry['copy_seconds']+=rec.copy_seconds;telemetry['read_seconds']+=rec.read_seconds
                    telemetry['temporary_bytes_peak']=max(telemetry['temporary_bytes_peak'],rec.temporary_bytes)
                    telemetry['cleanup_success'] &= rec.cleanup_success
                    writer.writerow({'nominal':identity['nominal'],'source_sha256':rec.source_sha256,'source_bytes':rec.temporary_bytes,
                        'scene_slot_exposures':int(identity['scene_slot_exposures']),'copy_seconds':rec.copy_seconds,
                        'read_seconds':rec.read_seconds,'temporary_bytes':rec.temporary_bytes,'cleanup_success':rec.cleanup_success})
                    stage.records.clear();completed=i
                    if i==1 or i%500==0 or i==len(plan):
                        stream.flush();print(json.dumps({'frames':i,'total':len(plan),'weighted_pixels':int(hist.sum()),
                            'elapsed_seconds':time.perf_counter()-began,'2025_PIXELS_READ':0}),flush=True)
            if guard.source_open_events!=telemetry['raw_source_open_events'] or guard.prohibited_attempts:raise ValueError('SOURCE_GUARD_COUNTER_MISMATCH')
            if list(stage.root.iterdir()) or stage._owned:raise OSError('OWNED_STAGING_NOT_EMPTY')
        stats=histogram_summary(hist)
        if stats['valid_pixel_count']!=10455*6*251001 or telemetry['b13_pixel_values_read']!=len(plan)*251001:raise ValueError('EXPOSURE_OR_ACTUAL_READ_DENOMINATOR_CHANGED')
        table(run/'normalization_scene_slot_packed_histogram.csv',({'packed_int16_code':j-32768,'weighted_count':int(n)} for j,n in enumerate(hist)),['packed_int16_code','weighted_count'])
        value={'normalization_version':'B1_2023_M1_COMMON_INTERSECTION_SCENE_SLOT_SHARED_v1','status':'TRAIN_ONLY_FITTED_FROZEN',
            'ready':True,**stats,'fit_years':[2023],'fit_months':list(range(3,11)),'fit_role':'Train','fit_scene_count':10455,
            'scene_slot_exposures':62730,'weighting':'SCENE_SLOT_EXPOSURE_EACH_NATIVE_PIXEL','unique_frames_read':completed,
            'all_six_slots_share_identical_scaler':True,'packing_scale_float32':float(np.float32(.01)),
            'packing_offset_float32':float(np.float32(273.15)),
            'transform':'((Kelvin_float32.astype(float64)-mean_K)/std_K).astype(float32)',
            'training_manifest':freeze['manifests']['b1_2023_formal_manifest.csv'],'exposure_plan':freeze['normalization_exposure_plan'],
            'histogram':pin(run/'normalization_scene_slot_packed_histogram.csv'),
            'generation_code_sha256':{n:sha256(REPO_ROOT/n) for n in CODE},
            '2024_PIXELS_READ_FOR_FIT':0,'2025_PIXELS_READ':0,'IMERG_PIXELS_READ':0,'MODEL_PARAMETERS_UPDATED':False,
            'B0_MATCHED_CONTROL_SCALER_ADOPTION':'RESEARCHER_DECISION_REQUIRED','created_utc':audit.old_gate.now()}
        save(run/'normalization_b1_2023_shared_v1.json',value)
        save(run/'normalization_execution.json',{'status':'PASS_REAL_2023_TRAIN_FIT','normalization':pin(run/'normalization_b1_2023_shared_v1.json'),
            'completed_unique_frames':completed,'telemetry':telemetry,'source_guard_final_open_events':guard.source_open_events,
            'source_guard_prohibited_attempts':guard.prohibited_attempts,'staging_root':str(stagepath),'owned_staging_files_remaining':0,
            'elapsed_seconds':time.perf_counter()-began,'2024_PIXELS_READ_FOR_FIT':0,'2025_PIXELS_READ':0,'IMERG_PIXELS_READ':0,
            'MODEL_CHECKPOINT_LOADS':0,'MODEL_FORWARD_CALLS':0,'BACKWARD_CALLS':0,'OPTIMIZER_STEPS':0,'historical_files_unchanged':verify_history(run)})
        return {'status':'PASS_REAL_2023_TRAIN_FIT',**stats,'unique_frames':completed}
    except BaseException as exc:
        save(run/'normalization_failure.json',{'status':'FIT_FAILED_IMMUTABLE_HISTORY','exception_class':type(exc).__name__,
            'completed_unique_frames':completed,'telemetry':telemetry,'created_utc':audit.old_gate.now(),
            'source_guard_final_open_events':guard.source_open_events,'source_guard_prohibited_attempts':guard.prohibited_attempts})
        raise
