"""Reproduce default .NET ReadLines denial; verify explicit shared-write reader.

Only owned synthetic journals are used; no training/source/checkpoint accesses.
"""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

REPO = Path(__file__).resolve().parents[2]
EXECUTION = REPO.parent / 'YunTAPR-Net-v2-phase-a-execution'
sys.path.insert(0, str(EXECUTION / 'src'))


def held_reader(path, safe):
    quoted = str(path).replace("'", "''")
    if safe:
        code = f"$taskFile=[IO.FileStream]::new('{quoted}',[IO.FileMode]::Open,[IO.FileAccess]::Read,([IO.FileShare]::ReadWrite -bor [IO.FileShare]::Delete)); $taskReader=[IO.StreamReader]::new($taskFile); $null=$taskReader.ReadLine();"
    else:
        code = f"$taskReader=[IO.File]::ReadLines('{quoted}').GetEnumerator(); $null=$taskReader.MoveNext();"
    code += "[Console]::Out.WriteLine('READER_HELD'); [Console]::Out.Flush(); $null=[Console]::In.ReadLine(); $taskReader.Dispose();"
    process = subprocess.Popen([shutil.which('pwsh'), '-NoProfile', '-NonInteractive', '-Command', code],
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
        creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
    line = process.stdout.readline()
    if line.strip() != 'READER_HELD':
        process.kill(); raise RuntimeError('Reader fixture did not acquire handle: ' + line)
    return process


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    from yuntapr.training.phase_a_audit_v2 import append_event
    root = REPO / 'docs/v2_phase_a_authorized'
    with tempfile.TemporaryDirectory(prefix='journal_reader_fixture_', dir=root) as name:
        fixture = Path(name).resolve()
        assert fixture.is_relative_to(root.resolve())
        file = fixture / 'steps.jsonl'
        append_event(file, 'OPTIMIZER_STEP_COMPLETED', update=0)
        process = held_reader(file, False)
        try:
            try:
                append_event(file, 'OPTIMIZER_STEP_ATTEMPT', update=1)
            except PermissionError as exc:
                reproduced = {'errno': exc.errno, 'winerror': getattr(exc, 'winerror', None), 'error': repr(exc)}
            else:
                raise AssertionError('Expected .NET ReadLines sharing conflict did not occur')
        finally:
            _, error = process.communicate('\n', timeout=10)
            assert process.returncode == 0, error
        process = held_reader(file, True)
        try:
            for update in range(1, 1001):
                append_event(file, 'OPTIMIZER_STEP_COMPLETED', update=update)
        finally:
            _, error = process.communicate('\n', timeout=10)
            assert process.returncode == 0, error
        assert len(file.read_text(encoding='utf-8').splitlines()) == 1001
        assert fixture.is_relative_to(root.resolve())
    result = {'status': 'PASS', 'TEST_FIXTURE_ONLY': True,
              'default_dotnet_readlines_blocks_pinned_append_event': True,
              'reproduced_error': reproduced,
              'explicit_readwrite_delete_reader_concurrent_appends_pass': 1000,
              'approved_audit_reader_policy': 'No default .NET File.ReadLines/Get-Content on live journals; use explicit FileShare.ReadWrite|Delete or tested Python reader.',
              'mutable_atomic_json_policy': 'Never open live atomic-replacement targets.',
              'fixtures_cleaned': not fixture.exists(), 'formal_optimizer_steps_added': 0,
              '2025_RAW_ACCESS': 0, '2025_PIXELS_READ': 0,
              'completed_utc': datetime.now(timezone.utc).isoformat()}
    with args.output.open('x', encoding='utf-8', newline='\n') as stream:
        json.dump(result, stream, indent=2); stream.write('\n')
    print(json.dumps(result), flush=True)


if __name__ == '__main__': main()
