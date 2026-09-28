"""GFS semantics, read-only guards, mapping and research-period representation."""
from pathlib import Path
from datetime import datetime,timezone
import sys
import numpy as np,pytest,netCDF4
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"src"))
from config import GFS,IMERG,OUT,REQUIRED
from rules import parse_filename,canonical_variables,forbidden_precip,pressure_to_hpa,choose_main,unique_time
from common import coord_hash,source_path,output_path
from time_audit import audit_time
from coverage import build_matrix,research_months

def test_gfs_filename():
    r=parse_filename("gfs_0p25_2024123118_f006.nc")
    assert r["init"]==datetime(2024,12,31,18,tzinfo=timezone.utc)
    assert r["valid"]==datetime(2025,1,1,tzinfo=timezone.utc) and r["lead_hours"]==6
def test_unknown_filename_not_guessed():
    with pytest.raises(ValueError):parse_filename("gfs_unknown.nc")
def test_thermo_filename():
    assert parse_filename("gfs_thermo_0p25_2025010106_f003.nc")["lead_hours"]==3
def test_coordinate_hash_numeric_and_endian():
    a=np.array([1,2,3],dtype="<f4")
    assert coord_hash(a)==coord_hash(a.astype(">f4"))==coord_hash(a.astype("f8"))
def test_coordinate_hash_internal_change():
    assert coord_hash([0,1,2])!=coord_hash([0,1.00001,2])
@pytest.mark.parametrize("raw,canonical",[("Temperature_isobaric",["T_850","T_700","T_500"]),
    ("Relative_humidity_isobaric",["RH_850","RH_700","RH_500"]),
    ("u-component_of_wind_isobaric",["U_850","U_700"]),("v-component_of_wind_isobaric",["V_850","V_700"])])
def test_required_pressure_mapping(raw,canonical):
    result,_=canonical_variables(raw,{},("valid_time","pressure_level","latitude","longitude"),[500,700,850])
    assert result==canonical
def test_surface_pressure():
    assert canonical_variables("Pressure_surface",{"units":"Pa"},("valid_time","latitude","longitude"),[])[0]==["PS"]
def test_msl_not_surface_pressure():
    assert canonical_variables("Pressure_reduced_to_MSL_msl",{"shortName":"sp"},("time","lat","lon"),[])[0]==[]
def test_specific_humidity_not_relative():
    assert canonical_variables("Specific_humidity_isobaric",{},("pressure_level","latitude","longitude"),[500,700,850])[0]==[]
def test_ten_meter_wind_not_isobaric():
    assert canonical_variables("u-component_of_wind_height_above_ground",{"standard_name":"eastward_wind"},("time","lat","lon"),[])[0]==[]
@pytest.mark.parametrize("name",["APCP","PRATE","tp","Total_precipitation_surface_3_Hour_Accumulation"])
def test_precipitation_never_predictor(name):
    assert forbidden_precip(name,{})
    assert canonical_variables(name,{},("time","latitude","longitude"),[])[0]==[]
def test_pwat_not_precipitation():
    name="Precipitable_water_entire_atmosphere_single_layer"
    assert not forbidden_precip(name,{})
    assert canonical_variables(name,{},("time","lat","lon"),[])[0]==["PWAT"]
def test_pressure_units():
    assert pressure_to_hpa([85000,70000],"Pa")==[850,700]
    with pytest.raises(ValueError):pressure_to_hpa([850],"unknown")
def test_multi_root_choice_no_merge():
    roots=[Path("F:/raw/GFS_thermo"),Path("F:/raw/GFS")]
    assert choose_main(roots,roots[1])==roots[1]
    with pytest.raises(ValueError):choose_main([Path("F:/a"),Path("F:/b")],Path("F:/absent"))
def test_raw_guards():
    with pytest.raises(ValueError):output_path(GFS/"output.csv")
    with pytest.raises(ValueError):source_path(GFS.parent/"GFS_thermo/anything.nc")
    with pytest.raises(ValueError):source_path(IMERG/"2024/imerg_20240701.nc")
def test_missing_timestamp_not_epoch():
    assert unique_time([])==(None,"UNKNOWN")
def test_conflicting_time_not_arbitrarily_selected():
    assert unique_time([("a",1),("b",2)])==(None,"CONFLICT")
def make_times(path,missing=False,contradict=False):
    with netCDF4.Dataset(str(path),"w") as ds:
        if missing:return
        ds.createDimension("valid_time",1)
        ref=ds.createVariable("reftime","i8",());ref.units="hours since 2024-01-01 00:00:00";ref[...]=0
        v=ds.createVariable("valid_time","i8",("valid_time",));v.units="hours since 2024-01-01 00:00:00";v[:]=[4 if contradict else 3]
        v.udunits="hours since 2023-01-01 00:00:00"
        ds.forecast_cycle="2024010100";ds.forecast_hour=3
        ds.conservative_available_time_utc="2024-01-01T05:00:00Z"
        ds.availability_note="Assumption, not observed publication"
def test_time_reconstruction_and_proxy(tmp_path):
    p=tmp_path/"time.nc";make_times(p)
    with netCDF4.Dataset(str(p),"r") as ds:r=audit_time(ds,"gfs_0p25_2024010100_f003.nc")
    assert r["time_consistency_status"]=="PASS" and r["lead_time_hours"]==3
    assert r["auxiliary_metadata_conflict"] and r["release_time"] is None
    assert r["operational_availability_time"] is None
def test_valid_init_lead_mismatch(tmp_path):
    p=tmp_path/"time.nc";make_times(p,contradict=True)
    with netCDF4.Dataset(str(p),"r") as ds:r=audit_time(ds,"gfs_0p25_2024010100_f003.nc")
    assert r["time_consistency_status"]=="FAIL"
def test_missing_metadata_no_fake_time(tmp_path):
    p=tmp_path/"empty.nc";make_times(p,missing=True)
    with netCDF4.Dataset(str(p),"r") as ds:r=audit_time(ds,"unknown.nc")
    assert r["init_time"] is None and r["valid_time"] is None and r["time_consistency_status"]=="UNKNOWN"
def test_matrix_and_october_gap():
    matrix=build_matrix({"2025-09":30},{},{},{})
    assert len(matrix)==24 and "2025-10" in set(matrix["YYYY-MM"])
    assert matrix.set_index("YYYY-MM").loc["2025-10","IMERG_available"]=="MISSING"
    assert matrix.set_index("YYYY-MM").loc["2025-09","IMERG_available"]=="READY"
    assert matrix.set_index("YYYY-MM").loc["2025-10","Himawari_available"]=="NOT_AUDITED"
def test_file_coverage_not_variable_readiness():
    matrix=build_matrix({},{"2025-03":{"inventory_status":"READY","core_complete":False}},{},{})
    assert matrix.set_index("YYYY-MM").loc["2025-03","GFS_available"]=="PARTIAL"

def test_calendar_month_edges_are_audited(monkeypatch):
    import pandas as pd
    import coverage as cov
    outputs={}
    monkeypatch.setattr(cov,"write_csv",lambda path,rows,columns=None:outputs.setdefault(path.name,rows))
    inv=pd.DataFrame([{"relative_path":"middle","read_success":True}])
    timing=pd.DataFrame([{"relative_path":"middle","init_time":"2024-02-15T00:00:00Z",
                          "valid_time":"2024-02-15T00:00:00Z","lead_time_hours":0}])
    presence=pd.DataFrame([{"relative_path":"middle",**{v:True for v in REQUIRED},
                           "core_variable_complete":True,"surface_pressure_support_status":"PASS"}])
    result,hours,leads=cov.temporal_coverage(inv,timing,presence)
    assert result.iloc[0].expected_init_count_calendar_month==29
    assert result.iloc[0].missing_cycles==28
    assert result.iloc[0].inventory_status=="PARTIAL"

def test_staging_opens_read_only_and_cleans_only_owned_copy(tmp_path,monkeypatch):
    import common
    source=tmp_path/"synthetic.nc"
    with netCDF4.Dataset(str(source),"w") as ds:
        ds.createDimension("x",1);v=ds.createVariable("x","f4",("x",));v[:]=[7]
    before=common.sha256(source);records=[];modes=[]
    real=netCDF4.Dataset
    def capture(path,mode,*args,**kwargs):
        modes.append(mode)
        return real(path,mode,*args,**kwargs)
    monkeypatch.setattr(common,"source_path",lambda p:Path(p).resolve())
    monkeypatch.setattr(common,"append_json",lambda p,r:records.append(r))
    monkeypatch.setattr(common.netCDF4,"Dataset",capture)
    reader=common.Reader()
    with reader.open(source,hash_check=True) as ds:
        assert ds["x"][0]==7
    assert modes==["r"] and common.sha256(source)==before
    assert len(reader.created)==0 and records[0]["cleanup_success"]
    assert not Path(records[0]["cache_path"]).exists() and source.exists()
    assert records[0]["sha256_verified"] and records[0]["source_stat_unchanged"]

def test_single_file_failure_is_isolated(tmp_path,monkeypatch):
    import contextlib,pandas as pd
    import gfs_audit as audit
    bad=tmp_path/"gfs_0p25_2024010100_f000.nc"
    good=tmp_path/"gfs_0p25_2024010106_f000.nc"
    bad.write_bytes(b"\x89HDF\r\n\x1a\ncorrupt synthetic container")
    with netCDF4.Dataset(str(good),"w") as ds:
        ds.createDimension("latitude",2);ds.createDimension("longitude",2)
        ds.createVariable("latitude","f4",("latitude",))[:]=[25,24]
        ds.createVariable("longitude","f4",("longitude",))[:]=[100,101]
    before_bad=bad.read_bytes();before_good=good.read_bytes();outputs={}
    class SyntheticReader:
        @contextlib.contextmanager
        def open(self,p,hash_check=False):
            with netCDF4.Dataset(str(p),"r") as ds:yield ds
    monkeypatch.setattr(audit,"GFS",tmp_path)
    monkeypatch.setattr(audit,"discover",lambda:([bad,good],[]))
    monkeypatch.setattr(audit,"Reader",SyntheticReader)
    monkeypatch.setattr(audit,"write_csv",lambda p,r,columns=None:outputs.update({p.name:r.copy() if isinstance(r,pd.DataFrame) else pd.DataFrame(r)}))
    monkeypatch.setattr(audit,"write_json",lambda p,r:outputs.update({p.name:r}))
    monkeypatch.setattr(audit,"append_json",lambda *args:None)
    audit.audit()
    inventory=outputs["gfs_inventory.csv"]
    assert list(inventory.read_success)==[False,True]
    assert len(outputs["gfs_read_errors.csv"])==1
    assert outputs["gfs_execution.json"]["read_success"]==1
    assert bad.read_bytes()==before_bad and good.read_bytes()==before_good

def test_old_run_write_is_rejected():
    import common
    previous=OUT.parent/"run_20260928T031444_178129Z"/"README.md"
    with pytest.raises(ValueError):common.write_text(previous,"must never overwrite")

def test_existing_output_cannot_be_overwritten(tmp_path,monkeypatch):
    import common
    path=tmp_path/"already_present.txt";path.write_text("historical content",encoding="utf-8")
    monkeypatch.setattr(common,"output_path",lambda p:Path(p))
    with pytest.raises(FileExistsError):common.write_text(path,"replacement")
    assert path.read_text(encoding="utf-8")=="historical content"
