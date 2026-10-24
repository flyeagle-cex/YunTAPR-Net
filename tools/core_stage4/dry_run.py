"""Ten predeclared scenes; real batch2 backward + batch8 inference, ZERO updates."""
from pathlib import Path
import argparse,csv,gc,hashlib,json,os,sys,time,traceback
ROOT=Path(__file__).resolve().parents[2];sys.dont_write_bytecode=True;sys.path.insert(0,str(ROOT/'src'))
os.environ['CUBLAS_WORKSPACE_CONFIG']=':4096:8';os.environ['OMP_NUM_THREADS']='1';os.environ['MKL_NUM_THREADS']='1'
import torch
from yuntapr.experimental.core_innovation.stage4 import *
from yuntapr.experimental.core_innovation.stage4.data import PopulationPlan,BatchReader
from yuntapr.experimental.core_innovation.stage4.engine import resources,paired_models,forward,write,state_digest,parameter_groups,clip_and_check,epoch_order,lr_for_update
from yuntapr.experimental.core_innovation.stage4.evaluation import Evaluation,paired_difference
from yuntapr.experimental.core_innovation.stage3.planning import digest
torch.set_num_threads(1)


def main(a):
    out=a.output.resolve()
    if not out.is_relative_to(ROOT/'docs/core_stage4/.local') or out.exists():raise PermissionError('New isolated private dry-run directory required')
    out.mkdir(parents=True)
    # Guard both optimizer construction and step, while backward is permitted.
    counts=dict(optimizer_constructions=0,optimizer_steps=0)
    def forbidden_init(*args,**kw):counts['optimizer_constructions']+=1;raise PermissionError('DRY_RUN_ZERO_OPTIMIZER')
    def forbidden_step(*args,**kw):counts['optimizer_steps']+=1;raise PermissionError('DRY_RUN_ZERO_UPDATES')
    torch.optim.Optimizer.__init__=forbidden_init;torch.optim.AdamW.step=forbidden_step
    plan=PopulationPlan(a.stage3_run,a.request,root=ROOT);selection=plan.dry_ids()
    if len(selection['Train'])!=2 or len(selection['Development'])!=8:raise ValueError('Declared May-1/2 dry subset unavailable')
    admission=resources();write(out/'selection.json',dict(ids=selection,selection_rule='First two Train May1, first eight Dev May1/2, manifest order; not rain-selected',seed=DRY_SEED,data=plan.identity,admission=admission))
    reader=BatchReader(plan,selection,out/'reads',decision_id='RESEARCHER_STAGE4_REAL_SMALL_BATCH_DRY_RUN_20261024')
    try:
        train=reader.batch('Train',selection['Train']);dev=reader.batch('Development',selection['Development']);reads=reader.meter.totals()
    finally:reader.close()
    # Necessary normalized tensor cache permits changed-code checks without any
    # further raw opens. These private tensor files are never Git artifacts.
    for role,b in (('train',train),('dev',dev)):
        with (out/(role+'_batch.pt')).open('xb') as f:torch.save(b,f)
    write(out/'batch_receipt.json',dict(actual_reads=reads,train_ids=train.ids,dev_ids=dev.ids,data=plan.identity,
        tensor_sha256={k:hashlib.sha256((out/(k+'_batch.pt')).read_bytes()).hexdigest() for k in ('train','dev')},optimizer_counts=counts))
    print(json.dumps(dict(event='BATCHES_LOADED',train=list(train.x.shape),dev=list(dev.x.shape),environment=list(dev.environment.shape),actual_reads=reads)),flush=True)
    with (ROOT/'docs/b0_pretraining_closure/runs/run_20260930T095416Z/formal_sample_eligibility_2023_2024.csv').open(encoding='utf-8-sig',newline='') as f:
        strong=tuple(r['window_start'] for r in csv.DictReader(f) if r['window_start'].startswith('2024') and float(r['imerg_max_yunnan_mmhr'] or 0)>=20)
    models=paired_models(DRY_SEED,ROOT);initial_common={kind:state_digest(dict(backbone=m.backbone.state_dict(),heads=m.heads.state_dict())) for kind,m in models.items()}
    if initial_common['B3']!=initial_common['B4']:raise AssertionError('Common initialization mismatch')
    results={};reports={};first=None
    for kind in ('B3','B4'):
        resources();model=models.pop(kind).cuda();before=state_digest(model.state_dict());_,grouping=parameter_groups(model,check_counts=False)
        b=train.to('cuda');model.train();torch.cuda.synchronize();torch.cuda.reset_peak_memory_stats();start=time.perf_counter()
        with torch.autocast('cuda',dtype=torch.bfloat16):o,loss=forward(model,b)
        loss.training_objective.backward();clip=clip_and_check(model);torch.cuda.synchronize()
        training=dict(batch=len(b.ids),seconds=time.perf_counter()-start,peak_allocated_bytes=torch.cuda.max_memory_allocated(),peak_reserved_bytes=torch.cuda.max_memory_reserved(),
            all_gradients_finite=True,loss_finite=bool(torch.isfinite(loss.training_objective)),n_valid=loss.n_valid,n_rain=loss.n_rain,**clip)
        model.zero_grad(set_to_none=True);del b,o,loss;gc.collect();torch.cuda.empty_cache()
        if before!=state_digest(model.state_dict()):raise AssertionError('Backward changed parameters/buffers')
        b=dev.to('cuda');model.eval();torch.cuda.synchronize();torch.cuda.reset_peak_memory_stats();start=time.perf_counter()
        with torch.no_grad(),torch.autocast('cuda',dtype=torch.bfloat16):o,loss=forward(model,b)
        torch.cuda.synchronize();validation=dict(batch=len(b.ids),seconds=time.perf_counter()-start,peak_allocated_bytes=torch.cuda.max_memory_allocated(),peak_reserved_bytes=torch.cuda.max_memory_reserved(),n_valid=loss.n_valid)
        ev=Evaluation(dev.ids,dev.analyses,plan.identity,out/(kind+'_metrics'),strong_scene_ids=strong)
        try:ev.add(o,b);reports[kind]=ev.finish()
        finally:ev.close()
        outputs=(o.rain_prob.detach().cpu(),o.conditional_quantiles_log.detach().cpu())
        if first is None:first=outputs
        elif not all(torch.equal(x,y) for x,y in zip(first,outputs)):raise AssertionError('Zero-residual initial paired predictions differ')
        if before!=state_digest(model.state_dict()):raise AssertionError('Validation changed parameters/buffers')
        parameters=sum(p.numel() for p in model.parameters())
        estimated_adam_extra=8*parameters+8*max(p.numel() for p in model.parameters())
        results[kind]=dict(parameters=parameters,initial_sha256=before,common_initial_sha256=initial_common[kind],grouping=grouping,
            training_probe=training,validation_probe=validation,weights_unchanged=True,optimizer_constructed=False,optimizer_updates=0,
            estimated_training_peak_with_adamw_and_512MiB_margin=training['peak_allocated_bytes']+estimated_adam_extra+512*1024**2,
            estimate_limitation='AdamW buffers/step not allocated or executed; estimate is not measured optimizer-step peak')
        print(json.dumps(dict(event='MODEL_DRY_PASS',model=kind,parameters=parameters,training=training,validation=validation)),flush=True)
        del b,o,loss,model,outputs;gc.collect();torch.cuda.empty_cache()
    difference=paired_difference(reports['B3'],reports['B4'])
    write(out/'untrained_metrics_private.json',dict(scope='UNTRAINED_DRY_CHECK_NOT_SCIENTIFIC_RESULTS',models=reports,paired=difference))
    orders={str(e):digest(epoch_order(plan.ids('Train'),DRY_SEED,e)) for e in range(1,10)}
    result=dict(status='PASS_REAL_BATCH_DRY_RUN_ZERO_UPDATES',data=plan.identity,dry_seed=DRY_SEED,formal_seed=None,models=results,actual_reads=reads,
        shared_initial_predictions_exact=True,order_sha256=orders,updates_per_epoch=STEPS,updates_per_model=EPOCHS*STEPS,paired_candidate_cap=PAIR_CAP,
        validation_batches_per_epoch=121,paired_validation_batches=2178,scheduler=dict(steps_per_epoch=STEPS,warmup=STEPS,horizon=50*STEPS,
            lr_first=lr_for_update(1,steps_per_epoch=STEPS),lr_480=lr_for_update(480,steps_per_epoch=STEPS),lr_4320=lr_for_update(4320,steps_per_epoch=STEPS)),
        optimizer_counts=counts,formal_training_started=False,raw_2025_reads=0,new_statistics_fitted=False,
        pending=['Formal seed, E0/9-epoch budget and launch authorization','MEE13 width16 target-residual and produced scalers scientific freeze','Fixed f006 coverage/time bias acceptance','Pinned target DEM and altitude strata for real high-altitude diagnostics'],
        final_resources=resources())
    if counts!={'optimizer_constructions':0,'optimizer_steps':0}:raise AssertionError('Optimizer guard activated')
    write(out/'completion.json',result);print(json.dumps(dict(event='COMPLETED',status=result['status'],paired_candidate_cap=PAIR_CAP,optimizer_counts=counts)),flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--stage3-run',type=Path,required=True);p.add_argument('--request',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    try:main(a)
    except BaseException as exc:
        if a.output.exists() and not (a.output/'failure.json').exists():write(a.output/'failure.json',dict(status='STOPPED_NO_AUTOMATIC_RETRY',error=type(exc).__name__+': '+str(exc),traceback=traceback.format_exc()))
        traceback.print_exc();raise SystemExit(1)
