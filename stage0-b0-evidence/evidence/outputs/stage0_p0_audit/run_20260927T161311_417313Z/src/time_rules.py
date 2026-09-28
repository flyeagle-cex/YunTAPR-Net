"""Audit only time information actually present in the daily subset and satellite file."""
from datetime import datetime,timedelta,timezone
from collections import Counter
import re
from common import utc_iso
def imerg_filename_date(filename):
    m=re.fullmatch(r"imerg_(\d{8})\.nc",filename,re.I)
    if not m:raise ValueError("Filename does not match imerg_YYYYMMDD.nc")
    return datetime.strptime(m[1],"%Y%m%d").date()
def himawari_filename(filename):
    m=re.fullmatch(r"NC_(H\d{2})_(\d{8})_(\d{4})_.*?\.(\d+_\d+)\.nc",filename,re.I)
    if not m:raise ValueError("Unrecognized Himawari filename")
    return {"satellite":m[1],"grid_tag":m[4],
            "nominal":datetime.strptime(m[2]+m[3],"%Y%m%d%H%M").replace(tzinfo=timezone.utc)}
def audit_daily_times(times,file_date):
    if file_date is None:raise ValueError("Cannot compare times with unparsed file date")
    expected=[datetime.combine(file_date,datetime.min.time(),timezone.utc)+timedelta(minutes=30*i) for i in range(48)]
    counts=Counter(times)
    missing=sorted(set(expected)-set(times));unexpected=sorted(set(times)-set(expected))
    duplicate=[t for t,n in counts.items() if n>1]
    diffs=[(b-a).total_seconds() for a,b in zip(times,times[1:])]
    return {"time_count":len(times),"count_is_48":len(times)==48,
            "strict_30min_intervals":len(times)>1 and all(d==1800 for d in diffs),
            "exact_daily_slots":times==expected,"filename_date_matches":all(t.date()==file_date for t in times) and bool(times),
            "missing_time_count":len(missing),"missing_times":[utc_iso(t) for t in missing],
            "duplicate_time_count":sum(n-1 for n in counts.values()),"duplicate_times":[utc_iso(t) for t in duplicate],
            "unexpected_times":[utc_iso(t) for t in unexpected],
            "non_30min_interval_count":sum(d!=1800 for d in diffs),
            "first_time":utc_iso(times[0]) if times else None,"last_time":utc_iso(times[-1]) if times else None}
def latencies(nominal,start,end,created):
    return {"start_offset_seconds":(start-nominal).total_seconds(),
            "scan_duration_seconds":(end-start).total_seconds(),
            "creation_delay_seconds":(created-end).total_seconds() if created else None,
            "nominal_to_created_seconds":(created-nominal).total_seconds() if created else None,
            "analysis_time":utc_iso(nominal+timedelta(minutes=10)),
            "causal_as_latest":end<=nominal+timedelta(minutes=10),
            "start_before_nominal":start<nominal,"end_before_start":end<start,
            "created_before_end":created<end if created else None}
