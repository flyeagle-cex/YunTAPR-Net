"""Additional inventory, temporal evidence and closeout fields requested by this run."""
from pathlib import Path
from datetime import datetime,timezone
import json
import pandas as pd
from config import *
from common import *

PREVIOUS=PROJECT/"outputs/stage0_continuous_engineering/run_20260928T031444_178129Z"
def md(df):
    def value(v):return str(v).replace("|","/").replace("\n"," ") if pd.notna(v) else "UNKNOWN"
    return "| "+" | ".join(df.columns)+" |\n| "+" | ".join(["---"]*len(df.columns))+" |\n"+"\n".join("| "+" | ".join(value(v) for v in r)+" |" for r in df.itertuples(index=False,name=None))
def additions():
    inventory=pd.read_csv(OUT/"GFS/gfs_inventory.csv")
    for col in ["month","init_time","valid_time","lead_time"]:assert col in inventory
    duplicates=inventory[inventory.filename.duplicated(keep=False)]
    zero=inventory[inventory.size_bytes.eq(0)]
    largest=inventory.sort_values(["size_bytes","relative_path"],ascending=[False,True]).head(20).copy()
    largest["review_semantics"]="QC_STAT_ONLY_SIZE_RANK_NOT_ANOMALY_OR_EXCLUSION"
    write_csv(OUT/"GFS/gfs_duplicate_filenames.csv",duplicates)
    write_csv(OUT/"GFS/gfs_zero_byte_files.csv",zero)
    write_csv(OUT/"GFS/gfs_largest_files_qc_stat_only.csv",largest)
    annual=inventory.groupby("year").agg(file_count=("relative_path","size"),size_bytes=("size_bytes","sum")).reset_index()
    monthly=inventory.groupby(["year","month"]).agg(file_count=("relative_path","size"),size_bytes=("size_bytes","sum")).reset_index()
    write_csv(OUT/"GFS/gfs_inventory_by_year.csv",annual);write_csv(OUT/"GFS/gfs_inventory_by_month.csv",monthly)
    quantiles=inventory.size_bytes.quantile([0,.25,.5,.75,.95,.99,1])
    summary={"file_count":len(inventory),"total_logical_bytes":int(inventory.size_bytes.sum()),
        "extensions":inventory.extension.value_counts().to_dict(),"parse_status_counts":inventory.parse_status.fillna("UNKNOWN").value_counts().to_dict(),
        "duplicate_filename_rows":len(duplicates),"zero_byte_files":len(zero),"size_distribution_quantiles_bytes":quantiles.to_dict(),
        "large_file_semantics":"QC_STAT_ONLY; show size distribution and largest 20, no anomaly threshold chosen",
        "scientific_size_threshold":None,"read_success":int(inventory.read_success.sum())}
    write_json(OUT/"GFS/gfs_inventory_summary.json",summary)
    report=f"""# GFS inventory summary

Statistics scope: QC_STAT_ONLY. 文件大小排名不是错误或排除标签，未设异常大文件阈值，未删除任何文件。

文件总数：{len(inventory):,}。总逻辑大小：{int(inventory.size_bytes.sum()):,} bytes。
扩展名：{summary["extensions"]}。parse status：{summary["parse_status_counts"]}。
成功打开：{summary["read_success"]:,}；零字节文件：{len(zero)}；重复文件名涉及行数：{len(duplicates)}。
异常大文件：没有科研/剔除阈值；完整分布与 top20 大小文件清单已输出，仅供查看，不声称它们异常。

## 年份分布

{md(annual)}

## 大小分布

{md(pd.DataFrame({"quantile":quantiles.index,"size_bytes":quantiles.values}))}

## 月份分布

{md(monthly)}

时间来源是当前文件名、CF 坐标与 global cycle/lead 的一致证据；字段见 inventory 和 gfs_time_semantics_audit.csv。
未知时间应保持 null+UNKNOWN 状态，不使用 fake epoch、mtime 或 init 代替 release。
辅助 udunits/history 冲突仍单独保留，不因 parse_status=OK 抹去来源风险。
"""
    write_text(OUT/"GFS/gfs_inventory_summary.md",report)

    patterns={}
    for line in (OUT/"GFS/global_metadata_patterns.jsonl").open(encoding="utf-8"):
        r=json.loads(line);patterns[r["metadata_id"]]=r["global_attrs"]
    keycounts={};leadchecks=[]
    timing_by_path=pd.read_csv(OUT/"GFS/gfs_time_semantics_audit.csv").set_index("relative_path")
    for r in inventory.to_dict("records"):
        attrs=patterns.get(r.get("metadata_id"),{})
        for key in attrs:
            if any(term in key.lower() for term in ["time","creat","generat","release","publish","download","analysis","reference","avail","source","history"]):
                keycounts[key]=keycounts.get(key,0)+1
        raw=attrs.get("lead_time_hours")
        actual=timing_by_path.loc[r["relative_path"],"lead_time_hours"]
        match=float(raw)==float(actual) if raw is not None and pd.notna(actual) else None
        leadchecks.append({"relative_path":r["relative_path"],"global_lead_time_hours":raw,
                          "reconstructed_lead_time_hours":actual,"consistency":"PASS" if match else "FAIL" if match is False else "UNKNOWN_NOT_PRESENT"})
    write_csv(OUT/"GFS/gfs_global_lead_metadata_crosscheck.csv",leadchecks)
    rows=[]
    for key,count in sorted(keycounts.items()):
        kind="RAW_METADATA_TEXT"
        if any(term in key.lower() for term in ["center","subcenter","identifier","type_of"]):kind="PROCESS_ID_OR_CENTER_NOT_TIMESTAMP"
        elif key=="conservative_available_time_utc":kind="ASSUMPTION_NOT_OBSERVED_RELEASE"
        elif key=="conversion_time":kind="CONVERSION_TIMESTAMP_NOT_RELEASE"
        elif "history" in key.lower():kind="HISTORICAL_PROVENANCE_NOT_RELEASE"
        rows.append({"metadata_key":key,"file_count":count,"interpretation":kind})
    write_csv(OUT/"GFS/gfs_time_metadata_field_inventory.csv",rows)
    if any(r["consistency"]=="FAIL" for r in leadchecks):
        raise RuntimeError("New global lead conflict requires time summary reconciliation")

    # Structured evidence for the distinct time concepts; do not parse conversion history as availability.
    times=pd.read_csv(OUT/"GFS/gfs_time_semantics_audit.csv")
    evidence=[]
    for r in times.to_dict("records"):
        raw=json.loads(r["raw_time_metadata"]);ga=json.loads(r["creation_generation_archive_metadata"])
        ref={k:v for k,v in raw.items() if k in {"reftime","forecast_reference_time"} or v.get("attrs",{}).get("standard_name")=="forecast_reference_time"}
        creation={k:v for k,v in ga.items() if any(t in k.lower() for t in ["creat","generat","conversion"])}
        download={k:v for k,v in ga.items() if "download" in k.lower()}
        archive={k:v for k,v in ga.items() if any(t in k.lower() for t in ["archive","source","history"])}
        evidence.append({"relative_path":r["relative_path"],"init_time":r["init_time"],"valid_time":r["valid_time"],
            "lead_time_hours":r["lead_time_hours"],"reference_time_metadata":dumps(ref) if ref else "UNKNOWN",
            "creation_generation_conversion_metadata":dumps(creation) if creation else "UNKNOWN",
            "download_time_metadata":dumps(download) if download else "UNKNOWN",
            "source_archive_metadata":dumps(archive) if archive else "UNKNOWN",
            "file_modification_mtime_ns":r["file_mtime_ns"],
            "release_time":"UNKNOWN","operational_availability":"NOT ESTABLISHED FROM CURRENT FILE METADATA",
            "note":"Metadata text evidence only; no creation/conversion/download/mtime substitution for release"})
    write_csv(OUT/"GFS/gfs_distinct_time_evidence.csv",evidence)
    baseline=json.loads((OUT/"logs/baseline_reference_hashes_before.json").read_text(encoding="utf-8"))
    for row in baseline:
        row["sha256_after"]=sha256(row["path"]);row["unchanged"]=row["sha256"]==row["sha256_after"]
    assert all(r["unchanged"] for r in baseline)
    write_json(OUT/"logs/baseline_reference_hashes_after.json",baseline)
    # Verify the newly reread boundary against prior evidence, without rescanning prior raw files.
    checks=[]
    for name in ["imerg_boundary_values.csv","imerg_boundary_patch_5x5.csv"]:
        current=pd.read_csv(OUT/"IMERG"/name);old=pd.read_csv(PREVIOUS/"IMERG"/name)
        pd.testing.assert_frame_equal(current,old)
        checks.append({"table":name,"comparison":"EXACT_FRAME_EQUAL","prior_evidence":str(PREVIOUS/"IMERG"/name)})
    write_csv(OUT/"IMERG/boundary_prior_result_comparison.csv",checks)
    cache=json.loads((OUT/"logs/staging_summary.json").read_text(encoding="utf-8"))
    cache.update(copy_count=cache["files"],cumulative_copied_bytes=cache["temporary_bytes_sum"],
        max_single_copy_bytes=cache["single_file_max_bytes"],copy_seconds=cache["copy_seconds_sum"],
        remaining_staged_bytes=sum(p.stat().st_size for p in CACHE.glob("*.nc")))
    (OUT/"logs/staging_summary.json").write_text(dumps(cache),encoding="utf-8")
    dep=json.loads((OUT/"logs/dependency_change_record.json").read_text(encoding="utf-8"))
    dep.update(timestamp=datetime.now(timezone.utc).isoformat(),install_command=None,
        change_record_fields=["package","old_version","new_version","reason","install_command","timestamp"])
    (OUT/"logs/dependency_change_record.json").write_text(dumps(dep),encoding="utf-8")
    print(dumps(summary),flush=True)
if __name__=="__main__":additions()
