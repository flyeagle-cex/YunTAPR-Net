"""Synthetic authorization rejection tests; never launches or opens raw/model files."""
import argparse
from datetime import datetime, timezone
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
from unittest.mock import patch

BASE = Path(__file__).resolve().parent
REPO = BASE.parents[1]
spec = importlib.util.spec_from_file_location('launcher_v3', BASE / 'launch_b1_verified_resume_v3.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    cases = []
    with tempfile.TemporaryDirectory(prefix='launch_guard_fixture_', dir=BASE) as name:
        root = Path(name).resolve()
        assert root.is_relative_to(BASE.resolve())
        auth_path = root / 'authorization.json'
        original = {'publication_repository': str(REPO), 'execution_checkout': str(REPO.parent / 'YunTAPR-Net-v2-phase-a-execution'),
            'scope': 'FORMAL_PAIRED_PHASE_A_V2', 'resume_authorized': True, 'resume_model': 'B1_V2',
            'FORMAL_TRAINING_AUTHORIZED': True, 'V2_PHASE_A_AUTHORIZED': True, 'V2_PHASE_B_AUTHORIZED': False,
            '2025_RAW_ACCESS': 0, '2025_PIXELS_READ': 0}
        definitions = [('wrong_sha', {}, 'wrong_sha'), ('wrong_scope', {'scope': 'PHASE_B'}, None),
            ('phase_b_authorized', {'V2_PHASE_B_AUTHORIZED': True}, None),
            ('raw_2025_nonzero', {'2025_RAW_ACCESS': 1}, None),
            ('pixels_2025_nonzero', {'2025_PIXELS_READ': 1}, None),
            ('wrong_remote', {}, 'wrong_remote'), ('wrong_branch', {}, 'wrong_branch'),
            ('remote_commit_mismatch', {}, 'remote_commit_mismatch')]
        for case, changes, fault in definitions:
            auth_path.write_text(json.dumps({**original, **changes}), encoding='utf-8')
            digest = module.sha(auth_path) if fault != 'wrong_sha' else '0' * 64
            def git(_root, *argv):
                if argv[:2] == ('remote', 'get-url'):
                    return 'https://example.invalid/other.git' if fault == 'wrong_remote' else 'https://github.com/flyeagle-cex/YunTAPR-Net.git'
                if argv == ('branch', '--show-current'):
                    return 'other' if fault == 'wrong_branch' else 'main'
                if argv[0] == 'ls-remote':
                    return ('b' * 40 if fault == 'remote_commit_mismatch' else 'a' * 40) + '\trefs/heads/main'
                if argv == ('rev-parse', 'HEAD'):
                    return 'a' * 40
                raise AssertionError('Unexpected git call')
            with patch.object(sys, 'argv', ['launcher', '--authorization', str(auth_path), '--sha256', digest,
                       '--authorization-commit', 'a' * 40, '--launch']), patch.object(module, 'git', git), \
                       patch.object(module.subprocess, 'Popen') as dispatch:
                try:
                    module.main()
                except AssertionError:
                    pass
                else:
                    raise AssertionError('Unsafe authorization accepted: ' + case)
                dispatch.assert_not_called()
            cases.append({'case': case, 'status': 'PASS_REJECTED_BEFORE_DISPATCH'})
    value = {'status': 'PASS', 'tests_passed': len(cases), 'tests_total': 8, 'cases': cases,
        'TEST_FIXTURE_ONLY': True, 'fixtures_cleaned': not root.exists(),
        'network_calls': 0, 'formal_optimizer_steps_added': 0, 'raw_source_opens': 0,
        '2025_RAW_ACCESS': 0, '2025_PIXELS_READ': 0,
        'completed_utc': datetime.now(timezone.utc).isoformat()}
    with args.output.open('x', encoding='utf-8', newline='\n') as stream:
        json.dump(value, stream, indent=2); stream.write('\n')
    print(json.dumps(value), flush=True)


if __name__ == '__main__':
    main()
