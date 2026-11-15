"""Artificial approval/scope gate checks for the physical-Pinball dispatcher."""
import copy
import json
from pathlib import Path
import sys
import tempfile
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'src'))
sys.dont_write_bytecode = True
from yuntapr.experimental.research_readiness import physical_pinball_training as tasks


def rejected(call):
    try:
        call()
    except (ValueError, PermissionError):
        return True
    raise AssertionError('Mutated or unapproved scope accepted')


def main():
    contract = tasks.evaluation_contract(ROOT)
    parent = tasks.read(ROOT / 'docs/research_readiness/20261110_cosine9/EXECUTION_PROPOSAL.json')
    protocol = dict(parent['protocol'], quantile_profile=tasks.PHYSICAL_PROFILE)
    prepared = {'data': {'fixture': True}, 'roles': {
        'Train': {'bytes_per_pass': 26424262556, 'file_count': 7918},
        'Development': {'bytes_per_pass': 26639253112, 'file_count': 7950}}}
    proposal = {
        'tasks': copy.deepcopy(tasks.TASKS), 'protocol': protocol,
        'scientific_choices': {'candidate_schedule': tasks.schedule_identity(),
            'candidate_loss': tasks.profile_identity(), 'evaluation': contract,
            'evaluation_contract_sha256': tasks.sha(ROOT / tasks.CONTRACT),
            'control_reuse': {'fixture': True}},
        'data': prepared['data'], 'budget': tasks.budget(prepared),
        'runtime_binding': {'fixture': True}, 'code_sha256': {'fixture': 'code'},
        'parent_proposal_identity': {'sha256': 'parent'}}
    tasks.validate_scope(proposal, ROOT)
    checks = {'valid_scope': True}
    for name, field, value in [('profile', 'quantile_profile', 'UNIFORM'),
                               ('schedule', 'schedule_profile', 'ORIGINAL_50'),
                               ('batch', 'batch', 4), ('seed', 'seed', 2030)]:
        altered = copy.deepcopy(proposal)
        altered['protocol'][field] = value
        checks['reject_' + name] = rejected(lambda: tasks.validate_scope(altered, ROOT))
    altered = copy.deepcopy(proposal)
    altered['scientific_choices']['evaluation']['screen']['absolute_roundoff_tolerance'] = 1
    checks['reject_contract'] = rejected(lambda: tasks.validate_scope(altered, ROOT))
    with tempfile.TemporaryDirectory() as directory:
        folder = Path(directory)
        approval = folder / 'approval.json'
        checks['missing_approval'] = rejected(lambda: tasks.checked(ROOT, folder/'p', folder/'v', approval, 'fixture'))
        approval.write_text('{}', encoding='utf-8')
        private = {'proposal_sha256': '', 'inherited': str(folder/'inherited'),
                   'inherited_file_sha256': 'inherited', 'parent_proposal': str(folder/'parent'),
                   'control': str(folder/'control')}
        def validate_fixture(changed):
            changed['proposal_sha256'] = tasks.digest({k: v for k, v in changed.items() if k != 'proposal_sha256'})
            private['proposal_sha256'] = changed['proposal_sha256']
            values = {str(folder/'p'): changed, str(folder/'v'): private, str(approval): {}}
            real_read = tasks.read
            def fixture_read(path):
                return values[str(path)] if str(path) in values else real_read(path)
            real_sha = tasks.sha
            def fixture_sha(path):
                if Path(path) == folder/'inherited': return 'inherited'
                if Path(path) == folder/'parent': return 'parent'
                return real_sha(path)
            with patch.object(tasks, 'read', side_effect=fixture_read), \
                 patch.object(tasks, 'sha', side_effect=fixture_sha), \
                 patch.object(tasks, 'validate_approval'), \
                 patch.object(tasks, 'runtime_binding', return_value={'fixture': True}), \
                 patch.object(tasks, 'code_hashes', return_value={'fixture': 'code'}), \
                 patch.object(tasks, 'control_binding', return_value={'fixture': True}), \
                 patch.object(tasks, 'load_inherited', return_value=({}, prepared)):
                return tasks.checked(ROOT, folder/'p', folder/'v', approval, 'fixture')
        validate_fixture(copy.deepcopy(proposal))
        checks['valid_mock_binding'] = True
        altered = copy.deepcopy(proposal)
        altered['budget']['total_updates'] += 1
        checks['reject_budget'] = rejected(lambda: validate_fixture(altered))
        altered = copy.deepcopy(proposal)
        altered['code_sha256'] = {'fixture': 'tampered'}
        checks['reject_code'] = rejected(lambda: validate_fixture(altered))
    # These guards finish before any experiment output or worker is created.
    result = {'status': 'PASS', 'scope': 'ARTIFICIAL_DISPATCH_GATES_ONLY', 'checks': checks,
              'real_approval_used': False, 'training_or_inference': False,
              'raw_or_weight_payload_access': False}
    target = ROOT / 'docs/research_readiness/20261115_physical_pinball_prepare/RUNTIME_GATE_CHECK.json'
    with target.open('x', encoding='utf-8', newline='\n') as stream:
        json.dump(result, stream, indent=2, allow_nan=False)
        stream.write('\n')
    print(json.dumps(result))


if __name__ == '__main__':
    main()
