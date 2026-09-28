"""Scientific invariants and file safety, using tiny synthetic NetCDF fixtures."""
import ast,sys,tempfile,unittest
from pathlib import Path
from datetime import datetime,timezone,timedelta
from unittest.mock import patch
import numpy as np
import pandas as pd
import netCDF4
sys.path.insert(0,str(Path(__file__).parents[1]/"src"))
from config import CHANNELS,PROJECT,RAW
from common import sourcepath,outpath
from read_himawari import decode_packed,_read_local,load_himawari_sequence,MissingChannelError,CoordinateShapeError,MetadataError
from build_sequence_index import expected_times,unique_candidate,AmbiguousCandidateError,build_sequences
from qc import coordinate_info,grid_info

def fixture(path,omit=None):
    with netCDF4.Dataset(str(path),"w") as ds:
        ds.createDimension("latitude",2);ds.createDimension("longitude",3)
        ds.createVariable("latitude","f4",("latitude",))[:]=[30,20]
        ds.createVariable("longitude","f4",("longitude",))[:]=[97,98,99]
        for i,ch in enumerate(CHANNELS):
            if ch==omit:continue
            v=ds.createVariable(ch,"i2",("latitude","longitude"),fill_value=-32768)
            v.setncatts(dict(scale_factor=.01,add_offset=273.15,valid_min=-27315,
                            valid_max=32767,missing_value=-32768))
            v.set_auto_maskandscale(False)
            v[:]=np.array([[i,100,-32768],[-30000,200,300]],dtype=np.int16)

class ScienceTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(dir=PROJECT/"tests")
        self.path=Path(self.temp.name)/"sample.nc";fixture(self.path)
        self.target=datetime(2024,7,1,0,30,tzinfo=timezone.utc)
    def tearDown(self):self.temp.cleanup()
    def test_cross_day(self):
        self.assertEqual(expected_times(datetime(2024,7,2,0,10,tzinfo=timezone.utc))[-1].day,1)
    def test_cross_month(self):self.assertEqual(expected_times(self.target)[-1],datetime(2024,6,30,23,40,tzinfo=timezone.utc))
    def test_cross_year(self):
        self.assertEqual(expected_times(datetime(2024,1,1,tzinfo=timezone.utc))[-1].year,2023)
    def test_time_order(self):
        ts=expected_times(self.target)
        self.assertEqual(len(ts),6)
        self.assertTrue(all(ts[i]-ts[i+1]==timedelta(minutes=10) for i in range(5)))
    def paths(self):
        return [RAW/t.strftime("%Y%m")/t.strftime("%d")/f"NC_H09_{t:%Y%m%d_%H%M}_R21_FLDK.06001_06001.nc"
                for t in expected_times(self.target)]
    def test_future_leakage(self):
        with self.assertRaises(AssertionError):load_himawari_sequence(self.paths(),None,self.target-timedelta(minutes=10))
    def test_channel_order(self):
        self.assertEqual(CHANNELS,("tbb_08","tbb_09","tbb_10","tbb_11","tbb_13","tbb_15","tbb_16"))
        x,*_=_read_local(self.path)
        np.testing.assert_allclose(x[:,0,0],273.15+np.arange(7)*.01,atol=3e-5)
    def test_shape_dtype_mask_nan(self):
        x,m,lat,lon,meta=_read_local(self.path)
        self.assertEqual(x.shape,(7,2,3));self.assertEqual(x.dtype,np.float32);self.assertEqual(m.dtype,bool)
        self.assertTrue(np.isnan(x[~m]).all());self.assertFalse((x[~m]==0).any())
        self.assertTrue(np.isfinite(x[m]).all());self.assertEqual(int(m.sum()),28)
    def test_no_latitude_flip(self):
        *_,lat,lon,meta=_read_local(self.path)
        np.testing.assert_array_equal(lat,[30,20])
    def test_sequence_shape_reshape(self):
        with patch("read_himawari.read_himawari_7ch",return_value=_read_local(self.path)):
            x,m=load_himawari_sequence(self.paths(),None,self.target)
        self.assertEqual(x.shape,(6,7,2,3));self.assertEqual(m.shape,x.shape)
        self.assertEqual(x.reshape(42,2,3).shape,(42,2,3))
        np.testing.assert_array_equal(x.reshape(42,2,3)[7],x[1,0])
    def test_wrong_order_rejected(self):
        with self.assertRaises(AssertionError):load_himawari_sequence(self.paths()[::-1],None,self.target)
    def test_inconsistent_coords_rejected(self):
        first=_read_local(self.path);second=list(first);second[2]=first[2]+1
        with patch("read_himawari.read_himawari_7ch",side_effect=[first,second]):
            with self.assertRaises(CoordinateShapeError):load_himawari_sequence(self.paths(),None,self.target)
    def test_missing_channel(self):
        p=Path(self.temp.name)/"missing.nc";fixture(p,"tbb_13")
        with self.assertRaises(MissingChannelError):_read_local(p)
    def test_monotonic_detection(self):
        self.assertEqual(coordinate_info(np.array([3,2,1]),"lat")["direction"],"descending")
        self.assertTrue(coordinate_info(np.array([1,3,2]),"lat")["anomaly"])
        self.assertTrue(coordinate_info(np.array([1,np.nan,2]),"lat")["anomaly"])
    def test_missing_sequence(self):
        cols=["timestamp_filename_utc","relative_path","quality_class","flags","grid_signature","satellite",
              "read_success","has_all_7_channels"]
        s=build_sequences(pd.DataFrame(columns=cols),pd.DataFrame(columns=cols),2024,7)
        self.assertFalse(s.sequence_complete.any());self.assertTrue((s.missing_frame_count==6).all())
        self.assertEqual(len(s),31*24*6)
    def test_ambiguous_rejected(self):
        with self.assertRaises(AmbiguousCandidateError):unique_candidate(["one.nc","two.nc"])
    def test_same_tag_different_coordinates(self):
        one=grid_info(np.array([3,2]),np.array([1,2]),(7,2,2))
        two=grid_info(np.array([3,2]),np.array([2,3]),(7,2,2))
        self.assertNotEqual(one["grid_signature"],two["grid_signature"])
    def test_missing_decode_metadata(self):
        with self.assertRaises(MetadataError):decode_packed(np.array([1]),{})
    def test_invalid_float_and_fill(self):
        x,m=decode_packed(np.array([np.nan,np.inf,-32768,0]),dict(scale_factor=1,add_offset=273,
                           valid_min=-10,valid_max=10,missing_value=-32768))
        np.testing.assert_array_equal(m,[False,False,False,True]);self.assertEqual(x[-1],273)
    def test_h_output_prohibited(self):
        with self.assertRaises(ValueError):outpath(RAW/"202407/output.csv")
    def test_source_scope(self):
        with self.assertRaises(ValueError):sourcepath(RAW/"202408/01/file.nc")
        with self.assertRaises(ValueError):sourcepath(RAW/"202406/29/file.nc")
    def test_flags_column_selection_regression(self):
        from sample_audit import select_samples
        times=[(self.target+timedelta(minutes=10*i)).isoformat() for i in range(60)]
        sequences=pd.DataFrame({"target_time_utc":times,"sequence_complete":True,"loadable":True,
                                "contains_satellite_transition":False})
        master=pd.DataFrame({"timestamp_filename_utc":times,"flags":"TIME_MISMATCH","grid_tag":"test"})
        selected=select_samples(sequences,master)
        self.assertEqual(int(selected.selection_reason.str.contains("random_seed_42").sum()),50)
        self.assertEqual(selected.target_time_utc.nunique(),len(selected))

    def test_no_training_or_normalization_calls(self):
        forbidden={"backward","step","nan_to_num"}
        for p in (PROJECT/"src").glob("*.py"):
            if p.name=="preflight.py":continue
            tree=ast.parse(p.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if isinstance(node,ast.Call) and isinstance(node.func,ast.Attribute):
                    self.assertNotIn(node.func.attr,forbidden,msg=str(p))
                if isinstance(node,(ast.FunctionDef,ast.Name)):
                    name=getattr(node,"name",getattr(node,"id","")).lower()
                    self.assertNotIn(name,{"train_mean","train_std","normalization_stats"})

if __name__=="__main__":unittest.main(verbosity=2)
