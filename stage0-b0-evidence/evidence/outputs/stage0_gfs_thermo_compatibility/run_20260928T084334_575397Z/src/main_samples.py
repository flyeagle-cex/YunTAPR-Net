"""Allowlisted main raw verification only; no primary full-library metadata scan."""
import json
import numpy as np,pandas as pd
from config import *
from common import *
from time_audit import audit_time
def main():
    targets=json.loads((OUT/"logs/main_targeted_samples.json").read_text(encoding="utf-8"))
    oldgrid=pd.read_csv(BASELINE/"GFS/gfs_grid_audit.csv").set_index("relative_path")
    oldtime=pd.read_csv(BASELINE/"GFS/gfs_time_semantics_audit.csv").set_index("relative_path")
    reader=Reader();records=[];checks=[];reference=None
    for target in targets:
        rel=target["relative_path"];path=MAIN/rel
        with reader.open(path,hash_check=True) as ds:
            lat=np.asarray(ds["latitude"][:]);lon=np.asarray(ds["longitude"][:])
            time=audit_time(ds,path.name)
            meta={"relative_path":rel,"selection":target["selection"],"year":target["year"],
                "global_attrs":attrs(ds),"time_audit":time,
                "variables":{n:{"attrs":attrs(v),"shape":v.shape,"dtype":str(v.dtype),"dimensions":v.dimensions,
                                "coordinate_values":v[:] if v.ndim<=1 else None} for n,v in ds.variables.items()}}
            records.append(meta)
            check={"relative_path":rel,"lat_hash_matches_baseline":coord_hash(lat)==oldgrid.loc[rel,"lat_hash"],
                "lon_hash_matches_baseline":coord_hash(lon)==oldgrid.loc[rel,"lon_hash"],
                "init_unchanged":time["init_time"]==oldtime.loc[rel,"init_time"],
                "valid_unchanged":time["valid_time"]==oldtime.loc[rel,"valid_time"],
                "lead_unchanged":time["lead_time_hours"]==oldtime.loc[rel,"lead_time_hours"]}
            assert all(v for k,v in check.items() if k!="relative_path")
            checks.append(check)
            if reference is None:reference={"relative_path":rel,"latitude":lat,"longitude":lon,"lat_hash":coord_hash(lat),"lon_hash":coord_hash(lon),
                "source":"Targeted original file verified against reused unique-grid baseline"}
    write_json(OUT/"TIME_LINEAGE/main_targeted_raw_metadata.json",records)
    write_json(OUT/"logs/main_grid_reference.json",reference)
    write_csv(OUT/"TIME_LINEAGE/main_targeted_verification.csv",checks)
    print(dumps([{"file":r["relative_path"],"global_attrs":r["global_attrs"]} for r in records if r["year"] in [2023,2025]]))
if __name__=="__main__":main()
