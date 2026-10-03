"""Independent synthetic tests: no raw opens, models, optimizers or backward."""
from datetime import timedelta
from pathlib import Path,PureWindowsPath
import shutil,tempfile,unittest,uuid
import netCDF4
import numpy as np
from yuntapr.data import b1_scientific_freeze as f
from yuntapr.data import b1_temporal_audit as a

def frames_for(t):
    return {n.isoformat():{'nominal':n.isoformat(),'status':'FULL_VALID','reasons':'','valid_count':'251001',
        **{k:'True' for k in ('present','readable','decoded','full_valid','metadata_valid')},
        'obs_start':(n+timedelta(seconds=40)).isoformat(),'obs_end':(n+timedelta(seconds=578)).isoformat(),
        'date_created':(n+timedelta(minutes=20)).isoformat(),'relative_path':n.strftime('%Y%m/%d/')+n.strftime('NC_H09_%Y%m%d_%H%M_R21_FLDK.06001_06001.nc'),
        'source_sha256':'a'*64,'source_bytes':'100'} for n in a.slot_nominals(t)}

class M1Tests(unittest.TestCase):
    def setUp(self):self.t=a.utc('2023-03-02T00:00:00Z');self.frames=frames_for(self.t)
    def test_exact_six_ordered_causal_and_latest(self):
        result=f.strict_scene_frames(self.t,self.frames)
        self.assertEqual(len(result),6);self.assertEqual(result[-1]['nominal'],(self.t+timedelta(minutes=20)).isoformat())
    def test_each_slot_missing_rejects_without_substitution(self):
        for n in self.frames:
            with self.subTest(n=n):
                bad=self.frames.copy();del bad[n]
                with self.assertRaises(KeyError):f.strict_scene_frames(self.t,bad)
    def test_each_kind_incomplete_rejects_whole_scene(self):
        n=next(iter(self.frames))
        for status in ('MISSING','PARTIAL','ALL_FILL','CORRUPT_OR_UNREADABLE'):
            bad={k:dict(v) for k,v in self.frames.items()};bad[n]['status']=status
            with self.assertRaises(ValueError):f.strict_scene_frames(self.t,bad)
    def test_native_one_invalid_pixel_rejected(self):
        self.frames[next(iter(self.frames))]['valid_count']='251000'
        with self.assertRaises(ValueError):f.strict_scene_frames(self.t,self.frames)
    def test_actual_causal_end_equality_allowed(self):
        self.frames[next(iter(self.frames))]['obs_end']=(self.t+timedelta(minutes=30)).isoformat()
        self.assertEqual(len(f.strict_scene_frames(self.t,self.frames)),6)
    def test_future_end_and_reverse_interval_rejected(self):
        for start,end in ((self.t,self.t+timedelta(minutes=30,seconds=1)),(self.t+timedelta(seconds=1),self.t)):
            bad={k:dict(v) for k,v in self.frames.items()};bad[next(iter(bad))].update(obs_start=start.isoformat(),obs_end=end.isoformat())
            with self.assertRaises(ValueError):f.strict_scene_frames(self.t,bad)
    def test_window_start_no_february_even_when_fixture_exists(self):
        t=a.utc('2023-03-01T00:00:00Z')
        with self.assertRaisesRegex(ValueError,'NO_FEBRUARY'):f.strict_scene_frames(t,frames_for(t))
    def test_scan_bucket_deviation_is_not_new_exclusion(self):
        n=next(iter(self.frames));self.frames[n]['obs_start']=(a.utc(n)-timedelta(seconds=1)).isoformat()
        self.assertEqual(len(f.strict_scene_frames(self.t,self.frames)),6)

class ExposureTests(unittest.TestCase):
    def test_overlapping_scenes_keep_repeated_frame_exposure(self):
        t=a.utc('2023-03-02T00:00:00Z');u=t+timedelta(minutes=30);frames={**frames_for(t),**frames_for(u)}
        scenes=[{'window_start':v.isoformat(),'analysis_time':(v+timedelta(minutes=30)).isoformat()} for v in (t,u)]
        plan=f.exposure_plan(scenes,frames)
        self.assertEqual(len(plan),9);self.assertEqual(sum(r['scene_slot_exposures'] for r in plan),12)
        self.assertEqual(sorted(r['scene_slot_exposures'] for r in plan),[1]*6+[2]*3)
    def test_validation_and_2025_never_fit(self):
        for year in (2024,2025):
            with self.assertRaisesRegex(ValueError,'TRAIN_2023_ONLY'):
                f.exposure_plan([{'window_start':f'{year}-03-02T00:00:00Z'}],{})
    def test_weighted_histogram_matches_independently_expanded_pixels(self):
        parts=[(np.array([-1700,-1700,0,3000],dtype=np.int16),3),(np.array([-4000,1000,2000],dtype=np.int16),1)]
        hist=np.zeros(65536,dtype=np.int64)
        for raw,m in parts:f.accumulate_packed(hist,raw,m)
        expanded=np.concatenate([np.tile(raw,m) for raw,m in parts])
        kelvin=(expanded.astype(np.float32)*np.float32(.01)+np.float32(273.15)).astype(np.float64)
        result=f.histogram_summary(hist)
        self.assertEqual(result['valid_pixel_count'],15);self.assertEqual(result['ddof'],0)
        self.assertAlmostEqual(result['mean_K'],float(kelvin.mean()),places=12)
        self.assertAlmostEqual(result['std_K'],float(kelvin.std(ddof=0)),places=12)
        unique=np.concatenate([raw for raw,m in parts]);unweighted=(unique.astype(np.float32)*np.float32(.01)+np.float32(273.15)).astype(np.float64)
        self.assertNotAlmostEqual(result['mean_K'],float(unweighted.mean()),places=4)
    def test_int64_exposure_denominator_exceeds_32bit(self):
        self.assertEqual(10455*6*251001,15745292730);self.assertGreater(10455*6*251001,2**31)
    def test_bad_histogram_or_weight_rejected(self):
        for m in (0,-1,True,1.5):
            with self.assertRaises(ValueError):f.accumulate_packed(np.zeros(65536,dtype=np.int64),np.array([1],dtype=np.int16),m)
        with self.assertRaises(ValueError):f.histogram_summary(np.zeros(65536,dtype=np.int64))

class GuardTests(unittest.TestCase):
    def setUp(self):
        self.relative=r'202303\02\NC_H09_20230302_0000_R21_FLDK.06001_06001.nc'
        self.guard=f.NormalizationGuard([{'relative_path':self.relative}])
    def test_only_whitelisted_train_source_allowed(self):
        self.guard.check(str(a.HROOT/PureWindowsPath(self.relative)),'rb');self.assertEqual(self.guard.source_open_events,1)
    def test_validation_february_2025_unlisted_imerg_checkpoint_rejected_before_io(self):
        for path in (a.HROOT/r'202403\02\NC_H09_20240302_0000_R21_FLDK.06001_06001.nc',
            a.HROOT/r'202302\28\NC_H09_20230228_2350_R21_FLDK.06001_06001.nc',
            a.HROOT/r'202503\02\NC_H09_20250302_0000_R21_FLDK.06001_06001.nc',
            a.HROOT/r'202303\02\NC_H09_20230302_0010_R21_FLDK.06001_06001.nc',
            a.IROOT/'2023/imerg.nc',a.CHECKPOINT_ROOT/'model.pt'):
            with self.assertRaises(PermissionError):self.guard.check(str(path),'rb')
        self.assertEqual(self.guard.source_open_events,0)
    def test_write_rejected_even_for_whitelisted_source(self):
        with self.assertRaises(PermissionError):self.guard.check(str(a.HROOT/PureWindowsPath(self.relative)),'wb')

class PhysicalReaderTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from yuntapr.spatial.sp04_mapping import load_sp04
        cls.mapping=load_sp04()
    def read_fixture(self,kind):
        parent=Path(tempfile.gettempdir())/'yuntapr_b1_normalization_fixtures';parent.mkdir(exist_ok=True)
        directory=parent/uuid.uuid4().hex;directory.mkdir()
        path=directory/'b13.nc';telemetry={'b13_pixel_values_read':0}
        try:
            with netCDF4.Dataset(str(path),'w') as ds:
                for name,size in (('latitude',501),('longitude',501),('time',1)):ds.createDimension(name,size)
                for name,axis in (('latitude','native_lat'),('longitude','native_lon')):
                    vals=self.mapping.axes[axis]
                    ds.createVariable(name,'f4',(name,))[:]=vals[::-1] if kind=='flip' and name=='latitude' else vals
                var=ds.createVariable('tbb_13','i2',('latitude','longitude'),fill_value=-32768)
                var.setncatts({'units':'K','scale_factor':np.float32(.02 if kind=='packing' else .01),
                    'add_offset':np.float32(273.15),'valid_min':np.int16(-30000),'valid_max':np.int16(30000)})
                var.set_auto_maskandscale(False);raw=np.full((501,501),-1700,dtype=np.int16)
                if kind=='partial':raw[0,0]=-32768
                var[:]=raw
                for name,value in (('start_time',.6666666666666666),('end_time',9)):
                    tv=ds.createVariable(name,'f8',('time',));tv.units='minutes since 2023-07-01 00:00:00';tv[:]=[value]
                ds.date_created='2023-07-01T00:20:00Z'
            identity={'obs_start':'2023-07-01T00:00:40Z','obs_end':'2023-07-01T00:09:00Z',
                'minimum_analysis_time':'2023-07-01T00:30:00Z','date_created':'2023-07-01T00:20:00Z'}
            try:
                with a.AuditGuard():result=f.read_packed_frame(path,self.mapping,identity,telemetry)
                return result,telemetry,None
            except ValueError as exc:return None,telemetry,str(exc)
        finally:
            if directory.resolve().parent!=parent.resolve():raise ValueError('UNSAFE_FIXTURE_CLEANUP')
            shutil.rmtree(directory)
    def test_real_reader_returns_packed_int16_exactly_once(self):
        raw,counts,error=self.read_fixture('full')
        self.assertIsNone(error);self.assertEqual(raw.dtype,np.int16);self.assertEqual(raw.shape,(501,501))
        self.assertTrue(np.all(raw==-1700));self.assertEqual(counts['b13_pixel_values_read'],251001)
    def test_partial_is_rejected_no_missing_zero(self):
        raw,counts,error=self.read_fixture('partial');self.assertIsNone(raw)
        self.assertIn('NO_LONGER_FULL_VALID',error);self.assertEqual(counts['b13_pixel_values_read'],251001)
    def test_flip_rejects_before_pixels(self):
        raw,counts,error=self.read_fixture('flip');self.assertIsNone(raw)
        self.assertIn('no flip/transpose',error);self.assertEqual(counts['b13_pixel_values_read'],0)
    def test_packing_change_rejects_before_pixels(self):
        raw,counts,error=self.read_fixture('packing');self.assertIsNone(raw)
        self.assertIn('PACKING_CHANGED',error);self.assertEqual(counts['b13_pixel_values_read'],0)

if __name__=='__main__':unittest.main()
