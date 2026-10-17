"""Only verified clean same-campaign LAST continuation; no historical adoption."""
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
