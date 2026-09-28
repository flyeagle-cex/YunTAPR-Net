"""Transparent file diagnostics; descriptive flags are not automatic repair decisions."""
from __future__ import annotations
import hashlib,json
from datetime import datetime,timezone
import numpy as np
from config import CONFIG,CHANNELS
from common import dumps

def coordinate_info(values:np.ndarray,kind:str)->dict:
    a=np.asarray(values,dtype=np.float64)
    finite=bool(np.isfinite(a).all())
    d=np.diff(a)
    direction="ascending" if finite and len(d)>0 and np.all(d>0) else (
              "descending" if finite and len(d)>0 and np.all(d<0) else "non_monotonic")
    spacing=float(np.median(np.abs(d))) if finite and len(d)>0 else None
    regular=bool(spacing is not None and np.allclose(np.abs(d),spacing,rtol=0,
                 atol=CONFIG["coordinate_spacing_atol_degrees"]))
    limit=90 if kind=="lat" else 180
    in_bounds=bool(finite and np.all(np.abs(a)<=limit))
    return {"min":float(a.min()) if finite and len(a) else None,
            "max":float(a.max()) if finite and len(a) else None,"direction":direction,
            "spacing":spacing,"anomaly":not(in_bounds and regular and direction!="non_monotonic")}

def grid_info(lat,lon,xshape):
    a=coordinate_info(lat,"lat");b=coordinate_info(lon,"lon")
    h=hashlib.sha256()
    for v in (lat,lon):
        h.update(np.asarray(v,dtype="<f8").tobytes())
    h.update(str(tuple(xshape)).encode())
    return dict(shape_lat=len(lat),shape_lon=len(lon),lat_min=a["min"],lat_max=a["max"],
                lon_min=b["min"],lon_max=b["max"],lat_direction=a["direction"],lon_direction=b["direction"],
                grid_resolution_lat=a["spacing"],grid_resolution_lon=b["spacing"],
                coord_anomaly=a["anomaly"] or b["anomaly"],grid_signature=h.hexdigest())

def primary(flags):
    return next((q for q in CONFIG["qc_priority"] if q in flags),"OK")

def assess(x,mask,lat,lon,metadata,nominal):
    flags=[];notes=[]
    row=grid_info(lat,lon,x.shape)
    if row["coord_anomaly"]:flags.append("COORD_ANOMALY")
    fractions=mask.mean(axis=(1,2))
    total=float(mask.mean())
    row["valid_fraction_total"]=total
    for ch,value in zip(CHANNELS,fractions):row["valid_fraction_B"+ch[-2:]]=float(value)
    if total==CONFIG["all_fill_fraction"]:flags.append("ALL_FILL")
    elif total<CONFIG["partial_valid_upper"]:flags.append("PARTIAL_VALID")
    if 0<total<CONFIG["almost_empty_fraction"]:notes.append("ALMOST_EMPTY")
    mismatch=False
    for name in ("start_time","end_time"):
        info=metadata[name];row[name]=info["iso"]
        if info["parse_error"]:
            flags.append("OTHER");notes.append(name+"_parse_error="+info["parse_error"])
        if info["iso"] and nominal:
            try:
                actual=datetime.fromisoformat(info["iso"].replace("Z","+00:00"))
                if actual.tzinfo is None:raise ValueError("Internal time has no timezone")
                delta=(actual-nominal).total_seconds()
                row[name+"_minus_nominal_seconds"]=delta
                if abs(delta)>CONFIG["time_mismatch_tolerance_seconds"]:
                    mismatch=True;notes.append(f"{name}_minus_nominal_seconds={delta:.6f}")
            except Exception as error:flags.append("OTHER");notes.append(str(error))
        elif not info["iso"]:notes.append(name+"_metadata_absent")
    if mismatch:flags.append("TIME_MISMATCH")
    # Exact internal observation times are retained; nominal time is only a candidate index.
    row.update(time_mismatch=mismatch,date_created=metadata["date_created"],
               quality_class=primary(flags),flags=";".join(dict.fromkeys(flags)),notes=";".join(notes))
    return row
