"""B0 2025 Final Test protocol/preflight entrypoint; formal execution is gated off."""
from __future__ import annotations
import argparse
import csv
from datetime import datetime, timezone
import gc
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import traceback
import unittest
import uuid

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'src'),str(ROOT/'scripts')]
import numpy as np
import torch
from yuntapr.contracts.loader import sha256
from yuntapr.data.masks import read_frozen_yunnan_mask
from yuntapr.data.sample_schema import utc
from yuntapr.spatial.sp04_mapping import load_sp04
from yuntapr.training.batch_contract import B0Batch
from yuntapr.training.phase_a_protocol import seed_reproducibility,state_digest
from yuntapr.evaluation import final_test_b0 as f

PUBLIC=ROOT/'docs/final_test_b0/preflight'


def now(): return datetime.now(timezone.utc).isoformat()


def jsonable(value):
    if isinstance(value,np.ndarray): return jsonable(value.tolist())
    if isinstance(value,np.generic): return jsonable(value.item())
    if isinstance(value,dict): return {str(k):jsonable(v) for k,v in value.items()}
    if isinstance(value,(list,tuple)): return [jsonable(v) for v in value]
    if isinstance(value,float) and not np.isfinite(value): return None
    return value


def save(path,value):
    with Path(path).open('x',encoding='utf-8',newline='\n') as stream:
        json.dump(jsonable(value),stream,ensure_ascii=False,indent=2,allow_nan=False);stream.write('\n')


def baseline_inventory():
    pins={}
    entries=subprocess.check_output(['git','ls-tree','-r','-z',f.BASELINE],cwd=ROOT).decode().rstrip('\0').split('\0')
    for entry in entries:
        meta,name=entry.split('\t',1);data=(ROOT/name).read_bytes()
        if hashlib.sha1(b'blob '+str(len(data)).encode()+b'\0'+data).hexdigest()!=meta.split()[2]:
            raise ValueError('Baseline file modified: '+name)
        pins[name]=hashlib.sha256(data).hexdigest()
    return pins


def unit_tests(out):
    # Existing tests chosen here perform pure metric/guard checks; the historical
    # training/resume suites that construct optimizers/backpropagate are not run.
    existing=['tests.phase_a_protocol_v1.test_protocol_v1.ProtocolTests.test_grouped_ap_and_auc_ties',
        'tests.phase_a_protocol_v1.test_protocol_v1.ProtocolTests.test_global_validation_raw_numerators_unequal_partition',
        'tests.scientific_review.test_review_units.ReviewUnits']
    names=['tests.final_test_b0.test_final_test.ProtocolTests','tests.final_test_b0.test_final_test.GuardTests',
           'tests.final_test_b0.test_final_test.AccumulatorTests',*existing]
    results=[]
    with (out/'unit_test_results.txt').open('x',encoding='utf-8',newline='\n') as stream:
        for name in names:
            suite=unittest.defaultTestLoader.loadTestsFromName(name)
            result=unittest.TextTestRunner(stream=stream,verbosity=2).run(suite);stream.flush()
            record={'suite':name,'executed':result.testsRun,'failures':len(result.failures),
                'errors':len(result.errors),'skipped':len(result.skipped),'pass':result.wasSuccessful() and not result.skipped}
            results.append(record);print('PREFLIGHT_TEST '+json.dumps(record),flush=True)
            if not record['pass']: raise RuntimeError('Final Test preflight test failed: '+name)
    save(out/'unit_test_summary.json',{'status':'PASS','suites':results,'total_tests_executed':sum(r['executed'] for r in results),
        'actual_backward_calls':0,'actual_optimizer_creations':0,'actual_optimizer_steps':0,
        'scope':'synthetic/schema/blocked-operation guards and existing inference-only regressions'})


def inference_smoke(protocol,out):
    seed_reproducibility();torch.set_num_threads(2)
    if not torch.cuda.is_available(): raise RuntimeError('Approved CUDA environment required; no package/fallback change')
    with f.FinalInferenceGuard() as guard,torch.inference_mode():
        payload,identity=f.verify_final(protocol)
        model=f.load_inference_model(payload,'cuda');del payload;gc.collect()
        before=state_digest(model.state_dict())
        normalizer=f.FinalTestNormalizer.load(protocol,fixture=True)
        raw=np.full((501,501),270.,dtype=np.float32);valid=np.ones((501,501),dtype=bool)
        normalized=normalizer.transform(raw,valid,utc('2024-07-01T00:00:00+00:00'))
        x=torch.from_numpy(normalized[None,None]).cuda()
        mask=torch.ones_like(x,dtype=torch.bool)
        observed_raw={}
        handle=model.heads.quantile.register_forward_hook(lambda m,a,o:observed_raw.update(dtype=str(o.dtype)))
        torch.cuda.reset_peak_memory_stats()
        began=time.perf_counter()
        with torch.autocast('cuda',dtype=torch.bfloat16): output=model(x,mask)
        torch.cuda.synchronize();handle.remove()
        y=torch.full((1,1,100,100),float('nan'),device='cuda',dtype=torch.float32)
        use=torch.zeros_like(y,dtype=torch.bool);use[0,0,0,:4]=True
        y[0,0,0,:4]=torch.tensor([0.,.1,1.,20.],device='cuda')
        # Dates are synthetic schema labels only, not reads of 2025 observations.
        sample=type('Fixture',(),{'sample_id':'2025-03-01T00:00:00+00:00',
            'imerg_window_start':utc('2025-03-01T00:00:00+00:00'),
            'analysis_time':utc('2025-03-01T00:30:00+00:00')})()
        acc=f.FinalAccumulator(load_sp04().axes,[sample.sample_id],protocol['inherited_diagnostics'])
        acc.add(output,type('FixtureBatch',(),{'y_imerg':y,'imerg_valid_mask':use,'yunnan_eval_mask':use})(),[sample],[{'index':0}])
        metrics=acc.primary_report()
        after=state_digest(model.state_dict())
        if (before!=after or any(guard.attempts.values()) or model.training or any(p.requires_grad for p in model.parameters())
                or observed_raw.get('dtype')!='torch.float32' or output.conditional_quantiles_log.dtype!=torch.float64
                or output.conditional_quantiles_physical.dtype!=torch.float64):
            raise ValueError('Read-only FINAL inference precision/mutation guard failed')
        save(out/'final_identity_verification.json',identity)
        save(out/'synthetic_FINAL_forward_smoke.json',{'status':'PASS','scope':f.PREFLIGHT_SCOPE,
            'input':'synthetic constant 270 K; historical 2024 fixture normalization timestamp',
            'target':'synthetic [0, float32(0.1),1,20], four valid fixture cells only',
            'synthetic_2025_dates_are_schema_labels_only':True,'not_a_Final_Test_result':True,
            'model_state_sha256_before':before,'model_state_sha256_after':after,
            'raw_quantile_dtype':observed_raw['dtype'],'qlog_dtype':str(output.conditional_quantiles_log.dtype),
            'qphysical_dtype':str(output.conditional_quantiles_physical.dtype),'synthetic_metrics':metrics,
            'MODEL_PARAMETERS_UPDATED':False,'OPTIMIZER_STEPS':0,'BACKWARD_CALLS':0,'2025_PIXELS_READ':0,
            'prohibited_attempts_during_smoke':guard.attempts,'wall_seconds':time.perf_counter()-began,
            'GPU_peak_allocated_bytes':torch.cuda.max_memory_allocated(),'GPU_peak_reserved_bytes':torch.cuda.max_memory_reserved()})
        del model,output,x,y,acc;gc.collect();torch.cuda.empty_cache()


def preflight():
    out=PUBLIC/('run_'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S_%fZ'))
    out.mkdir(parents=True,exist_ok=False)
    final_before=sha256(f.FINAL_PATH)
    try:
        with f.RawSourceGuard(preflight=True) as source_guard:
            protocol=f.load_protocol();pins=baseline_inventory()
            save(out/'preflight_manifest.json',{'baseline_commit':f.BASELINE,'created_utc':now(),
                'protocol_sha256':f.PROTOCOL_SHA,'implementation_sha256':f.implementation_hashes(),
                'baseline_files_sha256':pins,'FINAL_sha256_before':final_before,
                'FINAL_TEST_2025_AUTHORIZED':False,'FINAL_TEST_2025_EXECUTED':False,'2025_PIXELS_READ':0})
            unit_tests(out)
            attempts_before_smoke=len(source_guard.prohibited_attempts)
            inference_smoke(protocol,out)
            if len(source_guard.prohibited_attempts)!=attempts_before_smoke or source_guard.raw_open_events:
                raise ValueError('Source guard violation during actual preflight inference')
            if sha256(f.FINAL_PATH)!=final_before or final_before!=f.FINAL_SHA or baseline_inventory()!=pins:
                raise ValueError('FINAL or historical artifact modified by preflight')
            os.environ['YUNTAPR_FINAL_TEST_PREFLIGHT_EVIDENCE']=str(out)
            with (out/'artifact_test_results.txt').open('x',encoding='utf-8',newline='\n') as stream:
                suite=unittest.defaultTestLoader.loadTestsFromName('tests.final_test_b0.test_final_test.PreflightArtifactTests')
                result=unittest.TextTestRunner(stream=stream,verbosity=2).run(suite)
                if not result.wasSuccessful() or result.skipped: raise RuntimeError('Preflight artifact tests failed')
            unit=f.read(out/'unit_test_summary.json')
            status={'FINAL_TEST_PROTOCOL_FROZEN':True,'FINAL_TEST_RUNNER_READY':True,
                'FINAL_TEST_2025_AUTHORIZED':False,'FINAL_TEST_2025_EXECUTED':False,'2025_PIXELS_READ':0,
                'MODEL_PARAMETERS_UPDATED':False,'OPTIMIZER_STEPS':0,'BACKWARD_CALLS':0,
                'FINAL_read_only_identity_provenance_PASS':True,'FINAL_SHA256_before':final_before,
                'FINAL_SHA256_after':sha256(f.FINAL_PATH),'BASELINE_FILES_UNCHANGED':len(pins),
                'TOTAL_TESTS_EXECUTED':unit['total_tests_executed']+result.testsRun,
                'NEW_PREFLIGHT_ARTIFACT_TESTS':result.testsRun,'TEST_FAILURES':0,'TEST_ERRORS':0,'TEST_SKIPS':0,
                'raw_sources_opened':source_guard.raw_open_events,
                'expected_raw_access_attempts_blocked_in_guard_tests':attempts_before_smoke,
                'run_id':out.name,'completed_utc':now()}
            save(out/'final_status.json',status)
        print('FINAL_TEST_PREFLIGHT_PASS '+json.dumps({'run_directory':str(out),**status}),flush=True)
    except Exception as error:
        save(out/'preflight_failure.json',{'error':repr(error),'traceback':traceback.format_exc(),
            'FINAL_TEST_RUNNER_READY':False,'FINAL_TEST_2025_AUTHORIZED':False,
            'FINAL_TEST_2025_EXECUTED':False,'2025_PIXELS_READ':0,'MODEL_PARAMETERS_UPDATED':False,
            'OPTIMIZER_STEPS':0,'BACKWARD_CALLS':0,'failed_utc':now()})
        raise


def formal(args):
    # This gate precedes source discovery, source existence checks and FINAL loading.
    with f.RawSourceGuard(preflight=True):
        protocol=f.load_protocol()
        authorization=f.FinalAuthorization.load(args.authorization,args.authorization_sha256,args.population)
        authorization.require()
        with Path(args.population).open(encoding='utf-8',newline='') as stream: catalogue=list(csv.DictReader(stream))
        eligible=f.validate_population(catalogue)
    out=ROOT/'docs/final_test_b0/formal'/('run_'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S_%fZ'))
    out.mkdir(parents=True,exist_ok=False)
    stage=Path(r'F:\pytorch\Research\stage0_himawari\cache\staging')/('final_test_'+out.name+'_'+uuid.uuid4().hex)
    before=sha256(f.FINAL_PATH)
    try:
        with f.RawSourceGuard(preflight=False) as raw_guard,f.FinalInferenceGuard() as inference_guard,torch.inference_mode():
            # Verify every pinned original before inference; runtime staging verifies again.
            source_identities=[];days={}
            for row in eligible:
                h,i=f.guard_source_paths(row)
                if h.stat().st_size!=int(row['b13_bytes']) or sha256(h)!=row['b13_sha256']:
                    raise ValueError('STOP: B13 source SHA/size failure')
                if str(i) not in days:
                    if i.stat().st_size!=int(row['imerg_bytes']) or sha256(i)!=row['imerg_sha256']:
                        raise ValueError('STOP: IMERG source SHA/size failure')
                    days[str(i)]=row['imerg_sha256']
                if days[str(i)]!=row['imerg_sha256']: raise ValueError('Conflicting IMERG day identity')
                source_identities.append([row['sample_id'],row['b13_sha256'],row['imerg_sha256']])
            seed_reproducibility();torch.set_num_threads(2)
            payload,identity=f.verify_final(protocol);model=f.load_inference_model(payload,'cuda');del payload
            model_before=state_digest(model.state_dict())
            mapping=load_sp04()
            loss_protocol=yaml_load(ROOT/protocol['identity']['frozen_loss_protocol']['path'])
            mask_path=Path(loss_protocol['identity']['yunnan_mask']['path'])
            yunnan=read_frozen_yunnan_mask(mask_path,mapping)
            dataset=f.FinalDataset(eligible,mapping,yunnan,mask_path,stage,protocol,authorization)
            acc=f.FinalAccumulator(mapping.axes,[r['sample_id'] for r in eligible],protocol['inherited_diagnostics'])
            save(out/'formal_manifest.json',{'scope':f.SCOPE,'authorization_sha256':authorization.sha256,
                'protocol_sha256':f.PROTOCOL_SHA,'implementation_sha256':f.implementation_hashes(),
                'candidate_slots':len(catalogue),'eligible_scenes':len(eligible),
                'source_identity_digest':state_digest(source_identities),'FINAL':identity,'created_utc':now()})
            with (out/'read_ledger.jsonl').open('x',encoding='utf-8',newline='\n') as ledger:
                for start in range(0,len(dataset),2):
                    items=[dataset[index] for index in range(start,min(start+2,len(dataset)))]
                    samples,details=map(list,zip(*items))
                    batch=B0Batch.from_formal_samples(samples)
                    for name in ('x_b13','b13_valid_mask','y_imerg','imerg_valid_mask','yunnan_eval_mask'):
                        setattr(batch,name,getattr(batch,name).cuda())
                    with torch.autocast('cuda',dtype=torch.bfloat16): output=model(batch.x_b13,batch.b13_valid_mask)
                    acc.add(output,batch,samples,details)
                    for detail in details: ledger.write(json.dumps(jsonable(detail),ensure_ascii=False)+'\n')
                    ledger.flush()
            primary=acc.primary_report();diagnostics=acc.diagnostics(yunnan)
            if state_digest(model.state_dict())!=model_before or any(inference_guard.attempts.values()) or sha256(f.FINAL_PATH)!=before:
                raise ValueError('STOP: FINAL/inference-model mutation or prohibited operation')
            save(out/'primary_metrics.json',primary);save(out/'diagnostics.json',diagnostics)
            save(out/'spatial_coordinate_identity.json',{'target_lat':mapping.axes['target_lat'],
                'target_lon':mapping.axes['target_lon'],'coordinate_hashes':{k:hashlib.sha256(mapping.axes[k].tobytes()).hexdigest()
                for k in ('target_lat','target_lon')},'latitude_ascending':True,'transpose':False,'flip':False})
            save(out/'final_status.json',{'FINAL_TEST_PROTOCOL_FROZEN':True,'FINAL_TEST_RUNNER_READY':True,
                'FINAL_TEST_2025_AUTHORIZED':True,'FINAL_TEST_2025_EXECUTED':True,'eligible_scenes':acc.seen,
                '2025_PIXELS_READ':acc.seen*(251001+10000),'MODEL_PARAMETERS_UPDATED':False,'OPTIMIZER_STEPS':0,
                'BACKWARD_CALLS':0,'FINAL_SHA256_after':sha256(f.FINAL_PATH),'reconciliation':acc.reconcile(),'completed_utc':now()})
    except Exception as error:
        save(out/'failure.json',{'error':repr(error),'traceback':traceback.format_exc(),'STOP_REQUIRED':True,'failed_utc':now()})
        raise


def yaml_load(path):
    import yaml
    return yaml.safe_load(Path(path).read_text(encoding='utf-8'))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=['preflight','run'])
    parser.add_argument('--authorization',type=Path)
    parser.add_argument('--authorization-sha256')
    parser.add_argument('--population',type=Path)
    args=parser.parse_args()
    if args.action=='preflight':
        if args.authorization or args.population: parser.error('Preflight uses fixtures only')
        preflight()
    else: formal(args)
