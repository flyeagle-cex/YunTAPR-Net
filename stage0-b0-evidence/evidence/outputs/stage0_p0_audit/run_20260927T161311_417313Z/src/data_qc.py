"""Per-file bounded-memory diagnostics. Missing observations are never changed to zero."""
import numpy as np
from config import CONFIG
from common import attrs
def decode_values(raw,metadata):
    raw=np.asarray(raw)
    raw_nan=np.isnan(raw) if np.issubdtype(raw.dtype,np.inexact) else np.zeros(raw.shape,dtype=bool)
    finite=np.isfinite(raw);fill=np.zeros(raw.shape,dtype=bool)
    for name in ("_FillValue","missing_value"):
        if name in metadata:
            for sentinel in np.asarray(metadata[name]).reshape(-1):
                fill|=np.isnan(raw) if np.isnan(sentinel) else raw==sentinel
    mask=finite & ~fill
    if "valid_range" in metadata:
        mask&=(raw>=metadata["valid_range"][0])&(raw<=metadata["valid_range"][1])
    if "valid_min" in metadata:mask&=raw>=metadata["valid_min"]
    if "valid_max" in metadata:mask&=raw<=metadata["valid_max"]
    # Missing scale/offset means unscaled data, per ordinary NetCDF storage semantics.
    x=raw.astype(np.float64)*float(metadata.get("scale_factor",1))+float(metadata.get("add_offset",0))
    mask&=np.isfinite(x)
    x[~mask]=np.nan
    return x,mask,raw_nan,fill
def variable_qc(variable,qi=False):
    metadata=attrs(variable);total=0;valid=0;raw_nans=0;fills=0;sum_value=0.0
    minimum=None;maximum=None;zero=0;negative=0;counts={v:0 for v in CONFIG["precip_thresholds_mm_per_hr"]}
    qi_values=[]
    if variable.ndim<1:raise ValueError("Expected an array variable")
    for begin in range(0,variable.shape[0],CONFIG["read_chunk_first_dimension"]):
        raw=variable[begin:begin+CONFIG["read_chunk_first_dimension"]]
        x,mask,nan,fill=decode_values(raw,metadata);a=x[mask]
        total+=x.size;valid+=a.size;raw_nans+=int(nan.sum());fills+=int(fill.sum())
        if a.size:
            lo=float(a.min());hi=float(a.max())
            minimum=lo if minimum is None else min(minimum,lo)
            maximum=hi if maximum is None else max(maximum,hi)
            sum_value+=float(a.sum(dtype=np.float64))
            zero+=int((a==0).sum());negative+=int((a<0).sum())
            if qi:qi_values.append(a)
            else:
                for threshold in counts:counts[threshold]+=int((a>threshold).sum())
    prefix="QI" if qi else "precip"
    result={f"{prefix}_nan_fraction":(total-valid)/total if total else None,
            f"{prefix}_valid_fraction":valid/total if total else None,
            f"{prefix}_min":minimum,f"{prefix}_max":maximum,
            f"{prefix}_mean":sum_value/valid if valid else None,
            "total_pixel_count":total,"valid_pixel_count":valid,"invalid_pixel_count":total-valid,
            "raw_nan_count":raw_nans,"fillvalue_count":fills,"negative_valid_pixel_count":negative,
            "statistics_scope":"QC_STAT_ONLY","status":"OK" if valid else "NO_VALID_VALUES"}
    if qi:
        result["QI_median"]=float(np.median(np.concatenate(qi_values))) if valid else None
        result["notes"]="Per-file exact median; no QI threshold, filtering, or model input."
    else:
        result["R_eq_0_fraction"]=zero/valid if valid else None
        result["R_eq_0_total_fraction"]=zero/total if total else None
        result["zero_valid_pixel_count"]=zero
        for threshold,count in counts.items():
            name=str(threshold).replace(".","p")
            result[f"R_gt_{name}_fraction"]=count/valid if valid else None
            result[f"R_gt_{name}_total_fraction"]=count/total if total else None
        result["fraction_denominator"]="valid pixels; *_total_fraction uses all pixels"
    return result
