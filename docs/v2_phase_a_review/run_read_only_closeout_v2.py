"""Explicit sequential post-training closeout with a localhost read-only page.

Only terminal B1 CPU audit, completed-pair 2024 BEST inference, then metadata
packet generation. No formal launch/resume, optimizer, Phase-B, 2025, retries
or automatic publication. PDF visual verification and publication stay pending.
"""
import argparse
from datetime import datetime, timezone
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import subprocess
import sys
import threading
import time
import traceback

from completion_gate import check_pair, resolve_authority

REPO = Path(__file__).resolve().parents[2]
PYTHON = Path('F:/pytorch/Research/.venv-cuda/Scripts/python.exe')
ORIGIN_SHA = 'e32404d0d397dd62e1763d3fb16b4a8d8c72fb79ba52bae3f40ac095f4492869'
CODE = (
    'docs/v2_phase_a_review/run_read_only_closeout_v2.py',
    'docs/v2_phase_a_review/completion_gate.py',
    'docs/v2_phase_a_review/closeout_audit_v2.py',
    'docs/v2_phase_a_review/build_paired_decision_packet_v2.py',
    'docs/v2_phase_a_authorized/review_paired_best_v2.py',
    'docs/v2_phase_a_authorized/review_v2_helpers.py',
)


def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def save(path, value):
    with path.open('x', encoding='utf-8', newline='\n') as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2, allow_nan=False); stream.write('\n')


def git(*args):
    return subprocess.check_output(['git', '-c', 'core.longpaths=true', *args], cwd=REPO)


def verify_code(commit):
    remote = git('ls-remote', 'origin', 'refs/heads/main').decode().split()[0]
    subprocess.run(['git', 'merge-base', '--is-ancestor', commit, remote], cwd=REPO, check=True)
    proof = {}
    for relative in CODE:
        published = git('show', commit + ':' + relative)
        digest = hashlib.sha256(published).hexdigest()
        if sha(REPO / relative) != digest:
            raise ValueError('Published closeout code changed: ' + relative)
        proof[relative] = digest
    return {'publication_commit': commit, 'verified_remote_main': remote, 'code_sha256': proof}


def enforce_gate(auth_path, expected_sha):
    if sha(auth_path) != expected_sha:
        raise PermissionError('Latest completion authorization SHA mismatch')
    gate = check_pair(auth_path)
    if gate['status'] != 'METADATA_COMPLETION_GATE_PASS':
        raise PermissionError('Both formal models must complete normally before closeout')
    if gate['origin_authorization_sha256'] != ORIGIN_SHA:
        raise PermissionError('Another pair authority')
    if Path('F:/pytorch/Research/outputs/formal_training/paired_v2_gpu.lock').exists():
        raise PermissionError('Formal GPU lock still exists')
    auth, _ = resolve_authority(auth_path)
    if auth['V2_PHASE_B_AUTHORIZED'] or auth['2025_RAW_ACCESS'] or auth['2025_PIXELS_READ']:
        raise PermissionError('Scope/firewall violation')
    return auth, gate


def allowed_command(phase, auth, expected_sha, b0_audit, b1_audit=None, review=None, packet=None):
    authority = ['--authorization', str(auth), '--authorization-sha256', expected_sha]
    if phase == 'B1_TERMINAL_AUDIT':
        return [str(PYTHON), '-B', str(REPO / CODE[2]), *authority, '--model', 'B1_V2']
    if phase == 'FULL_2024_BEST_REVIEW':
        if review is None:
            raise ValueError('Independent review root missing')
        return [str(PYTHON), '-B', str(REPO / CODE[4]), *authority, '--execute', '--output', str(review)]
    if phase == 'PAIRED_DECISION_PACKET':
        if None in (b1_audit, review, packet):
            raise ValueError('Verified audits/review required')
        return [str(PYTHON), '-B', str(REPO / CODE[3]), *authority,
                '--b0-audit', str(b0_audit), '--b1-audit', str(b1_audit),
                '--review-root', str(review), '--output', str(packet)]
    raise PermissionError('No training/resume/Phase-B command supported')


def observed_progress(phase, event):
    if phase == 'B1_TERMINAL_AUDIT' and 'verified_epoch' in event:
        return {'model': 'B1_V2', 'checked_epochs': event['verified_epoch'],
                'total_epochs': event['total_epochs']}
    if phase == 'FULL_2024_BEST_REVIEW' and event.get('operation') == 'READ_ONLY_2024_REVIEW':
        return {'model': event['model'], 'review_scenes': event['scenes'],
                'review_total_scenes': event['total_scenes']}
    return {}


def run_child(phase, command, out, published, update):
    for relative, digest in published['code_sha256'].items():
        if sha(REPO / relative) != digest:
            raise ValueError('Utility changed after launch: ' + relative)
    env = dict(os.environ, PYTHONUTF8='1', PYTHONDONTWRITEBYTECODE='1',
               PYTHONHASHSEED='2026', CUBLAS_WORKSPACE_CONFIG=':4096:8')
    if phase == 'B1_TERMINAL_AUDIT':
        env['CUDA_VISIBLE_DEVICES'] = '-1'
    else:
        env.pop('CUDA_VISIBLE_DEVICES', None)
    last = None
    with (out / (phase + '.stderr.log')).open('x', encoding='utf-8', newline='\n') as error, \
         (out / (phase + '.stdout.log')).open('x', encoding='utf-8', newline='\n') as log:
        process = subprocess.Popen(command, cwd=REPO, env=env, stdout=subprocess.PIPE,
            stderr=error, text=True, encoding='utf-8', creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        save(out / (phase + '_process.json'), {'phase': phase, 'pid': process.pid,
             'command': command, 'started_utc': datetime.now(timezone.utc).isoformat()})
        update(status='READ_ONLY_CLOSEOUT_RUNNING', phase=phase, child_pid=process.pid)
        try:
            for line in process.stdout:
                log.write(line); log.flush()
                try:
                    event = json.loads(line)
                except ValueError:
                    continue
                last = event
                update(latest_child_event=event, **observed_progress(phase, event))
            code = process.wait()
        finally:
            process.stdout.close()
        save(out / (phase + '_exit.json'), {'exit_code': code, 'phase': phase,
             'completed_utc': datetime.now(timezone.utc).isoformat()})
        if code:
            raise RuntimeError(phase + ' failed; preserved logs; no automatic retry')
    return last


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--authorization', required=True, type=Path)
    parser.add_argument('--authorization-sha256', required=True)
    parser.add_argument('--publication-commit', required=True)
    parser.add_argument('--b0-audit', required=True, type=Path)
    parser.add_argument('--port', type=int, default=8771)
    parser.add_argument('--execute', action='store_true')
    args = parser.parse_args()
    auth, gate = enforce_gate(args.authorization, args.authorization_sha256)
    if not args.execute:
        print(json.dumps({'status': 'READ_ONLY_CLOSEOUT_PREFLIGHT_PASS',
                          'metadata_gate': gate, 'execution_started': False})); return
    published = verify_code(args.publication_commit)
    b0 = json.loads((args.b0_audit / 'terminal_model_audit.json').read_text(encoding='utf-8'))
    if b0['status'] != 'TERMINAL_MODEL_AUDIT_PASS' or b0['BEST'] != gate['models']['B0_MATCHED_V2']['BEST']:
        raise ValueError('Verified B0 audit identity differs')
    run_id = datetime.now(timezone.utc).strftime('run_%Y%m%dT%H%M%S_%fZ')
    out = REPO / 'docs/v2_phase_a_review/post_training_closeout' / run_id
    out.mkdir(parents=True, exist_ok=False)
    review = REPO / 'docs/v2_paired_phase_a_review/runs' / run_id
    packet = REPO / 'docs/v2_phase_a_review/paired_packets' / run_id
    state = {'status': 'READ_ONLY_CLOSEOUT_INITIALIZING', 'phase': 'PREFLIGHT',
             '2025_RAW_ACCESS': 0, '2025_PIXELS_READ': 0, 'V2_PHASE_B_AUTHORIZED': False,
             'CLOSEOUT_OPTIMIZER_STEPS': 0, 'CLOSEOUT_BACKWARD_CALLS': 0,
             'FORMAL_TRAINING_ENDED': True, 'RESEARCHER_PHASE_A_REVIEW_REQUIRED': True,
             'PDF_VISUALLY_VERIFIED': False, 'FINAL_GITHUB_PUBLICATION_VERIFIED': False,
             'evidence_root': str(out), 'review_root': str(review), 'packet_root': str(packet)}
    lock = threading.Lock()
    def update(**changes):
        with lock:
            state.update(changes); state['updated_unix_seconds'] = time.time()
            with (out / 'closeout_events.jsonl').open('a', encoding='utf-8', newline='\n') as stream:
                stream.write(json.dumps(state, ensure_ascii=False, allow_nan=False) + '\n')
    sys.path.insert(0, str(Path(auth['execution_checkout']) / 'scripts'))
    from paired_phase_a_v2.monitor import PAGE
    page = PAGE.replace('工程预检不授权正式训练', '正式训练已结束；当前仅只读审计与 2024 BEST 评价')
    page = page.replace("const names={", "const names={checked_epochs:'已审计 epoch',total_epochs:'审计 epoch 总数',review_scenes:'已推理验证场景',review_total_scenes:'验证场景总数',CLOSEOUT_OPTIMIZER_STEPS:'收尾 optimizer steps',")
    page = page.replace('id="status"', 'aria-live="polite" id="status"')
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_):
            pass
        def do_POST(self):
            self.send_error(405, 'Read only')
        def do_GET(self):
            route = self.path.split('?', 1)[0]
            if route == '/':
                body, mime = page.encode(), 'text/html; charset=utf-8'
            elif route == '/api/status':
                with lock:
                    value = dict(state, age_seconds=round(time.time() - state.get('updated_unix_seconds', time.time()), 1))
                body = json.dumps(value, ensure_ascii=False, allow_nan=False).encode()
                mime = 'application/json; charset=utf-8'
            else:
                self.send_error(404); return
            self.send_response(200); self.send_header('Content-Type', mime)
            self.send_header('Cache-Control', 'no-store'); self.send_header('Content-Length', str(len(body)))
            self.end_headers(); self.wfile.write(body)
    server = ThreadingHTTPServer(('127.0.0.1', args.port), Handler)
    save(out / 'launch_manifest.json', {'status': 'READ_ONLY_CLOSEOUT_LAUNCHED', **published,
         'completion_authorization_sha256': args.authorization_sha256, 'metadata_gate': gate,
         'b0_terminal_audit_sha256': sha(args.b0_audit / 'terminal_model_audit.json'),
         'monitor_url': 'http://127.0.0.1:' + str(args.port) + '/',
         'OPTIMIZER_STEPS': 0, 'BACKWARD_CALLS': 0, '2025_RAW_ACCESS': 0, '2025_PIXELS_READ': 0})
    def worker():
        try:
            update(status='READ_ONLY_CLOSEOUT_RUNNING', phase='B1_TERMINAL_AUDIT')
            result = run_child('B1_TERMINAL_AUDIT',
                allowed_command('B1_TERMINAL_AUDIT', args.authorization, args.authorization_sha256, args.b0_audit),
                out, published, update)
            if not result or result['status'] != 'TERMINAL_MODEL_AUDIT_PASS':
                raise ValueError('No B1 audit success identity')
            b1_audit = Path(result['output'])
            update(b1_audit_root=str(b1_audit), phase='FULL_2024_BEST_REVIEW', model='B0_MATCHED_V2',
                   review_scenes=0, review_total_scenes=10501)
            enforce_gate(args.authorization, args.authorization_sha256)
            run_child('FULL_2024_BEST_REVIEW',
                allowed_command('FULL_2024_BEST_REVIEW', args.authorization, args.authorization_sha256,
                                args.b0_audit, review=review), out, published, update)
            metrics = json.loads((review / 'paired_best_metrics.json').read_text(encoding='utf-8'))
            if metrics['status'] != 'PAIRED_FULL_2024_REVIEW_PASS':
                raise ValueError('Full paired 2024 review not passed')
            result = run_child('PAIRED_DECISION_PACKET',
                allowed_command('PAIRED_DECISION_PACKET', args.authorization, args.authorization_sha256,
                    args.b0_audit, b1_audit=b1_audit, review=review, packet=packet), out, published, update)
            if not result or result['status'] != 'PAIRED_DECISION_PACKET_PDF_AND_PUBLICATION_PENDING':
                raise ValueError('Packet creation not passed')
            update(status='READ_ONLY_REVIEW_PASS_PDF_AND_PUBLICATION_PENDING', phase='PDF_AND_PUBLICATION_PENDING')
            save(out / 'closeout_status.json', dict(state, automatic_next_stage=False))
        except BaseException as exc:
            update(status='FAILED_STOP', error=repr(exc), automatic_retry=False)
            save(out / 'failure.json', dict(state, traceback=traceback.format_exc()))
    threading.Thread(target=worker, daemon=True).start()
    print(json.dumps({'url': 'http://127.0.0.1:' + str(args.port) + '/', 'output': str(out)}), flush=True)
    server.serve_forever()


if __name__ == '__main__':
    main()
