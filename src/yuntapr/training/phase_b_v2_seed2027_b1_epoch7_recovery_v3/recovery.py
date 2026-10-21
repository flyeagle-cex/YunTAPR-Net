"""Explicit human-authorized B1 epoch7 adoption, then clean same-campaign pauses."""

def validate_history_metrics(history,payload):
    """Compare reports with the frozen JSON receipt algorithm, preserving order."""
    from .protocol import digest
    if digest(history['train'])!=digest(payload['train']):raise ValueError('AUTHORIZED_LAST_TRAIN_METRICS')
    if digest(history['development'])!=digest(payload['validation']):raise ValueError('AUTHORIZED_LAST_DEVELOPMENT_METRICS')
    return dict(train_sha256=digest(payload['train']),validation_sha256=digest(payload['validation']))

def load_authorized_last(identity, signatures, opt_template, train_ids, dev_ids):
    """Validate the exact old envelope before touching any live model state."""
    from .ancestor import Guard,RECOVERY_PREFIX as PREFIX,SOURCE_CP as CP,RUN
    from .protocol import ROOT,LAST_SHA,SOURCE_EPOCH,SOURCE_UPDATE
    from yuntapr.training.phase_b_v2_seed2027_epoch2_recovery_v2.checkpoint import Contract, Store
    with Guard(identity['code']['failed_ancestor_sha256']) as guard:
        old = guard.pool.metadata[PREFIX+'.local/'+RUN+'/identity.json']
        for key in ('run_id','model','arm','seed','alpha','gamma','lambda_q','design',
                    'statistics','data','limits','initial_sha256','warm_start'):
            if old[key] != identity[key]:raise ValueError('ADOPTED_LAST_SCIENTIFIC_IDENTITY_'+key)
        contract = Contract(old, signatures, opt_template, identity['initial_sha256'], train_ids, dev_ids)
        store = Store.reopen_owned(ROOT/CP, contract, SOURCE_EPOCH, LAST_SHA)
        try:payload = store.read(ROOT/CP/f'LAST_epoch_{SOURCE_EPOCH:02d}.ref.json')
        finally:store.close()
        if payload['epoch']!=SOURCE_EPOCH or payload['update']!=SOURCE_UPDATE or payload['quota']['reserved']!=159607:
            raise ValueError('EXACT_AUTHORIZED_LAST_BOUNDARY')
        history = guard.pool.metadata[PREFIX+'.local/'+RUN+'/progress.json']['epochs']
        if [r['epoch'] for r in history]!=list(range(1,SOURCE_EPOCH+1)) or history[-1]['checkpoint']['payload_sha256']!=LAST_SHA:
            raise ValueError('AUTHORIZED_LAST_HISTORY')
        validate_history_metrics(history[-1],payload)
        return payload, history
def apply_validated_state(model, optimizer, schedule, payload) -> dict:
    """Called only AFTER full contract validation; no update or RNG reseeding."""
    from yuntapr.experimental.phase_b_v2_runner_candidate import rng
    from yuntapr.training.phase_a_protocol import state_digest
    from .engine import cpu_tree
    rng.validate(payload['rng'])
    model.load_state_dict(payload['model'], strict=True)
    optimizer.load_state_dict(payload['optimizer'])
    schedule.load_state_dict(payload['scheduler'])
    if state_digest(model.state_dict()) != state_digest(payload['model']):
        raise ValueError('MODEL_RESTORE_NOT_BIT_IDENTICAL')
    if state_digest(cpu_tree(optimizer.state_dict())) != state_digest(payload['optimizer']):
        raise ValueError('ADAMW_RESTORE_NOT_BIT_IDENTICAL')
    if schedule.state_dict() != payload['scheduler']:
        raise ValueError('SCHEDULER_RESTORE_NOT_EXACT')
    rng.restore(payload['rng'])
    if state_digest(cpu_tree(rng.capture())) != state_digest(payload['rng']):
        raise ValueError('RNG_RESTORE_NOT_EXACT')
    return dict(model_sha256=state_digest(payload['model']), optimizer_sha256=state_digest(payload['optimizer']),
                rng_sha256=state_digest(payload['rng']), scheduler=payload['scheduler'],
                all_state_verified_before_first_resumed_step=True)
