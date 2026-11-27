"""Synthetic-only tests for the 2025 final-test payload readers.

No real 2025 (or 2023/2024) payload is opened here: every NetCDF file is built
by this module inside an ASCII system temporary directory.  The HDF5 C library
used by netCDF4 cannot create files under a non-ASCII path, so the fixture root
must be ASCII; the git worktree is never written.
"""
from datetime import datetime, timedelta, timezone
import hashlib
import os
from pathlib import Path
import shutil
import tempfile

import numpy as np
import pytest

from yuntapr.experimental.core_innovation import gfs
from yuntapr.experimental.research_readiness import final_test_2025_planning as planning
from yuntapr.experimental.research_readiness import final_test_2025_readers as readers

netCDF4 = pytest.importorskip('netCDF4')

UTC = timezone.utc


def _utc(text):
    return datetime.fromisoformat(text).replace(tzinfo=UTC)


def _sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _attrs(ds, values):
    for name, value in values.items():
        ds.setncattr(name, value)


def _packed(ds, name, dims, units, values, *, fill=-9999.0, scale=1.0, offset=0.0,
            valid_min=-1.0e9, valid_max=1.0e9):
    var = ds.createVariable(name, 'f4', dims, fill_value=np.float32(fill))
    var.scale_factor = np.float32(scale)
    var.add_offset = np.float32(offset)
    var.valid_min = np.float32(valid_min)
    var.valid_max = np.float32(valid_max)
    var.units = units
    var[:] = np.asarray(values, dtype=np.float32)
    return var


def _cf_seconds(when, epoch):
    return (when - epoch).total_seconds()


def _write_satellite(path, nominal, seed):
    path.parent.mkdir(parents=True, exist_ok=True)
    epoch = datetime(2025, 2, 28, 0, 0, tzinfo=UTC)
    ds = netCDF4.Dataset(path, 'w', format='NETCDF4')
    try:
        ds.createDimension('latitude', 501)
        ds.createDimension('longitude', 501)
        lat = ds.createVariable('latitude', 'f8', ('latitude',))
        lat.units = 'degrees_north'
        lat[:] = np.linspace(32.0, 7.0, 501)
        lon = ds.createVariable('longitude', 'f8', ('longitude',))
        lon.units = 'degrees_east'
        lon[:] = np.linspace(95.0, 120.0, 501)
        for slot, channel in enumerate(readers.CHANNELS):
            var = ds.createVariable('tbb_' + channel[1:], 'i2', ('latitude', 'longitude'),
                                    fill_value=np.int16(-9999))
            var.scale_factor = np.float32(0.01)
            var.add_offset = np.float32(200.0)
            var.valid_min = np.int16(-100)
            var.valid_max = np.int16(8000)
            var.units = 'K'
            rng = np.random.default_rng(seed * 10 + slot)
            raw = rng.integers(2000, 4000, size=(501, 501)).astype(np.int16)
            raw[0, 0] = -9999
            var[:] = raw
        for name, when in (('start_time', nominal + timedelta(seconds=40)),
                           ('end_time', nominal + timedelta(minutes=9, seconds=38))):
            var = ds.createVariable(name, 'f8')
            var.units = 'seconds since 2025-02-28 00:00:00'
            var.assignValue(_cf_seconds(when, epoch))
        ds.date_created = '2025-03-01T00:00:00Z'
    finally:
        ds.close()


def _write_gfs(path, identity):
    path.parent.mkdir(parents=True, exist_ok=True)
    epoch = datetime(2025, 3, 1, 0, 0, tzinfo=UTC)
    ds = netCDF4.Dataset(path, 'w', format='NETCDF4')
    try:
        ds.createDimension('latitude', 5)
        ds.createDimension('longitude', 6)
        ds.createDimension('pressure_level', 3)
        lat = ds.createVariable('latitude', 'f8', ('latitude',))
        lat.units = 'degrees_north'
        lat[:] = np.linspace(32.0, 31.0, 5)
        lon = ds.createVariable('longitude', 'f8', ('longitude',))
        lon.units = 'degrees_east'
        lon[:] = np.linspace(95.0, 96.0, 6)
        level = ds.createVariable('pressure_level', 'f8', ('pressure_level',))
        level.units = 'hPa'
        level[:] = [500.0, 700.0, 850.0]
        for name, when in (('forecast_reference_time', identity.init),
                           ('valid_time', identity.valid)):
            var = ds.createVariable(name, 'f8')
            var.units = 'hours since 2025-03-01 00:00:00'
            var.assignValue(_cf_seconds(when, epoch) / 3600.0)
        ds.setncattr('initialization_time_utc', identity.init.strftime('%Y-%m-%dT%H:%M:%S+00:00'))
        ds.setncattr('valid_time_utc', identity.valid.strftime('%Y-%m-%dT%H:%M:%S+00:00'))
        ds.setncattr('forecast_hour', 6)
        dims3 = ('pressure_level', 'latitude', 'longitude')
        _packed(ds, 'u-component_of_wind_isobaric', dims3, 'm s-1',
                np.full((3, 5, 6), 3.0))
        _packed(ds, 'v-component_of_wind_isobaric', dims3, 'm s-1',
                np.full((3, 5, 6), -2.0))
        _packed(ds, 'Temperature_isobaric', dims3, 'K',
                np.full((3, 5, 6), 280.0))
        _packed(ds, 'Relative_humidity_isobaric', dims3, '%',
                np.full((3, 5, 6), 65.0))
        _packed(ds, 'Pressure_surface', ('latitude', 'longitude'), 'Pa',
                np.full((5, 6), 100000.0))
        _packed(ds, 'Precipitable_water_entire_atmosphere_single_layer',
                ('latitude', 'longitude'), 'kg m-2', np.full((5, 6), 25.0))
        _packed(ds, 'Convective_available_potential_energy_surface',
                ('latitude', 'longitude'), 'J kg-1', np.full((5, 6), 500.0))
    finally:
        ds.close()


def _write_imerg(path, epoch):
    path.parent.mkdir(parents=True, exist_ok=True)
    ds = netCDF4.Dataset(path, 'w', format='NETCDF4')
    try:
        ds.createDimension('time', 48)
        ds.createDimension('lat', 130)
        ds.createDimension('lon', 140)
        time = ds.createVariable('time', 'f8', ('time',))
        time.units = 'seconds since 2025-02-28 00:00:00'
        time[:] = np.arange(48) * 1800.0
        lat = ds.createVariable('lat', 'f8', ('lat',))
        lat.units = 'degrees_north'
        lat[:] = np.linspace(32.0, 7.0, 130)
        lon = ds.createVariable('lon', 'f8', ('lon',))
        lon.units = 'degrees_east'
        lon[:] = np.linspace(95.0, 120.0, 140)
        var = ds.createVariable('precipitation', 'f4', ('time', 'lat', 'lon'),
                                fill_value=np.float32(-9999.0))
        var.units = 'mm hr-1'
        var.missing_value = np.float32(-9999.0)
        rng = np.random.default_rng(7)
        values = rng.uniform(0.0, 40.0, size=(48, 130, 140)).astype(np.float32)
        values[0, 0, 0] = -9999.0
        var[:] = values
        ds.setncattr('source', 'GPM_3IMERGHH_07')
        ds.setncattr('title', 'IMERG Final Run V07 converted half-hourly target')
        ds.setncattr('run_type', 'Final')
        ds.setncattr('version', 'V07')
    finally:
        ds.close()


@pytest.fixture()
def synthetic_bundle():
    base = Path(os.environ.get('LOCALAPPDATA', 'C:/Users/Public')) / 'Temp'
    if not base.is_dir() or not str(base).isascii():
        pytest.skip('ASCII system temporary directory required for netCDF4 fixtures')
    root = Path(tempfile.mkdtemp(prefix='yuntapr_2025_fixture_', dir=str(base)))
    try:
        layout = planning.synthetic_layout(root)
        scene = planning.enumerate_scenes(
            layout, months=(3,), analysis_start=datetime(2025, 3, 1, 0, tzinfo=UTC),
            analysis_end=datetime(2025, 3, 1, 6, tzinfo=UTC))[0].as_dict()
        identity = readers.ForecastIdentity2025(
            init=_utc(scene['gfs_init']), lead=timedelta(hours=6),
            valid=_utc(scene['analysis_time']))
        _write_gfs(layout.root('gfs_main') / scene['gfs_main_relative_path'], identity)
        _write_gfs(layout.root('gfs_thermo') / scene['gfs_thermo_relative_path'], identity)
        window = _utc(scene['window_start'])
        _write_imerg(layout.root('imerg') / scene['imerg_day_relative_path'],
                     datetime(2025, 2, 28, 0, tzinfo=UTC))
        for slot in range(6):
            _write_satellite(layout.root('himawari') / scene[f'slot_{slot:02d}_relative_path'],
                             _utc(scene[f'slot_{slot:02d}_nominal']), slot)
        expected = {}
        for kind, modality_root in (('himawari', layout.root('himawari')),
                                    ('imerg', layout.root('imerg')),
                                    ('gfs', layout.root('gfs_main')),
                                    ('gfs_thermo', layout.root('gfs_thermo'))):
            for path in sorted(Path(modality_root).rglob('*')):
                if path.is_file():
                    relative = path.relative_to(modality_root).as_posix()
                    expected[relative] = {'sha256': _sha(path), 'bytes': path.stat().st_size}
        authorization = readers.PayloadAuthorization2025.fixture_only(root)
        yield layout, scene, expected, authorization, window, root
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_default_access_is_denied():
    with pytest.raises(PermissionError):
        readers.PayloadAccess2025.default()
    with pytest.raises(PermissionError):
        readers.PayloadAccess2025(None)
    with pytest.raises(PermissionError):
        readers.read_scene_payload(None, {})
    with pytest.raises(PermissionError):
        readers.read_satellite_scene(None, {})
    with pytest.raises(PermissionError):
        readers.read_imerg_scene(None, {})


def test_forecast_identity_2025_only():
    good = readers.ForecastIdentity2025(init=_utc('2025-03-01T00:00:00'),
                                        lead=timedelta(hours=6),
                                        valid=_utc('2025-03-01T06:00:00'))
    assert good.lead == timedelta(hours=6)
    carry_in = readers.ForecastIdentity2025(init=_utc('2025-02-28T18:00:00'),
                                            lead=timedelta(hours=6),
                                            valid=_utc('2025-03-01T00:00:00'))
    assert carry_in.init.month == 2
    with pytest.raises(PermissionError):
        readers.ForecastIdentity2025(init=_utc('2025-02-28T12:00:00'),
                                     lead=timedelta(hours=6),
                                     valid=_utc('2025-02-28T18:00:00'))
    assert readers.ForecastIdentity2025(init=_utc('2025-10-01T00:00:00'),
                                        lead=timedelta(hours=6),
                                        valid=_utc('2025-10-01T06:00:00'))
    with pytest.raises(PermissionError):
        readers.ForecastIdentity2025(init=_utc('2024-03-01T00:00:00'),
                                     lead=timedelta(hours=6),
                                     valid=_utc('2024-03-01T06:00:00'))
    with pytest.raises(ValueError):
        readers.ForecastIdentity2025(init=_utc('2025-03-01T00:00:00'),
                                     lead=timedelta(hours=3),
                                     valid=_utc('2025-03-01T03:00:00'))
    with pytest.raises(ValueError):
        readers.ForecastIdentity2025(init=_utc('2025-03-01T01:00:00'),
                                     lead=timedelta(hours=6),
                                     valid=_utc('2025-03-01T07:00:00'))
    with pytest.raises(ValueError):
        readers.ForecastIdentity2025(init=_utc('2025-03-01T00:00:00'),
                                     lead=timedelta(hours=6),
                                     valid=_utc('2025-03-01T07:00:00'))


def test_frozen_2023_2024_guards_still_reject_2025():
    with pytest.raises(PermissionError):
        gfs.ForecastIdentity(init=_utc('2025-03-01T00:00:00'), lead=timedelta(hours=6),
                             valid=_utc('2025-03-01T06:00:00'))
    identity = readers.ForecastIdentity2025(init=_utc('2025-03-01T00:00:00'),
                                            lead=timedelta(hours=6),
                                            valid=_utc('2025-03-01T06:00:00'))
    with pytest.raises(TypeError):
        gfs.decode_gfs_bytes(b'not-a-forecast', identity, [])
    with pytest.raises(TypeError):
        readers.decode_gfs_2025(b'not-a-forecast', object(), [])


def test_fixture_authorization_is_root_scoped(tmp_path):
    authorization = readers.PayloadAuthorization2025.fixture_only(tmp_path)
    access = readers.PayloadAccess2025(authorization)
    assert access.authorization.allow_october is False
    assert set(authorization.roots) == {'himawari', 'imerg', 'gfs', 'gfs_thermo'}
    with pytest.raises(PermissionError):
        readers.PayloadAuthorization2025.fixture_only(Path(r'F:\云南极端降水数据\raw\GFS\2025'))
    with pytest.raises(PermissionError):
        readers.PayloadAuthorization2025.fixture_only(Path(r'H:\葵花202303_202510\2025'))
    with pytest.raises(ValueError):
        readers.PayloadAuthorization2025.fixture_only(Path('relative-fixture'))
    for bad in ('../escape.nc', '2025/../../escape.nc', 'C:/absolute.nc'):
        with pytest.raises(PermissionError):
            access.resolve('himawari', bad)
    with pytest.raises(PermissionError):
        access.resolve('himawari', '202510/01/NC_H09_20251001_0000_R21_FLDK.06001_06001.nc')
    with pytest.raises(PermissionError):
        access.resolve('himawari', '202511/01/NC_H09_20251101_0000_R21_FLDK.06001_06001.nc')
    with pytest.raises(PermissionError):
        access.resolve('himawari', '202502/27/NC_H09_20250227_2300_R21_FLDK.06001_06001.nc')
    with pytest.raises(PermissionError):
        access.resolve('imerg', '2025/imerg_20250227.nc')
    assert access.resolve('himawari', '202503/01/NC_H09_20250301_0000_R21_FLDK.06001_06001.nc')
    assert access.resolve('himawari', '202502/28/NC_H09_20250228_2300_R21_FLDK.06001_06001.nc')
    assert access.resolve('imerg', '2025/imerg_20250228.nc')
    assert access.resolve('gfs', '2025/20250228/gfs_0p25_2025022818_f006.nc')


def test_researcher_authorization_requires_exact_fields(tmp_path):
    roots = {'himawari': r'H:\fixture\himawari', 'imerg': r'F:\fixture\imerg',
             'gfs': r'F:\fixture\gfs', 'gfs_thermo': r'F:\fixture\gfs_thermo'}
    valid = {
        'version': 'v1', 'AUTHORIZED_BY': 'RESEARCHER', 'scope': readers.PAYLOAD_SCOPE,
        'FINAL_TEST_2025_PAYLOAD_AUTHORIZED': True,
        'protocol': {'path': 'config/evaluation/x.yaml', 'sha256': 'a' * 64},
        'catalogue_sha256': 'b' * 64, 'roots': roots, 'allow_october': False,
        'created_utc': '2026-11-27T00:00:00+00:00',
    }
    authorization = readers.PayloadAuthorization2025.researcher(valid)
    readers.PayloadAccess2025(authorization)
    with pytest.raises(ValueError):
        readers.PayloadAuthorization2025.researcher(dict(valid, extra=1))
    with pytest.raises(PermissionError):
        readers.PayloadAuthorization2025.researcher(dict(valid, FINAL_TEST_2025_PAYLOAD_AUTHORIZED=False))
    with pytest.raises(ValueError):
        readers.PayloadAuthorization2025.researcher(
            dict(valid, roots={'himawari': 'C:/x', 'imerg': roots['imerg'],
                               'gfs': roots['gfs'], 'gfs_thermo': roots['gfs_thermo']}))


def test_end_to_end_synthetic_scene(synthetic_bundle):
    layout, scene, expected, authorization, window, _ = synthetic_bundle
    access = readers.PayloadAccess2025(authorization)
    payload = readers.read_scene_payload(access, scene, expected=expected)
    satellite = payload['satellite']
    assert satellite['values'].shape == (6, 7, 501, 501)
    assert satellite['values'].dtype == np.float32
    assert len(satellite['frames']) == 6
    assert [frame['slot'] for frame in satellite['frames']] == list(range(6))
    assert '_20250228_2300_' in satellite['frames'][0]['relative_path']
    environment = payload['environment']
    assert isinstance(environment['identity'], readers.ForecastIdentity2025)
    assert len(environment['environment'].fields) == 13
    target = payload['target']
    assert target['rate'].shape == (100, 100)
    assert target['valid'].shape == (100, 100)
    assert target['product'] == 'GPM_3IMERGHH_07'
    assert target['version'] == 'V07'
    assert target['run_type'] == 'Final'
    assert np.nanmax(target['rate']) > 0.1
    assert access.opened == 9
    assert access.bytes_read == sum(item['bytes'] for item in expected.values())
    assert len(access.sha256_read) == 9


def test_inventory_mismatch_is_rejected(synthetic_bundle):
    _, scene, expected, authorization, _, _ = synthetic_bundle
    first = scene['slot_00_relative_path']
    bad = dict(expected)
    bad[first] = dict(expected[first], sha256='f' * 64)
    with pytest.raises(ValueError):
        readers.read_satellite_scene(readers.PayloadAccess2025(authorization),
                                     scene, expected=bad)


def test_frame_in_nominal_bin_accepts_real_scan_offset():
    # Real Himawari frames start ~40 s after the nominal bin label and close
    # inside the same ten-minute bin (probed on a 2023 file).
    nominal = _utc('2023-03-01T05:00:00')
    start = _utc('2023-03-01T05:00:40.792040')
    end = _utc('2023-03-01T05:09:38.646280')
    assert readers._frame_in_nominal_bin(nominal, start, end) is True
    assert readers._frame_in_nominal_bin(
        nominal, _utc('2023-03-01T05:00:00'), _utc('2023-03-01T05:10:00')) is True


def test_frame_in_nominal_bin_rejects_out_of_bin_frames():
    nominal = _utc('2023-03-01T05:00:00')
    start = _utc('2023-03-01T05:00:40')
    end = _utc('2023-03-01T05:09:38')
    assert readers._frame_in_nominal_bin(nominal, _utc('2023-03-01T04:59:59'), end) is False
    assert readers._frame_in_nominal_bin(nominal, start, _utc('2023-03-01T05:10:01')) is False
    assert readers._frame_in_nominal_bin(nominal, end, start) is False
