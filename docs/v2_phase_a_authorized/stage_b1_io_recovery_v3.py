"""Stage only the closed journal failure, reader correction and verified resume binding."""
import hashlib
import json
from pathlib import Path
import subprocess

REPO = Path(__file__).resolve().parents[2]
BASE = REPO / 'docs/v2_phase_a_authorized'
PAIR = BASE / 'pair_20261007T070503_825794Z'
RESUME = PAIR / 'resume_20261009T003216_479921Z'
CLOSEOUT = PAIR / 'journal_failure_closeout_20261009T003025_643554Z'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    assert json.loads((RESUME / 'preparation_status.json').read_text(encoding='utf-8'))['status'] == 'PASS_AWAITING_REMOTE_PUBLICATION_AND_LAUNCH'
    assert json.loads((CLOSEOUT / 'evidence_manifest.json').read_text(encoding='utf-8'))['status'] == 'CLOSED_FAILURE_PRESERVED'
    files = [BASE / name for name in ('archive_b1_journal_conflict_v1.py', 'prepare_b1_resume_v3.py',
        'launch_b1_verified_resume_v3.py', 'stage_b1_io_recovery_v3.py', 'test_windows_journal_reader_v1.py',
        'journal_reader_sharing_test_20261009_v1.json', 'journal_reader_sharing_test_20261009_v2.json',
        'journal_reader_sandbox_attempt_20261009.json', 'LIVE_AUDIT_READ_POLICY.md',
        'test_b1_resume_launch_guards_v3.py', 'b1_resume_launch_guard_tests_20261009_v3.json')]
    files += sorted(CLOSEOUT.iterdir())
    files += [RESUME / name for name in ('resume_precheck.json', 'historical_preservation_before_resume.json',
        'RESEARCHER_RESUME_AUTHORIZATION_RECORD.md', 'authorization.json', 'preparation_status.json', 'raw_access_precheck.jsonl')]
    assert all(p.is_file() and p.suffix in {'.py', '.json', '.jsonl', '.md'} for p in files)
    assert all(p.resolve().is_relative_to(BASE.resolve()) for p in files)
    assert not subprocess.check_output(['git', 'diff', '--cached', '--name-only'], cwd=REPO).strip(), 'Preexisting index changes'
    refs = {p.relative_to(REPO).as_posix(): {'sha256': sha(p), 'bytes': p.stat().st_size} for p in files}
    manifest = RESUME / 'publication_manifest.json'
    value = {'status': 'EXPLICIT_ALLOWLIST_VERIFIED', 'scope': 'JOURNAL_FAILURE_CLOSEOUT_AND_EXISTING_PHASE_A_RESUME',
        'files': refs, 'formal_optimizer_steps_added_by_preparation': 0,
        '2025_RAW_ACCESS': 0, '2025_PIXELS_READ': 0, 'V2_PHASE_B_AUTHORIZED': False}
    with manifest.open('x', encoding='utf-8', newline='\n') as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2); stream.write('\n')
    subprocess.check_call(['git', '-c', 'core.longpaths=true', 'add', '--',
        *refs, manifest.relative_to(REPO).as_posix()], cwd=REPO)
    staged = subprocess.check_output(['git', '-c', 'core.longpaths=true', 'diff', '--cached', '--name-only', '-z'], cwd=REPO).decode('utf-8').strip('\0').split('\0')
    assert set(staged) == set(refs) | {manifest.relative_to(REPO).as_posix()}
    for rel, ref in refs.items():
        committed = subprocess.check_output(['git', 'show', ':' + rel], cwd=REPO)
        assert hashlib.sha256(committed).hexdigest() == ref['sha256'], rel
    print(json.dumps({'status': 'STAGED_AND_BYTES_VERIFIED', 'files': len(staged),
                     'manifest': manifest.relative_to(REPO).as_posix()}), flush=True)


if __name__ == '__main__':
    main()
