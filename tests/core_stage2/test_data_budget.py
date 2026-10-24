import unittest
from pathlib import Path
import uuid
import numpy as np
import torch
from netCDF4 import Dataset
import test_stage2 as base
from yuntapr.experimental.core_innovation.stage2 import CHANNELS, MEE_KEYS
from yuntapr.experimental.core_innovation.stage2.population import read_seven_band, prepare_b3_scene
from yuntapr.experimental.core_innovation.stage2.environment import EnvironmentScaler, prepare_mee
from yuntapr.experimental.core_innovation.stage2.dote_v13 import complete_dote
from yuntapr.experimental.core_innovation.stage2.fusion import paired_fusion_candidates
from yuntapr.experimental.core_innovation.stage2.budget import paired_budget
from yuntapr.experimental.core_innovation.gfs import EnvironmentFrame, Field, ForecastIdentity
from yuntapr.experimental.core_innovation.grid import GridSpec
from yuntapr.experimental.core_innovation.multispectral import TrainNormalization
from yuntapr.spatial.sp04_mapping import load_sp04


class AdditionalTests(unittest.TestCase):
    def test_gfs_canonical_pwat_unit_connects_to_train_scaler(self):
        g = GridSpec([26., 25., 24.], [101., 102., 103.]); b = base.binding()
        identity = ForecastIdentity(b.analysis, base.timedelta(0), b.analysis)
        units = ('kg m-2', 'J/kg', 'K', 'K', '%', '%', 'm/s', 'm/s', 'm/s', 'm/s', 'Pa')
        fields = {}; scalers = {}
        for k, unit in zip(MEE_KEYS, units):
            level = 85000. if '850' in k else 70000. if '700' in k else None
            quantity = ('surface_pressure' if k == 'ps' else 'precipitable_water' if k == 'pwat'
                        else 'temperature' if k.startswith('temperature') else 'relative_humidity' if k.startswith('relative')
                        else k[0] if k[0] in ('u', 'v') else 'cape')
            fields[k] = Field(np.full(g.shape, 80000. if k == 'ps' else 10.), np.ones(g.shape, bool), quantity, unit, level)
            scalers[k] = EnvironmentScaler(k, 0., 1., unit, (2023,), 'Train', 'synthetic_population')
        x, mask, keys = prepare_mee(EnvironmentFrame(identity, g, fields, 'retrospective', ()), target_grid=g, scalers=scalers)
        self.assertEqual(keys, MEE_KEYS); self.assertTrue(np.isfinite(x).all())
        self.assertFalse(mask[2].any()); self.assertTrue(mask[3].all()); self.assertTrue((x[2] == 0).all())
        with self.assertRaises(ValueError): EnvironmentScaler('pwat', 0, 1, 'kg m-2', (2024,), 'Train', 'bad')

    def test_b3_connected_order_and_frozen_b13_scaling(self):
        row, frames = base.PopulationTests().row_and_evidence()
        grid = GridSpec([26., 25., 24.], [101., 102., 103.])
        ordered = [frames[row[f'slot_{i}_nominal']] for i in range(6)]
        for f in ordered: f['native_grid_id'] = grid.identity
        x = np.full((6, 7, 3, 3), 280., np.float32); mask = np.ones_like(x, bool)
        stats = {c: TrainNormalization(c, 270., 10., 'K', (2023,), 'Train', 0, 'synthetic') for c in CHANNELS}
        stats['B13'] = TrainNormalization('B13', 260., 20., 'K', (2023,), 'Train', 0, 'frozen_B13')
        out = prepare_b3_scene(row, x, mask, ordered, normalization=stats, native_grid=grid)
        flat, valid = out.flatten_time_channels(); self.assertEqual(flat.shape, (1, 42, 3, 3))
        self.assertTrue((flat == 1).all()); self.assertTrue(valid.all())
        with self.assertRaises(ValueError): prepare_b3_scene(row, x, mask, ordered[::-1], normalization=stats, native_grid=grid)

    def test_b7_b8_share_projection_initialization_and_active_count(self):
        a, b = paired_fusion_candidates(feature_channels=[48, 96, 192, 256], gfs_channels=[11]*4,
            terrain_channels=[8]*4, projection_width=16, modulation_limit=.5)
        self.assertEqual(sum(p.numel() for p in a.parameters()), sum(p.numel() for p in b.parameters()))
        for key, value in a.gfs.state_dict().items(): self.assertTrue(torch.equal(value, b.gfs.state_dict()[key]))
        for key, value in a.terrain.state_dict().items(): self.assertTrue(torch.equal(value, b.terrain.state_dict()[key]))

    def test_independent_budget_rounding_no_inherited_allowance(self):
        b = paired_budget(train_population=5, dev_population=3, epochs=2, physical_batch=2, validation_batch=2)
        self.assertEqual(b['new_independent_optimizer_attempt_cap'], 12)
        self.assertEqual(b['validation_forward_batches'], 8)
        self.assertEqual(b['inherited_seed2027_budget_used'], 0); self.assertEqual(b['replay_allowance'], 0)

    def test_seven_band_actual_reader_packing_grid_missing_and_2025_guard(self):
        mapping = load_sp04(); root = Path(__file__).resolve().parents[2]/'tests/core_stage2/.local'/uuid.uuid4().hex
        root.mkdir(parents=True)
        name = 'NC_H09_20230501_0500_R21_FLDK.06001_06001.nc'
        for folder, channels in (('complete', CHANNELS), ('missing', CHANNELS[:-1])):
            sub = root/folder; sub.mkdir(); ds = Dataset('synthetic.nc', 'w', format='NETCDF4', memory=16*1024**2)
            ds.createDimension('latitude', 501); ds.createDimension('longitude', 501)
            for axis in ('latitude', 'longitude'):
                var = ds.createVariable(axis, 'f4', (axis,)); var[:] = mapping.axes['native_lat' if axis == 'latitude' else 'native_lon']
            for key, seconds in (('start_time', 41.), ('end_time', 579.)):
                var = ds.createVariable(key, 'f8'); var.units = 'seconds since 2023-05-01 05:00:00'; var.assignValue(seconds)
            for channel in channels:
                var = ds.createVariable('tbb_'+channel[1:], 'i2', ('latitude', 'longitude'), fill_value=-32768)
                var.set_auto_maskandscale(False); var.units = 'K'; var.valid_min = np.int16(-30000); var.valid_max = np.int16(30000)
                var.scale_factor = np.float32(.01); var.add_offset = np.float32(273.15); var[:] = 100
            path = sub/name; path.write_bytes(ds.close())
            if folder == 'complete':
                x, valid, evidence = read_seven_band(path, nominal='2023-05-01T05:00:00Z', mapping=mapping)
                self.assertEqual(x.shape, (7, 501, 501)); self.assertTrue(valid.all()); self.assertEqual(evidence['full_valid'], [True]*7)
                self.assertAlmostEqual(float(x[0, 0, 0]), float(np.float32(273.15)+np.float32(1.)), places=5)
            else:
                with self.assertRaisesRegex(ValueError, 'Required band missing'): read_seven_band(path, nominal='2023-05-01T05:00:00Z', mapping=mapping)
        with self.assertRaises(PermissionError): read_seven_band(root/'never_open_2025.nc', nominal='2025-05-01T05:00:00Z', mapping=mapping)


if __name__ == '__main__': unittest.main()
