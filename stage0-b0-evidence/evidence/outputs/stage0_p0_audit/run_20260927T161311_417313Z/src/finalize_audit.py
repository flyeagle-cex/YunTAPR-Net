"""Final integrity, independent numerical checks, pytest, and audit summaries."""
from pathlib import Path
from datetime import datetime,timezone
import json,logging,os,subprocess,sys,xml.etree.ElementTree as ET
import numpy as np,pandas as pd
from config import OUTPUT,CACHE,IMERG,HIMAWARI,CONFIG,PYTHON
from common import write_csv,write_json,write_text,sha256
def read(relative):return pd.read_csv(OUTPUT/relative)
def ntrue(frame,key):return int(frame[key].fillna(False).eq(True).sum()) if key in frame else 0
def verify_sources():
    before=read("logs/source_manifest_before.csv");checks=[]
    for r in before.to_dict("records"):
        root=IMERG if r["dataset"]=="IMERG" else HIMAWARI;p=root/r["relative_path"]
        try:
            s=p.stat();checks.append({**r,"exists":True,"size_unchanged":s.st_size==r["size_bytes"],
                                     "mtime_unchanged":s.st_mtime_ns==r["mtime_ns"]})
        except OSError as e:checks.append({**r,"exists":False,"size_unchanged":False,"mtime_unchanged":False,"error":str(e)})
    frame=pd.DataFrame(checks);write_csv(OUTPUT/"logs/source_integrity_after.csv",frame)
    hashrows=[]
    for r in read("logs/source_sample_hashes_before.csv").to_dict("records"):
        actual=sha256(Path(r["source_path"]));hashrows.append({**r,"sha256_after":actual,"unchanged":actual==r["sha256_before"]})
    samples=pd.DataFrame(hashrows);write_csv(OUTPUT/"logs/source_sample_hashes_after.csv",samples)
    return bool(frame["exists"].all() and frame.size_unchanged.all() and frame.mtime_unchanged.all() and samples.unchanged.all())

def main():
    assert Path(sys.executable).resolve()==PYTHON.resolve()
    logging.basicConfig(level=logging.INFO,format="%(asctime)s %(levelname)s %(message)s",
      handlers=[logging.FileHandler(OUTPUT/"logs/audit_run.log",encoding="utf-8"),logging.StreamHandler(sys.stdout)])
    initial=json.loads((OUTPUT/"logs/data_execution_status.json").read_text(encoding="utf-8"))
    assert initial["data_execution_status"]=="COMPLETED_PENDING_FINAL_CHECKS"
    testcmd=[sys.executable,"-B","-m","pytest","tests/test_p0.py","-q","-p","no:cacheprovider",
             "--rootdir",str(OUTPUT),"--confcutdir",str(OUTPUT),"--import-mode","importlib",
             "--basetemp",str(CACHE/"pytest_final"),"--junitxml",str(OUTPUT/"tests/pytest_final.xml")]
    test=subprocess.run(testcmd,cwd=OUTPUT,capture_output=True,text=True,
                        env=dict(os.environ,PYTHONDONTWRITEBYTECODE="1"))
    write_text(OUTPUT/"tests/pytest_final_output.txt",test.stdout+test.stderr)
    suites=list(ET.parse(OUTPUT/"tests/pytest_final.xml").getroot().iter("testsuite"))
    tested=sum(int(s.get("tests","0")) for s in suites)
    failures=sum(int(s.get("failures","0"))+int(s.get("errors","0")) for s in suites)
    integrity=verify_sources()
    inv=read("IMERG/imerg_inventory.csv");years=read("IMERG/imerg_year_inventory.csv")
    meta=read("IMERG/imerg_metadata_audit.csv");times=read("IMERG/imerg_time_audit.csv")
    grids=read("IMERG/imerg_grid_audit.csv");precip=read("IMERG/imerg_precip_qc.csv");qi=read("IMERG/imerg_quality_index_audit.csv")
    missing=read("IMERG/imerg_missing_dates.csv");duplicates=read("IMERG/imerg_duplicate_dates.csv");needs=read("IMERG/imerg_needs_review.csv")
    lat=read("HIMAWARI_202407/himawari_202407_latency.csv")
    stats=read("HIMAWARI_202407/himawari_202407_latency_summary.csv")
    anomalies=read("HIMAWARI_202407/himawari_202407_latency_anomalies.csv")
    checks=[]
    for name,frame in [("metadata",meta),("time",times),("grid",grids),("precipitation",precip),("QI",qi)]:
        checks.append({"check":name+"_every_file_accounted_for",
                       "pass":len(frame)==len(inv) and set(frame.relative_path)==set(inv.relative_path)})
    checks.append({"check":"himawari_every_file_accounted_for","pass":len(lat)==initial["himawari_files"]})
    good=precip[precip.status=="OK"]
    checks.append({"check":"precip_valid_missing_and_zero_accounting",
                   "pass":bool(np.allclose(good.precip_valid_fraction+good.precip_nan_fraction,1) and
                               (good.zero_valid_pixel_count<=good.valid_pixel_count).all())})
    parsed=lat[lat.parse_status=="OK"];p99=float(parsed.creation_delay_seconds.quantile(.99))
    checks.append({"check":"inclusive_p99_tail_label","pass":bool((lat.latency_tail_review==lat.creation_delay_seconds.ge(p99)).all())})
    computable=lat.obs_end.notna() & lat.nominal_time.notna()
    expected=pd.to_datetime(lat.loc[computable,"obs_end"],utc=True)<=pd.to_datetime(lat.loc[computable,"nominal_time"],utc=True)+pd.Timedelta(minutes=10)
    checks.append({"check":"causality_independent_recalculation",
                   "pass":bool((lat.loc[computable,"causal_as_latest"].to_numpy()==expected.to_numpy()).all())})
    bounds=[]
    with (OUTPUT/"IMERG/imerg_original_metadata.jsonl").open(encoding="utf-8") as f:
        for line in f:
            r=json.loads(line);variables=r["variables"]
            candidates=[k for k in variables if "bnd" in k.lower() or "bound" in k.lower()]
            attribute=variables.get("time",{}).get("attrs",{}).get("bounds")
            if candidates or attribute:bounds.append({"relative_path":r["relative_path"],"variables":str(candidates),"time_bounds_attr":attribute})
    write_csv(OUTPUT/"IMERG/imerg_time_bounds_metadata_presence.csv",bounds,["relative_path","variables","time_bounds_attr"])
    checks.append({"check":"no_unreported_native_time_bounds","pass":len(bounds)==0})
    checkframe=pd.DataFrame(checks);write_csv(OUTPUT/"logs/output_validation.csv",checkframe)
    io=pd.DataFrame([json.loads(l) for l in (OUTPUT/"logs/staging_io.jsonl").read_text(encoding="utf-8").splitlines()])
    write_csv(OUTPUT/"logs/staging_io.csv",io)
    ios={"copy_count":len(io),"cumulative_copied_bytes":int(io.bytes.sum()),"max_single_copy_bytes":int(io.bytes.max()),
         "copy_seconds":float(io.copy_seconds.sum()),"read_and_analysis_seconds":float(io.read_seconds.sum()),
         "cleanup_failures":int((~io.cleanup_success).sum()),"remaining_staged_nc_bytes":sum(p.stat().st_size for p in CACHE.glob("*.nc"))}
    write_json(OUTPUT/"logs/staging_summary.json",ios)
    counts=anomalies.anomaly_type.value_counts().to_dict() if len(anomalies) else {}
    true=ntrue(lat,"causal_as_latest");false=int(lat.causal_as_latest.eq(False).sum());unknown=int(lat.causal_as_latest.isna().sum())
    write_csv(OUTPUT/"HIMAWARI_202407/causal_as_latest_false_examples.csv",lat[lat.causal_as_latest.eq(False)])
    ok=test.returncode==0 and failures==0 and integrity and bool(checkframe["pass"].all())
    overall="BLOCKED" if not ok else ("NEEDS_REVIEW" if len(needs) or len(anomalies) else "PASS")
    summary={"status":overall,"engineering_execution":"PASS" if ok else "BLOCKED",
      "imerg_files":len(inv),"imerg_open_success":ntrue(meta,"open_success"),"imerg_open_failed":int(meta.status.eq("READ_ERROR").sum()),
      "years":{int(r["year"]):int(r["file_count"]) for r in years.to_dict("records")},
      "imerg_first_date":inv.date.min(),"imerg_last_date":inv.date.max(),
      "imerg_missing_dates_within_observed_span":len(missing),"imerg_duplicate_date_files":len(duplicates),
      "imerg_expected_title_files":ntrue(meta,"expected_title_match"),"imerg_expected_source_files":ntrue(meta,"expected_source_match"),
      "imerg_48_frames_files":ntrue(times,"count_is_48"),"imerg_exact_daily_slots_files":ntrue(times,"exact_daily_slots"),
      "imerg_strict_30min_files":ntrue(times,"strict_30min_intervals"),
      "imerg_unique_grid_count":int(grids.grid_hash.nunique()),"imerg_unique_lat_hash_count":int(grids.lat_hash.nunique()),
      "imerg_unique_lon_hash_count":int(grids.lon_hash.nunique()),
      "imerg_unique_precipitation_shapes":sorted(grids.precipitation_shape.dropna().unique().tolist()),
      "imerg_units":sorted(meta.precipitation_units.dropna().unique().tolist()),
      "imerg_invalid_precip_pixel_count":int(precip.invalid_pixel_count.fillna(0).sum()),
      "imerg_invalid_QI_pixel_count":int(qi.invalid_pixel_count.fillna(0).sum()),
      "imerg_precip_min":float(precip.precip_min.min()),"imerg_precip_max":float(precip.precip_max.max()),
      "imerg_negative_precip_count":int(precip.negative_valid_pixel_count.sum()),
      "imerg_needs_review_file_count":len(needs),"himawari_files":len(lat),"himawari_parsed":int(lat.parse_status.eq("OK").sum()),
      "himawari_anomaly_counts":counts,"creation_delay_quantiles_seconds":{k:float(parsed.creation_delay_seconds.quantile(q)) for k,q in [("p50",.5),("p95",.95),("p99",.99)]},
      "creation_delay_max_seconds":float(parsed.creation_delay_seconds.max()),"latency_tail_review_files":ntrue(lat,"latency_tail_review"),
      "p99_rule":CONFIG["latency_tail_definition"],"causal_as_latest_true":true,"causal_as_latest_false":false,
      "causal_as_latest_unknown":unknown,"causal_as_latest_pass_fraction":true/(true+false),
      "pytest_test_count":tested,"pytest_failures":failures,"source_integrity_pass":integrity,"raw_F_H_modified":False,
      "availability_time_conclusion":"Not established from current metadata alone.",
      "formal_research_years_changed":False,"normalization_or_training_executed":False,
      "staging":ios,"timing":initial,"ended_utc":datetime.now(timezone.utc).isoformat()}
    from write_reports import write_reports
    write_reports(summary,inv,years,meta,times,grids,precip,qi,lat,stats,anomalies,len(bounds))
    hashes=[{"path":str(p.relative_to(OUTPUT)),"sha256":sha256(p)} for folder in ["src","tests"] for p in sorted((OUTPUT/folder).glob("*.py"))]
    write_csv(OUTPUT/"logs/code_sha256.csv",hashes)
    write_json(OUTPUT/"audit_final_status.json",summary)
    files=[{"relative_path":str(p.relative_to(OUTPUT)),"size_bytes":p.stat().st_size} for p in sorted(OUTPUT.rglob("*")) if p.is_file()]
    write_csv(OUTPUT/"output_manifest.csv",files)
    logging.info("FINAL_STATUS %s",summary)
    print(json.dumps(summary,ensure_ascii=False,indent=2,default=str))
    if not ok:raise SystemExit(2)
if __name__=="__main__":main()
