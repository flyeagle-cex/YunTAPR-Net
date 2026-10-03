"""Separately authorized fixed shared Phase-A loop; no training by default."""
import argparse,datetime,gc,json,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT/'src'),str(ROOT),str(ROOT/'scripts')]
import torch
from torch.utils.data import DataLoader
from yuntapr.training.paired_phase_a import *
from yuntapr.training.phase_a_protocol import seed_reproducibility
from yuntapr.training.phase_a_validation import GlobalValidationAccumulator
from yuntapr.training.formal_phase_a import train_numerators
from yuntapr.models.b1 import paired_models
from yuntapr.data.dataset_b1 import TemporalDataset,STAGE_ROOT,make_batch,collate,worker_init,install_source_guard
from yuntapr.data.masks import read_frozen_yunnan_mask
from yuntapr.spatial.sp04_mapping import load_sp04


def execute_update(model,optimizer,batch,u):
    started=time.perf_counter();result,out=forward_backward_clip(model,optimizer,batch,u)
    optimizer.step()
    if any(not torch.isfinite(p).all() for p in model.parameters()) or any(not torch.isfinite(v).all() for s in optimizer.state.values() for v in s.values() if isinstance(v,torch.Tensor)):raise FloatingPointError('Nonfinite state after optimizer update')
    torch.cuda.synchronize();result['wall_seconds']=time.perf_counter()-started
    return result,out


def main(kind,argv=None):
    parser=argparse.ArgumentParser(description='Separate researcher authorization required; no default fitting')
    parser.add_argument('--authorization');parser.add_argument('--authorization-sha256');parser.add_argument('--resume-run-id')
    args=parser.parse_args(argv)
    # Absent authorization is rejected even before the metadata contract loader.
    if not args.authorization or not args.authorization_sha256:raise PermissionError('Separate researcher authorization required before source/model/optimizer')
    contract=RunnerContract.load();auth=Authorization.load(args.authorization,args.authorization_sha256,contract,kind)
    from train_b0_phase_b_finalfit_v1 import environment
    env=environment();seed_reproducibility();install_source_guard()
    mapping=load_sp04();mask=read_frozen_yunnan_mask(Path(contract.protocol['identity']['yunnan_mask']['path']),mapping)
    frames=load_frames();anchor,temporal,initial=paired_models();model=temporal if kind=='B1' else anchor
    del anchor,temporal;gc.collect();model=model.cuda();optimizer,groups=optimizer_for(model,kind)
    runid=args.resume_run_id or 'run_'+datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%S_%fZ')
    if not runid.startswith('run_') or Path(runid).name!=runid:raise ValueError('Safe run ID required')
    public=ROOT/'docs/formal_training'/('b1_phase_a' if kind=='B1' else 'b0_matched_phase_a')/'runs'/runid
    expected=checkpoint_expected(contract,auth,kind,runid,env,groups,initial);selection=ValidationSelection();registry={};history=[]
    if args.resume_run_id:
        registry=json.loads((public/'checkpoint_registry.json').read_text());payload=load_checkpoint(registry['LAST'],expected,model,optimizer)
        selection=ValidationSelection(**payload['selection']);history=json.loads((public/'training_validation_history.json').read_text())
        # Checkpoint is authoritative after a crash between durable LAST and history write.
        history=[r for r in history if r['epoch']<=selection.completed_epoch]
        if not history or history[-1]['epoch']!=selection.completed_epoch:history.append({'epoch':selection.completed_epoch,'validation':payload['validation'],'recovered_from_verified_LAST':True})
    else:public.mkdir(parents=True,exist_ok=False)
    datasets={y:TemporalDataset(kind,contract.records[kind,y],frames,mapping,mask,STAGE_ROOT/('paired_'+runid)/str(y)) for y in (2023,2024)}
    loaderargs=dict(num_workers=2,pin_memory=False,persistent_workers=False,prefetch_factor=1,worker_init_fn=worker_init,collate_fn=collate)
    if selection.non_improvement_count>=8 or selection.completed_epoch==50:
        atomic_json(public/'final_status.json',{'status':'FORMAL_PHASE_A_COMPLETE','completed_epoch':selection.completed_epoch,'additional_optimizer_steps':0});return
    for epoch in range(selection.completed_epoch+1,51):
        order,plan=batch_plan(epoch-1);coverage=EpochCoverage(epoch);socc=sqr=0.;nvalid=0;clips=0;pre_norms=[];post_norms=[]
        model.train();loader=DataLoader(datasets[2023],batch_sampler=plan,**loaderargs)
        for j,items in enumerate(loader,1):
            batch=make_batch(items);u=(epoch-1)*STEPS+j;metrics,out=execute_update(model,optimizer,batch,u)
            coverage.add(batch.indices,metrics['actual_denominator']);a,b,n,_=train_numerators(out,batch);socc+=a;sqr+=b;nvalid+=n
            clips+=int(metrics['clipped']);pre_norms.append(metrics['pre_clip_norm']);post_norms.append(metrics['post_clip_norm']);del batch,out,items
        completed=coverage.complete();acc=GlobalValidationAccumulator();seen=[];model.eval()
        with torch.inference_mode():
            for items in DataLoader(datasets[2024],batch_size=contract.protocol['validation']['batch'],shuffle=False,drop_last=False,**loaderargs):
                batch=make_batch(items);out,_=forward_loss(model,batch);acc.add(out,batch.y_imerg,batch.imerg_valid_mask,batch.yunnan_eval_mask);seen.extend(batch.indices);del batch,out,items
        if seen!=list(range(VAL)) or acc.n_valid!=VAL*3430:raise ValueError('Full fixed-order validation required')
        val=acc.report();decision=selection.update(epoch,val['global_val_core_loss'])
        payload=payload_for(model,optimizer,expected,selection,epoch,completed,val);registry=save_checkpoint(public,payload,expected,registry,decision['checkpoint_selected'])
        history.append({'epoch':epoch,'global_update':epoch*STEPS,'train':{'S_occ':socc,'S_qr':sqr,'N_valid':nvalid,'global_core_loss':(socc+sqr)/nvalid},'validation':val,'selection':decision,'clip_count':clips,'clip_fraction':clips/STEPS,'pre_clip_norm':pre_norms,'post_clip_norm':post_norms})
        atomic_json(public/'training_validation_history.json',history)
        atomic_json(public/'run_manifest.json',expected)
        del payload;gc.collect()
        if decision['stop']:break
    atomic_json(public/'final_status.json',{'status':'FORMAL_PHASE_A_COMPLETE','completed_epoch':selection.completed_epoch,'global_update':selection.completed_epoch*STEPS,'BEST':registry['BEST'],'LAST':registry['LAST'],'2025_PIXELS_READ':0})
