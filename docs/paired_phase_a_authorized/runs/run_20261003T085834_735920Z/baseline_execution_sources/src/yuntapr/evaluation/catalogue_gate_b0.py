"""Outcome-free catalogue schema and two-stage B0 Final Test authorization.

Importing this module does not discover or open sources or load checkpoints.
"""
from __future__ import annotations
from collections import Counter
from contextlib import ExitStack
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import csv
import hashlib
import json
import io
import math
from pathlib import Path, PureWindowsPath
import re
from types import MappingProxyType
import yaml

from yuntapr.contracts.loader import REPO_ROOT, sha256
from yuntapr.evaluation import final_test_b0 as legacy
from yuntapr.data.sample_schema import utc

PROTOCOL_PATH=Path('config/evaluation/b0_2025_final_test_protocol_v1.1.yaml')
PROTOCOL_SHA='b1be82d5bc03293c35ddc793faa1187e97fa48c537039181c0eb68a689f15eb8'
CATALOGUE_SCOPE='B0_2025_FINAL_TEST_CATALOGUE_ONLY'
FINAL_SCOPE='B0_2025_MAR_SEP_FINAL_TEST_ONLY'
FIXTURE_SCOPE='ENGINEERING_FIXTURE_CATALOGUE_ONLY'
START,END=legacy.START,legacy.END
COUNT=10272
COLUMNS=(
 'candidate_index','window_start','analysis_time','sample_id','expected_nominal',
 'b13_relative_path','b13_bytes','b13_sha256','expected_latest_available','b13_readable',
 'b13_metadata_valid','full_valid_native_pixels','b13_finite','obs_start','obs_end',
 'selected_nominal','used_older_causal_frame','imerg_day_path','imerg_bytes','imerg_sha256',
 'imerg_product','imerg_version','imerg_run_type','imerg_time_grid_provenance_pass',
 'imerg_index','imerg_valid_yunnan_count','eligible','rejection_reason')
POPULATION_COLUMNS=('candidate_index','sample_id','window_start','analysis_time','expected_nominal',
 'b13_relative_path','b13_bytes','b13_sha256','imerg_day_path','imerg_bytes','imerg_sha256','imerg_index')
SCIENCE_KEYS=('FINAL','identity','normalization','population','primary_metrics','metric_definitions',
 'inherited_diagnostics','diagnostic_declarations','inference','prohibitions')
_SEAL=object()

def read(path):return json.loads(safe_artifact_path(path).read_text(encoding='utf-8'))
def save(path,value):
    with safe_artifact_path(path).open('x',encoding='utf-8',newline='\n') as stream:
        json.dump(value,stream,ensure_ascii=False,indent=2,allow_nan=False);stream.write('\n')
def now():return datetime.now(timezone.utc).isoformat()

def frozen(value):
    if isinstance(value,dict):return MappingProxyType({k:frozen(v) for k,v in value.items()})
    if isinstance(value,(list,tuple)):return tuple(frozen(v) for v in value)
    return value

def safe_artifact_path(path):
    import os
    protected=(legacy.HROOT,legacy.IROOT,PureWindowsPath(r'F:\pytorch\Research\outputs\formal_training'))
    lexical=PureWindowsPath(os.path.abspath(path))
    if any(lexical.is_relative_to(root) for root in protected):
        raise PermissionError('Authorization and frozen metadata artifacts cannot point to raw sources or checkpoints')
    resolved=Path(path).resolve()
    if any(PureWindowsPath(str(resolved)).is_relative_to(root) for root in protected):
        raise PermissionError('Authorization and frozen metadata artifacts cannot point to raw sources or checkpoints')
    return resolved

def verified_bytes(path,expected_sha):
    resolved=safe_artifact_path(path)
    data=resolved.read_bytes()
    if hashlib.sha256(data).hexdigest()!=expected_sha:raise ValueError('Frozen file SHA mismatch')
    return data

def load_protocol(root=REPO_ROOT):
    root=Path(root);path=root/PROTOCOL_PATH
    if sha256(path)!=PROTOCOL_SHA:raise ValueError('Protocol v1.1 SHA mismatch')
    p=yaml.safe_load(path.read_text(encoding='utf-8'))
    v1=legacy.load_protocol(root)
    if (p['version']!='v1.1' or p['inherits']['sha256']!=legacy.PROTOCOL_SHA
            or tuple(p['catalogue_schema']['columns'])!=COLUMNS
            or tuple(p['catalogue_schema']['eligible_identity_columns'])!=POPULATION_COLUMNS
            or any(p[k]!=v1[k] for k in SCIENCE_KEYS)):
        raise ValueError('v1.1 changed inherited science or catalogue schema')
    return p

def implementation_hashes(root=REPO_ROOT):
    root=Path(root);result=legacy.implementation_hashes(root)
    for name in ('src/yuntapr/evaluation/catalogue_gate_b0.py',
                 'src/yuntapr/evaluation/catalogue_backend_b0.py',
                 'src/yuntapr/evaluation/final_test_b0_v1_1.py',
                 'scripts/build_b0_2025_final_test_catalogue_v1.py',
                 'scripts/test_b0_2025_final_v1_1.py',
                 'scripts/preflight_b0_catalogue_v1_1.py',
                 'tests/final_test_catalogue/test_catalogue_gate.py',
                 'tests/final_test_b0/test_catalogue_backend_v1_1.py'):
        result[name]=sha256(root/name)
    return result

def scheduled_times():
    return tuple(START+timedelta(minutes=30*i) for i in range(COUNT))

def strict_schema(row,columns=COLUMNS):
    if not isinstance(row,dict) or set(row)!=set(columns):
        # Any additional field is forbidden, including new outcome aliases.
        raise ValueError('Catalogue accepts exact allowed fields only; outcome-derived or unknown field rejected')
    if any(type(v) not in (str,int,float,bool) for v in row.values()):
        raise ValueError('Catalogue cells must be scalar; hidden nested outcomes rejected')
    if any(type(v) is float and not math.isfinite(v) for v in row.values()):
        raise ValueError('Nonfinite catalogue cell rejected')
    if columns==COLUMNS:
        for key in ('obs_start','obs_end','selected_nominal'):
            if row[key]:utc(row[key])
        for key,expected in (('imerg_product','IMERG'),('imerg_version','V07'),('imerg_run_type','Final')):
            if row[key] not in ('',expected):raise ValueError('Only validated product identities or empty unavailable values allowed')
    return row

def candidate_template(index,start):
    t=legacy.guard_time(start);nom=t+timedelta(minutes=20)
    if index<0 or index>=COUNT or t!=START+timedelta(minutes=30*index):
        raise ValueError('Candidate index/window mismatch')
    r={key:'' for key in COLUMNS}
    r.update(candidate_index=str(index),window_start=t.isoformat(),sample_id=t.isoformat(),
        analysis_time=(t+timedelta(minutes=30)).isoformat(),expected_nominal=nom.isoformat(),
        imerg_day_path=str(legacy.IROOT/'2025'/('imerg_'+t.strftime('%Y%m%d')+'.nc')),
        imerg_index=str(t.hour*2+t.minute//30),b13_bytes='0',imerg_bytes='0',
        full_valid_native_pixels='0',imerg_valid_yunnan_count='0',
        expected_latest_available='False',b13_readable='False',b13_metadata_valid='False',
        b13_finite='False',used_older_causal_frame='False',imerg_time_grid_provenance_pass='False',
        eligible='False')
    return r

def integer(value,name,minimum=0,maximum=None):
    if isinstance(value,bool) or not re.fullmatch(r'0|[1-9][0-9]*',str(value)):
        raise ValueError('Invalid integer field: '+name)
    n=int(value)
    if n<minimum or (maximum is not None and n>maximum):raise ValueError('Integer out of range: '+name)
    return n

def guard_paths(row):
    t=legacy.guard_time(row['window_start']);nom=t+timedelta(minutes=20)
    i=PureWindowsPath(row['imerg_day_path'])
    if ('..' in i.parts or i.parent!=legacy.IROOT/'2025'
            or i.name!='imerg_'+t.strftime('%Y%m%d')+'.nc'):
        raise ValueError('IMERG source identity or October source rejected before I/O')
    relative=PureWindowsPath(row['b13_relative_path'])
    if not row['b13_relative_path']:
        if legacy.flag(row['expected_latest_available']):raise ValueError('Available B13 requires source path identity')
        return None,Path(str(i))
    if (relative.drive or relative.is_absolute() or '..' in relative.parts or len(relative.parts)!=3
            or relative.parts[:2]!=(nom.strftime('%Y%m'),nom.strftime('%d'))
            or re.fullmatch(r'NC_H[0-9]{2}_'+nom.strftime('%Y%m%d_%H%M')+r'_R[0-9]{2}_FLDK\.[0-9]{5}_[0-9]{5}\.nc',relative.name) is None):
        raise ValueError('B13 expected latest source identity or October source rejected before I/O')
    return Path(str(legacy.HROOT/relative)),Path(str(i))

def eligibility(row):
    strict_schema(row);t=legacy.guard_time(row['window_start']);guard_paths(row)
    index=integer(row['candidate_index'],'candidate_index',maximum=COUNT-1)
    if (t!=START+timedelta(minutes=30*index) or row['sample_id']!=t.isoformat()
            or utc(row['analysis_time'])!=t+timedelta(minutes=30)
            or utc(row['expected_nominal'])!=t+timedelta(minutes=20)
            or integer(row['imerg_index'],'imerg_index',maximum=47)!=index%48):
        raise ValueError('Candidate/time identity mismatch')
    full=integer(row['full_valid_native_pixels'],'full_valid_native_pixels',maximum=251001)
    count=integer(row['imerg_valid_yunnan_count'],'imerg_valid_yunnan_count',maximum=3430)
    for k in ('b13_bytes','imerg_bytes'):integer(row[k],k)
    for k in ('b13_sha256','imerg_sha256'):
        if row[k] and not re.fullmatch('[0-9a-f]{64}',row[k]):raise ValueError('Invalid source SHA field')
    reasons=[]
    if not legacy.flag(row['expected_latest_available']):reasons.append('EXPECTED_LATEST_B13_MISSING_NO_FORMAL_FALLBACK')
    if not legacy.flag(row['b13_readable']):reasons.append('B13_NOT_READABLE')
    if full!=251001 or not legacy.flag(row['b13_finite']):reasons.append('B13_FULL_SCENE_REQUIRED')
    if not legacy.flag(row['b13_metadata_valid']):reasons.append('B13_METADATA_INVALID')
    elif (utc(row['selected_nominal'])!=t+timedelta(minutes=20)
          or utc(row['obs_start'])>utc(row['obs_end']) or utc(row['obs_end'])>utc(row['analysis_time'])):
        reasons.append('LATEST_CAUSAL_TIME_FAILED')
    if legacy.flag(row['used_older_causal_frame']):reasons.append('OLDER_FALLBACK_PROHIBITED')
    if (row['imerg_product'],row['imerg_version'],row['imerg_run_type'])!=('IMERG','V07','Final'):
        reasons.append('IMERG_V07_FINAL_REQUIRED')
    if not legacy.flag(row['imerg_time_grid_provenance_pass']):reasons.append('IMERG_TIME_GRID_PROVENANCE_FAILED')
    if count==0:reasons.append('NO_VALID_YUNNAN_SUPERVISION')
    if not reasons and any(not row[k] for k in ('b13_sha256','imerg_sha256')):
        raise ValueError('Eligible source SHA missing')
    if not reasons and any(int(row[k])<=0 for k in ('b13_bytes','imerg_bytes')):
        raise ValueError('Eligible source size missing')
    return reasons

def validate_catalogue(rows):
    if len(rows)!=COUNT:raise ValueError('All 10272 exact scheduled candidate windows required')
    eligible=[]
    for index,row in enumerate(rows):
        strict_schema(row)
        if integer(row['candidate_index'],'candidate_index')!=index or legacy.guard_time(row['window_start'])!=START+timedelta(minutes=30*index):
            raise ValueError('Missing/duplicate/reordered candidate rejected')
        reasons=eligibility(row)
        if legacy.flag(row['eligible'])!=(not reasons) or row['rejection_reason']!=';'.join(reasons):
            raise ValueError('Frozen eligibility or rejection reason mismatch')
        if not reasons:eligible.append(row)
    return eligible

def csv_from_bytes(data,columns=COLUMNS):
    with io.StringIO(data.decode('utf-8'),newline='') as stream:
        reader=csv.DictReader(stream)
        if tuple(reader.fieldnames or ())!=columns:raise ValueError('CSV header must be exact ordered whitelist; duplicate/outcome fields rejected')
        rows=list(reader)
    for row in rows:strict_schema(row,columns)
    return rows

def read_csv(path,columns=COLUMNS):return csv_from_bytes(safe_artifact_path(path).read_bytes(),columns)

def write_csv(path,rows,columns=COLUMNS):
    with safe_artifact_path(path).open('x',encoding='utf-8',newline='') as stream:
        writer=csv.DictWriter(stream,fieldnames=columns,lineterminator='\n');writer.writeheader()
        for row in rows:strict_schema(row,columns);writer.writerow(row)

def eligible_identities(rows):return [{k:row[k] for k in POPULATION_COLUMNS} for row in rows]

def validate_manifests(candidates,population):
    eligible=validate_catalogue(candidates)
    for row in population:strict_schema(row,POPULATION_COLUMNS)
    if population!=eligible_identities(eligible):raise ValueError('Eligible population manifest must equal exact fixed-order identity projection')
    return eligible

@dataclass(frozen=True)
class CatalogueAuthority:
    value:dict
    sha256:str
    _seal:object
    fixture:bool=False

    def __post_init__(self):object.__setattr__(self,'value',frozen(dict(self.value)))

    @classmethod
    def fixture_only(cls):
        return cls({'scope':FIXTURE_SCOPE},'FIXTURE_ONLY',_SEAL,True)

    @classmethod
    def load(cls,path,expected_sha):
        if path is None or not expected_sha:raise PermissionError('Separate researcher B0_2025_FINAL_TEST_CATALOGUE_ONLY authority required')
        value=json.loads(verified_bytes(path,expected_sha));p=load_protocol()
        expected={'version':'v1.1','AUTHORIZED_BY':'RESEARCHER','scope':CATALOGUE_SCOPE,
            'FINAL_TEST_CATALOGUE_AUTHORIZED':True,'FINAL_TEST_2025_AUTHORIZED':False,
            'protocol_sha256':PROTOCOL_SHA,'implementation_sha256':implementation_hashes(),
            'source_roots':{'Himawari':str(legacy.HROOT),'IMERG':str(legacy.IROOT)}}
        keys=set(expected)|{'created_utc','imerg_completion_manifest_path','imerg_completion_manifest_sha256'}
        if set(value)!=keys or any(value.get(k)!=v for k,v in expected.items()):raise PermissionError('Catalogue-only authority scope/provenance mismatch')
        utc(value['created_utc'])
        completion=PureWindowsPath(value['imerg_completion_manifest_path'])
        if '..' in completion.parts or not completion.is_relative_to(legacy.IROOT):
            raise PermissionError('IMERG completion manifest must remain under frozen raw root')
        relative=completion.relative_to(legacy.IROOT)
        if (completion.suffix.lower() not in ('.json','.jsonl')
                or not (len(relative.parts)==1 or len(relative.parts)==2 and relative.parts[0]=='manifests')):
            raise PermissionError('Only root/manifests metadata JSON completion manifests are allowed; raw NC and October rejected')
        if not re.fullmatch('[0-9a-f]{64}',value['imerg_completion_manifest_sha256']):
            raise ValueError('Completion manifest SHA pin required')
        return cls(value,expected_sha,_SEAL)

    def require_catalogue(self,*,allow_fixture=False):
        if self._seal is not _SEAL:raise PermissionError('Verified catalogue authority required')
        if self.fixture:
            if not allow_fixture or self.value.get('scope')!=FIXTURE_SCOPE:raise PermissionError('Fixture authority cannot access real sources')
        elif self.value.get('scope')!=CATALOGUE_SCOPE or self.value.get('FINAL_TEST_CATALOGUE_AUTHORIZED') is not True:
            raise PermissionError('Catalogue-only authority required')

    def require_final(self):raise PermissionError('Catalogue-only scope cannot authorize FINAL loading or inference')

class CatalogueOnlyGuard:
    """Block checkpoint/model/forward/metric paths during catalogue QC, including fixtures."""
    def __init__(self):self.saved=[];self.attempts=Counter();self.enabled=False;self.inference_guard=None
    def __enter__(self):
        try:return self._install()
        except BaseException:
            self.__exit__(None,None,None);raise
    def _install(self):
        import torch
        self.inference_guard=legacy.FinalInferenceGuard();self.inference_guard.__enter__()
        def patch(owner,name,kind):
            own=name in vars(owner);original=vars(owner).get(name)
            def reject(*args,**kwargs):
                self.attempts[kind]+=1;raise PermissionError('Catalogue-only scope prohibits '+kind)
            self.saved.append((owner,name,original,own));setattr(owner,name,reject)
        patch(torch,'load','checkpoint_loading')
        patch(torch.serialization,'load','checkpoint_loading')
        patch(legacy,'verify_final','FINAL_loading')
        patch(legacy,'load_inference_model','model_loading')
        patch(legacy.B0Model,'__init__','model_instantiation')
        patch(legacy.B0Model,'forward','model_forward')
        for name in ('forward_formal','_evaluate'):
            if hasattr(legacy.B0Model,name):patch(legacy.B0Model,name,'model_forward')
        patch(torch.nn.Module,'_call_impl','model_forward')
        patch(legacy.GlobalValidationAccumulator,'__init__','performance_metrics')
        patch(legacy.GlobalValidationAccumulator,'add','performance_metrics')
        patch(legacy.GlobalValidationAccumulator,'report','performance_metrics')
        patch(legacy.FinalAccumulator,'__init__','performance_metrics')
        for name in ('add','primary_report','diagnostics','report'):
            patch(legacy.FinalAccumulator,name,'performance_metrics')
        from yuntapr.training import scientific_review,phase_a_validation
        patch(scientific_review.ReviewAccumulator,'__init__','performance_metrics')
        patch(scientific_review.ReviewAccumulator,'add','performance_metrics')
        for name in ('spatial_metrics','reconcile'):
            if hasattr(scientific_review.ReviewAccumulator,name):patch(scientific_review.ReviewAccumulator,name,'performance_metrics')
        patch(scientific_review,'probability_summary','performance_metrics')
        patch(legacy,'probability_summary','performance_metrics')
        patch(phase_a_validation,'grouped_occurrence_metrics','performance_metrics')
        from yuntapr.losses import total_loss,focal,pinball
        from yuntapr.training import forward_step
        patch(forward_step,'b0_core_loss','loss')
        patch(total_loss,'b0_core_loss','loss')
        patch(total_loss,'focal_bce_sum','loss')
        patch(total_loss,'pinball_sum','loss')
        patch(focal,'focal_bce_sum','loss')
        patch(pinball,'pinball_sum','loss')
        self.enabled=True
        def audit(event,args):
            if self.enabled and event=='open' and isinstance(args[0],(str,bytes,Path)):
                import os
                p=PureWindowsPath(os.fsdecode(args[0]))
                if p.is_relative_to(PureWindowsPath(r'F:\pytorch\Research\outputs\formal_training')):
                    self.attempts['checkpoint_file_open']+=1;raise PermissionError('Catalogue-only scope cannot open any formal checkpoint')
        import sys
        sys.addaudithook(audit)
        return self
    def __exit__(self,*exc):
        self.enabled=False
        try:
            for owner,name,original,own in reversed(self.saved):
                if own:setattr(owner,name,original)
                else:delattr(owner,name)
        finally:
            self.saved.clear()
            if self.inference_guard is not None:self.inference_guard.__exit__(*exc)
            self.inference_guard=None

class PreflightSourceGuard(legacy.RawSourceGuard):
    """Pin original roots so synthetic hooks cannot retarget the zero-access guard."""
    def __init__(self):
        super().__init__(preflight=True)
        self.original_roots=(legacy.HROOT,legacy.IROOT,
            PureWindowsPath(r'F:\pytorch\Research\outputs\formal_training'))
    def check(self,value,mode='r',flags=0):
        import os
        if isinstance(value,(str,bytes,os.PathLike)):
            path=PureWindowsPath(os.fsdecode(value))
            if any(path.is_relative_to(root) for root in self.original_roots):
                self.prohibited_attempts.append(str(path))
                raise PermissionError('Fixture preflight cannot access any real raw source or checkpoint')
    def __enter__(self):
        super().__enter__()
        import sys
        def audit(event,args):
            if self.enabled and event in ('os.listdir','os.scandir'):self.check(args[0])
        sys.addaudithook(audit)
        return self

class CatalogueSourceGuard:
    """Catalogue-only raw reads are restricted to frozen roots, dates and manifest."""
    def __init__(self,authority):
        authority.require_catalogue()
        self.manifest=PureWindowsPath(authority.value['imerg_completion_manifest_path'])
        self.active=False;self.raw_open_events=0;self.qc_access=False
    def check(self,path,mode='r',flags=0,*,directory=False):
        import os
        if not isinstance(path,(str,bytes,os.PathLike)):return
        p=PureWindowsPath(os.fsdecode(path))
        writing=any(c in str(mode or '') for c in 'wax+') or bool(flags&(os.O_WRONLY|os.O_RDWR|os.O_CREAT|os.O_TRUNC))
        for root in (legacy.HROOT,legacy.IROOT):
            if not p.is_relative_to(root):continue
            if writing or '..' in p.parts:raise PermissionError('Catalogue raw sources are permanently read-only')
            parts=p.relative_to(root).parts
            allowed=p==self.manifest and not directory
            if directory:
                allowed=(root==legacy.HROOT and len(parts)==2 and parts[0] in {f'2025{m:02d}' for m in range(3,10)}
                         and re.fullmatch('[0-9]{2}',parts[1]) is not None)
            elif root==legacy.HROOT:
                allowed|=(len(parts)==3 and parts[0] in {f'2025{m:02d}' for m in range(3,10)}
                    and re.search('_'+re.escape(parts[0]+parts[1])+r'_\d{4}_',p.name) is not None and p.suffix.lower()=='.nc')
            else:
                allowed|=(len(parts)==2 and parts[0]=='2025' and re.fullmatch(r'imerg_20250[3-9]\d{2}\.nc',p.name) is not None)
            if not allowed:raise PermissionError('Catalogue scope rejects out-of-period/October source before I/O')
            self.qc_access=True
            if not directory:self.raw_open_events+=1
    def __enter__(self):
        import sys,netCDF4
        self.active=True
        def audit(event,args):
            if not self.active:return
            if event=='open':self.check(args[0],args[1],args[2] if len(args)>2 else 0)
            elif event in ('os.scandir','os.listdir'):self.check(args[0],directory=True)
        sys.addaudithook(audit);self.saved=netCDF4.Dataset
        def checked(path,*args,**kwargs):
            self.check(path,args[0] if args else kwargs.get('mode','r'))
            return self.saved(path,*args,**kwargs)
        netCDF4.Dataset=checked
        return self
    def __exit__(self,*exc):
        import netCDF4
        self.active=False;netCDF4.Dataset=self.saved

def sanitized_telemetry(value):
    allowed={'2025_PIXELS_READ','2025_CATALOGUE_QC_ACCESS','raw_source_open_events',
        'b13_pixel_values_read','imerg_pixel_values_read','source_hash_bytes_read',
        'copy_seconds','read_seconds','temporary_bytes_peak','cleanup_success',
        'source_copy_bytes_read','source_copy_bytes_written'}
    if not isinstance(value,dict) or set(value)-allowed:raise ValueError('Outcome or unknown telemetry field prohibited')
    result={}
    for key,v in value.items():
        if key in ('2025_CATALOGUE_QC_ACCESS','cleanup_success'):
            if type(v) is not bool:raise ValueError('Telemetry boolean required')
        elif key in ('copy_seconds','read_seconds'):
            if type(v) not in (int,float) or not math.isfinite(v) or v<0:raise ValueError('Nonnegative finite duration required')
        elif type(v) is not int or v<0:raise ValueError('Nonnegative telemetry integer required')
        result[key]=v
    return result

def build_catalogue(authority,backend,output_dir,*,fixture=False,_output_seal=None):
    authority.require_catalogue(allow_fixture=fixture)
    if bool(getattr(backend,'fixture_only',False))!=fixture or bool(authority.fixture)!=fixture:
        raise PermissionError('Fixture backend/authority cannot access real catalogue execution')
    output=safe_artifact_path(output_dir)
    # All authority checks precede output creation, discovery and probe calls.
    with CatalogueOnlyGuard():
        if _output_seal is not _SEAL:output.mkdir(parents=True,exist_ok=False)
        rows=[]
        for index,t in enumerate(scheduled_times()):
            row=backend.probe(index,t);strict_schema(row)
            reasons=eligibility(row)
            row['eligible']=str(not reasons);row['rejection_reason']=';'.join(reasons)
            rows.append(row)
        eligible=validate_catalogue(rows)
        candidate=output/'b0_2025_final_test_candidate_catalogue_v1.csv'
        population=output/'b0_2025_final_test_population_manifest_v1.csv'
        write_csv(candidate,rows);write_csv(population,eligible_identities(eligible),POPULATION_COLUMNS)
        validate_manifests(read_csv(candidate),read_csv(population,POPULATION_COLUMNS))
        counts=Counter(reason for row in rows for reason in row['rejection_reason'].split(';') if reason)
        telemetry=sanitized_telemetry(dict(getattr(backend,'telemetry',{})))
        result={'version':'v1.1','status':'FIXTURE_CATALOGUE_FROZEN' if fixture else 'CATALOGUE_FROZEN',
            'scope':FIXTURE_SCOPE if fixture else CATALOGUE_SCOPE,'protocol_sha256':PROTOCOL_SHA,
            'implementation_sha256':implementation_hashes(),'catalogue_authorization_sha256':authority.sha256,
            'candidate_catalogue_sha256':sha256(candidate),'eligible_population_manifest_sha256':sha256(population),
            'candidate_count':COUNT,'eligible_count':len(eligible),'rejected_count':COUNT-len(eligible),
            'rejection_reason_counts':dict(sorted(counts.items())),
            '2025_CATALOGUE_QC_ACCESS':not fixture,'2025_FINAL_TEST_EXECUTED':False,
            '2025_MODEL_INFERENCE_SCENES':0,'2025_FINAL_TEST_METRICS_COMPUTED':False,
            '2025_TARGET_OUTCOME_SUMMARIES_EXPOSED':False,'raw_access_telemetry':telemetry,
            'fixture_only':fixture,'freeze_completed_utc':now()}
        save(output/'catalogue_freeze_record.json',result)
        return result

@dataclass(frozen=True)
class FinalAuthority:
    value:dict
    sha256:str
    _seal:object
    candidates:tuple=()
    population:tuple=()

    def __post_init__(self):
        object.__setattr__(self,'value',frozen(dict(self.value)))
        object.__setattr__(self,'candidates',tuple(frozen(dict(r)) for r in self.candidates))
        object.__setattr__(self,'population',tuple(frozen(dict(r)) for r in self.population))

    @classmethod
    def load(cls,path,expected_sha,candidate_path,population_path,freeze_path):
        if path is None or not expected_sha:raise PermissionError('Second-stage researcher authorization required after catalogue freeze')
        value=json.loads(verified_bytes(path,expected_sha))
        # Require all bindings explicitly; a legacy population-only grant fails
        # before catalogue files, freeze evidence or FINAL can be opened.
        mandatory={'protocol_sha256','implementation_sha256','FINAL_sha256','normalization_sha256',
            'candidate_catalogue_sha256','eligible_population_manifest_sha256','catalogue_freeze_record_sha256'}
        if not mandatory<=value.keys():raise PermissionError('Frozen candidate and eligible population manifest SHA bindings required')
        wanted={'version':'v1.1','AUTHORIZED_BY':'RESEARCHER','scope':FINAL_SCOPE,
            'FINAL_TEST_2025_AUTHORIZED':True,'protocol_sha256':PROTOCOL_SHA,
            'implementation_sha256':implementation_hashes(),'FINAL_sha256':legacy.FINAL_SHA,
            'normalization_sha256':legacy.NORMALIZATION_SHA}
        keys=set(wanted)|mandatory|{'created_utc'}
        if set(value)!=keys or any(value.get(k)!=v for k,v in wanted.items()):raise PermissionError('Second-stage authority scope/provenance mismatch')
        if any(p is None for p in (candidate_path,population_path,freeze_path)):
            raise PermissionError('Frozen catalogue/population/record paths required')
        bindings={'candidate_catalogue_sha256':Path(candidate_path),'eligible_population_manifest_sha256':Path(population_path),
            'catalogue_freeze_record_sha256':Path(freeze_path)}
        snapshots={k:verified_bytes(p,value[k]) for k,p in bindings.items()}
        freeze=json.loads(snapshots['catalogue_freeze_record_sha256'])
        freeze_keys={'version','status','scope','protocol_sha256','implementation_sha256','catalogue_authorization_sha256',
            'candidate_catalogue_sha256','eligible_population_manifest_sha256','candidate_count','eligible_count','rejected_count',
            'rejection_reason_counts','2025_CATALOGUE_QC_ACCESS','2025_FINAL_TEST_EXECUTED','2025_MODEL_INFERENCE_SCENES',
            '2025_FINAL_TEST_METRICS_COMPUTED','2025_TARGET_OUTCOME_SUMMARIES_EXPOSED','raw_access_telemetry','fixture_only','freeze_completed_utc'}
        if set(freeze)!=freeze_keys or freeze.get('version')!='v1.1':raise ValueError('Freeze record exact metadata whitelist required')
        sanitized_telemetry(freeze['raw_access_telemetry'])
        if (freeze.get('status')!='CATALOGUE_FROZEN' or freeze.get('fixture_only') is not False
                or freeze.get('scope')!=CATALOGUE_SCOPE or freeze.get('protocol_sha256')!=PROTOCOL_SHA
                or freeze.get('implementation_sha256')!=implementation_hashes()
                or freeze.get('2025_TARGET_OUTCOME_SUMMARIES_EXPOSED') is not False
                or freeze.get('2025_CATALOGUE_QC_ACCESS') is not True
                or freeze.get('2025_FINAL_TEST_EXECUTED') is not False
                or type(freeze.get('2025_MODEL_INFERENCE_SCENES')) is not int or freeze['2025_MODEL_INFERENCE_SCENES']!=0
                or freeze.get('2025_FINAL_TEST_METRICS_COMPUTED') is not False
                or not re.fullmatch('[0-9a-f]{64}',freeze['catalogue_authorization_sha256'])
                or utc(value['created_utc'])<utc(freeze['freeze_completed_utc'])):
            raise PermissionError('Real catalogue must freeze before separate Final Test authorization')
        if any(freeze.get(k)!=value[k] for k in ('candidate_catalogue_sha256','eligible_population_manifest_sha256')):
            raise ValueError('Freeze record binding mismatch')
        candidates=csv_from_bytes(snapshots['candidate_catalogue_sha256'])
        population=csv_from_bytes(snapshots['eligible_population_manifest_sha256'],POPULATION_COLUMNS)
        eligible=validate_manifests(candidates,population)
        counts=dict(sorted(Counter(reason for row in candidates for reason in row['rejection_reason'].split(';') if reason).items()))
        if (not eligible or freeze.get('candidate_count')!=COUNT or freeze.get('eligible_count')!=len(eligible)
                or freeze.get('rejected_count')!=COUNT-len(eligible) or freeze.get('rejection_reason_counts')!=counts):
            raise ValueError('Frozen population reconciliation failed or empty Final Test population')
        return cls(value,expected_sha,_SEAL,tuple(candidates),tuple(population))

    def require_final(self):
        if self._seal is not _SEAL or self.value.get('scope')!=FINAL_SCOPE or self.value.get('FINAL_TEST_2025_AUTHORIZED') is not True:
            raise PermissionError('Verified second-stage Final Test authority required')

    def require_catalogue(self,**kwargs):raise PermissionError('Final Test authority does not authorize rebuilding catalogue')
