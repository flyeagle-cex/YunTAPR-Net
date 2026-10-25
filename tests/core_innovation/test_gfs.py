from datetime import datetime,timedelta,timezone
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import patch
import unittest
import uuid
import numpy as np
import netCDF4
from yuntapr.experimental.core_innovation.grid import GridSpec
from yuntapr.experimental.core_innovation.gfs import (
    ForecastIdentity,Availability,VariableRequest,read_gfs_file,combine_environment,decode_packed)

NOW=datetime(2023,5,1,tzinfo=timezone.utc)
IDENTITY=ForecastIdentity(NOW,timedelta(hours=3),NOW+timedelta(hours=3))
MAIN=(VariableRequest('u850','u','u-component_of_wind_isobaric',85000),
      VariableRequest('v850','v','v-component_of_wind_isobaric',85000),
      VariableRequest('ps','surface_pressure','Pressure_surface'))
THERMO=(VariableRequest('t850','temperature','Temperature_isobaric',85000),
        VariableRequest('rh850','relative_humidity','Relative_humidity_isobaric',85000))


@contextmanager
def dataset_bytes(path):
    # Avoid the existing Windows HDF5 Unicode filename limitation even in fixtures.
    ds=netCDF4.Dataset('synthetic_fixture.nc','w',format='NETCDF4',memory=1024**2)
    try:yield ds
    except BaseException:
        ds.close();raise
    else:path.write_bytes(ds.close())


def fixture(path,thermo=False,*,reference_shift=0,pressure_unit='hPa',lat=(32,31,30),surface_unit='Pa'):
    path.parent.mkdir(parents=True,exist_ok=True)
    with dataset_bytes(path) as ds:
        for d,n in (('valid_time',1),('pressure_level',2),('latitude',3),('longitude',4)):ds.createDimension(d,n)
        y=ds.createVariable('latitude','f8',('latitude',));y[:]=lat;y.units='degrees_north'
        x=ds.createVariable('longitude','f8',('longitude',));x[:]=[100,101,102,103];x.units='degrees_east'
        p=ds.createVariable('pressure_level','f8',('pressure_level',));p[:]=[700,850] if pressure_unit=='hPa' else [70000,85000];p.units=pressure_unit
        t=ds.createVariable('valid_time','i4',('valid_time',));t[:]=3;t.units='hours since 2023-05-01 00:00:00';t.udunits='old auxiliary metadata'
        r=ds.createVariable('forecast_reference_time' if thermo else 'reftime','i4');r.assignValue(reference_shift);r.units=t.units
        ds.initialization_time_utc=NOW.isoformat();ds.valid_time_utc=IDENTITY.valid.isoformat();ds.lead_time_hours=3
        ds.conservative_available_time_utc=(NOW+timedelta(hours=5)).isoformat();ds.availability_note='Assumption, not observed publication'
        for request in THERMO if thermo else MAIN:
            dims=('valid_time','latitude','longitude') if request.level_pa is None else ('valid_time','pressure_level','latitude','longitude')
            var=ds.createVariable(request.variable,'f4',dims,fill_value=-9999.)
            var.units={'u':'m s-1','v':'m/s','surface_pressure':surface_unit,'temperature':'K','relative_humidity':'%'}[request.quantity]
            values=np.full(var.shape,{'u':4,'v':-2,'surface_pressure':100000,'temperature':280,'relative_humidity':75}[request.quantity],dtype=np.float32)
            if request.quantity=='surface_pressure':values[0,1,1]=70000
            if request.quantity=='temperature':values[0,1,2,2]=-9999
            var[:]=values


class GFSTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.folder=Path(__file__).resolve().parent/'.local'/('gfs_'+uuid.uuid4().hex)
        cls.main=cls.folder/'main/gfs_0p25_2023050100_f003.nc'
        cls.thermo=cls.folder/'thermo/gfs_thermo_0p25_2023050100_f003.nc'
        fixture(cls.main);fixture(cls.thermo,True)

    def files(self):return read_gfs_file(self.main,IDENTITY,MAIN),read_gfs_file(self.thermo,IDENTITY,THERMO)

    def test_real_reader_on_synthetic_netcdf_packed_mask_and_units(self):
        a,b=self.files();self.assertEqual(a.grid.shape,(3,4));self.assertEqual(b.fields['t850'].unit,'K')
        self.assertFalse(b.fields['t850'].valid[2,2]);self.assertTrue(np.isnan(b.fields['t850'].values[2,2]))
        self.assertEqual(a.fields['u850'].level_pa,85000);self.assertEqual(a.fields['u850'].unit,'m/s')
        self.assertIn('auxiliary_udunits',a.provenance['legacy_metadata'])
        self.assertEqual(a.provenance['historical_availability'],'NOT_ESTABLISHED')

    def test_retrospective_pair_and_subsurface_level(self):
        a,b=self.files();out=combine_environment(a,b,target_valid_time=IDENTITY.valid,decision_time=IDENTITY.valid,mode='retrospective')
        self.assertFalse(out.fields['u850'].valid[1,1]);self.assertFalse(out.fields['rh850'].valid[1,1])
        x,m=out.stack(('t850','u850'));self.assertEqual(x.shape,(2,3,4));self.assertEqual(m.dtype,bool)

    def test_operational_requires_exact_historical_release_evidence(self):
        a,b=self.files();kwargs=dict(target_valid_time=IDENTITY.valid,decision_time=IDENTITY.valid,mode='operational')
        with self.assertRaises(PermissionError):combine_environment(a,b,**kwargs)
        with self.assertRaises(ValueError):Availability(NOW,'assumed','init_plus_5h',IDENTITY,('a'*64,'b'*64))
        late=Availability(IDENTITY.valid+timedelta(seconds=1),'synthetic_evidence','observed_historical_first_availability',IDENTITY,(a.provenance['input_sha256'],b.provenance['input_sha256']))
        with self.assertRaises(PermissionError):combine_environment(a,b,availability=late,**kwargs)
        wrong=Availability(NOW,'synthetic_evidence','observed_historical_first_availability',IDENTITY,('a'*64,'b'*64))
        with self.assertRaises(PermissionError):combine_environment(a,b,availability=wrong,**kwargs)

    def test_time_mismatch_cannot_use_filename_alone(self):
        path=self.folder/'bad/gfs_0p25_2023050100_f003.nc';fixture(path,reference_shift=1)
        with self.assertRaisesRegex(ValueError,'Primary CF'):read_gfs_file(path,IDENTITY,MAIN)
        with self.assertRaises(ValueError):ForecastIdentity(NOW,timedelta(hours=1),NOW)

    def test_2025_rejected_before_any_dataset_open(self):
        with self.assertRaises(PermissionError):ForecastIdentity(datetime(2025,1,1,tzinfo=timezone.utc),timedelta(0),datetime(2025,1,1,tzinfo=timezone.utc))
        with patch('netCDF4.Dataset',side_effect=AssertionError('must not open')):
            with self.assertRaises(PermissionError):read_gfs_file(self.folder/'gfs_0p25_2025050100_f003.nc',IDENTITY,MAIN)

    def test_byte_budget_and_missing_pressure_level_fail(self):
        with self.assertRaises(ValueError):read_gfs_file(self.main,IDENTITY,MAIN,max_file_bytes=10)
        with self.assertRaises(ValueError):read_gfs_file(self.main,IDENTITY,(VariableRequest('u','u','u-component_of_wind_isobaric',50000),))

    def test_forbidden_predictor_and_unknown_units(self):
        with self.assertRaises(ValueError):VariableRequest('rain','precipitable_water','Total_precipitation_surface')
        path=self.folder/'unit/gfs_0p25_2023050100_f003.nc';fixture(path,surface_unit='unknown')
        with self.assertRaises(ValueError):read_gfs_file(path,IDENTITY,MAIN)

    def test_packed_valid_range_precedes_scaling(self):
        x,v=decode_packed(np.array([0,20,32767,-1],np.int16),{'_FillValue':32767,'valid_range':[0,100],'scale_factor':.1,'add_offset':200})
        np.testing.assert_allclose(x[:2],[200,202]);np.testing.assert_array_equal(v,[True,True,False,False])
        self.assertTrue(np.isnan(x[2:]).all())

    def test_candidate_target_mapping_keeps_mask(self):
        a,b=self.files();out=combine_environment(a,b,target_valid_time=IDENTITY.valid,decision_time=IDENTITY.valid,mode='retrospective')
        target=GridSpec([30.5,31.5],[100.5,102.5]);projected=out.on_grid(target,operator='bilinear_point_candidate')
        self.assertEqual(projected.fields['t850'].values.shape,(2,2));self.assertFalse(projected.fields['t850'].valid.all())


if __name__=='__main__':unittest.main()
