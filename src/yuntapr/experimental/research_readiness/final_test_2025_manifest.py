"""2025 final-test population manifest: identity, scene rows and digest, no payload I/O.

The manifest is *metadata only*.  It can be built from planned rows plus a
caller-supplied frozen identity.  Real 2025 payload files are never opened,
stat'ed or listed here.  A synthetic fixture document is explicitly tagged
``SYNTHETIC_FIXTURE_2025`` and its rows must live under a temporary root.

Identity fields (frozen 2023/2024 inputs reused by the 2025 read-only test):
``sp04_grid_sha256``, ``supervision_mask_sha256``, ``static_sha256`` and
``train_scalers_sha256``.  Three of those values are pinned by prior evidence;
the SP04 grid identity must be supplied by the final catalogue freeze.
"""

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path

from . import final_test_2025_planning as planning

IDENTITY_FIELDS = ('sp04_grid_sha256', 'supervision_mask_sha256', 'static_sha256',
                   'train_scalers_sha256')
STATUS_FIXTURE = 'SYNTHETIC_FIXTURE_2025'
STATUS_PENDING = 'REAL_POPULATION_PENDING_CATALOGUE_FREEZE'
SCOPE = 'B4_B7_B8_2025_MAR_SEP_FINAL_TEST_POPULATION_ONLY'
FIXTURE_SCOPE = 'ENGINEERING_FIXTURE_2025_POPULATION_ONLY'
SUPERVISION_REGION_PIXELS = 3430

# Values evidenced by the frozen 2023/2024 files.  The SP04 grid identity is not
# recorded as one consolidated SHA in the public evidence and therefore stays
# unbound until the private catalogue freeze binds it.
FROZEN_IDENTITY_EVIDENCE_2023_2024 = {
    'sp04_grid_sha256': None,
    'supervision_mask_sha256': '70368bec3149e998922d565dab83347ba33f465df481a03ac3f90b85f1286d4b',
    'static_sha256': '788572b1e82ba388d6ddcd6b1f8a987af818f44cdde9d5d613db5d35af5281bd',
    'train_scalers_sha256': '53ab2f07aabb02e66ad237452447a35e0e2896278eae9d2da179336c06fea980',
}

POPULATION_COLUMNS = (
    'candidate_index', 'sample_id', 'window_start', 'analysis_time',
    'slot_00_relative_path', 'slot_01_relative_path', 'slot_02_relative_path',
    'slot_03_relative_path', 'slot_04_relative_path', 'slot_05_relative_path',
    'gfs_main_relative_path', 'gfs_thermo_relative_path', 'gfs_init',
    'imerg_day_relative_path', 'imerg_index', 'scene_sha256',
)

_POP_KEYS = ('version', 'year', 'scope', 'status', 'fixture_only', 'identity',
             'identity_sha256', 'months', 'scene_count', 'supervision_region_pixels',
             'clock_convention', 'scene_records', 'population_sha256', 'manifest_sha256')


def canonical_sha(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':')).encode('utf-8')).hexdigest()


def sha256_file(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda: stream.read(1 << 20), b''):
            digest.update(chunk)
    return digest.hexdigest()


def validate_identity(identity):
    if not isinstance(identity, dict) or tuple(identity) != IDENTITY_FIELDS:
        raise ValueError('Exact four-field frozen identity required: ' + repr(IDENTITY_FIELDS))
    for key in IDENTITY_FIELDS:
        value = identity[key]
        if not isinstance(value, str) or len(value) != 64 or any(c not in '0123456789abcdef' for c in value):
            raise ValueError('Lowercase 64-hex identity value required: ' + key)
    return True


def identity_sha256(identity):
    validate_identity(identity)
    return canonical_sha({key: identity[key] for key in IDENTITY_FIELDS})


def _month_counts(scene_records):
    counts = {}
    for row in scene_records:
        month = int(row['analysis_time'][5:7])
        counts[str(month)] = counts.get(str(month), 0) + 1
    return {key: counts[key] for key in sorted(counts)}


@dataclass(frozen=True)
class Population:
    document: dict

    @property
    def rows(self):
        return tuple(self.document['scene_records'])

    @property
    def population_sha256(self):
        return self.document['population_sha256']

    @property
    def identity(self):
        return dict(self.document['identity'])

    def csv_rows(self):
        return tuple(flat_population_row(row) for row in self.rows)


def flat_population_row(scene):
    """Flat population-manifest row for one scene (metadata only)."""
    row = {key: scene[key] for key in planning._SCENE_KEYS}
    planning.validate_scene(row, allow_october=True)
    flat = {'candidate_index': scene['candidate_index'], 'sample_id': scene['sample_id'],
            'window_start': scene['window_start'], 'analysis_time': scene['analysis_time']}
    for slot in range(6):
        flat[f'slot_{slot:02d}_relative_path'] = scene[f'slot_{slot:02d}_relative_path']
    flat['gfs_main_relative_path'] = scene['gfs_main_relative_path']
    flat['gfs_thermo_relative_path'] = scene['gfs_thermo_relative_path']
    flat['gfs_init'] = scene['gfs_init']
    flat['imerg_day_relative_path'] = scene['imerg_day_relative_path']
    flat['imerg_index'] = scene['imerg_index']
    flat['scene_sha256'] = planning.scene_digest(row)
    if tuple(flat) != POPULATION_COLUMNS:
        raise AssertionError('Population column order drifted')
    return flat


def build_population(scene_rows, identity, *, expected_count=None, allow_october=False,
                     fixture=False, supervision_region_pixels=SUPERVISION_REGION_PIXELS):
    """Validate planned rows and return a metadata-only population document.

    ``fixture=True`` tags the document ``SYNTHETIC_FIXTURE_2025`` and relaxes the
    full-calendar count; it never relaxes clock, uniqueness or relative-path
    validation.  A fixture root is checked by the caller/planning module.
    """
    validate_identity(identity)
    if type(supervision_region_pixels) is not int or supervision_region_pixels <= 0:
        raise ValueError('Frozen Yunnan supervision pixel count must be positive')
    rows = list(scene_rows)
    if not rows:
        raise ValueError('Non-empty scene population required')
    for row in rows:
        planning.validate_scene(row, allow_october=allow_october)
    records = [dict(row) for row in rows]
    ids = [row['sample_id'] for row in records]
    if len(set(ids)) != len(ids):
        raise ValueError('Duplicate sample_id in population')
    starts = [planning.utc(row['window_start']) for row in records]
    if starts != sorted(starts):
        raise ValueError('Population rows must be in strict analysis order')
    if [row['candidate_index'] for row in records] != list(range(len(records))):
        raise ValueError('Sequential candidate_index required')
    if expected_count is not None:
        if type(expected_count) is not int or expected_count <= 0:
            raise ValueError('Positive expected count required')
        if len(records) != expected_count:
            raise ValueError(f'Population count {len(records)} != expected {expected_count}')
    if not fixture:
        if 10 in {planning.utc(row['analysis_time']).month for row in records}:
            raise PermissionError('October population requires a separate explicit scope')
    body = {
        'version': 'v1', 'year': planning.YEAR,
        'scope': FIXTURE_SCOPE if fixture else SCOPE,
        'status': STATUS_FIXTURE if fixture else STATUS_PENDING,
        'fixture_only': bool(fixture), 'identity': {key: identity[key] for key in IDENTITY_FIELDS},
        'identity_sha256': identity_sha256(identity),
        'months': _month_counts(records), 'scene_count': len(records),
        'supervision_region_pixels': supervision_region_pixels,
        'clock_convention': planning.scope_manifest(allow_october=allow_october)['clock_convention'],
        'scene_records': records,
    }
    body['population_sha256'] = canonical_sha({
        'identity_sha256': body['identity_sha256'], 'fixture_only': bool(fixture),
        'months': body['months'], 'scene_records': records,
    })
    body['manifest_sha256'] = canonical_sha(body)
    document = {key: body[key] for key in _POP_KEYS}
    if tuple(document) != _POP_KEYS:
        raise AssertionError('Population schema drifted')
    return Population(document)


def validate_population(document, *, expected_count=None, allow_october=False,
                        require_fixture=None):
    """Recompute every digest and revalidate every row of a population document."""
    if isinstance(document, Population):
        document = document.document
    if not isinstance(document, dict) or tuple(document) != _POP_KEYS:
        raise ValueError('Exact population document schema required')
    if document['version'] != 'v1' or document['year'] != planning.YEAR:
        raise ValueError('Unsupported population version/year')
    fixture = document['fixture_only']
    if type(fixture) is not bool:
        raise ValueError('Boolean fixture_only required')
    if require_fixture is not None and fixture is not require_fixture:
        raise ValueError('Fixture mode differs from the required mode')
    if document['status'] != (STATUS_FIXTURE if fixture else STATUS_PENDING):
        raise ValueError('Population status does not match fixture mode')
    if document['scope'] != (FIXTURE_SCOPE if fixture else SCOPE):
        raise ValueError('Population scope does not match fixture mode')
    identity = document['identity']
    validate_identity(identity)
    if document['identity_sha256'] != identity_sha256(identity):
        raise ValueError('Population identity digest mismatch')
    records = document['scene_records']
    if not isinstance(records, list) or len(records) != document['scene_count'] or not records:
        raise ValueError('Non-empty scene record count required')
    for row in records:
        planning.validate_scene(row, allow_october=allow_october)
    ids = [row['sample_id'] for row in records]
    if len(set(ids)) != len(ids):
        raise ValueError('Duplicate sample_id in population')
    if [row['candidate_index'] for row in records] != list(range(len(records))):
        raise ValueError('Sequential candidate_index required')
    if starts := [planning.utc(row['window_start']) for row in records]:
        if starts != sorted(starts):
            raise ValueError('Population rows must be in strict analysis order')
    if document['months'] != _month_counts(records):
        raise ValueError('Monthly scene counts mismatch')
    if document['supervision_region_pixels'] != SUPERVISION_REGION_PIXELS:
        raise ValueError('Yunnan supervision pixel count changed')
    if expected_count is not None and len(records) != expected_count:
        raise ValueError(f'Population count {len(records)} != expected {expected_count}')
    recomputed = canonical_sha({'identity_sha256': document['identity_sha256'],
                                'fixture_only': fixture, 'months': document['months'],
                                'scene_records': records})
    if document['population_sha256'] != recomputed:
        raise ValueError('Population digest mismatch')
    body = {key: document[key] for key in _POP_KEYS if key != 'manifest_sha256'}
    if document['manifest_sha256'] != canonical_sha(body):
        raise ValueError('Population manifest digest mismatch')
    return True


def population_projection(document):
    """Rows suitable for the population CSV (flat, ordered columns)."""
    validate_population(document, require_fixture=None)
    return tuple(flat_population_row(row) for row in document['scene_records'])


def read_population(path):
    payload = json.loads(Path(path).read_text(encoding='utf-8'))
    validate_population(payload)
    return payload


def write_population(path, document, *, overwrite=False):
    if isinstance(document, Population):
        document = document.document
    validate_population(document, require_fixture=None)
    path = Path(path)
    mode, open_kwargs = ('w', {'encoding': 'utf-8'}) if overwrite else ('x', {'encoding': 'utf-8'})
    if not overwrite and path.exists():
        raise FileExistsError('Append-only population manifest: ' + str(path))
    with path.open(mode, **open_kwargs) as stream:
        json.dump(document, stream, indent=2, sort_keys=False, allow_nan=False)
        stream.write('\n')
    return sha256_file(path)
