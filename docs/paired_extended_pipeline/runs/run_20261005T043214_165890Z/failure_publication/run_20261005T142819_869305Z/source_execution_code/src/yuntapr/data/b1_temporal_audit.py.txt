"""B13-only 2023/2024 temporal audit. No B1 model, fitting or evaluation."""
from collections import Counter
from contextlib import ExitStack
from datetime import datetime,timedelta,timezone
import csv
import hashlib
import json
import os
from pathlib import Path,PureWindowsPath
import re
import subprocess
import sys
import time
from unittest.mock import patch

import netCDF4
import numpy as np
import yaml
from yuntapr.contracts.loader import REPO_ROOT,sha256
from yuntapr.data.himawari_b13 import decode_b13,_cf_time
from yuntapr.data.sample_schema import utc
from yuntapr.evaluation import catalogue_gate_b0 as old_gate
from yuntapr.evaluation.catalogue_backend_b0 import CatalogueEnglishStaging
from yuntapr.spatial.sp04_mapping import load_sp04

BASE='4286f8151fea2185c99b3cea0c8e532e8cd90070'
HROOT=PureWindowsPath(r'H:\葵花202303_202510')
IROOT=PureWindowsPath(r'F:\云南极端降水数据\raw\IMERG')
CHECKPOINT_ROOT=PureWindowsPath(r'F:\pytorch\Research\outputs\formal_training')
STAGING_PARENT=PureWindowsPath(r'F:\pytorch\Research\stage0_himawari\cache\staging')
SLOT_PATH='config/b1/b1_six_slot_audit_definition_v1.json'
LAGS=(60,50,40,30,20,10)
SOURCE_NAME=re.compile(r'^NC_H(?:08|09)_(\d{8})_(\d{4})_R21_FLDK\.06001_06001\.nc$')
FRAME_FIELDS=('nominal','relative_path','source_bytes','source_sha256','present','readable','decoded',
    'valid_count','full_valid','metadata_valid','obs_start','obs_end','date_created','status','reasons')
SLOT_FIELDS=('sample_id','slot','expected_nominal','frame_status','causality_pass','scan_bucket_conforms','reasons')
POP_FIELDS=('sample_id','role','window_start','analysis_time','imerg_day_path','imerg_index',
    'population_status','frame_identity_index_sha256')
NEW_CODE=('src/yuntapr/data/b1_temporal_audit.py','scripts/audit_b1_temporal_v1.py',
    'tests/b1_temporal_audit/test_b1_temporal_audit.py')

def save(path,value):old_gate.save(path,value)
def read(path):return old_gate.read(path)
def safe(path):return old_gate.safe_artifact_path(path)
def code_hashes():return {n:sha256(REPO_ROOT/n) for n in NEW_CODE}
def write_csv(path,fields,rows):
    with safe(path).open('x',encoding='utf-8',newline='') as stream:
        writer=csv.DictWriter(stream,fieldnames=fields,extrasaction='raise');writer.writeheader();writer.writerows(rows)
def read_csv(path):
    with safe(path).open(encoding='utf-8-sig',newline='') as stream:return list(csv.DictReader(stream))

def in_scope(t):
    t=utc(t);return t.year in (2023,2024) and 3<=t.month<=10
def times(year,minutes):
    if year not in (2023,2024) or minutes not in (10,30):raise ValueError('Fixed development schedule required')
    start=datetime(year,3,1,tzinfo=timezone.utc);end=datetime(year,11,1,tzinfo=timezone.utc)
    return tuple(start+timedelta(minutes=minutes*i) for i in range(int((end-start).total_seconds()/(60*minutes))))
def slot_nominals(window_start):
    t=utc(window_start)
    if not in_scope(t) or t.minute not in (0,30) or t.second or t.microsecond:
        raise ValueError('Only exact 2023/2024 March-October target windows permitted')
    return tuple(t+timedelta(minutes=30-lag) for lag in LAGS)
def definition_bindings():
    return {'version':'v1','authority':'RESEARCHER_EXPLICIT_APPROVAL','status':'FROZEN_FOR_TEMPORAL_AUDIT',
        'baseline_commit':BASE,'analysis_time':'T+30min','nominal_offsets_minutes_before_analysis':list(LAGS),
        'ordering':'OLDEST_TO_LATEST','tensor_shape':'[B,6,501,501]','axis_1':'ORDERED_B13_TIME_SLOTS',
        'time_axis_5d_used':False,'causality':'actual_CF_obs_start<=actual_CF_obs_end<=analysis_time',
        'expected_scan_buckets':'[nominal,nominal+10min); diagnostic only, not an extra exclusion threshold',
        'outside_period_policy':'OUTSIDE_AUDIT_SCOPE_SEPARATE_FROM_MISSING_NO_FEBRUARY_READ',
        'years':[2023,2024],'months':list(range(3,11)),'channels':['B13'],
        'missing_policy':'RESEARCHER_DECISION_REQUIRED','normalization':'RESEARCHER_DECISION_REQUIRED',
        'fairness_population':'RESEARCHER_DECISION_REQUIRED','B1_DESIGN_FROZEN':False,
        'B1_TRAINING_AUTHORIZED':False,'2025_ACCESS_AUTHORIZED':False}
def load_definition(path,expected_sha):
    value=json.loads(old_gate.verified_bytes(path,expected_sha));expected=definition_bindings()
    if set(value)!=set(expected)|{'approved_utc','researcher_confirmation'} or any(value[k]!=v for k,v in expected.items()):
        raise PermissionError('Exact researcher-approved audit definition required')
    for key in ('time_axis_5d_used','B1_DESIGN_FROZEN','B1_TRAINING_AUTHORIZED','2025_ACCESS_AUTHORIZED'):
        if value[key] is not False:raise PermissionError('Explicit disabled training/2025 flags required')
    utc(value['approved_utc'])
    if value['researcher_confirmation']!='批准该时相与审计定义；其余决策保持待定（推荐）':
        raise PermissionError('Recorded researcher confirmation required')
    return value

class AuditGuard:
    """Permit only original read-only H B13 within the approved development dates."""
    def __init__(self):self.active=False;self.source_open_events=0;self.prohibited_attempts=0
    def check(self,path,mode='r',flags=0,*,directory=False):
        if not isinstance(path,(str,bytes,os.PathLike)):return
        p=PureWindowsPath(os.fsdecode(path))
        if p.is_relative_to(IROOT) or p.is_relative_to(CHECKPOINT_ROOT):
            self.prohibited_attempts+=1;raise PermissionError('No IMERG raw or checkpoint access in B1 temporal audit')
        if not p.is_relative_to(HROOT):return
        parts=p.relative_to(HROOT).parts
        writing=any(c in str(mode or '') for c in 'wax+') or bool(flags&(os.O_WRONLY|os.O_RDWR|os.O_CREAT|os.O_TRUNC))
        allowed=not writing and '..' not in parts
        if directory:
            allowed &= len(parts)==2 and parts[0] in {f'{y}{m:02d}' for y in (2023,2024) for m in range(3,11)} and bool(re.fullmatch(r'\d{2}',parts[1]))
        else:
            match=SOURCE_NAME.fullmatch(p.name)
            allowed &= len(parts)==3 and bool(match)
            if allowed:
                nominal=datetime.strptime('_'.join(match.groups()),'%Y%m%d_%H%M').replace(tzinfo=timezone.utc)
                allowed &= in_scope(nominal) and nominal.minute%10==0 and parts[0]==nominal.strftime('%Y%m') and parts[1]==nominal.strftime('%d')
        if not allowed:
            self.prohibited_attempts+=1;raise PermissionError('B1 audit rejects writes, 2025, February or invalid source identity before I/O')
        if not directory:self.source_open_events+=1
    def __enter__(self):
        self.active=True
        def hook(event,args):
            if not self.active:return
            if event=='open':self.check(args[0],args[1],args[2] if len(args)>2 else 0)
            elif event in ('os.scandir','os.listdir'):self.check(args[0],directory=True)
            elif event in ('os.remove','os.rmdir'):self.check(args[0],'w')
            elif event in ('os.rename','os.replace'):
                self.check(args[0],'w');self.check(args[1],'w')
        sys.addaudithook(hook)
        self.stack=ExitStack();self.stack.enter_context(old_gate.legacy.FinalInferenceGuard())
        def denied(*args,**kwargs):
            self.prohibited_attempts+=1;raise PermissionError('No model forward, checkpoint or optimizer operation in temporal audit')
        import torch
        self.stack.enter_context(patch.object(torch.nn.Module,'_call_impl',denied))
        self.stack.enter_context(patch.object(torch,'load',denied));self.stack.enter_context(patch.object(torch,'save',denied))
        original=netCDF4.Dataset
        def dataset(path,*args,**kwargs):
            p=PureWindowsPath(os.fsdecode(path))
            if p.is_relative_to(HROOT) or p.is_relative_to(IROOT) or p.is_relative_to(CHECKPOINT_ROOT):
                self.prohibited_attempts+=1;raise PermissionError('netCDF4 must receive caller-owned English staging, never original raw paths')
            return original(path,*args,**kwargs)
        self.stack.enter_context(patch.object(netCDF4,'Dataset',dataset));return self
    def __exit__(self,*exc):
        self.active=False;return self.stack.__exit__(*exc)

def empty_frame(nominal,status='MISSING'):
    value=dict.fromkeys(FRAME_FIELDS,'');value.update(nominal=utc(nominal).isoformat(),present=False,readable=False,
        decoded=False,full_valid=False,metadata_valid=False,status=status,reasons=status)
    return value
def frame_qc(path,mapping,nominal,telemetry):
    value=empty_frame(nominal,'CORRUPT_OR_UNREADABLE');value['present']=True;reasons=[]
    stage='OPEN'
    try:
        with netCDF4.Dataset(str(path),'r') as ds:
            ds.set_auto_maskandscale(False);value['readable']=True;stage='GRID_METADATA'
            variable=ds['tbb_13']
            if variable.dimensions!=('latitude','longitude') or variable.shape!=(501,501) or variable.units!='K':
                raise ValueError('B13 native shape/dimensions/units mismatch')
            mapping.assert_axes(np.asarray(ds['latitude'][:]),np.asarray(ds['longitude'][:]),mapping.axes['target_lat'],mapping.axes['target_lon'])
            stage='PACKED_PIXELS';raw=np.asarray(variable[:]);telemetry['b13_pixel_values_read']+=int(raw.size)
            attrs={k:variable.getncattr(k) for k in ('scale_factor','add_offset','valid_min','valid_max','_FillValue','missing_value') if k in variable.ncattrs()}
            decoded,valid=decode_b13(raw,attrs);count=int(np.count_nonzero(valid))
            value.update(decoded=True,valid_count=count,full_valid=count==251001 and bool(np.isfinite(decoded).all()))
            del raw,decoded,valid
            if count==0:reasons.append('ALL_FILL')
            elif count<251001:reasons.append('PARTIAL')
            stage='TIME_METADATA';start,end=_cf_time(ds,'start_time'),_cf_time(ds,'end_time')
            created=str(ds.getncattr('date_created')) if 'date_created' in ds.ncattrs() else ''
            if created:utc(created)
            value.update(obs_start=start.isoformat(),obs_end=end.isoformat(),date_created=created)
            value['metadata_valid']=start<=end
            if not value['metadata_valid']:reasons.append('TIME_METADATA_ERROR')
            value['status']=('FULL_VALID' if not reasons else reasons[0])
    except (OSError,RuntimeError):
        value['readable']=False;reasons.append('CORRUPT_OR_UNREADABLE');value['status']='CORRUPT_OR_UNREADABLE'
    except (KeyError,IndexError,AttributeError,ValueError,TypeError,OverflowError):
        reason='TIME_METADATA_ERROR' if stage=='TIME_METADATA' else 'B13_GRID_OR_PACKING_METADATA_ERROR'
        reasons.append(reason);value['status']=reason
    value['reasons']=';'.join(sorted(set(reasons)));return value

def slot_qc(sample_id,slot,nominal,frame,analysis):
    if not in_scope(nominal):
        return {'sample_id':sample_id,'slot':slot,'expected_nominal':nominal.isoformat(),'frame_status':'OUTSIDE_AUDIT_SCOPE',
            'causality_pass':'UNKNOWN','scan_bucket_conforms':'UNKNOWN','reasons':'OUTSIDE_AUDIT_SCOPE'}
    reasons=[r for r in frame['reasons'].split(';') if r];causal='UNKNOWN';conforms='UNKNOWN'
    if frame['metadata_valid']:
        start,end=utc(frame['obs_start']),utc(frame['obs_end'])
        causal=str(start<=end<=analysis);conforms=str(nominal<=start<=end<=nominal+timedelta(minutes=10))
        if causal=='False':reasons.append('NONCAUSAL_FRAME')
    elif frame['present'] and frame['readable'] and not reasons:
        reasons.append('TIME_METADATA_UNAVAILABLE')
    if frame['present'] and frame['decoded'] and not frame['full_valid'] and not {'PARTIAL','ALL_FILL'}&set(reasons):
        reasons.append('B13_NOT_FULL_VALID')
    return {'sample_id':sample_id,'slot':slot,'expected_nominal':nominal.isoformat(),'frame_status':frame['status'],
        'causality_pass':causal,'scan_bucket_conforms':conforms,'reasons':';'.join(sorted(set(reasons)))}

def temporal_decision(slots,target_valid):
    if len(slots)!=6 or [r['slot'] for r in slots]!=list(range(6)):raise ValueError('Six ordered slots required')
    reasons=[f'S{r["slot"]}_{reason}' for r in slots for reason in r['reasons'].split(';') if reason]
    for r in slots:
        if not r['reasons'] and (r['frame_status']!='FULL_VALID' or r['causality_pass']!='True'):
            reasons.append(f'S{r["slot"]}_INCOMPLETE_QC_EVIDENCE')
    if not target_valid:reasons.append('TARGET_NO_VALID_YUNNAN_FROM_PINNED_2023_2024_EVIDENCE')
    return not reasons,tuple(reasons)

def load_targets():
    protocol=yaml.safe_load((REPO_ROOT/'config/training/phase_a_training_protocol_v1.yaml').read_text(encoding='utf-8'))
    refs=protocol['identity'];source=refs['combined_eligibility_source']
    if sha256(REPO_ROOT/source['path'])!=source['sha256']:raise ValueError('Original target evidence changed')
    targets=read_csv(REPO_ROOT/source['path'])
    expected=[t for y in (2023,2024) for t in times(y,30)]
    if [utc(r['window_start']) for r in targets]!=expected:raise ValueError('Exactly 23520 development targets in fixed order required')
    original={}
    for year,key,count in ((2023,'eligible_train_manifest',11720),(2024,'eligible_validation_manifest',11727)):
        ref=refs[key]
        if sha256(REPO_ROOT/ref['path'])!=ref['sha256']:raise ValueError('Original B0 eligible population changed')
        rows=read_csv(REPO_ROOT/ref['path']);identities={r['window_start'] for r in rows}
        if len(rows)!=len(identities) or len(rows)!=count:raise ValueError('Original B0 eligible identity counts changed')
        original[year]=identities
    return targets,original,{k:refs[k] for k in ('combined_eligibility_source','eligible_train_manifest','eligible_validation_manifest')}

def verify_history(history):
    for name,ref in history.items():
        data=(REPO_ROOT/name).read_bytes()
        if hashlib.sha256(data).hexdigest()!=ref['sha256'] or hashlib.sha1(b'blob '+str(len(data)).encode()+b'\0'+data).hexdigest()!=ref['git_blob_sha1']:
            raise ValueError('Immutable baseline history changed')
    return len(history)

def execute(args):
    definition=load_definition(args.definition,args.definition_sha256)
    if subprocess.check_output(['git','rev-parse','HEAD'],cwd=REPO_ROOT).decode().strip()!=BASE:raise PermissionError('Execution baseline changed')
    run=safe(args.run_directory);history=read(run/'history_before.json');verify_history(history)
    if (run/'audit_start.json').exists() or (run/'final_status.json').exists() or (run/'failure.json').exists():raise PermissionError('New audit only; never overwrite completed/failed execution')
    expected_stage=STAGING_PARENT/('b1_temporal_'+run.name)
    stage_path=Path(str(expected_stage))
    if PureWindowsPath(str(args.staging_root))!=expected_stage or stage_path.resolve()!=stage_path or stage_path.exists():raise PermissionError('New exact English staging child required')
    started=time.perf_counter();guard=AuditGuard();stage=None;frames={};telemetry={'raw_source_open_events':0,
        'source_hash_bytes_read':0,'source_copy_bytes_read':0,'source_copy_bytes_written':0,
        'b13_pixel_values_read':0,'copy_seconds':0.0,'read_seconds':0.0,'temporary_bytes_peak':0,'cleanup_success':True}
    save(run/'audit_start.json',{'baseline':BASE,'definition_sha256':args.definition_sha256,'definition':definition,
        'code_sha256':code_hashes(),'B1_DESIGN_FROZEN':False,'scope':'B1_2023_2024_B13_TEMPORAL_QC_ONLY',
        'staging_root':str(stage_path),'created_utc':old_gate.now()})
    try:
        with guard:
            root=Path(str(HROOT))
            if not root.is_dir():raise OSError('FROZEN_H_SOURCE_ROOT_UNAVAILABLE')
            mapping=load_sp04();targets,original,refs=load_targets()
            # Existing full-fit source identities pin all original B0 eligible frames.
            fit=REPO_ROOT/'docs/phase_b_finalfit_preparation/runs/run_20261002T014649_144967Z/phase_b_finalfit_manifest.csv'
            if sha256(fit)!='00e6bd018eae6aeb05be0740b55a92b7a5cc9a44b9ab2b80affbad3e3282ccff':raise ValueError('Pinned B0 source identity manifest changed')
            known={r['b13_relative_path']:(int(r['b13_bytes']),r['b13_sha256']) for r in read_csv(fit)}
            stage=CatalogueEnglishStaging(stage_path,telemetry)
            native=run/'native_frames';native.mkdir();slots_root=run/'six_slots';slots_root.mkdir()
            monthly=[];frame_files={}
            for year in (2023,2024):
                scheduled=times(year,10)
                for month in range(3,11):
                    key=f'{year}{month:02d}';month_rows=[];cached_day=None;discovered={}
                    for nominal in (t for t in scheduled if t.month==month):
                        if nominal.date()!=cached_day:
                            cached_day=nominal.date();day=root/key/nominal.strftime('%d');discovered={}
                            if day.is_dir():
                                for path in day.glob('*.nc'):
                                    match=SOURCE_NAME.fullmatch(path.name)
                                    if not match:raise OSError('UNEXPECTED_SOURCE_IDENTITY_IN_FROZEN_DAY')
                                    stamp=datetime.strptime('_'.join(match.groups()),'%Y%m%d_%H%M').replace(tzinfo=timezone.utc)
                                    if stamp.date()!=nominal.date() or stamp.minute%10:raise OSError('MISPLACED_SOURCE_IDENTITY')
                                    discovered.setdefault(stamp,[]).append(path)
                        paths=discovered.get(nominal,[])
                        if len(paths)>1:raise OSError('AMBIGUOUS_NOMINAL_SOURCE_IDENTITY')
                        value=empty_frame(nominal)
                        if paths:
                            path=paths[0]
                            if path.resolve(strict=True)!=root.resolve(strict=True)/path.relative_to(root):raise OSError('RAW_SOURCE_REDIRECT')
                            mark=len(stage.records)
                            try:
                                with stage.local(path) as local:value=frame_qc(local,mapping,nominal,telemetry)
                            finally:
                                for record in stage.records[mark:]:
                                    telemetry['copy_seconds']+=record.copy_seconds or 0.0;telemetry['read_seconds']+=record.read_seconds or 0.0
                                    telemetry['temporary_bytes_peak']=max(telemetry['temporary_bytes_peak'],record.temporary_bytes)
                                    telemetry['cleanup_success'] &= record.cleanup_success
                                    if not record.size_match or record.sha256_match is not True or not record.cleanup_success:raise OSError('STAGING_SIZE_SHA_OR_CLEANUP_FAILED')
                            record=stage.records[mark];del stage.records[mark:]
                            relative=str(path.relative_to(root));identity=(record.temporary_bytes,record.source_sha256)
                            if relative in known and identity!=known[relative]:raise OSError('FROZEN_B0_SOURCE_IDENTITY_MISMATCH')
                            value.update(relative_path=relative,source_bytes=identity[0],source_sha256=identity[1])
                        frames[nominal]=value;month_rows.append(value)
                        if len(frames)%144==0:
                            progress={'native_nominal_slots_completed':len(frames),'expected_native_nominal_slots':70560,
                                'last_nominal':nominal.isoformat(),'elapsed_seconds':time.perf_counter()-started,
                                'raw_access_telemetry':telemetry,'2025_RAW_PIXELS_READ':0,'2025_MODEL_INFERENCE_SCENES':0,
                                'B1_TRAINING_STARTED':False,'updated_utc':old_gate.now()}
                            temporary=run/'progress.owned.tmp'
                            with temporary.open('x',encoding='utf-8') as stream:json.dump(progress,stream,ensure_ascii=False,indent=2,allow_nan=False)
                            os.replace(temporary,run/'progress.json')
                    path=native/(key+'.csv');write_csv(path,FRAME_FIELDS,month_rows);frame_files[path.relative_to(run).as_posix()]=sha256(path)
                    counts=Counter(r['status'] for r in month_rows);monthly.append({'month':key,'native_slots':len(month_rows),'status_counts':dict(sorted(counts.items()))})
                    print(json.dumps({'native_month_completed':key,'native_slots_completed':len(frames),'elapsed_seconds':time.perf_counter()-started}),flush=True)
            if len(frames)!=70560 or stage._owned or not telemetry['cleanup_success']:raise ValueError('Full native population or cleanup reconciliation failed')
            frame_index={'files':frame_files,'nominal_count':70560,'definition_sha256':args.definition_sha256,'original_target_refs':refs}
            save(run/'frame_identity_index.json',frame_index);frame_index_sha=sha256(run/'frame_identity_index.json')
            summaries=[];candidate_counts={};slot_index_files={};population_files={}
            for year in (2023,2024):
                role='2023_TRAIN' if year==2023 else '2024_VALIDATION';all_slots=[];all_candidate=[];b0_pop=[];intersection=[]
                summary={'role':role,'candidate_targets':11760,'B0_original_eligible':len(original[year]),
                    'all_6_slots_present':0,'all_6_slots_full_valid_causal':0,'six_slot_candidate_eligible':0,
                    'intersection_with_B0_original':0,'candidate_rejected_or_unresolved':0,
                    'outside_scope_targets':0,'missing_by_slot':[0]*6,'unreadable_by_slot':[0]*6,
                    'partial_by_slot':[0]*6,'all_fill_by_slot':[0]*6,'metadata_error_by_slot':[0]*6,
                    'noncausal_by_slot':[0]*6,'outside_scope_by_slot':[0]*6,'scan_bucket_deviation_by_slot':[0]*6}
                reason_counts=Counter();combinations=Counter();month_slot_rows={m:[] for m in range(3,11)}
                for target in (r for r in targets if utc(r['window_start']).year==year):
                    t=utc(target['window_start']);a=t+timedelta(minutes=30);sid=t.isoformat()
                    rows=[slot_qc(sid,i,n,frames.get(n),a) for i,n in enumerate(slot_nominals(t))]
                    all_slots.extend(rows);month_slot_rows[t.month].extend(rows)
                    present=all(in_scope(n) and frames[n]['present'] for n in slot_nominals(t))
                    complete=all(not r['reasons'] for r in rows)
                    candidate,reasons=temporal_decision(rows,int(target['imerg_valid_yunnan_count'] or 0)>0)
                    summary['all_6_slots_present']+=present;summary['all_6_slots_full_valid_causal']+=complete
                    summary['six_slot_candidate_eligible']+=candidate;summary['candidate_rejected_or_unresolved']+=not candidate
                    summary['outside_scope_targets']+=any(r['frame_status']=='OUTSIDE_AUDIT_SCOPE' for r in rows)
                    for row in rows:
                        i=row['slot'];rs=set(row['reasons'].split(';'))
                        for reason,key in (('MISSING','missing_by_slot'),('CORRUPT_OR_UNREADABLE','unreadable_by_slot'),
                            ('PARTIAL','partial_by_slot'),('ALL_FILL','all_fill_by_slot'),('NONCAUSAL_FRAME','noncausal_by_slot'),
                            ('OUTSIDE_AUDIT_SCOPE','outside_scope_by_slot')):
                            summary[key][i]+=reason in rs
                        summary['metadata_error_by_slot'][i]+=bool(rs&{'TIME_METADATA_ERROR','B13_GRID_OR_PACKING_METADATA_ERROR'})
                        summary['scan_bucket_deviation_by_slot'][i]+=row['scan_bucket_conforms']=='False'
                    reason_counts.update(reasons)
                    if reasons:combinations[';'.join(reasons)]+=1
                    base={'sample_id':sid,'role':role,'window_start':sid,'analysis_time':a.isoformat(),
                        'imerg_day_path':target['imerg_day_path'],'imerg_index':target['imerg_index'],
                        'population_status':'','frame_identity_index_sha256':frame_index_sha}
                    if sid in original[year]:b0_pop.append(dict(base,population_status='B0_ORIGINAL_FROZEN_ELIGIBLE'))
                    if candidate:
                        all_candidate.append(dict(base,population_status='B1_COMPLETE_SIX_SLOT_FULL_VALID_CAUSAL_CANDIDATE_NOT_FORMAL'))
                        if sid in original[year]:intersection.append(dict(base,population_status='B0_B1_CANDIDATE_INTERSECTION_NOT_PRIMARY_FROZEN'))
                summary['intersection_with_B0_original']=len(intersection)
                if len(all_slots)!=11760*6 or summary['six_slot_candidate_eligible']+summary['candidate_rejected_or_unresolved']!=11760:
                    raise ValueError('Six-slot/target reconciliation failed')
                summary['rejection_or_unresolved_reason_counts']=dict(sorted(reason_counts.items()))
                summary['multi_reason_combinations']=dict(sorted(combinations.items()))
                for month,rows in month_slot_rows.items():
                    path=slots_root/(f'{year}{month:02d}'+'.csv');write_csv(path,SLOT_FIELDS,rows);slot_index_files[path.relative_to(run).as_posix()]=sha256(path)
                for label,rows in (('b0_original_eligible',b0_pop),('b1_candidate_eligible',all_candidate),('intersection_candidate',intersection)):
                    path=run/(f'{label}_{year}.csv');write_csv(path,POP_FIELDS,rows);population_files[path.name]=sha256(path)
                summaries.append(summary);candidate_counts[str(year)]=len(all_candidate)
            save(run/'temporal_availability_summary.json',{'scope':'CURRENT_RAW_B13_2023_2024_MARCH_OCTOBER',
                'population_policy_status':'CANDIDATE_ONLY_MISSING_POLICY_NOT_FROZEN','definition_sha256':args.definition_sha256,
                'native_months':monthly,'annual':summaries,'raw_access_telemetry':telemetry,'2025_RAW_PIXELS_READ':0})
            preserved=verify_history(history)
            if sha256(args.definition)!=args.definition_sha256 or code_hashes()!=read(run/'audit_start.json')['code_sha256']:
                raise ValueError('Approved definition or execution code changed during audit')
            if guard.prohibited_attempts or stage._owned:raise ValueError('Forbidden attempt or retained temporary copy')
            status={'B1_DESIGN_FROZEN':False,'B1_SLOT_DEFINITION_FROZEN':True,'B1_TENSOR_CONTRACT_FROZEN':True,
                'B1_TEMPORAL_AUDIT_EXECUTED':True,'B1_MISSING_POLICY_FROZEN':False,'B1_NORMALIZATION_FROZEN':False,
                'B1_FAIRNESS_PRIMARY_POPULATION_FROZEN':False,'B1_FORMAL_MODEL_IMPLEMENTED':False,'B1_TRAINING_STARTED':False,
                'B1_NORMALIZATION_FITTED':False,'2025_FINAL_TEST_EXECUTED':False,'2025_MODEL_INFERENCE_SCENES':0,
                '2025_RAW_PIXELS_READ':0,'MODEL_CHECKPOINT_LOADS':0,'MODEL_FORWARD_CALLS':0,'OPTIMIZER_STEPS':0,'BACKWARD_CALLS':0,
                'historical_files_unchanged':preserved,'native_nominal_slots':70560,'candidate_targets':23520,'slot_instances':141120,
                'candidate_eligible_counts':candidate_counts,'frame_identity_index_sha256':frame_index_sha,
                'native_frame_csv_sha256':frame_files,'six_slot_csv_sha256':slot_index_files,'population_csv_sha256':population_files,
                'raw_access_telemetry':telemetry,'guard_original_H_open_events':guard.source_open_events,
                'definition_sha256':args.definition_sha256,'elapsed_seconds':time.perf_counter()-started,'completed_utc':old_gate.now()}
            save(run/'final_status.json',status);print(json.dumps({'status':'B1_TEMPORAL_AUDIT_COMPLETE_DESIGN_PENDING',
                'candidate_eligible_counts':candidate_counts,'native_slots':70560,'elapsed_seconds':status['elapsed_seconds']}),flush=True)
        return status
    except Exception as error:
        save(run/'failure.json',{'status':'B1_TEMPORAL_AUDIT_STOPPED','error_type':type(error).__name__,
            'native_slots_completed':len(frames),'raw_access_telemetry':telemetry,'2025_RAW_PIXELS_READ':0,
            '2025_FINAL_TEST_EXECUTED':False,'2025_MODEL_INFERENCE_SCENES':0,'B1_TRAINING_STARTED':False,
            'OPTIMIZER_STEPS':0,'BACKWARD_CALLS':0,'failed_utc':old_gate.now()})
        raise
