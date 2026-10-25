"""Additive sufficient statistics; never alter frozen E0 or select a model."""
import numpy as np


class TailDiagnostics:
    """Real-rain strata, conditional q32 coverage and paired block summaries.

    Feed log1p quantiles, physical mm/h targets and the existing supervision mask.
    This is additive: the historical exact-score evaluator remains authoritative.
    """
    EDGES = (.1, 1., 5., 10., 20., 30., 50., float('inf'))

    def __init__(self):
        self.rows = []
        self.seen = set()

    def add(self, sid, rate, quantiles_log, valid):
        if sid in self.seen or not str(sid).startswith('2024-'):
            raise ValueError('Unique 2024 Development scene required')
        y = np.asarray(rate, dtype=np.float32)
        q = np.asarray(quantiles_log, dtype=np.float64)
        v = np.asarray(valid)
        if v.dtype != bool or v.shape != y.shape or q.shape != (32, *y.shape):
            raise ValueError('Exact 32-quantile target/mask shapes required')
        if (not np.isfinite(y[v]).all() or (y[v] < 0).any()
                or not np.isfinite(q[:, v]).all() or (np.diff(q[:, v], axis=0) < 0).any()):
            raise ValueError('Finite nonnegative targets and ordered quantiles required')
        rain = v & (y > np.float32(.1))
        yl = np.log1p(y.astype(np.float64))
        delta = yl[None] - q
        tau = ((np.arange(32)+.5)/32).reshape(32, *([1]*y.ndim))
        pin = np.maximum(tau*delta, (tau-1)*delta).mean(axis=0)
        rows = []
        for lo, hi in zip(self.EDGES, self.EDGES[1:]):
            m = rain & (y > np.float32(lo)) & (y <= np.float32(hi))
            n = int(m.sum())
            rows.append(dict(lower=lo, upper=None if np.isinf(hi) else hi,
                             n_rain=n, q32_covered=int((yl[m] <= q[-1, m]).sum()),
                             pinball_sum=float(pin[m].sum()),
                             q32_shortfall_log_sum=float(np.maximum(yl[m]-q[-1, m], 0).sum())))
        self.rows.append(dict(sample_id=sid, strata=rows))
        self.seen.add(sid)

    def finish(self):
        result = []
        for i in range(7):
            rows = [r['strata'][i] for r in self.rows]
            n = sum(r['n_rain'] for r in rows)
            covered = sum(r['q32_covered'] for r in rows)
            pin = sum(r['pinball_sum'] for r in rows)
            result.append(dict(lower=self.EDGES[i], upper=None if i == 6 else self.EDGES[i+1],
                               n_rain=n, q32_covered=covered,
                               q32_coverage=covered/n if n else None,
                               conditional_pinball=pin/n if n else None,
                               q32_shortfall_log_sum=sum(r['q32_shortfall_log_sum'] for r in rows)))
        return dict(scope='ADDITIVE_2024_DEV_DIAGNOSTIC', nominal_q32=.984375,
                    independent_event_count='NOT_ESTIMATED', strata=result, scene_sufficient_statistics=self.rows)
