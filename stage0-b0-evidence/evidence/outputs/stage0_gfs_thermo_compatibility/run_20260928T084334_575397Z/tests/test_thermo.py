from pathlib import Path
import sys,copy,json
import numpy as np,pytest,netCDF4
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"src"))
from config import OUT,BASELINE,THERMO,MAIN
from common import coord_hash,output_path,source_path,write_text
from rules import parse_filename,canonical_variables,pressure_to_hpa
from time_audit import audit_time
from compat_rules import *

def pair():
    a={"valid_time":"2025-03-01T06:00:00Z","time_ok":True,"read_ok":True,"lat_hash":"a","lon_hash":"b"}
    b={**a,"exact_coordinate_match":True,**{v:True for v in TARGETS}}
    return a,b
def test_thermo_filename_cross_year():
    p=parse_filename("gfs_thermo_0p25_2024123118_f006.nc")
    assert p["lead_hours"]==6 and p["valid"].year==2025
def test_time_identity_and_release_not_fabricated(tmp_path):
    p=tmp_path/"example.nc"
    with netCDF4.Dataset(str(p),"w") as ds:
        ds.createDimension("valid_time",1)
        r=ds.createVariable("forecast_reference_time","i8",());r.units="hours since 2025-03-01";r[...]=0
        v=ds.createVariable("valid_time","i8",("valid_time",));v.units=r.units;v[:]=[6]
        ds.lead_time_hours=6;ds.conservative_available_time_utc="2025-03-01T05:00:00Z"
    with netCDF4.Dataset(str(p),"r") as ds:r=audit_time(ds,"gfs_thermo_0p25_2025030100_f006.nc")
    assert r["time_consistency_status"]=="PASS"
    assert r["release_time"] is None and r["operational_availability_time"] is None
def test_exact_pair():
    a,b=pair();assert classify_pair([a],[b])=="MATCHED_COMPLETE"
def test_valid_mismatch():
    a,b=pair();b["valid_time"]="wrong"
    assert classify_pair([a],[b])=="TIME_CONFLICT"
def test_grid_hash_match():
    r=compare_grid([2,1],[3,4],[2,1],[3,4])
    assert r["exact_coordinate_match"] and r["lat_hash_match"] and r["lon_hash_match"]
def test_small_coordinate_difference_not_accepted():
    r=compare_grid([2,1],[3,4],[2,1+1e-12],[3,4])
    assert not r["exact_coordinate_match"] and not r["lat_hash_match"] and r["max_abs_lat_diff"]>0
@pytest.mark.parametrize("name,expected",[("Temperature_isobaric",["T_850","T_700","T_500"]),("Relative_humidity_isobaric",["RH_850","RH_700","RH_500"])])
def test_target_semantics(name,expected):
    assert canonical_variables(name,{},("time","pressure_level","latitude","longitude"),[500,700,850])[0]==expected
@pytest.mark.parametrize("name,standard",[("Specific_humidity_isobaric","specific_humidity"),("Dewpoint_isobaric","dew_point_temperature"),("Potential_temperature_isobaric","air_potential_temperature")])
def test_wrong_physical_quantity_never_substituted(name,standard):
    assert canonical_variables(name,{"standard_name":standard},("pressure_level","latitude","longitude"),[500,700,850])[0]==[]
def test_pressure_pa_vs_hpa():
    assert pressure_to_hpa([50000,70000,85000],"Pa")==[500,700,850]
    with pytest.raises(ValueError):pressure_to_hpa([850],"UNKNOWN")
def test_one_to_many_detected():
    a,b=pair()
    assert classify_pair([a],[b,copy.deepcopy(b)])=="METADATA_CONFLICT"
    assert pairing_cardinality(1,2)=="one_to_many"
def test_many_to_one_detected():
    a,b=pair();assert classify_pair([a,a],[b])=="METADATA_CONFLICT"
    assert pairing_cardinality(2,1)=="many_to_one"
def test_thermo_only():
    a,b=pair();assert classify_pair([],[b])=="THERMO_ONLY"
def test_main_only():
    a,b=pair();assert classify_pair([a],[])=="MAIN_ONLY"
def test_lineage_missing_not_established():
    assert lineage_status({},{},"2025030100",6)=="NOT_ESTABLISHED"
def test_lineage_same_identifier_only_caveated():
    attrs={"source":"https://thredds.rda.ucar.edu/d084001/gfs.0p25.2025030100.f006.grib2"}
    assert lineage_status(attrs,attrs,"2025030100",6)=="SUPPORTED_WITH_CAVEATS"
def test_source_token_conflict():
    a={"source":"NCAR d084001 gfs.0p25.2024030100.f006.grib2"}
    b={"source":"NCAR d084001 gfs.0p25.2025030100.f006.grib2"}
    assert lineage_status(a,b,"2025030100",6)=="CONFLICTING"
def test_stale_history_does_not_replace_current_url():
    a={"source":"NOAA GFS","original_grib_url":"https://noaa-gfs-bdp-pds.s3.amazonaws.com/gfs.20250301/00/atmos/gfs.t00z.pgrb2.0p25.f006",
       "History":"Original Dataset = gfs.0p25.2023062212.f000.grib2"}
    b={"source":"NCAR d084001 gfs.0p25.2025030100.f006.grib2"}
    assert lineage_status(a,b,"2025030100",6)=="SUPPORTED_WITH_CAVEATS"
    assert source_evidence(a,"2025030100",6)["stale_history"]
@pytest.mark.parametrize("missing",TARGETS)
def test_month_ready_requires_all_six(missing):
    a,b=pair();b[missing]=False
    assert classify_pair([a],[b])=="MATCHED_PARTIAL_VARIABLES"
    assert month_status(1,1,1,0)=="PARTIAL"
def test_month_exact_readiness():
    assert month_status(12,12,12,12)=="READY"
    assert month_status(12,12,0,0)=="MISSING"
    assert month_status(12,11,12,11)=="PARTIAL"
def test_raw_write_protection():
    with pytest.raises(ValueError):output_path(THERMO/"modified.nc")
    with pytest.raises(ValueError):source_path(MAIN/"not_allowlisted.nc")
def test_old_run_not_writable():
    with pytest.raises(ValueError):write_text(BASELINE/"overwrite.txt","unsafe")
def test_directory_collision_prevention(tmp_path):
    p=tmp_path/"run_fixed";p.mkdir()
    with pytest.raises(FileExistsError):p.mkdir(exist_ok=False)
def test_no_fake_timestamp(tmp_path):
    p=tmp_path/"missing.nc"
    with netCDF4.Dataset(str(p),"w"):pass
    with netCDF4.Dataset(str(p),"r") as ds:r=audit_time(ds,"unknown.nc")
    assert r["init_time"] is None and r["valid_time"] is None and r["release_time"] is None
def test_duplicate_valid_time_different_vintage_not_pair_key():
    a,b=pair()
    assert classify_pair([a],[b])=="MATCHED_COMPLETE"
    assert ("2025-03-01T00:00:00Z",6)!=("2025-03-01T06:00:00Z",0)

def test_nullable_pair_boolean_roundtrip(tmp_path):
    import pandas as pd
    from table_schema import read_audit_csv
    p=tmp_path/"main_thermo_pairing.csv"
    pd.DataFrame({"main_auxiliary_metadata_conflict":[True,False,None],
                  "thermo_auxiliary_metadata_conflict":[None,False,True]}).to_csv(p,index=False)
    df=read_audit_csv(p)
    assert pd.isna(df.loc[0,"thermo_auxiliary_metadata_conflict"])
    assert df.loc[1,"thermo_auxiliary_metadata_conflict"]==False
    df.to_parquet(p.with_suffix(".parquet"),engine="pyarrow",index=False)
    pd.testing.assert_frame_equal(df,pd.read_parquet(p.with_suffix(".parquet"),engine="pyarrow"))
