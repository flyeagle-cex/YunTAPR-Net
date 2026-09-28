"""Explicit audit pairing rules, not a Dataset or approved integration."""
import re,json
import numpy as np
from common import coord_hash
TARGETS=("T_850","T_700","T_500","RH_850","RH_700","RH_500")
def compare_grid(mainlat,mainlon,lat,lon):
    a,b,c,d=map(np.asarray,(mainlat,mainlon,lat,lon))
    shape=a.shape==c.shape and b.shape==d.shape
    return {"shape_match":bool(shape),"exact_coordinate_match":bool(shape and np.array_equal(a,c) and np.array_equal(b,d)),
        "lat_hash_match":coord_hash(a)==coord_hash(c),"lon_hash_match":coord_hash(b)==coord_hash(d),
        "max_abs_lat_diff":float(np.max(abs(a-c))) if a.shape==c.shape else None,
        "max_abs_lon_diff":float(np.max(abs(b-d))) if b.shape==d.shape else None}
def normalized_forecast_token(text):
    found=[]
    for cycle,lead in re.findall(r"gfs\.0p25\.(\d{10})\.f(\d{3})",str(text),re.I):
        found.append((cycle,int(lead)))
    for day,cycle1,cycle2,lead in re.findall(r"gfs\.(\d{8})/(\d{2})/atmos/gfs\.t(\d{2})z\.pgrb2\.0p25\.f(\d{3})",str(text),re.I):
        if cycle1==cycle2:found.append((day+cycle1,int(lead)))
    return sorted(set(found))
def source_evidence(attrs,cycle,lead):
    direct={k:v for k,v in attrs.items() if any(s in k.lower() for s in ("source","url","original_filename","references")) and "history" not in k.lower()}
    hist={k:v for k,v in attrs.items() if "history" in k.lower()}
    direct_tokens=normalized_forecast_token(" ".join(map(str,direct.values())))
    history_tokens=normalized_forecast_token(" ".join(map(str,hist.values())))
    wanted=(cycle,int(lead))
    text=" ".join(map(str,attrs.values())).lower()
    product=any(s in text for s in ("d084001","noaa-gfs-bdp-pds","ncep gfs","global forecast system"))
    current_token=wanted in direct_tokens or (not direct_tokens and wanted in history_tokens)
    conflicting_direct=bool(direct_tokens and any(t!=wanted for t in direct_tokens))
    stale_history=bool(history_tokens and any(t!=wanted for t in history_tokens))
    return {"gfs_product_evidence":product,"current_token_match":current_token,
            "direct_token_conflict":conflicting_direct,"stale_history":stale_history,
            "direct_tokens":direct_tokens,"history_tokens":history_tokens,
            "direct_fields":direct,"history_fields":hist}
def lineage_status(mainattrs,thermoattrs,cycle,lead):
    a=source_evidence(mainattrs,cycle,lead);b=source_evidence(thermoattrs,cycle,lead)
    if a["direct_token_conflict"] or b["direct_token_conflict"]:return "CONFLICTING"
    if not all(x["gfs_product_evidence"] and x["current_token_match"] for x in [a,b]):return "NOT_ESTABLISHED"
    # Declared archive/token matches are engineering evidence, not independent raw-GRIB content verification.
    return "SUPPORTED_WITH_CAVEATS"
def classify_pair(main,thermo):
    if not main:return "THERMO_ONLY"
    if not thermo:return "MAIN_ONLY"
    if len(main)!=1 or len(thermo)!=1:return "METADATA_CONFLICT"
    a,b=main[0],thermo[0]
    if not a.get("time_ok",False) or not b.get("time_ok",False) or a.get("valid_time")!=b.get("valid_time"):return "TIME_CONFLICT"
    if a.get("lat_hash")!=b.get("lat_hash") or a.get("lon_hash")!=b.get("lon_hash") or not b.get("exact_coordinate_match",False):return "GRID_CONFLICT"
    if not a.get("read_ok",False) or not b.get("read_ok",False):return "METADATA_CONFLICT"
    if b.get("source_lineage_status")=="CONFLICTING":return "METADATA_CONFLICT"
    return "MATCHED_COMPLETE" if all(b.get(v,False) for v in TARGETS) else "MATCHED_PARTIAL_VARIABLES"
def month_status(expected,main_present,thermo_present,complete):
    if thermo_present==0:return "MISSING"
    if expected>0 and main_present==expected and complete==expected:return "READY"
    return "PARTIAL"
def pairing_cardinality(main_n,thermo_n):
    if main_n==0 or thermo_n==0:return "unmatched"
    if main_n==1 and thermo_n==1:return "one_to_one"
    if main_n==1:return "one_to_many"
    if thermo_n==1:return "many_to_one"
    return "ambiguous"
