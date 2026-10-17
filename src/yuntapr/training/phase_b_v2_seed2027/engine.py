"""Full-data B9 transactions, independent validation, fixed V0 endpoint.

No BEST selection, historical recovery or automatic retry. Prepared fresh seeds only.
"""
from __future__ import annotations
from dataclasses import replace
import gc
import json
import time
import torch
from yuntapr.experimental.phase_b_v2_ablations.config import get_config
from yuntapr.experimental.phase_b_v2_ablations.total import candidate_loss
from yuntapr.experimental.phase_b_v2_integration.initialization import fresh_paired_models,seeded_environment
from yuntapr.experimental.phase_b_v2_real_forward_pilot.pilot import validate_output
from yuntapr.experimental.phase_b_v2_runner_candidate.optimizer import new_adamw,clip_and_check,check_finite
from yuntapr.experimental.phase_b_v2_runner_candidate import rng
from yuntapr.experimental.phase_b_v2_formal_runner_candidate.checkpoint import optimizer_template
from yuntapr.experimental.phase_b_v2_formal_integration_candidate.checkpoint import Schedule
from yuntapr.training.phase_a_protocol import state_digest
from .protocol import OUT,LOCAL,ORDER,LIMITS,CAMPAIGN,STEPS,TRAIN_N,DEV_N,SEED,digest,atomic_json,epoch_order,run_id,verify_release,owned_json
from .resources import utcnow
from .evaluation import Evaluator
from .checkpoint import Contract,Store,SCHEMA

def cpu_tree(value):
    if isinstance(value,torch.Tensor):return value.detach().cpu().clone()
    if isinstance(value,dict):return {k:cpu_tree(v) for k,v in value.items()}
    if isinstance(value,list):return [cpu_tree(v) for v in value]
    if isinstance(value,tuple):return tuple(cpu_tree(v) for v in value)
    return value

def checked_output(output,b):
    return validate_output(replace(output,rain_logit=output.rain_logit.detach(),rain_prob=output.rain_prob.detach(),
        conditional_quantiles_log=output.conditional_quantiles_log.detach()),b,torch.device('cuda:0'))

class Engine:
    def __init__(self,adapter,budget,ledger,release):
        self.adapter,self.plan,self.budget,self.ledger,self.release=adapter,adapter.plan,budget,ledger,release
        self.completed=[]
        self.initial_by_model={}
        for model,arm in ORDER:
            ident=run_id(model,arm);state=ledger.run_row(ident)
            if state['status']=='COMPLETE':
                result=json.loads((OUT/(ident+'.json')).read_bytes())
                if result['run_id']!=ident or result['epochs'][-1]['checkpoint']['payload_sha256']!=state['last_sha']:
                    raise ValueError('SAME_CAMPAIGN_COMPLETED_RESULT_IDENTITY')
                initial=result['initial_sha256']
                if model in self.initial_by_model and self.initial_by_model[model]!=initial:
                    raise ValueError('CROSS_ARM_FRESH_INITIAL_IDENTITY')
                self.initial_by_model[model]=initial
    def run_one(self,model_kind: str,arm: str):
        from .quota import PauseAtBoundary
        ident=run_id(model_kind,arm);self.ledger.start_run(ident)
        row=self.ledger.run_row(ident);folder=LOCAL/ident
        existing=folder.exists()
        if not existing:folder.mkdir(exist_ok=False)
        self.budget.cuda_admission();self.budget.check()
        torch.cuda.reset_peak_memory_stats()
        started=time.monotonic();store=None
        with seeded_environment(SEED):
            models,proof=fresh_paired_models(SEED);model=models.pop(model_kind).to('cuda:0');del models
            initial=state_digest(model.state_dict())
            if initial!=proof['state_sha256'][model_kind]:raise ValueError('FRESH_MODEL_DEVICE_IDENTITY')
            if model_kind in self.initial_by_model and self.initial_by_model[model_kind]!=initial:raise ValueError('CROSS_ARM_FRESH_INITIAL_IDENTITY')
            self.initial_by_model[model_kind]=initial
            buffers=state_digest(dict(model.named_buffers()))
            optimizer,grouping=new_adamw(model);schedule=Schedule()
            identity=dict(campaign=CAMPAIGN,run_id=ident,model=model_kind,arm=arm,seed=SEED,
                alpha=.5,gamma=get_config(arm).gamma,lambda_q=get_config(arm).lambda_q,
                design='D1/Q1/N0/I3/B9/S0/V0',statistics='M-C_EXPLORATORY',code=self.release,
                data=self.plan.identity,limits=LIMITS,authorization_ancestor=CAMPAIGN,
                initial_sha256=initial,warm_start=False)
            if existing:
                if owned_json(folder/'identity.json')!=identity:raise ValueError('SAME_RUN_IDENTITY_CHANGED')
            else:atomic_json(folder/'identity.json',identity)
            contract=Contract(identity,{k:(tuple(v.shape),str(v.dtype)) for k,v in model.state_dict().items()},
                optimizer_template(optimizer),initial,self.plan.ids(2023),self.plan.ids(2024))
            store=Store.reopen_owned(folder/'checkpoints',contract,row['epoch'],row['last_sha']) if existing else Store(folder/'checkpoints',contract)
            epochs=[];first_epoch=1
            try:
                if existing and row['epoch']>0:
                    from .recovery import apply_validated_state
                    payload=store.read(folder/'checkpoints'/f"LAST_epoch_{row['epoch']:02d}.ref.json")
                    if payload['epoch']!=row['epoch'] or payload['update']!=row['updates'] or payload['quota']['reserved']!=self.ledger.snapshot()['reserved']:
                        raise ValueError('PAUSED_LAST_QUOTA_OR_UPDATE_ROLLBACK')
                    apply_validated_state(model,optimizer,schedule,payload)
                    epochs=owned_json(folder/'progress.json')['epochs'];first_epoch=row['epoch']+1
                    self.budget.emit('VERIFIED_SAFE_PAUSE_LAST_RESUMED',run_id=ident,epoch=row['epoch'],last_sha=row['last_sha'])
                    del payload
                for epoch in range(first_epoch,10):
                    train=self.train(model,optimizer,schedule,identity,epoch,folder,buffers)
                    report=self.validate(model,identity,epoch,folder)
                    self.ledger.validated(ident,epoch,report)
                    payload=dict(schema=SCHEMA,identity=identity,model=cpu_tree(model.state_dict()),optimizer=cpu_tree(optimizer.state_dict()),
                        scheduler=schedule.state_dict(),rng=cpu_tree(rng.capture()),initial_sha=initial,epoch=epoch,
                        update=schedule.completed,train=train,validation=report,parent_last_sha=self.ledger.parent(ident),quota=self.ledger.snapshot())
                    self.budget.check();ref=store.save(f'LAST_epoch_{epoch:02d}',payload)
                    loaded=store.read(ref)
                    for key in payload:
                        if state_digest(loaded[key])!=state_digest(payload[key]):raise ValueError('FULL_CHECKPOINT_STATE_ROUNDTRIP_'+key)
                    receipt=store.receipt(ref);self.ledger.last(ident,epoch,receipt)
                    self.budget.emit('EPOCH_LAST_COMMITTED',run_id=ident,epoch=epoch,update=schedule.completed,receipt=receipt)
                    epochs.append(dict(epoch=epoch,train=train,development=report,checkpoint=receipt))
                    atomic_json(folder/'progress.json',dict(run_id=ident,status='COMPLETE' if epoch==9 else 'RUNNING',
                        complete_epoch=epoch,updates=schedule.completed,epochs=epochs,elapsed_seconds=time.monotonic()-started))
                    atomic_json(OUT/(ident+'_curve_data.json'),dict(run_id=ident,epoch=[r['epoch'] for r in epochs],
                        weighted_training_loss=[r['train']['weighted_training_mean'] for r in epochs],
                        common_development_core_fp64=[r['development']['summary']['core_fp64'] for r in epochs],
                        development_brier=[r['development']['summary']['brier'] for r in epochs],
                        training_loss_not_cross_arm_common_metric=True))
                    atomic_json(OUT/'execution_status.json',dict(status='RUNNING',current_run=ident,complete_epoch=epoch,
                        quota=self.ledger.snapshot(),updated_utc=utcnow(),**boundary_flags()))
                    del payload,loaded;gc.collect();self.budget.check()
                    if epoch<9 and self.ledger.pause_requested():raise PauseAtBoundary()
                if schedule.completed!=47052:raise ValueError('V0_FIXED_NINTH_EPOCH_ENDPOINT')
                result=dict(run_id=ident,status='COMPLETE',epochs=epochs,updates=47052,initial_sha256=initial,
                    final_sha256=state_digest(model.state_dict()),elapsed_seconds=time.monotonic()-started,
                    cuda_peak_allocated_bytes=torch.cuda.max_memory_allocated(),cuda_peak_reserved_bytes=torch.cuda.max_memory_reserved())
                self.completed.append(result);atomic_json(OUT/(ident+'.json'),result)
            finally:
                if store is not None:store.close()
                del model,optimizer;gc.collect();torch.cuda.empty_cache()
    def train(self,model,optimizer,schedule,identity,epoch,folder,buffer_sha):
        if verify_release()!=self.release:raise ValueError('SOURCE_CHANGED_BEFORE_EPOCH')
        ident=identity['run_id'];self.ledger.begin_epoch(ident,epoch)
        order=epoch_order(self.plan.ids(2023),epoch);visited=[];nvalid=nrain=0;occ=qr=weighted=0.;started=time.monotonic()
        model.train()
        for position in range(0,TRAIN_N,2):
            ids=order[position:position+2];self.budget.check()
            x,native,rate,valid,region=self.adapter.batch(ids,identity['model'],2023)
            optimizer.zero_grad(set_to_none=True);lr=schedule.prepare(optimizer)
            with torch.autocast('cuda',dtype=torch.bfloat16):
                output=model(x,native);checked_output(output,len(ids))
                loss=candidate_loss(output.rain_logit,output.conditional_quantiles_log,rate,valid,region,config=get_config(identity['arm']))
            if loss.n_valid!=len(ids)*3430 or not bool(torch.isfinite(loss.training_objective)):raise ValueError('TRAIN_SUPERVISION_OR_NONFINITE_LOSS')
            loss.training_objective.backward();clip=clip_and_check(model);self.budget.check()
            update=schedule.completed+1
            attempt=self.ledger.reserve(ident,update) # durable, nonrefundable BEFORE actual optimizer call
            optimizer.step();schedule.commit()
            check_finite(model.state_dict());check_finite(optimizer.state_dict())
            self.budget.check();self.ledger.returned(ident,update)
            a,b=float(loss.s_occ.detach()),float(loss.s_qr.detach())
            nvalid+=loss.n_valid;nrain+=loss.n_rain;occ+=a;qr+=b;weighted+=a+get_config(identity['arm']).lambda_q*b
            visited.extend(ids)
            self.budget.emit('STEP_RETURNED',run_id=ident,epoch=epoch,update=update,campaign_attempt=attempt,
                lr=lr,n_valid=loss.n_valid,n_rain=loss.n_rain,s_occ_unweighted=a,s_qr_unweighted=b,
                training_objective=float(loss.training_objective.detach()),**clip)
            if update==1 or update%100==0:
                atomic_json(OUT/'execution_status.json',dict(status='RUNNING',current_run=ident,epoch=epoch,
                    phase='TRAINING',epoch_completed_batches=(position//2)+1,epoch_total_batches=STEPS,
                    complete_epochs=epoch-1,run_updates=schedule.completed,quota=self.ledger.snapshot(),
                    first_optimizer_returned_verified=True,updated_utc=utcnow(),**boundary_flags()))
            # Release the graph and supervised tensors before the next allocation.
            del x,native,rate,valid,region,output,loss
        if (tuple(visited)!=order or len(set(visited))!=TRAIN_N or schedule.completed!=epoch*STEPS or nvalid!=TRAIN_N*3430 or
            state_digest(dict(model.named_buffers()))!=buffer_sha):raise ValueError('FULL_EPOCH_COVERAGE_OR_FROZEN_BUFFER')
        train=dict(scenes=TRAIN_N,batches=STEPS,ids_sha=digest(order),n_valid=nvalid,n_rain=nrain,
            s_occ_unweighted=occ,s_qr_unweighted=qr,weighted_training_mean=weighted/nvalid,
            training_loss_is_not_common_evaluation=True,elapsed_seconds=time.monotonic()-started)
        self.ledger.finish_train(ident,epoch,train);atomic_json(folder/f'train_epoch_{epoch:02d}.json',train)
        return train
    @torch.inference_mode()
    def validate(self,model,identity,epoch,folder):
        model.eval();ids=self.plan.ids(2024);efolder=folder/f'development_epoch_{epoch:02d}';efolder.mkdir(exist_ok=False)
        evaluator=Evaluator(ids,digest(identity),efolder);before=state_digest(model.state_dict());started=time.monotonic()
        try:
            for position in range(0,DEV_N,8):
                batch_ids=ids[position:position+8];self.budget.check()
                x,native,rate,valid,region=self.adapter.batch(batch_ids,identity['model'],2024)
                with torch.autocast('cuda',dtype=torch.bfloat16):output=model(x,native)
                checked_output(output,len(batch_ids))
                evaluator.add(batch_ids,tuple(self.plan.by_id[k]['window_start'] for k in batch_ids),output.rain_logit,output.rain_prob,
                    output.conditional_quantiles_log,rate,valid,region)
                del x,native,rate,valid,region,output
            report=evaluator.finish()
            if before!=state_digest(model.state_dict()):raise ValueError('VALIDATION_MUTATED_MODEL')
            # Timing belongs outside the hashed scientific completion receipt.
            atomic_json(efolder/'report.json',report)
            atomic_json(efolder/'resources.json',dict(elapsed_seconds=time.monotonic()-started,batches=1313,tail_batch=5))
            self.budget.emit('VALIDATION_COMPLETE',run_id=identity['run_id'],epoch=epoch,receipt_sha=report['receipt_sha'])
            return report
        finally:evaluator.close()
    def run(self):
        for model,arm in ORDER:
            ident=run_id(model,arm)
            if self.ledger.run_row(ident)['status']=='COMPLETE':
                self.completed.append(json.loads((OUT/(ident+'.json')).read_bytes()))
            else:self.run_one(model,arm)
        self.ledger.complete()
        from .analysis import compare
        compare(self.completed)
        return self.completed

def boundary_flags():
    return dict(selected_seed=SEED,execution_scope='SEED2027_RELEASE_PUBLISHED_LAUNCH_WITHHELD',
        FORMAL_SCIENTIFIC_EXECUTION_AUTHORIZED=False,FINALFIT_AUTHORIZED=False,
        HISTORICAL_RECOVERY_RATIFICATION='NOT_GRANTED',TEST_2025_AUTHORIZED=False,
        PIXELS_2025_READ=0,HISTORICAL_2025_PATH_ATTRIBUTE_ACCESS='NOT_INSTRUMENTED',
        statistics='M-C_EXPLORATORY',no_automatic_retry_or_recovery=True)
