"""Exact approved B1/E1 epoch6 LAST; restore model/AdamW/scheduler/RNG before replay."""


def validate_history_metrics(history,payload):
    from .protocol import digest
    if digest(history['train'])!=digest(payload['train']):raise ValueError('AUTHORIZED_LAST_TRAIN_METRICS')
    if digest(history['development'])!=digest(payload['validation']):raise ValueError('AUTHORIZED_LAST_DEVELOPMENT_METRICS')
    return dict(train_sha256=digest(payload['train']),validation_sha256=digest(payload['validation']))


def load_authorized_last(identity,signatures,opt_template,train_ids,dev_ids):
    from .ancestor import Guard,SOURCE_PREFIX,SOURCE_CP,lexical
    from .protocol import LIVE_ROOT,LAST_SHA,SOURCE_EPOCH,SOURCE_UPDATE,SOURCE_RUN
    from yuntapr.training.phase_b_v2_seed2027_b0_e1_recovery_v1.checkpoint import Contract,Store
    with Guard(identity['code']['failed_ancestor_sha256']) as guard:
        old=guard.pool.metadata[SOURCE_PREFIX+'.local/'+SOURCE_RUN+'/identity.json']
        for key in ('run_id','model','arm','seed','alpha','gamma','lambda_q','design','statistics','data','limits','initial_sha256','warm_start'):
            if old[key]!=identity[key]:raise ValueError('ADOPTED_LAST_SCIENTIFIC_IDENTITY_'+key)
        contract=Contract(old,signatures,opt_template,identity['initial_sha256'],train_ids,dev_ids)
        root=lexical(SOURCE_CP+'LAST_epoch_06.pt').parent
        store=Store.reopen_owned(root,contract,SOURCE_EPOCH,LAST_SHA)
        try:payload=store.read(root/f'LAST_epoch_{SOURCE_EPOCH:02d}.ref.json')
        finally:store.close()
        if payload['epoch']!=6 or payload['update']!=31368 or payload['quota']['reserved']!=260409:raise ValueError('EXACT_AUTHORIZED_LAST_BOUNDARY')
        history=guard.pool.metadata[SOURCE_PREFIX+'.local/'+SOURCE_RUN+'/progress.json']['epochs']
        if [e['epoch'] for e in history]!=list(range(1,7)) or history[-1]['checkpoint']['payload_sha256']!=LAST_SHA:raise ValueError('AUTHORIZED_LAST_HISTORY')
        validate_history_metrics(history[-1],payload)
        return payload,history


def apply_validated_state(model,optimizer,schedule,payload):
    # Existing exact restoration algorithm; no historical store mutation.
    from yuntapr.training.phase_b_v2_seed2027_b1_epoch7_recovery_v7.recovery import apply_validated_state as restore
    return restore(model,optimizer,schedule,payload)
