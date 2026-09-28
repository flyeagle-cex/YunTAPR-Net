"""Validate real deliverables and preserve error/recovery history before final hashes."""
import ast,json
from pathlib import Path
from datetime import datetime,timezone
import pandas as pd
from config import *
from common import *
from table_schema import read_audit_csv

def main():
    rows=[]
    def check(name,condition,detail=""):
        rows.append({"check":name,"status":"PASS" if condition else "FAIL","detail":detail})
        if not condition:raise AssertionError(name+": "+detail)
    required=[
        "THERMO/gfs_thermo_inventory.csv","THERMO/gfs_thermo_inventory_summary.md",
        "THERMO/gfs_thermo_file_structure_audit.csv","THERMO/gfs_thermo_grid_audit.csv",
        "THERMO/gfs_thermo_variable_mapping.csv","THERMO/gfs_thermo_variable_coverage.csv",
        "THERMO/gfs_thermo_time_semantics_audit.csv","COMPATIBILITY/grid_compatibility.csv",
        "COMPATIBILITY/main_thermo_pairing.csv","COMPATIBILITY/research_period_thermo_coverage.csv",
        "COMPATIBILITY/pairing_conflicts.csv","COMPATIBILITY/source_lineage_comparison.md",
        "COMPATIBILITY/source_lineage_fields.csv","TIME_LINEAGE/auxiliary_time_conflict_classification.csv",
        "TIME_LINEAGE/AUXILIARY_TIME_CONFLICT_REPORT.md","COMPATIBILITY/GFS_THERMO_COMPATIBILITY_ASSESSMENT.md",
        "schemas/gfs_main_thermo_pair_schema.md","tests/pytest_final_output.txt","tests/pytest_final.xml",
        "FINAL_GFS_THERMO_COMPATIBILITY_REPORT.md","RESEARCHER_DECISIONS_REQUIRED.md","audit_final_status.json","README.md"]
    for rel in required:check("exists:"+rel,(OUT/rel).is_file() and (OUT/rel).stat().st_size>0)
    inv=pd.read_csv(OUT/"THERMO/gfs_thermo_inventory.csv")
    check("thermo_full_inventory",len(inv)==12960 and inv.read_success.all() and inv.relative_path.is_unique)
    fields={"relative_path","filename","size_bytes","extension","year","month","date","parse_status","init_time","valid_time","lead_time"}
    check("inventory_required_schema",fields<=set(inv.columns))
    for name in ["file_structure_audit","grid_audit","time_semantics_audit","variable_presence"]:
        df=pd.read_csv(OUT/f"THERMO/gfs_thermo_{name}.csv")
        check("one_row_per_thermo:"+name,len(df)==len(inv) and df.relative_path.is_unique and set(df.relative_path)==set(inv.relative_path))
    structure=pd.read_csv(OUT/"THERMO/gfs_thermo_file_structure_audit.csv")
    check("unique_structure",structure.structure_id.nunique()==1)
    grid=pd.read_csv(OUT/"COMPATIBILITY/grid_compatibility.csv")
    check("all_exact_coordinates",grid.exact_coordinate_match.all() and grid.lat_hash_match.all() and grid.lon_hash_match.all())
    check("zero_coordinate_differences",grid.max_abs_lat_diff.eq(0).all() and grid.max_abs_lon_diff.eq(0).all())
    cover=pd.read_csv(OUT/"COMPATIBILITY/research_period_thermo_coverage.csv")
    check("24_research_months",len(cover)==24 and cover.month.is_unique)
    check("8820_complete_pairs",cover.complete_T_RH_pairs.sum()==8820 and cover.expected_main_forecast_pairs.sum()==8820)
    check("all_research_months_READY",cover.status.eq("READY").all() and cover.coverage_fraction.eq(1).all())
    pair=read_audit_csv(OUT/"COMPATIBILITY/main_thermo_pairing.csv")
    check("thermo_one_to_one",pair.pair_status.eq("MATCHED_COMPLETE").sum()==12960 and pair.thermo_count.max()==1 and pair.main_count.max()==1)
    check("forecast_key_unique",not pair.duplicated(["init_time","lead_time"]).any())
    check("main_only_null_preserved",pair.loc[pair.pair_status.eq("MAIN_ONLY"),"thermo_auxiliary_metadata_conflict"].isna().all())
    check("all_thermo_key_checks",pair.loc[pair.thermo_present,"valid_time_match"].all() and pair.loc[pair.thermo_present,"grid_match"].all())
    check("no_true_pair_conflicts",set(pair.pair_status)=={"MATCHED_COMPLETE","MAIN_ONLY"})
    lineage=pd.read_csv(OUT/"COMPATIBILITY/source_lineage_fields.csv")
    check("lineage_caveats_retained",len(lineage)==12960 and lineage.lineage_status.eq("SUPPORTED_WITH_CAVEATS").all())
    classes=pd.read_csv(OUT/"TIME_LINEAGE/auxiliary_time_conflict_classification.csv")
    check("old_auxiliary_counts_retained",len(classes)==24388 and classes.original_auxiliary_conflict.sum()==17665 and classes.classification.str.contains("STALE_HISTORY_TOKEN").sum()==3628)
    check("targeted_main_samples_only",classes.raw_sample_verified_this_run.sum()==9)
    check("thermo_before_after_stat",pd.read_csv(OUT/"logs/thermo_integrity_after.csv").unchanged.all())
    check("thermo_sample_hashes",pd.read_csv(OUT/"logs/thermo_sample_hashes_after.csv").unchanged.all())
    check("main_sample_hashes",pd.read_csv(OUT/"logs/main_samples_after.csv").unchanged.all())
    baseline=json.loads((OUT/"logs/reused_baseline_hashes_after.json").read_text(encoding="utf-8"))
    check("old_runs_unchanged",all(r["unchanged"] and sha256(r["path"])==r["sha256"] for r in baseline))
    cache=json.loads((OUT/"logs/staging_summary.json").read_text(encoding="utf-8"))
    check("owned_staging_clean",cache["remaining_staged_bytes"]==0 and not list(CACHE.glob("*.nc")))
    check("no_dependencies_changed",json.loads((OUT/"logs/dependency_change_record.json").read_text(encoding="utf-8"))["changes"]==[])
    state=json.loads((OUT/"audit_final_status.json").read_text(encoding="utf-8"))
    check("final_tests_real",state["tests"]["tests"]==33 and not any(state["tests"][k] for k in ["failures","errors","skipped"])
          and "33 passed" in (OUT/"tests/pytest_final_output.txt").read_text(encoding="utf-8"))
    check("no_approval_or_merge",state["researcher_approval_required_before_merge"] and not state["main_thermo_merge_performed"] and not state["official_predictor_readiness_changed"])
    check("partial_verdict_not_overstated",state["compatibility_verdict"]=="PARTIALLY_COMPATIBLE" and state["source_lineage_status"]=="SUPPORTED_WITH_CAVEATS")
    check("no_operational_release_fabricated",not state["operational_release_established"])
    for p in OUT.rglob("*.py"):ast.parse(p.read_text(encoding="utf-8"),filename=str(p))
    check("source_syntax_valid",True)
    # Record the real initial serializer failure and recovery in the final narrative.
    note="\nCSV/Parquet工程恢复：首次回读有1张配对表因NaN/None可空布尔表示差异而失败；已明确BooleanDtype并通过新增回归测试。缺失未填False，原失败summary/Parquet和前次测试XML保留；最终恢复见logs/parquet_final_summary.json。未新增依赖。\n"
    p=OUT/"FINAL_GFS_THERMO_COMPATIBILITY_REPORT.md";text=p.read_text(encoding="utf-8")
    ending="GFS_thermo compatibility engineering audit complete.\nNo GFS main/thermo merge was performed.\nResearcher approval is required before any dataset integration.\nNo frozen scientific convention was changed automatically.\n"
    check("final_four_lines_before",text.endswith(ending))
    p.write_text(text[:-len(ending)]+note+"\n"+ending,encoding="utf-8")
    with (OUT/"README.md").open("a",encoding="utf-8") as f:
        f.write("\nCSV/Parquet reader schema见src/table_schema.py。初次1张表的回读错误与恢复记录均保留；最终33测试包含可空布尔用例。recover_finalize.py只用于本次已保留失败结果后的恢复，不是普通新run必须重复执行的步骤。\n")
    for p in OUT.rglob("*.md"):
        lines=p.read_text(encoding="utf-8").splitlines();fixed=[]
        for line in lines:
            if line.startswith("| ") and fixed and fixed[-1] and not fixed[-1].startswith("| "):fixed.append("")
            if not line.startswith("| ") and line and fixed and fixed[-1].startswith("| "):fixed.append("")
            fixed.append(line)
        p.write_text("\n".join(fixed)+"\n",encoding="utf-8")
    for csv in sorted(OUT.rglob("*.csv")):
        if csv.name=="output_manifest.csv":continue
        df=read_audit_csv(csv);parquet=csv.with_suffix(".parquet")
        if not parquet.exists():df.to_parquet(parquet,engine="pyarrow",index=False,compression="snappy")
        pd.testing.assert_frame_equal(df,pd.read_parquet(parquet,engine="pyarrow"))
    check("all_final_audit_tables_roundtrip",True)
    write_csv(OUT/"logs/delivery_validation.csv",rows)
    pd.read_csv(OUT/"logs/delivery_validation.csv").to_parquet(OUT/"logs/delivery_validation.parquet",engine="pyarrow",index=False)
    source=[{"path":str(p.relative_to(OUT)),"sha256":sha256(p)} for p in sorted(OUT.rglob("*.py"))]
    write_csv(OUT/"logs/code_sha256.csv",source)
    pd.read_csv(OUT/"logs/code_sha256.csv").to_parquet(OUT/"logs/code_sha256.parquet",engine="pyarrow",index=False)
    write_json(OUT/"logs/delivery_validation.json",{"status":"PASS","checks":len(rows),"utc":datetime.now(timezone.utc).isoformat(),
        "initial_serialization_failure_preserved":True,"unresolved_engineering_failures":0})
    append_json(OUT/"logs/audit_run.log",{"phase":"complete","checks":len(rows),"engineering_status":"PASS","compatibility_verdict":"PARTIALLY_COMPATIBLE"})
    manifest=[{"relative_path":str(p.relative_to(OUT)),"file_type":p.suffix.lstrip("."),"description":"Thermo compatibility audit evidence",
               "size_bytes":p.stat().st_size,"sha256_if_reasonable":sha256(p)} for p in sorted(OUT.rglob("*")) if p.is_file()]
    write_csv(OUT/"output_manifest.csv",manifest)
    print(dumps({"status":"PASS","checks":len(rows),"manifest_artifacts":len(manifest),"output":str(OUT)}),flush=True)
if __name__=="__main__":main()
