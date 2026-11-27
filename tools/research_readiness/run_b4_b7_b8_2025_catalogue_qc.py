"""Run or plan the authorized 2025 catalogue QC (hash-only payload) gate.

``plan`` reads only the frozen stat-only inventory measurement JSON and prints the
expected counts/bytes; it never opens, stats or lists a 2025 payload path.
``run`` requires the researcher catalogue-QC authorization and the measurement
digest explicitly on the command line; any failure prints STOP_REQUIRED on stderr
and exits non-zero (2).  Nothing is ever retried automatically.
"""

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT / 'src') not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / 'src'))

from yuntapr.experimental.research_readiness import final_test_2025_catalogue_execution as execution


def build_parser():
    parser = argparse.ArgumentParser(
        prog='run_b4_b7_b8_2025_catalogue_qc',
        description='Authorized hash-only 2025 catalogue QC and catalogue freeze.')
    commands = parser.add_subparsers(dest='command', required=True)
    plan = commands.add_parser(
        'plan', help='print expected counts/bytes from the frozen measurement JSON; no payload I/O')
    plan.add_argument('--inventory-measurement', required=True,
                      help='frozen inventory_measurement_v1.json path')
    run = commands.add_parser('run', help='execute the authorized hash-only QC pass')
    run.add_argument('--authorization', required=True,
                     help='researcher catalogue-QC authorization JSON')
    run.add_argument('--authorization-sha256', required=True,
                     help='expected SHA-256 of the authorization file')
    run.add_argument('--inventory-measurement', required=True,
                     help='frozen inventory_measurement_v1.json path')
    run.add_argument('--inventory-measurement-sha256', required=True,
                     help='expected SHA-256 of the measurement file')
    run.add_argument('--output-dir', required=True,
                     help='new append-only catalogue QC output directory')
    return parser


def _plan(args):
    document, digest = execution.load_measurement(args.inventory_measurement)
    plan = execution.measurement_plan(document)
    plan['inventory_measurement_sha256'] = digest
    print(json.dumps(plan, indent=2, sort_keys=True, ensure_ascii=False))
    return 0


def _run(args):
    status = execution.run_catalogue_qc(
        args.authorization, args.authorization_sha256,
        args.inventory_measurement, args.inventory_measurement_sha256,
        args.output_dir)
    print(json.dumps(status, indent=2, sort_keys=True, ensure_ascii=False))
    return 0


def main(argv=None):
    args = build_parser().parse_args(argv)
    try:
        return _plan(args) if args.command == 'plan' else _run(args)
    except Exception as error:  # noqa: BLE001 - STOP_REQUIRED surface
        print(json.dumps({'status': 'STOP_REQUIRED',
                          'error_type': type(error).__name__,
                          'error': str(error)}, sort_keys=True, ensure_ascii=False),
              file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
