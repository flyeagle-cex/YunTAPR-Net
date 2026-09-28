"""Group by real coordinate fingerprint as well as filename tag."""
import pandas as pd
from config import CONFIG
def grid_audit(master):
    rows=[]
    for (tag,sig),group in master.groupby(["grid_tag","grid_signature"],dropna=False):
        r=group.iloc[0]
        rows.append(dict(grid_tag=tag,grid_signature=sig,file_count=len(group),
          shape=f"({r['shape_lat']},{r['shape_lon']})",lat_min=r["lat_min"],lat_max=r["lat_max"],
          lon_min=r["lon_min"],lon_max=r["lon_max"],lat_direction=r["lat_direction"],
          lon_direction=r["lon_direction"],median_dlat=r["grid_resolution_lat"],
          median_dlon=r["grid_resolution_lon"],covers_yunnan_context=CONFIG["covers_yunnan_context"],
          anomaly_count=int((group["quality_class"]!="OK").sum()),
          notes="Exact coordinates hashed; no bbox criterion and no automatic latitude flip."))
    return pd.DataFrame(rows)
