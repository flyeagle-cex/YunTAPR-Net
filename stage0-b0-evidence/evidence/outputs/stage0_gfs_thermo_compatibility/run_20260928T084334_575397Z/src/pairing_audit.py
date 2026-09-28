"""File-level forecast compatibility audit; output is an audit table, never training samples."""
from collections import defaultdict,Counter
import calendar,json
import pandas as pd
from config import *
from common import *
from compat_rules import *

def metadata(path):
    result={}
    for line in path.open(encoding="utf-8"):
        r=json.loads(line);result[r["metadata_id"]]=r["global_attrs"]
    return result
def load_side(root,prefix,thermo=False):
    inv=pd.read_csv(root/(prefix+"inventory.csv"))
    time=pd.read_csv(root/(prefix+"time_semantics_audit.csv"),usecols=["relative_path","init_time","valid_time","lead_time_hours","time_consistency_status","auxiliary_metadata_conflict"])
    grid=pd.read_csv(root/(prefix+"grid_audit.csv"))
    cols=["relative_path","lat_hash","lon_hash","grid_hash"]+(["exact_coordinate_match"] if thermo else [])
    df=time.merge(inv[["relative_path","read_success","metadata_id"]],on="relative_path",how="left").merge(grid[cols],on="relative_path",how="left")
    if thermo:
        presence=pd.read_csv(root/(prefix+"variable_presence.csv"))
        df=df.merge(presence[["relative_path",*TARGETS]],on="relative_path",how="left")
    df["time_ok"]=df.time_consistency_status.eq("PASS")
    df["read_ok"]=df.read_success.fillna(False)
    index=defaultdict(list);unknown=[]
    for r in df.to_dict("records"):
        if pd.isna(r["init_time"]) or pd.isna(r["lead_time_hours"]):unknown.append(r);continue
        index[(r["init_time"],float(r["lead_time_hours"]))].append(r)
    return index,unknown,df
def run():
    main,mu,mdf=load_side(BASELINE/"GFS","gfs_")
    thermo,tu,tdf=load_side(OUT/"THERMO","gfs_thermo_",True)
    mg=metadata(BASELINE/"GFS/global_metadata_patterns.jsonl")
    tg=metadata(OUT/"THERMO/global_metadata_patterns.jsonl")
    rows=[];conflicts=[];lineage=[];cardinal=Counter()
    for key in sorted(set(main)|set(thermo)):
        aa=main.get(key,[]);bb=thermo.get(key,[]);init,lead=key
        cardinal[pairing_cardinality(len(aa),len(bb))]+=1
        a=aa[0] if len(aa)==1 else {};b=bb[0] if len(bb)==1 else {}
        source="NOT_ESTABLISHED"
        if a and b:
            ma=mg.get(a["metadata_id"],{});ta=tg.get(b["metadata_id"],{})
            cycle=pd.Timestamp(init).strftime("%Y%m%d%H")
            source=lineage_status(ma,ta,cycle,lead);b["source_lineage_status"]=source
            me=source_evidence(ma,cycle,lead);te=source_evidence(ta,cycle,lead)
            def select(attrs):
                return {k:v for k,v in attrs.items() if any(t in k.lower() for t in [
                    "source","institution","center","model","product","history","reference","convention",
                    "creat","conversion","original","process","generat","title","archive","avail"])}
            lineage.append({"init_time":init,"lead_time":lead,"main_file":a["relative_path"],"thermo_file":b["relative_path"],
                "lineage_status":source,"main_source":str(ma.get("source","UNKNOWN")),"thermo_source":str(ta.get("source","UNKNOWN")),
                "main_provenance_fields":dumps(select(ma)),"thermo_provenance_fields":dumps(select(ta)),
                "main_evidence":dumps(me),"thermo_evidence":dumps(te),"main_auxiliary_conflict":a["auxiliary_metadata_conflict"],
                "thermo_auxiliary_conflict":b["auxiliary_metadata_conflict"],
                "independent_raw_grib_content_identity":"NOT_ESTABLISHED"})
        status=classify_pair(aa,bb)
        row={"init_time":init,"lead_time":lead,"valid_time_main":a.get("valid_time"),"valid_time_thermo":b.get("valid_time"),
             "main_present":bool(aa),"thermo_present":bool(bb),"main_count":len(aa),"thermo_count":len(bb),
             "main_files":dumps([r["relative_path"] for r in aa]),"thermo_files":dumps([r["relative_path"] for r in bb]),
             "valid_time_match":bool(a and b and a["valid_time"]==b["valid_time"]),
             "grid_match":bool(a and b and a["lat_hash"]==b["lat_hash"] and a["lon_hash"]==b["lon_hash"] and b.get("exact_coordinate_match",False)),
             **{v.replace("_","")+"_present":bool(b.get(v,False)) for v in TARGETS},
             "pair_status":status,"source_lineage_status":source,
             "main_auxiliary_metadata_conflict":a.get("auxiliary_metadata_conflict"),
             "thermo_auxiliary_metadata_conflict":b.get("auxiliary_metadata_conflict"),
             "audit_only":True}
        rows.append(row)
        if status in {"TIME_CONFLICT","GRID_CONFLICT","METADATA_CONFLICT"}:
            conflicts.append({"conflict_type":status,"side":"paired","init_time":init,"lead_time":lead,
                "valid_time":a.get("valid_time"),"file_count":len(aa)+len(bb),"files":dumps({"main":row["main_files"],"thermo":row["thermo_files"]}),
                "ambiguous":len(aa)>1 or len(bb)>1,"note":"No file selected where ambiguous"})
    for side,df in [("main",mdf),("thermo",tdf)]:
        for valid,group in df[df.valid_time.notna()].groupby("valid_time"):
            if len(group)>1:
                distinct=group[["init_time","lead_time_hours"]].drop_duplicates()
                conflicts.append({"conflict_type":"SHARED_VALID_TIME_DIFFERENT_FORECAST_KEYS" if len(distinct)==len(group) else "DUPLICATE_FORECAST_KEY",
                    "side":side,"init_time":dumps(group.init_time.tolist()),"lead_time":dumps(group.lead_time_hours.tolist()),
                    "valid_time":valid,"file_count":len(group),"files":dumps(group.relative_path.tolist()),
                    "ambiguous":len(distinct)!=len(group),"note":"Shared valid_time alone is not ambiguous when init/lead differ"})
    for side,unknown in [("main",mu),("thermo",tu)]:
        for r in unknown:
            conflicts.append({"conflict_type":"UNKNOWN_FORECAST_KEY","side":side,"init_time":None,"lead_time":None,"valid_time":r.get("valid_time"),
                "file_count":1,"files":r["relative_path"],"ambiguous":True,"note":"Not guessed or silently paired"})
    pair=pd.DataFrame(rows)
    write_csv(OUT/"COMPATIBILITY/main_thermo_pairing.csv",pair)
    write_csv(OUT/"COMPATIBILITY/pairing_conflicts.csv",conflicts,["conflict_type","side","init_time","lead_time","valid_time","file_count","files","ambiguous","note"])
    write_csv(OUT/"COMPATIBILITY/source_lineage_fields.csv",lineage)
    grid=pd.read_csv(OUT/"THERMO/gfs_thermo_grid_audit.csv")
    write_csv(OUT/"COMPATIBILITY/grid_compatibility.csv",grid[["relative_path","lat_hash","lon_hash","exact_coordinate_match","lat_hash_match","lon_hash_match","shape_match","resolution_match","max_abs_lat_diff","max_abs_lon_diff"]])
    monthly=[];missing=[];pair["month"]=pd.to_datetime(pair.init_time,utc=True).dt.strftime("%Y-%m")
    hours=sorted(pd.to_datetime(mdf.init_time,utc=True).dt.hour.unique().tolist())
    leads=sorted(mdf.lead_time_hours.dropna().unique().tolist())
    for y in [2023,2024,2025]:
        for m in range(3,11):
            month=f"{y}-{m:02d}";group=pair[pair.month==month];present_main=group[group.main_present]
            expected_keys=set((iso(pd.Timestamp(y,m,day,h,tz="UTC").to_pydatetime()),float(lead))
                for day in range(1,calendar.monthrange(y,m)[1]+1) for h in hours for lead in leads)
            main_keys={k for k in main if k in expected_keys};thermo_keys={k for k in thermo if k in expected_keys}
            absent=expected_keys-thermo_keys
            for init,lead in sorted(absent):missing.append({"month":month,"init_time":init,"lead_time":lead,"reason":"THERMO_KEY_MISSING"})
            expected_inits={k[0] for k in expected_keys};thermo_inits={k[0] for k in thermo_keys}
            complete=int(group.pair_status.eq("MATCHED_COMPLETE").sum())
            matched=int((group.main_count.eq(1)&group.thermo_count.eq(1)).sum())
            no_variable={v:int((group.main_present&~group[v.replace("_","")+"_present"]).sum()) for v in TARGETS}
            monthly.append({"month":month,"expected_main_forecast_pairs":len(expected_keys),"main_present":len(main_keys),
                "thermo_present":len(thermo_keys),"matched_pairs":matched,"complete_T_RH_pairs":complete,
                "coverage_fraction":complete/len(expected_keys),"missing_main_pairs":len(expected_keys-main_keys),
                "missing_init_cycles":len(expected_inits-thermo_inits),"missing_lead_pairs":len(absent),
                "missing_lead_values":dumps(sorted(set(leads)-set(k[1] for k in thermo_keys))),
                "missing_variables_by_pair":dumps(no_variable),"time_conflicts":int(group.pair_status.eq("TIME_CONFLICT").sum()),
                "grid_conflicts":int(group.pair_status.eq("GRID_CONFLICT").sum()),"metadata_conflicts":int(group.pair_status.eq("METADATA_CONFLICT").sum()),
                "source_lineage_counts":dumps(group.source_lineage_status.value_counts().to_dict()),
                "status":month_status(len(expected_keys),len(main_keys),len(thermo_keys),complete),
                "readiness_scope":"STRUCTURAL_METADATA_COVERAGE_ONLY; not approval or observed availability"})
    write_csv(OUT/"COMPATIBILITY/research_period_thermo_coverage.csv",monthly)
    write_csv(OUT/"COMPATIBILITY/research_period_missing_thermo_keys.csv",missing,["month","init_time","lead_time","reason"])
    summary={"main_files":len(mdf),"thermo_files":len(tdf),"union_forecast_keys":len(pair),
        "pair_status_counts":pair.pair_status.value_counts().to_dict(),"cardinality":dict(cardinal),
        "one_to_one_fraction_of_thermo_files":cardinal["one_to_one"]/len(tdf),
        "one_to_one_fraction_of_main_files":cardinal["one_to_one"]/len(mdf),
        "unknown_main_keys":len(mu),"unknown_thermo_keys":len(tu),"lineage_counts":pd.DataFrame(lineage).lineage_status.value_counts().to_dict(),
        "shared_valid_time_groups":len(conflicts),"ambiguous_conflict_rows":sum(bool(r["ambiguous"]) for r in conflicts),
        "research_expected_pairs":sum(r["expected_main_forecast_pairs"] for r in monthly),
        "research_complete_pairs":sum(r["complete_T_RH_pairs"] for r in monthly),
        "research_month_status":dict(Counter(r["status"] for r in monthly))}
    write_json(OUT/"logs/pairing_summary.json",summary);print(dumps(summary),flush=True)
if __name__=="__main__":run()
