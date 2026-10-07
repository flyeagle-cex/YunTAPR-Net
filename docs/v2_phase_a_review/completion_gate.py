"""Read-only metadata gate. Does not load a model, checkpoint binary or raw data."""
import argparse
import json
import math
from pathlib import Path


def reconcile_selection(rows):
    best = es = None
    best_epoch = es_epoch = counter = 0
    for epoch, row in enumerate(rows, 1):
        if epoch > 50 or counter >= 8 or row['epoch'] != epoch:
            raise ValueError('Epoch order/termination violation')
        value = row['validation']['global_val_core_loss']
        if not math.isfinite(value): raise ValueError('Nonfinite selection value')
        selected = best is None or value < best
        improved = es is None or value < es - 1e-4
        if selected: best, best_epoch = value, epoch
        if improved: es, es_epoch, counter = value, epoch, 0
        else: counter += 1
        expected = {'checkpoint_selected': selected, 'early_stop_improvement': improved, 'stop': counter >= 8}
        if row['decision'] != expected: raise ValueError('Decision differs from frozen core-loss rule')
        if row['selection'] != {'best_checkpoint_value':best, 'selected_checkpoint_epoch':best_epoch,
                               'early_stop_best':es, 'non_improvement_count':counter, 'completed_epoch':epoch}:
            raise ValueError('Selection state does not reconcile')
    if not rows: raise ValueError('No complete epochs')
    return {'completed_epoch':len(rows),'best_checkpoint_epoch':best_epoch,'best_es_epoch':es_epoch,
            'best_es_value':es,'final_early_stop_counter':counter,
            'termination_reason':'EARLY_STOP_PATIENCE_8' if counter >= 8 else ('MAX_EPOCH_50' if len(rows)==50 else 'NOT_TERMINATED')}


def load(path): return json.loads(Path(path).read_text(encoding='utf-8'))


def check_pair(auth_path):
    auth_path=Path(auth_path);auth=load(auth_path);public=Path(auth['publication_root'])
    required=[auth_path.parent/'process_exit.json',public/'pair_training_completed.json']
    required += [public/k/'final_report.json' for k in auth['models']]
    missing=[str(p) for p in required if not p.is_file()]
    if missing:return {'status':'WAITING_FOR_BOTH_PHASE_A_COMPLETION','missing':missing,'REVIEW_INFERENCE_ALLOWED':False}
    if load(required[0])['exit_code']!=0:raise ValueError('Runner failed; no review launch')
    if load(required[1])['status']!='TRAINING_COMPLETE_PUBLICATION_PENDING':raise ValueError('Missing pair completion marker')
    proof={}
    for kind in auth['models']:
        d=public/kind;final=load(d/'final_report.json');rows=load(d/'training_validation_history.json')
        if final['status']!='COMPLETE':raise ValueError('Model not normally complete')
        expected=reconcile_selection(rows)
        if expected['termination_reason']=='NOT_TERMINATED' or any(final[k]!=v for k,v in expected.items()):
            raise ValueError('Early-stop/final state disagreement')
        registry=load(d/'checkpoint_registry.json')
        if len(registry['epochs'])!=len(rows):raise ValueError('Incomplete checkpoint registry')
        if registry['LAST']!=registry['epochs'][-1] or registry['BEST']!=registry['epochs'][expected['best_checkpoint_epoch']-1]:
            raise ValueError('BEST/LAST does not follow fixed selection')
        root=(Path(auth['checkpoint_roots'][kind])/auth['run_ids'][kind]).resolve()
        for row,ref in zip(rows,registry['epochs']):
            epoch=row['epoch'];marker=load(d/f'epoch_{epoch:03d}_complete.json')
            if marker['status']!='PASS' or marker['checkpoint']!=ref or marker['audit']['status']!='PASS':
                raise ValueError('Checkpoint has no completed audit marker')
            if row['checkpoint']!=ref or ref['epoch']!=epoch or ref['run_id']!=auth['run_ids'][kind] or ref['model']!=kind:
                raise ValueError('Checkpoint identity mismatch')
            if not Path(ref['absolute_local_path']).resolve().is_relative_to(root):raise ValueError('Checkpoint root mismatch')
            t,v=row['training'],row['validation']
            if (t['scenes'],t['steps'],t['N_valid'],t['exactly_once'])!=(10455,5228,35860650,True):raise ValueError('Train coverage mismatch')
            if (v['scenes'],v['forwards'],v['N_valid'])!=(10501,1313,36018430):raise ValueError('Validation coverage mismatch')
            for phase,forwards,scenes in [('TRAIN',5228,10455),('VALIDATION',1313,10501)]:
                diag=row['diagnostics'][phase]
                if diag['forwards']!=forwards or diag['scenes']!=scenes:raise ValueError('Diagnostic coverage mismatch')
            if row['io']['2025_RAW_ACCESS'] or row['io']['2025_PIXELS_READ'] or row['io']['DENIED_ATTEMPTS']:
                raise ValueError('Source firewall violated')
        proof[kind]={**expected,'BEST':registry['BEST'],'LAST':registry['LAST']}
    return {'status':'METADATA_COMPLETION_GATE_PASS','REVIEW_INFERENCE_ALLOWED':False,
            'next_gate':'Rehash code/config/data identities, all local epoch artifacts and checkpoint bytes; provenance before model state application',
            'models':proof,'V2_PHASE_B_AUTHORIZED':False,'2025_RAW_ACCESS':0}


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--authorization',type=Path,required=True)
    print(json.dumps(check_pair(p.parse_args().authorization),ensure_ascii=False,indent=2))
