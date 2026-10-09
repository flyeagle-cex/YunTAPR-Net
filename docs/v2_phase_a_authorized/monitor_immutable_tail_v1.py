"""Independent Phase-A monitor: immutable reports and append-only logs only.

Never opens progress.json, checkpoint registries, BEST/LAST, mutable training
histories, raw sources or checkpoint binaries. Never controls the training run.
The pinned formal runner and scientific identities remain unchanged.
"""
import argparse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import sys
import tempfile
import threading
import time

REPO = Path(__file__).resolve().parents[2]
EXECUTION = REPO.parent / 'YunTAPR-Net-v2-phase-a-execution'
PAIR = REPO / 'docs/formal_training_v2/pair_20261007T070503_825794Z'
sys.path[:0] = [str(EXECUTION / 'src'), str(EXECUTION / 'scripts')]
FORBIDDEN = {'progress.json', 'checkpoint_registry.json', 'last_checkpoint_identity.json',
             'best_checkpoint_identity.json', 'training_validation_history.json', 'attempt_counters.json'}


def permitted(path):
    p = Path(path)
    if p.name in FORBIDDEN or p.suffix.lower() in {'.pt', '.pth', '.ckpt', '.nc'}:
        raise PermissionError('Monitor forbids mutable runner metadata and source/checkpoint binaries')
    if p.name not in {'steps.jsonl', 'train_diagnostics.jsonl', 'validation_diagnostics.jsonl',
                      'failure.json', 'final_report.json'} and not (
        p.name.startswith('epoch_') and p.name.endswith(('_report.json', '_complete.json'))):
        raise PermissionError('Only immutable epoch evidence and append-only journals allowed')
    return p


def tail_events(path):
    p = permitted(path)
    with p.open('rb') as stream:
        stream.seek(0, 2)
        start = max(0, stream.tell() - 65536)
        stream.seek(start)
        data = stream.read()
    if start:
        data = data.partition(b'\n')[2]
    complete = data[:data.rfind(b'\n') + 1].splitlines()
    return [json.loads(line) for line in complete]


def immutable_json(path):
    return json.loads(permitted(path).read_text(encoding='utf-8-sig'))


def status(kind, local, public, pid=None):
    from quantile_autopsy_v1.monitor import alive
    value = {'status': 'NO_LIVE_TRAINING', 'model': kind, 'age_seconds': 0,
             'monitor_source': 'APPEND_ONLY_JOURNALS_AND_IMMUTABLE_EPOCH_REPORTS',
             'monitor_reads_mutable_runner_json': False,
             '2025_RAW_ACCESS': 0, '2025_PIXELS_READ': 0, 'V2_PHASE_B_AUTHORIZED': False}
    reports = sorted(public.glob('epoch_*_report.json'))
    if reports:
        report = immutable_json(reports[-1])
        value['last_completed_epoch_report'] = report
        value['completed_epoch'] = report.get('epoch', report.get('completed_epoch'))
        value['validation_core_loss'] = report['validation']['global_val_core_loss']
        value['BEST_epoch'] = report['selection']['selected_checkpoint_epoch']
        value['patience'] = report['selection']['non_improvement_count']
        value['completed_epoch_upper_tail'] = report['diagnostics']
    attempts = sorted((local / 'audit').glob('run_*'))
    active_attempt = attempts[-1] if attempts else None
    steps = sorted(active_attempt.glob('epoch_*/steps.jsonl'), key=lambda p: p.stat().st_mtime_ns) if active_attempt else []
    if pid:
        value.update(pid=pid, process_alive=alive(pid))
        if value['process_alive']:
            value.update(status='RUNNING_NO_STEP_YET', phase='INITIALIZATION_OR_AUDIT')
    if steps:
        file = steps[-1]
        events = tail_events(file)
        done = [e for e in events if e.get('event') == 'OPTIMIZER_STEP_COMPLETED']
        if done:
            event = done[-1]
            epoch = int(file.parent.name.split('_')[1])
            value.update(epoch=epoch, step=event['update'] - (epoch - 1) * 5228,
                         train_loss=event['loss'], LR=event['LR'], gradient_norm=event['pre_clip_norm'],
                         retained_trajectory_update_in_live_attempt=event['update'],
                         latest_step_event=event, pid=event['pid'])
            value['age_seconds'] = round((time.time_ns() - event['time_ns']) / 1e9, 1)
        if pid:
            value['pid'] = pid
        value['process_alive'] = alive(value.get('pid'))
        if value['process_alive']:
            value.update(status='RUNNING', phase='TRAIN_OR_VALIDATION_SEE_EPOCH_MARKERS')
        failed = file.parent.parent / 'failure.json'
        if failed.exists():
            value.update(status='FAILED_STOP', failure=immutable_json(failed))
        diag = file.with_name('train_diagnostics.jsonl')
        if diag.exists():
            value['latest_upper_tail_forward'] = tail_events(diag)[-1:]
    final = public / 'final_report.json'
    if final.exists():
        value.update(status='COMPLETE', final_report=immutable_json(final))
    return value


def self_test(output):
    from yuntapr.training.phase_a_audit_v2 import append_event, atomic_json
    root = REPO / 'docs/v2_phase_a_authorized'
    failures = []
    reads = []
    with tempfile.TemporaryDirectory(prefix='immutable_monitor_fixture_', dir=root) as name:
        fixture = Path(name).resolve()
        assert fixture.is_relative_to(root.resolve())
        path = fixture / 'steps.jsonl'
        append_event(path, 'OPTIMIZER_STEP_COMPLETED', update=0)
        stop = threading.Event()
        def reader():
            while not stop.is_set():
                try:
                    reads.extend(tail_events(path))
                except BaseException as exc:
                    failures.append(repr(exc)); stop.set()
        worker = threading.Thread(target=reader)
        worker.start()
        try:
            for index in range(1, 1001):
                append_event(path, 'OPTIMIZER_STEP_COMPLETED', update=index)
            immutable = fixture / 'epoch_001_report.json'
            atomic_json(immutable, {'status': 'PASS'}, immutable=True)
            assert immutable_json(immutable)['status'] == 'PASS'
        finally:
            stop.set(); worker.join()
        assert not failures and reads and tail_events(path)[-1]['update'] == 1000
        rejected = []
        for forbidden in sorted(FORBIDDEN | {'epoch_014.pt', 'raw_source.nc'}):
            try:
                permitted(fixture / forbidden)
            except PermissionError:
                rejected.append(forbidden)
            else:
                raise AssertionError('Forbidden monitor path accepted')
        assert fixture.is_relative_to(root.resolve())
    result = {'status': 'PASS', 'TEST_FIXTURE_ONLY': True,
              'concurrent_append_writes': 1000, 'valid_event_observations': len(reads),
              'reader_writer_errors': failures, 'forbidden_paths_rejected': rejected,
              'immutable_epoch_report_read_pass': True, 'fixtures_cleaned': not fixture.exists(),
              'training_code_modified': False, 'formal_optimizer_steps_added': 0,
              '2025_RAW_ACCESS': 0, '2025_PIXELS_READ': 0}
    with output.open('x', encoding='utf-8', newline='\n') as stream:
        json.dump(result, stream, indent=2); stream.write('\n')
    print(json.dumps(result), flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--model', choices=['B0_MATCHED_V2', 'B1_V2'])
    parser.add_argument('--port', type=int, default=8771)
    parser.add_argument('--pid', type=int)
    parser.add_argument('--self-test-output', type=Path)
    args = parser.parse_args()
    if args.self_test_output:
        return self_test(args.self_test_output)
    kind = args.model
    auth = json.loads((REPO / 'docs/v2_phase_a_authorized/pair_20261007T070503_825794Z/authorization.json').read_text(encoding='utf-8'))
    public = PAIR / kind
    local = Path(auth['checkpoint_roots'][kind]) / auth['run_ids'][kind]
    from paired_phase_a_v2.monitor import PAGE
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_): pass
        def do_POST(self): self.send_error(405, 'Read only')
        def do_GET(self):
            route = self.path.split('?', 1)[0]
            if route == '/':
                body, mime = PAGE.encode(), 'text/html; charset=utf-8'
            elif route == '/api/status':
                try:
                    value = status(kind, local, public, args.pid)
                except Exception as exc:
                    value = {'status': 'MONITOR_READ_ERROR', 'error': repr(exc)}
                body, mime = json.dumps(value, ensure_ascii=False, allow_nan=False).encode(), 'application/json; charset=utf-8'
            else:
                self.send_error(404); return
            self.send_response(200); self.send_header('Content-Type', mime)
            self.send_header('Cache-Control', 'no-store'); self.send_header('Content-Length', str(len(body)))
            self.end_headers(); self.wfile.write(body)
    print(json.dumps({'url': f'http://127.0.0.1:{args.port}/', 'model': kind}), flush=True)
    ThreadingHTTPServer(('127.0.0.1', args.port), Handler).serve_forever()


if __name__ == '__main__':
    main()
