"""Independent mask-partitioned epoch-5 clone. No formal entrypoint or binary saves.

The only update function is the exact frozen paired_extended_v1.execute_update.
Any per-step identity/numeric mismatch stops immediately, without retry.
"""
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[2]
sys.path[:0]=[str(ROOT/'scripts'),str(ROOT/'src'),str(ROOT)]
from mask_partitioned_replay_v1 import common as c
import argparse
import csv
import gc
import json
import os
import time
import traceback
import numpy as np
import torch
from torch.utils.data import DataLoader,get_worker_info
import paired_extended_v1 as x
from mask_partitioned_replay_v1.observer import Observer
from mask_partitioned_replay_v1.summary import finalize
from quantile_autopsy_v1.close_readonly import source_journals
from yuntapr.models.b0 import B0Model
from yuntapr.training import paired_phase_a as frozen
from yuntapr.training import paired_phase_a_audit as a
from yuntapr.training.phase_a_protocol import seed_reproducibility,state_digest,capture_rng,restore_rng,lr_for_update
from yuntapr.training.formal_phase_b import compatible_states
from yuntapr.training.formal_phase_a import train_numerators
from yuntapr.spatial.sp04_mapping import load_sp04
from yuntapr.data.masks import read_frozen_yunnan_mask
from train_b0_phase_b_finalfit_v1 import environment

def numpy_stats(value):
    v=np.asarray(value,dtype=np.float64)
    if not np.isfinite(v).all():raise ValueError('Observed input not finite')
    return {'min':float(v.min()),'max':float(v.max()),'mean':float(v.mean()),
            'std':float(v.std(ddof=0)),'absmax':float(np.abs(v).max()),'all_finite':True}

class ReplayDataset(x.FinalFitDataset):
    def __getitem__(self,index):
        observations=[];original=x.normalize
        def observed_normalize(kelvin,scaler):
            before=numpy_stats(kelvin)
            normalized=original(kelvin,scaler)
            observations.append({'physical_K':before,'normalized':numpy_stats(normalized)})
            return normalized
        x.normalize=observed_normalize
        try:item=super().__getitem__(index)
        finally:x.normalize=original
        if len(observations)!=1:raise ValueError('B0 latest-slot only in overflow replay')
        item['engineering_input_observation']=observations[0]
        return item

def worker_init(worker_id):
    ds=get_worker_info().dataset
    cap=c.read(c.verify(ds.context['authorization']))
    if cap['operation']!=c.SCOPE or cap['formal_resume_authorized'] or cap['B1_authorized']:
        raise PermissionError('Isolated diagnostic authority required')
    install_checkpoint_guard(cap['checkpoint_identity']['absolute_local_path'],ds.context['public'])
    x.worker_init(worker_id)

def install_checkpoint_guard(last,run):
    last=Path(last).resolve();run=Path(run).resolve()
    protected=[Path(ref['path']).resolve() for ref in c.read(run/'historical_immutability_before.json')['files']]
    protected_set={os.path.normcase(str(p)) for p in protected}
    local_formal=Path(r'F:\pytorch\Research\outputs\formal_training').resolve()
    readonly_checkpoints={p for p in protected if p.suffix.lower() in ('.pt','.pth','.ckpt')}
    def guard(event,args):
        if event not in ('open','os.remove','os.rename','os.rmdir'):return
        paths=args[:1] if event=='open' else args[:2]
        for value in paths:
            if not isinstance(value,(str,bytes,os.PathLike)):continue
            p=Path(os.fsdecode(value)).resolve();key=os.path.normcase(str(p))
            mutate=event!='open'
            if event=='open':
                mode=args[1] if args[1] is not None else args[2]
                mutate=(any(k in mode for k in 'wa+') if isinstance(mode,str)
                        else isinstance(mode,int) and bool(mode&(os.O_WRONLY|os.O_RDWR|os.O_CREAT|os.O_TRUNC)))
            if mutate and (key in protected_set or p.is_relative_to(c.FAILED) or p.is_relative_to(local_formal)):
                raise PermissionError('Historical/formal artifacts permanently read-only')
            if event=='open' and p.suffix.lower() in ('.pt','.pth','.ckpt'):
                c.checkpoint_byte_read_policy(p,mutate,readonly_checkpoints)
    sys.addaudithook(guard)
    def no_save(*args,**kwargs):raise PermissionError('No resumable engineering checkpoint artifacts')
    torch.save=no_save
    original_load=torch.load
    def only_last_load(path,*args,**kwargs):
        c.checkpoint_deserialization_policy(path,last)
        return original_load(path,*args,**kwargs)
    torch.load=only_last_load

def source_plan(records,frames,plan):
    allowed={};ordered=[]
    for indices in plan:
        for index in indices:
            r=records[index];a.data.allowed_time(r['window_start'])
            nominal=(a.data.utc(r['analysis_time'])-x.timedelta(minutes=10)).isoformat()
            fr=frames[nominal];a.data.check_frame(fr,a.data.utc(r['analysis_time']))
            p=a.data.guard_source(a.data.H_ROOT/fr['relative_path'],'B13')
            if not p.is_file() or p.stat().st_size!=int(fr['source_bytes']):raise ValueError('Required B13 identity unavailable')
            allowed[str(p)]=int(fr['source_bytes'])
            target=a.data.guard_source(r['imerg_day_path'],'IMERG')
            if not target.is_file():raise ValueError('Required IMERG source unavailable')
            allowed[str(target)]=target.stat().st_size
            ordered.append(r['sample_id'])
    return list(allowed),{'required_file_count':len(allowed),'required_scenes':len(ordered),
        'ordered_sample_identity_sha256':state_digest(ordered),'all_files_exist_and_B13_sizes_match':True,
        'actual_source_SHA_verified_on_each_staged_read':True,
        'scope':'Only first 8626 epoch-5 batches; no extra prefetch batches or 2025'}

def replay(run):
    run=run.resolve();cap=c.read(run/'execution_scope.json')
    if cap['operation']!=c.SCOPE or cap['baseline']!=c.BASELINE or not cap['AUTHORIZED']:
        raise PermissionError('Exact diagnostic scope required')
    if (run/'mask_partitioned_replay_reconciliation.json').exists() or (run/'mask_partitioned_forward_observations.jsonl').exists():
        raise FileExistsError('No overwrite or automatic replay retry')
    c.verify(cap['researcher_authorization']);c.verify_snapshot(run)
    install_checkpoint_guard(cap['checkpoint_identity']['absolute_local_path'],run)
    # Frozen source inventory is unchanged; new diagnostic scripts are separate.
    expected=c.read(c.FAILED/'run_manifest.json')
    for path,wanted in expected['code_hashes'].items():
        if c.digest(ROOT/path)!=wanted:raise ValueError('Frozen production code changed: '+path)
    for key in ('authority','protocol','normalization','manifest'):c.verify(expected[key])
    actual_environment=environment()
    if actual_environment!=expected['environment']:raise ValueError('Replay environment changed')
    seed_reproducibility()
    contract=frozen.RunnerContract.load();frames=a.data.load_frames();records=c.csv_rows(expected['manifest']['path'])
    x.validate_records(records)
    order,full_plan=x.batch_plan(5);plan=full_plan[:c.FAIL_BATCH]
    reference=list(c.historical_updates(5))
    if len(reference)!=c.SUCCESS:raise ValueError('Successful historical update count changed')
    for j,row in enumerate(reference):
        if row['sample_ids']!=[records[i]['sample_id'] for i in plan[j]]:raise ValueError('Historical permutation mismatch')
    allowed,source_proof=source_plan(records,frames,plan)
    fw=a.RawFirewall(True,allowed,run/f'raw_access_parent_{os.getpid()}.jsonl');fw.install()
    mapping=load_sp04();mask=read_frozen_yunnan_mask(Path(contract.protocol['identity']['yunnan_mask']['path']),mapping)
    model=B0Model().cuda();optimizer,groups=frozen.optimizer_for(model,'B0_MATCHED')
    if groups!=expected['optimizer_groups']:raise ValueError('Optimizer group identity changed')
    payload=x.load_verified(cap['checkpoint_identity'],expected)
    if payload['model_state_dict_sha256']!=c.MODEL_SHA:raise ValueError('Trusted model logical SHA mismatch')
    compatible_states(payload,model,optimizer)
    prior_gate=c.read(c.PRIOR/'replay_identity_preflight.json')
    for key,ref in prior_gate['state_hashes'].items():
        if payload[key+'_sha256']!=ref['expected']:
            raise ValueError('Prior autopsy state provenance mismatch before application: '+key)
    # Provenance and state hashes were checked before state application.
    model.load_state_dict(payload['model_state_dict'],strict=True)
    optimizer.load_state_dict(payload['optimizer_state_dict']);restore_rng(payload['rng_states'])
    state_proof={name:{'expected':payload[name+'_sha256'],'actual':state_digest(value)} for name,value in
        [('model_state_dict',model.state_dict()),('optimizer_state_dict',optimizer.state_dict()),('rng_states',capture_rng())]}
    if any(p['expected']!=p['actual'] for p in state_proof.values()):raise ValueError('State restoration identity mismatch')
    gate={'utc':c.now(),'scope':c.SCOPE,'checkpoint_identity':cap['checkpoint_identity'],
        'provenance_verified_before_state_application':True,'state_hashes':state_proof,
        'scheduler':{'stateless':True,'restored_boundary':c.BOUNDARY,'last_lr':payload['last_applied_lr'],
                     'next_update':c.BOUNDARY+1,'next_lr':lr_for_update(c.BOUNDARY+1,steps_per_epoch=10478)},
        'epoch_5_permutation_sha256':state_digest(order),'historical_sample_ids_exact_match':True,
        'environment':actual_environment,'source_preflight':source_proof,
        'observer_fixture_gate':c.pin(run/'observer_test_result.json'),
        'engineering_model_parameters_updated':False,'formal_optimizer_steps':c.FORMAL_STEPS,
        '2025_RAW_ACCESS':0,'model_binary_written':False}
    gate['exact_prior_autopsy_preflight']=c.preflight_matches_prior(gate)
    gate['frozen_mask_identity']=c.pin(Path(contract.protocol['identity']['yunnan_mask']['path']))
    gate['frozen_target_mask_logical_sha256']=state_digest(mask)
    gate['frozen_target_mask_shape']=[100,100]
    gate['frozen_target_mask_true_cells']=int(mask.sum())
    if c.read(run/'observer_test_result.json')['status']!='PASS':raise PermissionError('Observer tests must pass')
    c.write(run/'replay_identity_preflight.json',gate);del payload;gc.collect()
    stage=a.data.STAGE_ROOT/('extended_paired_'+run.name+'_mask_partitioned_replay')
    if stage.exists():raise FileExistsError('New owned English staging root required')
    ds=ReplayDataset('B0_MATCHED',records,frames,mapping,mask,stage);ds.scaler=c.read(expected['normalization']['path'])
    ds.context={'public':str(run),'authorization':c.pin(run/'execution_scope.json'),
        'allowed_sources':allowed,'normalization_sha256':expected['normalization']['sha256']}
    model.train();obs=Observer(model,torch.from_numpy(mask))
    counts={'ENGINEERING_OPTIMIZER_STEPS':0,'ENGINEERING_BACKWARD_CALLS':0,'ENGINEERING_FORWARD_CALLS':0,
            'FORMAL_OPTIMIZER_STEPS_ADDED':0,'FORMAL_OPTIMIZER_STEPS':c.FORMAL_STEPS,
            '2025_RAW_ACCESS':0,'2025_PIXELS_READ':0,'B1_PHASE_B_STARTED':False}
    prior_handle=(c.PRIOR/'replay_observations.jsonl').open(encoding='utf8')
    prior_iterator=(json.loads(line) for line in prior_handle)
    partition_union_matches=0
    keys=('sample_ids','update','LR','actual_denominator','loss','pre_clip_norm','post_clip_norm','clipped')
    matches={k:0 for k in keys};failure=None;started=time.perf_counter()
    def status(state,**extra):
        c.progress(run,{'status':state,'run':str(run),'pid':os.getpid(),
            'engineering_updates':counts['ENGINEERING_OPTIMIZER_STEPS'],'expected_successful_updates':c.SUCCESS,
            'engineering_forwards':counts['ENGINEERING_FORWARD_CALLS'],'failure_batch':c.FAIL_BATCH,
            'formal_optimizer_steps':c.FORMAL_STEPS,'2025_raw_access':0,'B1_phase_b_started':False,
            'elapsed_seconds':time.perf_counter()-started,'exact_match_counts':matches,**extra})
    loader=DataLoader(ds,batch_sampler=plan,num_workers=2,pin_memory=False,persistent_workers=False,
        prefetch_factor=1,worker_init_fn=worker_init,collate_fn=a.data.collate)
    def backward_hook(*args):counts['ENGINEERING_BACKWARD_CALLS']+=1
    original_backward=torch.Tensor.backward
    def observed_backward(tensor,*args,**kwargs):
        backward_hook();return original_backward(tensor,*args,**kwargs)
    torch.Tensor.backward=observed_backward
    step_hook=optimizer.register_step_post_hook(lambda *_:counts.__setitem__('ENGINEERING_OPTIMIZER_STEPS',counts['ENGINEERING_OPTIMIZER_STEPS']+1))
    model_hook=model.register_forward_pre_hook(lambda *_:counts.__setitem__('ENGINEERING_FORWARD_CALLS',counts['ENGINEERING_FORWARD_CALLS']+1))
    try:
        with (run/'mask_partitioned_forward_observations.jsonl').open('x',encoding='utf8') as log:
            status('REPLAY_RUNNING',identity_gate='PASS',latest={})
            with obs.installed(),a.loader_items(loader) as iterator:
                for j,items in enumerate(iterator,1):
                    batch=a.data.make_batch(items);u=c.BOUNDARY+j
                    if batch.indices!=plan[j-1] or batch.sample_ids!=[records[i]['sample_id'] for i in plan[j-1]]:
                        raise ValueError('REPRODUCTION_FAILURE: loader sample order')
                    prior_row=next(prior_iterator,None)
                    if prior_row is None or prior_row['sample_ids']!=batch.sample_ids or prior_row['update']!=u:
                        raise ValueError('REPRODUCTION_FAILURE: previous autopsy forward identity')
                    obs.begin(batch,items,records,optimizer,u)
                    try:metrics,out=x.execute_update(model,optimizer,batch,u)
                    except FloatingPointError as exc:
                        if str(exc)!=c.ERROR or j!=c.FAIL_BATCH or obs.failure is None:
                            raise RuntimeError('REPRODUCTION_FAILURE: different forward failure') from exc
                        failure=obs.failure
                        c.write(run/'failing_batch_identity.json',{'scope':c.SCOPE,'global_update':u,'epoch_batch':j,
                            'failed_forward':True,'sample_identities':failure['sample_identities']})
                        c.write(run/'mask_partitioned_failure_forward.json',failure)
                        observation=obs.current;observation['status']='EXPECTED_FORWARD_OVERFLOW'
                        observation['LR']=lr_for_update(u,steps_per_epoch=10478)
                    else:
                        if j>c.SUCCESS:raise RuntimeError('REPRODUCTION_FAILURE: expected overflow absent')
                        aa,bb,n,r=train_numerators(out,batch)
                        actual={**metrics,'sample_ids':batch.sample_ids}
                        c.exact_reconcile(reference[j-1],actual)
                        for key in keys:matches[key]+=1
                        observation=obs.current;observation.update(metrics)
                        observation.update({'status':'SUCCESS_EXACT_MATCH','L_occ':aa/n,'L_qr':bb/n,
                            'rainy_count':r,'numerator_arithmetic':'readonly train_numerators; production loss remains unchanged',
                            'optimizer_after_update':obs.moments(optimizer)})
                        del out
                    c.check_partition_union(prior_row,observation)
                    partition_union_matches+=1
                    log.write(json.dumps(observation,allow_nan=False,separators=(',',':'))+'\n')
                    if j%10==0 or failure:
                        log.flush()
                        status('REPLAY_RUNNING' if failure is None else 'EXPECTED_OVERFLOW_CAPTURED',
                            latest={'update':u,'qlog_max':observation['qlog']['max'],
                                    'inside_max_qlog':observation['mask_partitioned']['YUNNAN_INSIDE']['global_qlog_max'],
                                    'outside_max_qlog':observation['mask_partitioned']['YUNNAN_OUTSIDE']['global_qlog_max'],
                                    'loss':observation.get('loss'),'pre_clip_norm':observation.get('pre_clip_norm')})
                    obs.release();del batch,items
                    if failure:break
        if (failure is None or counts['ENGINEERING_OPTIMIZER_STEPS']!=c.SUCCESS
            or counts['ENGINEERING_BACKWARD_CALLS']!=c.SUCCESS or counts['ENGINEERING_FORWARD_CALLS']!=c.FAIL_BATCH
            or any(v!=c.SUCCESS for v in matches.values()) or partition_union_matches!=c.FAIL_BATCH
            or next(prior_iterator,None) is not None):
            raise RuntimeError('REPRODUCTION_FAILURE: exact event counts not met')
        status('SUMMARIZING_REPLAY_RESULTS',latest={
            'inside_max_qlog':failure['inside_max_qlog'],'outside_max_qlog':failure['outside_max_qlog']})
        source_proof_closed=source_journals(run,[sid for indices in plan for sid in [records[i]['sample_id'] for i in indices]],records)
        summaries=finalize(run)
        reconciliation={'status':'EXACT_FAILURE_REPRODUCED','utc':c.now(),'scope':c.SCOPE,'counts':counts,
            'exact_matches':matches,'exact_comparison_tolerance':0,'wall_seconds_excluded':True,
            'state_restoration':state_proof,'exact_prior_autopsy_preflight':gate['exact_prior_autopsy_preflight'],
            'partition_union_matches_prior_autopsy':partition_union_matches,
            'source_journal_audit':source_proof_closed,'mask_partitioned_summary':summaries,
            'failure_batch':c.FAIL_BATCH,'failed_global_forward':c.BOUNDARY+c.FAIL_BATCH,
            'exception':c.ERROR,'formal_checkpoint_written':False,'engineering_checkpoint_written':False,
            'immutable_history':c.verify_snapshot(run),'staging':x.staging_state(stage),
            'final_disposable_model_state_sha256':state_digest(model.state_dict()),
            'final_disposable_optimizer_state_sha256':state_digest(optimizer.state_dict()),
            'FORMAL_RESUME_AUTHORIZED':False,'RESEARCHER_DECISION_REQUIRED':True}
        if not reconciliation['staging']['cleanup_success']:raise ValueError('Staging cleanup incomplete')
        c.write(run/'mask_partitioned_replay_reconciliation.json',reconciliation)
        status('MASK_PARTITIONED_REPLAY_COMPLETE_AWAITING_AUDIT',failure_qlog_max=failure['qlog_max'],
            inside_max_qlog=summaries['key_results']['INSIDE_MAX_QLOG'],
            outside_max_qlog=summaries['key_results']['OUTSIDE_MAX_QLOG'],exception=c.ERROR)
        print(json.dumps({'status':'EXACT_FAILURE_REPRODUCED','engineering_steps':c.SUCCESS,'formal_steps':c.FORMAL_STEPS}),flush=True)
    except BaseException as exc:
        reconciliation={'status':'REPRODUCTION_FAILURE','utc':c.now(),'scope':c.SCOPE,'counts':counts,
            'exact_matches':matches,'error_type':type(exc).__name__,'error':str(exc),'traceback':traceback.format_exc(),
            'FORMAL_RESUME_AUTHORIZED':False,'RESEARCHER_DECISION_REQUIRED':True,'automatic_retry':False}
        if not (run/'mask_partitioned_replay_reconciliation.json').exists():c.write(run/'mask_partitioned_replay_reconciliation.json',reconciliation)
        status('REPRODUCTION_FAILURE',error=str(exc));raise
    finally:
        prior_handle.close()
        torch.Tensor.backward=original_backward;step_hook.remove();model_hook.remove();obs.release()
        del model,optimizer,ds,loader;gc.collect();torch.cuda.empty_cache()

def main():
    p=argparse.ArgumentParser();p.add_argument('--run',required=True,type=Path);args=p.parse_args()
    try:replay(args.run)
    except BaseException as exc:
        if not (args.run/'mask_partitioned_replay_reconciliation.json').exists():
            c.write(args.run/'mask_partitioned_replay_reconciliation.json',{'status':'PREFLIGHT_FAILURE','utc':c.now(),
                'scope':c.SCOPE,'error':str(exc),'traceback':traceback.format_exc(),
                'FORMAL_OPTIMIZER_STEPS_ADDED':0,'2025_RAW_ACCESS':0,'FORMAL_RESUME_AUTHORIZED':False})
            c.progress(args.run,{'status':'PREFLIGHT_FAILURE','error':str(exc),'formal_optimizer_steps':c.FORMAL_STEPS,
                'engineering_updates':0,'expected_successful_updates':c.SUCCESS,'2025_raw_access':0})
        raise

if __name__=='__main__':main()
