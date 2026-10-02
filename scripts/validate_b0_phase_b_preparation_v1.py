"""Sanity, two isolated real engineering steps, tests and preparation report. No fit loop."""
import argparse
from dataclasses import fields
from datetime import datetime,timezone
import gc
import json
import math
import os
from pathlib import Path
import shutil
import sys
import tempfile
import time
import traceback
import unittest
from unittest.mock import patch
import uuid
import weakref

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'src'),str(ROOT/'scripts')]
import numpy as np
import torch
import yaml
from prepare_b0_phase_b_finalfit_v1 import (read,save,rows,table,preserve,source_paths,sha256,ROOT,PRIVATE,
    STAGING,REVIEW,REVIEW_ID,BASELINE,PROTOCOL,DECISION,SCENES,PIXELS,STEPS,EPOCHS,UPDATES,TAIL_POLICY,INITIALIZATION)
from yuntapr.training.phase_b_preparation import PhaseBNormalizer,batch_plan,finalfit_lr,validate_population
from yuntapr.training.phase_a_protocol import seed_reproducibility,state_digest,lr_for_update,adamw,head_pin
from yuntapr.models.b0 import B0Model


def reject_checkpoint_load(*args,**kwargs):
    raise RuntimeError('Phase-A checkpoint/model/optimizer/scheduler initialization forbidden')


def sanity(out):
    preserve(out)
    identities=rows(out/'phase_b_finalfit_manifest.csv');validate_population(identities)
    normpath=out/'normalization_phaseB_finalfit_2023_2024.json';norm=read(normpath)
    normalizer=PhaseBNormalizer.from_artifact(normpath,sha256(normpath))
    evidence=read(out/'preparation_manifest.json')
    protocol={'version':'v1','status':'RESEARCHER_APPROVED_PREPARATION_ONLY','baseline_commit':BASELINE,
        'B0_PHASE_A_ACCEPTED':True,'TRANSFER_EPOCH_BUDGET_TO_PHASE_B':11,'FINALFIT_EPOCHS':EPOCHS,
        'PHASE_B_AUTHORIZED':False,'PHASE_B_FORMAL_TRAINING_STARTED':False,'B1_TO_B8_AUTHORIZED':False,
        'PHASE_B_MODEL_INITIALIZATION':INITIALIZATION,'PRIMARY_SEED':2026,'phase_a_model_state_allowed':False,
        'phase_a_optimizer_state_allowed':False,'phase_a_scheduler_state_allowed':False,
        'architecture_loss_optimizer_precision_and_clipping':'inherit exactly from SHA-pinned Phase-A protocol',
        'inherited_protocol':evidence['identity']['phase_a_protocol'],'scientific_contract':evidence['identity']['scientific_contract_v1.1'],
        'acceptance':{'path':DECISION.relative_to(ROOT).as_posix(),'sha256':sha256(DECISION)},
        'finalfit_manifest':{'path':(out/'phase_b_finalfit_manifest.csv').relative_to(ROOT).as_posix(),'sha256':sha256(out/'phase_b_finalfit_manifest.csv')},
        'normalization':{'path':normpath.relative_to(ROOT).as_posix(),'sha256':sha256(normpath),'status':'READY'},
        'physical_batch':2,'gradient_accumulation_steps':1,'drop_last':False,'singleton_effective_batch':1,
        'steps_per_epoch':STEPS,'total_planned_updates':UPDATES,'FINALFIT_TAIL_BATCH_POLICY':TAIL_POLICY,
        'loss_denominator':'all valid Yunnan supervised pixels in the actual batch; singleton is not divided by physical batch 2',
        'population_years':[2023,2024],'months':list(range(3,11)),'counts':{'2023':11720,'2024':11727,'2025':0},
        'sampling':{'shuffle':True,'epoch_seed_rule':'2026 + zero_based_epoch_index','permutation':'independent torch.Generator randperm(23447)',
            'once_per_epoch':True,'duplicate_drop_padding_replacement':False},
        'scheduler':{'type':'ONE_EPOCH_LINEAR_WARMUP_THEN_COSINE','rule':'SAME_EPOCH_PROGRESS_ON_50_EPOCH_HORIZON',
            'base_lr':1e-4,'min_lr':1e-6,'horizon_epochs':50,'warmup_epochs':1,'W':STEPS,'U':50*STEPS,'update_index_base':1,
            'warmup':'base_lr * (u/W)','cosine':'min_lr+(base_lr-min_lr)*(1+cos(pi*(u-W)/(U-W)))/2',
            'apply_before_optimizer_step':True,'warmup_range':'0<lr<=base_lr; may be below min_lr','cosine_range':'min_lr<=lr<=base_lr'},
        'early_stopping':False,'validation_triggered_scheduler':False,'epoch_reselection':False,'2025_access':False,
        'ENGINEERING_ONLY_TWO_BATCH_DRYRUN_AUTHORIZED':True,'formal_training_entrypoint_provided':False}
    with PROTOCOL.open('x',encoding='utf-8',newline='\n') as f:yaml.safe_dump(protocol,f,allow_unicode=True,sort_keys=False)
    permutations=[]
    for epoch in range(EPOCHS):
        p,batches=batch_plan(epoch)
        if sorted(p.tolist())!=list(range(SCENES)) or len(batches)!=STEPS or len(batches[-1])!=1 or any(len(b)!=2 for b in batches[:-1]):raise ValueError('Permutation/tail gate failed')
        permutations.append({'epoch_index':epoch,'seed':2026+epoch,'identities_exactly_once':True,'batches':len(batches),
            'permutation_state_sha256':state_digest(p),'singleton_index':int(p[-1])})
    p,_=batch_plan(0)
    private=Path(evidence['private_directory'])
    permutationpath=private/'epoch1_permutation.csv'
    table(permutationpath,[{'epoch_position':k,'finalfit_index':int(v),'sample_id':identities[int(v)]['sample_id']} for k,v in enumerate(p)])
    selected=[int(p[0]),int(p[1]),int(p[-1])]
    save(out/'engineering_sample_selection.json',{'scope':'ENGINEERING_ONLY','declared_before_read':True,
        'rule':'first batch2 and last singleton in the seed-2026 epoch1 permutation; no target/model selection',
        'selected_finalfit_indices':selected,'batches':[[identities[i]['sample_id'] for i in selected[:2]],[identities[selected[-1]]['sample_id']]],
        'manifest_sha256':sha256(out/'phase_b_finalfit_manifest.csv'),'epoch1_permutation':{'absolute_local_path':str(permutationpath),'bytes':permutationpath.stat().st_size,'sha256':sha256(permutationpath)}})
    W,U=STEPS,50*STEPS
    warm=np.array([finalfit_lr(u) for u in range(1,W+1)])
    cosine=np.array([finalfit_lr(u) for u in range(W+1,U+1)])
    if (finalfit_lr(W)!=1e-4 or finalfit_lr(U)!=1e-6 or not ((warm>0)&(warm<=1e-4)).all()
        or not (np.diff(warm)>0).all() or not ((cosine>=1e-6)&(cosine<=1e-4)).all() or not (np.diff(cosine)<=0).all()):raise ValueError('Scheduler boundary/range gate failed')
    replay=[]
    for quarter in range(1,201):
        a=lr_for_update(quarter*1465);b=finalfit_lr(quarter*2931)
        if a!=b:raise ValueError('Exact epoch-progress replay mismatch')
        replay.append({'epoch_progress':quarter/4,'phase_a_update':quarter*1465,'phase_b_update':quarter*2931,
            'phase_a_lr_hex':a.hex(),'phase_b_lr_hex':b.hex(),'exact':True})
    with patch('torch.load',side_effect=reject_checkpoint_load) as loader:
        seed_reproducibility();a=B0Model();initial_sha=state_digest(a.state_dict());head_pin(a);del a
        seed_reproducibility();b=B0Model();second_sha=state_digest(b.state_dict());del b
        if initial_sha!=second_sha or loader.call_count:raise ValueError('Fresh initialization gate failed')
    save(out/'protocol_sanity.json',{'status':'PASS','population':SCENES,'normalization_pixels':PIXELS,'tail_policy':TAIL_POLICY,
        'actual_epoch_permutations':permutations,'all_11_planned_epochs_exactly_once':True,
        'scheduler_boundaries':[{'u':u,'lr':finalfit_lr(u),'lr_hex':finalfit_lr(u).hex()} for u in [1,W,W+1,UPDATES,U]],
        'scheduler_updates_numerically_checked':U,'real_optimizer_steps_for_sweep':0,'same_epoch_progress_replay_exact':True,'quarter_epoch_replay':replay,
        'fresh_seed_initialization_reproducible':True,'initial_model_state_sha256':initial_sha,'checkpoint_load_calls':loader.call_count,
        'normalization_sha256':normalizer.artifact_sha256,'normalization_mu':normalizer.mu,'normalization_sigma':normalizer.sigma,
        'PHASE_B_AUTHORIZED':False,'PHASE_B_FORMAL_TRAINING_STARTED':False,'preservation':preserve(out)})
    print('PROTOCOL_SANITY_GATE_PASS',flush=True)


def dryrun(out):
    from yuntapr.data.staging import BoundedEnglishStaging,StagedB13Reader,StagedIMERGReader
    from yuntapr.data.dataset_b0 import B0Record,B0Dataset
    from yuntapr.data.sample_schema import utc
    from yuntapr.data.masks import read_frozen_yunnan_mask
    from yuntapr.spatial.sp04_mapping import load_sp04
    from yuntapr.training.batch_contract import B0Batch
    from yuntapr.training.forward_step import formal_rules_engineering_forward_step
    from yuntapr.training.formal_phase_a import precision_check,assert_determinism
    from torch.nn import functional as F
    preserve(out);started=time.perf_counter()
    manifest=read(out/'preparation_manifest.json');identities=rows(out/'phase_b_finalfit_manifest.csv')
    selection=read(out/'engineering_sample_selection.json')
    mapping=load_sp04();maskpath=Path(manifest['identity']['yunnan_mask']['path']);yunnan=read_frozen_yunnan_mask(maskpath,mapping)
    normpath=out/'normalization_phaseB_finalfit_2023_2024.json';normalizer=PhaseBNormalizer.from_artifact(normpath,sha256(normpath))
    stage=BoundedEnglishStaging(STAGING/('phase_b_prepare_'+out.name)/'engineering',734003200,True,True)
    reader=StagedB13Reader(stage,mapping);ireader=StagedIMERGReader(stage,mapping)
    samples=[];audit=[]
    for index in selection['selected_finalfit_indices']:
        identity=identities[index];h,i=source_paths(identity)
        before=len(stage.records);x,valid,meta=reader(h,utc(identity['expected_nominal']))
        if meta.obs_end!=utc(identity['selected_obs_end']):raise ValueError('Frozen causal metadata changed')
        record=B0Record(identity['sample_id'],utc(identity['window_start']),(meta,),i,int(identity['imerg_index']),'IMERG','V07','Final',True)
        def cached(path,nominal):
            if path!=h or nominal!=meta.nominal_time:raise ValueError('Unexpected cached source')
            return x,valid,meta
        assembler=B0Dataset([record],mapping,yunnan,cached,ireader,frozen_mask_path=maskpath,formal_supervised=True,normalizer=normalizer)
        sample=assembler[0];ops=stage.records[before:]
        if (len(ops)!=2 or [r.source_sha256 for r in ops]!=[identity['b13_sha256'],identity['imerg_sha256']]
            or ops[0].temporary_bytes!=int(identity['b13_bytes']) or not all(r.cleanup_success for r in ops)
            or int((sample.imerg_valid_mask & yunnan).sum())!=int(identity['imerg_valid_yunnan_count'])
            or int(((sample.y_imerg>.1)&sample.imerg_valid_mask&yunnan).sum())!=int(identity['imerg_rain_yunnan_count'])):raise ValueError('Engineering source/QC identity mismatch')
        samples.append(sample)
        audit.append({'finalfit_index':index,'sample_id':sample.sample_id,'year':identity['year'],'nominal_time':str(meta.nominal_time),
            'obs_start':str(meta.obs_start),'obs_end':str(meta.obs_end),'date_created':str(meta.date_created),
            'normalization_sha256':normalizer.artifact_sha256,'operations':[r.__dict__ for r in ops]})
    batch_evidence=[]
    with patch('torch.load',side_effect=reject_checkpoint_load) as loader:
        seed_reproducibility();assert_determinism();torch.set_num_threads(2)
        model=B0Model().cuda().train();initial_sha=state_digest(model.state_dict())
        if initial_sha!=read(out/'protocol_sanity.json')['initial_model_state_sha256']:raise ValueError('Dry-run model is not fresh seed2026')
        optimizer,groups=adamw(model);observed={}
        handle=model.heads.quantile.register_forward_hook(lambda m,i,o:observed.update(raw_dtype=o.dtype))
        for step,selected_samples in enumerate((samples[:2],samples[2:]),1):
            batch=B0Batch.from_formal_samples(selected_samples)
            for field in fields(batch):
                value=getattr(batch,field.name)
                if isinstance(value,torch.Tensor):setattr(batch,field.name,value.cuda())
            optimizer.zero_grad(set_to_none=True);lr=finalfit_lr(step)
            for group in optimizer.param_groups:group['lr']=lr
            torch.cuda.reset_peak_memory_stats()
            with torch.autocast('cuda',dtype=torch.bfloat16):
                output,loss=formal_rules_engineering_forward_step(model,batch,focal_alpha=.5,focal_gamma=2.,quantile_axis_reduction='mean')
            # Verify unchanged numerical contract without tagging this engineering step as formal.
            q=output.conditional_quantiles_log;physical=output.conditional_quantiles_physical
            if observed['raw_dtype']!=torch.float32 or q.dtype!=torch.float64 or physical.dtype!=torch.float64 or loss.conditional_quantile.dtype!=torch.float64:raise ValueError('Precision changed')
            if not (torch.isfinite(q).all() and torch.isfinite(physical).all() and (q[:,0]>math.log1p(.1)).all() and (q[:,1:]>q[:,:-1]).all() and (physical[:,1:]>physical[:,:-1]).all()):raise ValueError('Numerical gate failed')
            valid=batch.imerg_valid_mask & batch.yunnan_eval_mask;n=int(valid.sum());rainy=batch.y_imerg>.1
            clean=torch.where(valid,batch.y_imerg,torch.zeros_like(batch.y_imerg))
            with torch.no_grad():
                logits=output.rain_logit.to(torch.float64);label=rainy.to(torch.float64)
                bce=F.softplus(logits)-logits*label
                occ_ref=(.5*(1-torch.exp(-bce))**2*bce*valid).sum()/n
                taus=((torch.arange(1,33,device='cuda',dtype=torch.float64)-.5)/32).reshape(1,32,1,1)
                err=torch.log1p(clean.to(torch.float64))-q
                qr_ref=(torch.maximum(taus*err,(taus-1)*err).mean(1,keepdim=True)*(rainy&valid)).sum()/n
                occ_error=abs(float(loss.occurrence)-float(occ_ref));qr_error=abs(float(loss.conditional_quantile)-float(qr_ref))
                if n!=loss.valid_supervised_count or n!=sum(int((s.imerg_valid_mask & s.yunnan_eval_mask).sum()) for s in selected_samples) or occ_error>1e-7 or qr_error>1e-12:raise ValueError('Actual batch valid-pixel reduction mismatch')
            loss_value=float(loss.total.detach());loss.total.backward()
            params=list(model.parameters())
            if any(p.grad is None or not torch.isfinite(p.grad).all() for p in params):raise ValueError('Missing/nonfinite gradients')
            pre=float(torch.nn.utils.clip_grad_norm_(params,5.,norm_type=2.,error_if_nonfinite=True))
            post=float(torch.linalg.vector_norm(torch.stack([torch.linalg.vector_norm(p.grad.detach(),2) for p in params]),2))
            if post>5.00001:raise ValueError('Clip norm gate failed')
            before=state_digest(model.state_dict());optimizer.step();after=state_digest(model.state_dict())
            if before==after:raise ValueError('Engineering optimizer step did not update temporary model')
            torch.cuda.synchronize()
            batch_evidence.append({'scope':'ENGINEERING_ONLY','engineering_update':step,'batch_size':len(selected_samples),
                'sample_ids':[s.sample_id for s in selected_samples],'valid_denominator':n,'loss':loss_value,'occurrence_reference_abs_error':occ_error,
                'quantile_reference_abs_error':qr_error,'LR':lr,'pre_clip_norm':pre,'post_clip_norm':post,'model_parameters_changed':True,
                'raw_quantile_dtype':str(observed['raw_dtype']),'qlog_dtype':str(q.dtype),'pinball_dtype':str(loss.conditional_quantile.dtype),
                'forward_pass':True,'loss_pass':True,'backward_pass':True,'clip_pass':True,'optimizer_step_pass':True,
                'peak_GPU_allocated_bytes':torch.cuda.max_memory_allocated(),'peak_GPU_reserved_bytes':torch.cuda.max_memory_reserved()})
            del output,loss,batch,params,q,physical,logits,label,bce,occ_ref,taus,err,qr_ref,valid,rainy,clean
        handle.remove();modelref=weakref.ref(model);optimizerref=weakref.ref(optimizer)
        del model,optimizer,groups,handle
        gc.collect();torch.cuda.empty_cache();torch.cuda.synchronize()
        released=modelref() is None and optimizerref() is None
    if stage._owned or not released:raise ValueError('Temporary artifacts not released')
    save(out/'engineering_dryrun.json',{'status':'PASS','scope':'ENGINEERING_ONLY','batches':batch_evidence,
        'actual_source_read_audit':audit,'initial_model_state_sha256':initial_sha,'checkpoint_load_calls':loader.call_count,
        'phase_a_model_optimizer_scheduler_state_loaded':False,'temporary_model_optimizer_released':released,
        'temporary_checkpoint_binaries_created':0,'temporary_checkpoint_binaries_remaining':0,'owned_staging_files_remaining':len(stage._owned),
        'ENGINEERING_OPTIMIZER_STEPS':2,'ENGINEERING_BACKWARD_CALLS':2,'FORMAL_OPTIMIZER_STEPS':0,
        '2025_PIXELS_READ':0,'PHASE_B_AUTHORIZED':False,'PHASE_B_FORMAL_TRAINING_STARTED':False,
        'wall_seconds':time.perf_counter()-started,'preservation':preserve(out)})
    print('REAL_BATCH2_AND_SINGLETON_ENGINEERING_GATE_PASS',flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('action',choices=['sanity','dryrun']);parser.add_argument('--run-dir',type=Path,required=True)
    args=parser.parse_args();out=args.run_dir.resolve()
    try:
        {'sanity':sanity,'dryrun':dryrun}[args.action](out)
    except Exception as error:
        traceback.print_exc()
        save(out/('failure_'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S_%fZ')+'.json'),{'action':args.action,'error':repr(error),'traceback':traceback.format_exc(),'PHASE_B_AUTHORIZED':False,'PHASE_B_FORMAL_TRAINING_STARTED':False})
        raise SystemExit(1)
