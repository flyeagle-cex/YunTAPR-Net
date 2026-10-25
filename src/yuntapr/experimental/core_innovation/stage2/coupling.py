"""Explicit binding to the inherited concurrent half-hour precipitation target."""
from dataclasses import dataclass
from datetime import datetime, timedelta
from ..gfs import ForecastIdentity, utc
from . import OFFSETS


@dataclass(frozen=True)
class TargetBinding:
    window_start: datetime
    analysis: datetime
    nominal: tuple[datetime, ...]
    observation_start: tuple[datetime, ...]
    observation_end: tuple[datetime, ...]

    def __post_init__(self):
        for key in ('window_start', 'analysis'):
            object.__setattr__(self, key, utc(getattr(self, key)))
        for key in ('nominal', 'observation_start', 'observation_end'):
            object.__setattr__(self, key, tuple(utc(t) for t in getattr(self, key)))
        if self.analysis != self.window_start + timedelta(minutes=30):
            raise ValueError('Inherited target is [window_start, analysis), 30 minutes')
        if any(t.year not in (2023, 2024) or not 3 <= t.month <= 10
               for t in (self.window_start, self.analysis, *self.nominal,
                         *self.observation_start, *self.observation_end)):
            raise PermissionError('Only authorized March-October 2023/2024')
        if any(len(x) != 6 for x in (self.nominal, self.observation_start, self.observation_end)):
            raise ValueError('Six inherited historical slots required')
        for i, offset in enumerate(OFFSETS):
            if self.nominal[i] != self.analysis - timedelta(minutes=offset):
                raise ValueError('Frozen nominal slot ordering differs')
            if not self.observation_start[i] <= self.observation_end[i] <= self.analysis:
                raise ValueError('Future or reversed actual satellite interval')
            if i and self.observation_end[i] <= self.observation_end[i-1]:
                raise ValueError('Actual satellite history must increase')

    def check_forecast(self, forecast: ForecastIdentity, *, valid_policy: str):
        # No hidden nearest-time search or GFS future-valid interpolation.
        if valid_policy != 'valid_equals_analysis_retrospective_candidate':
            raise ValueError('Explicit candidate temporal operator required')
        if forecast.init > self.analysis or forecast.valid != self.analysis:
            raise ValueError('Future initialization or different target valid time')
        return {'target_semantics': 'CONCURRENT_HALF_HOUR_ESTIMATION_NOT_FUTURE_RAIN_FORECAST',
                'target_window': [self.window_start.isoformat(), self.analysis.isoformat()],
                'satellite_latest_end': max(self.observation_end).isoformat(),
                'init': forecast.init.isoformat(), 'valid': forecast.valid.isoformat(),
                'lead_hours': forecast.lead.total_seconds()/3600,
                'historical_release_established': False, 'mode': 'retrospective'}


def vintage_relation(a: ForecastIdentity, b: ForecastIdentity):
    if a == b:
        return 'IDENTICAL_FORECAST'
    if a.valid == b.valid:
        return 'SAME_VALID_DIFFERENT_VINTAGE'
    return 'DIFFERENT_VALID_NOT_A_VINTAGE_COMPARISON'
