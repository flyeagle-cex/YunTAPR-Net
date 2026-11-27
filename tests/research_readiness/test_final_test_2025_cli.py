"""Synthetic test for the deny-by-default 2025 final-test CLI wiring.

The CLI must call ``adapter.execute`` with an argument shape that actually binds to
its signature; a mismatch aborts the one-shot run before any payload access and
consumes the researcher authorization.  No test here opens any 2025 raw path.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path
from types import SimpleNamespace

REPO = Path(__file__).resolve().parents[2]
CLI_PATH = REPO / 'tools/research_readiness/start_b4_b7_b8_2025_final_test.py'


def _load_cli():
    spec = importlib.util.spec_from_file_location('final_test_2025_cli', CLI_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_run_passes_arguments_that_bind_to_execute(monkeypatch):
    cli = _load_cli()
    captured = {}

    def fake_execute(*args, **kwargs):
        captured['args'] = args
        captured['kwargs'] = kwargs
        return {'status': 'FAKE_EXECUTED'}

    monkeypatch.setattr(cli.adapter, 'execute', fake_execute)
    args = SimpleNamespace(
        authorization='auth.json',
        authorization_sha256='a' * 64,
        payload_authorization='payload.json',
        payload_authorization_sha256='b' * 64,
        output_dir='out',
        dry_run=False,
    )
    assert cli.command_run(args) == 0
    assert captured['args'][0] == Path('auth.json')
    assert captured['args'][1] == 'a' * 64
    assert captured['args'][2] == Path('payload.json')
    assert captured['args'][3] == 'b' * 64
    assert captured['kwargs'] == {'output_dir': Path('out')}
