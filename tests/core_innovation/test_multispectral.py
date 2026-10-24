from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
import unittest

import numpy as np

from yuntapr.experimental.core_innovation.grid import GridSpec
from yuntapr.experimental.core_innovation.multispectral import TrainNormalization, prepare_multispectral


class MultispectralTests(unittest.TestCase):
    def setUp(self):
        self.analysis = datetime(2024, 7, 1, 1, 0, tzinfo=timezone.utc)
        self.offsets = (20, 10)
        self.nominal = [[self.analysis - timedelta(minutes=offset) for offset in self.offsets]]
        self.starts = [[value + timedelta(seconds=30) for value in self.nominal[0]]]
        self.ends = [[value + timedelta(minutes=9) for value in self.nominal[0]]]
        self.grid = GridSpec(np.array([26., 25.]), np.array([100., 101., 102.]))
        self.values = np.ones((1, 2, 2, 2, 3), dtype=np.float32) * 280
        self.values[:, :, 1] = 260
        self.valid = np.ones(self.values.shape, dtype=bool)
        self.normalizers = {
            'B13': TrainNormalization('B13', 270., 10., 'K', (2023,), 'Train', 0, 'synthetic_train_B13'),
            'B08': TrainNormalization('B08', 250., 5., 'K', (2023,), 'Train', 0, 'synthetic_train_B08'),
        }

    def call(self, **changes):
        args = dict(values=self.values, source_valid=self.valid, source_channels=('B13', 'B08'),
                    selected_channels=('B08', 'B13'), units={'B13': 'K', 'B08': 'K'},
                    normalization=self.normalizers, nominal_times=self.nominal,
                    obs_start_times=self.starts, obs_end_times=self.ends, analysis_times=[self.analysis],
                    expected_offsets_before_analysis_minutes=self.offsets,
                    source_grid=self.grid, expected_grid=self.grid, missing_policy='reject')
        args.update(changes)
        return prepare_multispectral(**args)

    def test_explicit_channel_order_shared_slots_and_flatten(self):
        result = self.call()
        self.assertEqual(result.channels, ('B08', 'B13'))
        self.assertTrue((result.values[:, :, 0] == 2).all())
        self.assertTrue((result.values[:, :, 1] == 1).all())
        values, masks = result.flatten_time_channels()
        self.assertEqual(values.shape, (1, 4, 2, 3))
        self.assertTrue((values[:, 0] == 2).all())
        self.assertTrue((values[:, 1] == 1).all())
        self.assertTrue(masks.all())
        self.assertEqual(result.values.dtype, np.float32)
        self.assertFalse(result.historical_operational_availability_proven)

    def test_partial_and_fill_require_explicit_masked_neutral(self):
        self.values[0, 0, 1, 0, 0] = np.nan
        self.valid[0, 0, 1, 0, 0] = False
        with self.assertRaisesRegex(ValueError, 'missing pixels'):
            self.call()
        result = self.call(missing_policy='masked_neutral')
        self.assertFalse(result.valid[0, 0, 0, 0, 0])
        self.assertEqual(result.values[0, 0, 0, 0, 0], 0)
        self.assertTrue(np.isfinite(result.values).all())
        with self.assertRaisesRegex(ValueError, 'Nonfinite'):
            self.call(source_valid=np.ones_like(self.valid), missing_policy='masked_neutral')

    def test_missing_channels_and_scalers_never_fallback_to_b13(self):
        with self.assertRaisesRegex(ValueError, 'unavailable'):
            self.call(selected_channels=('B16',))
        with self.assertRaisesRegex(ValueError, 'matching explicit'):
            self.call(normalization={'B13': self.normalizers['B13']})
        with self.assertRaisesRegex(ValueError, 'matching explicit'):
            self.call(units={'B13': 'K', 'B08': 'C'})

    def test_future_or_reordered_actual_intervals_fail(self):
        with self.assertRaisesRegex(ValueError, 'completed'):
            self.call(obs_end_times=[[self.ends[0][0], self.analysis + timedelta(seconds=1)]])
        with self.assertRaisesRegex(ValueError, 'intervals'):
            self.call(obs_start_times=[[self.ends[0][0] + timedelta(seconds=1), self.starts[0][1]]])
        with self.assertRaisesRegex(ValueError, 'offsets'):
            self.call(nominal_times=[self.nominal[0][::-1]])
        with self.assertRaisesRegex(ValueError, 'oldest-to-latest'):
            self.call(expected_offsets_before_analysis_minutes=(10, 20))
        with self.assertRaisesRegex(ValueError, 'intervals'):
            self.call(obs_end_times=[[self.ends[0][1], self.ends[0][0]]])

    def test_naive_time_2025_and_outside_period_fail(self):
        for date in (datetime(2025, 7, 1, 1, 0, tzinfo=timezone.utc),
                     datetime(2024, 2, 1, 1, 0, tzinfo=timezone.utc), self.analysis.replace(tzinfo=None)):
            with self.assertRaises(ValueError):
                self.call(analysis_times=[date])

    def test_grid_axis_flip_and_mask_dtype_fail(self):
        with self.assertRaisesRegex(ValueError, 'grid identity'):
            self.call(source_grid=GridSpec(self.grid.lat[::-1], self.grid.lon))
        with self.assertRaisesRegex(ValueError, 'descend'):
            ascending = GridSpec(self.grid.lat[::-1], self.grid.lon)
            self.call(source_grid=ascending, expected_grid=ascending)
        with self.assertRaisesRegex(ValueError, 'bool validity'):
            self.call(source_valid=self.valid.astype(np.uint8))

    def test_normalization_cannot_fit_validation_or_final_test(self):
        for years, role, std in (((2024,), 'Train', 1), ((2025,), 'Train', 1),
                                 ((2023,), 'Dev', 1), ((2023,), 'Train', 0)):
            with self.assertRaises(ValueError):
                TrainNormalization('B08', 250, std, 'K', years, role, 0, 'synthetic')
        years = [2023]
        stats = TrainNormalization('B08', 250., 5., 'K', years, 'Train', 0, 'synthetic')
        years.append(2024)
        self.assertEqual(stats.fit_years, (2023,))

    def test_visible_reflectance_cannot_be_declared_kelvin(self):
        with self.assertRaisesRegex(ValueError,'thermal'):
            TrainNormalization('B01',250.,5.,'K',(2023,),'Train',0,'synthetic')

    def test_all_invalid_remains_explicitly_masked_finite_neutral(self):
        result = self.call(values=np.full_like(self.values, np.nan),
                           source_valid=np.zeros_like(self.valid), missing_policy='masked_neutral')
        self.assertFalse(result.valid.any())
        self.assertTrue((result.values == 0).all())

    def test_existing_frozen_b13_artifact_explicit_adapter(self):
        root = Path(__file__).resolve().parents[2]
        path = root / 'docs/b1_scientific_freeze/runs/run_20261003T045139_110133Z/normalization_b1_2023_shared_v1.json'
        payload = path.read_bytes()
        identity = hashlib.sha256(payload).hexdigest()
        self.assertEqual(identity, '656fe7a929cbd8617b08427e8d1fa7029b26512253efb44faa576796137d4a31')
        stats = TrainNormalization.from_b1_artifact(json.loads(payload), artifact_sha256=identity)
        self.assertEqual(stats.channel, 'B13')
        self.assertEqual(stats.fit_years, (2023,))
        self.assertEqual(stats.mean, 271.60515414265217)
        self.assertEqual(stats.std, 19.93959597783802)


if __name__ == '__main__':
    unittest.main()
