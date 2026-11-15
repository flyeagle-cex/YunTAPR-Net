"""Artificial CPU checks for temporal and physical input contracts."""
import argparse
from dataclasses import replace
from datetime import datetime, timedelta, timezone
import importlib.util
import json
from pathlib import Path
import sys
import unittest
from types import SimpleNamespace
from unittest.mock import patch

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / 'src')]
from yuntapr.experimental.core_innovation.gfs import EnvironmentFrame, Field, ForecastIdentity, GFSFile
from yuntapr.experimental.core_innovation.grid import GridSpec
from yuntapr.experimental.core_innovation.stage2 import MEE_KEYS, MEE_V13_KEYS, OFFSETS
from yuntapr.experimental.core_innovation.stage2.coupling import TargetBinding
from yuntapr.experimental.core_innovation.stage2.environment import (
    EnvironmentScaler, V13_UNITS, prepare_mee, validate_physical_fields,
)
from yuntapr.experimental.research_readiness.dynamic_terrain import PhysicalDote, DoteDefinition
from yuntapr.experimental.research_readiness.static_terrain import StaticPack, B6_CHANNELS, UNITS


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--receipt', type=Path, required=True)
    args = parser.parse_args()
    checks = {}
    def rejected(name, action):
        try:
            action()
        except (ValueError, PermissionError):
            checks[name] = True
        else:
            raise AssertionError(name + ' accepted')

    now = datetime(2024, 5, 1, 6, tzinfo=timezone.utc)
    nominal = tuple(now - timedelta(minutes=offset) for offset in OFFSETS)
    binding = TargetBinding(now - timedelta(minutes=30), now, nominal, nominal,
                            tuple(t + timedelta(minutes=3) for t in nominal))
    identity = ForecastIdentity(now - timedelta(hours=6), timedelta(hours=6), now)
    assert binding.check_forecast(identity, valid_policy='valid_equals_analysis_retrospective_candidate')['lead_hours'] == 6
    checks['six_satellite_slots_and_f006_same_analysis_pass'] = True
    grid = GridSpec([24., 25.], [100., 101.])
    fields, scalers = {}, {}
    for key, unit in zip(MEE_V13_KEYS, V13_UNITS):
        quantity = {'ps': 'surface_pressure', 'pwat': 'precipitable_water', 'cape': 'cape'}.get(key, key[:-3])
        level = None if key in ('ps', 'pwat', 'cape') else float(key[-3:]) * 100.
        value = 100000. if key == 'ps' else 10.
        fields[key] = Field(np.full(grid.shape, value), np.ones(grid.shape, bool), quantity, unit, level)
        scalers[key] = EnvironmentScaler(key, 1., 2., unit, (2023,), 'Train', 'ARTIFICIAL')
    frame = EnvironmentFrame(identity, grid, fields, 'retrospective', ())
    output, valid, order = prepare_mee(frame, target_grid=grid, scalers=scalers, keys=MEE_V13_KEYS)
    mapped = frame.on_grid(grid, operator='bilinear_point_candidate')
    original, original_valid = mapped.stack(MEE_V13_KEYS)
    np.testing.assert_array_equal(valid, original_valid)
    np.testing.assert_array_equal(output, ((np.where(valid, original, 1.) - 1.) / 2.).astype(np.float32))
    assert order == MEE_V13_KEYS
    checks['valid_13_fields_preserve_original_mapping_scaling_and_masks'] = True
    old_frame = replace(frame, fields={key: fields[key] for key in MEE_KEYS})
    old_scalers = {key: scalers[key] for key in MEE_KEYS}
    old_values, old_masks, _ = prepare_mee(old_frame, target_grid=grid, scalers=old_scalers, keys=MEE_KEYS)
    np.testing.assert_array_equal(old_values, output[:11])
    np.testing.assert_array_equal(old_masks, valid[:11])
    checks['existing_11_field_interface_remains_compatible'] = True
    integer_frame = replace(frame, fields={key: replace(field, values=field.values.astype(np.int64)) for key, field in fields.items()})
    integer_values, integer_masks, _ = prepare_mee(integer_frame, target_grid=grid, scalers=scalers, keys=MEE_V13_KEYS)
    np.testing.assert_array_equal(integer_values, output)
    np.testing.assert_array_equal(integer_masks, valid)
    checks['existing_real_integer_physical_values_remain_compatible'] = True

    spec = importlib.util.spec_from_file_location('existing_gfs_fixture', ROOT / 'tests/core_innovation/test_gfs.py')
    gfs_fixture = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(gfs_fixture)
    gfs_fixture.GFSTests.setUpClass()
    decoded = gfs_fixture.read_gfs_file(gfs_fixture.GFSTests.main, gfs_fixture.IDENTITY, gfs_fixture.MAIN)
    validate_physical_fields(decoded, ('u850', 'v850', 'ps'))
    assert decoded.fields['u850'].values.dtype == np.float64
    checks['existing_gfs_decoder_synthetic_netcdf_produces_compatible_metadata'] = True
    assert 'temperature500' in MEE_V13_KEYS and fields['temperature500'].level_pa == 50000.
    checks['temperature500_is_an_existing_declared_channel'] = True

    # Exercise BatchReader.batch through the actual combine_environment and
    # TargetBinding calls. Only source I/O and multispectral arithmetic are stubs.
    from yuntapr.experimental.core_innovation.stage4 import data as batch_module
    reader = object.__new__(batch_module.BatchReader)
    sid, analysis_text = binding.window_start.isoformat(), now.isoformat()
    row = {'analysis_time': analysis_text}
    satellite, records = {}, {}
    for i, stamp in enumerate(nominal):
        text = stamp.isoformat()
        metadata = dict(nominal=text, obs_start=text, obs_end=(stamp + timedelta(minutes=3)).isoformat())
        row[f'slot_{i}_nominal'] = text
        satellite[text] = (f'satellite_{i}', metadata)
        records[f'satellite_{i}'] = (np.ones((7, 2, 2), np.float32), np.ones((7, 2, 2), bool), metadata)
    records['main'] = GFSFile(identity, grid, fields, {})
    records['thermo'] = GFSFile(identity, grid, {}, {})
    reader.plan = SimpleNamespace(rows={'Development': {sid: row}}, sat=satellite,
                                  gfs={analysis_text: {'main': 'main', 'thermo': 'thermo'}}, spectral={})
    reader.ids_by_role, reader.scene_seen = {'Development': (sid,)}, set()
    reader.region = lambda: np.ones(grid.shape, bool)
    reader._read = lambda path, decoder: records[path]
    reader.mapping, reader.native, reader.grid = None, grid, grid
    reader.plan.environment = scalers
    normalized = SimpleNamespace(flatten_time_channels=lambda: (np.ones((1, 42, 2, 2), np.float32), np.ones((1, 42, 2, 2), bool)))
    class ReachedAlignedMEE(Exception):
        pass
    def stop_at_mee(actual_frame, **kwargs):
        assert actual_frame.identity is identity
        validate_physical_fields(actual_frame, MEE_V13_KEYS)
        raise ReachedAlignedMEE()
    with patch.object(batch_module, 'prepare_multispectral', return_value=normalized), patch.object(batch_module, 'prepare_mee', side_effect=stop_at_mee):
        try:
            reader.batch('Development', [sid])
        except ReachedAlignedMEE:
            checks['reader_actual_combine_and_target_binding_reach_aligned_mee'] = True
        else:
            raise AssertionError('Aligned reader path not reached')
        records['thermo'] = replace(records['thermo'], identity=ForecastIdentity(now - timedelta(hours=3), timedelta(hours=3), now))
        rejected('reader_actual_combine_rejects_mixed_forecast_vintage', lambda: reader.batch('Development', [sid]))

    rejected('wrong_gfs_valid_time', lambda: binding.check_forecast(
        ForecastIdentity(now - timedelta(hours=5), timedelta(hours=6), now + timedelta(hours=1)),
        valid_policy='valid_equals_analysis_retrospective_candidate'))
    rejected('wrong_satellite_order', lambda: replace(binding, nominal=nominal[::-1]))
    rejected('future_satellite_observation', lambda: replace(binding, observation_end=(*binding.observation_end[:-1], now + timedelta(seconds=1))))
    for name, key, changes in (
        ('wrong_wind_quantity', 'u850', {'quantity': 'v'}),
        ('wrong_pressure_level', 'u850', {'level_pa': 70000.}),
        ('wrong_temperature_level', 'temperature500', {'level_pa': 85000.}),
        ('wrong_pwat_unit', 'pwat', {'unit': 'mm'}),
        ('wrong_pressure_unit', 'ps', {'unit': 'hPa'}),
        ('wrong_field_grid_shape', 'u700', {'values': np.ones((3, 2))}),
        ('wrong_mask_dtype', 'v700', {'valid': np.ones(grid.shape, np.float32)}),
        ('nonfinite_valid_value', 'pwat', {'values': np.full(grid.shape, np.nan)}),
    ):
        altered = dict(fields, **{key: replace(fields[key], **changes)})
        rejected(name, lambda altered=altered: prepare_mee(
            replace(frame, fields=altered), target_grid=grid, scalers=scalers, keys=MEE_V13_KEYS))
    missing = dict(fields)
    del missing['u850']
    rejected('missing_physical_variable', lambda: validate_physical_fields(replace(frame, fields=missing), MEE_V13_KEYS))
    invalid = dict(fields, pwat=replace(fields['pwat'], values=np.full(grid.shape, np.nan), valid=np.zeros(grid.shape, bool)))
    validate_physical_fields(replace(frame, fields=invalid), MEE_V13_KEYS)
    checks['masked_nan_remains_allowed'] = True

    terrain_grid = GridSpec(np.linspace(24, 25, 100), np.linspace(100, 101, 100))
    values = np.zeros((6, 100, 100), np.float32)
    values[0], values[5] = 1000., 1.
    pack = StaticPack(terrain_grid, values, np.ones_like(values, bool), np.ones((100, 100), bool),
                      B6_CHANNELS, UNITS, 'a' * 64, 'ARTIFICIAL')
    definition = DoteDefinition(40., 'ARTIFICIAL')
    PhysicalDote(pack, definition)
    checks['canonical_b6_physical_pack_pass'] = True
    rejected('wrong_terrain_channel_order', lambda: PhysicalDote(replace(pack, channels=B6_CHANNELS[::-1]), definition))
    rejected('wrong_gradient_unit', lambda: PhysicalDote(replace(pack, units=('m', 'm/degree', *UNITS[2:])), definition))
    rejected('wrong_terrain_mask_shape', lambda: PhysicalDote(replace(pack, valid=np.ones((6, 99, 100), bool)), definition))

    spec = importlib.util.spec_from_file_location('existing_dynamic_checks', ROOT / 'tests/research_readiness/test_dynamic_terrain.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    names = ('test_native_underground_neighbour_invalidates_bilinear_wind_support',
             'test_physical_direction_pressure_and_moisture_definitions',
             'test_pwat_missing_does_not_invalidate_O_or_supervision')
    suite = unittest.TestSuite(module.DynamicTests(name) for name in names)
    result = unittest.TextTestRunner(verbosity=1).run(suite)
    assert result.wasSuccessful()
    checks['three_existing_physical_dote_checks'] = True
    # Preserve the already computed elevation x rainfall cells at serialization.
    import torch
    from yuntapr.experimental.research_readiness.dynamic_training import TerrainTail
    elevations = pack.values.copy()
    elevations[0, :, :33] = 500.
    elevations[0, :, 33:66] = 1500.
    elevations[0, :, 66:] = 2500.
    tail = TerrainTail(replace(pack, values=elevations))
    rate = torch.full((1, 1, 100, 100), .5, dtype=torch.float32)
    rate[0, 0, 0, [0, 33, 66]] = 25.
    masks = torch.ones_like(rate, dtype=torch.bool)
    batch = SimpleNamespace(rate=rate, valid=masks, region=masks, ids=('2024-05-01T05:30:00Z',))
    output = SimpleNamespace(rain_prob=torch.full_like(rate, .6),
                             conditional_quantiles_log=torch.linspace(.2, 4., 32, dtype=torch.float64)[None, :, None, None].expand(1, 32, 100, 100))
    tail.add_batch(output, batch)
    global_rows = tail.finish()['strata']
    count = sum(row['n_rain'] for row in global_rows)
    summary = dict(n_valid=10000, n_rain=count,
                   coverage=[sum(row['q32_covered'] for row in global_rows) / count],
                   conditional_pinball=sum(row['n_rain'] * (row['conditional_pinball'] or 0) for row in global_rows) / count)
    finished = tail.finish_checked({'groups': {'all': {'summary': summary}}}, batch.ids)
    bins = finished['elevation_diagnostics']['bins']
    for index, global_row in enumerate(global_rows):
        assert sum(row['rainfall_strata'][index]['n_rain'] for row in bins.values()) == global_row['n_rain']
    assert all(sum(row['n_rain'] for row in item['rainfall_strata'][4:]) == 1 for item in bins.values())
    checks['elevation_cross_rainfall_seven_bins_preserved_without_new_inference'] = True
    receipt = dict(status='PASS_ARTIFICIAL_CPU_ALIGNMENT_ONLY', checks=checks,
                   checks_passed=len(checks), inherited_tests_passed=3,
                   actual_raw_data_reads=0, checkpoint_reads=0, optimizer_updates=0,
                   historical_run_revalidation=False, scientific_status='NOT_VERIFIED')
    with args.receipt.open('x', encoding='utf-8', newline='\n') as stream:
        json.dump(receipt, stream, indent=2)
        stream.write('\n')
    print(json.dumps({'status': receipt['status'], 'checks_passed': len(checks), 'inherited_tests_passed': 3}))


if __name__ == '__main__':
    main()
