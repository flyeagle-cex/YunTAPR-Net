"""Keep all timing evidence; stale auxiliary metadata cannot become a release time."""
from datetime import datetime,timedelta,timezone
import re
import numpy as np
from common import attrs,decode_cf,parse_iso,iso,dumps
from rules import parse_filename,unique_time

def audit_time(ds,filename):
    ga=attrs(ds);init_candidates=[];valid_candidates=[];leads=[];raw={};issues=[];aux=[]
    filename_info=None
    try:
        filename_info=parse_filename(filename)
        init_candidates.append(("filename",filename_info["init"]))
        leads.append(("filename_f",filename_info["lead_hours"]))
    except ValueError:issues.append("FILENAME_TIME_UNKNOWN")
    for key in ("initialization_time_utc","forecast_cycle"):
        if key in ga:
            try:
                value=(datetime.strptime(str(ga[key]),"%Y%m%d%H").replace(tzinfo=timezone.utc)
                       if key=="forecast_cycle" else parse_iso(ga[key]))
                init_candidates.append(("global:"+key,value))
            except Exception as e:issues.append(f"{key}:{e}")
    if "valid_time_utc" in ga:
        try:valid_candidates.append(("global:valid_time_utc",parse_iso(ga["valid_time_utc"])))
        except Exception as e:issues.append(str(e))
    if "forecast_hour" in ga:
        try:leads.append(("global:forecast_hour",float(ga["forecast_hour"])))
        except Exception as e:issues.append(str(e))
    for name,v in ds.variables.items():
        standard=str(getattr(v,"standard_name",""))
        is_reference=name in {"reftime","forecast_reference_time"} or standard=="forecast_reference_time"
        is_valid=name=="valid_time"
        if not (is_reference or is_valid or name in {"accumulation_time","accumulation_time_bounds"}):continue
        values=v[:];vat=attrs(v);raw[name]={"values":values,"attrs":vat}
        try:
            dates=decode_cf(values,getattr(v,"units",None),getattr(v,"calendar","standard"))
            if is_reference or is_valid:
                if len(dates)!=1:raise ValueError("Multiple forecast times in one file require expanded audit")
                (init_candidates if is_reference else valid_candidates).append(("variable:"+name,dates[0]))
            if "udunits" in vat:
                legacy=decode_cf(values,vat["udunits"],vat.get("calendar","standard"))
                if legacy!=dates:aux.append(f"{name}: CF units and auxiliary udunits decode differently")
        except Exception as e:issues.append(f"{name}: {e}")
    init,init_state=unique_time(init_candidates)
    lead,lead_state=unique_time(leads)
    observed_valid,valid_state=unique_time(valid_candidates)
    derivation="INDEPENDENT_VALID_TIME"
    valid=observed_valid
    if valid_state=="UNKNOWN" and init is not None and lead is not None:
        valid=init+timedelta(hours=lead);derivation="DERIVED_NOT_INDEPENDENT"
    if lead is None and lead_state=="UNKNOWN" and init is not None and valid is not None:
        lead=(valid-init).total_seconds()/3600;derivation+=";LEAD_DERIVED_FROM_TIMES"
    if init_state=="CONFLICT" or lead_state=="CONFLICT" or valid_state=="CONFLICT":
        consistency="CONFLICT"
    elif init is None or valid is None or lead is None:consistency="UNKNOWN"
    elif valid!=init+timedelta(hours=lead):consistency="FAIL"
    elif derivation!="INDEPENDENT_VALID_TIME":consistency="DERIVED_CONSISTENT"
    else:consistency="PASS"
    history_text=" ".join(str(ga.get(k,"")) for k in ("history","History"))
    provenance_tokens=re.findall(r"gfs\.0p25\.(\d{10})\.f(\d{3})",history_text)
    if filename_info:
        for cycle,fh in provenance_tokens:
            if cycle!=filename_info["init"].strftime("%Y%m%d%H") or int(fh)!=filename_info["lead_hours"]:
                aux.append("History Original Dataset token differs from current filename cycle/lead")
    creation={k:v for k,v in ga.items() if any(word in k.lower() for word in
              ("creat","generat","history","download","conversion","avail","archive","source"))}
    return {"init_time":iso(init),"valid_time":iso(valid),"lead_time_hours":lead,
        "time_consistency_status":consistency,"reconstruction_basis":derivation,
        "init_candidates":dumps([(k,iso(t)) for k,t in init_candidates]),
        "valid_candidates":dumps([(k,iso(t)) for k,t in valid_candidates]),"lead_candidates":dumps(leads),
        "raw_time_metadata":dumps(raw),"creation_generation_archive_metadata":dumps(creation),
        "availability_proxy_raw":str(ga.get("conservative_available_time_utc","")) or None,
        "availability_note_raw":str(ga.get("availability_note","")) or None,
        "release_time":None,"operational_availability_time":None,
        "release_status":"NOT ESTABLISHED FROM CURRENT FILE METADATA",
        "auxiliary_metadata_conflict":bool(aux),"auxiliary_metadata_notes":"; ".join(aux),
        "parse_status":"OK" if consistency in {"PASS","DERIVED_CONSISTENT"} and not issues else consistency,
        "notes":"; ".join(issues)}
