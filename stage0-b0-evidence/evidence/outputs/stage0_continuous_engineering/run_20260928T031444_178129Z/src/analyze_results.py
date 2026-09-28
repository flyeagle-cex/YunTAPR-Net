"""Aggregate executed audits, calendar coverage and source-integrity evidence."""
import sys,json,importlib.metadata
from pathlib import Path
from collections import Counter
from datetime import datetime,timezone
import numpy as np,pandas as pd
from config import *
from common import *
from coverage import temporal_coverage,build_matrix

def csv(relative):return pd.read_csv(OUT/relative)
def analyze():
    inv=csv("GFS/gfs_inventory.csv");times=csv("GFS/gfs_time_semantics_audit.csv")
    present=csv("GFS/gfs_variable_presence.csv");grid=csv("GFS/gfs_grid_audit.csv")
    cov,hours,leads=temporal_coverage(inv,times,present)
    bymonth={r["month"]:{**r,"core_complete":r["core_complete_files"]==r["file_count"]} for r in cov.to_dict("records")}
    imerg=pd.read_csv(P0/"IMERG/imerg_inventory.csv")
    imergcounts=pd.to_datetime(imerg.date).dt.strftime("%Y-%m").value_counts().to_dict()
    targeted=json.loads((OUT/"CROSS_SOURCE/imerg_202510_targeted_presence.json").read_text(encoding="utf-8"))
    if targeted["count"]!=0:raise RuntimeError("IMERG October presence changed; reconcile monthly prior evidence")
    imergcounts["2025-10"]=0
    him=csv("CROSS_SOURCE/himawari_month_directory_evidence.csv")
    matrix=build_matrix(imergcounts,bymonth,dict(zip(him.month,him.status)),{"SRTM":"PARTIAL","mask":"PARTIAL","external":"NOT_AUDITED"})
    write_csv(OUT/"CROSS_SOURCE/research_period_data_matrix.csv",matrix)
    years=[]
    merged=inv[["relative_path","year"]].merge(present,on="relative_path")
    for year,group in merged.groupby("year"):
        years.append({"year":year,"file_count":len(group),"core_complete_files":int(group.core_variable_complete.sum()),
                     **{v+"_count":int(group[v].sum()) for v in REQUIRED}})
    write_csv(OUT/"GFS/gfs_year_variable_coverage.csv",years)
    # Per-file stat evidence covers every main-root file; cryptographic evidence covers a stated sample.
    checks=[]
    for r in inv.to_dict("records"):
        path=(GFS/r["relative_path"]).resolve()
        if not path.is_relative_to(GFS.resolve()):raise ValueError("Inventory path outside raw root")
        st=path.stat()
        checks.append({"relative_path":r["relative_path"],"size_before":r["size_bytes"],"size_after":st.st_size,
                       "mtime_ns_before":r["mtime_ns"],"mtime_ns_after":st.st_mtime_ns,
                       "unchanged":st.st_size==r["size_bytes"] and st.st_mtime_ns==r["mtime_ns"]})
    write_csv(OUT/"logs/gfs_source_integrity_after.csv",checks)
    samples=csv("logs/gfs_source_sample_hashes_before.csv").to_dict("records")
    for row in samples:
        row["sha256_after"]=sha256(row["source_path"]);row["unchanged"]=row["sha256_before"]==row["sha256_after"]
    write_csv(OUT/"logs/gfs_source_sample_hashes_after.csv",samples)
    # Spatial center ranges are not a gridded common-valid mask.
    rows=[]
    hi=pd.read_csv(HIM_AUDIT/"qc/grid_consistency_report_202407.csv")
    for r in hi.to_dict("records"):
        rows.append({"source":"Himawari","evidence":str(HIM_AUDIT/"qc/grid_consistency_report_202407.csv"),
            **{k:r[k] for k in ["lat_min","lat_max","lon_min","lon_max","shape","lat_direction","lon_direction"]},
            "resolution_lat":r["median_dlat"],"resolution_lon":r["median_dlon"],
            "coverage_scope":"2024-07 only; original descending latitude retained"})
    ig=pd.read_csv(P0/"IMERG/imerg_grid_audit.csv").drop_duplicates("grid_hash")
    for r in ig.to_dict("records"):
        rows.append({"source":"IMERG","evidence":str(P0/"IMERG/imerg_grid_audit.csv"),
            **{k:r[k] for k in ["lat_min","lat_max","lon_min","lon_max","lat_direction","lon_direction"]},
            "shape":str((r["lat_count"],r["lon_count"])),"resolution_lat":r["mean_dlat"],"resolution_lon":r["mean_dlon"],
            "coverage_scope":"Prior full-library audit reused; this run reads two boundary files only"})
    for r in grid[grid.status.eq("OK")].drop_duplicates("grid_hash").to_dict("records"):
        rows.append({"source":"GFS","evidence":"GFS/gfs_grid_audit.csv",
            **{k:r[k] for k in ["lat_min","lat_max","lon_min","lon_max","lat_direction","lon_direction","resolution_lat","resolution_lon"]},
            "shape":str((r["lat_count"],r["lon_count"])),"coverage_scope":"Full main-root coordinate metadata audit"})
    static=json.loads((OUT/"CROSS_SOURCE/static_evidence.json").read_text(encoding="utf-8"))
    rows.append({"source":"SRTM","evidence":"CROSS_SOURCE/srtm_tile_inventory.csv",**static["SRTM"]["bounds"],
        "shape":"3601x3601 per tile (ZIP size evidence)","resolution_lat":1/3600,"resolution_lon":1/3600,
        "lat_direction":"NOT_READ","lon_direction":"NOT_READ",
        "coverage_scope":"Tile extent envelope; three holes recorded; raster void/value validity NOT_AUDITED"})
    write_csv(OUT/"CROSS_SOURCE/spatial_coverage_ranges.csv",rows)
    overlap={k:(max if k.endswith("min") else min)(r[k] for r in rows) for k in ["lat_min","lat_max","lon_min","lon_max"]}
    overlap["status"]="CANDIDATE ONLY";overlap["covers_yunnan_context"]="PENDING_RESEARCHER_CONFIRMATION"
    overlap["model_input_bbox"]=None
    holes=csv("CROSS_SOURCE/srtm_rectangle_missing_tiles.csv")
    overlap["srtm_missing_tiles_intersecting_open_overlap"]=int(sum(
        r.lon_min<overlap["lon_max"] and r.lon_min+1>overlap["lon_min"] and
        r.lat_min<overlap["lat_max"] and r.lat_min+1>overlap["lat_min"] for r in holes.itertuples()))
    write_json(OUT/"CROSS_SOURCE/common_numerical_overlap_candidate.json",overlap)
    io=[json.loads(line) for line in (OUT/"logs/staging_io.jsonl").read_text(encoding="utf-8").splitlines()]
    write_csv(OUT/"logs/staging_io.csv",io)
    stage={"files":len(io),"temporary_bytes_sum":sum(r["bytes"] for r in io),
        "single_file_max_bytes":max(r["bytes"] for r in io),"copy_seconds_sum":sum(r["copy_seconds"] or 0 for r in io),
        "read_seconds_sum":sum(r["read_seconds"] or 0 for r in io),
        "cleanup_failures":sum(not r["cleanup_success"] for r in io),
        "read_failures":sum(not r["read_success"] for r in io),
        "raw_stat_changes":sum(not r["source_stat_unchanged"] for r in io),
        "cache_nc_files_remaining":len(list(CACHE.glob("*.nc"))),
        "max_configured_cache_bytes":CONFIG["cache_max_bytes"],
        "concurrency_note":"GFS single-file reader and two-file IMERG task may briefly overlap; global observed peak was not instrumented"}
    write_json(OUT/"logs/staging_summary.json",stage)
    before=json.loads((OUT/"logs/environment_before.json").read_text(encoding="utf-8"))
    after={d.metadata["Name"]:d.version for d in importlib.metadata.distributions()}
    changed=[{"package":k,"old_version":before["packages"].get(k),"new_version":after.get(k)}
             for k in sorted(set(after)|set(before["packages"])) if after.get(k)!=before["packages"].get(k)]
    write_json(OUT/"logs/environment_after.json",{"python":sys.executable,"packages":after,"checked_utc":datetime.now(timezone.utc).isoformat()})
    write_json(OUT/"logs/dependency_change_record.json",{"changes":changed,"reason":"All discovered primary GFS files are NetCDF; existing netCDF4, numpy and pandas suffice. No package installation or upgrade executed."})
    summary={"file_count":len(inv),"total_bytes":int(inv.size_bytes.sum()),"read_success":int(inv.read_success.sum()),
        "formats":inv.file_format.value_counts().to_dict(),"netcdf_data_models":inv.netcdf_data_model.value_counts().to_dict(),
        "years":inv.year.value_counts().sort_index().to_dict(),"grid_count":int(grid.grid_hash.nunique()),
        "grid_examples":grid[grid.status.eq("OK")].drop_duplicates("grid_hash").to_dict("records"),
        "time_consistency":times.time_consistency_status.value_counts().to_dict(),
        "auxiliary_metadata_conflict_count":int(times.auxiliary_metadata_conflict.fillna(False).sum()),
        "auxiliary_notes_counts":times.auxiliary_metadata_notes.fillna("").value_counts().to_dict(),
        "raw_availability_proxy_count":int(times.availability_proxy_raw.notna().sum()),
        "init_hours_utc":hours,"lead_hours":leads,"lead_intervals_hours":np.diff(leads).tolist(),"maximum_lead_hours":max(leads),
        "core_complete_files":int(present.core_variable_complete.sum()),
        "surface_pressure_support":present.surface_pressure_support_status.value_counts().to_dict(),
        "forbidden_variable_rows":len(csv("GFS/gfs_forbidden_precip_variables_detected.csv")),
        "forbidden_files":int(csv("GFS/gfs_forbidden_precip_variables_detected.csv").relative_path.nunique()),
        "raw_stat_all_unchanged":all(r["unchanged"] for r in checks),"raw_hash_sample_all_unchanged":all(r["unchanged"] for r in samples),
        "dependency_changes":changed,"stage_io":stage,"overlap":overlap,
        "operational_availability":"NOT ESTABLISHED FROM CURRENT FILE METADATA"}
    write_json(OUT/"logs/analysis_summary.json",summary)
    print(dumps({k:v for k,v in summary.items() if k not in {"grid_examples","auxiliary_notes_counts","stage_io"}}),flush=True)
if __name__=="__main__":analyze()
