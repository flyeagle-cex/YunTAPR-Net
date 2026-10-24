"""Real LAST validation/restore only: no forward, backward or optimizer.step."""
import importlib, json
from pathlib import Path
import operate
from yuntapr.training.phase_b_v2_seed2027_b1_e1_epoch6_recovery_v1 import protocol as p
from yuntapr.training.phase_b_v2_seed2027_b1_e1_epoch6_recovery_v1.admission import require_launch_headroom

def main():
    if p.DB.exists():raise PermissionError('RESTORE_PREFLIGHT_ONLY_BEFORE_LAUNCH')
    headroom=require_launch_headroom();release=p.verify_release()
    import torch
    torch.set_num_threads(1)
    for file in Path(p.__file__).parent.glob('*.py'):
        importlib.import_module('yuntapr.training.phase_b_v2_seed2027_b1_e1_epoch6_recovery_v1.'+file.stem)
    from yuntapr.training.phase_b_v2_seed2026_v2.data import Plan
    from yuntapr.experimental.phase_b_v2_real_forward_pilot.resources import memory
    class MetadataOnlyBudget:
        def __init__(self):self.bytes=0
        def admit_bytes(self,n):
            if not 0<n<128*1024**2:raise MemoryError('BOUNDED_METADATA_PREFLIGHT')
        def check(self):return memory()
        def account_bytes(self,n):self.bytes+=n
        def emit(self,event,**kw):
            if event not in ('PUBLIC_METADATA_READ','FULL_FROZEN_PLAN_VALIDATED'):raise PermissionError('METADATA_ONLY_PREFLIGHT')
    budget=MetadataOnlyBudget();plan=Plan(budget)
    from yuntapr.experimental.phase_b_v2_integration.initialization import fresh_paired_models
    from yuntapr.experimental.phase_b_v2_runner_candidate.optimizer import new_adamw
    from yuntapr.experimental.phase_b_v2_formal_runner_candidate.checkpoint import optimizer_template
    from yuntapr.experimental.phase_b_v2_formal_integration_candidate.checkpoint import Schedule
    from yuntapr.training.phase_a_protocol import state_digest
    from yuntapr.training.phase_b_v2_seed2027_b1_e1_epoch6_recovery_v1.ancestor import Guard,SOURCE_PREFIX
    from yuntapr.training.phase_b_v2_seed2027_b1_e1_epoch6_recovery_v1.recovery import load_authorized_last,apply_validated_state
    models,proof=fresh_paired_models(2027);model=models.pop('B1_V2');del models
    optimizer,_=new_adamw(model);schedule=Schedule()
    with Guard(release['failed_ancestor_sha256']) as guard:
        identity=dict(guard.pool.metadata[SOURCE_PREFIX+'.local/'+p.SOURCE_RUN+'/identity.json'])
    if identity['data']!=plan.identity or identity['initial_sha256']!=state_digest(model.state_dict()):raise ValueError('ACTUAL_FROZEN_DATA_OR_MODEL_IDENTITY')
    identity.update(campaign=p.CAMPAIGN,code=release,authorization_ancestor=p.CAMPAIGN,authorized_recovery_last=p.LAST_SHA)
    payload,history=load_authorized_last(identity,{k:(tuple(v.shape),str(v.dtype)) for k,v in model.state_dict().items()},optimizer_template(optimizer),plan.ids(2023),plan.ids(2024))
    # Any accidental optimizer call in restoration is a fatal preflight failure.
    def forbidden(*args,**kwargs):raise AssertionError('NO_OPTIMIZER_CALL_IN_RESTORE_PREFLIGHT')
    optimizer.step=forbidden
    restored=apply_validated_state(model,optimizer,schedule,payload)
    if schedule.completed!=31368 or [r['epoch'] for r in history]!=list(range(1,7)):raise ValueError('EXACT_RESTORE_BOUNDARY')
    result=dict(status='PASS',last_sha256=p.LAST_SHA,epoch=6,update=31368,restored=restored,
        all_modules_imported=True,source_repository=str(p.LIVE_ROOT.name),overlay_isolated=True,
        public_metadata_bytes=budget.bytes,raw_observation_reads=0,optimizer_step_calls=0,model_forward_calls=0,
        ledger_created=p.DB.exists(),headroom_before=headroom)
    p.atomic_json(p.OUT/'RESTORE_PREFLIGHT.json',result)
    print(json.dumps(result))

if __name__=='__main__':main()
