"""Small artificial-array CPU checks, with no model/data/weight/cache access."""
from datetime import datetime, timedelta, timezone
import inspect
import unittest

import numpy as np

from yuntapr.experimental.core_innovation.grid import GridSpec
from yuntapr.experimental.core_innovation.terrain import TerrainFeatures
from yuntapr.experimental.core_innovation.dote import dote_proxy
from yuntapr.experimental.core_innovation.stage2.dote_v13 import complete_dote

from yuntapr.experimental.research_readiness.dote_control_candidates import (
    CHANNELS, PRESSURES_PA, fixed_wind_direction, scene_random_rotation,
    scene_rotation_degrees, remove_moisture_numbers,
    select_pressure_level_numbers, reject_post_mask_unmasking,
    reject_unbound_specific_humidity,
)


class DoteControlCandidateTests(unittest.TestCase):
    def test_control_winds_drive_existing_windward_leeward_crosswind_formulas(self):
        # Known artificial east-facing slope: integration of the new wind
        # control with the unchanged physical proxy and W/L/M implementation.
        grid = GridSpec([25., 24.], [101., 102.])
        z = np.zeros((2, 2)); good = np.ones((2, 2), dtype=bool)
        terrain = TerrainFeatures(grid, z, good, np.ones_like(z), z,
                                  good, z, z, good)
        u = np.full((2, 2, 2), 3.); v = np.full_like(u, 4.)
        mask = np.ones_like(u, dtype=bool)
        ps = np.full((2, 2), 100000.); ps[0, 0] = 85000.
        moisture_good = good.copy(); moisture_good[1, 1] = False
        for angle, expected_o in ((0., 5.), (180., -5.), (90., 0.)):
            with self.subTest(angle=angle):
                wind = fixed_wind_direction(u, v, mask,
                    direction_degrees=angle, **self.kwargs())
                proxy = dote_proxy(terrain, wind.u_east, wind.v_north,
                    wind.valid, np.array([850., 700.]), ps, good,
                    wind_grid=grid, wind_unit='m/s', pressure_unit='hPa',
                    surface_pressure_unit='Pa')
                result = complete_dote(proxy, np.full((2, 2), 20.),
                    moisture_good, pwat_grid=grid, pwat_unit='kg m-2',
                    pwat_reference_kg_m2=10.,
                    reference_provenance='ARTIFICIAL_SCALE_NOT_TRAIN_ESTIMATE',
                    moisture_basis='windward_W')
                np.testing.assert_allclose(result.O[result.valid], expected_o,
                                           atol=1e-14)
                np.testing.assert_allclose(result.W[result.valid],
                                           max(expected_o, 0.), atol=1e-14)
                np.testing.assert_allclose(result.L[result.valid],
                                           max(-expected_o, 0.), atol=1e-14)
                np.testing.assert_allclose(result.M[result.moisture_valid],
                                           2.*max(expected_o, 0.), atol=1e-14)
                self.assertFalse(result.valid[0, 0, 0])  # p_level == p_surface
                self.assertTrue(result.valid[1, 0, 0])
                self.assertTrue(result.valid[:, 1, 1].all())
                self.assertFalse(result.moisture_valid[:, 1, 1].any())

    def winds(self):
        u = np.array([[[3., 0.], [-2., 8.]], [[1., -4.], [0., 2.]]])
        v = np.array([[[4., 0.], [1., -6.]], [[2., 3.], [0., 1.]]])
        valid = np.ones_like(u, dtype=bool)
        valid[0, 0, 1] = False
        u[0, 0, 1] = np.nan
        return u, v, valid

    def kwargs(self):
        return dict(unit='m/s', pressure_levels_pa=PRESSURES_PA)

    def scene(self, sid='artificial-A'):
        return dict(scene_id=sid, scene_time=datetime(2024, 6, 1, tzinfo=timezone.utc),
                    control_seed=17)

    def numbers(self):
        x = np.arange(1, 33, dtype=np.float32).reshape(8, 2, 2)
        m = np.ones_like(x, dtype=bool)
        m[6, 0, 0] = False
        x[6, 0, 0] = np.nan
        return x, m

    def test_fixed_east_and_north_preserve_speed_masks_and_inputs(self):
        u, v, m = self.winds()
        before = (u.copy(), v.copy(), m.copy())
        east = fixed_wind_direction(u, v, m, direction_degrees=0, **self.kwargs())
        north = fixed_wind_direction(u, v, m, direction_degrees=90, **self.kwargs())
        speed = np.hypot(u[m], v[m])
        np.testing.assert_allclose(east.u_east[m], speed)
        np.testing.assert_allclose(east.v_north[m], 0, atol=1e-14)
        np.testing.assert_allclose(north.u_east[m], 0, atol=1e-14)
        np.testing.assert_allclose(north.v_north[m], speed)
        for result in (east, north):
            np.testing.assert_array_equal(result.valid, m)
            self.assertTrue(np.isnan(result.u_east[~m]).all())
            self.assertTrue(np.isnan(result.v_north[~m]).all())
        for a, b in zip((u, v, m), before):
            np.testing.assert_array_equal(a, b)
        east.valid[0, 1, 1] = False
        self.assertTrue(m[0, 1, 1])

    def test_fixed_direction_rejects_hidden_units_shape_and_bad_angle(self):
        u, v, m = self.winds()
        for angle in (-1, 360, np.nan, np.inf, True):
            with self.subTest(angle=angle), self.assertRaises(ValueError):
                fixed_wind_direction(u, v, m, direction_degrees=angle, **self.kwargs())
        for change in (dict(unit='knots'), dict(pressure_levels_pa=(850, 700)),
                       dict(pressure_levels_pa=(70000, 85000))):
            with self.assertRaises(ValueError):
                fixed_wind_direction(u, v, m, direction_degrees=0,
                                     **(self.kwargs() | change))
        with self.assertRaises(ValueError):
            fixed_wind_direction(u[0], v[0], m[0], direction_degrees=0, **self.kwargs())

    def test_random_rotation_preserves_speed_and_cross_level_dot_products(self):
        u, v, m = self.winds()
        before = (u.copy(), v.copy(), m.copy())
        result = scene_random_rotation(u, v, m, **self.scene(), **self.kwargs())
        np.testing.assert_allclose(np.hypot(result.u_east[m], result.v_north[m]),
                                   np.hypot(u[m], v[m]), rtol=1e-14, atol=1e-14)
        joint = m[0] & m[1]
        original = u[0]*u[1] + v[0]*v[1]
        rotated = result.u_east[0]*result.u_east[1] + result.v_north[0]*result.v_north[1]
        np.testing.assert_allclose(rotated[joint], original[joint], rtol=1e-14, atol=1e-14)
        np.testing.assert_array_equal(result.valid, m)
        theta = np.deg2rad(result.metadata['angle_degrees'])
        recovered_u = result.u_east*np.cos(theta) + result.v_north*np.sin(theta)
        recovered_v = -result.u_east*np.sin(theta) + result.v_north*np.cos(theta)
        np.testing.assert_allclose(recovered_u[m], u[m], rtol=1e-14, atol=1e-14)
        np.testing.assert_allclose(recovered_v[m], v[m], rtol=1e-14, atol=1e-14)
        for a, b in zip((u, v, m), before):
            np.testing.assert_array_equal(a, b)
        self.assertFalse(result.metadata['conditional_randomization_test'])

    def test_random_rotation_is_order_independent_does_not_consume_global_rng(self):
        u, v, m = self.winds()
        np.random.seed(29)
        state = np.random.get_state()
        a = scene_random_rotation(u, v, m, **self.scene(), **self.kwargs())
        scene_random_rotation(u, v, m, **self.scene('artificial-B'), **self.kwargs())
        b = scene_random_rotation(u, v, m, **self.scene(), **self.kwargs())
        np.testing.assert_array_equal(a.u_east, b.u_east)
        np.testing.assert_array_equal(a.v_north, b.v_north)
        after = np.random.get_state()
        self.assertEqual(state[0], after[0])
        np.testing.assert_array_equal(state[1], after[1])
        self.assertEqual(state[2:], after[2:])
        self.assertNotEqual(a.metadata['angle_degrees'],
                            scene_rotation_degrees(**self.scene('artificial-B')))
        self.assertNotEqual(a.metadata['angle_degrees'],
                            scene_rotation_degrees(**(self.scene() | dict(control_seed=18))))

    def test_scene_identity_is_timezone_canonical_and_no_label_model_seed_api(self):
        a = self.scene()
        local = a['scene_time'].astimezone(timezone(timedelta(hours=8)))
        self.assertEqual(scene_rotation_degrees(**a),
                         scene_rotation_degrees(**(a | dict(scene_time=local))))
        for field in ('model_seed', 'labels', 'rate', 'outcome'):
            self.assertNotIn(field, inspect.signature(scene_rotation_degrees).parameters)
            with self.assertRaises(TypeError):
                scene_rotation_degrees(**a, **{field: 1})
        for change, error in ((dict(scene_id=' '), ValueError),
                              (dict(scene_time=datetime(2024, 6, 1)), ValueError),
                              (dict(scene_time=datetime(2022, 6, 1, tzinfo=timezone.utc)), PermissionError),
                              (dict(control_seed=True), ValueError),
                              (dict(control_seed=-1), ValueError)):
            with self.assertRaises(error):
                scene_rotation_degrees(**(a | change))

    def test_remove_m_preserves_ow_l_masks_and_inputs_and_discloses_capacity(self):
        x, m = self.numbers()
        before = x.copy()
        result = remove_moisture_numbers(x, m, channel_order=CHANNELS)
        np.testing.assert_array_equal(result.values[:6], x[:6])
        self.assertTrue((result.values[6:][m[6:]] == 0).all())
        self.assertTrue(np.isnan(result.values[6:][~m[6:]]).all())
        np.testing.assert_array_equal(result.valid, m)
        np.testing.assert_array_equal(x, before)
        self.assertFalse(result.metadata['effective_capacity_equivalence'])
        self.assertEqual(result.metadata['width16_structurally_zero_loss_gradient_weights'], 32)
        self.assertEqual(result.metadata['interpretation'],
                         'FEATURE_AVAILABILITY_CONDITIONAL_ON_REAL_MASKS')
        result.valid[0, 0, 0] = False
        self.assertTrue(m[0, 0, 0])

    def test_select_level_keeps_interleaved_channels_and_both_real_masks(self):
        x, m = self.numbers()
        for level, keep, remove in ((85000, (0, 2, 4, 6), (1, 3, 5, 7)),
                                    (70000, (1, 3, 5, 7), (0, 2, 4, 6))):
            with self.subTest(level=level):
                result = select_pressure_level_numbers(x, m, level_pa=level, channel_order=CHANNELS)
                np.testing.assert_array_equal(result.values[list(keep)], x[list(keep)])
                self.assertTrue((result.values[list(remove)][m[list(remove)]] == 0).all())
                np.testing.assert_array_equal(result.valid, m)
                self.assertEqual(result.metadata['width16_structurally_zero_loss_gradient_weights'], 64)
                self.assertFalse(result.metadata['removed_level_or_moisture_mask_information'])
        with self.assertRaises(ValueError):
            select_pressure_level_numbers(x, m, level_pa=850, channel_order=CHANNELS)

    def test_numeric_contract_rejects_wrong_order_masks_and_nonfinite_valid(self):
        x, m = self.numbers()
        with self.assertRaises(ValueError):
            remove_moisture_numbers(x, m, channel_order=CHANNELS[::-1])
        with self.assertRaises(ValueError):
            remove_moisture_numbers(x, m.astype(np.uint8), channel_order=CHANNELS)
        x[0, 0, 0] = np.nan
        with self.assertRaises(ValueError):
            remove_moisture_numbers(x, m, channel_order=CHANNELS)

    def test_no_unmasking_or_unbound_q_substitution_is_available(self):
        with self.assertRaisesRegex(PermissionError, 'cannot be reconstructed'):
            reject_post_mask_unmasking()
        with self.assertRaisesRegex(NotImplementedError, 'does not derive'):
            reject_unbound_specific_humidity()


if __name__ == '__main__':
    unittest.main()
