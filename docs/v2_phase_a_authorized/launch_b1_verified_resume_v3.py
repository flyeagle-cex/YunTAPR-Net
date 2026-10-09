"""Explicit remote-bound launch after terminal journal failure and reader correction."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import urllib.request


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(8 * 1024**2), b''): h.update(block)
    return h.hexdigest()


def git(root, *args):
    return subprocess.check_output(['git', '-c', 'core.longpaths=true', *args], cwd=root).decode('utf-8').strip()


def save(path, value):
    with path.open('x', encoding='utf-8', newline='\n') as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2, allow_nan=False); stream.write('\n')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--authorization', required=True, type=Path)
    parser.add_argument('--sha256', required=True)
    parser.add_argument('--authorization-commit', required=True)
    parser.add_argument('--launch', action='store_true', help='Only after remote provenance verification')
    args = parser.parse_args()
    auth_path = args.authorization.resolve()
    assert sha(auth_path) == args.sha256
    auth = json.loads(auth_path.read_text(encoding='utf-8'))
    repo, execution = Path(auth['publication_repository']), Path(auth['execution_checkout'])
    assert auth_path.is_relative_to(repo / 'docs/v2_phase_a_authorized')
    assert auth['scope'] == 'FORMAL_PAIRED_PHASE_A_V2' and auth['resume_authorized'] is True
    assert auth['resume_model'] == 'B1_V2' and auth['FORMAL_TRAINING_AUTHORIZED'] and auth['V2_PHASE_A_AUTHORIZED']
    assert not auth['V2_PHASE_B_AUTHORIZED'] and not auth['2025_RAW_ACCESS'] and not auth['2025_PIXELS_READ']
    assert git(repo, 'remote', 'get-url', 'origin') == 'https://github.com/flyeagle-cex/YunTAPR-Net.git'
    assert git(repo, 'branch', '--show-current') == 'main'
    remote = git(repo, 'ls-remote', 'origin', 'refs/heads/main').split()[0]
    assert remote == git(repo, 'rev-parse', 'HEAD') == args.authorization_commit
    for path_key, sha_key in [('origin_authorization_path', 'origin_authorization_sha256'),
                              ('preflight_path', 'preflight_sha256'), ('test_summary_path', 'test_summary_sha256'),
                              ('resume_precheck_path', 'resume_precheck_sha256'),
                              ('researcher_approval_reference', 'researcher_approval_record_sha256'),
                              ('diagnostic_monitor_script', 'diagnostic_monitor_sha256'),
                              ('journal_reader_test_path', 'journal_reader_test_sha256'),
                              ('prior_failure_closeout_path', 'prior_failure_closeout_sha256')]:
        assert sha(auth[path_key]) == auth[sha_key], path_key
        path = Path(auth[path_key])
        if path.is_relative_to(repo):
            committed = subprocess.check_output(['git', 'show', args.authorization_commit + ':' + path.relative_to(repo).as_posix()], cwd=repo)
            assert hashlib.sha256(committed).hexdigest() == auth[sha_key], path_key
    committed = subprocess.check_output(['git', 'show', args.authorization_commit + ':' + auth_path.relative_to(repo).as_posix()], cwd=repo)
    assert hashlib.sha256(committed).hexdigest() == args.sha256
    assert git(execution, 'rev-parse', 'HEAD') == auth['execution_commit'] == 'a1af0325b481202941c57e8fc94f3b20e441630a'
    assert not git(execution, 'status', '--porcelain', '--untracked-files=normal')
    for rel, expected in auth['code_sha256'].items(): assert sha(execution / rel) == expected, rel
    proof = json.loads(Path(auth['resume_precheck_path']).read_text(encoding='utf-8'))
    assert proof['status'] == 'PASS' and proof['state_application_performed'] is False
    assert proof['formal_optimizer_steps_added'] == 0 and proof['next_epoch'] == 15
    assert proof['reconciliation']['discarded_updates_lower_bound'] == proof['reconciliation']['discarded_updates_upper_bound'] == auth['discarded_uncheckpointed_updates'] == 3477
    assert proof['reconciliation']['all_attempt_updates_lower_bound'] == proof['reconciliation']['all_attempt_updates_upper_bound'] == auth['all_attempt_successful_updates_before_resume'] == 76669
    assert proof['journal_reader_test']['sha256'] == auth['journal_reader_test_sha256']
    reader_test = json.loads(Path(auth['journal_reader_test_path']).read_text(encoding='utf-8'))
    assert reader_test['status'] == 'PASS' and reader_test['fixtures_cleaned']
    assert reader_test['explicit_readwrite_delete_reader_concurrent_appends_pass'] == 1000
    last = json.loads((Path(auth['publication_root']) / 'B1_V2/last_checkpoint_identity.json').read_text(encoding='utf-8'))
    assert last == proof['checkpoint'] and last['sha256'] == auth['resume_LAST_sha256']
    assert sha(last['absolute_local_path']) == last['sha256'] and Path(last['absolute_local_path']).stat().st_size == last['bytes']
    mask = proof['frozen_manifest_identities']['yunnan_mask']
    assert sha(mask['path']) == mask['sha256']
    assert Path('H:/葵花202303_202510').is_dir()
    assert not Path('F:/pytorch/Research/outputs/formal_training/paired_v2_gpu.lock').exists()
    with urllib.request.urlopen('http://127.0.0.1:8771/api/status', timeout=10) as response:
        monitor = json.load(response)
    assert monitor['monitor_reads_mutable_runner_json'] is False
    assert monitor['monitor_source'] == 'APPEND_ONLY_JOURNALS_AND_IMMUTABLE_EPOCH_REPORTS'
    assert monitor.get('process_alive') is not True, 'Old formal process still live'
    result = {'status': 'REMOTE_LAST_BOUND_B1_RESUME_VERIFIED',
              'authorization_commit': args.authorization_commit, 'remote_main': remote,
              'authorization_sha256': args.sha256, 'LAST': last,
              'verified_utc': datetime.now(timezone.utc).isoformat(),
              'V2_PHASE_B_AUTHORIZED': False, '2025_RAW_ACCESS': 0, '2025_PIXELS_READ': 0}
    if not args.launch:
        print(json.dumps(result), flush=True); return
    save(auth_path.parent / 'remote_resume_verification.json', result)
    env = os.environ.copy()
    env.update(PYTHONUTF8='1', PYTHONDONTWRITEBYTECODE='1', PYTHONHASHSEED='2026', CUBLAS_WORKSPACE_CONFIG=':4096:8')
    command = [sys.executable, '-B', str(execution / 'scripts/run_paired_phase_a_v2.py'), 'resume',
               '--authorization', str(auth_path), '--authorization-sha256', args.sha256]
    child = subprocess.Popen(command, cwd=execution, env=env, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
    save(auth_path.parent / 'resume_process.json', {'pid': child.pid, 'wrapper_pid': os.getpid(), 'command': command, **result})
    print(json.dumps({'status': 'FORMAL_RESUME_PROCESS_DISPATCHED', 'pid': child.pid}), flush=True)
    code = child.wait()
    save(auth_path.parent / 'process_exit.json', {'exit_code': code, 'utc': datetime.now(timezone.utc).isoformat(),
         'status': 'RUNNER_EXITED_REVIEW_REQUIRED' if code == 0 else 'FAILED_STOP_NO_AUTOMATIC_RETRY',
         'V2_PHASE_B_AUTHORIZED': False, '2025_RAW_ACCESS': 0, '2025_PIXELS_READ': 0})
    raise SystemExit(code)


if __name__ == '__main__':
    main()
