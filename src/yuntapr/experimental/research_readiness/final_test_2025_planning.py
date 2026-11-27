"""Pure 2025 final-test scene planning: fixed clock, fixed relative layout, no I/O.

This module is the replacement for the 2023/2024-only ``stage3.planning``
helpers.  The old helpers keep rejecting anything outside 2023/2024; nothing
here weakens them.  This module only *plans* rows.  It never opens, stats or
lists a 2025 payload path.  Whether an inventory actually contains the planned
files is decided later by the catalogue stage from a caller-supplied inventory.

Frozen clock choice for B4/B7/B8/B7_ZERO_DOTE final test
------------------------------------------------------
Four analyses per UTC day at 00/06/12/18 because the inherited retrospective
GFS reader binds ``init = analysis - 6h`` with a fixed f006 lead.  The IMERG
target begins at ``window_start = analysis - 30min`` (the half-hour target
window immediately before the analysis token) and the six Himawari slots are
nominal at analysis-60 ... analysis-10 minutes, matching the inherited
``stage2.OFFSETS``.  Therefore ``sample_id == window_start`` and every window
start lies on :30 minutes (the last half-hour of the six hours before the
analysis).  This differs from the B0 30-minute window cadence only because
B0 does not consume GFS; protocol draft must state the difference explicitly.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
import hashlib
import json
import re

YEAR = 2025
UTC = timezone.utc
DEFAULT_MONTHS = tuple(range(3, 10))
AUTHORIZABLE_MONTHS = tuple(range(3, 11))
ANALYSIS_HOURS = (0, 6, 12, 18)
SATELLITE_OFFSETS_MINUTES = (60, 50, 40, 30, 20, 10)
CHANNELS = ('B08', 'B09', 'B10', 'B11', 'B13', 'B15', 'B16')
GFS_INIT_LAG_HOURS = 6
GFS_LEAD_HOURS = 6
TARGET_WINDOW_MINUTES = 30

# File-name templates.  The default Himawari template (H09 / R21) is the pattern
# evidenced by the frozen 2023/2024 relative paths, not by any 2025 directory.
# The task brief mentioned H08/R02; both are configurable and neither has been
# confirmed for 2025 payloads.  This is an open question in the draft protocol.
HIMAWARI_TEMPLATE = 'NC_H09_YYYYMMDD_HHMM_R21_FLDK.06001_06001.nc'
HIMAWARI_ALTERNATE_TEMPLATE = 'NC_H08_YYYYMMDD_HHMM_R02_FLDK.06001_06001.nc'
IMERG_TEMPLATE = 'imerg_YYYYMMDD.nc'
GFS_MAIN_TEMPLATE = 'gfs_0p25_YYYYMMDDHH_f006.nc'
GFS_THERMO_TEMPLATE = 'gfs_thermo_0p25_YYYYMMDDHH_f006.nc'

HIMAWARI_ROOT = r'H:\葵花202303_202510'
IMERG_ROOT = r'F:\云南极端降水数据\raw\IMERG'
GFS_ROOT = r'F:\云南极端降水数据\raw\GFS'
GFS_THERMO_ROOT = r'F:\云南极端降水数据\raw\GFS_THERMO'

_SHA = re.compile(r'[0-9a-f]{64}')

_SCENE_KEYS = (
    'candidate_index', 'sample_id', 'window_start', 'analysis_time', 'month',
    'slot_00_nominal', 'slot_01_nominal', 'slot_02_nominal', 'slot_03_nominal',
    'slot_04_nominal', 'slot_05_nominal',
    'slot_00_relative_path', 'slot_01_relative_path', 'slot_02_relative_path',
    'slot_03_relative_path', 'slot_04_relative_path', 'slot_05_relative_path',
    'gfs_init', 'gfs_main_relative_path', 'gfs_thermo_relative_path',
    'imerg_day_relative_path', 'imerg_index',
)


def parse_utc(value):
    """Parse a timezone-aware ISO string (or pass a datetime through)."""
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, str):
        parsed = datetime.fromisoformat(value)
    else:
        raise TypeError('UTC timestamp required')
    if parsed.tzinfo is None:
        raise ValueError('Timezone-aware UTC timestamp required')
    return parsed.astimezone(UTC)


def utc(value):
    parsed = parse_utc(value)
    if parsed.microsecond or parsed.second:
        raise ValueError('Whole-minute 2025 final-test clock required')
    return parsed


_TOKEN = re.compile(r'YYYYMMDD|HHMM|YYYY|MM|DD|HH')
_TOKEN_VALUES = ('YYYYMMDD', 'HHMM', 'YYYY', 'MM', 'DD', 'HH')


def render_template(template, when):
    """Single longest-token-first substitution (HHMM is minutes, not month)."""
    if not isinstance(template, str) or not template:
        raise ValueError('Non-empty file template required')
    values = {'YYYYMMDD': when.strftime('%Y%m%d'), 'HHMM': when.strftime('%H%M'),
              'YYYY': when.strftime('%Y'), 'MM': when.strftime('%m'),
              'DD': when.strftime('%d'), 'HH': when.strftime('%H')}
    text = _TOKEN.sub(lambda match: values[match.group(0)], template)
    leftover = [token for token in _TOKEN_VALUES if token in text]
    if leftover:
        raise ValueError('Unresolved template token: ' + ', '.join(leftover))
    return text


def render_relpath(layout, kind, when):
    """Render one relative payload path from the frozen layout templates."""
    when = utc(when)
    if kind == 'himawari':
        return '/'.join((when.strftime('%Y%m'), when.strftime('%d'),
                         render_template(layout.himawari_template, when)))
    if kind == 'imerg':
        return '/'.join((when.strftime('%Y'), render_template(layout.imerg_template, when)))
    if kind in ('gfs_main', 'gfs_thermo'):
        template = layout.gfs_main_template if kind == 'gfs_main' else layout.gfs_thermo_template
        return '/'.join((when.strftime('%Y'), when.strftime('%Y%m%d'),
                         render_template(template, when)))
    raise ValueError('Unknown payload kind: ' + str(kind))


@dataclass(frozen=True)
class PathLayout2025:
    """Relative 2025 layout; roots are kept separate and configurable.

    Defaults reproduce the *2023/2024 frozen evidence* directory layout:
    Himawari ``YYYYMM/DD/NC_H09_..._R21....nc``, IMERG ``YYYY/imerg_YYYYMMDD.nc``
    and GFS ``YYYY/YYYYMMDD/gfs[_thermo]_0p25_YYYYMMDDHH_f006.nc``.  No 2025
    directory was inspected to build these defaults.
    """
    himawari_root: str = HIMAWARI_ROOT
    imerg_root: str = IMERG_ROOT
    gfs_root: str = GFS_ROOT
    gfs_thermo_root: str = GFS_THERMO_ROOT
    himawari_template: str = HIMAWARI_TEMPLATE
    imerg_template: str = IMERG_TEMPLATE
    gfs_main_template: str = GFS_MAIN_TEMPLATE
    gfs_thermo_template: str = GFS_THERMO_TEMPLATE

    def __post_init__(self):
        for name in ('himawari_template', 'imerg_template', 'gfs_main_template', 'gfs_thermo_template'):
            value = getattr(self, name)
            if not isinstance(value, str) or not value or '/' in value or '\\' in value:
                raise ValueError('Flat file template required: ' + name)
        for name in ('himawari_root', 'imerg_root', 'gfs_root', 'gfs_thermo_root'):
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip():
                raise ValueError('Explicit root path required: ' + name)
        if self.himawari_template == self.gfs_main_template:
            raise ValueError('Distinct modality templates required')

    @classmethod
    def default(cls):
        return cls()

    def root(self, kind):
        return Path({'himawari': self.himawari_root, 'imerg': self.imerg_root,
                     'gfs_main': self.gfs_root, 'gfs_thermo': self.gfs_thermo_root}[kind])

    def as_dict(self):
        return dict(himawari_root=self.himawari_root, imerg_root=self.imerg_root,
                    gfs_root=self.gfs_root, gfs_thermo_root=self.gfs_thermo_root,
                    himawari_template=self.himawari_template, imerg_template=self.imerg_template,
                    gfs_main_template=self.gfs_main_template,
                    gfs_thermo_template=self.gfs_thermo_template)


@dataclass(frozen=True)
class SatelliteFrame:
    channel: str
    nominal: datetime
    relative_path: str

    def as_dict(self):
        return dict(channel=self.channel, nominal=self.nominal.isoformat(),
                    relative_path=self.relative_path)


@dataclass(frozen=True)
class ScenePlan:
    candidate_index: int
    sample_id: str
    window_start: datetime
    analysis_time: datetime
    satellites: tuple
    gfs_init: datetime
    gfs_main_relative_path: str
    gfs_thermo_relative_path: str
    imerg_day_relative_path: str
    imerg_index: int

    @property
    def month(self):
        return self.analysis_time.month

    def as_dict(self):
        if len(self.satellites) != 6:
            raise ValueError('Six satellite frames required')
        row = dict(candidate_index=self.candidate_index, sample_id=self.sample_id,
                   window_start=self.window_start.isoformat(),
                   analysis_time=self.analysis_time.isoformat(), month=self.month,
                   gfs_init=self.gfs_init.isoformat(),
                   gfs_main_relative_path=self.gfs_main_relative_path,
                   gfs_thermo_relative_path=self.gfs_thermo_relative_path,
                   imerg_day_relative_path=self.imerg_day_relative_path,
                   imerg_index=self.imerg_index)
        for slot, frame in enumerate(self.satellites):
            row[f'slot_{slot:02d}_nominal'] = frame.nominal.isoformat()
            row[f'slot_{slot:02d}_relative_path'] = frame.relative_path
        missing = [key for key in _SCENE_KEYS if key not in row]
        if missing:
            raise ValueError('Scene schema missing: ' + str(missing))
        return {key: row[key] for key in _SCENE_KEYS}


def canonical_sha(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':')).encode('utf-8')).hexdigest()


def expected_slot_count(months=DEFAULT_MONTHS, *, year=YEAR):
    """Exact four-per-day slot count for whole UTC months (no 2025 I/O)."""
    months = tuple(months)
    if not months or any(m not in AUTHORIZABLE_MONTHS for m in months):
        raise ValueError('Months must lie in March..October')
    days = 0
    for month in months:
        first = datetime(year, month, 1, tzinfo=UTC)
        following = datetime(year + (month == 12), 1 if month == 12 else month + 1, 1, tzinfo=UTC)
        days += (following - first).days
    return days * len(ANALYSIS_HOURS)


def _bound(value, default, *, label):
    if value is None:
        return default
    parsed = utc(value)
    if parsed.year != YEAR:
        raise PermissionError('2025 final-test clock only')
    return parsed


def enumerate_scenes(layout=None, *, months=DEFAULT_MONTHS, allow_october=False,
                     analysis_start=None, analysis_end=None):
    """Return the frozen analysis-slot scene plans, purely in memory.

    ``allow_october=False`` rejects month 10 before any enumeration.  When it is
    true (only after a separate explicit scope decision) October slots are
    included but the caller must still produce a real authorization object
    before any catalogue/payload work.
    """
    if layout is None:
        layout = PathLayout2025.default()
    if not isinstance(layout, PathLayout2025):
        raise TypeError('PathLayout2025 required')
    months = tuple(months)
    if not months or tuple(sorted(set(months))) != months:
        raise ValueError('Strictly ordered unique months required')
    if any(month not in AUTHORIZABLE_MONTHS for month in months):
        raise ValueError('Months must lie in March..October')
    if 10 in months and not allow_october:
        raise PermissionError('October 2025 is outside the default frozen scope')

    first_day = datetime(YEAR, min(months), 1, tzinfo=UTC)
    last_month = max(months)
    month_end = datetime(YEAR + (last_month == 12), 1 if last_month == 12 else last_month + 1, 1, tzinfo=UTC)
    start = _bound(analysis_start, first_day, label='analysis_start')
    end = _bound(analysis_end, month_end, label='analysis_end')
    if start >= end:
        raise ValueError('Non-empty analysis interval required')
    if start.minute or start.second or start.microsecond or end.minute or end.second or end.microsecond:
        raise ValueError('Analysis bounds must be whole hours')
    if start.hour not in ANALYSIS_HOURS or end.hour not in ANALYSIS_HOURS:
        raise ValueError('Analysis bounds must lie on the frozen 00/06/12/18 grid')
    if start.month < min(months) or (end - timedelta(microseconds=1)).month > max(months):
        raise ValueError('Analysis interval exceeds the declared month scope')

    rows = []
    index = 0
    day = start
    while day < end:
        if day.month not in months:
            day += timedelta(days=1)
            continue
        for hour in ANALYSIS_HOURS:
            analysis = day.replace(hour=hour)
            if not start <= analysis < end:
                continue
            window_start = analysis - timedelta(minutes=TARGET_WINDOW_MINUTES)
            init = analysis - timedelta(hours=GFS_INIT_LAG_HOURS)
            satellites = []
            for channel, offset in zip(CHANNELS[:6], SATELLITE_OFFSETS_MINUTES):
                nominal = analysis - timedelta(minutes=offset)
                satellites.append(SatelliteFrame(channel, nominal,
                                                 render_relpath(layout, 'himawari', nominal)))
            rows.append(ScenePlan(
                candidate_index=index, sample_id=window_start.isoformat(),
                window_start=window_start, analysis_time=analysis,
                satellites=tuple(satellites), gfs_init=init,
                gfs_main_relative_path=render_relpath(layout, 'gfs_main', init),
                gfs_thermo_relative_path=render_relpath(layout, 'gfs_thermo', init),
                imerg_day_relative_path=render_relpath(layout, 'imerg', window_start),
                imerg_index=window_start.hour * 2 + window_start.minute // 30))
            index += 1
        day += timedelta(days=1)
    if len(rows) != expected_slot_count(months, year=YEAR):
        # Only exact whole-month intervals are representable without ambiguity.
        whole = (start == first_day and end == month_end)
        if whole:
            raise ValueError('Frozen slot count mismatch')
    return tuple(rows)


def validate_scene(row, layout=None, *, allow_october=False):
    """Validate one flat scene row without any filesystem access."""
    if layout is None:
        layout = PathLayout2025.default()
    if not isinstance(row, dict) or tuple(row) != _SCENE_KEYS:
        missing = None if not isinstance(row, dict) else [k for k in _SCENE_KEYS if k not in row]
        extra = None if not isinstance(row, dict) else [k for k in row if k not in _SCENE_KEYS]
        raise ValueError(f'Exact scene schema required (missing={missing}, extra={extra})')
    if type(row['candidate_index']) is not int or row['candidate_index'] < 0:
        raise ValueError('Non-negative integer candidate_index required')
    sample_id = utc(row['sample_id']); window = utc(row['window_start']); analysis = utc(row['analysis_time'])
    if sample_id != window or window != analysis - timedelta(minutes=TARGET_WINDOW_MINUTES):
        raise ValueError('sample_id/window_start/analysis clock mismatch')
    if window.year != YEAR or analysis.year != YEAR:
        raise PermissionError('2025 final-test clock only')
    if analysis.hour not in ANALYSIS_HOURS or analysis.minute or analysis.second:
        raise ValueError('Analysis must lie on 00/06/12/18 UTC')
    if window.minute != 30:
        raise ValueError('Window start must lie on the :30 half-hour grid')
    if analysis.month not in AUTHORIZABLE_MONTHS:
        raise PermissionError('2025 month outside March..October')
    if analysis.month == 10 and not allow_october:
        raise PermissionError('October 2025 is outside the default frozen scope')
    if row['month'] != analysis.month:
        raise ValueError('Month token mismatch')
    expected_init = analysis - timedelta(hours=GFS_INIT_LAG_HOURS)
    if utc(row['gfs_init']) != expected_init:
        raise ValueError('GFS init must be analysis-6h')
    if row['gfs_main_relative_path'] != render_relpath(layout, 'gfs_main', expected_init):
        raise ValueError('GFS main relative path differs from frozen template')
    if row['gfs_thermo_relative_path'] != render_relpath(layout, 'gfs_thermo', expected_init):
        raise ValueError('GFS thermo relative path differs from frozen template')
    window = window.astimezone(UTC)
    if row['imerg_day_relative_path'] != render_relpath(layout, 'imerg', window):
        raise ValueError('IMERG relative path differs from frozen template')
    if row['imerg_index'] != window.hour * 2 + window.minute // 30:
        raise ValueError('IMERG half-hour index mismatch')
    for slot, offset in enumerate(SATELLITE_OFFSETS_MINUTES):
        nominal = utc(row[f'slot_{slot:02d}_nominal'])
        if nominal != analysis - timedelta(minutes=offset):
            raise ValueError(f'Slot {slot} nominal offset mismatch')
        expected = render_relpath(layout, 'himawari', nominal)
        if row[f'slot_{slot:02d}_relative_path'] != expected:
            raise ValueError(f'Slot {slot} relative path differs from frozen template')
    return True


def scene_digest(row):
    validate_scene(row, allow_october=True)
    return canonical_sha({key: row[key] for key in _SCENE_KEYS})


def scope_manifest(*, months=DEFAULT_MONTHS, allow_october=False):
    months = tuple(months)
    if 10 in months and not allow_october:
        raise PermissionError('October 2025 is outside the default frozen scope')
    return dict(year=YEAR, months=list(months), analysis_hours_utc=list(ANALYSIS_HOURS),
                satellite_offsets_minutes=list(SATELLITE_OFFSETS_MINUTES),
                channels=list(CHANNELS), window_minutes=TARGET_WINDOW_MINUTES,
                gfs_init_lag_hours=GFS_INIT_LAG_HOURS, gfs_lead_hours=GFS_LEAD_HOURS,
                october_authorized=bool(allow_october),
                expected_candidate_slots=expected_slot_count(months, year=YEAR),
                clock_convention='sample_id=window_start=analysis-30min; analysis on 00/06/12/18 UTC')


def synthetic_layout(root):
    """Fixture layout under a caller-supplied temporary root (never a source root)."""
    root = Path(root)
    if not root.is_absolute():
        raise ValueError('Absolute synthetic root required')
    text = str(root).replace('\\', '/').lower()
    for forbidden in ('h:/', 'f:/云南', 'f:/pytorch'):
        if text.startswith(forbidden):
            raise PermissionError('Synthetic fixture layout must not point at real payload roots')
    return PathLayout2025(himawari_root=str(root / 'himawari'), imerg_root=str(root / 'imerg'),
                          gfs_root=str(root / 'gfs'), gfs_thermo_root=str(root / 'gfs_thermo'))
