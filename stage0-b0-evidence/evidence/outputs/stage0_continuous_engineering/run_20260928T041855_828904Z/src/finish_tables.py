"""Complete supplemental tables and CSV/Parquet validation; never mutate raw sources."""
import json,importlib,sys
from pathlib import Path
import pandas as pd
from config import *
from common import *

def finish_tables():
    cov=OUT/"GFS/gfs_temporal_coverage.csv"
    df=pd.read_csv(cov)
    df["lead_hours_observed"]=df.lead_hours_observed.str.replace(r"np\.int64\((\d+)\)",r"\1",regex=True)
    df.to_csv(cov,index=False,encoding="utf-8-sig")
    mapping=OUT/"GFS/gfs_variable_mapping.csv"
    df=pd.read_csv(mapping);total=len(pd.read_csv(OUT/"GFS/gfs_inventory.csv"));df["total_main_root_files"]=total;df["availability_fraction"]=df.file_count/total
    df["coverage_denominator_note"]="Fraction for this exact metadata/shape/level signature; canonical coverage aggregates signatures separately"
    df.to_csv(mapping,index=False,encoding="utf-8-sig")
    times=pd.read_csv(OUT/"GFS/gfs_time_semantics_audit.csv")
    dup=times[times.duplicated(["init_time","lead_time_hours"],keep=False)].copy()
    write_csv(OUT/"GFS/gfs_duplicate_init_lead_pairs.csv",dup)
    conflicts=times[times.auxiliary_metadata_conflict].copy()
    write_csv(OUT/"GFS/gfs_auxiliary_time_metadata_needs_review.csv",conflicts)
    write_json(OUT/"logs/table_completion_record.json",{
        "changes":["Normalize numpy scalar display in new temporal coverage CSV","Add per-signature availability fraction to new mapping table",
                   "Add duplicate init/lead and auxiliary metadata review tables"],
        "raw_sources_modified":False,"historical_runs_modified":False,"duplicate_pair_file_count":len(dup)})
    versions={"python":sys.executable,"imports":{}}
    for name in ["zarr","numcodecs","pyarrow","xarray","netCDF4","numpy","pandas","torch","pytest"]:
        m=importlib.import_module(name)
        versions["imports"][name]={"import":"PASS","version":getattr(m,"__version__","UNKNOWN")}
    assert Path(sys.executable).resolve()==PYTHON.resolve()
    write_json(OUT/"logs/dependency_import_verification.json",versions)
    results=[]
    for path in sorted(OUT.rglob("*.csv")):
        target=path.with_suffix(".parquet")
        row={"csv":str(path.relative_to(OUT)),"parquet":str(target.relative_to(OUT)),"engine":"pyarrow","status":"NOT_RUN","error":""}
        try:
            df=pd.read_csv(path)
            if target.exists():raise FileExistsError(target)
            df.to_parquet(target,engine="pyarrow",index=False,compression="snappy")
            back=pd.read_parquet(target,engine="pyarrow")
            pd.testing.assert_frame_equal(df,back)
            row.update(status="PASS",rows=len(df),columns=len(df.columns),parquet_bytes=target.stat().st_size)
        except Exception as e:row.update(status="FAILED",error=f"{type(e).__name__}: {e}")
        results.append(row)
    write_csv(OUT/"logs/parquet_write_validation.csv",results)
    # This validation table has its own pair, checked directly without recursive self-inclusion.
    p=OUT/"logs/parquet_write_validation.csv";df=pd.read_csv(p);df.to_parquet(p.with_suffix(".parquet"),engine="pyarrow",index=False)
    pd.testing.assert_frame_equal(df,pd.read_parquet(p.with_suffix(".parquet"),engine="pyarrow"))
    write_json(OUT/"logs/parquet_summary.json",{"attempted":len(results),"passed":sum(r["status"]=="PASS" for r in results),
        "failed":[r for r in results if r["status"]!="PASS"],"validation_table_pair":"PASS",
        "scope":"All audit CSVs existing at conversion; final output_manifest is administrative CSV only",
        "engine":"pyarrow","compression":"snappy","roundtrip":"Exact pandas frame equality after CSV parse"})
    print(dumps({"imports":versions,"parquet_passed":sum(r["status"]=="PASS" for r in results),"parquet_total":len(results),"duplicate_pairs":len(dup)}),flush=True)
if __name__=="__main__":finish_tables()
