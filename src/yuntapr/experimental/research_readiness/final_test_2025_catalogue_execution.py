"""2025 catalogue QC execution gate: hash-only payload QC then catalogue freeze.

This module is the only place in the research-readiness package that opens a 2025
payload file, and it may do so only under a researcher catalogue authorization
that carries the separate ``CATALOGUE_QC_PAYLOAD_AUTHORIZED`` grant.  Its actions
are bounded to:

* the exact files named by the frozen stat-only inventory measurement (no
  traversal, no glob, no directory listing of any payload root);
* read-only size verification and streaming SHA-256 hashing of each present file;
* a metadata-only IMERG day decode (product/version/run type, half-hour time grid
  provenance, per-half-hour valid Yunnan counts) through an injectable decoder;
* a catalogue/freeze build from the resulting inventory, with zero checkpoint,
  model, inference, metric or training work.

Any inconsistency (bad authorization, bad measurement digest, file-set drift,
size drift, decoder contract violation) is a STOP: the run writes
``failure.json`` with ``status: STOP_REQUIRED`` and re-raises.
"""

import hashlib
import json
import os
import re
import shutil
import tempfile
import time
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

from . import final_test_2025_catalogue as catalogue
from . import final_test_2025_inventory as inventory
from . import final_test_2025_manifest as manifest
from . import final_test_2025_planning as planning

VERSION = 'v1'
TASK = 'B4_B7_B8_2025_CATALOGUE_QC'
STATUS_COMPLETED = 'CATALOGUE_QC_COMPLETED'
STATUS_STOP = 'STOP_REQUIRED'
MEASUREMENT_TASK = 'B4_B7_B8_2025_INVENTORY_MEASUREMENT'
MEASUREMENT_VERSION = 'v1'
MEASUREMENT_STATUS = 'MEASURED_STAT_ONLY'
MEASUREMENT_FILENAME = 'inventory_measurement_v1.json'
ENTRIES_FILENAME = 'inventory_qc_entries.json'
SUMMARY_FILENAME = 'inventory_qc_summary.json'
LEDGER_FILENAME = 'runtime_ledger.jsonl'
FINAL_STATUS_FILENAME = 'final_status.json'
FAILURE_FILENAME = 'failure.json'
DEFAULT_CHUNK_BYTES = 1 << 20
IMERG_COUNT = 48

# netCDF4/HDF5 cannot open the non-ASCII 2025 IMERG payload paths on this host:
# the library's OS-level open fails with FileNotFoundError even though the file
# exists.  The decoder therefore stages a byte-identical copy under an ASCII-only
# staging root, decodes it and removes it immediately.  The staging copy is never
# retained and is not counted as a source read beyond the one authorized read.
ASCII_STAGING_ROOT = Path(os.environ.get(
    'YUNTAPR_ASCII_STAGING_ROOT',
    r'F:\pytorch\Research\stage0_himawari\cache\staging'))
STAGING_PREFIX = 'imerg_qc_'

# The real IMERG decode needs the frozen Yunnan target mask and the pinned SP04
# coordinate mapping.  Both are resolved through the frozen loss protocol, exactly
# as the B0 catalogue backend did; this code path runs only in the real QC run.
FROZEN_LOSS_PROTOCOL_RELPATH = 'config/training/phase_a_training_protocol_v1.yaml'
FROZEN_LOSS_PROTOCOL_SHA256 = 'dcacbe34050da7e777ad0cb72c53b5b51b48ce57eb9260b09fd283d96de12a4a'
FROZEN_MASK_FILE_SHA256 = '9d921def661fc3e58cd1ed783fcf87abbf493da6ae5e5fea79c28043f73495ef'

# The stat-only inventory measurement is frozen evidence: it was executed once
# under the protocol revision that existed at measurement time.  The catalogue-QC
# revision of the same protocol only adds the gate-2 (QC payload) authorization
# text; the stat-only contract, the scene calendar and the expected file set are
# unchanged.  A measurement binding one of the predecessor revisions listed below
# is therefore still accepted, and the expected file set itself is re-derived by
# validate_measurement before any payload is opened.  Revisions that change the
# contract must never be added here.
MEASUREMENT_PROTOCOL_REVISIONS = frozenset({
    '3b5608a2b406c927a7d99aba9aace6f782ce1e19478460cb794954c6dc662421',  # gate-0 inventory revision
})

# The implementation files a real catalogue-QC authorization must bind.  The
# execution gate re-hashes every one of them against the working tree before it
# opens any payload file, so a code/protocol drift turns into a STOP instead of a
# silently different QC result.
IMPLEMENTATION_FILES = (
    'config/evaluation/b4_b7_b8_b7zero_2025_final_test_protocol_v1.yaml',
    'src/yuntapr/experimental/research_readiness/final_test_2025_catalogue.py',
    'src/yuntapr/experimental/research_readiness/final_test_2025_catalogue_execution.py',
    'src/yuntapr/experimental/research_readiness/final_test_2025_inventory.py',
    'src/yuntapr/experimental/research_readiness/final_test_2025_manifest.py',
    'src/yuntapr/experimental/research_readiness/final_test_2025_planning.py',
    'tools/research_readiness/run_b4_b7_b8_2025_catalogue_qc.py',
)

_SHA = re.compile(r'[0-9a-f]{64}')
_IMERG_NAME = re.compile(r'^imerg_(\d{8})\.nc$')

_MEASUREMENT_KEYS = ('authorization', 'created_utc', 'expected', 'files', 'guards',
                     'integrity', 'layout', 'observed', 'protocol_sha256', 'runtime',
                     'scope', 'status', 'task', 'version')
_AUTHORIZATION_KEYS = ('authorized_by', 'created_utc', 'decision_id', 'sha256')
_EXPECTED_KEYS = ('expected_scenes', 'expected_unique', 'total_unique')
_FILE_KEYS = ('modality', 'relative_path', 'exists', 'bytes', 'mtime_utc')
_GUARD_KEYS = ('checkpoint_hashes', 'checkpoint_loads', 'checkpoint_stats',
               'inference_scenes', 'metrics_computed', 'model_builds', 'october_paths',
               'payload_content_hashes', 'payload_content_reads', 'payload_files_opened',
               'stat_only')
_INTEGRITY_KEYS = ('inventory_sha256', 'record_count')
_LAYOUT_KEYS = ('himawari_root', 'imerg_root', 'gfs_root', 'gfs_thermo_root',
                'himawari_template', 'imerg_template', 'gfs_main_template',
                'gfs_thermo_template')
_OBSERVED_KEYS = ('errors', 'missing_paths', 'per_modality', 'total_bytes',
                  'total_expected_unique', 'total_missing_unique', 'total_present_unique')
_RUNTIME_KEYS = ('completed_utc', 'elapsed_seconds', 'started_utc', 'stat_calls')
_SCOPE_KEYS = ('allow_october', 'analysis_hours', 'expected_scenes', 'months',
               'scene_plan_sha256', 'year')
_DECODER_KEYS = ('product', 'version', 'run_type', 'time_grid_provenance_pass',
                 'valid_yunnan_counts')
_ENTRY_KEYS = ('modality', 'relative_path', 'exists', 'bytes', 'bytes_read', 'sha256',
               'readable', 'product', 'version', 'run_type',
               'time_grid_provenance_pass', 'valid_yunnan_counts')

# The only guard state a stat-only inventory measurement may have declared.
_MEASUREMENT_GUARDS = {
    'checkpoint_hashes': 0, 'checkpoint_loads': 0, 'checkpoint_stats': 0,
    'inference_scenes': 0, 'metrics_computed': 0, 'model_builds': 0,
    'october_paths': 0, 'payload_content_hashes': 0, 'payload_content_reads': 0,
    'payload_files_opened': 0, 'stat_only': True,
}
# Guard values this QC phase must end with: payload bytes are hashed and IMERG
# metadata is decoded, but no checkpoint, model, inference or metric work happens.
_QC_GUARDS = {
    'checkpoint_loads': 0, 'checkpoint_stats': 0, 'checkpoint_hashes': 0,
    'model_builds': 0, 'inference_scenes': 0, 'metrics_computed': 0,
    'training_updates': 0, 'parameter_updates': 0, 'normalization_refits': 0,
    'threshold_tunings': 0, 'final_test_2025_executed': False,
}


def _lower_hex(value, label):
    if not isinstance(value, str) or len(value) != 64 or not _SHA.fullmatch(value):
        raise ValueError('Lowercase 64-hex value required: ' + label)
    return value


def _exact_key_set(value, keys, label):
    if not isinstance(value, dict) or set(value) != set(keys) or len(value) != len(tuple(keys)):
        raise ValueError('Exact ' + label + ' key set required')
    return True


def _utc(value):
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, str):
        parsed = datetime.fromisoformat(value)
    else:
        raise TypeError('UTC timestamp required')
    if parsed.tzinfo is None:
        raise ValueError('Timezone-aware UTC timestamp required')
    return parsed.astimezone(timezone.utc)


def _iso_utc(value=None):
    return (value or datetime.now(timezone.utc)).astimezone(timezone.utc).isoformat()


def _open_binary(path, mode):
    return Path(path).open(mode)


def sha256_file(path, *, chunk_bytes=DEFAULT_CHUNK_BYTES, opener=None):
    """Streaming read-only SHA-256; returns ``(digest, bytes_read)``."""
    chunk_bytes = _chunk_bytes(chunk_bytes)
    opener = opener or _open_binary
    digest = hashlib.sha256()
    total = 0
    with opener(path, 'rb') as stream:
        while True:
            block = stream.read(chunk_bytes)
            if not block:
                break
            digest.update(block)
            total += len(block)
    return digest.hexdigest(), total


def _chunk_bytes(value):
    if type(value) is not int or value <= 0:
        raise ValueError('Positive integer hash chunk size required')
    return value


def implementation_digest(files):
    """Canonical digest of a repository-relative implementation SHA map."""
    if not isinstance(files, dict) or not files:
        raise ValueError('Non-empty implementation file map required')
    ordered = {key: files[key] for key in sorted(files)}
    payload = json.dumps(ordered, sort_keys=True, separators=(',', ':')).encode('utf-8')
    return hashlib.sha256(payload).hexdigest()


def implementation_binding(repo_root):
    """Current working-tree SHA map of the catalogue-QC implementation files."""
    repo_root = Path(repo_root).resolve()
    files = {}
    for relative_path in IMPLEMENTATION_FILES:
        path = (repo_root / relative_path).resolve()
        try:
            path.relative_to(repo_root)
        except ValueError:
            raise PermissionError('Implementation file escapes the repository: '
                                  + relative_path) from None
        parent = path.parent
        if not parent.is_dir() or not path.is_file():
            raise PermissionError('Missing implementation file: ' + relative_path)
        files[relative_path] = sha256_file(path)[0]
    return {'sha256': implementation_digest(files), 'files': files}


def verify_implementation(repo_root, implementation):
    """Re-hash every bound implementation file before any payload is opened."""
    expected = implementation.get('files')
    actual = implementation_binding(repo_root)['files']
    if dict(expected) != actual:
        raise PermissionError('Implementation binding differs from the working tree')
    if implementation.get('sha256') != implementation_digest(actual):
        raise PermissionError('Implementation digest differs from the working tree')
    return actual


def layout_document(layout):
    """The layout block the frozen stat-only measurement recorded."""
    if not isinstance(layout, planning.PathLayout2025):
        raise TypeError('PathLayout2025 required')
    return {
        'himawari_root': str(layout.himawari_root),
        'imerg_root': str(layout.imerg_root),
        'gfs_root': str(layout.gfs_root),
        'gfs_thermo_root': str(layout.gfs_thermo_root),
        'himawari_template': layout.himawari_template,
        'imerg_template': layout.imerg_template,
        'gfs_main_template': layout.gfs_main_template,
        'gfs_thermo_template': layout.gfs_thermo_template,
    }


def load_measurement(path, expected_sha256=None):
    """Load the inventory measurement JSON; digest check happens before JSON."""
    path = Path(path)
    payload = path.read_bytes()
    digest = hashlib.sha256(payload).hexdigest()
    if expected_sha256 is not None:
        _lower_hex(expected_sha256, 'inventory measurement sha256')
        if digest != expected_sha256:
            raise PermissionError('Inventory measurement SHA mismatch')
    document = json.loads(payload.decode('utf-8'))
    return document, digest


def _input_path(repo_root, value):
    """Caller-supplied input path; repo-relative paths anchor at the repository."""
    path = Path(value)
    return path if path.is_absolute() else Path(repo_root) / path


def validate_measurement(document, *, layout=None):
    """Re-derive the frozen scene plan and verify the stat-only measurement."""
    _exact_key_set(document, _MEASUREMENT_KEYS, 'inventory measurement')
    if (document['version'] != MEASUREMENT_VERSION
            or document['task'] != MEASUREMENT_TASK
            or document['status'] != MEASUREMENT_STATUS):
        raise ValueError('Frozen stat-only 2025 inventory measurement required')
    _utc(document['created_utc'])
    _lower_hex(document['protocol_sha256'], 'measurement protocol sha256')

    authorization = document['authorization']
    _exact_key_set(authorization, _AUTHORIZATION_KEYS, 'measurement authorization')
    if authorization['authorized_by'] != 'RESEARCHER':
        raise PermissionError('Researcher-authored inventory measurement required')
    if not isinstance(authorization['decision_id'], str) or not authorization['decision_id']:
        raise ValueError('Measurement decision_id required')
    _lower_hex(authorization['sha256'], 'measurement authorization sha256')
    _utc(authorization['created_utc'])

    guards = document['guards']
    _exact_key_set(guards, _GUARD_KEYS, 'measurement guards')
    if guards != _MEASUREMENT_GUARDS:
        raise ValueError('Inventory measurement guards are not stat-only')

    scope = document['scope']
    _exact_key_set(scope, _SCOPE_KEYS, 'measurement scope')
    if scope['year'] != planning.YEAR:
        raise ValueError('Measurement year differs from the frozen 2025 scope')
    if scope['allow_october'] is not False:
        raise PermissionError('October is hard-rejected before source I/O')
    if list(scope['analysis_hours']) != list(planning.ANALYSIS_HOURS):
        raise ValueError('Measurement analysis hours differ from the frozen cadence')
    months = tuple(scope['months'])
    if not months or months != tuple(sorted(set(months))):
        raise ValueError('Strictly ordered unique measurement months required')
    if any(month not in inventory.MARCH_SEPTEMBER_MONTHS for month in months):
        raise PermissionError('Inventory measurement is March..September only')
    if type(scope['expected_scenes']) is not int or scope['expected_scenes'] <= 0:
        raise ValueError('Positive expected scene count required')
    _lower_hex(scope['scene_plan_sha256'], 'measurement scene plan sha256')

    if layout is None:
        layout = planning.PathLayout2025.default()
    if document['layout'] != layout_document(layout):
        raise ValueError('Measurement layout differs from the frozen source layout')
    expected = inventory.build_expected(layout, months=months)
    if scope['expected_scenes'] != expected['expected_scenes']:
        raise ValueError('Measurement scene count differs from the frozen scene plan')
    if scope['scene_plan_sha256'] != expected['canonical_sha256']:
        raise ValueError('Measurement scene plan digest mismatch')

    expected_block = document['expected']
    _exact_key_set(expected_block, _EXPECTED_KEYS, 'measurement expected block')
    if expected_block['expected_scenes'] != expected['expected_scenes']:
        raise ValueError('Measurement expected scene count mismatch')
    _exact_key_set(expected_block['expected_unique'], inventory.MODALITY_ORDER,
                   'measurement expected modality counts')
    if dict(expected_block['expected_unique']) != dict(expected['expected_unique']):
        raise ValueError('Measurement expected modality counts mismatch')
    total_unique = sum(expected['expected_unique'].values())
    if expected_block['total_unique'] != total_unique:
        raise ValueError('Measurement expected total unique count mismatch')

    files = document['files']
    if not isinstance(files, list) or len(files) != total_unique:
        raise ValueError('Measurement file count differs from the frozen scene plan')
    wanted = [(kind, relative_path) for kind in inventory.MODALITY_ORDER
              for relative_path in expected['unique_paths'][kind]]
    present = []
    missing = []
    for record, wanted_key in zip(files, wanted):
        _exact_key_set(record, _FILE_KEYS, 'inventory file record')
        if (record['modality'], record['relative_path']) != wanted_key:
            raise ValueError('Measurement file set/order differs from the frozen scene plan')
        inventory._assert_frozen_scope(record['relative_path'])
        if record['exists'] is True:
            if type(record['bytes']) is not int or record['bytes'] <= 0:
                raise ValueError('Positive measured byte size required for a present file')
            if not isinstance(record['mtime_utc'], str):
                raise ValueError('Measured modification time required for a present file')
            _utc(record['mtime_utc'])
            present.append(record)
        elif record['exists'] is False:
            if record['bytes'] is not None or record['mtime_utc'] is not None:
                raise ValueError('Missing inventory entries must not carry size or mtime')
            missing.append(record)
        else:
            raise ValueError('Boolean inventory exists flag required')
    if len(present) + len(missing) != total_unique:
        raise ValueError('Measurement file set is incomplete')

    observed = document['observed']
    _exact_key_set(observed, _OBSERVED_KEYS, 'measurement observed block')
    if observed['errors'] != []:
        raise ValueError('Measurement recorded stat errors')
    recomputed = inventory.summarize(files, expected)
    for key in ('per_modality', 'total_expected_unique', 'total_present_unique',
                'total_missing_unique', 'total_bytes'):
        if observed[key] != recomputed[key]:
            raise ValueError('Measurement observed block mismatch: ' + key)
    if observed['missing_paths'] != recomputed['missing_paths']:
        raise ValueError('Measurement missing-path list mismatch')

    integrity = document['integrity']
    _exact_key_set(integrity, _INTEGRITY_KEYS, 'measurement integrity block')
    if integrity['record_count'] != len(files):
        raise ValueError('Measurement record count mismatch')
    digest = inventory.canonical_sha({
        'expected_unique': expected['expected_unique'],
        'total_bytes': recomputed['total_bytes'],
        'missing_unique': recomputed['total_missing_unique'],
        'records': [dict(modality=record['modality'],
                         relative_path=record['relative_path'],
                         exists=record['exists'], bytes=record['bytes'])
                    for record in files],
    })
    if digest != integrity['inventory_sha256']:
        raise ValueError('Measurement inventory digest mismatch')

    runtime = document['runtime']
    _exact_key_set(runtime, _RUNTIME_KEYS, 'measurement runtime block')
    if runtime['stat_calls'] != len(files):
        raise ValueError('Measurement stat-call count mismatch')
    if not isinstance(runtime['elapsed_seconds'], (int, float)) or runtime['elapsed_seconds'] < 0:
        raise ValueError('Non-negative measurement elapsed time required')

    return {
        'layout': layout,
        'expected': expected,
        'files': files,
        'present': present,
        'missing': missing,
        'scene_count': expected['expected_scenes'],
        'total_bytes': recomputed['total_bytes'],
        'per_modality': recomputed['per_modality'],
        'missing_paths': recomputed['missing_paths'],
        'inventory_sha256': integrity['inventory_sha256'],
    }


def measurement_plan(document):
    """Plan-only view of a frozen measurement: counts/bytes, no payload I/O.

    This deliberately checks only document self-consistency (schema, frozen status,
    count/byte arithmetic).  The run phase re-derives the full scene plan and
    verifies the authoritative digest via :func:`validate_measurement`.
    """
    _exact_key_set(document, _MEASUREMENT_KEYS, 'inventory measurement')
    if (document['version'] != MEASUREMENT_VERSION
            or document['task'] != MEASUREMENT_TASK
            or document['status'] != MEASUREMENT_STATUS):
        raise ValueError('Frozen stat-only 2025 inventory measurement required')
    expected = document['expected']
    observed = document['observed']
    integrity = document['integrity']
    _exact_key_set(expected, _EXPECTED_KEYS, 'measurement expected block')
    _exact_key_set(observed, _OBSERVED_KEYS, 'measurement observed block')
    _exact_key_set(integrity, _INTEGRITY_KEYS, 'measurement integrity block')
    _exact_key_set(expected['expected_unique'], inventory.MODALITY_ORDER,
                   'measurement expected modality counts')
    counts = dict(expected['expected_unique'])
    total = expected['total_unique']
    if sum(counts.values()) != total:
        raise ValueError('Measurement expected modality counts do not sum to the total')
    files = document['files']
    if not isinstance(files, list) or len(files) != total:
        raise ValueError('Measurement file list length mismatch')
    if integrity['record_count'] != total:
        raise ValueError('Measurement record count mismatch')
    present = [record for record in files if record['exists'] is True]
    missing = [record for record in files if record['exists'] is False]
    if len(present) + len(missing) != total:
        raise ValueError('Measurement exists flags are incomplete')
    if observed['total_present_unique'] != len(present):
        raise ValueError('Measurement observed present count mismatch')
    if observed['total_missing_unique'] != len(missing):
        raise ValueError('Measurement observed missing count mismatch')
    present_bytes = sum(record['bytes'] for record in present)
    if observed['total_bytes'] != present_bytes:
        raise ValueError('Measurement observed byte total mismatch')
    return {
        'task': TASK,
        'status': 'PLAN_ONLY_NO_PAYLOAD_ACCESS',
        'validation': 'DOCUMENT_CONSISTENCY_ONLY_FULL_VALIDATION_AT_RUN',
        'measurement_status': document['status'],
        'measurement_created_utc': document['created_utc'],
        'protocol_sha256': document['protocol_sha256'],
        'expected_scenes': expected['expected_scenes'],
        'expected_unique': counts,
        'total_unique': total,
        'present_unique': len(present),
        'missing_unique': len(missing),
        'present_bytes': present_bytes,
        'payload_files_to_hash': len(present),
        'payload_bytes_to_hash': present_bytes,
        'imerg_days_to_decode': counts['imerg'],
        'guards': document['guards'],
    }


def payload_path(layout, modality, relative_path):
    """Resolve one measured relative path below its frozen root; no traversal."""
    if modality not in catalogue.INVENTORY_MODALITIES:
        raise ValueError('Unknown inventory modality: ' + str(modality))
    inventory._assert_frozen_scope(relative_path)
    root = Path(layout.root(modality)).resolve()
    candidate = (root / Path(relative_path)).resolve()
    try:
        candidate.relative_to(root)
    except ValueError:
        raise PermissionError('Payload path escapes its frozen source root') from None
    return candidate


def imerg_day_start(relative_path):
    """The UTC day start encoded by ``YYYY/imerg_YYYYMMDD.nc``."""
    name = Path(relative_path).name
    match = _IMERG_NAME.fullmatch(name)
    if not match:
        raise ValueError('IMERG day path must be YYYY/imerg_YYYYMMDD.nc: ' + relative_path)
    return datetime.strptime(match.group(1), '%Y%m%d').replace(tzinfo=timezone.utc)


def _decoded_day(value):
    _exact_key_set(value, _DECODER_KEYS, 'IMERG day metadata')
    for key in ('product', 'version', 'run_type'):
        if not isinstance(value[key], str):
            raise ValueError('String IMERG metadata required: ' + key)
    if not isinstance(value['time_grid_provenance_pass'], bool):
        raise ValueError('Boolean IMERG time-grid provenance required')
    counts = tuple(value['valid_yunnan_counts'])
    if len(counts) != IMERG_COUNT:
        raise ValueError('48 half-hour Yunnan overlap counts required')
    if any(type(count) is not int or count < 0 for count in counts):
        raise ValueError('Non-negative half-hour Yunnan overlap counts required')
    return {
        'product': value['product'],
        'version': value['version'],
        'run_type': value['run_type'],
        'time_grid_provenance_pass': value['time_grid_provenance_pass'],
        'valid_yunnan_counts': counts,
    }


class FrozenIMERGDecoder:
    """Real metadata-only IMERG V07 Final decoder (netCDF4 imported lazily).

    The decode reproduces the frozen B0 validity semantics (``imerg_validity_only``)
    and reads only the 48x100x100 Yunnan target crop.  Any per-file decode error is
    reported as empty metadata / zero overlap, exactly like the B0 catalogue QC,
    so it becomes a candidate rejection rather than an infrastructure STOP.
    """

    def __init__(self, staging_root=None):
        self._mapping = None
        self._yunnan = None
        self._staging_root = (Path(staging_root) if staging_root is not None
                              else ASCII_STAGING_ROOT)

    @contextmanager
    def _staged(self, path):
        """Byte-identical ASCII-path copy for netCDF4, removed immediately after."""
        self._staging_root.mkdir(parents=True, exist_ok=True)
        workdir = Path(tempfile.mkdtemp(prefix=STAGING_PREFIX,
                                        dir=str(self._staging_root)))
        target = workdir / 'imerg_day.nc'
        try:
            shutil.copyfile(path, target)
            yield target
        finally:
            shutil.rmtree(workdir, ignore_errors=True)

    def _context(self):
        if self._mapping is None:
            import yaml

            from yuntapr.data.masks import read_frozen_yunnan_mask
            from yuntapr.spatial.sp04_mapping import load_sp04

            repo_root = Path(__file__).resolve().parents[4]
            loss_path = repo_root / FROZEN_LOSS_PROTOCOL_RELPATH
            if sha256_file(loss_path)[0] != FROZEN_LOSS_PROTOCOL_SHA256:
                raise ValueError('STOP: frozen loss protocol SHA mismatch')
            loss_protocol = yaml.safe_load(loss_path.read_text(encoding='utf-8'))
            mask_identity = loss_protocol['identity']['yunnan_mask']
            mask_path = Path(mask_identity['path'])
            if mask_identity['sha256'] != FROZEN_MASK_FILE_SHA256:
                raise ValueError('STOP: frozen Yunnan mask identity mismatch')
            if sha256_file(mask_path)[0] != FROZEN_MASK_FILE_SHA256:
                raise ValueError('STOP: protocol-bound frozen Yunnan mask SHA mismatch')
            self._mapping = load_sp04()
            self._yunnan = read_frozen_yunnan_mask(mask_path, self._mapping)
        return self._mapping, self._yunnan

    def __call__(self, path, day_start):
        import netCDF4
        import numpy as np

        from yuntapr.evaluation import catalogue_backend_b0 as backend

        mapping, yunnan = self._context()
        product = version = run_type = ''
        counts = (0,) * IMERG_COUNT
        try:
            with self._staged(path) as staged_path:
                with netCDF4.Dataset(str(staged_path), 'r') as dataset:
                    dataset.set_auto_maskandscale(False)
                    global_attrs = {name: dataset.getncattr(name)
                                    for name in ('source', 'title') if name in dataset.ncattrs()}
                    if global_attrs.get('source') == catalogue.IMERG_PRODUCT:
                        product, version = catalogue.IMERG_PRODUCT, catalogue.IMERG_VERSION
                    if 'IMERG Final Run V07' in str(global_attrs.get('title', '')):
                        run_type = catalogue.IMERG_RUN_TYPE
                    variable = dataset['precipitation']
                    if (tuple(variable.dimensions) != ('time', 'lat', 'lon')
                            or tuple(variable.shape) != (IMERG_COUNT, 130, 140)
                            or variable.units != 'mm hr-1'):
                        raise ValueError('IMERG converted dimension/shape/units mismatch')
                    mapping.assert_axes(mapping.axes['native_lat'], mapping.axes['native_lon'],
                                        np.asarray(dataset['lat'][10:110]),
                                        np.asarray(dataset['lon'][20:120]))
                    times = backend._cf_times(dataset['time'])
                    expected = tuple(_utc(day_start) + timedelta(minutes=30 * index)
                                     for index in range(IMERG_COUNT))
                    if times != expected:
                        raise ValueError('IMERG complete half-hour time grid mismatch')
                    yunnan = np.asarray(yunnan)
                    if yunnan.dtype != np.dtype(bool) or yunnan.shape != (100, 100):
                        raise ValueError('Frozen Yunnan target mask must be 100x100 bool')
                    raw = np.asarray(variable[:, 10:110, 20:120])
                    valid = backend.imerg_validity_only(
                        raw, backend._attrs(variable, backend._IMERG_ATTRS))
                    counts = tuple(int(value) for value in
                                   np.count_nonzero(valid & yunnan[None], axis=(1, 2)))
        except (OSError, ValueError, KeyError, IndexError, AttributeError):
            return {'product': product, 'version': version, 'run_type': run_type,
                    'time_grid_provenance_pass': False,
                    'valid_yunnan_counts': (0,) * IMERG_COUNT}
        return {'product': product, 'version': version, 'run_type': run_type,
                'time_grid_provenance_pass': True, 'valid_yunnan_counts': counts}


@dataclass(frozen=True)
class QCEntry:
    modality: str
    relative_path: str
    exists: bool
    bytes: int
    bytes_read: int
    sha256: str
    readable: bool
    product: str = ''
    version: str = ''
    run_type: str = ''
    time_grid_provenance_pass: bool = False
    valid_yunnan_counts: tuple = ()

    def as_dict(self):
        return {
            'modality': self.modality,
            'relative_path': self.relative_path,
            'exists': self.exists,
            'bytes': self.bytes,
            'bytes_read': self.bytes_read,
            'sha256': self.sha256,
            'readable': self.readable,
            'product': self.product,
            'version': self.version,
            'run_type': self.run_type,
            'time_grid_provenance_pass': self.time_grid_provenance_pass,
            'valid_yunnan_counts': list(self.valid_yunnan_counts),
        }


def _inventory_entries(measurement, entries):
    """Present-file inventory entries for the catalogue build."""
    by_key = {(entry.modality, entry.relative_path): entry for entry in entries if entry.exists}
    built = []
    for kind in catalogue.INVENTORY_MODALITIES:
        for record in measurement['files']:
            if record['modality'] != kind or not record['exists']:
                continue
            entry = by_key[(kind, record['relative_path'])]
            built.append(catalogue.InventoryEntry(
                modality=kind, relative_path=entry.relative_path, bytes=entry.bytes_read,
                sha256=entry.sha256, readable=True, product=entry.product,
                version=entry.version, run_type=entry.run_type,
                time_grid_provenance_pass=entry.time_grid_provenance_pass,
                valid_yunnan_count=entry.valid_yunnan_counts[0] if entry.valid_yunnan_counts else 0,
                valid_yunnan_counts=entry.valid_yunnan_counts))
    return built


def _verify_population_scenes(population, expected):
    """The population must be exactly the measurement's frozen scene plan."""
    records = population.document['scene_records']
    scenes = expected['scene_paths']
    if len(records) != len(scenes):
        raise ValueError('Population scene count differs from the frozen scene plan')
    for record, scene in zip(records, scenes):
        if record['sample_id'] != scene['sample_id'] or record['month'] != scene['month']:
            raise ValueError('Population scene identity differs from the frozen scene plan')
        slots = [record[f'slot_{slot:02d}_relative_path'] for slot in range(6)]
        if slots != scene['satellites']:
            raise ValueError('Population satellite frames differ from the frozen scene plan')
        if record['gfs_main_relative_path'] != scene['gfs_main']:
            raise ValueError('Population GFS main path differs from the frozen scene plan')
        if record['gfs_thermo_relative_path'] != scene['gfs_thermo']:
            raise ValueError('Population GFS thermo path differs from the frozen scene plan')
        if record['imerg_day_relative_path'] != scene['imerg']:
            raise ValueError('Population IMERG day differs from the frozen scene plan')


def _write_failure(output, error, *, started_utc, hashes, decode_opens):
    output = Path(output)
    try:
        output.mkdir(parents=True, exist_ok=True)
        path = output / FAILURE_FILENAME
        if path.exists():
            return
        payload = {
            'version': VERSION,
            'task': TASK,
            'status': STATUS_STOP,
            'error_type': type(error).__name__,
            'error': str(error),
            'automatic_retry': False,
            'payload_files_hashed': int(hashes),
            'payload_decode_opens': int(decode_opens),
            'started_utc': started_utc,
            'completed_utc': _iso_utc(),
        }
        path.write_text(json.dumps(payload, indent=2, sort_keys=True,
                                   ensure_ascii=False) + '\n', encoding='utf-8')
    except OSError:
        pass


def run_catalogue_qc(authorization_path, authorization_sha256, measurement_path,
                     measurement_sha256, output_dir, *, repo_root=None, layout=None,
                     chunk_bytes=DEFAULT_CHUNK_BYTES, decoder=None, created_utc=None,
                     opener=None):
    """One authorized hash-only 2025 catalogue QC run; output dir must not exist."""
    if repo_root is None:
        repo_root = Path(__file__).resolve().parents[4]
    repo_root = Path(repo_root)
    chunk_bytes = _chunk_bytes(chunk_bytes)
    started_utc = _iso_utc(created_utc)
    started = time.monotonic()
    payload_hashes = 0
    decode_opens = 0
    output = catalogue.safe_artifact_path(output_dir)
    if output.exists():
        raise FileExistsError('Append-only catalogue QC output directory already exists: '
                              + str(output))
    try:
        authorization = catalogue.CatalogueAuthorization2025.load(
            _input_path(repo_root, authorization_path),
            expected_sha256=authorization_sha256)
        authorization.require_catalogue()
        authorization.require_qc_payload()
        verify_implementation(repo_root, authorization.implementation)
        protocol_file = (repo_root / authorization.protocol['path']).resolve()
        if sha256_file(protocol_file)[0] != authorization.protocol['sha256']:
            raise PermissionError('Protocol binding differs from the working tree')

        measurement_path = catalogue.safe_artifact_path(
            _input_path(repo_root, measurement_path))
        document, measurement_digest = load_measurement(measurement_path, measurement_sha256)
        binding = authorization.inventory_measurement
        declared = Path(binding['path'])
        if not declared.is_absolute():
            declared = repo_root / declared
        if declared.resolve() != measurement_path.resolve():
            raise PermissionError('Inventory measurement path differs from the authorization binding')
        if binding['sha256'] != measurement_digest:
            raise PermissionError('Inventory measurement SHA differs from the authorization binding')
        if _utc(binding['created_utc']) != _utc(document['created_utc']):
            raise PermissionError('Inventory measurement creation time differs from the authorization')
        measurement_revision = document['protocol_sha256']
        if (measurement_revision != authorization.protocol['sha256']
                and measurement_revision not in MEASUREMENT_PROTOCOL_REVISIONS):
            raise PermissionError('Measurement protocol revision is not recognized by this QC gate')
        if authorization.fixture:
            raise PermissionError('Engineering fixture authorization cannot run a real QC pass')

        measurement = validate_measurement(document, layout=layout)
        layout = measurement['layout']
        expected = measurement['expected']
        scenes = [scene.as_dict() for scene in planning.enumerate_scenes(
            layout, months=tuple(document['scope']['months']), allow_october=False)]
        population = manifest.build_population(
            scenes, authorization.identity, expected_count=measurement['scene_count'])
        _verify_population_scenes(population, expected)

        decoder = decoder or FrozenIMERGDecoder()
        entries = []
        ledger = []
        imerg_entries = {}
        for record in measurement['files']:
            modality = record['modality']
            relative_path = record['relative_path']
            path = payload_path(layout, modality, relative_path)
            if not record['exists']:
                try:
                    path.stat()
                except FileNotFoundError:
                    pass
                except OSError as error:
                    raise RuntimeError('Missing payload probe failed: '
                                       + relative_path) from error
                else:
                    raise RuntimeError('Measured-missing payload is present now: '
                                       + relative_path)
                entries.append(QCEntry(modality=modality, relative_path=relative_path,
                                       exists=False, bytes=0, bytes_read=0,
                                       sha256='', readable=False))
                ledger.append({'sequence': len(ledger), 'event': 'MISSING_VERIFIED',
                               'modality': modality, 'relative_path': relative_path})
                continue
            info = path.stat()
            if not info.st_mode & 0o170000 == 0o100000:
                raise RuntimeError('Measured payload is not a regular file: ' + relative_path)
            if info.st_size != record['bytes']:
                raise RuntimeError('Measured byte size drift: ' + relative_path)
            hashing = time.monotonic()
            digest, bytes_read = sha256_file(path, chunk_bytes=chunk_bytes, opener=opener)
            payload_hashes += 1
            if bytes_read != record['bytes']:
                raise RuntimeError('Payload read size drift: ' + relative_path)
            if modality == 'imerg':
                day_start = imerg_day_start(relative_path)
                decode_started = time.monotonic()
                decode_opens += 1
                decoded = _decoded_day(decoder(path, day_start))
                imerg_entries[relative_path] = decoded
                ledger.append({'sequence': len(ledger), 'event': 'IMERG_DECODE',
                               'modality': modality, 'relative_path': relative_path,
                               'day_start_utc': day_start.isoformat(),
                               'valid_yunnan_total': int(sum(decoded['valid_yunnan_counts'])),
                               'seconds': round(time.monotonic() - decode_started, 6)})
                entry = QCEntry(modality=modality, relative_path=relative_path,
                                exists=True, bytes=record['bytes'], bytes_read=bytes_read,
                                sha256=digest, readable=True,
                                product=decoded['product'], version=decoded['version'],
                                run_type=decoded['run_type'],
                                time_grid_provenance_pass=decoded['time_grid_provenance_pass'],
                                valid_yunnan_counts=decoded['valid_yunnan_counts'])
            else:
                entry = QCEntry(modality=modality, relative_path=relative_path,
                                exists=True, bytes=record['bytes'], bytes_read=bytes_read,
                                sha256=digest, readable=True)
            entries.append(entry)
            ledger.append({'sequence': len(ledger), 'event': 'PAYLOAD_HASH',
                           'modality': modality, 'relative_path': relative_path,
                           'bytes': record['bytes'], 'sha256': digest,
                           'seconds': round(time.monotonic() - hashing, 6)})

        undecodable = sum(1 for decoded in imerg_entries.values()
                          if decoded['product'] == '' and decoded['version'] == '')
        if imerg_entries and undecodable == len(imerg_entries):
            raise ValueError('STOP: no IMERG day file could be decoded (decoder/encoding failure)')

        index = catalogue.InventoryIndex(_inventory_entries(measurement, entries))
        rows = catalogue.build_catalogue(population, index)
        summary = catalogue.eligibility_summary(rows)
        bundle = catalogue.build_catalogue_artefacts(
            authorization, population, index, output, fixture=False,
            created_utc=created_utc)
        hashed_bytes = sum(entry.bytes_read for entry in entries if entry.exists)
        imerg_days = len(imerg_entries)
        elapsed = time.monotonic() - started
        completed_utc = _iso_utc()
        entries_document = {
            'version': VERSION, 'task': TASK, 'status': STATUS_COMPLETED,
            'identity': authorization.identity,
            'inventory_measurement_sha256': measurement_digest,
            'entry_count': len(entries), 'present_count': len(measurement['present']),
            'missing_count': len(measurement['missing']),
            'entries': [entry.as_dict() for entry in entries],
        }
        summary_document = {
            'version': VERSION, 'task': TASK, 'status': STATUS_COMPLETED,
            'expected_scenes': measurement['scene_count'],
            'scene_count': len(rows),
            'expected_unique': expected['expected_unique'],
            'present_unique': len(measurement['present']),
            'missing_unique': len(measurement['missing']),
            'present_bytes': measurement['total_bytes'],
            'hashed_bytes': hashed_bytes,
            'imerg_days': imerg_days,
            'imerg_half_hours_checked': imerg_days * IMERG_COUNT,
            'per_modality': measurement['per_modality'],
            'eligible_count': summary['eligible'],
            'rejected_count': summary['rejected'],
            'rejection_counts': summary['rejection_counts'],
            'missing_paths': measurement['missing_paths'],
            'guards': dict(_QC_GUARDS),
            'runtime': {'started_utc': started_utc, 'completed_utc': completed_utc,
                        'elapsed_seconds': round(elapsed, 6),
                        'hash_bytes_per_second': round(hashed_bytes / elapsed, 3) if elapsed > 0 else None},
        }
        (output / ENTRIES_FILENAME).write_text(
            json.dumps(entries_document, indent=2, sort_keys=True, ensure_ascii=False) + '\n',
            encoding='utf-8')
        (output / SUMMARY_FILENAME).write_text(
            json.dumps(summary_document, indent=2, sort_keys=True, ensure_ascii=False) + '\n',
            encoding='utf-8')
        (output / LEDGER_FILENAME).write_text(
            ''.join(json.dumps(event, sort_keys=True, ensure_ascii=False) + '\n'
                    for event in ledger), encoding='utf-8')
        status = {
            'version': VERSION, 'task': TASK, 'status': STATUS_COMPLETED,
            'payload_access': 'HASH_AND_IMERG_METADATA_ONLY',
            'authorization_sha256': authorization_sha256,
            'inventory_measurement_sha256': measurement_digest,
            'inventory_sha256': measurement['inventory_sha256'],
            'protocol_sha256': document['protocol_sha256'],
            'implementation_sha256': authorization.implementation['sha256'],
            'checkpoint_catalog_sha256': catalogue.CHECKPOINT_CATALOG_SHA256,
            'identity': authorization.identity,
            'catalogue_sha256': bundle['catalogue_sha256'],
            'population_sha256': bundle['population_sha256'],
            'freeze_sha256': bundle['freeze_sha256'],
            'scene_count': len(rows),
            'eligible_count': summary['eligible'],
            'rejected_count': summary['rejected'],
            'rejection_counts': summary['rejection_counts'],
            'payload_files_hashed': payload_hashes,
            'payload_bytes_hashed': hashed_bytes,
            'imerg_days_decoded': imerg_days,
            'imerg_half_hours_checked': imerg_days * IMERG_COUNT,
            'guards': dict(_QC_GUARDS),
            'runtime': summary_document['runtime'],
            'final_test_2025_executed': False,
            'completed_utc': completed_utc,
        }
        (output / FINAL_STATUS_FILENAME).write_text(
            json.dumps(status, indent=2, sort_keys=True, ensure_ascii=False) + '\n',
            encoding='utf-8')
        return status
    except Exception as error:  # noqa: BLE001 - one-shot failure surface
        _write_failure(output, error, started_utc=started_utc,
                       hashes=payload_hashes, decode_opens=decode_opens)
        raise
