"""Only the deterministic 20 selected cases are opened; all raw handles are read-only."""
import json
import numpy as np,pandas as pd
from config import *
from common import *
from time_audit import audit_time
from compat_rules import source_evidence
def run():
    cases=json.loads((OUT/"logs/selected_cases.json").read_text(encoding="utf-8"))
    reader=Reader();records=[];traces=[]
    for case in cases:
        sides={}
        for branch,root,relative in [("main",MAIN,case["main_relative"]),("thermo",THERMO,case["thermo_relative"])]:
            p=root/relative
            with reader.open(p,hash_check=True) as ds:
                timing=audit_time(ds,p.name);ga=attrs(ds)
                lat=np.asarray(ds["latitude"][:]);lon=np.asarray(ds["longitude"][:])
                variables={n:{"shape":v.shape,"dtype":str(v.dtype),"attrs":attrs(v)} for n,v in ds.variables.items()}
                record={"case_id":case["case_id"],"branch":branch,"path":str(p),"relative_path":relative,
                    "global_attrs":ga,"time":timing,"variables":variables,"lat_hash":coord_hash(lat),"lon_hash":coord_hash(lon)}
            assert timing["init_time"]==case["init_time"] and timing["valid_time"]==case["valid_time"] and timing["lead_time_hours"]==case["lead"]
            records.append(record);sides[branch]=record
        a,b=sides["main"],sides["thermo"]
        ea=source_evidence(a["global_attrs"],pd.Timestamp(case["init_time"]).strftime("%Y%m%d%H"),case["lead"])
        eb=source_evidence(b["global_attrs"],pd.Timestamp(case["init_time"]).strftime("%Y%m%d%H"),case["lead"])
        assert a["lat_hash"]==b["lat_hash"] and a["lon_hash"]==b["lon_hash"]
        traces.append({"case_id":case["case_id"],"period":case["period"],"init_time":case["init_time"],"lead":case["lead"],"valid_time":case["valid_time"],
            "main_file":a["path"],"thermo_file":b["path"],"main_original_token":dumps(ea),"thermo_original_token":dumps(eb),
            "main_source":str(a["global_attrs"].get("source","UNKNOWN")),"thermo_source":str(b["global_attrs"].get("source","UNKNOWN")),
            "conversion_evidence":dumps({s:{k:v for k,v in obj["global_attrs"].items() if any(x in k.lower() for x in ["history","creat","conversion"])} for s,obj in sides.items()}),
            "pairing_consistency":"PASS_CURRENT_TIME_AND_EXACT_COORDINATE_HASH",
            "notes":"Directly reread selected files only; provenance linkage to logs is assessed separately; no release inferred"})
    write_json(OUT/"PROVENANCE/selected_case_raw_metadata.json",records)
    write_csv(OUT/"PROVENANCE/forecast_case_trace.csv",traces)
    print(dumps({"cases":len(traces),"raw_files":len(records),"all_time_and_grid_checks":"PASS"}),flush=True)
if __name__=="__main__":run()
