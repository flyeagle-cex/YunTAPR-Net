"""Exactly one bounded attempt; watchdog enforces time and process memory."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import threading
import time

HERE = Path(__file__).absolute().parent; ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT/'src'))
from yuntapr.experimental.phase_b_v2_real_forward_pilot import LIMITS
from yuntapr.experimental.phase_b_v2_real_forward_pilot.resources import memory, utcnow
parser = argparse.ArgumentParser(); parser.add_argument('--worker', action='store_true')
parser.add_argument('--pre-access-repair', action='store_true')
args = parser.parse_args(); private = HERE/'.local'/('attempt_002' if args.pre_access_repair else 'attempt_001')
if args.worker:
    from yuntapr.experimental.phase_b_v2_real_forward_pilot.pilot import run
    run(private)
else:
    carry = None
    if args.pre_access_repair:
        previous = json.loads((HERE/'.local/attempt_001/worker_status.json').read_bytes())
        original = json.loads((HERE/'.local/attempt_001/supervisor.json').read_bytes())
        if (previous['raw_reads'] or any(previous['model_batch_attempts'].values())
            or previous['failure']['type'] != 'AssertionError'
            or not previous['failure']['reason'].startswith('Duplicate torch object')):
            raise PermissionError('REPAIR_ALLOWED_ONLY_BEFORE_RAW_OR_MODEL_FORWARD')
        carry = dict(reason='PRE_ACCESS_DYNAMO_WRAPPER_REPAIR', raw_payload_content_bytes=0,
            model_forward_attempts=0, public_metadata_content_bytes=previous['accounted_content_bytes'],
            original_started_at_utc=original['started_at_utc'])
    private.mkdir(parents=True, exist_ok=False)
    if carry: (private/'pre_access_carry.json').write_bytes(json.dumps(carry).encode())
    start = time.monotonic(); started = utcnow()
    env = dict(os.environ, PYTHONUTF8='1', PYTHONHASHSEED='2026', CUBLAS_WORKSPACE_CONFIG=':4096:8')
    command = [sys.executable, str(Path(__file__).absolute()), '--worker']
    if args.pre_access_repair: command.append('--pre-access-repair')
    process = subprocess.Popen(command,
        cwd=ROOT, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    def pump():
        with (private/'worker_private.log').open('wb') as secret, (HERE/('execution_progress_002.log' if carry else 'execution_progress.log')).open('xb') as public:
            for raw in iter(process.stdout.readline, b''):
                secret.write(raw); secret.flush()
                try:
                    record = json.loads(raw); safe = (json.dumps(record)+'\n').encode()
                    public.write(safe); public.flush(); print(safe.decode(), end='', flush=True)
                except (ValueError, UnicodeDecodeError): pass
    thread = threading.Thread(target=pump, daemon=True); thread.start()
    stop = None; peak = None
    from datetime import datetime, timezone
    prior_seconds = (datetime.now(timezone.utc)-datetime.fromisoformat(carry['original_started_at_utc'])).total_seconds() if carry else 0
    while process.poll() is None:
        try:
            peak = memory(int(process._handle))
            if peak['peak_working_set_bytes'] > LIMITS['max_working_set_bytes']:
                stop = 'SUPERVISOR_THREE_GIB_WORKING_SET_LIMIT'
        except OSError:
            if process.poll() is None: stop = 'SUPERVISOR_MEMORY_NOT_VERIFIABLE'
        if time.monotonic()-start+prior_seconds >= LIMITS['max_elapsed_seconds']-5:
            stop = 'SUPERVISOR_THIRTY_MINUTE_LIMIT'
        if stop: process.kill(); break
        time.sleep(.2)
    process.wait(timeout=5); thread.join(timeout=5)
    receipt = {'started_at_utc': started, 'finished_at_utc': utcnow(),
        'elapsed_seconds': time.monotonic()-start, 'original_budget_elapsed_seconds':time.monotonic()-start+prior_seconds,
        'worker_exit_code': process.returncode,
        'hard_stop': stop, 'last_process_resources': peak,
        'resource_poll_seconds': .2, 'watchdog_seconds': LIMITS['max_elapsed_seconds']-5}
    (private/'supervisor.json').write_bytes((json.dumps(receipt, indent=2)+'\n').encode())
    from export_reports import build
    status = build(private, receipt)
    print(json.dumps({'overall_status': status['overall_status'], 'decoded_scenes': status['decoded_scenes'],
                      'model_batches': status['model_batch_successes']}), flush=True)
    sys.exit(0 if status['overall_status'] == 'BOUNDED_REAL_FORWARD_PILOT_PASS' else 2)
