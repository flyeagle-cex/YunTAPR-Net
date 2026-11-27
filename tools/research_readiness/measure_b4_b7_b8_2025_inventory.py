#!/usr/bin/env python
"""Command line entry for the stat-only 2025 final-test inventory measurement.

The only executable action is ``run`` and it requires an exact-key researcher
authorization bound to the frozen protocol and implementation.  ``plan`` prints
the theoretical calendar counts without touching any 2025 source.  This tool
never opens, hashes or decodes a payload file and never loads a checkpoint.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
_SRC = REPO_ROOT / 'src'
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from yuntapr.experimental.research_readiness import final_test_2025_inventory as inventory  # noqa: E402
from yuntapr.experimental.research_readiness.final_test_2025_planning import PathLayout2025  # noqa: E402

TASK = 'B4_B7_B8_2025_INVENTORY_MEASUREMENT'


def _emit(payload):
    print(json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False))


def _write_failure(output_root, message):
    output_root = Path(output_root)
    try:
        output_root.mkdir(parents=True, exist_ok=True)
        (output_root / 'failure.json').write_text(json.dumps({
            'task': TASK,
            'status': 'STOP_REQUIRED',
            'error': message,
            'automatic_retry': False,
        }, indent=2, sort_keys=True) + '\n', encoding='utf-8')
    except OSError:
        pass


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='action', required=True)

    plan = sub.add_parser('plan', help='theoretical calendar counts; no 2025 I/O')
    plan.add_argument('--months', default='3,4,5,6,7,8,9')

    run = sub.add_parser('run', help='one stat-only measurement under researcher authorization')
    run.add_argument('--authorization', required=True)
    run.add_argument('--authorization-sha256', required=True)
    run.add_argument('--output-root', required=True)

    args = parser.parse_args(argv)
    layout = PathLayout2025.default()

    if args.action == 'plan':
        months = tuple(int(part) for part in args.months.split(',') if part.strip())
        if months != tuple(sorted(set(months))):
            raise SystemExit('months must be strictly ordered and unique')
        _emit(inventory.plan_counts(layout, months=months))
        return 0

    output_root = Path(args.output_root)
    try:
        if output_root.exists():
            raise FileExistsError('output root must not exist: ' + str(output_root))
        status = inventory.run_measurement(
            args.authorization, args.authorization_sha256, output_root,
            repo_root=REPO_ROOT, layout=layout,
        )
    except Exception as exc:  # noqa: BLE001 - one-shot failure surface
        _write_failure(output_root, type(exc).__name__ + ': ' + str(exc))
        _emit({'task': TASK, 'status': 'STOP_REQUIRED',
               'error': type(exc).__name__ + ': ' + str(exc),
               'automatic_retry': False})
        return 2
    _emit(status)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
