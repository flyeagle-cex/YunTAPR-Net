"""Classify reused auxiliary-time evidence and finish integrity/statistical summaries."""
import json,importlib.metadata
from collections import Counter
from pathlib import Path
import numpy as np,pandas as pd
from config import *
from common import *
from compat_rules import source_evidence
from pairing_audit import metadata
def run():
    time=pd.read_csv(BASELINE/"GFS/gfs_time_semantics_audit.csv")
    inv=pd.read_csv(BASELINE/"GFS/gfs_inventory.csv").set_index("relative_path")
    globals=metadata(BASELINE/"GFS/global_metadata_patterns.jsonl")
    sample_paths={r["relative_path"] for r in json.loads((OUT/"logs/main_targeted_samples.json").read_text(encoding="utf-8"))}
    classified=[]
    for r in time.to_dict("records"):
        rel=r["relative_path"];attrs=globals[inv.loc[rel,"metadata_id"]]
        notes=str(r.get("auxiliary_metadata_notes",""));categories=[]
        if "History Original Dataset token differs" in notes:categories.append("STALE_HISTORY_TOKEN")
        if "CF units and auxiliary udunits decode differently" in notes:categories.append("ALTERNATIVE_REFERENCE_TIME")
        primary=r["time_consistency_status"]
        if primary in {"FAIL","CONFLICT"}:categories.append("TRUE_FORECAST_TIME_CONFLICT")
        if r["auxiliary_metadata_conflict"] and not categories:categories.append("UNKNOWN")
        context=[]
        if any("conversion" in k.lower() or "creat" in k.lower() for k in attrs):context.append("CONVERSION_TIMESTAMP")
        if any("source" in k.lower() or "archive" in k.lower() for k in attrs):context.append("DOWNLOAD_OR_ARCHIVE_RECORD")
        ev=source_evidence(attrs,pd.Timestamp(r["init_time"]).strftime("%Y%m%d%H"),r["lead_time_hours"])
        if ev["direct_tokens"] or ev["history_tokens"]:context.append("SOURCE_FILENAME_TOKEN")
        classified.append({"relative_path":rel,"year":pd.Timestamp(r["init_time"]).year,
            "original_auxiliary_conflict":r["auxiliary_metadata_conflict"],
            "classification":";".join(categories) if categories else "NO_AUXILIARY_CONFLICT",
            "context_metadata_categories":";".join(context),"primary_time_consistency":primary,
            "true_forecast_time_conflict_detected":primary in {"FAIL","CONFLICT"},
            "init_time_unchanged":r["init_time"],"valid_time_unchanged":r["valid_time"],"lead_time_unchanged":r["lead_time_hours"],
            "raw_sample_verified_this_run":rel in sample_paths,
            "source_token_evidence":dumps(ev),"original_auxiliary_notes":notes,
            "scope_note":"Classification of metadata evidence; does not prove payload originates from claimed source forecast"})
    df=pd.DataFrame(classified)
    write_csv(OUT/"TIME_LINEAGE/auxiliary_time_conflict_classification.csv",df)
    category=Counter(v for r in classified for v in r["classification"].split(";"))
    write_json(OUT/"TIME_LINEAGE/classification_summary.json",{
        "files":len(df),"original_auxiliary_conflicts":int(df.original_auxiliary_conflict.sum()),
        "classification_counts":dict(category),"true_primary_forecast_conflicts":int(df.true_forecast_time_conflict_detected.sum()),
        "targeted_raw_files":len(sample_paths),"targeted_years":sorted(df[df.raw_sample_verified_this_run].year.unique().tolist()),
        "main_full_raw_metadata_scan_performed":False})
    before=pd.read_csv(OUT/"logs/thermo_manifest_before.csv");checks=[]
    for row in before.to_dict("records"):
        p=(THERMO/row["relative_path"]).resolve();assert p.is_relative_to(THERMO.resolve())
        st=p.stat();checks.append({**row,"size_after":st.st_size,"mtime_ns_after":st.st_mtime_ns,
            "unchanged":st.st_size==row["size_bytes"] and st.st_mtime_ns==row["mtime_ns"]})
    assert all(r["unchanged"] for r in checks)
    write_csv(OUT/"logs/thermo_integrity_after.csv",checks)
    hashes=pd.read_csv(OUT/"logs/thermo_source_sample_hashes_before.csv").to_dict("records")
    for r in hashes:r.update(sha256_after=sha256(r["source_path"]))
    for r in hashes:r["unchanged"]=r["sha256_after"]==r["sha256_before"]
    assert all(r["unchanged"] for r in hashes)
    write_csv(OUT/"logs/thermo_sample_hashes_after.csv",hashes)
    mainchecks=pd.read_csv(OUT/"logs/main_samples_before.csv").to_dict("records")
    for r in mainchecks:
        p=MAIN/r["relative_path"];st=p.stat();r["sha256_after"]=sha256(p)
        r["unchanged"]=r["sha256_after"]==r["sha256"] and r["size_bytes"]==st.st_size and r["mtime_ns"]==st.st_mtime_ns
    assert all(r["unchanged"] for r in mainchecks)
    write_csv(OUT/"logs/main_samples_after.csv",mainchecks)
    baseline=json.loads((OUT/"logs/reused_baseline_hashes_before.json").read_text(encoding="utf-8"))
    for r in baseline:r["sha256_after"]=sha256(r["path"]);r["unchanged"]=r["sha256_after"]==r["sha256"]
    assert all(r["unchanged"] for r in baseline)
    write_json(OUT/"logs/reused_baseline_hashes_after.json",baseline)
    env=json.loads((OUT/"logs/environment_before.json").read_text(encoding="utf-8"))
    after={d.metadata["Name"]:d.version for d in importlib.metadata.distributions()}
    changes=[{"package":k,"old_version":env["packages"].get(k),"new_version":after.get(k)} for k in sorted(set(after)|set(env["packages"])) if after.get(k)!=env["packages"].get(k)]
    write_json(OUT/"logs/dependency_change_record.json",{"changes":changes,"install_commands":[],"reason":"Existing netCDF4/numpy/pandas/pyarrow/pytest sufficient"})
    write_json(OUT/"logs/environment_after.json",{"packages":after})
    io=[json.loads(line) for line in (OUT/"logs/staging_io.jsonl").read_text(encoding="utf-8").splitlines()]
    write_csv(OUT/"logs/staging_io.csv",io)
    write_json(OUT/"logs/staging_summary.json",{"copy_count":len(io),"cumulative_copied_bytes":sum(r["bytes"] for r in io),
        "max_single_copy_bytes":max(r["bytes"] for r in io),"copy_seconds":sum(r["copy_seconds"] or 0 for r in io),
        "read_seconds":sum(r["read_seconds"] or 0 for r in io),"cleanup_failures":sum(not r["cleanup_success"] for r in io),
        "remaining_staged_bytes":sum(p.stat().st_size for p in CACHE.glob("*.nc")),
        "main_targeted_copies":sum(Path(r["source_path"]).is_relative_to(MAIN) for r in io),
        "thermo_copies":sum(Path(r["source_path"]).is_relative_to(THERMO) for r in io),
        "scope":"Thermo probes + full metadata audit + 9 allowlisted main samples; no permanent library copy"})
    ti=pd.read_csv(OUT/"THERMO/gfs_thermo_inventory.csv")
    tt=pd.read_csv(OUT/"THERMO/gfs_thermo_time_semantics_audit.csv")
    grid=pd.read_csv(OUT/"THERMO/gfs_thermo_grid_audit.csv")
    structure=pd.read_csv(OUT/"THERMO/gfs_thermo_file_structure_audit.csv")
    summary={"files":len(ti),"total_bytes":int(ti.size_bytes.sum()),"read_success":int(ti.read_success.sum()),
        "formats":ti.file_format.value_counts().to_dict(),"data_models":ti.netcdf_data_model.value_counts().to_dict(),
        "year_counts":ti.year.value_counts().sort_index().to_dict(),"extension_counts":ti.extension.value_counts().to_dict(),
        "zero_byte_files":int(ti.size_bytes.eq(0).sum()),"duplicate_filename_rows":int(ti.filename.duplicated(keep=False).sum()),
        "parse_statuses":ti.parse_status.value_counts().to_dict(),"size_statistics_QC_STAT_ONLY":ti.size_bytes.describe(percentiles=[.5,.95,.99]).to_dict(),
        "grid_count":int(grid.grid_hash.nunique()),"structural_versions":int(structure.structure_id.nunique()),
        "exact_grid_all":bool(grid.exact_coordinate_match.all()),"max_abs_lat_diff":float(grid.max_abs_lat_diff.max()),
        "max_abs_lon_diff":float(grid.max_abs_lon_diff.max()),"time_consistency":tt.time_consistency_status.value_counts().to_dict(),
        "init_hours":sorted(pd.to_datetime(tt.init_time,utc=True).dt.hour.unique().tolist()),
        "leads":sorted(tt.lead_time_hours.unique().tolist()),"thermo_auxiliary_conflicts":int(tt.auxiliary_metadata_conflict.sum()),
        "availability_proxy_present":int(tt.availability_proxy_raw.notna().sum()),"units_unmodified":True,
        "operational_release":"NOT ESTABLISHED FROM CURRENT FILE METADATA",
        "raw_integrity_all_pass":True,"raw_integrity_scope":"size/mtime verification is not full content hash proof."}
    write_json(OUT/"logs/thermo_summary.json",summary)
    month=ti.groupby(["year","month"]).agg(files=("relative_path","size"),bytes=("size_bytes","sum")).reset_index()
    write_csv(OUT/"THERMO/gfs_thermo_month_inventory.csv",month)
    versions=structure.groupby("structure_id").agg(file_count=("relative_path","size"),example_file=("relative_path","first")).reset_index()
    write_csv(OUT/"THERMO/gfs_thermo_structure_versions.csv",versions)
    print(dumps(summary),flush=True)
if __name__=="__main__":run()
