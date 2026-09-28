"""P0 scientific-rule and safety tests; no researcher convention is inferred."""
from datetime import datetime,date,timedelta,timezone
from pathlib import Path
import sys,hashlib,uuid
import numpy as np,pytest,netCDF4
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"src"))
import common
from config import OUTPUT,CACHE,IMERG,HIMAWARI
from common import coordinate_hash,decode_cf_time,parse_iso_utc,sha256,Staging,source_path,output_path
from time_rules import audit_daily_times,latencies,imerg_filename_date,himawari_filename
from data_qc import decode_values,variable_qc
from himawari_latency import logical_anomalies

@pytest.fixture
def slots():
    base=datetime(2019,1,1,tzinfo=timezone.utc)
    return [base+timedelta(minutes=30*i) for i in range(48)]

def test_daily_48_slots(slots):
    r=audit_daily_times(slots,date(2019,1,1))
    assert r["count_is_48"] and r["exact_daily_slots"] and r["strict_30min_intervals"]

def test_missing_half_hour(slots):
    r=audit_daily_times(slots[:10]+slots[11:],date(2019,1,1))
    assert r["missing_time_count"]==1 and not r["count_is_48"] and r["non_30min_interval_count"]==1

def test_duplicate_half_hour(slots):
    r=audit_daily_times(slots+[slots[0]],date(2019,1,1))
    assert r["duplicate_time_count"]==1 and not r["exact_daily_slots"]

def test_non_30min_preserves_count(slots):
    slots[10]+=timedelta(seconds=1)
    r=audit_daily_times(slots,date(2019,1,1))
    assert r["count_is_48"] and not r["strict_30min_intervals"]

def test_filename_date_mismatch(slots):
    assert not audit_daily_times(slots,date(2019,1,2))["filename_date_matches"]

def test_empty_times():
    r=audit_daily_times([],date(2019,1,1))
    assert r["missing_time_count"]==48 and not r["exact_daily_slots"]

def test_leap_day_filename():
    assert imerg_filename_date("imerg_20200229.nc")==date(2020,2,29)
    with pytest.raises(ValueError):imerg_filename_date("imerg_20190229.nc")

def test_coordinate_hash_equal_byteorder():
    x=np.array([19.05,19.15],dtype="<f4")
    assert coordinate_hash(x)==coordinate_hash(x.astype(">f4"))
    assert coordinate_hash(x)==coordinate_hash(x.astype("f8"))

def test_coordinate_hash_detects_internal_change():
    x=np.array([0.,1.,2.,3.]);y=np.array([0.,1.001,2.,3.])
    assert x.min()==y.min() and x.max()==y.max()
    assert coordinate_hash(x)!=coordinate_hash(y)

def test_coordinate_hash_direction():
    x=np.array([1.,2.,3.])
    assert coordinate_hash(x)!=coordinate_hash(x[::-1])

def test_nan_fill_not_zero():
    raw=np.array([0.,np.nan,-9999.,2.])
    x,mask,_,_=decode_values(raw,{"_FillValue":-9999.})
    np.testing.assert_array_equal(mask,[True,False,False,True])
    assert x[0]==0 and np.isnan(x[1:3]).all()
    assert int((x[mask]==0).sum())==1

def test_negative_not_silently_filtered():
    x,m,_,_=decode_values(np.array([-1.,0.,1.]),{})
    assert m.all() and x[0]==-1 # Recorded for review, not corrected by a new scientific rule.

def test_mjd_decode():
    start=decode_cf_time([60492.0],"days since 1858-11-17 0:0:0")[0]
    assert start==datetime(2024,7,1,tzinfo=timezone.utc)
    later=decode_cf_time([60492.0+60/86400],"days since 1858-11-17 0:0:0")[0]
    assert abs((later-start).total_seconds()-60)<1e-5 # floating-day decoding precision only

@pytest.mark.parametrize("text",["2024-07-01T00:20:00Z","2024-07-01T00:20:00+00:00","2024-07-01T08:20:00+08:00"])
def test_iso_utc(text):
    assert parse_iso_utc(text)==datetime(2024,7,1,0,20,tzinfo=timezone.utc)

def test_naive_created_timestamp_rejected():
    with pytest.raises(ValueError):parse_iso_utc("2024-07-01T00:20:00")

def test_latency_values_and_order():
    nominal=datetime(2024,7,1,tzinfo=timezone.utc)
    r=latencies(nominal,nominal+timedelta(seconds=40),nominal+timedelta(seconds=580),nominal+timedelta(seconds=1180))
    assert r["start_offset_seconds"]==40 and r["scan_duration_seconds"]==540
    assert r["creation_delay_seconds"]==600 and r["nominal_to_created_seconds"]==1180
    assert r["causal_as_latest"] and not r["created_before_end"]

@pytest.mark.parametrize("end_seconds,expected",[(599.9,True),(600,True),(600.000001,False)])
def test_causality_boundary(end_seconds,expected):
    nominal=datetime(2024,7,1,tzinfo=timezone.utc)
    r=latencies(nominal,nominal+timedelta(seconds=40),nominal+timedelta(seconds=end_seconds),nominal+timedelta(hours=10))
    assert r["causal_as_latest"] is expected # Production delay is irrelevant to observation causality.

def test_temporal_order_independent_tail():
    nominal=datetime(2024,7,1,tzinfo=timezone.utc)
    r=latencies(nominal,nominal+timedelta(seconds=40),nominal+timedelta(seconds=580),nominal+timedelta(seconds=570))
    flags=logical_anomalies(r,1000)
    assert ("TEMPORAL_ORDER_ERROR","date_created < obs_end") in flags
    assert not any(k=="LATENCY_TAIL_REVIEW" for k,_ in flags)

def test_tail_marker_inclusive_not_error():
    flags=logical_anomalies({"creation_delay_seconds":1000,"created_before_end":False},1000)
    assert [k for k,_ in flags]==["LATENCY_TAIL_REVIEW"]

def test_himawari_filename():
    r=himawari_filename("NC_H09_20240701_0000_R21_FLDK.06001_06001.nc")
    assert r["nominal"]==datetime(2024,7,1,tzinfo=timezone.utc) and r["satellite"]=="H09"

def test_source_roots_and_output_guard():
    with pytest.raises(ValueError):source_path(HIMAWARI.parent/"202406/30/a.nc")
    with pytest.raises(ValueError):source_path(IMERG.parent/"GFS/a.nc")
    with pytest.raises(ValueError):output_path(IMERG/"result.csv")

def test_real_netcdf_qc_denominators(tmp_path):
    path=tmp_path/"qc.nc"
    with netCDF4.Dataset(str(path),"w") as ds:
        ds.createDimension("time",1);ds.createDimension("pixel",5)
        v=ds.createVariable("precipitation","f4",("time","pixel"),fill_value=np.nan)
        v[:]=np.array([[0.,np.nan,.2,2.,21.]],dtype="f4")
    with netCDF4.Dataset(str(path),"r") as ds:
        ds.set_auto_maskandscale(False);r=variable_qc(ds["precipitation"])
    assert r["precip_valid_fraction"]==.8 and r["R_eq_0_fraction"]==.25
    assert r["R_gt_20_fraction"]==.25 and r["R_gt_20_total_fraction"]==.2
    assert r["precip_nan_fraction"]==.2

def test_qi_exact_median_no_threshold(tmp_path):
    path=tmp_path/"qi.nc"
    with netCDF4.Dataset(str(path),"w") as ds:
        ds.createDimension("time",1);ds.createDimension("pixel",4)
        v=ds.createVariable("qi","f4",("time","pixel"),fill_value=np.nan)
        v[:]=np.array([[0.,np.nan,.2,.8]],dtype="f4")
    with netCDF4.Dataset(str(path),"r") as ds:
        ds.set_auto_maskandscale(False);r=variable_qc(ds["qi"],qi=True)
    assert r["valid_pixel_count"]==3 and r["QI_median"]==pytest.approx(.2)
    assert r["QI_min"]==0

def test_chinese_fallback_source_unchanged(tmp_path,monkeypatch):
    original=tmp_path/"原始测试.nc"
    with netCDF4.Dataset(str(tmp_path/"ascii.nc"),"w") as ds:
        ds.createDimension("x",1);ds.createVariable("value","f4",("x",))[:]=[7.]
    original.write_bytes((tmp_path/"ascii.nc").read_bytes())
    before=sha256(original);stat=original.stat()
    def only_fixture(path):
        p=Path(path).resolve()
        if p!=original.resolve():raise ValueError("Fixture scope")
        return p
    monkeypatch.setattr(common,"source_path",only_fixture)
    folder=CACHE/("pytest_staging_"+uuid.uuid4().hex)
    stage=Staging(folder,OUTPUT/"tests"/("staging_test_"+uuid.uuid4().hex+".jsonl"))
    with stage.open(original,verify_hash=True) as ds:assert ds["value"][0]==7
    assert sha256(original)==before
    assert original.stat().st_size==stat.st_size and original.stat().st_mtime_ns==stat.st_mtime_ns
    assert not list(folder.glob("*.nc"))

def test_failed_read_does_not_modify_source(tmp_path,monkeypatch):
    original=tmp_path/"损坏样本.nc";original.write_bytes(b"intentionally not NetCDF")
    before=sha256(original)
    monkeypatch.setattr(common,"source_path",lambda p:original.resolve())
    stage=Staging(CACHE/("pytest_failure_"+uuid.uuid4().hex),OUTPUT/"tests"/("failed_staging_"+uuid.uuid4().hex+".jsonl"))
    with pytest.raises(OSError):
        with stage.open(original):pass
    assert sha256(original)==before and not list(stage.folder.glob("*.nc"))
