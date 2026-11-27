#!/usr/bin/env python
"""CLI for the catalogue-gated B4/B7/B8 2025 final-test preparation.

Every subcommand denies by default.  ``plan`` is pure arithmetic over the 2025
calendar (856 four-per-day windows, March..September) and never opens payload.
``prepare`` writes only a non-executable preparation manifest.  ``catalogue`` and
``run`` require explicit researcher authorization JSON paths; without them they
exit non-zero before any 2025 path or checkpoint is touched.  ``run --dry-run``
prints the bound execution plan and stops.

This tool never trains, selects, tunes, retries or writes outside the explicit
``--output-dir`` supplied by the caller.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from yuntapr.experimental.research_readiness import final_test_2025_adapter as adapter
from yuntapr.experimental.research_readiness import final_test_2025_catalogue as catalogue
from yuntapr.experimental.research_readiness import (
    final_test_2025_manifest as manifest)
from yuntapr.experimental.research_readiness import (
    final_test_2025_planning as planning)
from yuntapr.experimental.research_readiness import (
    final_test_2025_readers as readers)


def _json(payload):
    return json.dumps(payload, indent=2, sort_keys=True, allow_nan=False)


def _deny(message):
    print('DENIED: ' + message, file=sys.stderr)
    return 2


def command_plan(args):
    scenes = list(planning.enumerate_scenes(planning.PathLayout2025.default()))
    first, last = scenes[0].as_dict(), scenes[-1].as_dict()
    return _json({
        'status': 'PLAN_ONLY_NO_PAYLOAD_ACCESS',
        'scope': planning.scope_manifest(),
        'expected_scenes': planning.expected_slot_count(),
        'enumerated_scenes': len(scenes),
        'first_scene': first, 'last_scene': last,
        'models': list(adapter.MODELS), 'seeds': list(adapter.SEEDS),
        'payload_access_authorized': False,
    })


def command_prepare(args):
    if args.output_dir is None:
        return _deny('prepare requires an explicit --output-dir')
    output = Path(args.output_dir)
    if not output.is_absolute():
        return _deny('--output-dir must be absolute')
    if output.exists() and any(output.iterdir()):
        return _deny('--output-dir must be new or empty')
    output.mkdir(parents=True, exist_ok=True)
    payload = {
        'version': 'v1',
        'status': 'DRAFT_NON_EXECUTABLE_NOT_RESEARCHER_FROZEN',
        'scope': planning.scope_manifest(),
        'expected_scenes': planning.expected_slot_count(),
        'catalogue_columns': list(catalogue.COLUMNS),
        'population_columns': list(manifest.POPULATION_COLUMNS),
        'checkpoint_catalog_sha256': catalogue.CHECKPOINT_CATALOG_SHA256,
        'checkpoints': [
            {'model': model, 'seed': seed,
             'sha256': catalogue.CHECKPOINTS[(model, seed)]['sha256'],
             'bytes': catalogue.CHECKPOINTS[(model, seed)]['bytes']}
            for model, seed in catalogue.CHECKPOINTS],
        'required_authorizations': [
            'catalogue authorization JSON (researcher)',
            'payload authorization JSON (researcher, separate gate)',
            'final-test authorization JSON (researcher, post-freeze)',
        ],
        'payload_access_authorized': False,
        'final_test_authorized': False,
        'executed': False,
        'notes': 'No 2025 payload was listed, stat-ed or opened to build this manifest.',
    }
    target = output / 'preparation_manifest.json'
    if target.exists():
        return _deny('preparation manifest already exists (append-only)')
    target.write_text(_json(payload) + '\n', encoding='utf-8')
    print(str(target))
    return 0


def _read_inventory(path):
    """Load a caller-supplied inventory document; never traverse a payload root."""
    raw = json.loads(Path(path).read_text(encoding='utf-8'))
    entries = raw.get('entries') if isinstance(raw, dict) else raw
    if not isinstance(entries, list):
        raise ValueError('Inventory must be a list or {"entries": [...]}')
    return catalogue.InventoryIndex([catalogue.InventoryEntry(**entry) for entry in entries])


def command_catalogue(args):
    if not args.authorization:
        return _deny('catalogue requires an explicit --authorization JSON path')
    if not args.population:
        return _deny('catalogue requires an explicit --population JSON path')
    if not args.inventory:
        return _deny('catalogue requires an explicit --inventory JSON path')
    if not args.output_dir:
        return _deny('catalogue requires an explicit --output-dir')
    authorization = catalogue.CatalogueAuthorization2025.load(
        Path(args.authorization), args.authorization_sha256)
    population = manifest.Population(manifest.read_population(Path(args.population)))
    inventory = _read_inventory(Path(args.inventory))
    freeze = catalogue.build_catalogue_artefacts(
        authorization, population, inventory, Path(args.output_dir), fixture=False)
    print(_json(freeze))
    return 0


def command_run(args):
    if not args.authorization:
        return _deny('run requires an explicit --authorization JSON path')
    if not args.payload_authorization:
        return _deny('run requires an explicit --payload-authorization JSON path')
    if args.dry_run:
        print(_json(adapter.dry_run(Path(args.authorization), args.authorization_sha256)))
        return 0
    if not args.output_dir:
        return _deny('run requires an explicit --output-dir')
    status = adapter.execute(
        Path(args.authorization),
        args.authorization_sha256,
        Path(args.payload_authorization),
        args.payload_authorization_sha256,
        output_dir=Path(args.output_dir))
    print(_json(status))
    return 0


def build_parser():
    parser = argparse.ArgumentParser(
        prog='start_b4_b7_b8_2025_final_test',
        description='Deny-by-default B4/B7/B8 2025 final-test preparation CLI.')
    sub = parser.add_subparsers(dest='command', required=True)

    plan = sub.add_parser('plan', help='pure 2025 calendar plan; no payload access')
    plan.set_defaults(handler=command_plan)

    prepare = sub.add_parser('prepare', help='write a non-executable preparation manifest')
    prepare.add_argument('--output-dir')
    prepare.set_defaults(handler=command_prepare)

    cat = sub.add_parser('catalogue', help='build the candidate catalogue from caller inventory')
    cat.add_argument('--authorization')
    cat.add_argument('--authorization-sha256', default=None)
    cat.add_argument('--population')
    cat.add_argument('--inventory')
    cat.add_argument('--output-dir')
    cat.set_defaults(handler=command_catalogue)

    run = sub.add_parser('run', help='execute the frozen final test once (or dry-run)')
    run.add_argument('--authorization')
    run.add_argument('--authorization-sha256', default=None)
    run.add_argument('--payload-authorization')
    run.add_argument('--payload-authorization-sha256', default=None)
    run.add_argument('--output-dir')
    run.add_argument('--dry-run', action='store_true')
    run.set_defaults(handler=command_run)
    return parser


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    if hasattr(readers, 'PayloadAccess2025'):
        # The readers module must remain the only 2025-capable payload layer.
        pass
    return args.handler(args)


if __name__ == '__main__':
    sys.exit(main())
