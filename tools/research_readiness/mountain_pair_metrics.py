"""Additive elevation x rainfall diagnostics from an existing inference pass."""
import hashlib
import math

import numpy as np

ELEVATIONS = ('elevation_lt_1000m', 'elevation_1000_to_2000m', 'elevation_ge_2000m')
EDGES = (.1, 1., 5., 10., 20., 30., 50., float('inf'))
CONTRACT = {
    'profile': 'MOUNTAIN_TERRAIN_PAIR_V1',
    'direction': 'REAL_MINUS_ZERO',
    'elevation_edges_m': [1000., 2000.],
    'rainfall_edges_mm_h': [.1, 1., 5., 10., 20., 30., 50., None],
    'primary_population': 'elevation_ge_2000m_AND_float32_R_strictly_gt20',
    'primary_metrics': ['log_pinball', 'physical_pinball_over20'],
    'roundoff_tolerance': 1e-10,
    'purpose': 'EXPLORATORY_LOCAL_INCREMENT_AND_GLOBAL_TRADEOFF_DESCRIPTION',
    'empty_cells': 'NOT_ESTIMABLE',
    'inference': 'ONE_FIXED_E9_PASS_PER_ARM_NO_TRAINING',
    'independent_event_count': 'NOT_IDENTIFIED',
    'scientific_status': 'NOT_VERIFIED',
}


class MountainAccumulator:
    def __init__(self, pack, scene_ids):
        self.ids, self.position, self.closed = tuple(scene_ids), 0, False
        self.failed = False
        if not self.ids or len(set(self.ids)) != len(self.ids):
            raise ValueError('Unique declared scene order required')
        self.grid = pack.grid.identity
        elevation = pack.values[0]
        valid = pack.valid[0] & pack.region
        if not pack.valid[0][pack.region].all():
            raise ValueError('Elevation holes cannot shrink the supervision population')
        self.masks = (valid & (elevation < 1000), valid & (elevation >= 1000) & (elevation < 2000), valid & (elevation >= 2000))
        self.digest = hashlib.sha256()
        self.scenes = []
        self.counts = np.zeros((3, 7), dtype=np.int64)
        self.log = np.zeros((3, 7), dtype=np.float64)
        self.physical = np.zeros((3, 7), dtype=np.float64)
        self.covered = np.zeros((3, 7), dtype=np.int64)
        self.valid_counts = np.zeros(3, dtype=np.int64)
        self.brier = np.zeros(3, dtype=np.float64)

    def add_batch(self, output, batch):
        self.add(batch.ids, batch.rate.detach().cpu().numpy(), batch.valid.detach().cpu().numpy(),
                 batch.region.detach().cpu().numpy(), output.rain_prob.detach().double().cpu().numpy(),
                 output.conditional_quantiles_log.detach().double().cpu().numpy())

    def add(self, ids, rate, valid, region, probability, qlog):
        if self.closed or self.failed:
            raise RuntimeError('Closed or failed diagnostic')
        try:
            self._add(ids, rate, valid, region, probability, qlog)
        except BaseException:
            self.failed = True
            raise

    def _add(self, ids, rate, valid, region, probability, qlog):
        ids = tuple(ids)
        if not ids or ids != self.ids[self.position:self.position + len(ids)]:
            raise ValueError('Scene identity/order differs')
        rate, probability, qlog = np.asarray(rate), np.asarray(probability), np.asarray(qlog)
        valid, region = np.asarray(valid), np.asarray(region)
        expected = (len(ids), 1, *self.masks[0].shape)
        if (rate.shape != expected or probability.shape != expected or valid.shape != expected
                or region.shape != expected or valid.dtype != bool or region.dtype != bool
                or qlog.shape != (len(ids), 32, *expected[-2:])):
            raise ValueError('Exact batch/field/mask shapes required')
        if (not np.isfinite(probability).all() or ((probability < 0) | (probability > 1)).any()
                or not np.isfinite(qlog).all() or (qlog[:, 0] <= math.log1p(.1)).any()
                or (np.diff(qlog, axis=1) <= 0).any()):
            raise ValueError('Finite supported probabilities and ordered conditional nodes required')
        tau = ((np.arange(32, dtype=np.float64) + .5) / 32)[None, :]
        for index, sid in enumerate(ids):
            mask = (valid & region)[index, 0]
            if (mask & ~np.logical_or.reduce(self.masks)).any():
                raise ValueError('Supervision outside the frozen elevation partition')
            y = rate[index, 0].astype(np.float32)
            if not np.isfinite(y[mask]).all() or (y[mask] < 0).any():
                raise ValueError('Invalid supervised reference')
            labels = np.full(mask.shape, -1, dtype=np.int8)
            for group, elevation_mask in enumerate(self.masks):
                labels[mask & elevation_mask] = group
            # The same mask, truth bytes and terrain membership must reproduce
            # across arms. Predictions never participate in this identity.
            self.digest.update(sid.encode() + b'\0')
            self.digest.update(mask.tobytes())
            self.digest.update(np.asarray(y[mask], dtype='<f4').tobytes())
            self.digest.update(labels[mask].tobytes())
            wet = mask & (y > np.float32(.1))
            nodes = qlog[index].reshape(32, -1)[:, wet.reshape(-1)].T
            observed = y[wet].astype(np.float64)
            with np.errstate(over='raise', invalid='raise'):
                log_error = np.log1p(observed)[:, None] - nodes
                physical_error = (observed[:, None] - np.expm1(nodes)) / 20.
                log_score = np.maximum(tau * log_error, (tau - 1) * log_error).mean(1)
                physical_score = np.maximum(tau * physical_error, (tau - 1) * physical_error).mean(1)
            covered = nodes[:, -1] >= np.log1p(observed)
            group_rows = []
            for group, elevation_mask in enumerate(self.masks):
                selected = mask & elevation_mask
                self.valid_counts[group] += int(selected.sum())
                error = probability[index, 0][selected] - (y[selected] > np.float32(.1))
                self.brier[group] += float(np.square(error).sum())
                cells = []
                for cell, (lower, upper) in enumerate(zip(EDGES, EDGES[1:])):
                    chosen = (labels[wet] == group) & (observed > np.float32(lower)) & (observed <= np.float32(upper))
                    count = int(chosen.sum())
                    a, b, c = float(log_score[chosen].sum()), float(physical_score[chosen].sum()), int(covered[chosen].sum())
                    self.counts[group, cell] += count
                    self.log[group, cell] += a
                    self.physical[group, cell] += b
                    self.covered[group, cell] += c
                    cells.append(dict(n_rain=count, log_pinball_sum=a, physical_pinball_over20_sum=b, q32_covered=c))
                group_rows.append(cells)
            self.scenes.append(dict(scene_id=sid, elevation_rainfall_cells=group_rows))
        self.position += len(ids)

    def finish(self, report):
        if self.closed or self.failed or self.position != len(self.ids):
            raise RuntimeError('Incomplete or already closed diagnostic')
        summary = report['groups']['all']['summary']
        n_valid, n_rain = int(self.valid_counts.sum()), int(self.counts.sum())
        if (n_valid <= 0 or n_rain <= 0 or n_valid != summary['n_valid'] or n_rain != summary['n_rain']
                or not math.isclose(float(self.log.sum()) / n_rain, summary['conditional_pinball'], abs_tol=1e-10)
                or not math.isclose(float(self.brier.sum()) / n_valid, summary['brier'], abs_tol=1e-10)
                or int(self.covered.sum()) != summary['covered'][-1]):
            self.failed = True
            raise RuntimeError('Terrain sums differ from the frozen global evaluator')
        groups = {}
        for group, name in enumerate(ELEVATIONS):
            cells = []
            for cell in range(7):
                count = int(self.counts[group, cell])
                cells.append(dict(lower_exclusive=EDGES[cell], upper_inclusive=None if cell == 6 else EDGES[cell + 1],
                                  n_rain=count, log_pinball_sum=float(self.log[group, cell]),
                                  physical_pinball_over20_sum=float(self.physical[group, cell]),
                                  log_pinball=float(self.log[group, cell]) / count if count else None,
                                  physical_pinball_over20=float(self.physical[group, cell]) / count if count else None,
                                  q32_covered=int(self.covered[group, cell])))
            groups[name] = dict(n_valid=int(self.valid_counts[group]), n_rain=int(self.counts[group].sum()),
                                brier_sum=float(self.brier[group]), cells=cells)
        self.closed = True
        return dict(profile=CONTRACT['profile'], grid_sha256=self.grid,
                    paired_population_sha256=self.digest.hexdigest(), scenes=len(self.ids),
                    population=dict(n_valid=n_valid, n_rain=n_rain, n_strong=int(self.counts[:, 4:].sum())),
                    elevation_groups=groups, scene_statistics=self.scenes, scientific_status='NOT_VERIFIED')


def primary_contrast(real, zero):
    if real['paired_population_sha256'] != zero['paired_population_sha256'] or real['grid_sha256'] != zero['grid_sha256']:
        raise ValueError('Paired reference/mask/elevation identities differ')
    for name in ELEVATIONS:
        for a, b in zip(real['elevation_groups'][name]['cells'], zero['elevation_groups'][name]['cells']):
            if a['n_rain'] != b['n_rain']:
                raise ValueError('Paired cell populations differ')
    a = real['elevation_groups'][ELEVATIONS[2]]['cells'][4:]
    b = zero['elevation_groups'][ELEVATIONS[2]]['cells'][4:]
    count = sum(row['n_rain'] for row in a)
    if not count:
        return dict(status='NOT_ESTIMABLE', n_strong=0)
    deltas = {metric: (math.fsum(row[metric + '_sum'] for row in a) - math.fsum(row[metric + '_sum'] for row in b)) / count
              for metric in ('log_pinball', 'physical_pinball_over20')}
    tolerance = CONTRACT['roundoff_tolerance']
    status = ('DIRECTIONAL_LOCAL_IMPROVEMENT' if all(value < -tolerance for value in deltas.values())
              else 'DIRECTIONAL_LOCAL_DEGRADATION' if all(value > tolerance for value in deltas.values())
              else 'MIXED_OR_WITHIN_ROUNDOFF')
    return dict(status=status, n_strong=count, real_minus_zero=deltas)
