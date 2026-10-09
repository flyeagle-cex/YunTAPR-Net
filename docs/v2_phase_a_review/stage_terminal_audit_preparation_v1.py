"""Explicit publication allowlist for real B0 closeout and future read-only review tests."""
import hashlib
import json
from pathlib import Path
import subprocess

REPO = Path(__file__).resolve().parents[2]
AUDIT = REPO / 'docs/v2_phase_a_review/closure_audits/run_20261009T005719_747987Z/B0_MATCHED_V2'


def main():
    value = json.loads((AUDIT / 'terminal_model_audit.json').read_text(encoding='utf-8'))
    assert value['status'] == 'TERMINAL_MODEL_AUDIT_PASS' and value['model'] == 'B0_MATCHED_V2'
    assert value['PAIR_PHASE_A_COMPLETE_CLAIMED'] is False
    files = [REPO / 'docs/v2_phase_a_review' / name for name in ('closeout_audit_v2.py', 'test_closeout_audit_v2.py',
        'closeout_fixture_tests_20261009_v2.json', 'current_resume_early_review_rejected_20261009.json',
        'READ_ONLY_CLOSEOUT_HANDOFF_v2.md', 'stage_terminal_audit_preparation_v1.py')]
    files += [REPO / 'docs/v2_phase_a_authorized' / name for name in ('review_paired_best_v2.py', 'review_v2_helpers.py',
        'test_review_v2_helpers.py', 'review_helper_fixture_tests_20261009_v1.json')]
    files += sorted(AUDIT.glob('*.json'))
    assert all(p.is_file() and p.suffix in {'.py', '.json', '.md'} and p.resolve().is_relative_to((REPO / 'docs').resolve()) for p in files)
    for p in files:
        if p.name in ('closeout_fixture_tests_20261009_v2.json', 'review_helper_fixture_tests_20261009_v1.json'):
            assert json.loads(p.read_text(encoding='utf-8'))['status'] == 'PASS'
    refs = {p.relative_to(REPO).as_posix(): {'sha256': hashlib.sha256(p.read_bytes()).hexdigest(), 'bytes': p.stat().st_size} for p in files}
    manifest = AUDIT / 'publication_manifest.json'
    with manifest.open('x', encoding='utf-8', newline='\n') as stream:
        json.dump({'status': 'B0_AUDIT_COMPLETE_PAIRED_REVIEW_NOT_RUN', 'files': refs,
            'PAIR_PHASE_A_COMPLETE': False, 'FULL_2024_PAIRED_REVIEW_EXECUTED': False,
            'FORMAL_OPTIMIZER_STEPS_ADDED': 0, '2025_RAW_ACCESS': 0, '2025_PIXELS_READ': 0,
            'V2_PHASE_B_AUTHORIZED': False}, stream, indent=2, ensure_ascii=False); stream.write('\n')
    assert not subprocess.check_output(['git', 'diff', '--cached', '--name-only'], cwd=REPO).strip()
    subprocess.check_call(['git', '-c', 'core.longpaths=true', 'add', '--', *refs, manifest.relative_to(REPO).as_posix()], cwd=REPO)
    staged = subprocess.check_output(['git', 'diff', '--cached', '--name-only', '-z'], cwd=REPO).decode('utf-8').strip('\0').split('\0')
    assert set(staged) == set(refs) | {manifest.relative_to(REPO).as_posix()}
    for path, ref in refs.items():
        blob = subprocess.check_output(['git', 'show', ':' + path], cwd=REPO)
        assert hashlib.sha256(blob).hexdigest() == ref['sha256'], path
    print(json.dumps({'status': 'EXPLICIT_AUDIT_PUBLICATION_STAGED', 'files': len(staged), 'actual_b0_epochs_audited': 17}), flush=True)


if __name__ == '__main__':
    main()
