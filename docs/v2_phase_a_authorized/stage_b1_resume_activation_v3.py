"""Publish explicit lightweight startup receipts; never stages formal binaries or raw data."""
import hashlib
import json
from pathlib import Path
import subprocess

REPO = Path(__file__).resolve().parents[2]
BASE = REPO / 'docs/v2_phase_a_authorized'
RUN = BASE / 'pair_20261007T070503_825794Z/resume_20261009T003216_479921Z'


def main():
    evidence = json.loads((RUN / 'applied_resume_identity_verification.json').read_text(encoding='utf-8'))
    assert evidence['status'] == 'APPLIED_STATE_AND_COMPLETED_UPDATE_PASS'
    assert evidence['model_optimizer_scheduler_rng_exact_match'] and evidence['observed_update_matches_original_zero_tolerance']
    assert not evidence['PAIR_PHASE_A_COMPLETE'] and evidence['2025_RAW_ACCESS'] == evidence['2025_PIXELS_READ'] == 0
    files = [Path(__file__), BASE / 'verify_b1_applied_resume_v3.py']
    files += [RUN / name for name in ('remote_resume_verification.json', 'resume_process.json', 'wrapper_process.json',
               'monitor_process.json', 'applied_resume_identity_snapshot.json', 'applied_resume_identity_verification.json')]
    assert all(p.resolve().is_relative_to(BASE.resolve()) and p.suffix in {'.py', '.json'} for p in files)
    refs = {p.relative_to(REPO).as_posix(): {'sha256': hashlib.sha256(p.read_bytes()).hexdigest(), 'bytes': p.stat().st_size} for p in files}
    manifest = RUN / 'launch_evidence_manifest.json'
    with manifest.open('x', encoding='utf-8', newline='\n') as stream:
        json.dump({'status': 'B1_EPOCH_15_RESUME_ACTIVE', 'authorization_commit': 'f269272c821b49c5226ddf6d75eeb7108522cd34',
            'files': refs, 'audit_added_formal_optimizer_steps': 0, 'PAIR_PHASE_A_COMPLETE': False,
            '2025_RAW_ACCESS': 0, '2025_PIXELS_READ': 0, 'V2_PHASE_B_AUTHORIZED': False}, stream, indent=2, ensure_ascii=False)
        stream.write('\n')
    assert not subprocess.check_output(['git', 'diff', '--cached', '--name-only'], cwd=REPO).strip()
    subprocess.check_call(['git', '-c', 'core.longpaths=true', 'add', '--', *refs, manifest.relative_to(REPO).as_posix()], cwd=REPO)
    staged = subprocess.check_output(['git', 'diff', '--cached', '--name-only', '-z'], cwd=REPO).decode('utf-8').strip('\0').split('\0')
    assert set(staged) == set(refs) | {manifest.relative_to(REPO).as_posix()}
    for path, ref in refs.items():
        blob = subprocess.check_output(['git', 'show', ':' + path], cwd=REPO)
        assert hashlib.sha256(blob).hexdigest() == ref['sha256'], path
    print(json.dumps({'status': 'STARTUP_RECEIPTS_STAGED_AND_VERIFIED', 'files': len(staged),
                     'observed_completed_epoch15_step': evidence['observed_completed_step']}), flush=True)


if __name__ == '__main__':
    main()
