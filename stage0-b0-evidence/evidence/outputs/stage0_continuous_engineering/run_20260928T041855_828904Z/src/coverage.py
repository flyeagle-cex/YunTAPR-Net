"""Diagnostic coverage grids; these do not select forecast vintages or training years."""
from datetime import datetime,timezone,timedelta
import calendar
import numpy as np,pandas as pd
from config import OUT,REQUIRED,CONFIG
from common import write_csv
from rules import coverage_status
def research_months():
    return [f"{y}-{m:02d}" for y in CONFIG["research_candidate_years"] for m in CONFIG["research_candidate_months"]]
def build_matrix(imerg_counts,gfs_months,him_months,static):
    rows=[]
    for month in research_months():
        year,number=map(int,month.split("-"));days=calendar.monthrange(year,number)[1]
        g=gfs_months.get(month,{})
        inventory=g.get("inventory_status","MISSING")
        gstatus=inventory if inventory!="READY" else "READY" if g.get("core_complete",False) else "PARTIAL"
        rows.append({"YYYY-MM":month,"Himawari_available":him_months.get(month,"NOT_AUDITED"),
             "IMERG_available":coverage_status(imerg_counts.get(month,0),days),
             "GFS_available":gstatus,"GFS_inventory_status":inventory,
             "SRTM_available_if_known":static.get("SRTM","NOT_AUDITED"),
             "Yunnan_mask_available_if_known":static.get("mask","NOT_AUDITED"),
             "external_validation_available_if_known":static.get("external","NOT_AUDITED"),
             "IMERG_observed_days":imerg_counts.get(month,0),"IMERG_calendar_days":days,
             "GFS_missing_core_variables":g.get("missing_core_variables","UNKNOWN"),
             "notes":"Main GFS only; no supplemental-root merge. NOT_AUDITED is not MISSING."})
    return pd.DataFrame(rows)
def temporal_coverage(inv,times,presence):
    merged=inv[["relative_path","read_success"]].merge(times,on="relative_path").merge(presence,on="relative_path")
    merged["init_dt"]=pd.to_datetime(merged.init_time,utc=True,errors="coerce")
    merged["valid_dt"]=pd.to_datetime(merged.valid_time,utc=True,errors="coerce")
    parsed=merged[merged.init_dt.notna() & merged.lead_time_hours.notna()].copy()
    hours=sorted(parsed.init_dt.dt.hour.unique().tolist())
    leads=sorted(parsed.lead_time_hours.unique().tolist())
    rows=[];cycles=[];leadgaps=[]
    for month,group in parsed.groupby(parsed.init_dt.dt.strftime("%Y-%m")):
        first=pd.Timestamp(month+"-01",tz="UTC");last=first+pd.offsets.MonthEnd(0)
        observed_init=set(group.init_dt);observed_pairs=set(zip(group.init_dt,group.lead_time_hours))
        expected=[d+pd.Timedelta(hours=h) for d in pd.date_range(first,last,freq="D") for h in hours]
        missing=[d for d in expected if d not in observed_init]
        for init in missing:cycles.append({"month":month,"missing_init_time":init.isoformat(),"reference":"observed global init-hour set; diagnostic only"})
        gaps=[(d,h) for d in expected for h in leads if (d,h) not in observed_pairs]
        for init,lead in gaps:leadgaps.append({"month":month,"init_time":init.isoformat(),"missing_lead_hours":lead,"reference":"global observed lead union; not a scientific requirement"})
        absent=[v for v in REQUIRED if not group[v].all()]
        rows.append({"month":month,"year":int(month[:4]),"file_count":len(group),
                     "unique_init_count":len(observed_init),"init_hours":str(hours),
                     "lead_hours_observed":str(sorted(group.lead_time_hours.unique().tolist())),
                     "global_reference_leads":str(leads),"expected_init_count_calendar_month":len(expected),
                     "missing_cycles":len(missing),"missing_init_lead_pairs_reference":len(gaps),
                     "first_init":group.init_dt.min().isoformat(),"last_init":group.init_dt.max().isoformat(),
                     "first_valid":group.valid_dt.min().isoformat(),"last_valid":group.valid_dt.max().isoformat(),
                     "core_complete_files":int(group.core_variable_complete.sum()),
                     "missing_core_variables":";".join(absent),"inventory_status":"READY" if not missing and not gaps else "PARTIAL",
                     "surface_pressure_support_status":"PASS" if group.surface_pressure_support_status.eq("PASS").all() else
                       "MISSING" if group.surface_pressure_support_status.eq("MISSING").all() else "PARTIAL"})
    write_csv(OUT/"GFS/gfs_temporal_coverage.csv",rows)
    write_csv(OUT/"GFS/gfs_missing_cycles.csv",cycles,["month","missing_init_time","reference"])
    write_csv(OUT/"GFS/gfs_missing_lead_pairs.csv",leadgaps,["month","init_time","missing_lead_hours","reference"])
    return pd.DataFrame(rows),hours,leads
