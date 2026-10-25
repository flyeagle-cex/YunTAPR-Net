"""Only stage-2 additions; the inherited 52 checks are not rediscovered."""
import unittest
from datetime import datetime, timedelta, timezone
import numpy as np
import torch
from yuntapr.experimental.core_innovation.grid import GridSpec
from yuntapr.experimental.core_innovation.terrain import terrain_features
from yuntapr.experimental.core_innovation.dote import dote_proxy
from yuntapr.experimental.core_innovation.gfs import ForecastIdentity
from yuntapr.experimental.core_innovation.multispectral import TrainNormalization
from yuntapr.experimental.core_innovation.stage2 import CHANNELS, OFFSETS, MEE_KEYS
from yuntapr.experimental.core_innovation.stage2.coupling import TargetBinding, vintage_relation
from yuntapr.experimental.core_innovation.stage2.population import joint_population, TrainMoments
from yuntapr.experimental.core_innovation.stage2.dote_v13 import complete_dote, aggregate_native_terrain
from yuntapr.experimental.core_innovation.stage2.fusion import FusionCandidate
from yuntapr.experimental.core_innovation.stage2.models import MEECandidate, SpectralCandidate
from yuntapr.models.quantile_v2.parameterization import CandidateNumerics


def binding():
    a = datetime(2023, 5, 1, 6, tzinfo=timezone.utc)
    n = tuple(a-timedelta(minutes=m) for m in OFFSETS)
    return TargetBinding(a-timedelta(minutes=30), a, n, n,
                         tuple(t+timedelta(minutes=9) for t in n))


class TemporalTests(unittest.TestCase):
    def test_same_valid_different_vintage_and_different_valid(self):
        b = binding(); a = ForecastIdentity(b.analysis, timedelta(0), b.analysis)
        c = ForecastIdentity(b.analysis-timedelta(hours=6), timedelta(hours=6), b.analysis)
        d = ForecastIdentity(c.init, timedelta(hours=3), b.analysis-timedelta(hours=3))
        self.assertEqual(vintage_relation(a, c), 'SAME_VALID_DIFFERENT_VINTAGE')
        self.assertEqual(vintage_relation(c, d), 'DIFFERENT_VALID_NOT_A_VINTAGE_COMPARISON')
        self.assertFalse(b.check_forecast(c, valid_policy='valid_equals_analysis_retrospective_candidate')['historical_release_established'])

    def test_target_mismatch_future_actual_and_future_forecast_reject(self):
        b = binding()
        with self.assertRaises(ValueError):
            TargetBinding(b.window_start, b.analysis, b.nominal, b.observation_start,
                          b.observation_end[:-1]+(b.analysis+timedelta(seconds=1),))
        with self.assertRaises(ValueError):
            b.check_forecast(ForecastIdentity(b.analysis+timedelta(hours=3), timedelta(0), b.analysis+timedelta(hours=3)),
                             valid_policy='valid_equals_analysis_retrospective_candidate')


class PopulationTests(unittest.TestCase):
    def row_and_evidence(self):
        b = binding(); row = {'sample_id': b.window_start.isoformat(), 'window_start': b.window_start.isoformat(),
                             'analysis_time': b.analysis.isoformat(), 'role': 'Train'}
        frames = {}
        for i, n in enumerate(b.nominal):
            key = n.isoformat(); row[f'slot_{i}_nominal'] = key
            frames[key] = {'nominal': key, 'obs_start': n.isoformat(), 'obs_end': b.observation_end[i].isoformat(),
                           'channels': list(CHANNELS), 'full_valid': [True]*7, 'units': ['K']*7,
                           'source_sha256': 'a'*64, 'native_grid_id': 'grid'}
        return row, frames

    def test_joint_missing_and_channel_substitution_do_not_pass(self):
        row, frames = self.row_and_evidence()
        self.assertTrue(joint_population([row], frames, native_grid_id='grid')['same_population_as_B1'])
        frames[row['slot_0_nominal']]['channels'][0] = 'B07'
        report = joint_population([row], frames, native_grid_id='grid')
        self.assertFalse(report['formal_ready']); self.assertFalse(report['accepted_ids'])
        self.assertFalse(joint_population([row], {}, native_grid_id='grid')['formal_ready'])

    def test_exposure_fit_2023_only_complete_and_b13_preserved(self):
        ids = ['2023-05-01T00:00:00+00:00', '2023-05-01T00:30:00+00:00']
        fitter = TrainMoments(ids, population_id='synthetic_population')
        x = np.arange(6*7*3*3).reshape(6, 7, 3, 3).astype(np.float32)
        frozen = TrainNormalization('B13', 271., 20., 'K', (2023,), 'Train', 0, 'frozen')
        fitter.update(ids[0], x, np.ones_like(x, bool), channels=CHANNELS, role='Train')
        with self.assertRaises(ValueError): fitter.finish(frozen_b13=frozen)
        with self.assertRaises(ValueError): fitter.update(ids[0], x, np.ones_like(x, bool), channels=CHANNELS, role='Train')
        fitter.update(ids[1], x+20, np.ones_like(x, bool), channels=CHANNELS, role='Train')
        result = fitter.finish(frozen_b13=frozen)
        self.assertIs(result['B13'], frozen)
        self.assertAlmostEqual(result['B08'].mean, np.concatenate((x[:, 0].ravel(), (x+20)[:, 0].ravel())).mean(), places=5)
        self.assertAlmostEqual(result['B08'].std, np.concatenate((x[:, 0].ravel(), (x+20)[:, 0].ravel())).astype(float).std(), places=8)
        with self.assertRaises(PermissionError): TrainMoments(['2024-05-01T00:00:00Z'], population_id='bad')


class DoteTests(unittest.TestCase):
    def terrain(self):
        grid = GridSpec(np.linspace(26.01, 25.99, 9), np.linspace(102.99, 103.01, 9))
        z = np.broadcast_to(np.arange(9)*10., grid.shape).copy()
        return terrain_features(z, np.ones_like(z, bool), grid, elevation_unit='m')

    def test_native_gradient_aggregation_axis_reversal_and_complete_border(self):
        t = self.terrain(); target = GridSpec([25.9975, 26.0025], [102.9975, 103.0025])
        a = aggregate_native_terrain(t, target, footprint_degrees=.005, boundary_rule='require_complete_native_stencils')
        self.assertTrue(a.gradient_valid.all()); self.assertTrue((a.east_gradient > 0).all())
        np.testing.assert_allclose(a.north_gradient, 0, atol=1e-12)
        reverse = terrain_features(t.elevation_m[::-1, ::-1], t.elevation_valid[::-1, ::-1],
            GridSpec(t.grid.lat[::-1], t.grid.lon[::-1]), elevation_unit='m')
        r = aggregate_native_terrain(reverse, target, footprint_degrees=.005, boundary_rule='require_complete_native_stencils')
        np.testing.assert_allclose(a.east_gradient, r.east_gradient)
        border = aggregate_native_terrain(t, GridSpec([25.99, 26.], [103., 103.01]),
            footprint_degrees=.005, boundary_rule='require_complete_native_stencils')
        self.assertFalse(border.gradient_valid.all())

    def test_owlm_reversal_moisture_and_underground(self):
        t = self.terrain(); u = np.ones((2, *t.grid.shape)); ps = np.full(t.grid.shape, 80000.)
        def calc(wind):
            p = dote_proxy(t, wind, np.zeros_like(wind), np.ones_like(wind, bool), np.array([850., 700.]),
                ps, np.ones_like(ps, bool), wind_grid=t.grid, wind_unit='m/s', pressure_unit='hPa', surface_pressure_unit='Pa')
            return complete_dote(p, np.full(t.grid.shape, 40.), np.ones_like(ps, bool), pwat_grid=t.grid,
                pwat_unit='kg/m2', pwat_reference_kg_m2=20., reference_provenance='synthetic_physical_scale', moisture_basis='signed_O')
        a, r = calc(u), calc(-u)
        self.assertFalse(a.valid[0].any()); self.assertTrue(a.valid[1, 4, 4])
        np.testing.assert_allclose(a.W, r.L, equal_nan=True)
        np.testing.assert_allclose(a.M, a.O*2, equal_nan=True)
        np.testing.assert_allclose(a.O, -r.O, equal_nan=True)


class FusionTests(unittest.TestCase):
    def pair(self):
        args = dict(feature_channels=[4, 8], gfs_channels=[3, 3], terrain_channels=[8, 8], projection_width=3, modulation_limit=.5)
        return FusionCandidate(kind='B7', **args), FusionCandidate(kind='B8', **args)

    def inputs(self):
        grids = [GridSpec([26., 25., 24.], [101., 102., 103.]), GridSpec([26., 24.], [101., 103.])]
        f = [torch.randn(1, c, *g.shape, requires_grad=True) for c, g in zip((4, 8), grids)]
        gfs = [torch.randn(1, 3, *g.shape, requires_grad=True) for g in grids]
        terrain = [torch.randn(1, 8, *g.shape, requires_grad=True) for g in grids]
        masks = [torch.ones(1, 1, *g.shape, dtype=torch.bool) for g in grids]
        return f, gfs, terrain, masks, grids

    def test_exact_active_parameter_match_identity_and_same_dynamic_input(self):
        a, b = self.pair(); f, g, t, m, grids = self.inputs()
        self.assertEqual(sum(p.numel() for p in a.parameters()), sum(p.numel() for p in b.parameters()))
        for model in (a, b):
            out = model(f, g, t, m, m, m, feature_grids=grids, gfs_grids=grids, terrain_grids=grids)
            for x, y in zip(out.values, f): self.assertTrue(torch.equal(x, y))

    def test_active_gradients_after_identity_release_and_invalid_condition(self):
        for model in self.pair():
            f, g, t, m, grids = self.inputs()
            # Perturb candidate initialization without an optimizer; tests full
            # functional paths, not just zero-initialized output gradients.
            with torch.no_grad():
                for layer in model.fuse: layer.weight.fill_(.01)
                if model.modulation:
                    for layer in model.modulation.projections: layer.weight.fill_(.01)
            out = model(f, g, t, m, m, m, feature_grids=grids, gfs_grids=grids, terrain_grids=grids)
            sum(x.square().mean() for x in out.values).backward()
            for name, p in model.named_parameters():
                self.assertIsNotNone(p.grad, name); self.assertTrue(torch.isfinite(p.grad).all(), name); self.assertGreater(p.grad.abs().sum().item(), 0, name)
            cm = [torch.zeros_like(mask) for mask in m]
            bad = [torch.full_like(x, float('nan')) for x in g]
            out = model(f, bad, t, m, cm, m, feature_grids=grids, gfs_grids=grids, terrain_grids=grids)
            for x, y in zip(out.values, f): self.assertTrue(torch.equal(x, y))


class ModelTests(unittest.TestCase):
    def test_mee_pressure_masks_order_and_gradient(self):
        model = MEECandidate(width=8); x = torch.randn(1, 11, 4, 4, requires_grad=True)
        mask = torch.ones_like(x, dtype=torch.bool); mask[:, [2, 4, 6, 7]] = False
        out, used = model(x, mask, keys=MEE_KEYS); self.assertTrue(used.all())
        out.sum().backward(); self.assertTrue(torch.isfinite(x.grad).all())
        with self.assertRaises(ValueError): model(x, mask, keys=MEE_KEYS[::-1])
        mask[:, 10] = False
        out, used = model(x, mask, keys=MEE_KEYS); self.assertFalse(used.any()); self.assertTrue((out == 0).all())

    def test_b3_b4_construct_reuse_heads_and_only_stem_differs_from_pilot(self):
        n = CandidateNumerics(epsilon_w=1e-4, epsilon_span=1e-4)
        b3 = SpectralCandidate('B3', numerics=n); b4 = SpectralCandidate('B4', numerics=n, mee_width=16)
        self.assertEqual(b3.backbone.enc0.conv1.in_channels, 42)
        self.assertEqual(b3.heads.__class__, b4.heads.__class__)
        self.assertEqual(b3.projection.indices.tolist(), b4.projection.indices.tolist())
        self.assertGreater(sum(p.numel() for p in b4.parameters()), sum(p.numel() for p in b3.parameters()))
        with self.assertRaises(ValueError): b3(torch.zeros(1, 6, 501, 501), torch.ones(1, 6, 501, 501, dtype=torch.bool), channel_order=CHANNELS)


if __name__ == '__main__': unittest.main()
