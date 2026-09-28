"""Inventory and six per-file IMERG audits; exceptions are recorded and isolated."""
from __future__ import annotations
from pathlib import Path
from datetime import date,timedelta
from collections import Counter
import calendar,hashlib,json,logging,time
import numpy as np,pandas as pd
from config import IMERG,OUTPUT,CONFIG
from common import attrs,safe,dumps,decode_cf_time,utc_iso,coordinate_info,write_csv,append_json
from data_qc import variable_qc
from time_rules import imerg_filename_date,audit_daily_times

def inventory(paths):
    rows=[]
    for p in paths:
        st=p.stat();row={"relative_path":str(p.relative_to(IMERG)),"filename":p.name,
                        "year":None,"month":None,"day":None,"date":None,"size_bytes":st.st_size,
                        "mtime_ns":st.st_mtime_ns,"filename_parse_status":"OK","notes":""}
        try:
            d=imerg_filename_date(p.name)
            row.update(year=d.year,month=d.month,day=d.day,date=d.isoformat())
        except Exception as e:row.update(filename_parse_status="PARSE_ERROR",notes=str(e))
        rows.append(row)
    frame=pd.DataFrame(rows)
    write_csv(OUTPUT/"IMERG/imerg_inventory.csv",frame)
    valid=frame[frame.date.notna()]
    unique=set(date.fromisoformat(d) for d in valid.date)
    missing=[];yearrows=[]
    if unique:
        low=min(unique);high=max(unique);day=low
        while day<=high:
            if day not in unique:missing.append({"date":day.isoformat(),"scope":"between first and last observed filename dates"})
            day+=timedelta(days=1)
        for year,g in valid.groupby("year"):
            y=int(year);lo=max(low,date(y,1,1));hi=min(high,date(y,12,31))
            yearrows.append({"year":y,"file_count":len(g),"unique_date_count":g.date.nunique(),
                             "first_date":g.date.min(),"last_date":g.date.max(),
                             "days_within_observed_span":(hi-lo).days+1,
                             "missing_days_within_observed_span":sum(date.fromisoformat(r["date"]).year==y for r in missing),
                             "calendar_year_days":366 if calendar.isleap(y) else 365,
                             "outside_observed_span_days":(366 if calendar.isleap(y) else 365)-((hi-lo).days+1)})
    duplicates=valid[valid.date.duplicated(keep=False)].copy()
    write_csv(OUTPUT/"IMERG/imerg_year_inventory.csv",yearrows,["year","file_count","unique_date_count","first_date","last_date"])
    write_csv(OUTPUT/"IMERG/imerg_missing_dates.csv",missing,["date","scope"])
    write_csv(OUTPUT/"IMERG/imerg_duplicate_dates.csv",duplicates)
    return frame

def run_imerg(paths,staging):
    inv=inventory(paths)
    reports={k:[] for k in ["metadata","time","grid","precip","qi"]}
    review=[];reference=None
    for index,(p,item) in enumerate(zip(paths,inv.to_dict("records"))):
        tick=time.perf_counter();base={"relative_path":item["relative_path"],"filename":p.name,"status":"NOT_RUN","error":""}
        rows={k:dict(base) for k in reports};reasons=[]
        file_date=date.fromisoformat(item["date"]) if item["date"] else None
        if file_date is None:reasons.append("FILENAME_DATE_PARSE_ERROR")
        try:
            with staging.open(p,verify_hash=index in {0,len(paths)//4,len(paths)//2,3*len(paths)//4,len(paths)-1}) as ds:
                meta=rows["metadata"]
                global_attrs=attrs(ds);dims={k:len(v) for k,v in ds.dimensions.items()}
                present={k:k in ds.variables for k in ["time","lat","lon","precipitation","precipitationQualityIndex"]}
                meta.update(status="OK",open_success=True,title=str(global_attrs.get("title","")),
                            source=str(global_attrs.get("source","")),history=str(global_attrs.get("history","")),
                            dimensions=dumps(dims),time_count=dims.get("time"),lat_count=dims.get("lat"),lon_count=dims.get("lon"),
                            has_precipitation=present["precipitation"],has_precipitationQualityIndex=present["precipitationQualityIndex"],
                            precipitation_units=str(getattr(ds["precipitation"],"units","")) if present["precipitation"] else None,
                            precipitation_FillValue=dumps(getattr(ds["precipitation"],"_FillValue",None)) if present["precipitation"] else None,
                            time_units=str(getattr(ds["time"],"units","")) if present["time"] else None,
                            calendar=str(getattr(ds["time"],"calendar","standard")) if present["time"] else None)
                meta["expected_title_match"]=meta["title"]==CONFIG["imerg_expected_title"]
                meta["expected_source_match"]=meta["source"]==CONFIG["imerg_expected_source"]
                meta["expected_units_match"]=meta["precipitation_units"]==CONFIG["imerg_expected_units"]
                for key in ["expected_title_match","expected_source_match","expected_units_match"]:
                    if not meta[key]:reasons.append(key.upper()+"_FALSE")
                append_json(OUTPUT/"IMERG/imerg_original_metadata.jsonl",
                    {"relative_path":item["relative_path"],"global_attrs":global_attrs,
                     "variables":{k:{"shape":v.shape,"dimensions":v.dimensions,"dtype":str(v.dtype),"attrs":attrs(v)} for k,v in ds.variables.items()}})
                try:
                    if not present["time"]:raise KeyError("Missing time variable")
                    tv=ds["time"];raw=tv[:];values=decode_cf_time(raw,getattr(tv,"units",None),getattr(tv,"calendar","standard"))
                    time_row=audit_daily_times(values,file_date)
                    rows["time"].update(time_row,status="OK" if time_row["exact_daily_slots"] else "NEEDS_REVIEW",
                                        raw_values=dumps(raw),decoded_values=dumps([utc_iso(t) for t in values]),
                                        time_units=meta["time_units"],calendar=meta["calendar"],
                                        native_granule_bounds="NOT_PRESENT_NOT_INFERRED")
                    for key in ("missing_times","duplicate_times","unexpected_times"):rows["time"][key]=dumps(rows["time"][key])
                    if not time_row["exact_daily_slots"]:reasons.append("DAILY_TIME_PATTERN_ANOMALY")
                except Exception as e:
                    rows["time"].update(status="PARSE_ERROR",error=f"{type(e).__name__}: {e}");reasons.append("TIME_PARSE_ERROR")
                try:
                    if not(present["lat"] and present["lon"]):raise KeyError("Missing coordinates")
                    lat=np.asarray(ds["lat"][:]);lon=np.asarray(ds["lon"][:])
                    if lat.ndim!=1 or lon.ndim!=1:raise ValueError("Coordinates are not one-dimensional")
                    li=coordinate_info(lat);lo=coordinate_info(lon)
                    if reference is None:reference=(lat.copy(),lon.copy())
                    grid_hash=hashlib.sha256((li["hash"]+":"+lo["hash"]).encode()).hexdigest()
                    spatial_match=True
                    if present["precipitation"]:
                        pv=ds["precipitation"]
                        spatial_match=pv.dimensions==("time","lat","lon") and pv.shape[1:]==(len(lat),len(lon))
                    gr=dict(status="OK",grid_hash=grid_hash,lat_hash=li["hash"],lon_hash=lo["hash"],
                            lat_count=len(lat),lon_count=len(lon),lat_direction=li["direction"],lon_direction=lo["direction"],
                            lat_min=li["min"],lat_max=li["max"],lon_min=lo["min"],lon_max=lo["max"],
                            mean_dlat=li["mean_delta"],mean_dlon=lo["mean_delta"],
                            lat_equals_reference=bool(np.array_equal(lat,reference[0])),
                            lon_equals_reference=bool(np.array_equal(lon,reference[1])),
                            precipitation_shape=str(ds["precipitation"].shape) if present["precipitation"] else None,
                            precipitation_spatial_dimensions_match=spatial_match)
                    if not (li["finite"] and lo["finite"] and spatial_match) or "non_monotonic" in (li["direction"],lo["direction"]):
                        gr["status"]="NEEDS_REVIEW";reasons.append("COORDINATE_ANOMALY")
                    if not(gr["lat_equals_reference"] and gr["lon_equals_reference"]):reasons.append("GRID_VARIANT")
                    rows["grid"].update(gr)
                    meta.update({k:v for k,v in gr.items() if k.startswith(("lat_","lon_","mean_"))})
                except Exception as e:
                    rows["grid"].update(status="ERROR",error=f"{type(e).__name__}: {e}");reasons.append("GRID_AUDIT_ERROR")
                for key,variable in (("precip","precipitation"),("qi","precipitationQualityIndex")):
                    try:
                        if not present[variable]:raise KeyError(f"Missing variable {variable}")
                        qc=variable_qc(ds[variable],qi=key=="qi")
                        rows[key].update(qc)
                        if qc["invalid_pixel_count"]:reasons.append(variable+"_HAS_MISSING")
                        if key=="precip" and qc["negative_valid_pixel_count"]:reasons.append("NEGATIVE_PRECIPITATION")
                        if qc["status"]!="OK":reasons.append(variable+"_"+qc["status"])
                    except Exception as e:
                        rows[key].update(status="ERROR",error=f"{type(e).__name__}: {e}");reasons.append(variable+"_QC_ERROR")
        except Exception as e:
            logging.warning("IMERG isolated file failure %s: %s",p,e)
            reasons.append("FILE_READ_ERROR")
            for row in rows.values():row.update(status="READ_ERROR",error=f"{type(e).__name__}: {e}")
            rows["metadata"]["open_success"]=False
        for key,row in rows.items():
            row["read_and_audit_seconds"]=time.perf_counter()-tick
            row["needs_review"]=bool(reasons)
            reports[key].append(row)
        if reasons:review.append({"relative_path":item["relative_path"],"reasons":";".join(dict.fromkeys(reasons))})
        append_json(OUTPUT/"logs/imerg_checkpoint.jsonl",{"relative_path":item["relative_path"],"statuses":{k:r["status"] for k,r in rows.items()},"reasons":reasons})
        if (index+1)%100==0 or index+1==len(paths):logging.info("IMERG audited %d/%d files; needs_review=%d",index+1,len(paths),len(review))
    names={"metadata":"imerg_metadata_audit.csv","time":"imerg_time_audit.csv","grid":"imerg_grid_audit.csv",
           "precip":"imerg_precip_qc.csv","qi":"imerg_quality_index_audit.csv"}
    for key,name in names.items():write_csv(OUTPUT/"IMERG"/name,reports[key])
    write_csv(OUTPUT/"IMERG/imerg_needs_review.csv",review,["relative_path","reasons"])
    precipitation=pd.DataFrame(reports["precip"])
    if "precip_max" in precipitation:
        ranked=precipitation.sort_values("precip_max",ascending=False,na_position="last").head(20).copy()
        ranked["interpretation"]="Top 20 file maxima for review; no magnitude threshold imposed; not an error label."
        write_csv(OUTPUT/"IMERG/imerg_precip_extreme_examples.csv",ranked)
    return reports
