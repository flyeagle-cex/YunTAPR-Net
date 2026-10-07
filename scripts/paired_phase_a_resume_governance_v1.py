"""Explicit researcher resume: audit accounting and log segmentation only.

Numerical code, source eligibility, completed checkpoints, and origin provenance
are inherited without changes. Canonical counters describe the retained model
trajectory; ALL_ATTEMPTS counters also include the discarded interrupted epoch.
"""
from pathlib import Path
import json, sys
ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT/'src'), str(ROOT), str(ROOT/'scripts')]
import torch
from yuntapr.training import paired_phase_a_audit as inherited

PLAN = None
ORIGINAL_ATOMIC = inherited.atomic_json


def accounting(canonical, plan=None, *, backward=None):
    plan = plan or PLAN
    boundary = plan['resume_completed_epoch'] * 5228
    discarded = plan['discarded_uncheckpointed_updates']
    return {
        'counter_semantics': 'RETAINED_MODEL_TRAJECTORY_WITH_SEPARATE_ALL_ATTEMPTS_ACCOUNTING',
        'MODEL_TRAJECTORY_OPTIMIZER_STEPS': canonical,
        'DISCARDED_UNCHECKPOINTED_OPTIMIZER_STEPS': discarded,
        'ALL_ATTEMPTS_ACTUAL_FORMAL_OPTIMIZER_STEPS': max(canonical, boundary) + discarded,
        'ALL_ATTEMPTS_ACTUAL_BACKWARD_CALLS': max(canonical if backward is None else backward, boundary) + discarded,
        'resume_journal': plan['resume_directory'],
    }


def verify_additions(value):
    for relative, digest in value['resume_governance_code_hashes'].items():
        p = ROOT/relative
        if not p.resolve().is_relative_to(ROOT) or inherited.sha256(p) != digest:
            raise PermissionError('Resume governance source identity changed: '+relative)


def protected_atomic(path, value):
    path = Path(path)
    public = Path(PLAN['public_directory'])
    if path.parent == public and path.name in ('run_manifest.json', 'first_update_identity_gate.json'):
        if json.loads(path.read_text(encoding='utf8')) != value:
            raise PermissionError('Resume cannot replace origin provenance: '+path.name)
        return
    if path.parent == public and path.name == 'final_status.json':
        value = {**value, **accounting(value['FORMAL_OPTIMIZER_STEPS'], backward=value.get('BACKWARD_CALLS'))}
    ORIGINAL_ATOMIC(path, value)


class ResumeRunAudit(inherited.RunAudit):
    def event(self, event, **values):
        if event == 'FORMAL_FRESH_RUN_READY':
            event = 'FORMAL_RESUMED_RUN_READY'
        super().event(event, **{**accounting(self.counters.FORMAL_OPTIMIZER_STEPS, backward=self.counters.BACKWARD_CALLS), **values})

    def snapshot(self, **values):
        super().snapshot(**{**accounting(self.counters.FORMAL_OPTIMIZER_STEPS, backward=self.counters.BACKWARD_CALLS), **values})


def resume_worker_init(worker_id):
    """Keep frozen worker seed/decoder/guards; partition this attempt's records."""
    info = torch.utils.data.get_worker_info()
    context = info.dataset.audit_context
    p = Path(context['authorization_path'])
    if inherited.sha256(p) != context['authorization_sha256']:
        raise PermissionError('Resume worker authorization changed')
    value = json.loads(p.read_text(encoding='utf8'))
    if not value.get('resume_authorized') or not value.get('researcher_resume_message'):
        raise PermissionError('Explicit researcher resume required')
    verify_additions(value)
    plan_path = inherited.repository_json_path(value['resume_plan_path'])
    if inherited.sha256(plan_path) != value['resume_plan_sha256']:
        raise PermissionError('Resume plan identity changed')
    plan = json.loads(plan_path.read_text(encoding='utf8'))
    if Path(context['public']) != Path(plan['public_directory']):
        raise PermissionError('Worker origin public directory mismatch')
    segment = Path(plan['worker_log_directory'])
    if not segment.resolve().is_relative_to(Path(plan['resume_directory']).resolve()) or not segment.is_dir():
        raise PermissionError('Resume worker log segment is not pre-registered')
    context['public'] = str(segment)
    inherited.audited_worker_init(worker_id)


def launch(argv=None):
    global PLAN
    import authorized_paired_phase_a_entry as entry
    # The inherited rejection gate runs before model, optimizer or source I/O.
    args, contract, auth, firewall = entry.reject_before_construction('B1', argv)
    if not args.resume_run_id or args.resume_run_id != auth.value['planned_run_id']:
        raise PermissionError('Exact existing B1 run ID required')
    verify_additions(auth.value)
    plan_path = inherited.repository_json_path(auth.value['resume_plan_path'])
    if inherited.sha256(plan_path) != auth.value['resume_plan_sha256']:
        raise PermissionError('Resume plan changed')
    PLAN = json.loads(plan_path.read_text(encoding='utf8'))
    if PLAN['origin_authorization_sha256'] != auth.value['origin_authorization_sha256']:
        raise PermissionError('Origin authorization differs from plan')
    test_path = Path(PLAN['resume_directory'])/'preflight_status.json'
    preflight = json.loads(test_path.read_text(encoding='utf8'))
    if preflight['status'] != 'RESUME_PREFLIGHT_PASS' or preflight['resume_authorization_sha256'] != auth.sha256:
        raise PermissionError('Completed resume preflight required')
    # Only records/metadata writes/worker log destinations are adapted in memory.
    entry.RunAudit = ResumeRunAudit
    entry.atomic_json = protected_atomic
    entry.audited_worker_init = resume_worker_init
    return entry.main('B1', argv)


if __name__ == '__main__':
    launch()
