"""Validate added A-P deliverables and produce the exact administrative manifest schema."""
from pathlib import Path
from datetime import datetime,timezone
import json,hashlib
import pandas as pd
from config import *
from common import *
def main():
    checks=[]
    def check(name,condition):
        checks.append({"check":name,"passed":bool(condition)})
        if not condition:raise AssertionError(name)
    for rel in ["GFS/gfs_inventory_summary.md","tests/pytest_final_output.txt","tests/pytest_final.xml",
                "audit_final_status.json","logs/gfs_source_manifest_before.csv",
                "GFS/gfs_distinct_time_evidence.csv","GFS/gfs_time_metadata_field_inventory.csv"]:
        check("exists:"+rel,(OUT/rel).is_file())
    inv=pd.read_csv(OUT/"GFS/gfs_inventory.csv");grid=pd.read_csv(OUT/"GFS/gfs_grid_audit.csv")
    check("inventory_required_fields",{"relative_path","filename","size_bytes","extension","year","month","date","parse_status","init_time","valid_time","lead_time"}<=set(inv.columns))
    check("grid_required_fields",{"file","grid_id","lat_shape","lon_shape","field_shape","lat_min","lat_max","lon_min","lon_max","lat_direction","lon_direction","mean_dlat","mean_dlon","lat_hash","lon_hash","grid_status","lat_dtype","lon_dtype"}<=set(grid.columns))
    mapping=pd.read_csv(OUT/"GFS/gfs_variable_mapping.csv")
    check("variable_required_fields",{"raw_variable_name","shortName","standard_name","long_name","typeOfLevel","level","units","shape","file_count","availability_fraction"}<=set(mapping.columns))
    before=pd.read_csv(OUT/"logs/gfs_source_manifest_before.csv");after=pd.read_csv(OUT/"logs/gfs_source_integrity_after.csv")
    check("full_before_after_manifest",len(before)==len(inv)==len(after) and set(before.relative_path)==set(after.relative_path) and after.unchanged.all())
    check("before_manifest_precedes_audit_outputs",(OUT/"logs/gfs_source_manifest_before.csv").stat().st_mtime_ns<(OUT/"GFS/gfs_inventory.csv").stat().st_mtime_ns)
    baseline=json.loads((OUT/"logs/baseline_reference_hashes_after.json").read_text(encoding="utf-8"))
    check("old_baseline_reference_hashes_unchanged",all(r["unchanged"] and sha256(r["path"])==r["sha256"] for r in baseline))
    timing=pd.read_csv(OUT/"GFS/gfs_global_lead_metadata_crosscheck.csv")
    check("explicit_global_lead_no_conflict",not timing.consistency.eq("FAIL").any())
    check("boundary_matches_prior",pd.read_csv(OUT/"IMERG/boundary_prior_result_comparison.csv").comparison.eq("EXACT_FRAME_EQUAL").all())
    state=json.loads((OUT/"audit_final_status.json").read_text(encoding="utf-8"))
    check("engineering_vs_review",state["engineering_status"]=="PASS" and state["researcher_review_status"]=="NEEDS_REVIEW")
    check("no_scientific_closeout_claim",state["stage0_closeout_ready"] is False and state["stage0_engineering_closeout_ready"] is True)
    check("scoped_tests_passed",state["tests"]["tests"]==33 and state["tests"]["failures"]==0 and state["tests"]["errors"]==0)
    check("final_test_log_recorded","33 passed" in (OUT/"tests/pytest_final_output.txt").read_text(encoding="utf-8"))
    check("initial_failure_preserved",(OUT/"tests/pytest_initial.xml").is_file() and 'errors="6"' in (OUT/"tests/pytest_initial.xml").read_text(encoding="utf-8"))
    check("no_prediction_inputs",state["NO_GFS_PRECIPITATION_USED_AS_MODEL_INPUT"] is True and state["formal_sample_pairing_executed"] is False)
    cache=json.loads((OUT/"logs/staging_summary.json").read_text(encoding="utf-8"))
    check("cache_required_fields",{"copy_count","cumulative_copied_bytes","max_single_copy_bytes","copy_seconds","cleanup_failures","remaining_staged_bytes"}<=set(cache))
    check("no_production_staging_left",cache["remaining_staged_bytes"]==0 and not list(CACHE.glob("*.nc")))
    # Improve table rendering only in this new run, before final hashes are captured.
    for p in OUT.rglob("*.md"):
        lines=p.read_text(encoding="utf-8").splitlines();result=[]
        for line in lines:
            if line.startswith("| ") and result and result[-1] and not result[-1].startswith("| "):result.append("")
            if not line.startswith("| ") and line and result and result[-1].startswith("| "):result.append("")
            result.append(line)
        p.write_text("\n".join(result)+"\n",encoding="utf-8")
    end=["Stage-0 continuous engineering run complete.","Waiting for researcher scientific review.","No frozen scientific convention was changed automatically."]
    check("final_exact_ending",(OUT/"FINAL_CONTINUOUS_ENGINEERING_REPORT.md").read_text(encoding="utf-8").strip().splitlines()[-3:]==end)
    done={"status":"PASS","checks":checks,"count":len(checks),"checked_utc":datetime.now(timezone.utc).isoformat()}
    write_json(OUT/"logs/current_requirements_validation.json",done)
    append_json(OUT/"logs/audit_run.log",{"phase":"current_requirements_validation","status":"PASS","checks":len(checks)})
    manifest=[]
    descriptions={"src":"Reproducible audit source code","tests":"Scoped automated test evidence","logs":"Execution, integrity and environment evidence",
                  "GFS":"Main-root GFS audit","IMERG":"Two-file boundary sanity check","CROSS_SOURCE":"Coverage and static evidence","schemas":"Schema only; no samples","docs":"Decision log"}
    for p in sorted(OUT.rglob("*")):
        if not p.is_file() or p==OUT/"output_manifest.csv":continue
        rel=p.relative_to(OUT)
        manifest.append({"relative_path":str(rel),"file_type":p.suffix.lstrip(".") or "text",
                        "description":descriptions.get(rel.parts[0],"Final report or run status"),
                        "size_bytes":p.stat().st_size,"sha256_if_reasonable":sha256(p)})
    path=OUT/"output_manifest.csv"
    pd.DataFrame(manifest).to_csv(path,index=False,encoding="utf-8-sig")
    back=pd.read_csv(path)
    check("manifest_schema",list(back.columns)==["relative_path","file_type","description","size_bytes","sha256_if_reasonable"])
    check("manifest_count",len(back)==len(manifest))
    print(dumps({"status":"PASS","additional_checks":len(checks),"manifest_artifacts":len(manifest),
                 "output_dir":str(OUT),"engineering_status":state["engineering_status"],"researcher_review_status":state["researcher_review_status"]}),flush=True)
if __name__=="__main__":main()
