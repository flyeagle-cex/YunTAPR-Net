"""Final artifact and cross-table checks; administrative manifests are not model samples."""
import ast,json,re
from datetime import datetime,timezone
from pathlib import Path
import numpy as np,pandas as pd
from config import *
from common import *

def validate():
    checks=[]
    def check(name,condition,detail=""):
        checks.append({"check":name,"status":"PASS" if condition else "FAIL","detail":detail})
        if not condition:raise AssertionError(name+": "+detail)
    required=[
        "FINAL_CONTINUOUS_ENGINEERING_REPORT.md","RESEARCHER_DECISIONS_REQUIRED.md","README.md",
        "docs/DECISION_LOG_STAGE0.md","schemas/sample_index_schema.md",
        "IMERG/imerg_20250624_boundary_extreme_check.txt","GFS/gfs_discovery_report.md",
        "GFS/gfs_inventory.csv","GFS/gfs_grid_audit.csv","GFS/gfs_variable_mapping.csv","GFS/gfs_variable_coverage.csv",
        "GFS/gfs_forbidden_precip_variables_detected.csv","GFS/gfs_time_semantics_audit.csv",
        "GFS/GFS_TIME_SEMANTICS_SUMMARY.md","GFS/gfs_temporal_coverage.csv",
        "CROSS_SOURCE/research_period_data_matrix.csv","CROSS_SOURCE/spatial_coverage_report.md",
        "logs/dependency_change_record.json","tests/pytest_verified.xml","final_continuous_engineering_status.json"]
    for relative in required:check("required:"+relative,(OUT/relative).is_file() and (OUT/relative).stat().st_size>0)
    inv=pd.read_csv(OUT/"GFS/gfs_inventory.csv");check("inventory_all_read",len(inv)==24388 and inv.read_success.all())
    for path in ["gfs_grid_audit.csv","gfs_variable_presence.csv","gfs_time_semantics_audit.csv"]:
        df=pd.read_csv(OUT/"GFS"/path)
        check("one_record_per_source:"+path,len(df)==len(inv) and df.relative_path.is_unique and set(df.relative_path)==set(inv.relative_path))
    grid=pd.read_csv(OUT/"GFS/gfs_grid_audit.csv")
    check("single_grid",grid.grid_hash.nunique()==1 and grid.coordinates_equal_first.all())
    timing=pd.read_csv(OUT/"GFS/gfs_time_semantics_audit.csv")
    check("all_valid_identity",timing.time_consistency_status.eq("PASS").all())
    check("unknown_release_stays_missing",timing.release_time.isna().all() and timing.operational_availability_time.isna().all())
    forbidden=pd.read_csv(OUT/"GFS/gfs_forbidden_precip_variables_detected.csv")
    check("forbidden_predictors_excluded",not forbidden.model_predictor_allowed.any() and len(forbidden)==13732)
    monthly=pd.read_csv(OUT/"GFS/gfs_temporal_coverage.csv")
    check("calendar_month_coverage",len(monthly)==84 and not monthly.month.duplicated().any())
    current=monthly[monthly.month.between("2025-03","2025-10")]
    check("2025_files_vs_variables",len(current)==8 and current.inventory_status.eq("READY").all() and current.core_complete_files.eq(0).all())
    matrix=pd.read_csv(OUT/"CROSS_SOURCE/research_period_data_matrix.csv")
    check("matrix_24_months",len(matrix)==24 and matrix["YYYY-MM"].is_unique and matrix.GFS_available.eq("PARTIAL").all())
    check("imerg_oct_gap",matrix.set_index("YYYY-MM").loc["2025-10","IMERG_available"]=="MISSING")
    point=pd.read_csv(OUT/"IMERG/imerg_boundary_values.csv")
    check("boundary_same_pixel",len(point)==3 and point.lat_index.nunique()==1 and point.lon_index.nunique()==1 and not point.missing.any())
    patch=pd.read_csv(OUT/"IMERG/imerg_boundary_patch_5x5.csv")
    check("boundary_patch_shape",len(patch)==25 and patch.latitude.nunique()==5 and patch.longitude.nunique()==5)
    hashes=pd.read_csv(OUT/"logs/imerg_boundary_source_hashes.csv")
    check("imerg_hashes_unchanged",len(hashes)==2 and hashes.unchanged.all())
    check("gfs_all_source_stats_unchanged",pd.read_csv(OUT/"logs/gfs_source_integrity_after.csv").unchanged.all())
    samples=pd.read_csv(OUT/"logs/gfs_source_sample_hashes_after.csv")
    check("gfs_five_sample_hashes",len(samples)==5 and samples.unchanged.all())
    tiles=pd.read_csv(OUT/"CROSS_SOURCE/srtm_tile_inventory.csv")
    check("srtm_directory_evidence",len(tiles)==237 and tiles.status.eq("CENTRAL_DIRECTORY_ONLY").all() and tiles.tile_shape_from_bytes.eq("(3601, 3601)").all())
    check("production_staging_clean",not list(CACHE.glob("*.nc")))
    changes=json.loads((OUT/"logs/dependency_change_record.json").read_text(encoding="utf-8"))
    check("no_dependency_changes",changes["changes"]==[])
    old=HIM_AUDIT.parent/"run_20260927T102645_638388Z/reports/output_status_202407.csv"
    check("historical_failed_gate_record_exists",old.is_file() and "BLOCKED_NOT_GENERATED" in old.read_text(encoding="utf-8-sig"))
    check("prior_completed_dry_run_exists",(HIM_AUDIT/"reports/final_dry_run_status_202407_v2.json").is_file())
    final=(OUT/"FINAL_CONTINUOUS_ENGINEERING_REPORT.md").read_text(encoding="utf-8")
    ending=["Stage-0 continuous engineering run complete.","Waiting for researcher scientific review.","No frozen scientific convention was changed automatically."]
    check("required_final_three_lines",final.strip().splitlines()[-3:]==ending)
    for p in OUT.rglob("*.py"):ast.parse(p.read_text(encoding="utf-8"),filename=str(p))
    check("all_python_sources_parse",True)
    for csv in OUT.rglob("*.csv"):
        if csv.name=="output_manifest.csv":continue
        parquet=csv.with_suffix(".parquet")
        check("parquet_pair:"+str(csv.relative_to(OUT)),parquet.exists())
        pd.testing.assert_frame_equal(pd.read_csv(csv),pd.read_parquet(parquet,engine="pyarrow"))
    check("all_csv_parquet_frames_equal",True)
    rows=[{"relative_path":str(p.relative_to(OUT)),"sha256":sha256(p)} for p in sorted(OUT.rglob("*.py"))]
    write_csv(OUT/"logs/code_sha256.csv",rows)
    pd.read_csv(OUT/"logs/code_sha256.csv").to_parquet(OUT/"logs/code_sha256.parquet",engine="pyarrow",index=False)
    write_csv(OUT/"logs/final_artifact_validation.csv",checks)
    pd.read_csv(OUT/"logs/final_artifact_validation.csv").to_parquet(OUT/"logs/final_artifact_validation.parquet",engine="pyarrow",index=False)
    done={"completed_utc":datetime.now(timezone.utc).isoformat(),"status":"PASS","checks":len(checks),
          "scientific_overall_status":"NEEDS_REVIEW","raw_mutation_executed":False}
    write_json(OUT/"logs/final_artifact_validation.json",done)
    append_json(OUT/"logs/audit_run.log",{"phase":"final_artifact_validation",**done})
    manifest=[]
    for p in sorted(OUT.rglob("*")):
        if p.is_file():manifest.append({"relative_path":str(p.relative_to(OUT)),"bytes":p.stat().st_size,"sha256":sha256(p)})
    write_csv(OUT/"output_manifest.csv",manifest)
    print(dumps(done),flush=True)
if __name__=="__main__":validate()
