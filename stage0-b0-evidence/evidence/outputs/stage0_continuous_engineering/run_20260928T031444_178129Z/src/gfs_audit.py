"""Full main-root metadata audit; supplemental roots are inventoried, never merged."""
from collections import Counter
from pathlib import Path
import hashlib,json,logging,time
import numpy as np,pandas as pd
from config import OUT,GFS,SUPPLEMENT,EXTENSIONS,REQUIRED
from common import Reader,attrs,dumps,coord_info,format_signature,write_json,write_csv,append_json,sha256
from rules import parse_filename,canonical_variables,pressure_to_hpa,forbidden_precip,choose_main
from time_audit import audit_time

def discover():
    # Preferred existing root wins. Sibling candidates are only named/inventoried.
    roots=[p for p in GFS.parent.iterdir() if p.is_dir() and p.name.lower().startswith("gfs")]
    main=choose_main(roots,GFS)
    records=[];main_files=[]
    for root in sorted(roots):
        files=sorted(p for p in root.rglob("*") if p.is_file() and p.suffix.lower() in EXTENSIONS)
        years=Counter(p.relative_to(root).parts[0] for p in files)
        records.append({"root":str(root),"selected_main":root==main,"file_count":len(files),
                        "extensions":dict(Counter(p.suffix.lower() for p in files)),"top_level_inventory":dict(years)})
        if root==main:main_files=files
    write_json(OUT/"GFS/discovery.json",{"roots":records,"main_root":str(main),
               "status":"MULTIPLE_GFS_ROOTS_RESEARCHER_REVIEW" if len(roots)>1 else "SINGLE_ROOT"})
    return main_files,records

def audit():
    files,roots=discover();reader=Reader();inventory=[];grids=[];times=[];presence=[];forbidden=[];errors=[]
    mapping={};metadata_patterns={};samples=[];reference=None
    sample_ids={0,len(files)//4,len(files)//2,3*len(files)//4,len(files)-1}
    for index,p in enumerate(files):
        stat=p.stat();relative=str(p.relative_to(GFS))
        row={"relative_path":relative,"filename":p.name,"size_bytes":stat.st_size,"mtime_ns":stat.st_mtime_ns,
             "extension":p.suffix.lower(),"year":None,"date":None,"parse_status":"UNKNOWN",
             "read_success":False,"file_format":"UNKNOWN","netcdf_data_model":None,"notes":""}
        try:
            fn=parse_filename(p.name);row.update(year=fn["init"].year,date=fn["init"].date().isoformat(),parse_status="FILENAME_PARSED")
        except ValueError:pass
        if index in sample_ids:samples.append({"source_path":str(p),"sha256_before":sha256(p)})
        coverage={"relative_path":relative,**{k:False for k in REQUIRED},
                  "core_variable_complete":False,"surface_pressure_support_status":"MISSING","status":"NOT_READ"}
        grid={"relative_path":relative,"status":"NOT_READ"}
        timing={"relative_path":relative,"parse_status":"READ_ERROR","init_time":None,"valid_time":None,
                "lead_time_hours":None,"time_consistency_status":"UNKNOWN","release_status":"NOT ESTABLISHED FROM CURRENT FILE METADATA"}
        try:
            row["file_format"]=format_signature(p)
            if not row["file_format"].startswith("NetCDF"):raise RuntimeError("Reader unavailable for detected format; file retained")
            with reader.open(p,hash_check=index in sample_ids) as ds:
                row["netcdf_data_model"]=ds.data_model;ga=attrs(ds)
                ga_key=hashlib.sha256(dumps(ga).encode()).hexdigest()
                if ga_key not in metadata_patterns:
                    metadata_patterns[ga_key]=1
                    append_json(OUT/"GFS/global_metadata_patterns.jsonl",{"metadata_id":ga_key,"global_attrs":ga,"example":relative})
                row["metadata_id"]=ga_key
                timing.update(audit_time(ds,p.name))
                row["parse_status"]=timing["parse_status"]
                latname=next((k for k in ("latitude","lat") if k in ds.variables),None)
                lonname=next((k for k in ("longitude","lon") if k in ds.variables),None)
                if latname is None or lonname is None:raise ValueError("Missing lat/lon coordinates")
                lat=np.asarray(ds[latname][:]);lon=np.asarray(ds[lonname][:]);li=coord_info(lat);lo=coord_info(lon)
                if reference is None:reference=(lat.copy(),lon.copy())
                signature=hashlib.sha256((li["hash"]+lo["hash"]).encode()).hexdigest()
                grid.update(status="OK",lat_count=len(lat),lon_count=len(lon),lat_min=li["minimum"],lat_max=li["maximum"],
                    lon_min=lo["minimum"],lon_max=lo["maximum"],lat_direction=li["direction"],lon_direction=lo["direction"],
                    resolution_lat=li["resolution"],resolution_lon=lo["resolution"],lat_hash=li["hash"],lon_hash=lo["hash"],
                    grid_hash=signature,coordinates_equal_first=bool(np.array_equal(lat,reference[0]) and np.array_equal(lon,reference[1])))
                pressure={}
                for name,v in ds.variables.items():
                    if "pressure_level" in name.lower() or "isobaric" in name.lower() and v.ndim==1:
                        try:pressure[name]=pressure_to_hpa(np.asarray(v[:]).reshape(-1),getattr(v,"units",""))
                        except Exception as e:row["notes"]+=f";pressure coordinate: {e}"
                ps_support=False
                for name,v in ds.variables.items():
                    vat=attrs(v)
                    if v.ndim<2:continue
                    levels=[value for dim in v.dimensions for value in pressure.get(dim,[])]
                    canonical,reason=canonical_variables(name,vat,v.dimensions,levels)
                    # Presence requires compatible spatial dimensions, not just a suggestive variable name.
                    spatial_ok=latname in v.dimensions and lonname in v.dimensions
                    if canonical and not spatial_ok:canonical=[];reason="SPATIAL_DIMENSIONS_INCOMPATIBLE"
                    record={"raw_variable_name":name,"standard_name":str(vat.get("standard_name","")),
                      "shortName":str(vat.get("shortName",vat.get("GRIB_shortName",""))),
                      "level_type":str(vat.get("Grib2_Level_Desc",vat.get("GRIB_typeOfLevel","isobaric" if levels else "named surface/column"))),
                      "pressure_levels_hpa":dumps(levels),"units":str(vat.get("units","")),"shape":str(v.shape),
                      "dimensions":str(v.dimensions),"canonical_names":dumps(canonical),"mapping_reason":reason,
                      "raw_attributes":dumps(vat),"predictor_allowed":bool(canonical)}
                    key=dumps(record)
                    if key not in mapping:mapping[key]={**record,"file_count":0,"example_file":relative}
                    mapping[key]["file_count"]+=1
                    for c in canonical:coverage[c]=True
                    if "PS" in canonical and str(vat.get("units","")).lower() in {"pa","hpa","mbar"}:ps_support=True
                    if forbidden_precip(name,vat):
                        forbidden.append({"relative_path":relative,"raw_variable_name":name,"units":str(vat.get("units","")),
                                          "shape":str(v.shape),"model_predictor_allowed":False,
                                          "reason":"FORBIDDEN_PRECIPITATION_PREDICTOR; file not declared bad"})
                coverage["core_variable_complete"]=all(coverage[k] for k in REQUIRED)
                coverage["surface_pressure_support_status"]="PASS" if ps_support and pressure else "PARTIAL" if coverage["PS"] else "MISSING"
                coverage["status"]="METADATA_AUDITED"
                row["read_success"]=True
        except Exception as e:
            row["notes"]+=f";{type(e).__name__}: {e}"
            errors.append({"relative_path":relative,"error_type":type(e).__name__,"error":str(e)})
            logging.warning("Isolated GFS audit failure %s: %s",relative,e)
        inventory.append(row);grids.append(grid);times.append(timing);presence.append(coverage)
        if (index+1)%500==0 or index+1==len(files):
            logging.info("GFS main-root audit %d/%d read_success=%d",index+1,len(files),sum(r["read_success"] for r in inventory))
    inv=pd.DataFrame(inventory);timeframe=pd.DataFrame(times);present=pd.DataFrame(presence)
    write_csv(OUT/"GFS/gfs_inventory.csv",inv)
    write_csv(OUT/"GFS/gfs_grid_audit.csv",grids)
    write_csv(OUT/"GFS/gfs_time_semantics_audit.csv",timeframe)
    write_csv(OUT/"GFS/gfs_variable_presence.csv",present)
    write_csv(OUT/"GFS/gfs_variable_mapping.csv",[{**r,"total_main_root_files":len(files),"availability_fraction":r["file_count"]/len(files)} for r in mapping.values()])
    write_csv(OUT/"GFS/gfs_forbidden_precip_variables_detected.csv",forbidden,
              ["relative_path","raw_variable_name","units","shape","model_predictor_allowed","reason"])
    write_csv(OUT/"GFS/gfs_read_errors.csv",errors,["relative_path","error_type","error"])
    write_csv(OUT/"logs/gfs_source_sample_hashes_before.csv",samples)
    coverage=[]
    for name in REQUIRED:
        count=int(present[name].sum())
        coverage.append({"canonical_name":name,"file_count":count,"total_files":len(files),
                         "availability_fraction":count/len(files),"coverage_type":"METADATA_PRESENCE_NOT_PIXEL_VALIDITY"})
    write_csv(OUT/"GFS/gfs_variable_coverage.csv",coverage)
    write_json(OUT/"logs/gfs_execution.json",{"file_count":len(files),"read_success":int(inv.read_success.sum()),
       "read_failed":len(errors),"metadata_patterns":len(metadata_patterns),"variable_mapping_patterns":len(mapping),
       "supplement_not_merged":True})
if __name__=="__main__":
    logging.basicConfig(level=logging.INFO,format="%(asctime)s %(levelname)s %(message)s",
        handlers=[logging.FileHandler(OUT/"logs/audit_run.log",encoding="utf-8"),logging.StreamHandler()])
    audit()
