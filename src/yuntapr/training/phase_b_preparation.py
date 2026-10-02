"""FinalFit preparation utilities. There is deliberately no formal training entrypoint."""
from dataclasses import dataclass
from pathlib import Path
import json
import math
import numpy as np
from yuntapr.contracts.loader import sha256
from yuntapr.data.formal_policy import require_full_valid
from yuntapr.data.sample_schema import utc
from yuntapr.training.phase_a_protocol import epoch_permutation, lr_for_update

SCENES = 23447
PIXELS = 5885220447
STEPS = 11724
EPOCHS = 11
UPDATES = 128964
TAIL_POLICY = "ALLOW_SINGLETON_NO_DROP_NO_DUPLICATE"
INITIALIZATION = "FRESH_SEED_2026"


def validate_population(rows):
    if len(rows) != SCENES or len({r['sample_id'] for r in rows}) != SCENES:
        raise ValueError('FinalFit population size or unique identities changed')
    counts = {2023: 0, 2024: 0}
    ordered = []
    for index, row in enumerate(rows):
        t = utc(row['window_start'])
        if t.year not in counts or t.month not in range(3, 11) or int(row['year']) != t.year:
            raise ValueError('Unauthorized FinalFit year/month')
        if int(row['finalfit_index']) != index or row['role'] != 'FinalFit':
            raise ValueError('Noncanonical FinalFit identity order/role')
        if row['source_role'] != ('Train' if t.year == 2023 else 'Validation'):
            raise ValueError('Original frozen data role changed')
        counts[t.year] += 1
        ordered.append((t, row['sample_id'], row['source_role']))
    if counts != {2023: 11720, 2024: 11727} or ordered != sorted(ordered):
        raise ValueError('Frozen year counts or canonical sort changed')
    return counts


def batch_plan(epoch_index, count=SCENES):
    if count != SCENES:
        raise ValueError('Only the approved FinalFit population is supported')
    permutation = epoch_permutation(epoch_index, count=count)
    return permutation, [permutation[i:i+2] for i in range(0, count, 2)]


def finalfit_lr(update):
    return lr_for_update(update, steps_per_epoch=STEPS)


def exact_histogram_summary(histogram):
    """Exact packed-code support decoded with the frozen float32 reader arithmetic."""
    hist = np.asarray(histogram)
    if hist.shape != (65536,) or hist.dtype != np.int64 or (hist < 0).any() or not hist.any():
        raise ValueError('Nonempty nonnegative int64 packed-code histogram required')
    values = (np.arange(-32768, 32768, dtype=np.float32)*np.float32(.01)+np.float32(273.15)).astype(np.float64)
    count = int(hist.sum())
    mean = float(np.dot(hist.astype(np.float64), values)/count)
    variance = float(np.dot(hist.astype(np.float64), (values-mean)**2)/count)
    cumulative = hist.cumsum()
    def percentile(fraction):
        rank = fraction*(count-1)
        lo, hi = math.floor(rank), math.ceil(rank)
        a = values[np.searchsorted(cumulative, lo+1)]
        b = values[np.searchsorted(cumulative, hi+1)]
        return float(a+(b-a)*(rank-lo))
    result = {'valid_pixel_count':count, 'mean_K':mean, 'std_K':math.sqrt(variance), 'ddof':0}
    result.update({key:percentile(p) for key,p in [('min_K',0),('p1_K',.01),('q1_K',.25),('median_K',.5),('q3_K',.75),('p99_K',.99),('max_K',1)]})
    result['IQR_K'] = result['q3_K']-result['q1_K']
    return result


def merge_moments(state, values):
    count, mean, m2 = state
    vals = np.asarray(values, dtype=np.float64).ravel()
    n, avg = vals.size, float(vals.mean())
    local_m2 = float(np.square(vals-avg).sum(dtype=np.float64))
    delta = avg-mean
    return count+n, mean+delta*n/(count+n), m2+local_m2+delta*delta*count*n/(count+n)


@dataclass(frozen=True)
class PhaseBNormalizer:
    version: str
    mu: float
    sigma: float
    artifact_sha256: str

    @classmethod
    def from_artifact(cls, path, expected_sha256):
        path = Path(path)
        if sha256(path) != expected_sha256:
            raise ValueError('FinalFit normalization SHA mismatch')
        value = json.loads(path.read_text(encoding='utf-8'))
        if (value['fit_years'] != [2023,2024] or value['fit_months'] != list(range(3,11))
                or value['ddof'] != 0 or not value['ready'] or value['eligible_scene_count'] != SCENES
                or value['valid_pixel_count'] != PIXELS or value['2025_PIXELS_READ'] != 0
                or not np.isfinite(value['mean_K']) or not np.isfinite(value['std_K']) or value['std_K'] <= 0):
            raise ValueError('Invalid FinalFit normalization population/constants')
        if sha256(path.with_name('phase_b_finalfit_manifest.csv')) != value['sample_manifest_sha256']:
            raise ValueError('FinalFit sample manifest changed')
        return cls(value['normalization_version'],value['mean_K'],value['std_K'],expected_sha256)

    def transform(self, raw_kelvin, valid, window_start):
        t = utc(window_start)
        if t.year not in (2023,2024) or t.month not in range(3,11):
            raise ValueError('Preparation permits only eligible 2023/2024 March-October')
        require_full_valid(raw_kelvin, valid)
        result = ((raw_kelvin.astype(np.float64)-self.mu)/self.sigma).astype(np.float32)
        if not np.isfinite(result).all():
            raise ValueError('Nonfinite FinalFit normalized input')
        return result
