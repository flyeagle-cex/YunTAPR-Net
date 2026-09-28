"""Packed, read-only 7-channel reader with bounded English staging."""
from __future__ import annotations
from contextlib import contextmanager
from pathlib import Path
import hashlib, logging, shutil, time, uuid
import netCDF4
import numpy as np
from config import CHANNELS, CONFIG, PROJECT
from common import sourcepath, outpath, append_json, jsonable, sha256

class MissingChannelError(ValueError): pass
class CoordinateShapeError(ValueError): pass
class MetadataError(ValueError): pass

class Staging:
    """Own one unique staging folder; never delete diagnostics or H-drive files."""
    def __init__(self, run_dir: Path):
        self.run_dir=Path(run_dir)
        self.folder=outpath(PROJECT/"cache/staging"/self.run_dir.name)
        self.folder.mkdir(parents=True,exist_ok=True)
        self.log=self.run_dir/"audit/staging_io.jsonl"
        self.created=set()
    @contextmanager
    def local(self,path:Path,verify_hash=False):
        source=sourcepath(path)
        size=source.stat().st_size
        retained=sum(p.stat().st_size for p in (PROJECT/"cache/staging").rglob("*.nc"))
        if retained+size>CONFIG["staging_max_bytes"]: raise RuntimeError("Bounded staging byte cap exceeded")
        if shutil.disk_usage(self.folder).free<size+CONFIG["min_disk_free_bytes"]:
            raise RuntimeError("Insufficient free space for bounded staging")
        target=outpath(self.folder/(uuid.uuid4().hex+".nc"))
        row={"source_path":str(source),"staging_path":str(target),"temporary_bytes":size,
             "copy_seconds":None,"read_seconds":None,"cleanup_success":False,
             "size_match":False,"sha256_verified":False,"error":""}
        success=False
        try:
            t=time.perf_counter()
            with source.open("rb") as src,target.open("xb") as dst:
                self.created.add(target)
                shutil.copyfileobj(src,dst,1024*1024)
            row["copy_seconds"]=time.perf_counter()-t
            row["size_match"]=target.stat().st_size==size
            if not row["size_match"]: raise IOError("Staging copy size mismatch")
            if verify_hash:
                if sha256(source)!=sha256(target):raise IOError("Staging SHA256 mismatch")
                row["sha256_verified"]=True
            t=time.perf_counter()
            try:
                yield target
                success=True
            finally: row["read_seconds"]=time.perf_counter()-t
        except Exception as error:
            row["error"]=f"{type(error).__name__}: {error}"
            raise
        finally:
            if success and target in self.created:
                # Resolve and constrain this exact owned file immediately before deletion.
                resolved=target.resolve()
                if resolved.parent!=self.folder.resolve() or resolved.drive.lower()!="f:":
                    raise RuntimeError("Unsafe staging cleanup rejected")
                try:
                    target.unlink()
                    self.created.remove(target)
                    row["cleanup_success"]=True
                except OSError as error:
                    row["cleanup_error"]=str(error)
                    logging.warning("Staging cleanup failed: %s",error)
            append_json(self.log,row)

def decode_packed(raw:np.ndarray, attrs:dict) -> tuple[np.ndarray,np.ndarray]:
    """Invalid packed observations remain NaN, never a valid zero or no-rain label."""
    required=("scale_factor","add_offset","valid_min","valid_max")
    missing=[k for k in required if k not in attrs]
    if missing:raise MetadataError(f"Missing packed metadata: {missing}")
    if not any(k in attrs for k in ("missing_value","_FillValue")):
        raise MetadataError("Missing both missing_value and _FillValue")
    if not np.isfinite(attrs["scale_factor"]) or not np.isfinite(attrs["add_offset"]):
        raise MetadataError("Nonfinite packed scale/offset")
    mask=np.isfinite(raw)&(raw>=attrs["valid_min"])&(raw<=attrs["valid_max"])
    for key in ("missing_value","_FillValue"):
        if key in attrs:
            for value in np.asarray(attrs[key]).reshape(-1):
                mask &= raw!=value
    with np.errstate(over="ignore",invalid="ignore"):
        x=raw.astype(np.float32)*np.float32(attrs["scale_factor"])+np.float32(attrs["add_offset"])
    mask &= np.isfinite(x)
    x[~mask]=np.nan
    return x.astype(np.float32,copy=False),mask.astype(bool,copy=False)

def _time(ds,name):
    if name in ds.variables:
        variable=ds[name]
        raw=variable[:]
        attrs={k:jsonable(variable.getncattr(k)) for k in variable.ncattrs()}
        data={"raw":jsonable(raw),"attrs":attrs,"iso":None,"parse_error":None}
        try:
            if raw.size!=1:raise ValueError("Time variable must contain one value")
            dt=netCDF4.num2date(raw.reshape(-1)[0],variable.units,
                               calendar=getattr(variable,"calendar","standard"),
                               only_use_cftime_datetimes=False)
            data["iso"]=dt.isoformat()+"Z"
        except Exception as error:data["parse_error"]=str(error)
        return data
    raw=getattr(ds,name,None)
    return {"raw":jsonable(raw),"attrs":{},"iso":str(raw) if raw is not None else None,
            "parse_error":None}

def _read_local(path:Path):
    """Internal entry point also supports tiny synthetic files for unit testing."""
    with netCDF4.Dataset(str(path),"r") as ds:
        ds.set_auto_maskandscale(False)
        missing=[c for c in CHANNELS if c not in ds.variables]
        if missing:raise MissingChannelError(f"Missing channels: {missing}")
        if "latitude" not in ds.variables or "longitude" not in ds.variables:
            raise CoordinateShapeError("Missing latitude/longitude")
        lat=np.asarray(ds["latitude"][:]).copy()
        lon=np.asarray(ds["longitude"][:]).copy()
        if lat.ndim!=1 or lon.ndim!=1:raise CoordinateShapeError("Expected 1-D coordinate arrays")
        attrs={k:jsonable(ds.getncattr(k)) for k in ds.ncattrs()}
        metadata={"global_attrs":attrs,"channels":{},"start_time":_time(ds,"start_time"),
                  "end_time":_time(ds,"end_time"),"date_created":attrs.get("date_created"),
                  "coordinate_attrs":{c:{a:jsonable(ds[c].getncattr(a)) for a in ds[c].ncattrs()}
                                      for c in ("latitude","longitude")}}
        arrays=[]; masks=[]
        for channel in CHANNELS:
            variable=ds[channel]
            if variable.shape!=(len(lat),len(lon)) or variable.dimensions!=("latitude","longitude"):
                raise CoordinateShapeError(f"{channel}: {variable.shape}, {variable.dimensions}")
            packed=variable[:]
            vat={a:variable.getncattr(a) for a in variable.ncattrs()}
            x,mask=decode_packed(packed,vat)
            arrays.append(x); masks.append(mask)
            metadata["channels"][channel]={"attrs":jsonable(vat),"packed_dtype":str(packed.dtype)}
        x=np.stack(arrays);mask=np.stack(masks)
        assert len(CHANNELS)==7 and x.shape==(7,len(lat),len(lon))
        assert x.dtype==np.float32 and mask.dtype==bool
        # Latitude order is an observed property, not something this reader should flip.
        return x,mask,lat,lon,metadata

def read_himawari_7ch(path:Path, staging:Staging, verify_hash=False):
    """Return float32 x, bool mask, latitude, longitude, metadata; propagate anomalies."""
    with staging.local(Path(path),verify_hash=verify_hash) as local:
        return _read_local(local)

def load_himawari_sequence(paths,staging:Staging,target_time=None,verify_hash=False):
    """Newest to oldest; no copying neighbouring observations and no future nominal frame."""
    from build_sequence_index import parse_filename, expected_times
    if len(paths)!=6:raise ValueError("Exactly six paths required")
    times=[parse_filename(Path(p).name)["time"] for p in paths]
    target=target_time or times[0]
    if any(t>target for t in times):raise AssertionError("Future nominal satellite frame")
    if times!=expected_times(target):raise AssertionError("History order or cadence mismatch")
    frames=[];masks=[];reference=None
    for p in paths:
        x,m,lat,lon,meta=read_himawari_7ch(p,staging,verify_hash=verify_hash)
        if reference is None:reference=(lat,lon,x.shape)
        elif (x.shape!=reference[2] or not np.array_equal(lat,reference[0]) or
              not np.array_equal(lon,reference[1])):
            raise CoordinateShapeError("Sequence grids differ; no resampling/flip allowed")
        frames.append(x);masks.append(m)
    result=np.stack(frames);mask=np.stack(masks)
    assert result.shape[:2]==(6,7) and mask.shape==result.shape and mask.dtype==bool
    return result,mask
