"""Read-only sufficient statistics; no model, optimizer or raw-source dependency."""
from datetime import datetime, date, timedelta
import numpy as np

TAU = (np.arange(1, 33, dtype=np.float64) - .5) / 32
THRESHOLDS = np.array([10, 50, 100, 500, 1000], dtype=np.float64)
RATE_UPPER = np.array([1, 5, 10, 20, 30, 50, np.inf])
GROUPS = ['ALL'] + [f'MONTH_{m:02d}' for m in range(3, 11)] + ['MAM', 'JJA', 'SO_PARTIAL_AUTUMN', 'CIVIL_DAY_PROXY', 'CIVIL_NIGHT_PROXY', 'DRY_LE_0.1', '(0.1,1]', '(1,5]', '(5,10]', '(10,20]', '(20,30]', '(30,50]', '(50,inf)']
# count, rainy, focal numerator, pinball numerator, Brier numerator, p sum,
# diagnostic-proxy signed/absolute/squared error; 32 coverage, 32 pinball,
# ten reliability counts / predicted sums / observed counts.
SIZE = 103

def date_index(window_start):
    t = datetime.fromisoformat(window_start)
    if t.utcoffset() != timedelta(0) or t.year != 2024 or not 3 <= t.month <= 10:
        raise ValueError('Only frozen 2024 March-October UTC target windows')
    return (t.date() - date(2024, 3, 1)).days

def probability_bin(p):
    # Inherit ten [k/10,(k+1)/10) bins, final bin includes 1.
    return np.minimum((p * 10).astype(np.int64), 9)

def rate_bin(y, rainy):
    return np.where(rainy, 1 + np.searchsorted(RATE_UPPER, y, side='left'), 0)

def score_codes(p):
    values = np.asarray(p, dtype=np.float32)
    bits = values.view(np.uint32)
    if not np.isfinite(values).all() or (values < 0).any() or (values > 1).any() or (bits & 65535).any():
        raise ValueError('Exact BF16 occurrence-score histogram contract failed; no rounding fallback')
    return (bits >> 16).astype(np.int64)

def ranking(counts):
    """Exact score-group AUROC ties=half, AP at group ends; no bin approximation."""
    c = np.asarray(counts, dtype=np.float64)[::-1]
    c = c[c.sum(1) > 0]
    if not len(c): return np.array([np.nan, np.nan])
    neg, pos = c[:, 0], c[:, 1]
    P, N = pos.sum(), neg.sum()
    tp, fp = np.cumsum(pos), np.cumsum(neg)
    ap = np.sum(pos / P * tp / (tp + fp)) if P else np.nan
    auc = np.sum(neg / N * (2 * tp - pos) / (2 * P)) if P and N else np.nan
    return np.array([auc, ap])

def metrics(s, scores):
    n, rain = s[:2]
    if not n: return np.full(5, np.nan)
    return np.r_[(s[2] + s[3]) / n, s[4] / n, ranking(scores), s[3] / rain if rain else np.nan]

def sums(y, rainy, p, q, focal):
    out = np.zeros(SIZE)
    n, nr = len(y), int(rainy.sum())
    out[:6] = [n, nr, focal.sum(), 0, ((p - rainy)**2).sum(), p.sum()]
    if nr:
        err = np.log1p(y[rainy])[:, None] - q[rainy]
        pin = np.maximum(TAU * err, (TAU - 1) * err)
        out[3] = pin.mean(1).sum()
        out[9:41] = (err <= 0).sum(0)
        out[41:73] = pin.sum(0)
    # Descriptive proxy inherited from original review, never a point-forecast head.
    boundary = np.log(np.finfo(np.float64).max)
    if (q > boundary).any():
        out[6:9] = np.nan  # explicit unavailable physical proxy; no clipping.
    else:
        proxy_error = p * np.expm1(q).mean(1) - y
        out[6:9] = [proxy_error.sum(), np.abs(proxy_error).sum(), (proxy_error**2).sum()]
    bins = probability_bin(p)
    out[73:83] = np.bincount(bins, minlength=10)
    out[83:93] = np.bincount(bins, weights=p, minlength=10)
    out[93:103] = np.bincount(bins, weights=rainy, minlength=10)
    return out

class Observer:
    def __init__(self, mask, evidence):
        from pathlib import Path
        self.mask = np.asarray(mask, dtype=bool).reshape(100, 100)
        assert self.mask.sum() == 3430
        self.evidence = Path(evidence)
        self.daily = np.zeros((245, len(GROUPS), SIZE))
        self.scores = np.zeros((35, len(GROUPS), 16257, 2), dtype=np.int64)
        self.unique = np.zeros((2, 5, 100, 100), dtype=bool)
        self.scenes = np.zeros((2, 5), dtype=np.int64)
        self.exposures = np.zeros((2, 5, 2), dtype=np.int64)
        self.rainy_exposures = np.zeros((2, 5), dtype=np.int64)
        self.maxima = np.full(2, -np.inf)
        self.max_locations = [None, None]
        self.scene_ids = []

    def add_arrays(self, q, p, logit, y, rainy, valid, records):
        """Inputs are detached CPU arrays; only aggregate/identity outputs retained."""
        import json
        boundary = np.log(np.finfo(np.float64).max)
        assert q.shape == (len(records), 100, 100, 32)
        if not np.isfinite(q).all() or not (np.diff(q, axis=-1) > 0).all() or not (q[..., 0] > np.log1p(.1)).all():
            raise FloatingPointError('Frozen numerical guard violated')
        with (self.evidence / 'threshold_locations.jsonl').open('a', encoding='utf-8') as extreme_log:
            for b, record in enumerate(records):
                day = date_index(record['window_start']); block = day // 7
                nominal = record.get('expected_nominal', record.get('slot_5_nominal'))
                clock = datetime.fromisoformat(nominal) + timedelta(hours=8)
                t = datetime.fromisoformat(record['window_start'])
                selected = valid[b] & self.mask
                assert selected.sum() == 3430
                rate, label, prob, quant, logits = y[b][selected], rainy[b][selected], p[b][selected], q[b][selected], logit[b][selected]
                # Frozen focal arithmetic, label established in float32 before promotion.
                bce = np.logaddexp(0, logits) - logits * label
                focal = .5 * (-np.expm1(-bce))**2 * bce
                codes = score_codes(prob)
                rb = rate_bin(rate, label)
                masks = [(0, np.ones(3430, bool)), (1 + t.month - 3, np.ones(3430, bool)),
                         (9 + (0 if t.month <= 5 else 1 if t.month <= 8 else 2), np.ones(3430, bool)),
                         (12 if 6 <= clock.hour < 18 else 13, np.ones(3430, bool))]
                masks += [(14 + j, rb == j) for j in range(8)]
                for group, chosen in masks:
                    if not chosen.any(): continue
                    self.daily[day, group] += sums(rate[chosen], label[chosen], prob[chosen], quant[chosen], focal[chosen])
                    for outcome in (0, 1):
                        self.scores[block, group, :, outcome] += np.bincount(codes[chosen & (label == bool(outcome))], minlength=16257)
                for region, mask in enumerate((self.mask, ~self.mask)):
                    region_q = q[b][mask]
                    index = int(np.argmax(region_q[:, -1]))
                    row, col = np.argwhere(mask)[index]
                    maximum = float(region_q[index, -1])
                    if maximum > self.maxima[region]:
                        self.maxima[region] = maximum
                        self.max_locations[region] = {'sample_id': record['sample_id'], 'row': int(row), 'column': int(col),
                            'tau': float(TAU[-1]), 'qlog': maximum, 'truth_mm_h': float(y[b, row, col]),
                            'target_valid': bool(valid[b, row, col]), 'p_rain': float(p[b, row, col]),
                            'physical_overflow_risk': bool(maximum > boundary)}
                    for k, threshold in enumerate(THRESHOLDS):
                        over = (q[b] > np.log1p(threshold)) & mask[..., None]
                        any_tau = over.any(-1)
                        self.exposures[region, k] += [int(over.sum()), int(any_tau.sum())]
                        self.unique[region, k] |= any_tau
                        self.scenes[region, k] += int(any_tau.any())
                        self.rainy_exposures[region, k] += int((any_tau & rainy[b] & valid[b]).sum())
                    # Register every >=50 q32 event once; includes actual truth and occurrence.
                    for row, col in np.argwhere(mask & (q[b, ..., -1] > np.log1p(50))):
                        extreme_log.write(json.dumps({'sample_id': record['sample_id'], 'region': ['YUNNAN_INSIDE','YUNNAN_OUTSIDE'][region],
                            'row': int(row), 'column': int(col), 'q32_log': float(q[b,row,col,-1]),
                            'truth_mm_h': float(y[b,row,col]), 'target_valid': bool(valid[b,row,col]),
                            'rainy_truth': bool(rainy[b,row,col]), 'p_rain': float(p[b,row,col])}, allow_nan=False) + '\n')
                self.scene_ids.append(record['sample_id'])

    def save(self):
        import json
        np.savez_compressed(self.evidence / 'sufficient_statistics.npz', daily=self.daily, scores=self.scores,
            unique=self.unique, scenes=self.scenes, exposures=self.exposures, rainy_exposures=self.rainy_exposures)
        result = {'max_qlog': self.maxima.tolist(), 'max_locations': self.max_locations,
            'thresholds_mm_h': THRESHOLDS.tolist(), 'threshold_scene_pixel_tau_and_any_counts': self.exposures.tolist(),
            'threshold_unique_grid_cells': self.unique.sum((2,3)).tolist(), 'threshold_scenes': self.scenes.tolist(),
            'threshold_rainy_true_scene_pixels': self.rainy_exposures.tolist(),
            'independent_precipitation_events': 'NOT_ESTIMABLE_NO_PREDEFINED_EVENT_CATALOGUE',
            'groups': GROUPS, 'scene_ids': self.scene_ids, 'physical_proxy_scope': 'DIAGNOSTIC_PROXY_ONLY_NOT_EXACT_EXPECTATION'}
        (self.evidence / 'observer_summary.json').write_text(json.dumps(result, indent=2, allow_nan=False)+'\n', encoding='utf-8')
        return result
