"""Publish only sanitized artificial receipts and a read-only stop observation."""
from pathlib import Path
from datetime import datetime, timezone
import hashlib, json, re, subprocess, sys

ROOT = Path(__file__).absolute().parents[2]
sys.path.insert(0, str(ROOT / 'src'))
OUT = ROOT / 'docs/phase_b_v2_console_lifetime_repair/v1'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(name, value):
    path = OUT / name
    if path.exists():
        raise PermissionError('NO_REVIEW_RECEIPT_OVERWRITE')
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False) + '\n', encoding='utf-8', newline='\n')


def main():
    # All inputs are fixed project metadata/artificial receipts, never data,
    # weights or actual model states. No recovery/start function is called.
    from yuntapr.training.phase_b_v2_seed2027_b1_epoch7_recovery_v3.control import status
    from yuntapr.training.phase_b_v2_seed2027_b1_epoch7_recovery_v3.protocol import DB, LOCAL
    before = sha(DB)
    snapshot = status()
    if (snapshot['effective_state'] != 'STOPPED_UNCLEAN' or snapshot['reserved'] != 166305
        or snapshot['returned_verified'] != 166304 or snapshot['new_reserved'] != 922
        or snapshot['new_returned_verified'] != 922 or snapshot['hard_cap'] != 364047):
        raise ValueError('NEW_STATE_REQUIRES_NEW_READ_ONLY_REVIEW')
    session = LOCAL / 'sessions/session_0001'
    task_name = json.loads((session / 'task_request.json').read_text(encoding='utf-8'))['task_name']
    from yuntapr.experimental.phase_b_v2_owner_lifetime_candidate.task_bridge import ps, quote
    task = json.loads(ps("$ErrorActionPreference='Stop';[Console]::OutputEncoding=[Text.Encoding]::UTF8;"
        + f"$t=Get-ScheduledTask -TaskName {quote(task_name)};$i=Get-ScheduledTaskInfo -TaskName {quote(task_name)};"
        + "[pscustomobject]@{state=[string]$t.State;result=$i.LastTaskResult;executable=[IO.Path]::GetFileName($t.Actions[0].Execute);restart_count=$t.Settings.RestartCount}|ConvertTo-Json -Compress"))
    if task['result'] != 3221225786:
        raise ValueError('TASK_RESULT_CHANGED')
    if sha(DB) != before:
        raise ValueError('HISTORICAL_LEDGER_CHANGED_DURING_AUDIT')
    write('STOP_OBSERVATION.json', dict(utc=datetime.now(timezone.utc).isoformat(),
        snapshot=snapshot, scheduler=task, scheduler_result_hex='0xC000013A',
        researcher_report='Only Codex was closed; no PowerShell close or Ctrl+C reported.',
        actual_exit_initiator='NOT_VERIFIED', historical_db_sha256=before,
        historical_db_unchanged_during_review=True,
        missing_receipts=[name for name in ('termination.json', 'task_failure.json',
            'supervisor_failure_private.txt', 'failure_private.txt') if not (session / name).exists()],
        checkpoint_payload_reads_this_review=0, new_optimizer_steps=0,
        new_recovery_authorization=False))
    latest = OUT / '.local/artificial_tasks_20261021T011613_449f1af0/results.json'
    results = json.loads(latest.read_text(encoding='utf-8'))
    if not results['pass_all'] or results['tests_run'] != 5 or results['skipped']:
        raise ValueError('ARTIFICIAL_TESTS_NOT_COMPLETE')
    write('ARTIFICIAL_RESULTS.json', results)
    raw_dir = OUT / '.local/raw_logs'
    raw_dir.mkdir(parents=True, exist_ok=False)
    logs = OUT / 'tests'
    logs.mkdir(exist_ok=False)
    receipts = []
    for number in range(1, 7):
        original = OUT / f'attempt_{number:03d}.log'
        saved = raw_dir / original.name
        original.rename(saved)
        text = saved.read_text(encoding='utf-8', errors='replace')
        text = re.sub(r'[A-Za-z]:[\\/][^\r\n"]*?YunTAPR-Net-push-chunks', '<REPOSITORY>', text)
        public = logs / saved.name
        public.write_text(text, encoding='utf-8', newline='\n')
        receipts.append(dict(attempt=number, raw_sha256=sha(saved),
            public_path=public.relative_to(ROOT).as_posix(), public_sha256=sha(public)))
    write('TEST_LOG_IDENTITY.json', dict(raw_preserved_private=True, logs=receipts))
    protected = subprocess.check_output(['git', 'ls-files', 'src/yuntapr/models',
        'src/yuntapr/losses', 'src/yuntapr/training/phase_b_v2_seed2027_b1_epoch7_recovery_v3',
        'src/yuntapr/experimental/phase_b_v2_execution_watchdog_candidate', 'config/science_v2'],
        cwd=ROOT, text=True, encoding='utf-8').splitlines()
    pins = {}
    for relative in protected:
        path = ROOT / relative
        actual = sha(path)
        committed = hashlib.sha256(subprocess.check_output(['git', 'show', 'HEAD:' + relative], cwd=ROOT)).hexdigest()
        # Repository checkouts may convert LF to CRLF. Identity comparison must
        # use Git's index filter when relevant, never normalize raw payloads.
        indexed = subprocess.check_output(['git', 'hash-object', '--path=' + relative, str(path)],
            cwd=ROOT, text=True).strip()
        expected = subprocess.check_output(['git', 'rev-parse', 'HEAD:' + relative], cwd=ROOT, text=True).strip()
        if indexed != expected:
            raise ValueError('PROTECTED_SOURCE_CHANGED:' + relative)
        pins[relative] = dict(worktree_sha256=actual, committed_bytes_sha256=committed,
            git_filtered_identity_match=True)
    write('PROTECTED_SOURCE_IDENTITY.json', dict(files=pins, count=len(pins),
        models_losses_protocol_and_old_runner_unchanged=True,
        historical_db_sha256=before, new_data_reads=0, new_optimizer_steps=0))


if __name__ == '__main__':
    main()
