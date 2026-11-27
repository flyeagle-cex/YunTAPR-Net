"""Stat-only 2025 source inventory measurement for the twelve-model final test.

Scope of this module
--------------------
The frozen protocol for the B4/B7/B8/B7_ZERO_DOTE 2025 final test requires an
exact unique-file set and exact byte totals *before* any payload content may be
read (hashed, decoded) or any checkpoint may be loaded.  The 856 analysis slots
are a purely theoretical calendar count; the real population is unknown.

This module therefore implements the **inventory measurement stage only**:

* it enumerates the expected relative paths (six satellite slots, GFS main and
  thermo, IMERG day file) from the frozen layout templates;
* it visits every unique expected path with ``os.stat`` **only** to determine
  presence, byte size, and mtime;
* it writes a measured unique-file manifest, per-modality byte totals and a
  sanitized summary to a new (never existing) output directory.

Hard prohibitions enforced here (and tested):

* no payload file content is opened, hashed or decoded;
* no checkpoint is stat'ed, hashed or loaded;
* no model is built and no metric is computed;
* only March..September 2025 analysis slots are enumerated (October rejected);
* the run requires an exact-key researcher authorization JSON bound to this
  implementation (protocol, this module, the planning module and the CLI).

The measured totals are the input for the separate catalogue-QC / payload-phase
budget request; they do not authorize any content read by themselves.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import stat as stat_module
import time
from datetime import datetime, timezone
from pathlib import Path

from .final_test_2025_planning import (
    ANALYSIS_HOURS,
    DEFAULT_MONTHS,
    PathLayout2025,
    canonical_sha,
    enumerate_scenes,
    utc,
)

INVENTORY_KIND = 'B4_B7_B8_2025_INVENTORY_MEASUREMENT'
INVENTORY_SCOPE = 'B4_B7_B8_2025_INVENTORY_MEASUREMENT_ONLY'
INVENTORY_STATUS = 'MEASURED_STAT_ONLY'
INVENTORY_VERSION = 'v1'

MAX_UNIQUE_FILES = 20_000
MAX_STAT_SECONDS = 900.0
MARCH_SEPTEMBER_MONTHS = tuple(range(3, 10))
# The first March analysis (2025-03-01T00:00Z) carries in a 2025-02-28 window.
ALLOWED_DATE_TOKENS = ('20250228',) + tuple(
    '2025%02d%02d' % (month, day)
    for month, days in ((3, 31), (4, 30), (5, 31), (6, 30), (7, 31), (8, 31), (9, 30))
    for day in range(1, days + 1)
)
_ALLOWED_DATE_TOKEN_SET = frozenset(ALLOWED_DATE_TOKENS)

AUTHORIZATION_KEYS = frozenset({
    'version',
    'decision_id',
    'AUTHORIZED_BY',
    'scope',
    'INVENTORY_MEASUREMENT_2025_AUTHORIZED',
    'protocol_sha256',
    'implementation_sha256',
    'created_utc',
})

IMPLEMENTATION_FILES = (
    'config/evaluation/b4_b7_b8_b7zero_2025_final_test_protocol_v1.yaml',
    'src/yuntapr/experimental/research_readiness/final_test_2025_inventory.py',
    'src/yuntapr/experimental/research_readiness/final_test_2025_planning.py',
    'tools/research_readiness/measure_b4_b7_b8_2025_inventory.py',
)

PROTOCOL_RELPATH = 'config/evaluation/b4_b7_b8_b7zero_2025_final_test_protocol_v1.yaml'
MODALITY_ORDER = ('himawari', 'gfs_main', 'gfs_thermo', 'imerg')
_SHA256 = re.compile(r'[0-9a-f]{64}')
_DATE_TOKEN = re.compile(r'(?<!\d)2025(0[1-9]|1[0-2])([0-3]\d)')


def _now():
    return datetime.now(timezone.utc).replace(microsecond=0)


def _iso(value):
    if isinstance(value, str):
        value = utc(value)
    return value.isoformat()


def sha256_file(path):
    digest = hashlib.sha256()
    with open(path, 'rb') as handle:
        for block in iter(lambda: handle.read(1 << 20), b''):
            digest.update(block)
    return digest.hexdigest()


def implementation_hashes(repo_root):
    """Exact SHA-256 mapping bound by the inventory authorization."""
    repo_root = Path(repo_root)
    hashes = {}
    for relpath in IMPLEMENTATION_FILES:
        target = repo_root / relpath
        if not target.is_file():
            raise FileNotFoundError(relpath)
        hashes[relpath] = sha256_file(target)
    return hashes


def validate_authorization(payload, repo_root, protocol_sha256=None):
    """Validate the exact-key stat-only authorization object.

    Returns a normalized policy dict; any deviation raises.  The authorization
    never permits content reads: it only gates the stat-only measurement.
    """
    if not isinstance(payload, dict):
        raise TypeError('Authorization object required')
    extra = set(payload) - AUTHORIZATION_KEYS
    missing = AUTHORIZATION_KEYS - set(payload)
    if extra or missing:
        raise ValueError(
            'Authorization keys must be exact; missing=%s unexpected=%s'
            % (sorted(missing), sorted(extra))
        )
    if payload['version'] != INVENTORY_VERSION:
        raise ValueError('Unsupported authorization version')
    if payload['AUTHORIZED_BY'] != 'RESEARCHER':
        raise PermissionError('Inventory authorization must come from the researcher')
    if payload['scope'] != INVENTORY_SCOPE:
        raise ValueError('Inventory authorization scope mismatch')
    if payload['INVENTORY_MEASUREMENT_2025_AUTHORIZED'] is not True:
        raise PermissionError('Inventory measurement is not authorized')
    if not isinstance(payload['decision_id'], str) or not payload['decision_id'].strip():
        raise ValueError('Non-empty decision_id required')
    for key in ('protocol_sha256', 'implementation_sha256'):
        value = payload[key]
        if key == 'protocol_sha256':
            if not isinstance(value, str) or not _SHA256.fullmatch(value):
                raise ValueError('protocol_sha256 must be a lowercase SHA-256')
        else:
            if not isinstance(value, dict) or not value:
                raise ValueError('implementation_sha256 must be a non-empty mapping')
            for relpath, digest in value.items():
                if not isinstance(relpath, str) or not isinstance(digest, str) or not _SHA256.fullmatch(digest):
                    raise ValueError('Malformed implementation_sha256 entry')
    repo_root = Path(repo_root)
    expected_protocol = sha256_file(repo_root / PROTOCOL_RELPATH)
    if payload['protocol_sha256'] != expected_protocol:
        raise PermissionError('protocol_sha256 mismatch')
    if protocol_sha256 is not None and payload['protocol_sha256'] != protocol_sha256:
        raise PermissionError('caller protocol_sha256 mismatch')
    if payload['implementation_sha256'] != implementation_hashes(repo_root):
        raise PermissionError('implementation_sha256 mismatch')
    created = utc(payload['created_utc'])
    if created.year < 2025:
        raise ValueError('created_utc must not precede the 2025 final-test scope')
    return dict(
        decision_id=payload['decision_id'],
        authorized_by=payload['AUTHORIZED_BY'],
        scope=payload['scope'],
        created_utc=created.isoformat(),
        protocol_sha256=payload['protocol_sha256'],
        implementation_sha256=dict(payload['implementation_sha256']),
    )


def _assert_frozen_scope(relpath):
    """Reject anything outside February-28..September-30 2025 before stat."""
    if not isinstance(relpath, str) or not relpath:
        raise ValueError('Non-empty relative path required')
    text = relpath.replace('\\', '/')
    if '..' in text.split('/') or text.startswith('/'):
        raise ValueError('Relative path must stay below its root: ' + text)
    head = text.split('/')[0]
    if not (head == '2025' or (len(head) == 6 and head.startswith('2025') and head[4:].isdigit())):
        raise PermissionError('Unexpected 2025 root layout: ' + text)
    tokens = {match.group(0) for match in _DATE_TOKEN.finditer(text)}
    if not tokens:
        raise PermissionError('No 2025 date token in path: ' + text)
    if any(token not in _ALLOWED_DATE_TOKEN_SET for token in tokens):
        raise PermissionError('Path outside the frozen 2025 carry-in scope: ' + text)
    return text


def build_expected(layout=None, *, months=DEFAULT_MONTHS, analysis_start=None, analysis_end=None):
    """Expected unique relative paths per modality (in-memory, no I/O)."""
    if layout is None:
        layout = PathLayout2025.default()
    if not isinstance(layout, PathLayout2025):
        raise TypeError('PathLayout2025 required')
    months = tuple(months)
    if not months or any(month not in MARCH_SEPTEMBER_MONTHS for month in months):
        raise PermissionError('Inventory measurement is March..September only')
    scenes = enumerate_scenes(
        layout, months=months, allow_october=False,
        analysis_start=analysis_start, analysis_end=analysis_end,
    )
    unique = {kind: set() for kind in MODALITY_ORDER}
    scene_paths = []
    for scene in scenes:
        satellite_paths = [_assert_frozen_scope(frame.relative_path) for frame in scene.satellites]
        gfs_main = _assert_frozen_scope(scene.gfs_main_relative_path)
        gfs_thermo = _assert_frozen_scope(scene.gfs_thermo_relative_path)
        imerg = _assert_frozen_scope(scene.imerg_day_relative_path)
        scene_paths.append(dict(sample_id=scene.sample_id, month=scene.month,
                                satellites=satellite_paths, gfs_main=gfs_main,
                                gfs_thermo=gfs_thermo, imerg=imerg))
        for path in satellite_paths:
            unique['himawari'].add(path)
        unique['gfs_main'].add(gfs_main)
        unique['gfs_thermo'].add(gfs_thermo)
        unique['imerg'].add(imerg)
    expected = {
        'expected_scenes': len(scenes),
        'expected_analysis_months': list(months),
        'expected_analysis_hours': list(ANALYSIS_HOURS),
        'scene_count': len(scenes),
        'expected_unique': {kind: len(unique[kind]) for kind in MODALITY_ORDER},
        'unique_paths': {kind: sorted(unique[kind]) for kind in MODALITY_ORDER},
        'scene_paths': scene_paths,
        'canonical_sha256': canonical_sha({
            'scenes': [row['sample_id'] for row in scene_paths],
            'unique': {kind: sorted(unique[kind]) for kind in MODALITY_ORDER},
        }),
    }
    total_unique = sum(expected['expected_unique'].values())
    if total_unique > MAX_UNIQUE_FILES:
        raise RuntimeError('Unique file set exceeds the stat-only cap')
    return expected


def measure_files(layout, expected, *, max_seconds=MAX_STAT_SECONDS):
    """Visit each unique expected path with os.stat only (no content reads)."""
    started = time.monotonic()
    records = []
    stat_calls = 0
    errors = []
    for kind in MODALITY_ORDER:
        root = Path(layout.root(kind))
        for relpath in expected['unique_paths'][kind]:
            if time.monotonic() - started > max_seconds:
                raise TimeoutError('Stat-only measurement exceeded its wall clock cap')
            full = root / Path(relpath)
            stat_calls += 1
            try:
                info = os.stat(full)
            except FileNotFoundError:
                records.append(dict(modality=kind, relative_path=relpath,
                                    exists=False, bytes=None, mtime_utc=None))
            except OSError as exc:
                errors.append(dict(modality=kind, relative_path=relpath,
                                   error=type(exc).__name__))
                records.append(dict(modality=kind, relative_path=relpath,
                                    exists=False, bytes=None, mtime_utc=None,
                                    error=type(exc).__name__))
            else:
                records.append(dict(
                    modality=kind, relative_path=relpath, exists=True,
                    bytes=int(info.st_size),
                    mtime_utc=datetime.fromtimestamp(info.st_mtime, timezone.utc).isoformat(),
                    is_regular_file=bool(stat_module.S_ISREG(int(info.st_mode))),
                ))
    return records, stat_calls, errors, time.monotonic() - started


def summarize(records, expected):
    per_modality = {}
    total_bytes = 0
    missing_total = 0
    for kind in MODALITY_ORDER:
        rows = [row for row in records if row['modality'] == kind]
        present = [row for row in rows if row['exists']]
        missing = [row for row in rows if not row['exists']]
        byte_values = [row['bytes'] for row in rows if row.get('bytes') is not None]
        modality_bytes = sum(byte_values)
        total_bytes += modality_bytes
        missing_total += len(missing)
        per_modality[kind] = dict(
            expected_unique=len(expected['unique_paths'][kind]),
            observed_unique=len(rows),
            present_unique=len(present),
            missing_unique=len(missing),
            total_bytes=int(modality_bytes),
            min_bytes=int(min(byte_values)) if byte_values else None,
            max_bytes=int(max(byte_values)) if byte_values else None,
        )
    missing_paths = [dict(modality=row['modality'], relative_path=row['relative_path'])
                     for row in records if not row['exists']]
    return dict(
        per_modality=per_modality,
        total_expected_unique=sum(expected['expected_unique'].values()),
        total_present_unique=sum(row['exists'] for row in records),
        total_missing_unique=missing_total,
        total_bytes=int(total_bytes),
        missing_paths=missing_paths[:500],
    )


def run_measurement(authorization_path, authorization_sha256, output_root, *,
                    repo_root=None, layout=None, months=DEFAULT_MONTHS,
                    analysis_start=None, analysis_end=None,
                    max_seconds=MAX_STAT_SECONDS):
    """Execute one stat-only measurement run; output root must not exist."""
    if repo_root is None:
        repo_root = Path(__file__).resolve().parents[4]
    repo_root = Path(repo_root)
    authorization_path = Path(authorization_path)
    if not authorization_path.is_file():
        raise FileNotFoundError(str(authorization_path))
    if not isinstance(authorization_sha256, str) or not _SHA256.fullmatch(authorization_sha256):
        raise ValueError('Lowercase authorization SHA-256 required')
    if sha256_file(authorization_path) != authorization_sha256:
        raise PermissionError('authorization file digest mismatch')
    raw = json.loads(authorization_path.read_text(encoding='utf-8'))
    policy = validate_authorization(raw, repo_root)
    output_root = Path(output_root)
    if output_root.exists():
        raise FileExistsError('Output root already exists: ' + str(output_root))
    if layout is None:
        layout = PathLayout2025.default()
    expected = build_expected(layout, months=months,
                              analysis_start=analysis_start, analysis_end=analysis_end)
    measured_utc = _now()
    records, stat_calls, errors, elapsed = measure_files(layout, expected, max_seconds=max_seconds)
    summary = summarize(records, expected)
    summary['errors'] = errors[:100]
    inventory_sha = canonical_sha({
        'expected_unique': expected['expected_unique'],
        'total_bytes': summary['total_bytes'],
        'missing_unique': summary['total_missing_unique'],
        'records': [dict(modality=row['modality'], relative_path=row['relative_path'],
                         exists=row['exists'], bytes=row.get('bytes')) for row in records],
    })
    run = dict(
        version=INVENTORY_VERSION,
        task=INVENTORY_KIND,
        status=INVENTORY_STATUS,
        created_utc=measured_utc.isoformat(),
        protocol_sha256=policy['protocol_sha256'],
        authorization=dict(
            decision_id=policy['decision_id'],
            authorized_by=policy['authorized_by'],
            created_utc=policy['created_utc'],
            sha256=authorization_sha256,
        ),
        scope=dict(year=2025, months=list(months),
                   analysis_hours=list(ANALYSIS_HOURS),
                   allow_october=False,
                   expected_scenes=expected['expected_scenes'],
                   scene_plan_sha256=expected['canonical_sha256']),
        layout=dict(
            himawari_root=str(layout.himawari_root),
            imerg_root=str(layout.imerg_root),
            gfs_root=str(layout.gfs_root),
            gfs_thermo_root=str(layout.gfs_thermo_root),
            himawari_template=layout.himawari_template,
            imerg_template=layout.imerg_template,
            gfs_main_template=layout.gfs_main_template,
            gfs_thermo_template=layout.gfs_thermo_template,
        ),
        expected=dict(expected_scenes=expected['expected_scenes'],
                      expected_unique=expected['expected_unique'],
                      total_unique=sum(expected['expected_unique'].values())),
        observed=summary,
        files=[dict(modality=row['modality'], relative_path=row['relative_path'],
                    exists=row['exists'], bytes=row.get('bytes'),
                    mtime_utc=row.get('mtime_utc')) for row in records],
        guards=dict(
            stat_only=True,
            payload_content_reads=0,
            payload_content_hashes=0,
            payload_files_opened=0,
            checkpoint_stats=0,
            checkpoint_hashes=0,
            checkpoint_loads=0,
            model_builds=0,
            inference_scenes=0,
            metrics_computed=0,
            october_paths=0,
        ),
        runtime=dict(started_utc=None, completed_utc=None,
                     elapsed_seconds=float(elapsed), stat_calls=int(stat_calls)),
        integrity=dict(inventory_sha256=inventory_sha,
                       record_count=len(records)),
    )
    output_root.mkdir(parents=True, exist_ok=False)
    run_path = output_root / 'inventory_measurement_v1.json'
    summary_path = output_root / 'inventory_measurement_summary.json'
    status_path = output_root / 'final_status.json'
    run_path.write_text(json.dumps(run, indent=2, sort_keys=True, ensure_ascii=False) + '\n',
                        encoding='utf-8')
    summary_path.write_text(json.dumps(dict(
        version=INVENTORY_VERSION,
        status=INVENTORY_STATUS,
        created_utc=run['created_utc'],
        expected_scenes=run['expected']['expected_scenes'],
        expected_unique=run['expected']['expected_unique'],
        total_bytes=run['observed']['total_bytes'],
        total_missing_unique=run['observed']['total_missing_unique'],
        per_modality=run['observed']['per_modality'],
        inventory_sha256=run['integrity']['inventory_sha256'],
        file_sha256=sha256_file(run_path),
        stat_calls=run['runtime']['stat_calls'],
        elapsed_seconds=run['runtime']['elapsed_seconds'],
    ), indent=2, sort_keys=True, ensure_ascii=False) + '\n', encoding='utf-8')
    status = dict(
        version=INVENTORY_VERSION,
        status=INVENTORY_STATUS,
        INVENTORY_MEASUREMENT_2025_AUTHORIZED=True,
        INVENTORY_MEASUREMENT_2025_EXECUTED=True,
        PAYLOAD_CONTENT_READS=0,
        MODEL_INFERENCE_SCENES=0,
        FINAL_TEST_2025_EXECUTED=False,
        completed_utc=_now().isoformat(),
        run_dir=output_root.name,
        inventory_sha256=run['integrity']['inventory_sha256'],
    )
    status_path.write_text(json.dumps(status, indent=2, sort_keys=True, ensure_ascii=False) + '\n',
                           encoding='utf-8')
    return status


def plan_counts(layout=None, *, months=DEFAULT_MONTHS, analysis_start=None, analysis_end=None):
    """Theoretical expected counts; no 2025 I/O is performed."""
    expected = build_expected(layout, months=months,
                              analysis_start=analysis_start, analysis_end=analysis_end)
    return dict(
        task=INVENTORY_KIND,
        status='PLAN_ONLY_NO_PAYLOAD_ACCESS',
        expected_scenes=expected['expected_scenes'],
        expected_unique=expected['expected_unique'],
        total_unique=sum(expected['expected_unique'].values()),
    )
