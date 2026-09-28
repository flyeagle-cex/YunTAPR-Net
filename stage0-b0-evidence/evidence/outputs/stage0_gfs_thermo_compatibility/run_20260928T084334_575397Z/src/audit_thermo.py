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
    manifest=pd.read_csv(OUT/"logs/thermo_manifest_before.csv")
    return [GFS/p for p in manifest.relative_path], []


def audit():
    files,roots=discover();reader=Reader();inventory=[];grids=[];times=[];presence=[];forbidden=[];errors=[];structures=[]
    mainref=json.loads((OUT/"logs/main_grid_reference.json").read_text(encoding="utf-8"))
    mainlat=np.asarray(mainref["latitude"]);mainlon=np.asarray(mainref["longitude"])
    mapping={};metadata_patterns={};samples=[];reference=None
    sample_ids={0,len(files)//4,len(files)//2,3*len(files)//4,len(files)-1}
    for index,p in enumerate(files):
        stat=p.stat();relative=str(p.relative_to(GFS))
        row={"relative_path":relative,"filename":p.name,"size_bytes":stat.st_size,"mtime_ns":stat.st_mtime_ns,
             "extension":p.suffix.lower(),"year":None,"month":None,"date":None,"parse_status":"UNKNOWN",
             "read_success":False,"file_format":"UNKNOWN","netcdf_data_model":None,"notes":""}
        try:
            fn=parse_filename(p.name);row.update(year=fn["init"].year,month=fn["init"].month,date=fn["init"].date().isoformat(),parse_status="FILENAME_PARSED")
        except ValueError:pass
        if index in sample_ids:samples.append({"source_path":str(p),"sha256_before":sha256(p)})
        coverage={"relative_path":relative,**{k:False for k in REQUIRED},
                  "core_variable_complete":False,"thermo_surface_pressure_presence_status":"MISSING","status":"NOT_READ"}
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
                    append_json(OUT/"THERMO/global_metadata_patterns.jsonl",{"metadata_id":ga_key,"global_attrs":ga,"example":relative})
                row["metadata_id"]=ga_key
                timing.update(audit_time(ds,p.name))
                structure={"dimensions":{n:len(v) for n,v in ds.dimensions.items()},
                    "variables":{n:{"dims":v.dimensions,"shape":v.shape,"dtype":str(v.dtype),"attrs":attrs(v)} for n,v in ds.variables.items()}}
                structure_id=hashlib.sha256(dumps(structure).encode()).hexdigest()
                structures.append({"relative_path":relative,"data_model":ds.data_model,"structure_id":structure_id,
                    "dimensions":dumps(structure["dimensions"]),"coordinate_variables":dumps({n:{"dtype":str(v.dtype),"values":v[:],"attrs":attrs(v)} for n,v in ds.variables.items() if v.ndim<=1}),
                    "variable_structure":dumps(structure["variables"]),"global_attrs":dumps(ga)})
                row["parse_status"]=timing["parse_status"]
                row.update(init_time=timing["init_time"],valid_time=timing["valid_time"],lead_time=timing["lead_time_hours"])
                timing["file_mtime_ns"]=stat.st_mtime_ns
                timing["file_mtime_role"]="FILESYSTEM_MODIFICATION_ONLY_NOT_OPERATIONAL_AVAILABILITY"
                timing["consistency_status"]=timing["time_consistency_status"]
                timing["lead_time"]=timing["lead_time_hours"]
                latname=next((k for k in ("latitude","lat") if k in ds.variables),None)
                lonname=next((k for k in ("longitude","lon") if k in ds.variables),None)
                if latname is None or lonname is None:raise ValueError("Missing lat/lon coordinates")
                lat=np.asarray(ds[latname][:]);lon=np.asarray(ds[lonname][:]);li=coord_info(lat);lo=coord_info(lon)
                if reference is None:reference=(lat.copy(),lon.copy())
                signature=hashlib.sha256((li["hash"]+lo["hash"]).encode()).hexdigest()
                grid.update(file=relative,grid_id=signature,grid_status="OK",
                    lat_shape=str(lat.shape),lon_shape=str(lon.shape),lat_dtype=str(lat.dtype),lon_dtype=str(lon.dtype),
                    field_shape=dumps({n:list(v.shape) for n,v in ds.variables.items() if v.ndim>=2}),
                    mean_dlat=float(np.mean(np.abs(np.diff(lat.astype(float))))),
                    mean_dlon=float(np.mean(np.abs(np.diff(lon.astype(float))))),
                    status="OK",lat_count=len(lat),lon_count=len(lon),lat_min=li["minimum"],lat_max=li["maximum"],
                    lon_min=lo["minimum"],lon_max=lo["maximum"],lat_direction=li["direction"],lon_direction=lo["direction"],
                    resolution_lat=li["resolution"],resolution_lon=lo["resolution"],lat_hash=li["hash"],lon_hash=lo["hash"],
                    grid_hash=signature,coordinates_equal_first=bool(np.array_equal(lat,reference[0]) and np.array_equal(lon,reference[1])))
                shape_match=lat.shape==mainlat.shape and lon.shape==mainlon.shape
                grid.update(exact_coordinate_match=bool(shape_match and np.array_equal(lat,mainlat) and np.array_equal(lon,mainlon)),
                    lat_hash_match=li["hash"]==mainref["lat_hash"],lon_hash_match=lo["hash"]==mainref["lon_hash"],
                    shape_match=shape_match,resolution_match=bool(li["resolution"]==0.25 and lo["resolution"]==0.25),
                    max_abs_lat_diff=float(np.max(np.abs(lat-mainlat))) if lat.shape==mainlat.shape else None,
                    max_abs_lon_diff=float(np.max(np.abs(lon-mainlon))) if lon.shape==mainlon.shape else None)
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
                      "long_name":str(vat.get("long_name","")),
                      "typeOfLevel":str(vat.get("GRIB_typeOfLevel",vat.get("Grib2_Level_Desc","UNKNOWN"))),
                      "level":dumps(levels),
                      "shortName":str(vat.get("shortName",vat.get("GRIB_shortName",""))),
                      "level_type":str(vat.get("Grib2_Level_Desc",vat.get("GRIB_typeOfLevel","isobaric" if levels else "named surface/column"))),
                      "pressure_levels_hpa":dumps(levels),"units":str(vat.get("units","")),"shape":str(v.shape),
                      "dtype":str(v.dtype),"pressure_coordinate":dumps({d:{"values_hpa":pressure[d],"raw_units":getattr(ds[d],"units","UNKNOWN")} for d in v.dimensions if d in pressure}),"dimensions":str(v.dimensions),"canonical_names":dumps(canonical),"mapping_reason":reason,
                      "raw_attributes":dumps(vat),"predictor_allowed":bool(canonical)}
                    key=dumps(record)
                    if key not in mapping:mapping[key]={**record,"file_count":0,"example_file":relative}
                    mapping[key]["file_count"]+=1
                    for c in canonical:
                        if c in REQUIRED:coverage[c]=True
                    if "PS" in canonical and str(vat.get("units","")).lower() in {"pa","hpa","mbar"}:ps_support=True
                    if forbidden_precip(name,vat):
                        forbidden.append({"relative_path":relative,"raw_variable_name":name,"units":str(vat.get("units","")),
                                          "shape":str(v.shape),"model_predictor_allowed":False,
                                          "reason":"FORBIDDEN_AS_YUNTAPR_PREDICTOR; file not declared bad"})
                coverage["core_variable_complete"]=all(coverage[k] for k in REQUIRED)
                coverage["thermo_surface_pressure_presence_status"]="PASS" if ps_support and pressure else "PARTIAL" if coverage.get("PS",False) else "MISSING"
                coverage["status"]="METADATA_AUDITED"
                row["read_success"]=True
        except Exception as e:
            row["notes"]+=f";{type(e).__name__}: {e}"
            errors.append({"relative_path":relative,"error_type":type(e).__name__,"error":str(e)})
            logging.warning("Isolated GFS audit failure %s: %s",relative,e)
        inventory.append(row);grids.append(grid);times.append(timing);presence.append(coverage)
        if (index+1)%500==0 or index+1==len(files):
            logging.info("THERMO independent audit %d/%d read_success=%d",index+1,len(files),sum(r["read_success"] for r in inventory))
    write_csv(OUT/"THERMO/gfs_thermo_file_structure_audit.csv",structures)
    inv=pd.DataFrame(inventory);timeframe=pd.DataFrame(times);present=pd.DataFrame(presence)
    write_csv(OUT/"THERMO/gfs_thermo_inventory.csv",inv)
    write_csv(OUT/"THERMO/gfs_thermo_grid_audit.csv",grids)
    write_csv(OUT/"THERMO/gfs_thermo_time_semantics_audit.csv",timeframe)
    write_csv(OUT/"THERMO/gfs_thermo_variable_presence.csv",present)
    write_csv(OUT/"THERMO/gfs_thermo_variable_mapping.csv",[{**r,"total_thermo_files":len(files),"availability_fraction":r["file_count"]/len(files)} for r in mapping.values()])
    write_csv(OUT/"THERMO/gfs_thermo_forbidden_precip_variables_detected.csv",forbidden,
              ["relative_path","raw_variable_name","units","shape","model_predictor_allowed","reason"])
    write_csv(OUT/"THERMO/gfs_thermo_read_errors.csv",errors,["relative_path","error_type","error"])
    write_csv(OUT/"logs/thermo_source_sample_hashes_before.csv",samples)
    coverage=[]
    for name in REQUIRED:
        count=int(present[name].sum())
        coverage.append({"canonical_name":name,"file_count":count,"total_files":len(files),
                         "availability_fraction":count/len(files),"coverage_type":"METADATA_PRESENCE_NOT_PIXEL_VALIDITY"})
    write_csv(OUT/"THERMO/gfs_thermo_variable_coverage.csv",coverage)
    write_json(OUT/"logs/thermo_execution.json",{"file_count":len(files),"read_success":int(inv.read_success.sum()),
       "read_failed":len(errors),"metadata_patterns":len(metadata_patterns),"variable_mapping_patterns":len(mapping),
       "main_thermo_not_merged":True})
if __name__=="__main__":
    logging.basicConfig(level=logging.INFO,format="%(asctime)s %(levelname)s %(message)s",
        handlers=[logging.FileHandler(OUT/"logs/audit_run.log",encoding="utf-8"),logging.StreamHandler()])
    audit()
