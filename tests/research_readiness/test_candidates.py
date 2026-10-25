import math
import unittest
import uuid
from pathlib import Path
import numpy as np
import torch
from yuntapr.experimental.core_innovation.grid import GridSpec
from yuntapr.experimental.core_innovation.terrain import TerrainFeatures, terrain_features, DemWindow
from yuntapr.experimental.core_innovation.stage2.models import SpectralCandidate, paired_spectral_candidates
from yuntapr.experimental.core_innovation.stage2 import CHANNELS, MEE_V13_KEYS
from yuntapr.models.quantile_v2.parameterization import CandidateNumerics
from yuntapr.experimental.research_readiness.b2 import initialize_b2, latest_frame, STEM_RULE, STEM_WEIGHTS
from yuntapr.experimental.research_readiness.static_terrain import pack_terrain, fit_static_train_scalers, StaticAdapter, StaticTerrainCandidate, join_north_south
from yuntapr.experimental.research_readiness.tail_diagnostics import TailDiagnostics
from yuntapr.experimental.research_readiness.b2_runner import validate_authorization, B2Ledger, difference
from yuntapr.contracts.loader import REPO_ROOT


class B2Tests(unittest.TestCase):
    def test_common_weights_and_input_mapping(self):
        torch.manual_seed(2029)
        reference = SpectralCandidate('B3', numerics=CandidateNumerics(1e-4, 1e-4))
        rng = torch.get_rng_state().clone()
        b2, receipt = initialize_b2(reference, stem_rule=STEM_RULE)
        self.assertTrue(torch.equal(rng, torch.get_rng_state()))
        for name, value in b2.state_dict().items():
            source = reference.state_dict()[name]
            if name in STEM_WEIGHTS:
                self.assertTrue(torch.equal(value, source[:, 35:42]*math.sqrt(6.)))
            else:
                self.assertTrue(torch.equal(value, source), name)
        self.assertEqual(b2.input_channels, 7)
        self.assertEqual(receipt['selected_slot'], 5)
        self.assertEqual(sum(p.numel() for p in reference.parameters())-sum(p.numel() for p in b2.parameters()), 16800)
        with self.assertRaises(ValueError):
            initialize_b2(reference, stem_rule='UNAPPROVED')

    def test_latest_frame_order_and_joint_missing_guard(self):
        x = torch.zeros(1, 42, 501, 501)
        for i in range(42):
            x[:, i] = i
        mask = torch.ones_like(x, dtype=torch.bool)
        value, valid = latest_frame(x, mask)
        self.assertEqual(value.shape, (1, 7, 501, 501))
        torch.testing.assert_close(value[0, :, 0, 0], torch.arange(35., 42.))
        mask[0, 0, 0, 0] = False
        with self.assertRaises(ValueError):
            latest_frame(x, mask)
        mask.fill_(True)
        x[0, 0, 0, 0] = float('nan')
        with self.assertRaises(ValueError):
            latest_frame(x, mask)


class StaticTests(unittest.TestCase):
    def setUp(self):
        self.grid = GridSpec(np.linspace(25., 24., 5), np.linspace(102., 103., 5))
        z = np.arange(25.).reshape(5, 5)*10
        self.features = terrain_features(z, np.ones((5, 5), bool), self.grid, elevation_unit='m')
        self.region = np.zeros((5, 5), bool)
        self.region[1:-1, 1:-1] = True

    def pack(self, kind='B6'):
        return pack_terrain(self.features, kind=kind, region=self.region, expected_grid=self.grid,
                            source_sha256='a'*64, aggregation_rule='SYNTHETIC_ALREADY_ALIGNED_NOT_PRODUCTION')

    def test_static_channel_order_scaling_and_identity_init(self):
        for kind, n in [('B5', 1), ('B6', 6)]:
            p = self.pack(kind)
            s = fit_static_train_scalers(p, fit_role='Train', fit_years=[2023], train_region=self.region, population_sha256='b'*64)
            self.assertEqual(p.values.shape[0], n)
            self.assertTrue(all(x['n_unique_pixels'] == 9 for x in s['scales']))
            model = StaticAdapter(p, s, width=16)
            out = model(2)
            self.assertEqual(out.shape, (2, 48, 5, 5))
            self.assertEqual(torch.count_nonzero(out).item(), 0)
            out.sum().backward()
            self.assertTrue(torch.isfinite(model.output.weight.grad).all())
            self.assertGreater(torch.count_nonzero(model.output.weight.grad).item(), 0)
            with self.assertRaises(ValueError):
                fit_static_train_scalers(p, fit_role='Development', fit_years=[2024], train_region=self.region, population_sha256='b'*64)

    def test_grid_shift_and_missing_yunnan_rejected(self):
        shifted = GridSpec(self.grid.lat, self.grid.lon+.01)
        with self.assertRaises(ValueError):
            pack_terrain(self.features, kind='B5', region=self.region, expected_grid=shifted, source_sha256='a'*64, aggregation_rule='X')
        self.region[0, 0] = True
        with self.assertRaises(ValueError):
            self.pack('B6')

    def test_flat_aspect_keeps_independent_mask(self):
        f = terrain_features(np.ones((5, 5)), np.ones((5, 5), bool), self.grid, elevation_unit='m')
        p = pack_terrain(f, kind='B6', region=self.region, expected_grid=self.grid, source_sha256='a'*64, aggregation_rule='FIXTURE')
        self.assertFalse(p.valid[-2:].any())
        self.assertTrue((p.values[-2:] == 0).all())
        self.assertTrue(p.valid[1:4, self.region].all())

    def test_north_south_halo_and_conflict_no_repair(self):
        z = np.arange(25.).reshape(5, 5)
        north = DemWindow(GridSpec(self.grid.lat[:3], self.grid.lon), z[:3], np.ones((3, 5), bool))
        south = DemWindow(GridSpec(self.grid.lat[2:], self.grid.lon), z[2:], np.ones((3, 5), bool))
        joined = join_north_south(north, south, max_cells=25)
        np.testing.assert_array_equal(joined.elevation_m, z)
        joined.grid.assert_same(self.grid)
        mismatch = DemWindow(south.grid, south.elevation_m+1., south.valid)
        with self.assertRaises(ValueError):
            join_north_south(north, mismatch)
        with self.assertRaises(ValueError):
            join_north_south(north, south, max_cells=24)


class StaticNativeIntegrationTests(unittest.TestCase):
    @torch.no_grad()
    def test_b5_b6_zero_residual_preserves_actual_b4_outputs(self):
        torch.manual_seed(2029)
        _, b4 = paired_spectral_candidates(numerics=CandidateNumerics(1e-4, 1e-4), mee_width=16, mee_keys=MEE_V13_KEYS)
        grid = b4.grid
        shape = grid.shape
        valid = np.ones(shape, bool)
        elevation = np.arange(10000.).reshape(shape)
        gx, gy = np.full(shape, .1), np.zeros(shape)
        features = TerrainFeatures(grid, elevation, valid, gx, gy, valid,
                                   np.full(shape, np.degrees(np.arctan(.1))), np.full(shape, 270.), valid)
        region = np.zeros(shape, bool)
        region.flat[:3430] = True
        x = torch.zeros(1, 42, 501, 501)
        native_valid = torch.ones_like(x, dtype=torch.bool)
        kwargs = dict(channel_order=CHANNELS, environment=torch.zeros(1, 13, 100, 100),
                      environment_valid=torch.ones(1, 13, 100, 100, dtype=torch.bool),
                      environment_grid=grid, environment_keys=MEE_V13_KEYS)
        reference = b4(x, native_valid, **kwargs)
        for kind in ('B5', 'B6'):
            pack = pack_terrain(features, kind=kind, region=region, expected_grid=grid, source_sha256='a'*64, aggregation_rule='SYNTHETIC_TARGET_ONLY')
            scalers = fit_static_train_scalers(pack, fit_role='Train', fit_years=[2023], train_region=region, population_sha256='b'*64)
            candidate = StaticTerrainCandidate(b4, pack, scalers, kind=kind, width=16)
            output = candidate(x, native_valid, **kwargs)
            self.assertTrue(torch.equal(output.rain_logit, reference.rain_logit))
            self.assertTrue(torch.equal(output.conditional_quantiles_log, reference.conditional_quantiles_log))


class TailTests(unittest.TestCase):
    def test_real_rain_boundaries_coverage_and_sufficient_statistics(self):
        y = np.array([0., .1, 1., 20., 30., 50., 51.], dtype=np.float32)
        q = np.broadcast_to(np.log1p(y.astype(float)), (32, 7)).copy()
        q[:, 4:] -= .2
        v = np.ones(7, bool)
        d = TailDiagnostics()
        d.add('2024-05-01T00:00:00Z', y, q, v)
        r = d.finish()
        self.assertEqual(sum(x['n_rain'] for x in r['strata']), 5)
        self.assertEqual(r['strata'][4]['n_rain'], 1)  # 30 belongs to (20,30]
        self.assertEqual(r['strata'][5]['n_rain'], 1)  # 50 belongs to (30,50]
        self.assertEqual(r['strata'][4]['q32_coverage'], 0.)
        self.assertEqual(r['strata'][0]['q32_coverage'], 1.)
        with self.assertRaises(ValueError):
            d.add('2024-05-01T00:00:00Z', y, q, v)
        with self.assertRaises(ValueError):
            TailDiagnostics().add('2025-01-01T00:00:00Z', y, q, v)


class AuthorizationTests(unittest.TestCase):
    def test_historical_or_incomplete_authorization_never_grants_b2(self):
        proposal = dict(proposal_sha256='a'*64, budget=dict(logical_source_bytes=123, logical_source_read_instances=5))
        for approval in ({}, dict(approved_by_researcher=False), dict(approved_by_researcher=True, model='B3', seed=2029)):
            with self.assertRaises(PermissionError):
                validate_authorization(approval, proposal, current_commit='b'*40)

    def test_update_intent_uncertainty_and_cap_stop(self):
        folder = REPO_ROOT/'tests/research_readiness/.local'/uuid.uuid4().hex
        folder.mkdir(parents=True)
        ledger = B2Ledger(folder/'updates.sqlite', dict(scope='SYNTHETIC_NO_OPTIMIZER'))
        try:
            ledger.reserve(1)
            with self.assertRaises(PermissionError):
                ledger.reserve(2)
            ledger.returned(1)
            with self.assertRaises(RuntimeError):
                ledger.returned(1)
            with ledger.db:
                ledger.db.executemany("INSERT INTO updates VALUES (?,'RETURNED')", [(u,) for u in range(2, 4321)])
            with self.assertRaises(PermissionError):
                ledger.reserve(4321)
        finally:
            ledger.db.close()
        with self.assertRaises(PermissionError):
            B2Ledger(folder/'updates.sqlite', {})

    def test_paired_results_refuse_population_or_mask_drift(self):
        import copy
        metrics = dict(brier=.2, auroc=.8, average_precision=.5, conditional_pinball=.1, q32_coverage=.9, q32_signed_bias=-.084375, n_valid=3430)
        b3 = dict(source_identity={'population':'A'}, population_ids_sha256='x', partition_sha256='y',
                  groups={'all':dict(ids_sha='z', summary=metrics)})
        b2 = copy.deepcopy(b3)
        b2['groups']['all']['summary']['brier'] = .1
        self.assertAlmostEqual(difference(b3, b2)['groups']['all']['brier'], -.1)
        # Exercise the actual private receipt schema, rather than only the
        # public extract's convenience q32_coverage field.
        for receipt in (b3, b2):
            s = receipt['groups']['all']['summary']
            s['coverage'] = [s.pop('q32_coverage')]*32
        self.assertAlmostEqual(difference(b3, b2)['groups']['all']['q32_coverage'], 0.)
        b2['partition_sha256'] = 'different mask'
        with self.assertRaises(ValueError):
            difference(b3, b2)


if __name__ == '__main__':
    unittest.main()
