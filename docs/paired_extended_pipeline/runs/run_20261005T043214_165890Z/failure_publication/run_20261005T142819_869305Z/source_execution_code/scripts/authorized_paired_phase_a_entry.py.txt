"""Approved audit-only loop adapter for the byte-identical frozen formal entries.

All model, data decoding, update, loss, scheduler, accumulation and selection
functions are inherited unchanged. This file supplies authorization and records.
"""
import argparse,datetime,gc,json,math,os,sys,traceback
from pathlib import Path
from dataclasses import asdict
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT/'src'),str(ROOT),str(ROOT/'scripts')]
import torch
from torch.utils.data import DataLoader
import paired_phase_a_entry as original
from yuntapr.training import paired_phase_a as frozen
from yuntapr.training.paired_phase_a_audit import *
from yuntapr.training.phase_a_protocol import seed_reproducibility,parameter_groups,ValidationSelection
from yuntapr.training.phase_a_validation import GlobalValidationAccumulator
from yuntapr.training.formal_phase_a import train_numerators
from yuntapr.models.b1 import paired_models
from yuntapr.data.masks import read_frozen_yunnan_mask
from yuntapr.spatial.sp04_mapping import load_sp04

def reject_before_construction(kind,argv):
    parser=argparse.ArgumentParser(description='Researcher-approved audit adapter, exact model-specific authorization required')
    parser.add_argument('--authorization',required=True);parser.add_argument('--authorization-sha256',required=True)
    parser.add_argument('--resume-run-id');args=parser.parse_args(argv)
    firewall=RawFirewall();firewall.install()
    # No raw source, model, optimizer, checkpoint or dataset is opened/constructed here.
    repository_json_path(args.authorization)
    contract=frozen.RunnerContract.load()
    auth=AuditedAuthorization.load(args.authorization,args.authorization_sha256,contract,kind)
    return args,contract,auth,firewall

def enrich_validation(report,scenes,support):
    report.update(validation_scenes=scenes,support_violation_count=support,
        coverage_error=[None if c is None else c-(i+.5)/32 for i,c in enumerate(report['per_tau_conditional_coverage'])])
    return report

def identity_order(contract,kind,year,indices):
    return state_digest([contract.records[kind,year][i]['sample_id'] for i in indices])

def main(kind,argv=None):
    args,contract,auth,firewall=reject_before_construction(kind,argv)
    runid=args.resume_run_id or auth.value['planned_run_id']
    if not re.fullmatch(r'run_\d{8}T\d{6}_\d{6}Z',runid):raise ValueError('Timestamped isolated run ID required')
    public=ROOT/'docs/formal_training'/('b1_phase_a' if kind=='B1' else 'b0_matched_phase_a')/'runs'/runid
    checkpoint_child=frozen.ROOTS[kind]/runid
    if not args.resume_run_id:
        if public.exists() or checkpoint_child.exists():raise FileExistsError('New output/checkpoint child must be absent before formal construction')
        public.mkdir(parents=True,exist_ok=False);checkpoint_child.mkdir(parents=True,exist_ok=False)
    elif not auth.value.get('resume_authorized',False):raise PermissionError('No automatic resume of an interrupted run')
    audit=RunAudit(public,kind);audit.event('AUTHORIZATION_AND_METADATA_GATE_PASS',authorization_sha256=auth.sha256)
    audit.snapshot(status='PRE_FORMAL_CONSTRUCTION_GATES_PASSED')
    registry={};history=[];lock=None;stage=data.STAGE_ROOT/('authorized_paired_'+runid)
    pair_root=repository_json_path(auth.value['pretraining_gate_path']).parent
    lock_path=pair_root/'gpu_sequential_execution.lock'
    try:
        lock=lock_path.open('x',encoding='utf8');lock.write(json.dumps({'model':kind,'run_id':runid,'pid':os.getpid()}));lock.flush();os.fsync(lock.fileno())
        from train_b0_phase_b_finalfit_v1 import environment
        env=environment();seed_reproducibility()
        mapping=load_sp04();mask=read_frozen_yunnan_mask(Path(contract.protocol['identity']['yunnan_mask']['path']),mapping)
        frames=data.load_frames()
        anchor,temporal,initial=paired_models();verify_initialization(anchor,temporal,initial)
        model=temporal if kind=='B1' else anchor
        del anchor,temporal;gc.collect()
        _,groups=parameter_groups(model,check_counts=False)
        if groups['counts']!=frozen.COUNTS[kind] or not groups['disjoint'] or not groups['complete_union']:
            raise ValueError('Frozen parameter groups failed before optimizer construction')
        model=model.cuda()
        if state_digest(model.state_dict())!=INITIAL[kind]:raise ValueError('Initial state changed during device transfer')
        optimizer,actual_groups=frozen.optimizer_for(model,kind)
        if actual_groups!=groups:raise ValueError('Optimizer group replay mismatch')
        expected=checkpoint_provenance(contract,auth,kind,runid,env,groups,initial)
        atomic_json(public/'run_manifest.json',expected)
        atomic_json(public/'first_update_identity_gate.json',{'status':'PASS','actual_initial_sha256':state_digest(model.state_dict()),
             'expected_initial_sha256':INITIAL[kind],'paired_initialization':initial,'parameter_groups':groups,
             'FORMAL_OPTIMIZER_STEPS':0,'historical_checkpoint_loaded':False,'2025_firewall_active':True})
        selection=ValidationSelection()
        if args.resume_run_id:
            registry=json.loads((public/'checkpoint_registry.json').read_text(encoding='utf8'))
            validate_resume_ancestry(auth,kind,runid,registry)
            # Verify BEST file ancestry without applying BEST model/optimizer state.
            best=registry['BEST'];bp=Path(best['absolute_local_path'])
            if bp.stat().st_size!=best['bytes'] or sha256(bp)!=best['sha256']:raise ValueError('BEST ancestry identity mismatch')
            with audit.instrument(model,optimizer):
                payload=frozen.load_checkpoint(registry['LAST'],expected,model,optimizer)
            selection=ValidationSelection(**payload['selection']);audit.completed_epoch=selection.completed_epoch
            n=selection.completed_epoch*5228
            audit.counters.FORMAL_OPTIMIZER_STEPS=n;audit.counters.OPTIMIZER_STEPS_COMPLETED=n;audit.counters.BACKWARD_CALLS=n
            audit.counters.TRAIN_FORWARD_CALLS=n;audit.counters.VALIDATION_FORWARD_CALLS=selection.completed_epoch*((10501+7)//8)
            audit.verified_last=registry['LAST']
            history=json.loads((public/'training_validation_history.json').read_text(encoding='utf8'))
            if len(history)!=selection.completed_epoch or history[-1]['epoch']!=selection.completed_epoch:raise ValueError('Resume history/ancestry mismatch')
            del payload
        allowed=allowed_sources(contract,kind,frames);firewall.allowed={firewall.key(p) for p in allowed};firewall.authorized=True
        firewall.log_path=public/f'raw_access_parent_{os.getpid()}.jsonl'
        context={'public':str(public),'authorization_path':str(Path(args.authorization).resolve()),
                 'authorization_sha256':auth.sha256,'allowed_sources':allowed}
        datasets={y:AuditedTemporalDataset(kind,contract.records[kind,y],frames,mapping,mask,stage/str(y)) for y in (2023,2024)}
        for dataset in datasets.values():dataset.audit_context=context
        loaderargs=dict(num_workers=2,pin_memory=False,persistent_workers=False,prefetch_factor=1,worker_init_fn=audited_worker_init,collate_fn=data.collate)
        audit.event('FORMAL_FRESH_RUN_READY',initial_sha256=INITIAL[kind],checkpoint_child=str(checkpoint_child))
        with audit.instrument(model,optimizer):
            for epoch in range(selection.completed_epoch+1,51):
                audit.epoch=epoch;audit.phase='TRAIN';audit.snapshot()
                order,plan=frozen.batch_plan(epoch-1);coverage=frozen.EpochCoverage(epoch)
                order_sha=identity_order(contract,kind,2023,order)
                audit.event('TRAIN_EPOCH_START',sample_order_identity_sha256=order_sha)
                socc=sqr=0.;nvalid=nrain=clips=0;pre_norms=[];post_norms=[];lr_start=None;lr_end=None
                model.train();loader=DataLoader(datasets[2023],batch_sampler=plan,**loaderargs)
                with loader_items(loader) as iterator:
                    for j,items in enumerate(iterator,1):
                        batch=data.make_batch(items);u=(epoch-1)*5228+j
                        if u==1 and state_digest(model.state_dict())!=INITIAL[kind]:raise ValueError('Pinned initial SHA failed immediately before first formal update')
                        metrics,out=original.execute_update(model,optimizer,batch,u)
                        coverage.add(batch.indices,metrics['actual_denominator'])
                        a,b,n,r=train_numerators(out,batch);socc+=a;sqr+=b;nvalid+=n;nrain+=r
                        clips+=int(metrics['clipped']);pre_norms.append(metrics['pre_clip_norm']);post_norms.append(metrics['post_clip_norm'])
                        if lr_start is None:lr_start=metrics['LR']
                        lr_end=metrics['LR']
                        audit.event('TRAIN_UPDATE_AUDITED',sample_ids=batch.sample_ids,**metrics)
                        if j%100==0 or j==5228:audit.snapshot(update=u,train_steps_this_epoch=j)
                        del batch,out,items
                completed=coverage.complete();acc=GlobalValidationAccumulator();seen=[];support=0
                audit.phase='VALIDATION';audit.event('FULL_VALIDATION_START');audit.snapshot();model.eval()
                with torch.inference_mode():
                    loader=DataLoader(datasets[2024],batch_size=8,shuffle=False,drop_last=False,**loaderargs)
                    with loader_items(loader) as iterator:
                        for j,items in enumerate(iterator,1):
                            batch=data.make_batch(items);out,_=frozen.forward_loss(model,batch)
                            support+=int((out.conditional_quantiles_log[:,0]<=math.log1p(.1)).sum())
                            acc.add(out,batch.y_imerg,batch.imerg_valid_mask,batch.yunnan_eval_mask);seen.extend(batch.indices)
                            if j%100==0:audit.snapshot(validation_scenes_seen=len(seen))
                            del batch,out,items
                if seen!=list(range(10501)) or acc.n_valid!=10501*3430:raise ValueError('Full fixed-order validation required')
                val=enrich_validation(acc.report(),len(seen),support)
                decision=selection.update(epoch,val['global_val_core_loss'])
                train={'S_occ':socc,'S_qr':sqr,'N_valid':nvalid,'N_rain':nrain,
                       'L_occ':socc/nvalid,'L_qr':sqr/nvalid,'global_core_loss':(socc+sqr)/nvalid,
                       'clip_count':clips,'clip_fraction':clips/5228,'pre_clip_norm':pre_norms,'post_clip_norm':post_norms,
                       'LR_start':lr_start,'LR_end':lr_end,'optimizer_steps':5228,'ordered_sample_identity_sha256':order_sha}
                validate_boundary_audit(audit,epoch,completed,train,val,order_sha)
                cleanup=staging_state(stage)
                if not cleanup['cleanup_success']:raise IOError('Owned staging cleanup failed at epoch boundary')
                audit.phase='CHECKPOINT_BOUNDARY'
                payload=frozen.payload_for(model,optimizer,expected,selection,epoch,completed,val,train)
                payload['ordered_sample_identity_sha256']=order_sha;payload['audit_counters']=asdict(audit.counters)
                payload['active_execution_authorization_sha256']=auth.sha256
                # frozen.save_checkpoint verifies file SHA, state SHA and roundtrip before LAST publication.
                registry=frozen.save_checkpoint(public,payload,expected,registry,decision['checkpoint_selected'])
                audit.verified_last=registry['LAST'];audit.completed_epoch=epoch
                row={'epoch':epoch,'global_update':epoch*5228,'train':train,'validation':val,'selection':decision,
                     'BEST_epoch':selection.selected_checkpoint_epoch,'BEST_val_core':selection.best_checkpoint_value,
                     'early_stop_counter':selection.non_improvement_count,'sample_order_identity_sha256':order_sha}
                history.append(row);atomic_json(public/'training_validation_history.json',history)
                audit.event('COMPLETED_EPOCH_BOUNDARY',val_core=val['global_val_core_loss'],BEST_epoch=selection.selected_checkpoint_epoch,
                            early_stop_counter=selection.non_improvement_count,LAST=registry['LAST'])
                audit.snapshot(validation_scenes_seen=10501)
                print(json.dumps({'model':kind,'epoch':epoch,'val_core':val['global_val_core_loss'],'BEST_epoch':selection.selected_checkpoint_epoch,
                                  'early_stop_counter':selection.non_improvement_count,'formal_steps':audit.counters.FORMAL_OPTIMIZER_STEPS}),flush=True)
                del payload,acc;gc.collect()
                if decision['stop']:break
        verify_history(auth.value['historical_snapshot_path'],auth.value['historical_snapshot_sha256'])
        if code_hashes()!=auth.value['code_hashes']:raise ValueError('Implementation changed during formal run')
        cleanup=staging_state(stage)
        if not cleanup['cleanup_success']:raise IOError('Owned staging cleanup failed')
        audit.phase='COMPLETE';audit.snapshot(status='FORMAL_PHASE_A_COMPLETE')
        status={'status':'FORMAL_PHASE_A_COMPLETE','model':kind,'run_id':runid,'completed_epoch':selection.completed_epoch,
                'selected_best_epoch':selection.selected_checkpoint_epoch,'selected_best_val_core':selection.best_checkpoint_value,
                'global_update':selection.completed_epoch*5228,'BEST':registry['BEST'],'LAST':registry['LAST'],
                **asdict(audit.counters),'2025_PIXELS_READ':0,'2025_RAW_ACCESS':0,'2025_MODEL_INFERENCE_SCENES':0,
                '2025_FINAL_TEST_EXECUTED':False,'Phase_B_authorized':False,'B2_authorized':False,
                'historical_files_byte_identical':True,'source_cleanup_state':cleanup}
        atomic_json(public/'final_status.json',status)
        audit.event('FORMAL_PHASE_A_COMPLETE')
        lock.close();lock=None;lock_path.unlink()
        return status
    except BaseException as error:
        try:cleanup=staging_state(stage)
        except BaseException as cleanup_error:cleanup={'cleanup_audit_error':repr(cleanup_error)}
        audit.preserve_failure(error,registry,cleanup)
        raise
    finally:
        if lock is not None:lock.close()
