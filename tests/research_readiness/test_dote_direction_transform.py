"""Small artificial scene/frame checks; no model, data loader or file payload."""
import copy
from dataclasses import replace
from datetime import datetime, timedelta, timezone
import unittest
from unittest.mock import patch

import numpy as np

from yuntapr.experimental.core_innovation.gfs import EnvironmentFrame, Field, ForecastIdentity
from yuntapr.experimental.core_innovation.grid import GridSpec
from yuntapr.experimental.core_innovation.stage3.planning import digest
from yuntapr.experimental.core_innovation.terrain import TerrainFeatures
from yuntapr.experimental.research_readiness.dote_direction_transform import (
    DirectionControl, DirectionDoteTransform, SceneManifestLookup,
)


def manifest(rows=None):
    if rows is None:
        rows = [dict(sample_id='2024-06-01T11:30:00Z',
                     window_start='2024-06-01T11:30:00Z', analysis_time='2024-06-01T12:00:00Z')]
    body = dict(scene_records=rows, purpose='ARTIFICIAL_METADATA_ONLY')
    return dict(body, manifest_sha256=digest(body))


def lookup(m=None, ids=None, role='ANALYSIS_TIME_UTC'):
    m = manifest() if m is None else m
    ids = [r['sample_id'] for r in m['scene_records']] if ids is None else ids
    return SceneManifestLookup(m, accepted_ids=ids, expected_manifest_sha256=m['manifest_sha256'],
                               canonical_time_role=role)


def frame(grid=None):
    grid = GridSpec([25., 24.], [101., 102.]) if grid is None else grid
    shape = grid.shape
    def f(value, quantity, unit, level=None):
        return Field(np.full(shape, value, dtype=float), np.ones(shape, dtype=bool), quantity, unit, level)
    fields = {f'{a}{p}': f(3. if a == 'u' else 4., a, 'm/s', p*100.)
              for a in ('u', 'v') for p in (850, 700)}
    fields.update(ps=f(100000., 'surface_pressure', 'Pa'),
                  pwat=f(20., 'precipitable_water', 'kg m-2'),
                  cape=f(7., 'cape', 'J/kg'))
    analysis = datetime(2024, 6, 1, 12, tzinfo=timezone.utc)
    return EnvironmentFrame(ForecastIdentity(analysis-timedelta(hours=6), timedelta(hours=6), analysis),
                            grid, fields, 'retrospective', ({'source': 'ARTIFICIAL'},))


def terrain(grid):
    z = np.zeros(grid.shape); good = np.ones(grid.shape, dtype=bool)
    return TerrainFeatures(grid, z, good, np.ones(grid.shape), z, good, z, z, good)


def transform(f, *, t=None, scene_lookup=None, control=None):
    return DirectionDoteTransform(terrain(f.grid) if t is None else t,
        lookup() if scene_lookup is None else scene_lookup,
        DirectionControl('FIXED_DIRECTION', direction_degrees=0.) if control is None else control,
        pwat_reference_kg_m2=10., reference_provenance='ARTIFICIAL_NOT_FITTED',
        moisture_basis='windward_W', velocity_reference_m_s=1.)


class DoteDirectionTransformTests(unittest.TestCase):
    def test_manifest_digest_exact_identity_explicit_time_role_and_snapshot(self):
        m = manifest(); original = copy.deepcopy(m); a = lookup(m)
        local = datetime(2024, 6, 1, 20, tzinfo=timezone(timedelta(hours=8)))
        b = a.resolve(local)
        self.assertEqual(b.sample_id, m['scene_records'][0]['sample_id'])
        self.assertEqual(b.canonical_scene_time, b.analysis)
        self.assertEqual(lookup(m, role='WINDOW_START_UTC').resolve(local).canonical_scene_time,
                         b.window_start)
        m['scene_records'][0]['sample_id'] = 'changed after construction'
        self.assertEqual(a.resolve(local), b)
        with self.assertRaises(TypeError):
            a._by_analysis[local] = b
        self.assertEqual(original['manifest_sha256'], a.manifest_sha256)

    def test_reject_corrupt_missing_duplicate_ambiguous_or_2025_scene_metadata(self):
        m = manifest(); corrupt = copy.deepcopy(m); corrupt['scene_records'][0]['analysis_time'] = '2024-06-01T12:30:00Z'
        with self.assertRaisesRegex(ValueError, 'fingerprint'):
            lookup(corrupt)
        row = m['scene_records'][0]
        cases = [([row, row], ValueError),
                 ([dict(row, analysis_time='2024-06-01T12:30:00Z')], ValueError),
                 ([dict(row, sample_id='2024-06-01T11:00:00Z')], ValueError),
                 ([dict(row, window_start='2024-06-01T11:30:00')], ValueError),
                 ([{k: v.replace('2024', '2025') for k, v in row.items()}], PermissionError)]
        for rows, error in cases:
            with self.subTest(rows=rows), self.assertRaises(error):
                lookup(manifest(rows))
        for ids in ([], [row['sample_id']]*2, ['2024-06-01T10:00:00Z']):
            with self.subTest(ids=ids), self.assertRaises(ValueError):
                lookup(m, ids=ids)
        with self.assertRaises(ValueError):
            lookup(m, role='GUESS_FROM_FRAME')

    def test_fixed_east_recomputes_owlm_keeps_real_support_and_all_input_fields(self):
        f = frame(); f.fields['ps'].values[0, 0] = 85000.
        f.fields['pwat'].valid[1, 1] = False
        before = copy.deepcopy(f)
        result = transform(f).physical(f)
        np.testing.assert_allclose(result.O[result.valid], 5.)
        np.testing.assert_allclose(result.W[result.valid], 5.)
        np.testing.assert_allclose(result.L[result.valid], 0.)
        np.testing.assert_allclose(result.M[result.moisture_valid], 10.)
        self.assertFalse(result.valid[0, 0, 0])
        self.assertTrue(result.valid[1, 0, 0])
        self.assertFalse(result.moisture_valid[:, 1, 1].any())
        x, mask = transform(f)(f)
        self.assertEqual(x.shape, (8, 2, 2)); self.assertEqual(x.dtype, np.float32)
        self.assertTrue((x[~mask] == 0.).all())
        for key in f.fields:
            np.testing.assert_array_equal(f.fields[key].values, before.fields[key].values)
            np.testing.assert_array_equal(f.fields[key].valid, before.fields[key].valid)
        self.assertEqual(f.provenance, before.provenance)

    def test_control_is_after_bilinear_mapping_not_rotation_of_native_winds(self):
        source = GridSpec([26., 25., 24.], [100., 101., 102.])
        target = GridSpec([25.5, 24.5], [100.5, 101.5]); f = frame(source)
        for p in (850, 700):
            f.fields[f'u{p}'].values[:] = [3., -3., 3.]
        result = transform(f, t=terrain(target)).physical(f)
        # Mapped original vectors are (0,4): speed=4, whereas transforming
        # each native (3,4)/(-3,4) before mapping would incorrectly give 5.
        self.assertTrue(result.valid.all())
        np.testing.assert_allclose(result.O, 4., atol=1e-14)
        np.testing.assert_allclose(result.M, 8., atol=1e-14)
        f.fields['ps'].values[0, 0] = 85000.
        masked = transform(f, t=terrain(target)).physical(f)
        self.assertFalse(masked.valid[0, 0, 0])  # native invalid corner is not restored
        self.assertTrue(masked.valid[1, 0, 0])

    def test_random_scene_mapping_is_shared_across_call_order_and_preserves_rng(self):
        f = frame(); second = copy.deepcopy(f)
        second = replace(second, identity=ForecastIdentity(f.identity.init+timedelta(hours=6),
            f.identity.lead, f.identity.valid+timedelta(hours=6)))
        rows = manifest()['scene_records'] + [dict(sample_id='2024-06-01T17:30:00Z',
            window_start='2024-06-01T17:30:00Z', analysis_time='2024-06-01T18:00:00Z')]
        m = manifest(rows); a = transform(f, scene_lookup=lookup(m),
            control=DirectionControl('SCENE_RANDOM_ROTATION', control_seed=17))
        b = transform(f, scene_lookup=lookup(m, ids=[r['sample_id'] for r in rows][::-1]),
            control=DirectionControl('SCENE_RANDOM_ROTATION', control_seed=17))
        np.random.seed(2029); state = np.random.get_state()
        first = a.physical(f); a.physical(second); again = b.physical(f)
        np.testing.assert_array_equal(first.O, again.O)
        angle = first.definition['direction_control']['angle_degrees']
        np.testing.assert_allclose(first.O, 3*np.cos(np.deg2rad(angle))-4*np.sin(np.deg2rad(angle)))
        after = np.random.get_state()
        self.assertEqual(state[0], after[0]); np.testing.assert_array_equal(state[1], after[1])
        self.assertEqual(state[2:], after[2:])
        self.assertEqual(first.definition['direction_control']['scene_id'], rows[0]['sample_id'])

    def test_reject_frame_identity_units_and_invalid_control_parameters(self):
        f = frame(); t = transform(f)
        other_time = ForecastIdentity(f.identity.init+timedelta(hours=6), f.identity.lead,
                                      f.identity.valid+timedelta(hours=6))
        bad_frames = [replace(f, mode='operational'), replace(f, identity=other_time),
            replace(f, identity=ForecastIdentity(f.identity.valid-timedelta(hours=3),
                                                timedelta(hours=3), f.identity.valid))]
        for key, change in [('u850', dict(unit='knots')), ('u700', dict(level_pa=85000.)),
                            ('ps', dict(unit='hPa')), ('pwat', dict(quantity='cape'))]:
            fields = dict(f.fields); fields[key] = replace(fields[key], **change)
            bad_frames.append(replace(f, fields=fields))
        for bad in bad_frames:
            with self.subTest(bad=bad.mode), self.assertRaises(ValueError):
                t(bad)
        for args in [('SCENE_RANDOM_ROTATION', True, None), ('SCENE_RANDOM_ROTATION', None, None),
                     ('FIXED_DIRECTION', 17, 0.), ('FIXED_DIRECTION', None, 360.),
                     ('FIXED_DIRECTION', None, None), ('GUESS', None, None)]:
            with self.subTest(args=args), self.assertRaises(ValueError):
                DirectionControl(*args)

    def test_projection_support_change_and_float32_overflow_stop_without_clipping(self):
        f = frame(); t = terrain(f.grid)
        t = replace(t, east_gradient=np.full(f.grid.shape, 1.5), north_gradient=np.full(f.grid.shape, 1.5))
        for p in (850, 700):
            f.fields[f'u{p}'].values[:] = 1.e308; f.fields[f'v{p}'].values[:] = -1.e308
        with self.assertRaisesRegex(FloatingPointError, 'support changed'):
            transform(f, t=t).physical(f)
        f = frame()
        for p in (850, 700):
            f.fields[f'u{p}'].values[:] = 1.e39; f.fields[f'v{p}'].values[:] = 0.
        with self.assertRaisesRegex(FloatingPointError, 'float32 conversion overflow'):
            transform(f)(f)

    def test_frame_callable_needs_no_file_access_or_reader_registration(self):
        f = frame(); candidate = transform(f)
        with patch('builtins.open', side_effect=AssertionError('Unexpected source access')):
            values, valid = candidate(f)
        self.assertEqual(valid.dtype, np.bool_); self.assertTrue(np.isfinite(values).all())
        metadata = candidate.physical(f).definition['direction_control']
        self.assertFalse(metadata['default_reader_registered'])
        self.assertFalse(metadata['experiment_ready'])


if __name__ == '__main__':
    unittest.main()
