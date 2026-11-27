"""2025 final-test catalogue gate and authority objects (metadata only).

Design mirrors the frozen B0 ``catalogue_gate_b0.FinalAuthority`` pattern:

* a catalogue is built **only** from a caller-supplied inventory (relative path,
  byte size, SHA-256).  This module never lists, stats or opens a payload path.
* a catalogue-only authorization JSON has an exact key set and binds the draft
  protocol SHA, the implementation SHA, the 12-checkpoint catalogue digest and
  the frozen source roots.  A fixture authorization exists for synthetic tests.
* the final-test authorization is a *separate* object and additionally binds the
  catalogue CSV, the frozen population CSV and the catalogue freeze record; its
  ``created_utc`` may not precede the freeze completion time.
* the catalogue authorization also carries a separate
  ``CATALOGUE_QC_PAYLOAD_AUTHORIZED`` flag.  When set it permits *read-only
  hash/metadata QC* of exactly the files named by the frozen inventory
  measurement (see ``final_test_2025_catalogue_execution``), and nothing else.
* ``authorize_payload`` always raises.  Opening 2025 payloads for inference is a
  distinct private payload-phase grant that this module cannot issue.
"""

from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
import csv
import hashlib
import io
import json
from pathlib import Path
import re

from . import final_test_2025_manifest as manifest
from . import final_test_2025_planning as planning

VERSION = 'v1'
CATALOGUE_SCOPE = 'B4_B7_B8_2025_FINAL_TEST_CATALOGUE_ONLY'
FINAL_SCOPE = 'B4_B7_B8_2025_MAR_SEP_FINAL_TEST_ONLY'
FIXTURE_SCOPE = 'ENGINEERING_FIXTURE_2025_CATALOGUE_ONLY'
PROTOCOL_FILENAME = 'b4_b7_b8_b7zero_2025_final_test_protocol_v1.yaml'
CATALOGUE_FILENAME = 'b4_b7_b8_2025_candidate_catalogue_v1.csv'
POPULATION_FILENAME = 'b4_b7_b8_2025_population_manifest_v1.json'
FREEZE_FILENAME = 'b4_b7_b8_2025_catalogue_freeze_record_v1.json'
IMERG_PRODUCT = 'GPM_3IMERGHH_07'
IMERG_VERSION = 'V07'
IMERG_RUN_TYPE = 'Final'
SUPERVISION_REGION_PIXELS = 3430

MODELS = ('B4', 'B7', 'B8', 'B7_ZERO_DOTE')
SEEDS = (2029, 2030, 2031)
CHECKPOINTS = {
    ('B4', 2029): {'sha256': '7c74eb80ab7d754e3262781d85ac370b2319c3bf27d37ac362860c104acfb34d',
                   'bytes': 52913659, 'execution_commit': '7fa609e89bdb8b744bb0e7eebc9e7b5c3a703e35',
                   'identity_source': 'docs/research_readiness/20261031_extreme_precipitation_audit/EXTREME_PRECIPITATION_AUDIT.csv'},
    ('B4', 2030): {'sha256': '7fb2c3714586634dfcee763d7eccdf4d746972044d7c0b9ac8827bca35db414c',
                   'bytes': 52914619, 'execution_commit': '943da957a3af846746c21b52d05a148bcb135064',
                   'identity_source': 'docs/research_readiness/20261031_extreme_precipitation_audit/EXTREME_PRECIPITATION_AUDIT.csv'},
    ('B4', 2031): {'sha256': '17cdf28b1b3032bbe1735f1203bd1cbf6993f78fb3d21e85f6b6a0cfef6fafea',
                   'bytes': 52914939, 'execution_commit': '943da957a3af846746c21b52d05a148bcb135064',
                   'identity_source': 'docs/research_readiness/20261031_extreme_precipitation_audit/EXTREME_PRECIPITATION_AUDIT.csv'},
    ('B7', 2029): {'sha256': '019a6dfabf2eef8eeb48bce993eaed64d86b78ea2da3e413e324f22f347f2e35',
                   'bytes': 53904005, 'execution_commit': 'b1f072e45fdd17b80106a774083995c350b28f04',
                   'identity_source': 'docs/research_readiness/20261031_extreme_precipitation_audit/EXTREME_PRECIPITATION_AUDIT.csv'},
    ('B7', 2030): {'sha256': '820796601fa0d0be5c11125171116c7548483b0e3e5ac45c102e5ca5d6ffc15d',
                   'bytes': 53905285, 'execution_commit': 'e81c6e1e0306e2a1e31103f1cc632be3c0d84d8c',
                   'identity_source': 'docs/research_readiness/20261031_extreme_precipitation_audit/EXTREME_PRECIPITATION_AUDIT.csv'},
    ('B7', 2031): {'sha256': '4537be7af702efd96d357a64099eb9c55f5cd9d2a4018677908e989c4a730fc7',
                   'bytes': 53906245, 'execution_commit': 'e81c6e1e0306e2a1e31103f1cc632be3c0d84d8c',
                   'identity_source': 'docs/research_readiness/20261031_extreme_precipitation_audit/EXTREME_PRECIPITATION_AUDIT.csv'},
    ('B8', 2029): {'sha256': '8abcf2082176bdbff54426649fe7a0125779873808e72e00197746f86a7f04f0',
                   'bytes': 53905021, 'execution_commit': 'ef11531a7cdeb35b767caebdb61e0e81c6123187',
                   'identity_source': 'docs/research_readiness/20261031_extreme_precipitation_audit/EXTREME_PRECIPITATION_AUDIT.csv'},
    ('B8', 2030): {'sha256': 'f20d81858e8a61e78778da846b970e75914609f3ed05069bbebdcec459ff246e',
                   'bytes': 53906237, 'execution_commit': 'e81c6e1e0306e2a1e31103f1cc632be3c0d84d8c',
                   'identity_source': 'docs/research_readiness/20261031_extreme_precipitation_audit/EXTREME_PRECIPITATION_AUDIT.csv'},
    ('B8', 2031): {'sha256': 'bc324e74209076613ae3ed9a2e20bab42e81456afd315728948ef5e2c5112f07',
                   'bytes': 53906877, 'execution_commit': 'e81c6e1e0306e2a1e31103f1cc632be3c0d84d8c',
                   'identity_source': 'docs/research_readiness/20261031_extreme_precipitation_audit/EXTREME_PRECIPITATION_AUDIT.csv'},
    ('B7_ZERO_DOTE', 2029): {'sha256': '445e4be5f49cba10057d90d16b82827b2c125964fd9bf4811d1e819fb3954a21',
                             'bytes': 53903301, 'execution_commit': '0c91ff0f36d5cce3f4516d38663482650f61b03a',
                             'identity_source': 'docs/research_readiness/20261025/evidence/final_test_preregistration_increment_20261030.json'},
    ('B7_ZERO_DOTE', 2030): {'sha256': 'b03ee41cd190dc7579a1fb993afb1f5598997fca91af3b1c2addc6eed430f0ba',
                             'bytes': 53905157, 'execution_commit': '8a4668377dbd40013245b54550c0963d10c286fb',
                             'identity_source': 'docs/research_readiness/20261025/evidence/final_test_preregistration_increment_20261030.json',
                             'byte_binding': '2026-11-27 stat+sha256 re-verified on B7_LAST_epoch_09.pt (B7 architecture, epoch 09)'},
    ('B7_ZERO_DOTE', 2031): {'sha256': 'f99952905157d8e649e567af671d0ee3ff02f11530a9996b80306ef758acdac0',
                             'bytes': 53906117, 'execution_commit': '8a4668377dbd40013245b54550c0963d10c286fb',
                             'identity_source': 'docs/research_readiness/20261025/evidence/final_test_preregistration_increment_20261030.json',
                             'byte_binding': '2026-11-27 stat+sha256 re-verified on B7_LAST_epoch_09.pt (B7 architecture, epoch 09)'},
}

CHECKPOINT_CATALOG_SHA256 = manifest.canonical_sha(
    {f'{model}:{seed}': {'sha256': item['sha256'], 'bytes': item['bytes'],
                         'execution_commit': item['execution_commit']}
     for (model, seed), item in sorted(CHECKPOINTS.items())})

# Frozen 2025 identity, mapped one-to-one from the draft protocol's
# ``frozen_inputs`` block (config/evaluation/
# b4_b7_b8_b7zero_2025_final_test_protocol_v1.yaml:105-110):
#   sp04_grid_sha256        <- frozen_inputs.sp04_grid_sha256
#                              (config/spatial/sp04_coordinate_manifest_v1.json)
#   supervision_mask_sha256 <- frozen_inputs.yunnan_mask_region_sha256
#                              (Yunnan supervision-region digest, 3430 of 100x100)
#   static_sha256           <- frozen_inputs.static_pack_sha256
#   train_scalers_sha256    <- frozen_inputs.train_statistics_sha256
# The mask *file* digest (9d921def...) is the sibling ``yunnan_mask_file_sha256``
# and is deliberately not an identity field: it belongs to the private B13/IMERG
# decode route, not to the catalogue identity.
FROZEN_IDENTITY_2025 = {
    'sp04_grid_sha256': 'e1c5d8ab1b58407503db4b56124f4a34a360507280b0e7989e8b9e2f60888473',
    'supervision_mask_sha256': '70368bec3149e998922d565dab83347ba33f465df481a03ac3f90b85f1286d4b',
    'static_sha256': '788572b1e82ba388d6ddcd6b1f8a987af818f44cdde9d5d613db5d35af5281bd',
    'train_scalers_sha256': '53ab2f07aabb02e66ad237452447a35e0e2896278eae9d2da179336c06fea980',
}

SHA = re.compile(r'[0-9a-f]{64}')

# Flat catalogue columns, ordered whitelist.  No outcome, metric, model-output,
# score or selection field is ever allowed into the catalogue.
COLUMNS = (
    'candidate_index', 'window_start', 'analysis_time', 'sample_id',
    'slot_00_relative_path', 'slot_00_bytes', 'slot_00_sha256',
    'slot_01_relative_path', 'slot_01_bytes', 'slot_01_sha256',
    'slot_02_relative_path', 'slot_02_bytes', 'slot_02_sha256',
    'slot_03_relative_path', 'slot_03_bytes', 'slot_03_sha256',
    'slot_04_relative_path', 'slot_04_bytes', 'slot_04_sha256',
    'slot_05_relative_path', 'slot_05_bytes', 'slot_05_sha256',
    'gfs_main_relative_path', 'gfs_main_bytes', 'gfs_main_sha256',
    'gfs_thermo_relative_path', 'gfs_thermo_bytes', 'gfs_thermo_sha256',
    'gfs_init',
    'imerg_day_relative_path', 'imerg_bytes', 'imerg_sha256',
    'imerg_product', 'imerg_version', 'imerg_run_type',
    'imerg_time_grid_provenance_pass', 'imerg_index',
    'imerg_valid_yunnan_count', 'supervision_region_pixels',
    'inventory_complete', 'eligible', 'rejection_reason',
)

INVENTORY_MODALITIES = ('himawari', 'gfs_main', 'gfs_thermo', 'imerg')
INVENTORY_KEYS = ('modality', 'relative_path', 'bytes', 'sha256', 'readable',
                  'product', 'version', 'run_type', 'time_grid_provenance_pass',
                  'valid_yunnan_count')
REJECTIONS = (
    'MISSING_HIMAWARI_SLOT',
    'MISSING_GFS_MAIN',
    'MISSING_GFS_THERMO',
    'MISSING_IMERG_DAY',
    'UNREADABLE_HIMAWARI_SLOT',
    'UNREADABLE_GFS',
    'UNREADABLE_IMERG',
    'BAD_INVENTORY_METADATA',
    'IMERG_METADATA_MISMATCH',
    'IMERG_TIME_GRID_MISMATCH',
    'IMERG_NO_YUNNAN_OVERLAP',
)

_CATALOGUE_AUTH_KEYS = ('version', 'decision_id', 'AUTHORIZED_BY', 'scope',
                        'FINAL_TEST_CATALOGUE_AUTHORIZED', 'FINAL_TEST_2025_AUTHORIZED',
                        'CATALOGUE_QC_PAYLOAD_AUTHORIZED', 'protocol', 'implementation',
                        'checkpoint_catalog_sha256', 'source_roots',
                        'inventory_measurement', 'identity', 'created_utc')
_FINAL_AUTH_KEYS = ('version', 'AUTHORIZED_BY', 'scope',
                    'FINAL_TEST_CATALOGUE_AUTHORIZED', 'FINAL_TEST_2025_AUTHORIZED',
                    'protocol', 'implementation', 'checkpoint_catalog_sha256',
                    'catalogue_sha256', 'population_sha256', 'freeze_record', 'created_utc')
_FREEZE_KEYS = ('version', 'status', 'scope', 'fixture_only', 'protocol', 'implementation',
                'checkpoint_catalog_sha256', 'identity', 'population', 'catalogue',
                'created_utc', 'eligible_count', 'rejected_count', 'rejection_counts',
                'payload_access_authorized')
_POP_CSV_KEYS = manifest.POPULATION_COLUMNS


def canonical_sha(value):
    return manifest.canonical_sha(value)


def sha256_bytes(payload):
    return hashlib.sha256(payload).hexdigest()


def sha256_file(path):
    return manifest.sha256_file(path)


def parse_utc(value):
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, str):
        parsed = datetime.fromisoformat(value)
    else:
        raise TypeError('UTC timestamp required')
    if parsed.tzinfo is None:
        raise ValueError('Timezone-aware UTC timestamp required')
    return parsed.astimezone(timezone.utc)


def iso_utc(value=None):
    return (value or datetime.now(timezone.utc)).astimezone(timezone.utc).isoformat()


def _lower_hex(value, label):
    if not isinstance(value, str) or len(value) != 64 or not SHA.fullmatch(value):
        raise ValueError('Lowercase 64-hex value required: ' + label)
    return value


def _exact_keys(value, keys, label):
    if not isinstance(value, dict) or tuple(value) != tuple(keys):
        raise ValueError(f'Exact {label} key set required')
    return True


def _protocol_entry(value):
    _exact_keys(value, ('path', 'sha256'), 'protocol binding')
    if not isinstance(value['path'], str) or not value['path'] or Path(value['path']).is_absolute():
        raise ValueError('Repository-relative protocol path required')
    _lower_hex(value['sha256'], 'protocol sha256')
    return {'path': value['path'], 'sha256': value['sha256']}


def _implementation_entry(value):
    _exact_keys(value, ('sha256', 'files'), 'implementation binding')
    _lower_hex(value['sha256'], 'implementation sha256')
    files = value['files']
    if not isinstance(files, dict) or not files:
        raise ValueError('Non-empty implementation file map required')
    for relpath, digest in files.items():
        if not isinstance(relpath, str) or not relpath:
            raise ValueError('Implementation file path required')
        _lower_hex(digest, 'implementation file sha256')
    return {'sha256': value['sha256'], 'files': dict(files)}


def _source_roots(value, *, fixture):
    _exact_keys(value, ('himawari', 'imerg', 'gfs', 'gfs_thermo'), 'source roots')
    for key in ('himawari', 'imerg', 'gfs', 'gfs_thermo'):
        if not isinstance(value[key], str) or not Path(value[key]).is_absolute():
            raise ValueError('Absolute source root required: ' + key)
    if fixture:
        return dict(value)
    expected = planning.PathLayout2025.default()
    wanted = dict(himawari=expected.himawari_root, imerg=expected.imerg_root,
                  gfs=expected.gfs_root, gfs_thermo=expected.gfs_thermo_root)
    if dict(value) != wanted:
        raise ValueError('Frozen 2025 source roots differ from the declared layout')
    return dict(value)


def safe_artifact_path(path):
    """Catalogue artefacts must stay outside frozen payload roots."""
    path = Path(path).resolve()
    text = str(path).replace('\\', '/').lower()
    for forbidden in ('h:/葵花202303_202510', 'f:/云南极端降水数据/raw',
                      'f:/pytorch', 'f:/云南极端降水数据/manifests'):
        if text == forbidden or text.startswith(forbidden + '/'):
            raise PermissionError('Catalogue artefacts must not be written under a payload/frozen root')
    return path


def _identity_entry(value):
    """Exact four-field frozen identity; must equal the protocol frozen_inputs."""
    _exact_keys(value, manifest.IDENTITY_FIELDS, 'frozen identity')
    identity = {key: _lower_hex(value[key], 'identity ' + key)
                for key in manifest.IDENTITY_FIELDS}
    if identity != FROZEN_IDENTITY_2025:
        raise ValueError('Frozen 2025 identity differs from the protocol frozen_inputs')
    return identity


def _inventory_measurement_entry(value):
    """Pin the stat-only inventory measurement JSON by path + SHA-256."""
    _exact_keys(value, ('path', 'sha256', 'created_utc'), 'inventory measurement binding')
    path = value['path']
    if not isinstance(path, str) or not path:
        raise ValueError('Inventory measurement path required')
    declared = Path(path)
    if declared.is_absolute():
        safe_artifact_path(declared)
    _lower_hex(value['sha256'], 'inventory measurement sha256')
    created = parse_utc(value['created_utc'])
    return {'path': path, 'sha256': value['sha256'], 'created_utc': created.isoformat()}


@dataclass(frozen=True)
class InventoryEntry:
    modality: str
    relative_path: str
    bytes: int
    sha256: str
    readable: bool = True
    product: str = ''
    version: str = ''
    run_type: str = ''
    time_grid_provenance_pass: bool = False
    valid_yunnan_count: int = 0
    valid_yunnan_counts: tuple = ()

    def __post_init__(self):
        if self.modality not in INVENTORY_MODALITIES:
            raise ValueError('Unknown inventory modality: ' + str(self.modality))
        path = Path(self.relative_path)
        if not self.relative_path or path.is_absolute() or '..' in path.parts or ':' in self.relative_path:
            raise ValueError('Safe relative inventory path required: ' + self.relative_path)
        if type(self.bytes) is not int or self.bytes < 0:
            raise ValueError('Non-negative integer byte size required')
        if self.sha256:
            _lower_hex(self.sha256, 'inventory sha256')
        if not isinstance(self.readable, bool):
            raise ValueError('Boolean readable flag required')
        if type(self.valid_yunnan_count) is not int or self.valid_yunnan_count < 0:
            raise ValueError('Non-negative Yunnan overlap count required')
        if self.valid_yunnan_counts:
            counts = tuple(self.valid_yunnan_counts)
            if len(counts) != 48:
                raise ValueError('48 half-hour Yunnan overlap counts required')
            if any(type(value) is not int or value < 0 for value in counts):
                raise ValueError('Non-negative half-hour Yunnan overlap counts required')
            object.__setattr__(self, 'valid_yunnan_counts', counts)

    def as_dict(self):
        return {key: getattr(self, key) for key in INVENTORY_KEYS if hasattr(self, key)}


def inventory_entry(value):
    if not isinstance(value, dict):
        raise ValueError('Inventory entry mapping required')
    unknown = [key for key in value if key not in INVENTORY_KEYS]
    if unknown:
        raise ValueError('Unknown inventory fields: ' + ', '.join(unknown))
    missing = [key for key in ('modality', 'relative_path', 'bytes', 'sha256') if key not in value]
    if missing:
        raise ValueError('Missing inventory fields: ' + ', '.join(missing))
    return InventoryEntry(**{key: value[key] for key in INVENTORY_KEYS if key in value})


class InventoryIndex:
    """Caller-supplied inventory; no directory traversal happens in this class."""

    def __init__(self, entries):
        indexed = {}
        for entry in entries:
            if not isinstance(entry, InventoryEntry):
                entry = inventory_entry(entry)
            if not entry.sha256:
                continue  # unverifiable entries are deliberately not indexed as present
            key = (entry.modality, entry.relative_path)
            if key in indexed:
                raise ValueError('Duplicate inventory entry: ' + str(key))
            indexed[key] = entry
        self._indexed = indexed

    def get(self, modality, relative_path):
        return self._indexed.get((modality, relative_path))

    def __len__(self):
        return len(self._indexed)

    def complete(self, modality, relative_path):
        entry = self.get(modality, relative_path)
        return entry is not None and entry.readable and entry.bytes > 0 and bool(entry.sha256)


def scheduled_times(population):
    manifest.validate_population(population, require_fixture=None)
    return tuple(planning.utc(row['analysis_time']) for row in population.document['scene_records'])


def _inventory_value(entry, field, default):
    return getattr(entry, field) if entry is not None else default


def catalogue_row(scene, index):
    """One flat catalogue row from planned scene + inventory lookup."""
    row = {key: None for key in COLUMNS}
    row['candidate_index'] = scene['candidate_index']
    row['window_start'] = scene['window_start']
    row['analysis_time'] = scene['analysis_time']
    row['sample_id'] = scene['sample_id']
    row['supervision_region_pixels'] = SUPERVISION_REGION_PIXELS
    reason = None
    satellites = []
    for slot in range(6):
        relative_path = scene[f'slot_{slot:02d}_relative_path']
        entry = index.get('himawari', relative_path)
        satellites.append(entry)
        row[f'slot_{slot:02d}_relative_path'] = relative_path
        row[f'slot_{slot:02d}_bytes'] = _inventory_value(entry, 'bytes', 0)
        row[f'slot_{slot:02d}_sha256'] = _inventory_value(entry, 'sha256', '')
        if entry is None:
            reason = reason or 'MISSING_HIMAWARI_SLOT'
        elif not index.complete('himawari', relative_path):
            reason = reason or ('UNREADABLE_HIMAWARI_SLOT' if not entry.readable else 'BAD_INVENTORY_METADATA')

    gfs_entries = {}
    for kind in ('gfs_main', 'gfs_thermo'):
        relative_path = scene[f'{kind}_relative_path']
        entry = index.get(kind, relative_path)
        gfs_entries[kind] = entry
        row[f'{kind}_relative_path'] = relative_path
        row[f'{kind}_bytes'] = _inventory_value(entry, 'bytes', 0)
        row[f'{kind}_sha256'] = _inventory_value(entry, 'sha256', '')
        if entry is None:
            reason = reason or f'MISSING_{kind.upper()}'
        elif not index.complete(kind, relative_path):
            reason = reason or ('UNREADABLE_GFS' if not entry.readable else 'BAD_INVENTORY_METADATA')
    row['gfs_init'] = scene['gfs_init']

    imerg_path = scene['imerg_day_relative_path']
    imerg_entry = index.get('imerg', imerg_path)
    # A day-cached entry may carry all 48 half-hour counts; the catalogue row
    # carries the count of the scene's own half-hour index.
    counts = getattr(imerg_entry, 'valid_yunnan_counts', ()) if imerg_entry is not None else ()
    imerg_count = counts[scene['imerg_index']] if counts else _inventory_value(imerg_entry, 'valid_yunnan_count', 0)
    row['imerg_day_relative_path'] = imerg_path
    row['imerg_bytes'] = _inventory_value(imerg_entry, 'bytes', 0)
    row['imerg_sha256'] = _inventory_value(imerg_entry, 'sha256', '')
    row['imerg_product'] = _inventory_value(imerg_entry, 'product', '')
    row['imerg_version'] = _inventory_value(imerg_entry, 'version', '')
    row['imerg_run_type'] = _inventory_value(imerg_entry, 'run_type', '')
    row['imerg_time_grid_provenance_pass'] = bool(_inventory_value(imerg_entry, 'time_grid_provenance_pass', False))
    row['imerg_valid_yunnan_count'] = imerg_count
    row['imerg_index'] = scene['imerg_index']
    if imerg_entry is None:
        reason = reason or 'MISSING_IMERG_DAY'
    elif not index.complete('imerg', imerg_path):
        reason = reason or ('UNREADABLE_IMERG' if not imerg_entry.readable else 'BAD_INVENTORY_METADATA')
    elif not (imerg_entry.product == IMERG_PRODUCT and imerg_entry.version == IMERG_VERSION
              and imerg_entry.run_type == IMERG_RUN_TYPE):
        reason = reason or 'IMERG_METADATA_MISMATCH'
    elif not imerg_entry.time_grid_provenance_pass:
        reason = reason or 'IMERG_TIME_GRID_MISMATCH'
    elif imerg_entry.valid_yunnan_count <= 0:
        reason = reason or 'IMERG_NO_YUNNAN_OVERLAP'

    row['inventory_complete'] = reason is None
    row['eligible'] = reason is None
    row['rejection_reason'] = reason
    if tuple(row) != COLUMNS:
        raise AssertionError('Catalogue column order drifted')
    return {key: row[key] for key in COLUMNS}


def build_catalogue(population, inventory, *, fixture=False):
    """Pure candidate-catalogue construction from planned rows + inventory."""
    manifest.validate_population(population, require_fixture=fixture)
    if not isinstance(inventory, InventoryIndex):
        inventory = InventoryIndex(inventory)
    rows = []
    for scene in population.document['scene_records']:
        rows.append(catalogue_row(scene, inventory))
    validate_catalogue(rows, expected_count=len(population.document['scene_records']))
    return tuple(rows)


def _scene_from_catalogue_row(row):
    """Reconstruct the planning scene row implied by one flat catalogue row."""
    analysis = planning.utc(row['analysis_time'])
    scene = {'candidate_index': row['candidate_index'], 'sample_id': row['sample_id'],
             'window_start': row['window_start'], 'analysis_time': row['analysis_time'],
             'month': analysis.month, 'gfs_init': row['gfs_init'],
             'gfs_main_relative_path': row['gfs_main_relative_path'],
             'gfs_thermo_relative_path': row['gfs_thermo_relative_path'],
             'imerg_day_relative_path': row['imerg_day_relative_path'],
             'imerg_index': row['imerg_index']}
    for slot, minutes in enumerate(planning.SATELLITE_OFFSETS_MINUTES):
        scene[f'slot_{slot:02d}_nominal'] = (analysis - timedelta(minutes=minutes)).isoformat()
        scene[f'slot_{slot:02d}_relative_path'] = row[f'slot_{slot:02d}_relative_path']
    return {key: scene[key] for key in planning._SCENE_KEYS}


def validate_catalogue(rows, *, expected_count=None):
    rows = list(rows)
    if not rows:
        raise ValueError('Non-empty catalogue required')
    if expected_count is not None and len(rows) != expected_count:
        raise ValueError('Catalogue count mismatch')
    ids = []
    rejections = {}
    for position, row in enumerate(rows):
        if not isinstance(row, dict) or tuple(row) != COLUMNS:
            raise ValueError('Exact 2025 catalogue schema required')
        if row['candidate_index'] != position:
            raise ValueError('Sequential candidate_index required')
        scene = _scene_from_catalogue_row(row)
        planning.validate_scene(scene, allow_october=True)
        if row['sample_id'] in ids:
            raise ValueError('Duplicate sample_id in catalogue')
        ids.append(row['sample_id'])
        for slot in range(6):
            if type(row[f'slot_{slot:02d}_bytes']) is not int or row[f'slot_{slot:02d}_bytes'] < 0:
                raise ValueError('Non-negative slot bytes required')
            if row[f'slot_{slot:02d}_sha256']:
                _lower_hex(row[f'slot_{slot:02d}_sha256'], 'slot sha256')
        for kind in ('gfs_main', 'gfs_thermo', 'imerg'):
            if type(row[f'{kind}_bytes']) is not int or row[f'{kind}_bytes'] < 0:
                raise ValueError('Non-negative inventory bytes required')
            if row[f'{kind}_sha256']:
                _lower_hex(row[f'{kind}_sha256'], kind + ' sha256')
        if row['imerg_index'] != planning.utc(row['window_start']).hour * 2 + planning.utc(row['window_start']).minute // 30:
            raise ValueError('IMERG half-hour index mismatch')
        if row['supervision_region_pixels'] != SUPERVISION_REGION_PIXELS:
            raise ValueError('Yunnan supervision region changed')
        if row['imerg_valid_yunnan_count'] < 0:
            raise ValueError('Negative Yunnan overlap count')
        if row['eligible']:
            if row['rejection_reason'] is not None:
                raise ValueError('Eligible row cannot carry a rejection reason')
            if not row['inventory_complete']:
                raise ValueError('Eligible row must have a complete inventory')
            if any(row[f'slot_{slot:02d}_bytes'] <= 0 or not row[f'slot_{slot:02d}_sha256'] for slot in range(6)):
                raise ValueError('Eligible row requires six verified satellite slots')
            if row['gfs_main_bytes'] <= 0 or row['gfs_thermo_bytes'] <= 0:
                raise ValueError('Eligible row requires GFS main and thermo files')
            if row['imerg_bytes'] <= 0 or row['imerg_valid_yunnan_count'] <= 0:
                raise ValueError('Eligible row requires a verified IMERG day with Yunnan overlap')
            if row['imerg_product'] != IMERG_PRODUCT or row['imerg_version'] != IMERG_VERSION:
                raise ValueError('Eligible row IMERG provenance mismatch')
            if row['imerg_run_type'] != IMERG_RUN_TYPE or not row['imerg_time_grid_provenance_pass']:
                raise ValueError('Eligible row IMERG run/time-grid mismatch')
        else:
            if row['rejection_reason'] not in REJECTIONS:
                raise ValueError('Unknown rejection reason')
            if row['inventory_complete']:
                raise ValueError('Incomplete row must carry inventory_complete False')
            rejections[row['rejection_reason']] = rejections.get(row['rejection_reason'], 0) + 1
    return True


def csv_bytes(rows, columns):
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=list(columns), lineterminator='\n', extrasaction='raise')
    writer.writeheader()
    for row in rows:
        if not isinstance(row, dict) or tuple(row) != tuple(columns):
            raise ValueError('CSV row schema mismatch')
        writer.writerow(row)
    return buffer.getvalue().encode('utf-8')


def write_csv(path, rows, columns, *, overwrite=False):
    path = Path(path)
    if path.exists() and not overwrite:
        raise FileExistsError('Append-only catalogue artefact exists: ' + str(path))
    payload = csv_bytes(rows, columns)
    with path.open('wb' if overwrite else 'xb') as stream:
        stream.write(payload)
    return sha256_bytes(payload)


def _csv_scalar(column, value):
    if column.endswith('_bytes') or column in ('candidate_index', 'imerg_index',
                                               'imerg_valid_yunnan_count', 'supervision_region_pixels'):
        return int(value)
    if column in ('eligible', 'inventory_complete', 'imerg_time_grid_provenance_pass'):
        return value == 'True'
    if column == 'rejection_reason':
        return None if value == '' else value
    return value


def read_csv(path):
    path = Path(path)
    with path.open('r', encoding='utf-8', newline='') as stream:
        reader = csv.DictReader(stream)
        if tuple(reader.fieldnames or ()) != COLUMNS:
            raise ValueError('Catalogue CSV header differs from the frozen whitelist')
        rows = [{key: _csv_scalar(key, value) for key, value in row.items()} for row in reader]
    validate_catalogue(rows)
    return tuple(rows)


def population_csv_rows(population):
    return manifest.population_projection(population.document)


def eligibility_summary(rows):
    rejections = {}
    eligible = 0
    for row in rows:
        if row['eligible']:
            eligible += 1
        else:
            rejections[row['rejection_reason']] = rejections.get(row['rejection_reason'], 0) + 1
    return {'eligible': eligible, 'rejected': len(rows) - eligible,
            'rejection_counts': {key: rejections[key] for key in sorted(rejections)}}


def freeze_record(authorization, population, catalogue_sha256, population_sha256, *,
                  eligible_count, rejected_count, rejection_counts, created_utc=None):
    record = {
        'version': VERSION, 'status': 'CATALOGUE_FROZEN',
        'scope': FIXTURE_SCOPE if authorization.fixture else CATALOGUE_SCOPE,
        'fixture_only': bool(authorization.fixture),
        'protocol': dict(authorization.protocol),
        'implementation': dict(authorization.implementation),
        'checkpoint_catalog_sha256': CHECKPOINT_CATALOG_SHA256,
        'identity': dict(population.document['identity']),
        'population': {'sha256': population_sha256}, 'catalogue': {'sha256': catalogue_sha256},
        'created_utc': iso_utc(created_utc), 'eligible_count': eligible_count,
        'rejected_count': rejected_count, 'rejection_counts': dict(rejection_counts),
        'payload_access_authorized': False,
    }
    if tuple(record) != _FREEZE_KEYS:
        raise AssertionError('Freeze record schema drifted')
    return record


class CatalogueAuthorization2025:
    """Catalogue-only grant.  Constructing one never grants payload access."""

    def __init__(self, value, *, fixture=False):
        if fixture:
            base = planning.synthetic_layout(Path(value['fixture_root'])) if 'fixture_root' in value else None
            if base is None:
                raise ValueError('Fixture authorization needs an absolute fixture root')
            created_iso = iso_utc(value.get('created_utc'))
            self._value = {
                'version': VERSION, 'decision_id': 'ENGINEERING_FIXTURE',
                'AUTHORIZED_BY': 'ENGINEERING_FIXTURE', 'scope': FIXTURE_SCOPE,
                'FINAL_TEST_CATALOGUE_AUTHORIZED': False,
                'FINAL_TEST_2025_AUTHORIZED': False,
                'CATALOGUE_QC_PAYLOAD_AUTHORIZED': False,
                'protocol': {'path': 'FIXTURE', 'sha256': '0' * 64},
                'implementation': {'sha256': '0' * 64, 'files': {'fixture': '0' * 64}},
                'checkpoint_catalog_sha256': CHECKPOINT_CATALOG_SHA256,
                'source_roots': {'himawari': base.himawari_root, 'imerg': base.imerg_root,
                                 'gfs': base.gfs_root, 'gfs_thermo': base.gfs_thermo_root},
                'inventory_measurement': {'path': 'FIXTURE', 'sha256': '0' * 64,
                                          'created_utc': created_iso},
                'identity': dict(value.get('identity') or {}),
                'created_utc': created_iso,
            }
            self.fixture = True
            self.created_utc = parse_utc(self._value['created_utc'])
            return
        _exact_keys(value, _CATALOGUE_AUTH_KEYS, 'catalogue authorization')
        if value['version'] != VERSION or value['AUTHORIZED_BY'] != 'RESEARCHER':
            raise ValueError('Researcher-authored v1 catalogue authorization required')
        if value['scope'] != CATALOGUE_SCOPE:
            raise ValueError('Catalogue authorization scope mismatch')
        if not isinstance(value['decision_id'], str) or not value['decision_id']:
            raise ValueError('Catalogue authorization decision_id required')
        if value['FINAL_TEST_CATALOGUE_AUTHORIZED'] is not True:
            raise PermissionError('Catalogue authorization not granted')
        if value['FINAL_TEST_2025_AUTHORIZED'] is not False:
            raise PermissionError('Catalogue authorization must not grant final-test payload access')
        if not isinstance(value['CATALOGUE_QC_PAYLOAD_AUTHORIZED'], bool):
            raise ValueError('Boolean CATALOGUE_QC_PAYLOAD_AUTHORIZED required')
        protocol = _protocol_entry(value['protocol'])
        implementation = _implementation_entry(value['implementation'])
        catalog_sha = _lower_hex(value['checkpoint_catalog_sha256'], 'checkpoint catalog sha256')
        if catalog_sha != CHECKPOINT_CATALOG_SHA256:
            raise ValueError('Checkpoint catalogue digest mismatch')
        roots = _source_roots(value['source_roots'], fixture=False)
        measurement = _inventory_measurement_entry(value['inventory_measurement'])
        identity = _identity_entry(value['identity'])
        created = parse_utc(value['created_utc'])
        if created < parse_utc(measurement['created_utc']):
            raise PermissionError('Catalogue QC authorization must not precede the inventory measurement')
        self._value = {'version': VERSION, 'decision_id': value['decision_id'],
                       'AUTHORIZED_BY': 'RESEARCHER', 'scope': CATALOGUE_SCOPE,
                       'FINAL_TEST_CATALOGUE_AUTHORIZED': True, 'FINAL_TEST_2025_AUTHORIZED': False,
                       'CATALOGUE_QC_PAYLOAD_AUTHORIZED': bool(value['CATALOGUE_QC_PAYLOAD_AUTHORIZED']),
                       'protocol': protocol, 'implementation': implementation,
                       'checkpoint_catalog_sha256': catalog_sha, 'source_roots': roots,
                       'inventory_measurement': measurement, 'identity': identity,
                       'created_utc': created.isoformat()}
        self.fixture = False
        self.created_utc = created

    @classmethod
    def load(cls, path, expected_sha256=None):
        path = Path(path)
        payload = path.read_bytes()
        digest = sha256_bytes(payload)
        if expected_sha256 is not None and digest != _lower_hex(expected_sha256, 'expected authorization sha256'):
            raise ValueError('Catalogue authorization SHA mismatch')
        return cls(json.loads(payload.decode('utf-8')))

    @classmethod
    def fixture_only(cls, root, *, created_utc=None):
        return cls({'fixture_root': str(Path(root)), 'created_utc': created_utc}, fixture=True)

    def require_catalogue(self, *, allow_fixture=False):
        if self.fixture and not allow_fixture:
            raise PermissionError('Engineering fixture authorization cannot build a real catalogue')
        if self.fixture:
            return True
        if self._value['FINAL_TEST_CATALOGUE_AUTHORIZED'] is not True:
            raise PermissionError('Catalogue authorization missing')
        return True

    def require_qc_payload(self):
        """Permit read-only hash/metadata QC of the frozen inventory files only."""
        if self.fixture:
            raise PermissionError('Engineering fixture authorization cannot open 2025 payloads')
        if self._value['CATALOGUE_QC_PAYLOAD_AUTHORIZED'] is not True:
            raise PermissionError('Catalogue QC payload authorization missing')
        return True

    def require_final(self):
        raise PermissionError('Catalogue-only authorization cannot run final inference')

    @property
    def protocol(self):
        return dict(self._value['protocol'])

    @property
    def implementation(self):
        return dict(self._value['implementation'])

    @property
    def inventory_measurement(self):
        return dict(self._value['inventory_measurement'])

    @property
    def identity(self):
        return dict(self._value['identity'])

    def as_dict(self):
        return json.loads(json.dumps(self._value))


class FinalAuthority2025:
    """Separate post-freeze final-test grant; still no payload access by itself."""

    def __init__(self, value):
        _exact_keys(value, _FINAL_AUTH_KEYS, 'final-test authorization')
        if value['version'] != VERSION or value['AUTHORIZED_BY'] != 'RESEARCHER':
            raise ValueError('Researcher-authored v1 final authorization required')
        if value['scope'] != FINAL_SCOPE:
            raise ValueError('Final-test authorization scope mismatch')
        if value['FINAL_TEST_CATALOGUE_AUTHORIZED'] is not True:
            raise PermissionError('Final-test authorization requires the catalogue authorization')
        if value['FINAL_TEST_2025_AUTHORIZED'] is not True:
            raise PermissionError('Final-test authorization not granted')
        protocol = _protocol_entry(value['protocol'])
        implementation = _implementation_entry(value['implementation'])
        catalog_sha = _lower_hex(value['checkpoint_catalog_sha256'], 'checkpoint catalog sha256')
        if catalog_sha != CHECKPOINT_CATALOG_SHA256:
            raise ValueError('Checkpoint catalogue digest mismatch')
        _exact_keys(value['freeze_record'], ('sha256', 'created_utc', 'status'), 'freeze-record binding')
        _lower_hex(value['freeze_record']['sha256'], 'freeze record sha256')
        if value['freeze_record']['status'] != 'CATALOGUE_FROZEN':
            raise ValueError('Freeze record not frozen')
        created = parse_utc(value['created_utc'])
        frozen = parse_utc(value['freeze_record']['created_utc'])
        if created < frozen:
            raise PermissionError('Final authorization must not precede the catalogue freeze')
        self._value = {'version': VERSION, 'AUTHORIZED_BY': 'RESEARCHER', 'scope': FINAL_SCOPE,
                       'FINAL_TEST_CATALOGUE_AUTHORIZED': True, 'FINAL_TEST_2025_AUTHORIZED': True,
                       'protocol': protocol, 'implementation': implementation,
                       'checkpoint_catalog_sha256': catalog_sha,
                       'catalogue_sha256': _lower_hex(value['catalogue_sha256'], 'catalogue sha256'),
                       'population_sha256': _lower_hex(value['population_sha256'], 'population sha256'),
                       'freeze_record': dict(value['freeze_record']),
                       'created_utc': created.isoformat()}
        self.created_utc = created

    @classmethod
    def load(cls, path, expected_sha256=None):
        path = Path(path)
        payload = path.read_bytes()
        digest = sha256_bytes(payload)
        if expected_sha256 is not None and digest != _lower_hex(expected_sha256, 'expected authorization sha256'):
            raise ValueError('Final authorization SHA mismatch')
        return cls(json.loads(payload.decode('utf-8')))

    def require_final(self):
        if self._value['FINAL_TEST_2025_AUTHORIZED'] is not True:
            raise PermissionError('Final-test authorization missing')
        return True

    def require_catalogue(self, *, allow_fixture=False):
        raise PermissionError('Final authority does not grant a new catalogue build')


def verify_catalogue_bundle(authorization, *, catalogue_path, population_path, freeze_path):
    """Cross-check CSVs and the freeze record against a FinalAuthority2025."""
    if not isinstance(authorization, FinalAuthority2025):
        raise TypeError('FinalAuthority2025 required')
    authorization.require_final()
    catalogue = read_csv(catalogue_path)
    population = manifest.read_population(population_path)
    if authorization._value['catalogue_sha256'] != sha256_file(catalogue_path):
        raise ValueError('Catalogue SHA differs from the final authorization')
    if authorization._value['population_sha256'] != sha256_file(population_path):
        raise ValueError('Population SHA differs from the final authorization')
    freeze_payload = Path(freeze_path).read_bytes()
    if authorization._value['freeze_record']['sha256'] != sha256_bytes(freeze_payload):
        raise ValueError('Freeze record SHA differs from the final authorization')
    freeze = json.loads(freeze_payload.decode('utf-8'))
    _exact_keys(freeze, _FREEZE_KEYS, 'freeze record')
    if freeze['status'] != 'CATALOGUE_FROZEN' or freeze['fixture_only']:
        raise ValueError('Real frozen catalogue required')
    if freeze['identity'] != population['identity']:
        raise ValueError('Freeze identity differs from the population identity')
    if freeze['population']['sha256'] != sha256_file(population_path):
        raise ValueError('Freeze record population SHA mismatch')
    if freeze['catalogue']['sha256'] != sha256_file(catalogue_path):
        raise ValueError('Freeze record catalogue SHA mismatch')
    if freeze['eligible_count'] != sum(1 for row in catalogue if row['eligible']):
        raise ValueError('Freeze record eligible count mismatch')
    if freeze['protocol'] != authorization._value['protocol']:
        raise ValueError('Freeze protocol binding mismatch')
    if freeze['implementation'] != authorization._value['implementation']:
        raise ValueError('Freeze implementation binding mismatch')
    if len(population['scene_records']) != len(catalogue):
        raise ValueError('Population/catalogue length mismatch')
    for scene, row in zip(population['scene_records'], catalogue):
        if scene['sample_id'] != row['sample_id']:
            raise ValueError('Population/catalogue scene order mismatch')
        if row['eligible'] and row['imerg_valid_yunnan_count'] <= 0:
            raise ValueError('Eligible scene has no Yunnan overlap')
    verify = manifest.validate_population(population)
    if not verify:
        raise ValueError('Population validation failed')
    return {'catalogue': catalogue, 'population': population, 'freeze': freeze,
            'eligible_count': freeze['eligible_count'],
            'rejected_count': freeze['rejected_count'],
            'rejection_counts': dict(freeze['rejection_counts'])}


def build_catalogue_artefacts(authorization, population, inventory, output_dir, *,
                              fixture=False, created_utc=None, overwrite=False):
    """Authorized metadata-only catalogue build; writes CSV/JSON append-only."""
    if not isinstance(authorization, CatalogueAuthorization2025):
        raise TypeError('CatalogueAuthorization2025 required')
    if bool(authorization.fixture) is not bool(fixture):
        raise PermissionError('Fixture mode must match the authorization')
    authorization.require_catalogue(allow_fixture=fixture)
    manifest.validate_population(population, require_fixture=fixture)
    if not fixture and dict(population.document['identity']) != authorization.identity:
        raise ValueError('Population identity differs from the catalogue authorization identity')
    rows = build_catalogue(population, inventory, fixture=fixture)
    summary = eligibility_summary(rows)
    output = safe_artifact_path(output_dir)
    if output.exists():
        raise FileExistsError('Append-only catalogue output directory already exists: ' + str(output))
    output.mkdir(parents=True, exist_ok=False)
    candidate_path = output / CATALOGUE_FILENAME
    population_path = output / POPULATION_FILENAME
    catalogue_sha = write_csv(candidate_path, rows, COLUMNS)
    population_sha = manifest.write_population(population_path, population)
    record = freeze_record(authorization, population, catalogue_sha, population_sha,
                           eligible_count=summary['eligible'], rejected_count=summary['rejected'],
                           rejection_counts=summary['rejection_counts'], created_utc=created_utc)
    freeze_path = output / FREEZE_FILENAME
    freeze_payload = (json.dumps(record, indent=2, allow_nan=False) + '\n').encode('utf-8')
    freeze_path.write_bytes(freeze_payload)
    freeze_sha = sha256_bytes(freeze_payload)
    verify_catalogue_bundle_readonly(candidate_path, population_path, freeze_path)
    return {'output_dir': str(output), 'catalogue_path': str(candidate_path),
            'population_path': str(population_path), 'freeze_path': str(freeze_path),
            'catalogue_sha256': catalogue_sha, 'population_sha256': population_sha,
            'freeze_sha256': freeze_sha, 'eligible_count': summary['eligible'],
            'rejected_count': summary['rejected'], 'rejection_counts': summary['rejection_counts'],
            'fixture_only': bool(fixture)}


def verify_catalogue_bundle_readonly(catalogue_path, population_path, freeze_path):
    """Read-only consistency check of a just-written (or existing) bundle."""
    rows = read_csv(catalogue_path)
    population = manifest.read_population(population_path)
    freeze = json.loads(Path(freeze_path).read_text(encoding='utf-8'))
    _exact_keys(freeze, _FREEZE_KEYS, 'freeze record')
    if freeze['catalogue']['sha256'] != sha256_file(catalogue_path):
        raise ValueError('Freeze catalogue SHA mismatch')
    if freeze['population']['sha256'] != sha256_file(population_path):
        raise ValueError('Freeze population SHA mismatch')
    if len(rows) != len(population['scene_records']):
        raise ValueError('Catalogue/population length mismatch')
    if freeze['eligible_count'] != sum(1 for row in rows if row['eligible']):
        raise ValueError('Freeze eligible count mismatch')
    return True


def authorize_payload(*args, **kwargs):
    """Payload access is never granted by the catalogue/protocol code."""
    raise PermissionError('2025 payload access requires a separate payload-phase authorization')
