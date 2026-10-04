"""Final Test execution after outcome-free catalogue freeze and separate authority.

This module is implemented now; no real Final Test execution is authorized.
"""
from pathlib import Path
import gc
import hashlib
import json
import uuid
import numpy as np
import torch
from yuntapr.evaluation import final_test_b0 as v1
from yuntapr.evaluation import catalogue_gate_b0 as gate
from yuntapr.data.dataset_b0 import B0Dataset,B0Record
from yuntapr.data.staging import BoundedEnglishStaging,StagedB13Reader,StagedIMERGReader
from yuntapr.data.sample_schema import utc
from yuntapr.data.masks import read_frozen_yunnan_mask
from yuntapr.spatial.sp04_mapping import load_sp04
from yuntapr.training.batch_contract import B0Batch
from yuntapr.training.phase_a_protocol import seed_reproducibility,state_digest
from yuntapr.contracts.loader import REPO_ROOT,sha256

def jsonable(value):
    if isinstance(value,np.ndarray):return jsonable(value.tolist())
    if isinstance(value,np.generic):return jsonable(value.item())
    if isinstance(value,dict):return {str(k):jsonable(v) for k,v in value.items()}
    if isinstance(value,(list,tuple)):return [jsonable(v) for v in value]
    if isinstance(value,float) and not np.isfinite(value):return None
    return value

def save(path,value):gate.save(path,jsonable(value))

def verify_final(protocol,authority):
    authority.require_final()
    if not isinstance(authority,gate.FinalAuthority):raise PermissionError('Verified second-stage authority required')
    return v1.verify_final(protocol)

class AuthorizedFinalDataset:
    def __init__(self,rows,mapping,yunnan,mask_path,stage_root,protocol,authority):
        authority.require_final()
        if not isinstance(authority,gate.FinalAuthority):raise PermissionError('Catalogue scope cannot construct inference dataset')
        approved=gate.validate_manifests([dict(r) for r in authority.candidates],
            [dict(r) for r in authority.population])
        if rows!=approved:raise ValueError('Inference dataset rows must equal the authorized frozen population snapshot')
        for row in rows:gate.strict_schema(row);gate.guard_paths(row)
        self.rows,self.mapping,self.yunnan,self.mask_path=rows,mapping,yunnan,mask_path
        self.authority=authority
        self.normalizer=v1.FinalTestNormalizer.load(protocol)
        self.staging=BoundedEnglishStaging(Path(stage_root),734003200,True,True)
        self.reader=StagedB13Reader(self.staging,mapping);self.ireader=StagedIMERGReader(self.staging,mapping)
    def __len__(self):return len(self.rows)
    def __getitem__(self,index):
        self.authority.require_final()
        row=self.rows[index];h,i=gate.guard_paths(row);before=len(self.staging.records)
        x,valid,observed=self.reader(h,utc(row['expected_nominal']))
        if (observed.nominal_time!=utc(row['selected_nominal']) or observed.obs_start!=utc(row['obs_start'])
                or observed.obs_end!=utc(row['obs_end']) or observed.obs_end>utc(row['analysis_time'])):
            raise ValueError('STOP: source timestamp identity changed')
        record=B0Record(row['sample_id'],utc(row['window_start']),(observed,),i,int(row['imerg_index']),
            'IMERG','V07','Final',True)
        def cached(path,nominal):
            if path!=h or nominal!=observed.nominal_time:raise ValueError('Unexpected source request')
            return x,valid,observed
        sample=B0Dataset([record],self.mapping,self.yunnan,cached,self.ireader,
            frozen_mask_path=self.mask_path,formal_supervised=True,normalizer=self.normalizer)[0]
        ops=self.staging.records[before:]
        if (len(ops)!=2 or [r.source_sha256 for r in ops]!=[row['b13_sha256'],row['imerg_sha256']]
                or [r.temporary_bytes for r in ops]!=[int(row['b13_bytes']),int(row['imerg_bytes'])]
                or any(not r.cleanup_success or not r.size_match or not r.sha256_match for r in ops)
                or self.staging._owned or int((sample.imerg_valid_mask&self.yunnan).sum())!=int(row['imerg_valid_yunnan_count'])):
            raise ValueError('STOP: fixed source SHA/size/QC/cleanup mismatch')
        # Outcome-derived reconciliation is created only inside authorized
        # inference execution; it never exists in either frozen catalogue CSV.
        rainy=int(((sample.y_imerg>np.float32(.1))&sample.imerg_valid_mask&self.yunnan).sum())
        del self.staging.records[before:]
        return sample,{'index':index,'sample_id':sample.sample_id,'obs_start':observed.obs_start.isoformat(),
            'obs_end':observed.obs_end.isoformat(),'date_created':observed.date_created.isoformat() if observed.date_created else '',
            'imerg_rain_yunnan_count':rainy,'count_scope':'AUTHORIZED_FINAL_TEST_RUNTIME_ONLY',
            'cleanup_success':True,'copy_seconds':sum(r.copy_seconds for r in ops),
            'read_seconds':sum(r.read_seconds for r in ops),'temporary_bytes_peak':max(r.temporary_bytes for r in ops)}

def formal(args):
    # No source existence/discovery, model/checkpoint reads or output creation
    # occur before both frozen manifests and the separate authorization verify.
    with v1.RawSourceGuard(preflight=True):
        p=gate.load_protocol()
        authority=gate.FinalAuthority.load(args.authorization,args.authorization_sha256,
            args.candidate_catalogue,args.eligible_population,args.catalogue_freeze_record)
        authority.require_final()
        candidates=[dict(row) for row in authority.candidates]
        population=[dict(row) for row in authority.population]
        rows=gate.validate_manifests(candidates,population)
    out=REPO_ROOT/'docs/final_test_b0/formal_v1_1'/('run_'+gate.now().replace('-','').replace(':','').replace('+0000','Z'))
    out.mkdir(parents=True,exist_ok=False)
    stage=Path(r'F:\pytorch\Research\stage0_himawari\cache\staging')/('final_v1_1_'+uuid.uuid4().hex)
    before=sha256(v1.FINAL_PATH)
    inference_scenes=0;completed_sample_values=0;metrics_started=False;raw_guard=v1.RawSourceGuard(preflight=False)
    try:
        with raw_guard,v1.FinalInferenceGuard(),torch.inference_mode():
            days={}
            for row in rows:
                h,i=gate.guard_paths(row)
                if h.stat().st_size!=int(row['b13_bytes']) or sha256(h)!=row['b13_sha256']:raise ValueError('STOP: B13 SHA/size failure')
                if str(i) not in days:
                    if i.stat().st_size!=int(row['imerg_bytes']) or sha256(i)!=row['imerg_sha256']:raise ValueError('STOP: IMERG SHA/size failure')
                    days[str(i)]=row['imerg_sha256']
                if days[str(i)]!=row['imerg_sha256']:raise ValueError('Conflicting IMERG day identity')
            seed_reproducibility();torch.set_num_threads(2)
            payload,identity=verify_final(p,authority);model=v1.load_inference_model(payload,'cuda');del payload;gc.collect()
            model_before=state_digest(model.state_dict());mapping=load_sp04()
            import yaml
            loss=yaml.safe_load((REPO_ROOT/p['identity']['frozen_loss_protocol']['path']).read_text(encoding='utf-8'))
            mask_path=Path(loss['identity']['yunnan_mask']['path']);yunnan=read_frozen_yunnan_mask(mask_path,mapping)
            dataset=AuthorizedFinalDataset(rows,mapping,yunnan,mask_path,stage,p,authority)
            acc=v1.FinalAccumulator(mapping.axes,[r['sample_id'] for r in rows],p['inherited_diagnostics'])
            save(out/'formal_manifest.json',{'protocol_sha256':gate.PROTOCOL_SHA,'authorization_sha256':authority.sha256,
                'implementation_sha256':gate.implementation_hashes(),'candidate_catalogue_sha256':authority.value['candidate_catalogue_sha256'],
                'eligible_population_manifest_sha256':authority.value['eligible_population_manifest_sha256'],
                'catalogue_freeze_record_sha256':authority.value['catalogue_freeze_record_sha256'],
                'candidate_count':len(candidates),'eligible_count':len(rows),'FINAL':identity,'created_utc':gate.now()})
            with (out/'runtime_ledger.jsonl').open('x',encoding='utf-8',newline='\n') as ledger:
                runtime_rain=0
                for first in range(0,len(dataset),2):
                    items=[dataset[j] for j in range(first,min(first+2,len(dataset)))]
                    samples,details=map(list,zip(*items));completed_sample_values+=len(samples)*(251001+10000)
                    batch=B0Batch.from_formal_samples(samples)
                    for name in ('x_b13','b13_valid_mask','y_imerg','imerg_valid_mask','yunnan_eval_mask'):
                        setattr(batch,name,getattr(batch,name).cuda())
                    with torch.autocast('cuda',dtype=torch.bfloat16):output=model(batch.x_b13,batch.b13_valid_mask)
                    inference_scenes+=len(samples);metrics_started=True
                    acc.add(output,batch,samples,details)
                    runtime_rain+=sum(r['imerg_rain_yunnan_count'] for r in details)
                    for detail in details:ledger.write(json.dumps(jsonable(detail),ensure_ascii=False)+'\n')
                    ledger.flush()
            metrics=acc.primary_report();diagnostics=acc.diagnostics(yunnan)
            if runtime_rain!=metrics['N_rain']:raise ValueError('Runtime-only rainy reconciliation failed')
            if state_digest(model.state_dict())!=model_before or sha256(v1.FINAL_PATH)!=before:raise ValueError('FINAL/model changed')
            save(out/'primary_metrics.json',metrics);save(out/'diagnostics.json',diagnostics)
            save(out/'final_status.json',{'FINAL_TEST_2025_AUTHORIZED':True,'FINAL_TEST_2025_EXECUTED':True,
                '2025_FINAL_TEST_EXECUTED':True,'2025_FINAL_TEST_METRICS_COMPUTED':True,
                '2025_MODEL_INFERENCE_SCENES':inference_scenes,'2025_TARGET_OUTCOME_SUMMARIES_EXPOSED':True,
                'raw_source_open_events':raw_guard.raw_open_events,
                'completed_sample_pixel_values_lower_bound':completed_sample_values,
                'raw_access_semantics':'completed sample values are a lower bound; failed/incomplete reads and source hashing are not counted as zero access',
                'MODEL_PARAMETERS_UPDATED':False,'OPTIMIZER_STEPS':0,'BACKWARD_CALLS':0,'completed_utc':gate.now()})
    except Exception as error:
        save(out/'failure.json',{'STOP_REQUIRED':True,'error_type':type(error).__name__,
            '2025_FINAL_TEST_EXECUTED':inference_scenes>0,'metrics_computation_started':metrics_started,
            '2025_RAW_SOURCE_ACCESS':raw_guard.raw_open_events>0,
            '2025_MODEL_INFERENCE_SCENES':inference_scenes,'raw_source_open_events':raw_guard.raw_open_events,
            'completed_sample_pixel_values_lower_bound':completed_sample_values,
            'exact_pixel_read_count':'NOT_MEASURED_NOT_ASSUMED_ZERO','failed_utc':gate.now()})
        raise
