"""Monthly metadata latency and physical observation causality only."""
from pathlib import Path
from datetime import timedelta
import logging,json,time
import numpy as np,pandas as pd
from config import HIMAWARI,OUTPUT,CONFIG
from common import attrs,dumps,decode_cf_time,parse_iso_utc,utc_iso,write_csv,append_json
from time_rules import himawari_filename,latencies

def time_value(ds,name):
    if name not in ds.variables:raise KeyError(name)
    v=ds[name];raw=v[:]
    record={"raw":dumps(raw),"units":str(getattr(v,"units","")),"calendar":str(getattr(v,"calendar","standard"))}
    if np.asarray(raw).size!=1:raise ValueError(f"{name} contains multiple values")
    decoded=decode_cf_time(raw,record["units"],record["calendar"])[0]
    return record,decoded

def logical_anomalies(row,p99):
    found=[]
    for field,detail in (("start_before_nominal","obs_start < nominal_time"),
                         ("end_before_start","obs_end < obs_start"),
                         ("created_before_end","date_created < obs_end")):
        if row.get(field) is True:found.append(("TEMPORAL_ORDER_ERROR",detail))
    delay=row.get("creation_delay_seconds")
    if p99 is not None and delay is not None and np.isfinite(delay) and delay>=p99:
        found.append(("LATENCY_TAIL_REVIEW","creation_delay_seconds >= monthly parsed-sample p99"))
    if row.get("causal_as_latest") is False:
        found.append(("OBSERVATION_CAUSALITY_FAILURE","obs_end > nominal_time + 10min"))
    return found

def run_himawari(paths,staging):
    rows=[];errors=[]
    for index,p in enumerate(paths):
        started=time.perf_counter()
        row={"relative_path":str(p.relative_to(HIMAWARI)),"filename":p.name,
             "nominal_time":None,"obs_start":None,"obs_end":None,"date_created":None,
             "satellite":None,"grid_tag":None,"parse_status":"OK","notes":"",
             "start_offset_seconds":None,"scan_duration_seconds":None,"creation_delay_seconds":None,
             "nominal_to_created_seconds":None,"causal_as_latest":None,"analysis_time":None,
             "start_before_nominal":None,"end_before_start":None,"created_before_end":None,
             "date_created_raw":None,"start_time_raw":None,"end_time_raw":None}
        notes=[];nominal=start=end=created=None
        try:
            parsed=himawari_filename(p.name);nominal=parsed["nominal"]
            row.update(nominal_time=utc_iso(nominal),satellite=parsed["satellite"],grid_tag=parsed["grid_tag"])
        except Exception as e:
            notes.append(str(e));errors.append({"relative_path":row["relative_path"],"anomaly_type":"PARSE_ERROR","details":str(e)})
        try:
            with staging.open(p,verify_hash=index in {0,len(paths)//4,len(paths)//2,3*len(paths)//4,len(paths)-1}) as ds:
                for name in ("start_time","end_time"):
                    try:
                        if name in ds.variables:
                            var=ds[name];row[name+"_raw"]=dumps(var[:]);row[name+"_units"]=str(getattr(var,"units",""))
                            row[name+"_calendar"]=str(getattr(var,"calendar","standard"))
                        record,value=time_value(ds,name)
                        if name=="start_time":start=value;row["obs_start"]=utc_iso(value)
                        else:end=value;row["obs_end"]=utc_iso(value)
                    except Exception as e:
                        kind="MISSING_TIME_METADATA" if isinstance(e,KeyError) else "PARSE_ERROR"
                        notes.append(f"{name}: {e}");errors.append({"relative_path":row["relative_path"],"anomaly_type":kind,"details":f"{name}: {e}"})
                row["date_created_raw"]=str(ds.getncattr("date_created")) if "date_created" in ds.ncattrs() else None
                try:
                    if row["date_created_raw"] is None:raise KeyError("date_created")
                    created=parse_iso_utc(row["date_created_raw"]);row["date_created"]=utc_iso(created)
                except Exception as e:
                    notes.append(f"date_created: {e}")
                    errors.append({"relative_path":row["relative_path"],"anomaly_type":"MISSING_TIME_METADATA" if isinstance(e,KeyError) else "PARSE_ERROR","details":f"date_created: {e}"})
        except Exception as e:
            notes.append(f"File read: {e}")
            errors.append({"relative_path":row["relative_path"],"anomaly_type":"READ_ERROR","details":str(e)})
            logging.warning("Himawari isolated file failure %s: %s",p,e)
        if nominal and start and end:
            row.update(latencies(nominal,start,end,created))
        else:
            # Preserve independently computable delays even when another field failed.
            if nominal:
                row["analysis_time"]=utc_iso(nominal+timedelta(minutes=10))
            if nominal and start:
                row["start_offset_seconds"]=(start-nominal).total_seconds();row["start_before_nominal"]=start<nominal
            if start and end:
                row["scan_duration_seconds"]=(end-start).total_seconds();row["end_before_start"]=end<start
            if end and created:
                row["creation_delay_seconds"]=(created-end).total_seconds();row["created_before_end"]=created<end
            if nominal and created:row["nominal_to_created_seconds"]=(created-nominal).total_seconds()
            if nominal and end:row["causal_as_latest"]=end<=nominal+timedelta(minutes=10)
        row["parse_status"]="OK" if not notes else "ERROR"
        row["notes"]="; ".join(notes)
        row["read_seconds"]=time.perf_counter()-started
        rows.append(row)
        append_json(OUTPUT/"logs/himawari_checkpoint.jsonl",row)
        if (index+1)%200==0 or index+1==len(paths):logging.info("Himawari latency %d/%d",index+1,len(paths))
    frame=pd.DataFrame(rows)
    fully_parsed=frame[frame.parse_status=="OK"]
    delays=fully_parsed.creation_delay_seconds.dropna()
    p99=float(delays.quantile(.99,interpolation="linear")) if len(delays) else None
    for row in rows:
        findings=logical_anomalies(row,p99)
        row["latency_tail_review"]=any(kind=="LATENCY_TAIL_REVIEW" for kind,_ in findings)
        row["latency_tail_p99_seconds"]=p99
        row["needs_review"]=bool(findings) or row["parse_status"]!="OK"
        for kind,detail in findings:
            errors.append({"relative_path":row["relative_path"],"anomaly_type":kind,"details":detail})
    duplicate=frame.nominal_time.notna() & frame.nominal_time.duplicated(keep=False)
    for i in frame.index[duplicate]:
        rows[i]["needs_review"]=True
        errors.append({"relative_path":rows[i]["relative_path"],"anomaly_type":"DUPLICATE_NOMINAL_TIME","details":rows[i]["nominal_time"]})
    frame=pd.DataFrame(rows);summaries=[]
    for metric in ["start_offset_seconds","scan_duration_seconds","creation_delay_seconds","nominal_to_created_seconds"]:
        a=frame[metric].dropna()
        summaries.append({"metric":metric,"count":len(a),"min":a.min(),"mean":a.mean(),"median":a.median(),
                          "p90":a.quantile(.90),"p95":a.quantile(.95),"p99":a.quantile(.99),"max":a.max(),
                          "std":a.std(ddof=1),"std_ddof":1,"statistics_scope":"QC_STAT_ONLY",
                          "population":"all files with this metric successfully computed"})
    anomaly=pd.DataFrame(errors,columns=["relative_path","anomaly_type","details"])
    if len(anomaly):
        anomaly=anomaly.merge(frame[["relative_path","nominal_time","obs_start","obs_end","date_created","creation_delay_seconds","latency_tail_review"]],on="relative_path",how="left")
    write_csv(OUTPUT/"HIMAWARI_202407/himawari_202407_latency.csv",frame)
    write_csv(OUTPUT/"HIMAWARI_202407/himawari_202407_latency_summary.csv",summaries)
    write_csv(OUTPUT/"HIMAWARI_202407/himawari_202407_latency_anomalies.csv",anomaly)
    return frame,pd.DataFrame(summaries),anomaly
