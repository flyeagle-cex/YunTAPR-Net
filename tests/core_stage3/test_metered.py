import hashlib,unittest,uuid
from pathlib import Path
import numpy as np
import netCDF4
from yuntapr.experimental.core_innovation.stage3.statistics import SourceCache,digest
from yuntapr.experimental.core_innovation.stage3.metered_io import SourceMeter,path_key,IdentityConflict
from yuntapr.experimental.core_innovation.stage2.population import read_seven_band
from yuntapr.spatial.sp04_mapping import load_sp04


class MeteredTests(unittest.TestCase):
    def setup_cache(self,raw,name):
        root=Path(__file__).resolve().parents[2]/'tests/core_stage3/.local'/uuid.uuid4().hex;root.mkdir(parents=True)
        source=root/name;source.write_bytes(raw);sha=hashlib.sha256(raw).hexdigest()
        manifest={'fixture':dict(year=2023,bytes=len(raw),files=1,expected_sha256=sha)}
        grant=dict(authorized=True,decision_id='SYNTHETIC_FIXTURE_ONLY',manifest_sha=digest(manifest),max_bytes=len(raw),max_files=1)
        cache=SourceCache(root/'fixture.sqlite',manifest=manifest,manifest_sha=digest(manifest),grant=grant)
        meter=SourceMeter(cache.db,{str(source):dict(bytes=len(raw),sha=sha,job_id='fixture')},max_files=1,max_bytes=len(raw));return source,cache,meter,sha

    def test_measured_bytes_intent_cache_and_forbidden_source(self):
        source,cache,meter,sha=self.setup_cache(b'synthetic bytes only','synthetic.nc');meter.install()
        try:
            def load():
                meter.active={path_key(source)}
                with source.open('rb') as f:raw=f.read(1000)
                return dict(year=2023,source_sha256=hashlib.sha256(raw).hexdigest(),raw_bytes_read=len(raw))
            cache.read_once('fixture',load);before=meter.totals()
            cache.read_once('fixture',lambda:self.fail('Duplicate decoder called'))
            self.assertEqual(meter.totals(),before);self.assertEqual(before['delivered_bytes'],len(b'synthetic bytes only'))
            with self.assertRaises(PermissionError):(source.parent/'unlisted_2025.nc').open('rb')
            with self.assertRaises((PermissionError,RuntimeError)):source.open('rb')
        finally:meter.uninstall();cache.close()

    def test_real_reader_memory_decode_through_meter_on_synthetic_netcdf(self):
        mapping=load_sp04();ds=netCDF4.Dataset('synthetic.nc','w',format='NETCDF4',memory=16*1024**2)
        ds.createDimension('latitude',501);ds.createDimension('longitude',501)
        for axis,key in (('latitude','native_lat'),('longitude','native_lon')):ds.createVariable(axis,'f4',(axis,))[:]=mapping.axes[key]
        for key,seconds in (('start_time',41.),('end_time',579.)):
            var=ds.createVariable(key,'f8');var.units='seconds since 2023-05-01 05:00:00';var.assignValue(seconds)
        for band in ('08','09','10','11','13','15','16'):
            v=ds.createVariable('tbb_'+band,'i2',('latitude','longitude'),fill_value=-32768);v.set_auto_maskandscale(False)
            v.units='K';v.scale_factor=np.float32(.01);v.add_offset=np.float32(273.15);v.valid_min=np.int16(-30000);v.valid_max=np.int16(30000);v[:]=100
        source,cache,meter,sha=self.setup_cache(bytes(ds.close()),'NC_H09_20230501_0500_R21_FLDK.06001_06001.nc');meter.install()
        try:
            def load():
                meter.active={path_key(source)};x,mask,r=read_seven_band(source,nominal='2023-05-01T05:00:00Z',mapping=mapping)
                self.assertTrue(mask.all());self.assertEqual(x.shape,(7,501,501))
                return dict(year=2023,source_sha256=r['source_sha256'],raw_bytes_read=r['bytes_read'])
            result=cache.read_once('fixture',load);self.assertEqual(meter.totals()['delivered_bytes'],result['raw_bytes_read'])
        finally:meter.uninstall();cache.close()
