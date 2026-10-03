"""Researcher-authorized catalogue execution with a pinned metadata-path adapter.

The c661d8a gate, readers, eligibility, protocol and all historical artifacts are
unchanged. Only the explicitly approved existing completion-manifest location is
adapted; checkpoint/model/forward/loss/metric guards remain active throughout QC.
"""
from collections import Counter
from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path, PureWindowsPath
import subprocess
import time
from yuntapr.contracts.loader import REPO_ROOT,sha256
from yuntapr.evaluation import catalogue_gate_b0 as gate
from yuntapr.evaluation import catalogue_backend_b0 as frozen_backend
from yuntapr.data.sample_schema import utc

BASE='c661d8a31dbd8cc205624716d8a2d0fcd0867023'
METADATA_MANIFEST=PureWindowsPath(r'F:\云南极端降水数据\manifests\imerg_manifest.jsonl')
STAGING_PARENT=PureWindowsPath(r'F:\pytorch\Research\stage0_himawari\cache\staging')
_EXECUTION_SEAL=object()
EXECUTION_FILES=('src/yuntapr/evaluation/catalogue_execution_v1_1.py',
 'scripts/execute_b0_2025_catalogue_only_v1_1.py',
 'tests/final_test_catalogue/test_catalogue_execution_v1_1.py')

def execution_hashes():return {name:sha256(REPO_ROOT/name) for name in EXECUTION_FILES}

def execution_staging_path(value,run):
    expected=STAGING_PARENT/('catalogue_only_'+run.name)
    if PureWindowsPath(str(value))!=expected:
        raise PermissionError('Dedicated staging child under the researcher-approved English cache required')
    path=Path(str(expected))
    if path.resolve()!=path or path.exists():
        raise PermissionError('Staging child must be new and must not redirect')
    return path

def authorization_bindings(protocol,manifest_sha):
    return {'version':'v1.1','AUTHORIZED_BY':'RESEARCHER','scope':gate.CATALOGUE_SCOPE,
        'baseline_commit':BASE,'FINAL_TEST_CATALOGUE_AUTHORIZED':True,'FINAL_TEST_2025_AUTHORIZED':False,
        'protocol_sha256':gate.PROTOCOL_SHA,'implementation_sha256':gate.implementation_hashes(),
        'execution_implementation_sha256':execution_hashes(),
        'catalogue_implementation_sha256':sha256(REPO_ROOT/'src/yuntapr/evaluation/catalogue_gate_b0.py'),
        'backend_implementation_sha256':sha256(REPO_ROOT/'src/yuntapr/evaluation/catalogue_backend_b0.py'),
        'FINAL_sha256':gate.legacy.FINAL_SHA,
        'FINAL_identity_record_sha256':protocol['identity']['final_checkpoint_identity']['sha256'],
        'normalization_sha256':gate.legacy.NORMALIZATION_SHA,
        'candidate_count':gate.COUNT,
        'source_roots':{'Himawari':str(gate.legacy.HROOT),'IMERG':str(gate.legacy.IROOT)},
        'imerg_completion_manifest_path':str(METADATA_MANIFEST),
        'imerg_completion_manifest_sha256':manifest_sha,
        'completion_manifest_metadata_path_exception_approved':True,
        'FINAL_verification_mode':'FROZEN_IDENTITY_RECORD_ONLY_RESEARCHER_APPROVED'}

@dataclass(frozen=True)
class ExecutionAuthority:
    value:dict
    sha256:str
    _seal:object
    fixture:bool=False
    def __post_init__(self):object.__setattr__(self,'value',gate.frozen(dict(self.value)))
    @classmethod
    def load(cls,path,expected_sha):
        if path is None or not expected_sha:raise PermissionError('Separate catalogue-only authorization required')
        value=json.loads(gate.verified_bytes(path,expected_sha))
        protocol=gate.load_protocol()
        manifest_sha=value.get('imerg_completion_manifest_sha256','')
        import re
        if not isinstance(manifest_sha,str) or not re.fullmatch('[0-9a-f]{64}',manifest_sha):
            raise ValueError('Pinned completion-manifest SHA required')
        expected=authorization_bindings(protocol,manifest_sha)
        if set(value)!=set(expected)|{'created_utc','researcher_request_sha256'}:
            raise PermissionError('Exact independent execution authorization schema required')
        if any(value.get(k)!=v for k,v in expected.items()):raise PermissionError('Execution authorization binding mismatch')
        if (value['FINAL_TEST_CATALOGUE_AUTHORIZED'] is not True
                or value['FINAL_TEST_2025_AUTHORIZED'] is not False
                or value['completion_manifest_metadata_path_exception_approved'] is not True):
            raise PermissionError('Explicit researcher catalogue-only scope required')
        if not re.fullmatch('[0-9a-f]{64}',value['researcher_request_sha256']):raise ValueError('Researcher request SHA required')
        utc(value['created_utc'])
        head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=REPO_ROOT).decode().strip()
        if head!=BASE:raise PermissionError('Authorized execution baseline changed')
        return cls(value,expected_sha,_EXECUTION_SEAL)
    def require_catalogue(self,*,allow_fixture=False):
        if (self._seal is not _EXECUTION_SEAL or self.fixture
                or self.value.get('scope')!=gate.CATALOGUE_SCOPE
                or self.value.get('FINAL_TEST_CATALOGUE_AUTHORIZED') is not True
                or self.value.get('FINAL_TEST_2025_AUTHORIZED') is not False):
            raise PermissionError('Verified independent catalogue-only authority required')
    def require_final(self):raise PermissionError('Catalogue-only authority cannot authorize FINAL loading or inference')

class ExecutionSourceGuard(gate.CatalogueSourceGuard):
    def __init__(self,authority):
        super().__init__(authority);self.metadata_open_events=0
    def check(self,path,mode='r',flags=0,*,directory=False):
        if isinstance(path,(str,bytes,os.PathLike)):
            p=PureWindowsPath(os.fsdecode(path))
            if p.is_relative_to(METADATA_MANIFEST.parent):
                writing=any(c in str(mode or '') for c in 'wax+') or bool(flags&(os.O_WRONLY|os.O_RDWR|os.O_CREAT|os.O_TRUNC))
                if p!=METADATA_MANIFEST or p!=self.manifest or writing or directory or '..' in p.parts:
                    raise PermissionError('Only the pinned existing metadata manifest is authorized read-only')
                self.metadata_open_events+=1;return
            raw_parent=gate.legacy.IROOT.parent
            if p.is_relative_to(raw_parent) and not p.is_relative_to(gate.legacy.IROOT):
                raise PermissionError('Other raw data roots are outside catalogue-only scope')
        return super().check(path,mode,flags,directory=directory)

class ExecutionBackend(frozen_backend.RealCatalogueBackend):
    def __init__(self,protocol,authority,staging_root,progress_root):
        authority.require_catalogue()
        self.progress_root=gate.safe_artifact_path(progress_root)
        self.slots_completed=0;self.started=time.perf_counter()
        super().__init__(protocol,authority,staging_root)
    def _original_location(self,source,root):
        if PureWindowsPath(str(source))==METADATA_MANIFEST:
            self.authority.require_catalogue()
            if (self.authority.value['completion_manifest_metadata_path_exception_approved'] is not True
                    or self.authority.value['imerg_completion_manifest_path']!=str(METADATA_MANIFEST)
                    or source.resolve(strict=True)!=Path(str(METADATA_MANIFEST))):
                raise ValueError('Pinned metadata manifest location changed')
            return
        return frozen_backend.RealCatalogueBackend._original_location(source,root)
    def probe(self,index,start):
        row=super().probe(index,start)
        self.slots_completed=index+1
        if self.slots_completed%48==0 or self.slots_completed==gate.COUNT:
            value={'status':'CATALOGUE_QC_RUNNING','candidate_slots_completed':self.slots_completed,
                'scheduled_candidate_slots':gate.COUNT,'last_window_start':row['window_start'],
                'elapsed_seconds':time.perf_counter()-self.started,
                'raw_access_telemetry':gate.sanitized_telemetry(dict(self.telemetry)),
                '2025_FINAL_TEST_EXECUTED':False,'2025_MODEL_INFERENCE_SCENES':0,
                '2025_FINAL_TEST_METRICS_COMPUTED':False,'2025_TARGET_OUTCOME_SUMMARIES_EXPOSED':False,
                'updated_utc':gate.now()}
            target=self.progress_root/'progress.json';temporary=self.progress_root/'progress.owned.tmp'
            with temporary.open('x',encoding='utf-8',newline='\n') as stream:
                json.dump(value,stream,ensure_ascii=False,indent=2,allow_nan=False);stream.write('\n')
            os.replace(temporary,target)
            print(json.dumps({'status':'CATALOGUE_QC_PROGRESS','slots_completed':self.slots_completed,
                'elapsed_seconds':value['elapsed_seconds']},ensure_ascii=True),flush=True)
        return row

def verify_history(history):
    for name,reference in history.items():
        data=(REPO_ROOT/name).read_bytes()
        if (hashlib.sha256(data).hexdigest()!=reference['sha256']
                or hashlib.sha1(b'blob '+str(len(data)).encode()+b'\0'+data).hexdigest()!=reference['git_blob_sha1']):
            raise ValueError('Historical artifact changed')
    return len(history)

def verify_frozen_artifacts(output,authority):
    output=gate.safe_artifact_path(output)
    candidates=gate.read_csv(output/'b0_2025_final_test_candidate_catalogue_v1.csv')
    population=gate.read_csv(output/'b0_2025_final_test_population_manifest_v1.csv',gate.POPULATION_COLUMNS)
    eligible=gate.validate_manifests(candidates,population)
    freeze=gate.read(output/'catalogue_freeze_record.json')
    wanted_keys={'version','status','scope','protocol_sha256','implementation_sha256','catalogue_authorization_sha256',
        'candidate_catalogue_sha256','eligible_population_manifest_sha256','candidate_count','eligible_count','rejected_count',
        'rejection_reason_counts','2025_CATALOGUE_QC_ACCESS','2025_FINAL_TEST_EXECUTED','2025_MODEL_INFERENCE_SCENES',
        '2025_FINAL_TEST_METRICS_COMPUTED','2025_TARGET_OUTCOME_SUMMARIES_EXPOSED','raw_access_telemetry','fixture_only','freeze_completed_utc'}
    if set(freeze)!=wanted_keys:raise ValueError('Freeze record exact outcome-free schema required')
    counts=dict(sorted(Counter(reason for row in candidates for reason in row['rejection_reason'].split(';') if reason).items()))
    expected={'version':'v1.1','status':'CATALOGUE_FROZEN','scope':gate.CATALOGUE_SCOPE,
        'protocol_sha256':gate.PROTOCOL_SHA,'implementation_sha256':gate.implementation_hashes(),
        'catalogue_authorization_sha256':authority.sha256,'candidate_count':gate.COUNT,
        'eligible_count':len(eligible),'rejected_count':gate.COUNT-len(eligible),'rejection_reason_counts':counts,
        '2025_CATALOGUE_QC_ACCESS':True,'2025_FINAL_TEST_EXECUTED':False,'2025_MODEL_INFERENCE_SCENES':0,
        '2025_FINAL_TEST_METRICS_COMPUTED':False,'2025_TARGET_OUTCOME_SUMMARIES_EXPOSED':False,'fixture_only':False,
        'candidate_catalogue_sha256':sha256(output/'b0_2025_final_test_candidate_catalogue_v1.csv'),
        'eligible_population_manifest_sha256':sha256(output/'b0_2025_final_test_population_manifest_v1.csv')}
    if any(freeze.get(k)!=v for k,v in expected.items()):raise ValueError('Frozen catalogue reconciliation failed')
    for key in ('2025_CATALOGUE_QC_ACCESS','2025_FINAL_TEST_EXECUTED','2025_FINAL_TEST_METRICS_COMPUTED',
                '2025_TARGET_OUTCOME_SUMMARIES_EXPOSED','fixture_only'):
        if type(freeze[key]) is not bool:raise ValueError('Freeze boolean required')
    for key in ('candidate_count','eligible_count','rejected_count','2025_MODEL_INFERENCE_SCENES'):
        if type(freeze[key]) is not int:raise ValueError('Freeze integer required')
    utc(freeze['freeze_completed_utc'])
    telemetry=gate.sanitized_telemetry(freeze['raw_access_telemetry'])
    if (telemetry.get('2025_PIXELS_READ')!=telemetry.get('b13_pixel_values_read',0)+telemetry.get('imerg_pixel_values_read',0)
            or telemetry.get('cleanup_success') is not True):raise ValueError('Raw-access telemetry or staging cleanup mismatch')
    return freeze,sha256(output/'catalogue_freeze_record.json')

def execute(args):
    # No raw source or staging access precedes exact independent authorization.
    authority=ExecutionAuthority.load(args.authorization,args.authorization_sha256)
    authority.require_catalogue();protocol=gate.load_protocol()
    run=gate.safe_artifact_path(args.run_directory)
    if not (run/'preparation_manifest.json').is_file() or (run/'final_status.json').exists() or (run/'failure.json').exists():
        raise ValueError('Prepared new run required; existing final/failure records cannot be overwritten')
    preparation=gate.read(run/'preparation_manifest.json')
    if preparation['baseline_commit']!=BASE or preparation['researcher_request_sha256']!=authority.value['researcher_request_sha256']:
        raise PermissionError('Prepared run authorization mismatch')
    staging=execution_staging_path(args.staging_root,run)
    history=gate.read(run/'history_before.json');verify_history(history)
    logs=run/'logs';logs.mkdir(exist_ok=False)
    output=run/'catalogue';backend=None;source_guard=ExecutionSourceGuard(authority)
    try:
        with gate.CatalogueOnlyGuard() as model_guard,source_guard:
            for root in (gate.legacy.HROOT,gate.legacy.IROOT):
                if not Path(str(root)).is_dir():raise OSError('FROZEN_SOURCE_ROOT_UNAVAILABLE')
            backend=ExecutionBackend(protocol,authority,staging,logs)
            gate.save(run/'execution_manifest.json',{'baseline_commit':BASE,'protocol_sha256':gate.PROTOCOL_SHA,
                'catalogue_authorization_sha256':authority.sha256,'implementation_sha256':gate.implementation_hashes(),
                'execution_implementation_sha256':execution_hashes(),'source_roots':dict(authority.value['source_roots']),
                'imerg_completion_manifest_path':str(METADATA_MANIFEST),
                'imerg_completion_manifest_sha256':authority.value['imerg_completion_manifest_sha256'],
                'created_utc':gate.now(),'scope':gate.CATALOGUE_SCOPE})
            gate.build_catalogue(authority,backend,output)
            freeze,freeze_sha=verify_frozen_artifacts(output,authority)
            if sha256(Path(str(METADATA_MANIFEST)))!=authority.value['imerg_completion_manifest_sha256']:
                raise ValueError('Pinned completion manifest changed during QC')
            if sha256(args.authorization)!=authority.sha256 or execution_hashes()!=dict(authority.value['execution_implementation_sha256']):
                raise ValueError('Execution authorization or adapter changed')
            preserved=verify_history(history)
            if model_guard.attempts or backend.staging._owned:raise ValueError('Prohibited operation or retained staging copy')
            gate.save(run/'final_status.json',{'FINAL_TEST_PROTOCOL_V1_1_FROZEN':True,
                'FINAL_TEST_CATALOGUE_AUTHORIZED':True,'REAL_2025_CANDIDATE_CATALOGUE':'FROZEN',
                'REAL_2025_CANDIDATE_COUNT':gate.COUNT,'REAL_2025_ELIGIBLE_COUNT':freeze['eligible_count'],
                'REAL_2025_REJECTED_COUNT':freeze['rejected_count'],
                'CANDIDATE_CATALOGUE_SHA256':freeze['candidate_catalogue_sha256'],
                'ELIGIBLE_POPULATION_MANIFEST_SHA256':freeze['eligible_population_manifest_sha256'],
                'CATALOGUE_FREEZE_RECORD_SHA256':freeze_sha,
                '2025_CATALOGUE_QC_ACCESS':source_guard.qc_access,'FINAL_TEST_2025_AUTHORIZED':False,
                'FINAL_TEST_2025_EXECUTED':False,'2025_FINAL_TEST_EXECUTED':False,'2025_MODEL_INFERENCE_SCENES':0,
                '2025_FINAL_TEST_METRICS_COMPUTED':False,'2025_TARGET_OUTCOME_SUMMARIES_EXPOSED':False,
                'MODEL_PARAMETERS_UPDATED':False,'OPTIMIZER_STEPS':0,'BACKWARD_CALLS':0,
                'FINAL_CHECKPOINT_LOADS':0,'MODEL_FORWARD_CALLS':0,
                'FINAL_identity_record_sha256_unchanged':True,'FINAL_actual_file_sha256_recomputed':False,
                'FINAL_actual_file_sha256_status':'NOT_RECOMPUTED_RESEARCHER_APPROVED_IDENTITY_RECORD_ONLY',
                'frozen_FINAL_sha256_identity_value':gate.legacy.FINAL_SHA,
                'historical_artifacts_unchanged':preserved,'source_guard_raw_open_events':source_guard.raw_open_events,
                'metadata_manifest_open_events':source_guard.metadata_open_events,
                'raw_access_telemetry':gate.sanitized_telemetry(dict(backend.telemetry)),
                'second_stage_researcher_authorization_required':True,'completed_utc':gate.now()})
            print(json.dumps({'status':'CATALOGUE_FROZEN_STOP','candidate_count':gate.COUNT,
                'eligible_count':freeze['eligible_count'],'rejected_count':freeze['rejected_count'],
                'freeze_record_sha256':freeze_sha},ensure_ascii=True),flush=True)
        return run
    except Exception as error:
        telemetry=gate.sanitized_telemetry(dict(getattr(backend,'telemetry',{})))
        gate.save(run/'failure.json',{'status':'CATALOGUE_STOPPED','error_type':type(error).__name__,
            'candidate_slots_completed':getattr(backend,'slots_completed',0),
            '2025_CATALOGUE_QC_ACCESS':source_guard.qc_access,
            'source_guard_raw_open_events':source_guard.raw_open_events,'metadata_manifest_open_events':source_guard.metadata_open_events,
            'raw_access_telemetry':telemetry,'FINAL_TEST_2025_AUTHORIZED':False,'FINAL_TEST_2025_EXECUTED':False,
            '2025_MODEL_INFERENCE_SCENES':0,'2025_FINAL_TEST_METRICS_COMPUTED':False,
            '2025_TARGET_OUTCOME_SUMMARIES_EXPOSED':False,'FINAL_CHECKPOINT_LOADS':0,'MODEL_FORWARD_CALLS':0,
            'OPTIMIZER_STEPS':0,'BACKWARD_CALLS':0,'failed_utc':gate.now()})
        raise
