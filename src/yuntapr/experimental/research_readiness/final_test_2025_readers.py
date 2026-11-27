"""2025 payload readers behind an explicit, deny-by-default access object.

The frozen 2023/2024 readers (``gfs.read_gfs_file``, ``stage2.population
.read_seven_band``, ``dataset_b1``) keep rejecting 2025 paths and identities.
This module is the *only* 2025-capable reader layer and it opens a file only
after a ``PayloadAuthorization2025`` was supplied by a caller that already
passed the separate payload-phase gate.  Nothing here lists, globs or stats a
2025 directory on its own: every call receives one explicit relative path from
the frozen planning/ catalogue side.

Synthetic fixtures are limited to an explicit temporary root tagged
``ENGINEERING_FIXTURE_2025_PAYLOAD_ONLY`` and can never resolve into the real
Himawari/IMERG/GFS roots.
"""
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
import hashlib
import json
from pathlib import Path
import re
from types import MappingProxyType

import numpy as np

from yuntapr.data.himawari_b13 import decode_b13
from yuntapr.data.imerg_v07 import decode_imerg
from yuntapr.experimental.core_innovation import gfs
from yuntapr.experimental.core_innovation.grid import GridSpec
from yuntapr.experimental.core_innovation.multispectral import (
    MultispectralBatch, TrainNormalization)

from . import final_test_2025_planning as planning

UTC = timezone.utc
VERSION = 'v1'
PAYLOAD_SCOPE = 'B4_B7_B8_2025_FINAL_TEST_PAYLOAD_ONLY'
FIXTURE_SCOPE = 'ENGINEERING_FIXTURE_2025_PAYLOAD_ONLY'
SHA256 = re.compile(r'[0-9a-f]{64}')
CHANNELS = planning.CHANNELS
GFS_LEAD = timedelta(hours=planning.GFS_LEAD_HOURS)
GFS_INIT_HOURS = planning.ANALYSIS_HOURS
MAX_SATELLITE_BYTES = 8 * 1024 ** 2
MAX_GFS_BYTES = 2 * 1024 ** 2
MAX_IMERG_BYTES = 32 * 1024 ** 2
IMERG_PRODUCT = 'GPM_3IMERGHH_07'
IMERG_VERSION = 'V07'
IMERG_RUN_TYPE = 'Final'
IMERG_SHAPE = (48, 130, 140)
NATIVE_SHAPE = (501, 501)
SUPERVISION_REGION_PIXELS = 3430

_PAYLOAD_AUTH_KEYS = (
    'version', 'AUTHORIZED_BY', 'scope', 'FINAL_TEST_2025_PAYLOAD_AUTHORIZED',
    'protocol', 'catalogue_sha256', 'roots', 'allow_october', 'created_utc',
)
_FIXTURE_AUTH_KEYS = ('fixture_root', 'created_utc')


def _exact_keys(value, keys, label):
    if not isinstance(value, dict):
        raise ValueError(f'{label} must be a JSON object')
    if tuple(sorted(value)) != tuple(sorted(keys)):
        raise ValueError(f'{label} must carry exactly the frozen keys')


def _utc(value):
    parsed = planning.utc(value)
    return parsed


def _sha_bytes(payload):
    return hashlib.sha256(payload).hexdigest()


def _lexical_normalize(text):
    import os
    return os.path.normpath(text)


def _within(path, root):
    try:
        Path(path).relative_to(Path(root))
    except ValueError:
        return False
    return True


# ---------------------------------------------------------------------------
# Clock identity: a 2025 sibling of ``gfs.ForecastIdentity`` (old guard intact)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ForecastIdentity2025:
    """2025-only forecast identity; the frozen 2023/2024 class is untouched."""

    init: datetime
    lead: timedelta
    valid: datetime

    def __post_init__(self):
        init, valid = _utc(self.init), _utc(self.valid)
        if init.year != planning.YEAR or valid.year != planning.YEAR:
            raise PermissionError('2025 final-test identity only')
        if valid.month not in planning.AUTHORIZABLE_MONTHS:
            raise PermissionError('2025 March..October identity only')
        carry_in = datetime(2025, 2, 28, 18, 0, tzinfo=UTC)
        if init.month == 2:
            if init != carry_in:
                raise PermissionError('Only the frozen 2025-02-28T18:00 carry-in initialization')
        elif init.month not in planning.AUTHORIZABLE_MONTHS:
            raise PermissionError('2025 March..October identity only')
        if not isinstance(self.lead, timedelta) or self.lead != GFS_LEAD:
            raise ValueError('Frozen 2025 GFS lead is exactly six hours')
        if init.hour not in GFS_INIT_HOURS or init.minute or init.second:
            raise ValueError('GFS init must lie on 00/06/12/18 UTC')
        if init + self.lead != valid:
            raise ValueError('GFS init + lead must equal valid')
        object.__setattr__(self, 'init', init)
        object.__setattr__(self, 'valid', valid)


# ---------------------------------------------------------------------------
# Authorization objects
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class PayloadAuthorization2025:
    """Explicit payload-phase grant.  Constructing it never happens implicitly."""

    _value: dict
    fixture: bool

    @classmethod
    def load(cls, path, expected_sha256=None):
        payload = Path(path).read_bytes()
        digest = _sha_bytes(payload)
        if expected_sha256 is not None:
            expected = str(expected_sha256).lower()
            if not SHA256.fullmatch(expected):
                raise ValueError('Lowercase 64-hex expected authorization SHA required')
            if digest != expected:
                raise ValueError('Payload authorization SHA mismatch')
        return cls(json.loads(payload.decode('utf-8')), fixture=False)

    @classmethod
    def researcher(cls, value):
        """Researcher-authored JSON, exact keys; never grants catalogue work."""
        _exact_keys(value, _PAYLOAD_AUTH_KEYS, 'payload authorization')
        if value['version'] != VERSION or value['AUTHORIZED_BY'] != 'RESEARCHER':
            raise ValueError('Researcher-authored v1 payload authorization required')
        if value['scope'] != PAYLOAD_SCOPE:
            raise ValueError('Payload authorization scope mismatch')
        if value['FINAL_TEST_2025_PAYLOAD_AUTHORIZED'] is not True:
            raise PermissionError('Payload authorization not granted')
        if type(value['allow_october']) is not bool:
            raise ValueError('Boolean allow_october required')
        protocol = value['protocol']
        if not isinstance(protocol, dict) or tuple(sorted(protocol)) != ('path', 'sha256'):
            raise ValueError('Protocol binding must carry path and sha256')
        if not isinstance(protocol['path'], str) or not protocol['path']:
            raise ValueError('Protocol path required')
        sha = str(protocol['sha256']).lower()
        if not SHA256.fullmatch(sha):
            raise ValueError('Lowercase 64-hex protocol SHA required')
        catalogue_sha = str(value['catalogue_sha256']).lower()
        if not SHA256.fullmatch(catalogue_sha):
            raise ValueError('Lowercase 64-hex catalogue SHA required')
        roots = _validated_roots(value['roots'])
        created = _utc(value['created_utc'])
        payload = {
            'version': VERSION, 'AUTHORIZED_BY': 'RESEARCHER', 'scope': PAYLOAD_SCOPE,
            'FINAL_TEST_2025_PAYLOAD_AUTHORIZED': True,
            'protocol': {'path': protocol['path'], 'sha256': sha},
            'catalogue_sha256': catalogue_sha, 'roots': roots,
            'allow_october': value['allow_october'], 'created_utc': created.isoformat(),
        }
        return cls(payload, fixture=False)

    @classmethod
    def fixture_only(cls, root, *, created_utc=None):
        """Synthetic-fixture grant scoped to one caller-provided temporary root."""
        root_path = Path(root)
        if not root_path.is_absolute():
            raise ValueError('Absolute fixture root required')
        base = str(Path(root)).rstrip('\\/')
        defaults = {kind: str(planning.PathLayout2025.default().root(
            'gfs_main' if kind == 'gfs' else kind)).rstrip('\\/')
                    for kind in _ROOT_KINDS}
        lowered = base.lower()
        for kind, default in defaults.items():
            if lowered == default.lower() or lowered.startswith(default.lower() + '\\') or lowered.startswith(default.lower() + '/'):
                raise PermissionError('Fixture root may not sit inside a real payload root')
        roots = {kind: str(Path(base) / kind) for kind in _ROOT_KINDS}
        payload = {
            'version': VERSION, 'AUTHORIZED_BY': 'ENGINEERING_FIXTURE', 'scope': FIXTURE_SCOPE,
            'FINAL_TEST_2025_PAYLOAD_AUTHORIZED': False,
            'protocol': {'path': 'FIXTURE', 'sha256': '0' * 64},
            'catalogue_sha256': '0' * 64, 'roots': roots,
            'allow_october': False,
            'created_utc': _utc(created_utc or datetime.now(UTC).replace(second=0, microsecond=0)).isoformat(),
        }
        return cls(payload, fixture=True)

    @property
    def allow_october(self):
        return self._value['allow_october']

    @property
    def roots(self):
        return MappingProxyType(dict(self._value['roots']))

    def require_payload(self):
        if self.fixture:
            return True
        if self._value['FINAL_TEST_2025_PAYLOAD_AUTHORIZED'] is not True:
            raise PermissionError('2025 payload authorization missing')
        return True

    def as_dict(self):
        return dict(self._value, roots=dict(self._value['roots']))


_ROOT_KINDS = ('himawari', 'imerg', 'gfs', 'gfs_thermo')


def _validated_roots(value):
    if not isinstance(value, dict) or tuple(sorted(value)) != tuple(sorted(_ROOT_KINDS)):
        raise ValueError('Exact four frozen source roots required')
    result = {}
    for kind in _ROOT_KINDS:
        root = value[kind]
        if not isinstance(root, str) or not root.strip():
            raise ValueError('Explicit non-empty root required: ' + kind)
        path = Path(root)
        if not path.is_absolute() or path.drive.upper() not in ('H:', 'F:'):
            raise ValueError('Absolute H:/F: source root required: ' + kind)
        result[kind] = str(path)
    return result


# ---------------------------------------------------------------------------
# Default-deny access object
# ---------------------------------------------------------------------------


@dataclass
class PayloadAccess2025:
    """Resolve one explicitly named relative path under an authorized root."""

    authorization: PayloadAuthorization2025
    opened: int = 0
    bytes_read: int = 0
    sha256_read: tuple = ()
    events: tuple = ()

    def __post_init__(self):
        if not isinstance(self.authorization, PayloadAuthorization2025):
            raise PermissionError('Explicit PayloadAuthorization2025 required for 2025 payload access')
        self.authorization.require_payload()

    @classmethod
    def default(cls):
        """There is no ambient/default access; the default is deny."""
        raise PermissionError('2025 payload access requires an explicit payload authorization')

    def _relative_parts(self, relative_path):
        if not isinstance(relative_path, str) or not relative_path.strip():
            raise ValueError('Explicit relative path required')
        raw = Path(relative_path)
        if raw.is_absolute() or raw.drive:
            raise PermissionError('Absolute payload path forbidden')
        parts = raw.parts
        if not parts or any(part in ('', '.', '..') for part in parts):
            raise PermissionError('Traversal-free relative payload path required')
        for part in parts:
            if len(part) in (6, 8) and part.isdigit() and part.startswith('2025'):
                month = int(part[4:6])
                if month == 2:
                    if part not in ('202502', '20250228'):
                        raise PermissionError('Only the 2025-02-28 carry-in payload date is admissible')
                    if part == '202502' and (len(parts) < 2 or parts[1] != '28'):
                        raise PermissionError('Only the 2025-02-28 carry-in payload date is admissible')
                elif month not in planning.AUTHORIZABLE_MONTHS:
                    raise PermissionError('Payload month outside March..October 2025')
                elif month == 10 and not self.authorization.allow_october:
                    raise PermissionError('October 2025 payload requires explicit scope')
        for part in parts:
            if part.startswith('imerg_') and part.endswith('.nc'):
                date = part[len('imerg_'):-3]
                if len(date) != 8 or not date.isdigit():
                    raise PermissionError('Explicit imerg_YYYYMMDD.nc filename required')
                month = int(date[4:6])
                if month == 2:
                    if date != '20250228':
                        raise PermissionError('Only the 2025-02-28 carry-in payload date is admissible')
                elif month not in planning.AUTHORIZABLE_MONTHS:
                    raise PermissionError('Payload month outside March..October 2025')
                elif month == 10 and not self.authorization.allow_october:
                    raise PermissionError('October 2025 payload requires explicit scope')
        return parts

    def resolve(self, kind, relative_path):
        if kind not in _ROOT_KINDS:
            raise ValueError('Unknown source kind: ' + str(kind))
        parts = self._relative_parts(relative_path)
        root = Path(self.authorization.roots[kind])
        joined = Path(root).joinpath(*parts)
        normalized = Path(_lexical_normalize(str(joined)))
        root_text = _lexical_normalize(str(root))
        if normalized == Path(root_text):
            raise PermissionError('Payload path must name a file below the root')
        try:
            Path(str(normalized)).relative_to(root_text)
        except ValueError:
            raise PermissionError('Payload path escapes the authorized root') from None
        return normalized

    def read_bytes(self, kind, relative_path, *, max_bytes, expected_sha256=None,
                   expected_bytes=None):
        if type(max_bytes) is not int or max_bytes <= 0:
            raise ValueError('Positive byte cap required')
        path = self.resolve(kind, relative_path)
        before = path.stat()
        real = path.resolve(strict=True)
        if not _within(real, self.authorization.roots[kind]):
            raise PermissionError('Resolved payload path escapes the authorized root')
        if not 0 < before.st_size <= max_bytes:
            raise PermissionError('Payload file exceeds the bounded read cap')
        if expected_bytes is not None and before.st_size != expected_bytes:
            raise ValueError('Payload byte count differs from inventory')
        with real.open('rb') as stream:
            payload = stream.read(max_bytes + 1)
        after = real.stat()
        if len(payload) != before.st_size or len(payload) > max_bytes:
            raise PermissionError('Bounded read changed or exceeded the cap')
        if (before.st_size, before.st_mtime_ns, before.st_ino) != (after.st_size, after.st_mtime_ns, after.st_ino):
            raise IOError('Payload changed during bounded read')
        digest = _sha_bytes(payload)
        if expected_sha256 is not None:
            expected = str(expected_sha256).lower()
            if not SHA256.fullmatch(expected):
                raise ValueError('Lowercase 64-hex expected payload SHA required')
            if digest != expected:
                raise ValueError('Payload SHA differs from inventory')
        record = {'kind': kind, 'relative_path': relative_path, 'bytes': len(payload),
                  'sha256': digest}
        self.opened += 1
        self.bytes_read += len(payload)
        self.sha256_read = self.sha256_read + (digest,)
        self.events = self.events + (record,)
        return payload, record


# ---------------------------------------------------------------------------
# Frozen 2025 slot decoding
# ---------------------------------------------------------------------------


def _cf_time(var):
    from netCDF4 import num2date
    if var.size != 1:
        raise ValueError('One observation time per frame required')
    if getattr(var, 'calendar', 'standard') not in ('standard', 'gregorian', 'proleptic_gregorian'):
        raise ValueError('Unsupported CF calendar')
    value = np.asarray(var[...]).ravel()[0]
    if not np.isfinite(value):
        raise ValueError('Nonfinite CF time')
    converted = num2date(value, var.units, calendar=getattr(var, 'calendar', 'standard'),
                         only_use_cftime_datetimes=False)
    return datetime(converted.year, converted.month, converted.day, converted.hour,
                    converted.minute, converted.second, converted.microsecond, tzinfo=UTC)


def _axes_ok(lat, lon):
    lat, lon = np.asarray(lat), np.asarray(lon)
    return (lat.shape == (NATIVE_SHAPE[0],) and lon.shape == (NATIVE_SHAPE[1],)
            and np.isfinite(lat).all() and np.isfinite(lon).all()
            and bool(np.all(np.diff(lat) < 0)) and bool(np.all(np.diff(lon) > 0)))


def _expectation(expected, relative_path):
    if expected is None:
        return None, None
    item = expected.get(relative_path)
    if item is None:
        return None, None
    return item.get('sha256'), item.get('bytes')


# ---------------------------------------------------------------------------
# 2025 five-modality reader: one explicitly planned scene at a time
# ---------------------------------------------------------------------------


def read_satellite_scene(access, scene, *, expected=None, channels=CHANNELS,
                         max_file_bytes=MAX_SATELLITE_BYTES):
    """Decode six planned Himawari frames into [6, 7, 501, 501] float32 values."""
    from netCDF4 import Dataset

    if not isinstance(access, PayloadAccess2025):
        raise PermissionError('Explicit 2025 payload access required')
    planning.validate_scene(scene)
    analysis = planning.utc(scene['analysis_time'])
    frames, native, slot_values = [], None, []
    for slot, offset in enumerate(planning.SATELLITE_OFFSETS_MINUTES):
        nominal = planning.utc(scene[f'slot_{slot:02d}_nominal'])
        if nominal != analysis - timedelta(minutes=offset):
            raise ValueError(f'Slot {slot} nominal offset mismatch')
        relative_path = scene[f'slot_{slot:02d}_relative_path']
        sha, size = _expectation(expected, relative_path)
        raw, record = access.read_bytes('himawari', relative_path, max_bytes=max_file_bytes,
                                        expected_sha256=sha, expected_bytes=size)
        with Dataset('bounded_2025_himawari.nc', mode='r', memory=raw) as ds:
            ds.set_auto_maskandscale(False)
            lat, lon = np.asarray(ds['latitude'][:]), np.asarray(ds['longitude'][:])
            if not _axes_ok(lat, lon):
                raise ValueError('Frozen 501 descending-latitude grid required')
            if native is None:
                native = (lat.copy(), lon.copy())
            elif not (np.array_equal(native[0], lat) and np.array_equal(native[1], lon)):
                raise ValueError('Mixed native grids across the six slots')
            band_values, band_masks = [], []
            for channel in channels:
                name = 'tbb_' + channel[1:]
                if name not in ds.variables:
                    raise ValueError('Required band missing: ' + channel)
                var = ds[name]
                if var.dimensions != ('latitude', 'longitude') or var.shape != NATIVE_SHAPE or var.units != 'K':
                    raise ValueError('Band grid/units mismatch: ' + channel)
                values, mask = decode_b13(np.asarray(var[:]),
                                          {key: var.getncattr(key) for key in var.ncattrs()})
                band_values.append(values)
                band_masks.append(mask)
            obs_start, obs_end = _cf_time(ds['start_time']), _cf_time(ds['end_time'])
            created = str(getattr(ds, 'date_created', '')) or None
        if not (obs_start <= nominal <= obs_end):
            raise ValueError('Cached nominal time lies outside the observed frame')
        for observed in (obs_start, obs_end):
            if observed.year != planning.YEAR:
                raise PermissionError('Observed 2025 frame required')
        slot_values.append(np.stack(band_values))
        frames.append({'slot': slot, 'nominal': nominal.isoformat(),
                       'obs_start': obs_start.isoformat(), 'obs_end': obs_end.isoformat(),
                       'date_created': created, 'relative_path': relative_path,
                       'bytes': record['bytes'], 'sha256': record['sha256'],
                       'channels': list(channels),
                       'full_valid': bool(all(np.all(mask) for mask in band_masks))})
    values = np.stack(slot_values)  # [6, 7, 501, 501]
    if values.shape != (6, len(tuple(channels)), 501, 501) or values.dtype != np.float32:
        raise ValueError('Decoded satellite tensor shape/dtype mismatch')
    return {'values': values, 'frames': tuple(frames), 'records': tuple(frames),
            'native_lat': native[0], 'native_lon': native[1]}


def variable_requests():
    """The frozen MEE v1.3 binding (11 main + 6 thermo fields, no new fields)."""
    from yuntapr.experimental.core_innovation.gfs import VariableRequest
    main = tuple(
        VariableRequest(q + str(level), q, name, level * 100.)
        for level in (850, 700)
        for q, name in (('u', 'u-component_of_wind_isobaric'),
                        ('v', 'v-component_of_wind_isobaric'))
    ) + (
        VariableRequest('ps', 'surface_pressure', 'Pressure_surface'),
        VariableRequest('pwat', 'precipitable_water',
                        'Precipitable_water_entire_atmosphere_single_layer'),
        VariableRequest('cape', 'cape', 'Convective_available_potential_energy_surface'),
    )
    thermo = tuple(
        VariableRequest(q + str(level), q, name, level * 100.)
        for level in (850, 700, 500)
        for q, name in (('temperature', 'Temperature_isobaric'),
                        ('relative_humidity', 'Relative_humidity_isobaric'))
    )
    return main, thermo


def decode_gfs_2025(raw, identity, requests, *, max_cells=65536):
    """Bounded 2025 sibling of ``gfs.decode_gfs_bytes`` (old guard untouched)."""
    from netCDF4 import Dataset
    if not isinstance(identity, ForecastIdentity2025):
        raise TypeError('Validated ForecastIdentity2025 required')
    if not isinstance(raw, bytes) or not 0 < len(raw) <= 8 * 1024 ** 2 or not 0 < max_cells <= 65536:
        raise ValueError('Bounded in-memory forecast required')
    if not requests or len({request.key for request in requests}) != len(requests):
        raise ValueError('Unique explicit variable requests required')
    fields, caveats = {}, {}
    with Dataset('bounded_2025_forecast.nc', mode='r', memory=raw) as ds:
        ds.set_auto_maskandscale(False)
        lat = gfs._one(ds, ('latitude', 'lat'))
        lon = gfs._one(ds, ('longitude', 'lon'))
        if lat.ndim != 1 or lon.ndim != 1 or lat.size * lon.size > max_cells:
            raise ValueError('Bounded rectilinear grid required')
        if lat.units not in ('degrees_north', 'degree_north') or lon.units not in ('degrees_east', 'degree_east'):
            raise ValueError('Geographic coordinate units required')
        grid = gfs.GridSpec(lat[:], lon[:])
        if gfs._cf_time(gfs._one(ds, ('forecast_reference_time', 'reftime', 'reference_time'))) != identity.init:
            raise ValueError('Primary CF forecast init mismatch')
        if gfs._cf_time(gfs._one(ds, ('valid_time', 'time'))) != identity.valid:
            raise ValueError('Primary CF valid time mismatch')
        for name, expected in (('initialization_time_utc', identity.init), ('valid_time_utc', identity.valid)):
            if name in ds.ncattrs() and gfs.parse_utc(ds.getncattr(name)) != expected:
                raise ValueError('Global/CF forecast time conflict')
        for name in ('forecast_hour', 'lead_time_hours'):
            if name in ds.ncattrs() and float(ds.getncattr(name)) * 3600 != identity.lead.total_seconds():
                raise ValueError('Global/CF lead conflict')
        pressure = gfs._one(ds, ('pressure_level', 'isobaric')) if any(r.level_pa is not None for r in requests) else None
        levels = gfs.pressure_pa(pressure[:], pressure.units) if pressure is not None else None
        if levels is not None and (levels.ndim != 1 or not np.isfinite(levels).all()
                                   or (levels <= 0).any() or len(np.unique(levels)) != len(levels)):
            raise ValueError('Unique positive finite pressure coordinate required')
        for request in requests:
            if request.variable not in ds.variables:
                raise ValueError('Requested field missing: ' + request.key)
            var = ds.variables[request.variable]
            index, remaining = [], []
            if request.quantity == 'specific_humidity' and var.dimensions.count(pressure.dimensions[0]) != 1:
                raise ValueError('Specific humidity requires one explicit pressure axis')
            for dim in var.dimensions:
                if dim == lat.dimensions[0] or dim == lon.dimensions[0]:
                    index.append(slice(None))
                    remaining.append(dim)
                elif pressure is not None and dim == pressure.dimensions[0] and request.level_pa is not None:
                    found = np.flatnonzero(levels == request.level_pa)
                    if len(found) != 1:
                        raise ValueError('Exact requested pressure level unavailable')
                    index.append(int(found[0]))
                elif dim in ('valid_time', 'time') and len(ds.dimensions[dim]) == 1:
                    index.append(0)
                else:
                    raise ValueError('Unapproved variable dimensions or vertical level type')
            if remaining != [lat.dimensions[0], lon.dimensions[0]]:
                raise ValueError('Explicit row=latitude col=longitude layout required')
            attrs = {name: var.getncattr(name) for name in var.ncattrs()}
            values, valid = gfs.decode_packed(var[tuple(index)], attrs)
            if values.shape != grid.shape:
                raise ValueError('Variable grid differs from coordinates')
            values, unit = gfs._convert(values, str(attrs.get('units', '')), request.quantity)
            if request.quantity == 'specific_humidity' and np.any((values[valid] < 0) | (values[valid] >= 1)):
                raise ValueError('Valid specific humidity must lie in [0, 1) kg kg-1')
            fields[request.key] = gfs.Field(values, valid, request.quantity, unit, request.level_pa)
        for name in ('conservative_available_time_utc', 'availability_note', 'history', 'legacy_history_before_20260925'):
            if name in ds.ncattrs():
                caveats[name] = str(ds.getncattr(name))
        valid_var = gfs._one(ds, ('valid_time', 'time'))
        if 'udunits' in valid_var.ncattrs():
            caveats['auxiliary_udunits'] = str(valid_var.udunits)
    return gfs.GFSFile(identity, grid, fields, {
        'input_sha256': hashlib.sha256(raw).hexdigest(), 'file_bytes_read': len(raw),
        'historical_availability': 'NOT_ESTABLISHED',
        'source_lineage': 'SUPPORTED_WITH_CAVEATS', 'legacy_metadata': caveats})


def read_gfs_environment(access, scene, *, expected=None, max_file_bytes=MAX_GFS_BYTES):
    """Decode main+thermo f006 and obey the frozen retrospective combine rules."""
    if not isinstance(access, PayloadAccess2025):
        raise PermissionError('Explicit 2025 payload access required')
    planning.validate_scene(scene)
    identity = ForecastIdentity2025(init=planning.utc(scene['gfs_init']), lead=GFS_LEAD,
                                    valid=planning.utc(scene['analysis_time']))
    main_requests, thermo_requests = variable_requests()
    files, records = {}, []
    for kind, access_kind, relative_path, requests in (
            ('gfs_main', 'gfs', scene['gfs_main_relative_path'], main_requests),
            ('gfs_thermo', 'gfs_thermo', scene['gfs_thermo_relative_path'], thermo_requests)):
        name = Path(relative_path).name
        match = re.fullmatch(r'gfs_(?:thermo_)?0p25_(\d{10})_f(\d{3})\.nc', name)
        if not match:
            raise PermissionError('Only explicit authorized forecast filenames')
        filename_init = datetime.strptime(match.group(1), '%Y%m%d%H').replace(tzinfo=UTC)
        if filename_init != identity.init or timedelta(hours=int(match.group(2))) != identity.lead:
            raise ValueError('Filename and requested forecast identity differ')
        sha, size = _expectation(expected, relative_path)
        raw, record = access.read_bytes(access_kind, relative_path, max_bytes=max_file_bytes,
                                        expected_sha256=sha, expected_bytes=size)
        files[kind] = decode_gfs_2025(raw, identity, requests)
        records.append(dict(record, init=identity.init.isoformat(),
                            valid=identity.valid.isoformat()))
    environment = gfs.combine_environment(files['gfs_main'], files['gfs_thermo'],
                                          target_valid_time=identity.valid,
                                          decision_time=identity.valid,
                                          mode='retrospective')
    return {'environment': environment, 'identity': identity, 'records': tuple(records)}


def _index_time(var, index):
    from netCDF4 import num2date
    if not 0 <= index < var.size:
        raise ValueError('IMERG half-hour index outside the day file')
    converted = num2date(var[index], var.units, calendar=getattr(var, 'calendar', 'standard'),
                         only_use_cftime_datetimes=False)
    return datetime(converted.year, converted.month, converted.day, converted.hour,
                    converted.minute, converted.second, converted.microsecond, tzinfo=UTC)


def read_imerg_scene(access, scene, *, expected=None, max_file_bytes=MAX_IMERG_BYTES):
    """Decode the frozen 100x100 Yunnan target window for one planned scene."""
    from netCDF4 import Dataset
    if not isinstance(access, PayloadAccess2025):
        raise PermissionError('Explicit 2025 payload access required')
    planning.validate_scene(scene)
    window_start = planning.utc(scene['window_start'])
    index = scene['imerg_index']
    relative_path = scene['imerg_day_relative_path']
    sha, size = _expectation(expected, relative_path)
    raw, record = access.read_bytes('imerg', relative_path, max_bytes=max_file_bytes,
                                    expected_sha256=sha, expected_bytes=size)
    with Dataset('bounded_2025_imerg.nc', mode='r', memory=raw) as ds:
        ds.set_auto_maskandscale(False)
        attrs = {name: ds.getncattr(name) for name in ds.ncattrs()}
        if attrs.get('source') != IMERG_PRODUCT or 'IMERG Final Run V07' not in str(attrs.get('title', '')):
            raise ValueError('IMERG source metadata does not establish V07 Final')
        variable = ds['precipitation']
        if variable.dimensions != ('time', 'lat', 'lon') or variable.shape != IMERG_SHAPE or variable.units != 'mm hr-1':
            raise ValueError('IMERG converted dimension/shape/units mismatch')
        if not 0 <= index < IMERG_SHAPE[0]:
            raise ValueError('IMERG half-hour index outside the day file')
        observed = _index_time(ds['time'], index)
        if observed != window_start:
            raise ValueError('IMERG observed half-hour differs from the planned window')
        lat, lon = np.asarray(ds['lat'][:]), np.asarray(ds['lon'][:])
        if lat.shape != (130,) or lon.shape != (140,):
            raise ValueError('IMERG converted coordinates mismatch')
        crop = np.asarray(variable[index, 10:110, 20:120])
        values, valid = decode_imerg(crop, {name: variable.getncattr(name) for name in variable.ncattrs()})
        run_type = str(attrs.get('run_type', IMERG_RUN_TYPE)) or IMERG_RUN_TYPE
        version = str(attrs.get('version', IMERG_VERSION)) or IMERG_VERSION
    if values.shape != (100, 100) or valid.shape != (100, 100):
        raise ValueError('Frozen 100x100 target window required')
    return {'rate': values.astype(np.float64), 'valid': valid,
            'target_lat': lat[10:110].copy(), 'target_lon': lon[20:120].copy(),
            'record': dict(record, window_start=window_start.isoformat(),
                           index=index, product=IMERG_PRODUCT, version=version,
                           run_type=run_type),
            'product': IMERG_PRODUCT, 'version': version, 'run_type': run_type}


def read_scene_payload(access, scene, *, expected=None):
    """One complete planned scene: six satellite frames, environment and target."""
    if not isinstance(access, PayloadAccess2025):
        raise PermissionError('Explicit 2025 payload access required')
    planning.validate_scene(scene)
    expected = expected or {}
    satellite = read_satellite_scene(access, scene, expected=expected)
    environment = read_gfs_environment(access, scene, expected=expected)
    imerg = read_imerg_scene(access, scene, expected=expected)
    return {'scene': dict(scene), 'satellite': satellite, 'environment': environment,
            'target': imerg, 'read_events': tuple(access.events)}


def _utc2025(value, *, allow_carry_in=False):
    """Timezone-aware UTC datetime strictly inside the authorized 2025 payload grid.

    The frozen window starts at 2025-02-28T23:30Z, so the six 2025-03-01T00:00Z
    satellite frames and the GFS 2025-02-28T18:00Z initialization legitimately
    carry in from February 28.  Only that single day is allowed; analysis times
    themselves must lie in March..October.
    """
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ValueError('Timezone-aware observed/analysis datetime required')
    value = value.astimezone(UTC)
    if value.year != planning.YEAR:
        raise PermissionError('This adapter is authorized for 2025 payload times only')
    if value.month == 2:
        if not (allow_carry_in and value.day == 28):
            raise PermissionError('Only the 2025-02-28 carry-in payload is allowed')
    elif value.month not in planning.AUTHORIZABLE_MONTHS:
        raise PermissionError('2025 payload times must lie in March..October')
    return value


def _channels2025(names):
    result = tuple(names)
    allowed = {f'B{i:02d}' for i in range(7, 17)}
    if not result or len(set(result)) != len(result) or any(name not in allowed for name in result):
        raise ValueError('Unique explicit Kelvin thermal Himawari channels B07..B16 required')
    return result


def prepare_multispectral_2025(values, source_valid, *, source_channels, selected_channels,
                               units, normalization, nominal_times, obs_start_times,
                               obs_end_times, analysis_times,
                               expected_offsets_before_analysis_minutes,
                               source_grid, expected_grid, missing_policy):
    """2025 copy of ``multispectral.prepare_multispectral`` with an explicit 2025 gate.

    The frozen 2023/2024 helper keeps its own year guard.  This function is only
    reachable through the deny-by-default 2025 adapter path and reuses the frozen
    ``TrainNormalization`` statistics without refitting anything.
    """
    channels, selected = _channels2025(source_channels), _channels2025(selected_channels)
    if any(channel not in channels for channel in selected):
        raise ValueError('Required channel unavailable; no substitution')
    if not isinstance(source_grid, GridSpec) or not isinstance(expected_grid, GridSpec):
        raise TypeError('Explicit source and expected coordinate grids required')
    expected_grid.assert_same(source_grid)
    if source_grid.lat[0] <= source_grid.lat[-1] or source_grid.lon[0] >= source_grid.lon[-1]:
        raise ValueError('Frozen Himawari native row axis must descend north-to-south; longitude ascend')
    x, valid = np.asarray(values), np.asarray(source_valid)
    if x.ndim != 5 or any(size <= 0 for size in x.shape) or x.dtype.kind != 'f':
        raise ValueError('Decoded floating values [B,T,C,H,W] required')
    if valid.dtype != bool or valid.shape != x.shape:
        raise ValueError('Independent bool validity mask must have identical [B,T,C,H,W] shape')
    if x.shape[2] != len(channels) or x.shape[-2:] != source_grid.shape:
        raise ValueError('Channel/spatial shape does not match explicit metadata')
    offsets = tuple(expected_offsets_before_analysis_minutes)
    if len(offsets) != x.shape[1] or any(type(offset) is not int or offset < 0 for offset in offsets):
        raise ValueError('One explicit nonnegative integer nominal offset required for every time slot')
    if any(a <= b for a, b in zip(offsets, offsets[1:])):
        raise ValueError('Expected offsets must descend strictly: oldest-to-latest time slots')
    if missing_policy not in ('reject', 'masked_neutral'):
        raise ValueError('Explicit missing_policy reject or masked_neutral required')
    if len(analysis_times) != x.shape[0] or any(
            len(times) != x.shape[0] for times in (nominal_times, obs_start_times, obs_end_times)):
        raise ValueError('Temporal metadata batch size mismatch')
    for batch in range(x.shape[0]):
        analysis = _utc2025(analysis_times[batch])
        if any(len(times[batch]) != x.shape[1] for times in (nominal_times, obs_start_times, obs_end_times)):
            raise ValueError('Every declared history frame needs nominal/start/end metadata')
        previous_end = None
        for slot, offset in enumerate(offsets):
            nominal = _utc2025(nominal_times[batch][slot], allow_carry_in=True)
            start, end = (_utc2025(obs_start_times[batch][slot], allow_carry_in=True),
                          _utc2025(obs_end_times[batch][slot], allow_carry_in=True))
            if nominal != analysis - timedelta(minutes=offset):
                raise ValueError('Nominal history does not match explicit offsets; no reorder or fallback')
            if start > end or end > analysis or (previous_end is not None and end <= previous_end):
                raise ValueError('Actual observation intervals must be ordered and completed by analysis time')
            previous_end = end
    indices = [channels.index(channel) for channel in selected]
    x, valid = x[:, :, indices, :, :], valid[:, :, indices, :, :].copy()
    if not np.all(np.isfinite(x) | ~valid):
        raise ValueError('Nonfinite observation marked valid; propagate missing mask explicitly')
    if missing_policy == 'reject' and not valid.all():
        raise ValueError('Required channel/frame has missing pixels under reject policy')
    normalized = np.zeros(x.shape, dtype=np.float32)
    for index, channel in enumerate(selected):
        stats = normalization.get(channel)
        if not isinstance(stats, TrainNormalization) or stats.channel != channel or units.get(channel) != stats.unit:
            raise ValueError('Every selected channel needs matching explicit Kelvin Train statistics')
        safe = np.where(valid[:, :, index], x[:, :, index], stats.mean)
        transformed = (safe.astype(np.float64) - stats.mean) / stats.std
        with np.errstate(over='ignore', invalid='ignore'):
            normalized[:, :, index] = transformed.astype(np.float32)
    if not np.isfinite(normalized).all():
        raise FloatingPointError('Nonfinite normalized multispectral tensor')
    return MultispectralBatch(normalized, valid, selected, offsets, source_grid, missing_policy)


__all__ = [
    'CHANNELS', 'ForecastIdentity2025', 'PayloadAccess2025', 'PayloadAuthorization2025',
    'FIXTURE_SCOPE', 'IMERG_PRODUCT', 'IMERG_VERSION', 'PAYLOAD_SCOPE',
    'decode_gfs_2025', 'prepare_multispectral_2025', 'read_gfs_environment',
    'read_imerg_scene', 'read_satellite_scene', 'read_scene_payload', 'variable_requests',
]
