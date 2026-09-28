"""Two-file IMERG boundary check and bounded static metadata discovery."""
from pathlib import Path
import json,re,zipfile,math
import numpy as np,pandas as pd
from config import *
from common import *

def boundary():
    reader=Reader();values=[];patch=[];hashes=[];reference=None
    targets={"imerg_20250623.nc":["2025-06-23T23:30:00Z"],"imerg_20250624.nc":["2025-06-24T00:00:00Z","2025-06-24T00:30:00Z"]}
    for rel in CONFIG["boundary_files"]:
        source=IMERG/rel;before=sha256(source)
        with reader.open(source,hash_check=True) as ds:
            lat=np.asarray(ds["lat"][:]);lon=np.asarray(ds["lon"][:])
            if reference is None:reference=(lat.copy(),lon.copy())
            else:
                assert np.array_equal(reference[0],lat) and np.array_equal(reference[1],lon),"Boundary grid mismatch"
            iy=int(np.argmin(abs(lat-24.95)));ix=int(np.argmin(abs(lon-95.45)))
            timevar=ds["time"];dates=decode_cf(timevar[:],timevar.units,getattr(timevar,"calendar","standard"))
            v=ds["precipitation"]
            assert v.dimensions==("time","lat","lon"),f"Unexpected dimensions {v.dimensions}"
            def decoded(a):
                a=np.asarray(a,dtype=float);invalid=~np.isfinite(a)
                for key in ["_FillValue","missing_value"]:
                    if hasattr(v,key):invalid|=np.isin(a,np.asarray(getattr(v,key)).reshape(-1))
                a=a*float(getattr(v,"scale_factor",1))+float(getattr(v,"add_offset",0))
                return np.where(invalid,np.nan,a)
            for target in targets[source.name]:
                matches=[i for i,t in enumerate(dates) if iso(t)==target]
                assert len(matches)==1,f"Nonunique boundary timestamp {target}"
                it=matches[0];raw=np.asarray(v[it,iy,ix]);value=float(decoded(raw))
                values.append(dict(time_utc=target,file=str(source),time_index=it,lat_index=iy,lon_index=ix,
                    latitude=float(lat[iy]),longitude=float(lon[ix]),precipitation=value,
                    units=v.units,missing=not np.isfinite(value),coordinate_time_semantics="converted CF coordinate; native window association provisional"))
                if target=="2025-06-24T00:00:00Z":
                    assert iy>=2 and ix>=2 and iy+2<len(lat) and ix+2<len(lon)
                    block=decoded(v[it,iy-2:iy+3,ix-2:ix+3])
                    for row in range(5):
                        for col in range(5):
                            patch.append(dict(latitude=float(lat[iy-2+row]),longitude=float(lon[ix-2+col]),
                                              precipitation=float(block[row,col]),units=v.units))
        after=sha256(source);assert before==after
        hashes.append({"source_path":str(source),"sha256_before":before,"sha256_after":after,"unchanged":before==after})
    write_csv(OUT/"IMERG/imerg_boundary_values.csv",values)
    write_csv(OUT/"IMERG/imerg_boundary_patch_5x5.csv",patch)
    write_csv(OUT/"logs/imerg_boundary_source_hashes.csv",hashes)
    lines=["IMERG 2025-06-24 boundary extreme sanity check","No interpolation, clipping, exclusion or scientific threshold.",
           "Same nearest grid pixel to latitude=24.95, longitude=95.45; actual coordinates retained.",
           "Converted CF timestamps are used literally; native half-hour-window association remains PROVISIONAL.",""]
    lines += [f'{r["time_utc"]}: {r["precipitation"]:.8f} {r["units"]}; lat={r["latitude"]:.10f}, lon={r["longitude"]:.10f}; missing={r["missing"]}' for r in values]
    lines+=["","00:00 patch: rows follow original ascending latitude; columns original ascending longitude.",
            "latitudes: "+str(sorted({r["latitude"] for r in patch})),
            "longitudes: "+str(sorted({r["longitude"] for r in patch}))]
    lines+=[" ".join(f'{r["precipitation"]:9.4f}' for r in patch[j:j+5]) for j in range(0,25,5)]
    lines+=["","This check supplies adjacent-time and local-spatial evidence only; it does not establish meteorological truth or create a training/QC rule.",
            "Both raw files and staging copies passed SHA256 verification; raw hashes unchanged."]
    write_text(OUT/"IMERG/imerg_20250624_boundary_extreme_check.txt","\n".join(lines)+"\n")
    return values

def static():
    tiles=[];root=RAW/"SRTM"
    for path in sorted(root.glob("*.hgt.zip")):
        m=re.fullmatch(r"([NS])(\d{2})([EW])(\d{3})\.SRTMGL1\.hgt\.zip",path.name)
        if not m:
            tiles.append({"filename":path.name,"status":"UNPARSED"});continue
        lat=int(m[2])*(1 if m[1]=="N" else -1);lon=int(m[4])*(1 if m[3]=="E" else -1)
        record=dict(filename=path.name,lat_min=lat,lat_max=lat+1,lon_min=lon,lon_max=lon+1,
                    interpretation="USGS southwest tile corner naming; extent evidence only",status="NOT_READ")
        try:
            with zipfile.ZipFile(path,"r") as z:
                members=[m for m in z.infolist() if m.filename.lower().endswith(".hgt")]
                record["hgt_members"]=len(members)
                record["member_names"]=";".join(m.filename for m in members)
                record["member_bytes"]=sum(m.file_size for m in members)
                record["tile_shape_from_bytes"]=str((3601,3601)) if len(members)==1 and members[0].file_size==2*3601**2 else "UNKNOWN"
                record["status"]="CENTRAL_DIRECTORY_ONLY"
        except Exception as e:record["status"]="ERROR";record["error"]=str(e)
        tiles.append(record)
    write_csv(OUT/"CROSS_SOURCE/srtm_tile_inventory.csv",tiles)
    parsed=[t for t in tiles if "lat_min" in t]
    tilekeys={(t["lat_min"],t["lon_min"]) for t in parsed}
    ext={key:(min if key.endswith("min") else max)(r[key] for r in parsed) for key in ["lat_min","lat_max","lon_min","lon_max"]}
    absent=[{"lat_min":y,"lon_min":x} for y in range(ext["lat_min"],ext["lat_max"]) for x in range(ext["lon_min"],ext["lon_max"]) if (y,x) not in tilekeys]
    write_csv(OUT/"CROSS_SOURCE/srtm_rectangle_missing_tiles.csv",absent,["lat_min","lon_min"])
    boundary=RAW/"BOUNDARY/GADM41/gadm41_CHN_1.json.zip"
    before=sha256(boundary)
    with zipfile.ZipFile(boundary,"r") as z:
        names=[n for n in z.namelist() if n.endswith(".json")]
        assert len(names)==1
        info=z.getinfo(names[0]);assert info.file_size<20*1024*1024
        geo=json.loads(z.read(names[0]))
    yunnan=[f for f in geo["features"] if f["properties"].get("NAME_1")=="Yunnan"]
    assert len(yunnan)==1
    def points(a):
        if len(a)>=2 and all(isinstance(v,(float,int)) for v in a[:2]):yield a
        else:
            for child in a:yield from points(child)
    xy=np.asarray(list(points(yunnan[0]["geometry"]["coordinates"])))[:,:2]
    b=dict(source=str(boundary),crs=geo.get("crs"),properties=yunnan[0]["properties"],
           geometry_type=yunnan[0]["geometry"]["type"],coordinate_count=len(xy),
           lon_min=float(xy[:,0].min()),lon_max=float(xy[:,0].max()),
           lat_min=float(xy[:,1].min()),lat_max=float(xy[:,1].max()),
           mask_status="PARTIAL: polygon exists; no model-grid mask was constructed or verified",
           sha256_before=before,sha256_after=sha256(boundary))
    assert b["sha256_before"]==b["sha256_after"]
    write_json(OUT/"CROSS_SOURCE/yunnan_boundary_evidence.json",b)
    result={"SRTM":{"tile_count":len(tiles),"bounds":ext,"missing_tiles_within_rectangle":len(absent),
                   "status":"PARTIAL","note":"Tile filenames and ZIP directory evidence only; raster values, voids, CRS and DEM validity not audited",
                   "central_directory_errors":sum(t["status"]=="ERROR" for t in tiles)},
            "mask":b,"external_validation":{"status":"NOT_AUDITED","note":"No independent evaluation dataset readiness established; existence of raw products is not validation readiness."}}
    write_json(OUT/"CROSS_SOURCE/static_evidence.json",result)
    months=[]
    for year in CONFIG["research_candidate_years"]:
        for month in CONFIG["research_candidate_months"]:
            p=HIM/f"{year}{month:02d}"
            months.append({"month":f"{year}-{month:02d}","path":str(p),"directory_exists":p.is_dir(),
                "status":"PARTIAL" if (year,month)==(2024,7) else "NOT_AUDITED",
                "evidence":"Prior July audit: 4390 files, 74 missing nominal slots" if (year,month)==(2024,7) else "Directory existence only; no full-month content scan"})
    write_csv(OUT/"CROSS_SOURCE/himawari_month_directory_evidence.csv",months)
    oct_files=list((IMERG/"2025").glob("imerg_202510*.nc"))
    write_json(OUT/"CROSS_SOURCE/imerg_202510_targeted_presence.json",{"target_pattern":"2025/imerg_202510*.nc","files":[str(p) for p in oct_files],"count":len(oct_files),"status":"MISSING" if not oct_files else "NEEDS_REVIEW"})
    print(dumps({"boundary_values":values if False else "written separately","static":result["SRTM"],"IMERG_202510_count":len(oct_files)}),flush=True)

if __name__=="__main__":
    values=boundary();print(dumps(values),flush=True);static()
