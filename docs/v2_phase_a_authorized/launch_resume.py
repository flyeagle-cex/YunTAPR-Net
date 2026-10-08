"""Remote-authority wrapper for the unchanged, epoch-boundary-only resume CLI."""
import argparse, hashlib, json, os, subprocess, sys
from datetime import datetime, timezone
from pathlib import Path

def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()

def git(root, *args):
    return subprocess.check_output(['git', '-c', 'core.longpaths=true', '-c', 'http.version=HTTP/1.1', *args], cwd=root).decode('utf-8').strip()

def save(p, value):
    with p.open('x', encoding='utf-8', newline='\n') as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2)
        stream.write('\n')

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--authorization', type=Path, required=True)
    parser.add_argument('--sha256', required=True)
    parser.add_argument('--authorization-commit', required=True)
    parser.add_argument('--verify-only', action='store_true')
    a = parser.parse_args()
    assert sha(a.authorization) == a.sha256
    auth = json.loads(a.authorization.read_text(encoding='utf-8'))
    repo, execution = Path(auth['publication_repository']), Path(auth['execution_checkout'])
    assert auth['resume_authorized'] is True and auth['resume_model'] == 'B0_MATCHED_V2'
    assert auth['FORMAL_TRAINING_AUTHORIZED'] and auth['V2_PHASE_A_AUTHORIZED'] and not auth['V2_PHASE_B_AUTHORIZED']
    assert not auth['2025_RAW_ACCESS'] and not auth['2025_PIXELS_READ']
    assert git(repo, 'branch', '--show-current') == 'main'
    remote = git(repo, 'ls-remote', 'origin', 'refs/heads/main').split()[0]
    assert remote == git(repo, 'rev-parse', 'HEAD') == a.authorization_commit
    rel = a.authorization.relative_to(repo).as_posix()
    recorded = subprocess.check_output(['git', 'show', a.authorization_commit+':'+rel], cwd=repo)
    assert hashlib.sha256(recorded).hexdigest() == a.sha256
    assert git(execution, 'rev-parse', 'HEAD') == auth['execution_commit']
    assert not git(execution, 'status', '--porcelain', '--untracked-files=normal')
    for rel, h in auth['code_sha256'].items():
        assert sha(execution/rel) == h, rel
    for path_key, sha_key in [('origin_authorization_path', 'origin_authorization_sha256'),
                              ('preflight_path', 'preflight_sha256'), ('test_summary_path', 'test_summary_sha256'),
                              ('resume_precheck_path', 'resume_precheck_sha256'),
                              ('researcher_approval_reference', 'researcher_approval_record_sha256')]:
        assert sha(auth[path_key]) == auth[sha_key], path_key
    proof = json.loads(Path(auth['resume_precheck_path']).read_text(encoding='utf-8'))
    assert proof['status'] == 'PASS' and proof['state_application_performed'] is False
    last = json.loads((Path(auth['publication_root'])/'B0_MATCHED_V2/last_checkpoint_identity.json').read_text(encoding='utf-8'))
    assert last == proof['checkpoint'] and last['sha256'] == auth['resume_LAST_sha256']
    assert sha(last['absolute_local_path']) == last['sha256']
    assert Path('H:/葵花202303_202510').is_dir()
    result = {'status': 'REMOTE_RESUME_AUTHORIZATION_VERIFIED', 'authorization_commit': a.authorization_commit,
              'remote_main': remote, 'authorization_sha256': a.sha256, 'LAST': last,
              'verified_utc': datetime.now(timezone.utc).isoformat(), 'V2_PHASE_B_AUTHORIZED': False}
    if a.verify_only:
        print(json.dumps(result)); return
    assert not Path('F:/pytorch/Research/outputs/formal_training/paired_v2_gpu.lock').exists(), 'Stale lock requires separately evidenced removal'
    save(a.authorization.parent/'remote_resume_verification.json', result)
    env = os.environ.copy()
    env.update(PYTHONUTF8='1', PYTHONDONTWRITEBYTECODE='1', PYTHONHASHSEED='2026', CUBLAS_WORKSPACE_CONFIG=':4096:8')
    command = [sys.executable, '-B', str(execution/'scripts/run_paired_phase_a_v2.py'), 'resume',
               '--authorization', str(a.authorization), '--authorization-sha256', a.sha256]
    child = subprocess.Popen(command, cwd=execution, env=env, creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
    save(a.authorization.parent/'resume_process.json', {'pid':child.pid, 'command':command, **result})
    rc = child.wait()
    save(a.authorization.parent/'process_exit.json', {'exit_code':rc, 'utc':datetime.now(timezone.utc).isoformat(),
        'status':'RUNNER_EXITED_REVIEW_REQUIRED' if rc == 0 else 'FAILED_STOP_NO_AUTOMATIC_RETRY',
        'V2_PHASE_B_AUTHORIZED':False, 'original_stopped_attempt_preserved':True})
    raise SystemExit(rc)

if __name__ == '__main__':
    main()
