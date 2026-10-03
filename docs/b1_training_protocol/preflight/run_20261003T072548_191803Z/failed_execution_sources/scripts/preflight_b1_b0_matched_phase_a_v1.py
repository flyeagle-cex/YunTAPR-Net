"""Authorized temporary real-source ENGINEERING_ONLY preflight, never formal fitting."""
from pathlib import Path
import argparse,datetime,gc,importlib.metadata,json,os,sys,time,traceback,weakref
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT/'src'),str(ROOT/'scripts')]
import torch,numpy as np
from torch.utils.data import DataLoader
from unittest.mock import patch
from yuntapr.contracts.loader import sha256
from yuntapr.models.b1 import paired_models
from yuntapr.training.paired_phase_a import *
from yuntapr.training.phase_a_protocol import seed_reproducibility
from yuntapr.data.dataset_b1 import *
from yuntapr.spatial.sp04_mapping import load_sp04
from yuntapr.data.masks import read_frozen_yunnan_mask
from paired_phase_a_entry import execute_update
from train_b0_phase_b_finalfit_v1 import environment


def save(path,obj):
    with Path(path).open('x',encoding='utf-8',newline='\n') as f:json.dump(obj,f,ensure_ascii=False,indent=2,allow_nan=False,default=str);f.write('\n')


def clean():gc.collect();torch.cuda.empty_cache();torch.cuda.synchronize()


def fresh(kind):
    a,b,proof=paired_models();model=a if kind=='B0_MATCHED' else b
    del a,b;gc.collect();return model.cuda(),proof


def memory_case(kind,items,training,iterations=1,forced=None):
    clean();free_before,total=torch.cuda.mem_get_info();reserved_before=torch.cuda.memory_reserved();torch.cuda.reset_peak_memory_stats()
    model=optimizer=batch=out=None;step_count=0;records=[];start=time.perf_counter();refs=[]
    try:
        model,initial=fresh(kind);refs.append(weakref.ref(model));batch=make_batch(items)
        if training:
            model.train();optimizer,groups=optimizer_for(model,kind);refs.append(weakref.ref(optimizer))
            for i in range(iterations):
                metrics,out=execute_update(model,optimizer,batch,forced or i+1);step_count+=1;records.append(metrics);del out;out=None
        else:
            model.eval();before=state_digest(model.state_dict())
            with torch.inference_mode():
                for _ in range(iterations):out,loss=forward_loss(model,batch);del out,loss;out=None
            if state_digest(model.state_dict())!=before:raise AssertionError('Inference updated parameters')
        torch.cuda.synchronize();peak_alloc=torch.cuda.max_memory_allocated();peak_res=torch.cuda.max_memory_reserved();free_after,_=torch.cuda.mem_get_info()
        estimated=min(free_after,free_before-max(0,peak_res-reserved_before))
        safe=lambda margin:peak_res<=(1-margin)*total and estimated>=margin*total
        result={'kind':kind,'scope':'ENGINEERING_ONLY','batch':len(items),'training':training,'iterations':iterations,
                'warmup_iterations':2 if iterations==7 else 0,'measured_iterations':5 if iterations==7 else iterations,
                'peak_allocated_bytes':peak_alloc,'peak_reserved_bytes':peak_res,'total_bytes':total,
                'free_before_bytes':free_before,'free_after_bytes':free_after,'estimated_min_free_bytes':estimated,
                'safe_15_percent':safe(.15),'recommended_20_percent':safe(.2),'wall_seconds':time.perf_counter()-start,
                'engineering_optimizer_steps':step_count,'FORMAL_OPTIMIZER_STEPS':0,'updates':records,'status':'PASS',
                'initial_model_sha256':initial[kind+'_INITIAL_MODEL_SHA256' if kind=='B1' else 'B0_MATCHED_INITIAL_MODEL_SHA256']}
    except torch.cuda.OutOfMemoryError as exc:
        result={'kind':kind,'scope':'ENGINEERING_ONLY','batch':len(items),'training':training,'status':'CUDA_OOM',
                'error':str(exc),'engineering_optimizer_steps':step_count,'FORMAL_OPTIMIZER_STEPS':0,
                'recommended_20_percent':False,'safe_15_percent':False,
                'peak_allocated_bytes':torch.cuda.max_memory_allocated(),'peak_reserved_bytes':torch.cuda.max_memory_reserved()}
    finally:
        model=optimizer=batch=out=None;clean()
    if any(r() is not None for r in refs):raise AssertionError('Temporary model/optimizer was not destroyed')
    result['temporary_model_optimizer_destroyed']=True
    return result


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,required=True);parser.add_argument('--staging',type=Path,required=True)
    args=parser.parse_args();run=args.output;run.mkdir(parents=True,exist_ok=True)
    if any((run/n).exists() for n in ('gpu_feasibility.json','engineering_preflight.json')):raise FileExistsError('Immutable preflight artifacts already exist')
    seed_reproducibility();install_source_guard();env=environment();save(run/'environment.json',env)
    old=yaml.safe_load((ROOT/'config/training/phase_a_training_protocol_v1.yaml').read_text())
    ids={k:v for k,v in old['identity'].items() if k in ('scientific_contract_v1.1','engineering_v4','SP04_mapping','SP04_manifest','yunnan_mask','prior_gpu_manifest')}
    ids['normalization']={'path':str(FREEZE/'normalization_b1_2023_shared_v1.json'),'sha256':SCALER_SHA}
    for (kind,year),pin in PINS.items():
        leaf='b1' if kind=='B1' else 'b0_matched_control'
        ids[f'{kind}_{year}']={'path':str(FREEZE/f'{leaf}_{year}_formal_manifest.csv'),'sha256':pin}
    for ref in ids.values():
        p=Path(ref['path']);p=p if p.is_absolute() else ROOT/p;pinned(p,ref['sha256'])
    records={(k,y):load_records(k,y) for k in ('B0_MATCHED','B1') for y in (2023,2024)}
    same={}
    for y in (2023,2024):
        keys=('sample_id','window_start','analysis_time','imerg_day_path','imerg_index','imerg_sha256')
        left=[[r[k] for k in keys] for r in records['B0_MATCHED',y]];right=[[r[k] for k in keys] for r in records['B1',y]]
        assert left==right;same[str(y)]={'scenes':len(left),'sample_and_target_identity_sha256':state_digest(left),'identical':True}
    save(run/'identity_preflight.json',{'identity':ids,'paired_samples':same,'2025_RAW_ACCESS':0,'normalization_refit':False})
    with patch('torch.load',side_effect=RuntimeError('Historical checkpoint loading forbidden in engineering preflight')):
        a,b,proof=paired_models();a2,b2,proof2=paired_models();assert proof==proof2
        proof['fresh_deterministic_replay_verified']=True;save(run/'paired_initialization_manifest.json',proof)
        groups={k:optimizer_for(m,k)[1] for k,m in [('B0_MATCHED',a),('B1',b)]};save(run/'optimizer_group_verification.json',groups)
        del a,b,a2,b2;clean()
        # Verify all 50 epochs by metadata, without any model updates or source reads.
        orderproof=[]
        for ep in range(1,51):
            c=EpochCoverage(ep)
            for ix in c.plan:c.add(ix,len(ix)*3430)
            x=c.complete();orderproof.append({'epoch':ep,**x,'same_B0_B1_order':True})
        save(run/'sample_order_verification.json',{'epochs':orderproof,'formal_training_executed':False})
        lrs=np.asarray([lr_for_update(u,steps_per_epoch=STEPS) for u in range(1,U+1)])
        assert lrs[W-1]==1e-4 and lrs[-1]==1e-6 and (lrs[:W]>0).all() and (lrs[W:]>=1e-6).all()
        save(run/'scheduler_verification.json',{'updates_checked':U,'u1':float(lrs[0]),'uW':float(lrs[W-1]),'uW1':float(lrs[W]),'uU':float(lrs[-1]),'W':W,'U':U,'min_lr_lower_bound':'COSINE_ONLY','pass':True})
        mapping=load_sp04();mask=read_frozen_yunnan_mask(Path(ids['yunnan_mask']['path']),mapping);frames=load_frames()
        datasets={}
        for k in ('B0_MATCHED','B1'):
            # 32 distinct real 2023 Train identities plus two 2024 fixture identities.
            datasets[k]=TemporalDataset(k,records[k,2023][:32],frames,mapping,mask,args.staging/k)
        loaded={};loaderproof={};start=time.perf_counter()
        for kind,dataset in datasets.items():
            initial_children=set(args.staging.rglob('*.nc')) if args.staging.exists() else set()
            result=[];worker_peaks=[]
            loader=DataLoader(dataset,batch_size=2,shuffle=False,drop_last=False,num_workers=2,pin_memory=False,persistent_workers=False,prefetch_factor=1,worker_init_fn=worker_init,collate_fn=collate)
            for batch in loader:
                result.extend(batch)
                import psutil
                worker_peaks.append(sum(p.memory_info().rss for p in psutil.Process().children(recursive=True) if p.is_running()))
            del loader;gc.collect();loaded[kind]=result
            assert [r['index'] for r in result]==list(range(32)) and len({r['worker_pid'] for r in result})==2
            assert not set(args.staging.rglob('*.nc'))-initial_children
            loaderproof[kind]={'scenes':32,'ordered_sample_ids':[r['sample_id'] for r in result],
                               'workers':sorted({r['worker_pid'] for r in result}),'worker_peak_rss_bytes':max(worker_peaks),
                               'source_reads':sum(len(r['staging']) for r in result),'staging_records':[q for r in result for q in r['staging']],
                               'cleanup_success':True,'status':'PASS'}
        for m,t in zip(loaded['B0_MATCHED'],loaded['B1']):
            assert m['sample_id']==t['sample_id'] and np.array_equal(m['x'][0],t['x'][5]) and np.array_equal(m['y'],t['y'],equal_nan=True)
        validations={}
        for k in ('B0_MATCHED','B1'):
            ds=TemporalDataset(k,records[k,2024][:2],frames,mapping,mask,args.staging/(k+'_validation'))
            validations[k]=[ds[i] for i in range(2)]
        for m,t in zip(validations['B0_MATCHED'],validations['B1']):assert np.array_equal(m['y'],t['y'],equal_nan=True) and np.array_equal(m['x'][0],t['x'][5])
        save(run/'loader_preflight.json',{'configuration':{'num_workers':2,'pin_memory':False,'persistent_workers':False,'prefetch_factor':1},
              'results':loaderproof,'validation_fixtures':[{k:v for k,v in r.items() if k not in ('x','y','valid','yunnan')} for r in validations['B1']],
              'same_target_and_latest_normalized_B13':True,'wall_seconds':time.perf_counter()-start,'2025_RAW_ACCESS':0,'status':'PASS'})
        feasibility={k:memory_case(k,loaded[k][:2],True,7) for k in ('B0_MATCHED','B1')}
        if not all(v['status']=='PASS' and v['recommended_20_percent'] for v in feasibility.values()):
            fallback=memory_case('B1',loaded['B1'][:1],True,2)
            save(run/'gpu_feasibility.json',{'training':feasibility,'fallback_physical1_accumulation2_component_checks':fallback,'fallback_frozen':False,'status':'RESEARCHER_DECISION_REQUIRED'})
            raise RuntimeError('Batch2 safety/headroom not closed; fallback must not be auto-frozen')
        # Find the actual maximum common integer batch under the inherited 20% rule.
        valcases={};
        def check(n):
            if n not in valcases:valcases[n]={k:memory_case(k,loaded[k][:n],False,2) for k in ('B0_MATCHED','B1')}
            return all(v['status']=='PASS' and v['recommended_20_percent'] for v in valcases[n].values())
        low=0;high=2
        while high<=32 and check(high):low=high;high*=2
        if high>32:raise RuntimeError('Validation safe upper bound unresolved at 32; no arbitrary maximum frozen')
        while high-low>1:
            mid=(low+high)//2
            if check(mid):low=mid
            else:high=mid
        if low<1:raise RuntimeError('No common safe validation batch')
        save(run/'gpu_feasibility.json',{'training':feasibility,'validation_cases':valcases,'common_validation_batch':low,
             'first_unsafe_common_batch':high,'maximum_common_integer_batch_verified':True,
             'safety_rule':'peak_reserved <= (1-margin)*total AND min(free_after,free_before-(peak_reserved-reserved_before)) >= margin*total',
             'minimum_margin':.15,'freeze_recommendation_margin':.20,'status':'PASS'})
        cases=[]
        for label,k,n,u in [('A','B0_MATCHED',2,1),('B','B1',2,1),('C','B0_MATCHED',1,STEPS),('D','B1',1,STEPS)]:
            case=memory_case(k,loaded[k][:n],True,1,u);case['case']=label
            assert case['status']=='PASS' and case['updates'][0]['actual_denominator']==n*3430
            if n==1:assert case['updates'][0]['LR']==1e-4
            cases.append(case)
        save(run/'engineering_preflight.json',{'scope':'ENGINEERING_ONLY','cases':cases,
             'engineering_optimizer_steps':sum(v['engineering_optimizer_steps'] for v in feasibility.values())+sum(v['engineering_optimizer_steps'] for v in cases),
             'FORMAL_OPTIMIZER_STEPS':0,'formal_checkpoint_written':False,'source_cleanup_success':True,
             '2025_PIXELS_READ':0,'2025_MODEL_INFERENCE_SCENES':0,'all_temporary_models_destroyed':True,'status':'PASS'})
        body=protocol_body(low,ids);config=ROOT/CONFIG;config.parent.mkdir(parents=True,exist_ok=True)
        with config.open('x',encoding='utf-8',newline='\n') as f:yaml.safe_dump(body,f,sort_keys=False,allow_unicode=True)
        registry={'protocol_path':CONFIG.as_posix(),'protocol_sha256':sha256(config),'run_id':run.name,
                  'GPU_batch2_and_loader_and_paired_initialization_pass':True,'formal_training_authorized':False}
        save(ROOT/'config/training/b1_b0_matched_phase_a_freeze_registry_v1.json',registry)
        save(run/'protocol_manifest.json',{**registry,'identity':ids,'PHYSICAL_BATCH':2,'ACCUMULATION':1,'STEPS_PER_EPOCH':STEPS,'W':W,'U':U,'validation_batch':low})
        save(run/'PAIRWISE_FAIRNESS_MANIFEST.json',{'paired_sample_identity':same,'normalization_sha256':SCALER_SHA,
             'same_loss_optimizer_scheduler_permutation_seed_earlystop_BEST_metrics':True,'difference':'INPUT_INFORMATION_DIFFERENCE',
             'B0_MATCHED':'latest B13 only','B1':'six causal B13 slots','parameter_delta':2400,'historical_B0_immutable':True})
    contract=RunnerContract.load();save(run/'runner_manifest.json',{'protocol_sha256':contract.protocol_sha256,'implementation_hashes':contract.code_hashes,
               'entrypoints':['scripts/train_b1_phase_a_v1.py','scripts/train_b0_matched_phase_a_v1.py'],
               'formal_training_authorized':False,'2025_RAW_ACCESS':0,'status':'IMPLEMENTED_PREFLIGHT_PENDING_TEST_CLOSURE'})
    print(json.dumps({'run_id':run.name,'physical_batch':2,'validation_batch':low,'engineering_optimizer_steps':18,'protocol_sha256':contract.protocol_sha256}),flush=True)


if __name__=='__main__':
    try:main()
    except Exception:
        stamp=datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%S_%fZ')
        try:
            path=Path(sys.argv[sys.argv.index('--output')+1]);save(path/('failure_'+stamp+'.json'),{'status':'PREFLIGHT_FAILED','traceback':traceback.format_exc(),'formal_optimizer_steps':0,'2025_pixels_read':0})
        finally:raise
