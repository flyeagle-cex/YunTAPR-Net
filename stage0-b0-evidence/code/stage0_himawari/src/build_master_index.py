"""Read every source via bounded staging and preserve original metadata."""
from pathlib import Path
import logging,time
import numpy as np
import pandas as pd
from config import RAW,CHANNELS,CONFIG
from common import append_json
from build_sequence_index import parse_filename
from read_himawari import read_himawari_7ch,MissingChannelError,CoordinateShapeError,MetadataError
from qc import assess,primary

def build_master(paths,staging,output:Path,prefix="monthly"):
    rows=[];metadata_path=output/"qc"/f"{prefix}_metadata.jsonl"
    for index,p in enumerate(paths):
        started=time.perf_counter()
        row=dict(relative_path=str(p.relative_to(RAW)),filename=p.name,size_bytes=p.stat().st_size,
                 timestamp_filename_utc=None,satellite=None,grid_tag=None,read_success=False,
                 has_all_7_channels=False,quality_class="READ_ERROR",flags="",notes="",
                 valid_fraction_total=None,time_mismatch=False,start_time=None,end_time=None,date_created=None,
                 shape_lat=None,shape_lon=None,lat_min=None,lat_max=None,lon_min=None,lon_max=None,
                 lat_direction=None,lon_direction=None,grid_resolution_lat=None,grid_resolution_lon=None,
                 grid_signature=None)
        for channel in CHANNELS:row["valid_fraction_B"+channel[-2:]]=None
        nominal=None
        try:
            info=parse_filename(p.name);nominal=info["time"]
            row.update(timestamp_filename_utc=nominal.isoformat(),satellite=info["satellite"],grid_tag=info["grid_tag"])
        except Exception as error:row["notes"]=str(error)
        try:
            x,mask,lat,lon,metadata=read_himawari_7ch(p,staging,verify_hash=index<5)
            row.update(assess(x,mask,lat,lon,metadata,nominal),read_success=True,has_all_7_channels=True)
            if nominal is None:
                row["flags"]+=";OTHER";row["notes"]+=";filename time parsing failed"
                row["quality_class"]=primary(row["flags"].split(";"))
            append_json(metadata_path,{"relative_path":row["relative_path"],"metadata":metadata})
            del x,mask
        except Exception as error:
            kind=("MISSING_CHANNEL" if isinstance(error,MissingChannelError) else
                  "COORD_ANOMALY" if isinstance(error,CoordinateShapeError) else
                  "OTHER" if isinstance(error,MetadataError) else "READ_ERROR")
            row.update(quality_class=kind,flags=kind,notes=f"{type(error).__name__}: {error}")
            logging.error("%s %s",p,row["notes"])
        row["load_seconds"]=time.perf_counter()-started
        rows.append(row)
        # Append-only checkpoint permits diagnosis if a long run stops.
        append_json(output/"index"/f"{prefix}_master_checkpoint.jsonl",row)
        if (index+1)%100==0 or index+1==len(paths):
            logging.info("%s QC %d/%d read_success=%d",prefix,index+1,len(paths),sum(r["read_success"] for r in rows))
    return pd.DataFrame(rows)

def finalize_qc(frame,reference=None):
    frame=frame.copy()
    counts=frame["grid_signature"].dropna().value_counts()
    if reference is None:
        reference=counts.index[0] if len(counts) else None
    median=float(frame["size_bytes"].median()) if len(frame) else 0
    for i,row in frame.iterrows():
        flags=[v for v in row["flags"].split(";") if v];notes=row["notes"]
        if row.get("grid_signature") and row["grid_signature"]!=reference:flags.append("GRID_VARIANT")
        if median and (row["size_bytes"]<median*CONFIG["size_anomaly_median_ratio_low"] or
                       row["size_bytes"]>median*CONFIG["size_anomaly_median_ratio_high"]):
            notes+=";SIZE_ANOMALY_DIAGNOSTIC_ONLY"
        frame.loc[i,"flags"]=";".join(dict.fromkeys(flags))
        frame.loc[i,"notes"]=notes
        frame.loc[i,"quality_class"]=primary(flags)
    return frame,reference
