"""Independent read-only 2024 BEST review after BOTH Phase-A runs complete.

No optimizer construction/state application, backward, training or physical transform.
Without --execute this command only reads completion metadata.
"""
import argparse
import gc
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace
from completion_gate import check_pair


def read(p):return json.loads(Path(p).read_text(encoding='utf-8'))
def digest(p):
    with Path(p).open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()
def verify_ref(ref):
    p=Path(ref['absolute_local_path'])
    if p.stat().st_size!=ref['bytes'] or digest(p)!=ref['sha256']:raise ValueError('Artifact identity changed: '+str(p))


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--authorization',type=Path,required=True)
    parser.add_argument('--authorization-sha256',required=True)
    parser.add_argument('--execute',action='store_true')
    args=parser.parse_args()
    if digest(args.authorization)!=args.authorization_sha256:raise PermissionError('Authorization SHA mismatch')
    proof=check_pair(args.authorization)
    if proof['status']!='METADATA_COMPLETION_GATE_PASS' or not args.execute:
        print(json.dumps(proof,ensure_ascii=False));return
    auth=read(args.authorization);execution=Path(auth['execution_checkout']);repo=Path(auth['publication_repository'])
    if Path(r'F:\pytorch\Research\outputs\formal_training\paired_v2_gpu.lock').exists():raise PermissionError('Formal GPU lock still held')
    for rel,sha in auth['code_sha256'].items():
        if digest(execution/rel)!=sha:raise ValueError('Pinned implementation changed: '+rel)
    if subprocess.check_output(['git','rev-parse','HEAD'],cwd=execution,text=True).strip()!=auth['execution_commit']:
        raise ValueError('Execution commit changed')
    if digest(auth['preflight_path'])!=auth['preflight_sha256']:raise ValueError('Preflight changed')
    gate=read(auth['preflight_path'])
    # Imports below this line cannot occur until the metadata gate has passed.
    sys.path[:0]=[str(execution/'src'),str(execution/'scripts'),str(execution)]
    import torch
    from yuntapr.training import formal_phase_a_v2 as f
    from yuntapr.training.checkpoint_v2 import verify_file
    from paired_phase_a_v2.preflight import environment
    from metrics import ReviewMetrics
    f.seed_reproducibility()
    if environment()!=gate['environment']:raise ValueError('Review environment differs from frozen forward environment')
    contract=f.Contract.load()
    if contract.code!=auth['code_sha256']:raise ValueError('Code SHA mismatch')
    sources={k:v for k,v in contract.sources().items() if v['year']==2024}
    if not sources or any(v['year']!=2024 for v in sources.values()):raise ValueError('2024-only source scope required')
    rid=f.run_id();out=repo/'docs/v2_phase_a_review/runs'/rid;out.mkdir(parents=True,exist_ok=False)
    checkpoint_refs=[];all_artifacts=[];expected_provenance={}
    public=Path(auth['publication_root'])
    try:
        for kind in auth['models']:
            local=Path(auth['checkpoint_roots'][kind])/auth['run_ids'][kind]
            history=read(public/kind/'training_validation_history.json')
            for row in history:
                verify_ref(row['checkpoint']);checkpoint_refs.append(row['checkpoint'])
                for ref in row['local_epoch_artifacts']:
                    p=Path(ref['absolute_local_path']).resolve()
                    if not p.is_relative_to(local.resolve()) or p.suffix not in ('.json','.jsonl','.csv'):
                        raise ValueError('Unexpected epoch artifact scope')
                    verify_ref(ref);all_artifacts.append(ref)
            # Bind the provenance belonging to the actual selected checkpoint attempt.
            selected=proof['models'][kind]['BEST'];attempt=Path(selected['absolute_local_path']).parent.name
            prov=read(local/'audit'/attempt/'provenance.json')
            for key in ('pair_id','protocol_sha256','head_sha256','normalization_sha256','execution_commit','code_sha256'):
                if prov[key]!=auth[key]:raise ValueError('Checkpoint provenance disagrees with authorization: '+key)
            if prov['origin_authorization_sha256']!=proof['origin_authorization_sha256'] or prov['run_id']!=auth['run_ids'][kind]:
                raise ValueError('Checkpoint belongs to another authorization/run')
            if prov['initialization']['models']!=auth['initial_state_sha256'] or prov['identity']!=contract.protocol['identity']:
                raise ValueError('Initialization/data identity mismatch')
            expected_provenance[kind]=prov
        f.atomic_json(out/'pre_inference_identity.json',{'metadata_gate':proof,'checkpoint_refs':checkpoint_refs,
            'epoch_artifacts':all_artifacts,'authorization_sha256':args.authorization_sha256,
            'review_code_sha256':{p.name:digest(p) for p in Path(__file__).parent.glob('*.py')},
            'executed_implementation':auth['execution_commit'],'evaluation_year':2024},immutable=True)
        results={}
        for kind in auth['models']:
            target=out/kind;target.mkdir()
            ref=proof['models'][kind]['BEST'];payload=verify_file(ref,expected_provenance[kind])
            model=f.FACTORIES[kind](numerics=f.CandidateNumerics(epsilon_w=1e-4,epsilon_span=1e-4),root=contract.root)
            model.load_state_dict(payload['model'],strict=True);model.requires_grad_(False);model.eval();model.cuda()
            initial=f.state_digest(model.state_dict())
            if initial!=payload['state_sha256']['model']:raise ValueError('BEST model state application mismatch')
            expected_validation=payload['validation'];del payload
            firewall=f.SourceFirewall(sources,target/'raw_access_parent.jsonl',mask_path=contract.protocol['identity']['yunnan_mask']['path'])
            counters=SimpleNamespace(FORWARD_CALLS=0,TRAIN_FORWARDS=0,VALIDATION_FORWARDS=0)
            with firewall.installed(),torch.inference_mode():
                sets,mask=f.datasets(contract,kind,f.data.STAGE_ROOT/('v2_readonly_review_'+rid+'_'+kind),target,sources)
                metrics=ReviewMetrics();diag=f.UpperTailDiagnostics(mask,'VALIDATION',target/'diagnostics.jsonl')
                order=[];exposures=0
                with f.loader_items(f.loader(sets[2024],validation=True)) as batches:
                    for step,items in enumerate(batches,1):
                        batch=f.data.make_batch(items);output,_=f.forward_loss(model,batch,counters,'VALIDATION')
                        metrics.add(output,batch.y_imerg,batch.imerg_valid_mask,batch.yunnan_eval_mask)
                        diag.observe(output.conditional_quantiles_log,batch.sample_ids)
                        order.extend(batch.indices);exposures+=sum(len(item['staging']) for item in items)
                        f.progress(out,status='RUNNING',phase='READ_ONLY_2024_BEST_REVIEW',model=kind,step=step,
                            REVIEW_FORWARD_CALLS=counters.FORWARD_CALLS,BACKWARD_CALLS=0,OPTIMIZER_STEPS=0,
                            FORMAL_OPTIMIZER_STEPS_ADDED=0,**{'2025_RAW_ACCESS':0,'2025_PIXELS_READ':0})
                        del batch,output,items
                if order!=list(range(10501)):raise ValueError('Incomplete/faulty fixed-order review')
                report=metrics.report()
                for key in expected_validation:
                    if report[key]!=expected_validation[key]:raise ValueError('BEST validation replay disagrees: '+key)
                if f.state_digest(model.state_dict())!=initial:raise ValueError('Review changed model state')
                io=f.reconcile_io(target)
                if io['RAW_SOURCE_OPENS']!=2*exposures or io['DENIED_ATTEMPTS']:raise ValueError('Review source I/O mismatch')
                results[kind]={'BEST':ref,'metrics':report,'upper_tail_diagnostics':diag.report(),'io':io,
                    'ordered_sample_ids_sha256':f.state_digest([contract.records[kind,2024][i]['sample_id'] for i in order]),
                    'MODEL_PARAMETERS_UPDATED':False,'BACKWARD_CALLS':0,'OPTIMIZER_STEPS':0,'REVIEW_FORWARD_CALLS':counters.FORWARD_CALLS}
                f.atomic_json(target/'review.json',results[kind],immutable=True)
            del model,metrics,diag,sets;gc.collect();torch.cuda.empty_cache()
        for ref in checkpoint_refs:verify_ref(ref)
        packet={'status':'READ_ONLY_PAIRED_REVIEW_COMPLETE','pair_id':auth['pair_id'],'models':results,
            'MODEL_PARAMETERS_UPDATED':False,'BACKWARD_CALLS':0,'OPTIMIZER_STEPS':0,'FORMAL_OPTIMIZER_STEPS_ADDED':0,
            '2025_RAW_ACCESS':0,'2025_PIXELS_READ':0,'V2_PHASE_B_AUTHORIZED':False,'RESEARCHER_PHASE_A_REVIEW_REQUIRED':True,
            'scope':'2024 validation development comparison; no 2025 generalization claim; no new checkpoint/epoch selection'}
        f.atomic_json(out/'paired_comparison_packet.json',packet,immutable=True)
        f.progress(out,status='COMPLETE',phase='RESEARCHER_REVIEW_REQUIRED',FORMAL_OPTIMIZER_STEPS_ADDED=0)
        print(json.dumps({'status':'COMPLETE','run':str(out)}))
    except BaseException as exc:
        f.atomic_json(out/'failure.json',{'status':'FAILED_STOP','error':repr(exc),'automatic_retry':False},immutable=True)
        f.progress(out,status='FAILED_STOP',error=repr(exc));raise


if __name__=='__main__':main()
