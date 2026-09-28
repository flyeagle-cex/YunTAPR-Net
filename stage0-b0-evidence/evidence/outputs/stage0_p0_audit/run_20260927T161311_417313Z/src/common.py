"""UTC parsing, bounded read-only staging, exact coordinates, and safe output."""
from __future__ import annotations
from contextlib import contextmanager
from datetime import datetime,timezone
from pathlib import Path
import hashlib,json,logging,shutil,time,uuid,math
import numpy as np
import netCDF4,pandas as pd
from config import PROJECT,OUTPUT,CACHE,IMERG,HIMAWARI,CONFIG

def safe(value):
    if isinstance(value,dict):return {str(k):safe(v) for k,v in value.items()}
    if isinstance(value,(list,tuple)):return [safe(v) for v in value]
    if isinstance(value,np.ndarray):return safe(value.tolist())
    if isinstance(value,np.generic):return safe(value.item())
    if isinstance(value,float) and not math.isfinite(value):return str(value)
    if isinstance(value,(Path,datetime)):return str(value)
    return value
def dumps(value):return json.dumps(safe(value),ensure_ascii=False,allow_nan=False)

def output_path(path):
    p=Path(path).resolve()
    if not p.is_relative_to(OUTPUT.resolve()):raise ValueError(f"Output outside this audit: {p}")
    return p

def source_path(path):
    p=Path(path).resolve()
    if not any(p.is_relative_to(root.resolve()) for root in (IMERG,HIMAWARI)):
        raise ValueError(f"Source outside authorized roots: {p}")
    return p

def write_json(path,value):
    with output_path(path).open("x",encoding="utf-8") as f:f.write(dumps(value))
def write_text(path,text):
    with output_path(path).open("x",encoding="utf-8") as f:f.write(text)
def write_csv(path,rows,columns=None):
    p=output_path(path)
    if p.exists():raise FileExistsError(p)
    df=rows if isinstance(rows,pd.DataFrame) else pd.DataFrame(rows)
    if not len(df) and columns is not None:df=pd.DataFrame(columns=columns)
    df.to_csv(p,index=False,encoding="utf-8-sig")
def append_json(path,value):
    with output_path(path).open("a",encoding="utf-8") as f:f.write(dumps(value)+"\n")
def sha256(path):
    h=hashlib.sha256()
    with Path(path).open("rb") as f:
        for block in iter(lambda:f.read(1024*1024),b""):h.update(block)
    return h.hexdigest()
def utc_iso(value):
    return value.astimezone(timezone.utc).isoformat().replace("+00:00","Z") if value else None
def parse_iso_utc(value):
    if isinstance(value,bytes):value=value.decode("utf-8")
    dt=datetime.fromisoformat(str(value).strip().replace("Z","+00:00"))
    if dt.tzinfo is None:raise ValueError("ISO timestamp has no explicit UTC/offset")
    return dt.astimezone(timezone.utc)
def decode_cf_time(values,units,calendar="standard"):
    if not units:raise ValueError("Missing netCDF time units")
    array=np.asarray(values)
    if not np.isfinite(array).all():raise ValueError("Nonfinite encoded time")
    dates=netCDF4.num2date(array.reshape(-1),units,calendar=calendar,
                         only_use_cftime_datetimes=False,only_use_python_datetimes=True)
    # netCDF4 resolves the CF reference timezone. Returned naive datetimes express UTC.
    return [v.replace(tzinfo=timezone.utc) if v.tzinfo is None else v.astimezone(timezone.utc)
            for v in np.asarray(dates).reshape(-1)]

def coordinate_hash(values):
    a=np.asarray(values,dtype="<f8").copy()
    a[a==0]=0.0
    h=hashlib.sha256(str(a.shape).encode("ascii")+a.tobytes(order="C"))
    return h.hexdigest()
def coordinate_info(values):
    a=np.asarray(values);finite=bool(np.isfinite(a).all());d=np.diff(a.astype(np.float64))
    direction="ascending" if finite and len(d)>0 and np.all(d>0) else (
              "descending" if finite and len(d)>0 and np.all(d<0) else "non_monotonic")
    return {"count":int(a.size),"direction":direction,"min":float(np.min(a)) if finite and a.size else None,
            "max":float(np.max(a)) if finite and a.size else None,
            "mean_delta":float(d.mean()) if finite and len(d) else None,"finite":finite,
            "hash":coordinate_hash(a),"dtype":str(a.dtype)}

def attrs(variable):
    return {a:variable.getncattr(a) for a in variable.ncattrs()}

class Staging:
    """At most one active file. Cleanup can only target an exact file created by this instance."""
    def __init__(self,folder=CACHE,log=OUTPUT/"logs/staging_io.jsonl"):
        self.folder=Path(folder).resolve()
        if not self.folder.is_relative_to((PROJECT/"cache").resolve()):raise ValueError("Unsafe cache root")
        self.folder.mkdir(parents=True,exist_ok=True)
        self.log=Path(log);self.owned=set()
    @contextmanager
    def open(self,path,verify_hash=False):
        source=source_path(path);before=source.stat()
        existing=sum(p.stat().st_size for p in self.folder.glob("*.nc"))
        if existing+before.st_size>CONFIG["cache_limit_bytes"]:raise RuntimeError("Bounded cache capacity exceeded")
        if shutil.disk_usage(self.folder).free < before.st_size+CONFIG["cache_min_free_bytes"]:
            raise RuntimeError("Insufficient staging disk space")
        target=self.folder/(uuid.uuid4().hex+".nc")
        row={"source_path":str(source),"cache_path":str(target),"bytes":before.st_size,
             "copy_seconds":None,"read_seconds":None,"read_success":False,"size_match":False,
             "cleanup_success":False,"sha256_verified":False,"source_stat_unchanged":False,"error":""}
        ds=None;t_read=None
        try:
            tick=time.perf_counter()
            with source.open("rb") as src,target.open("xb") as dst:
                self.owned.add(target);shutil.copyfileobj(src,dst,1024*1024)
            row["copy_seconds"]=time.perf_counter()-tick
            row["size_match"]=target.stat().st_size==before.st_size
            if not row["size_match"]:raise IOError("Staging copy size mismatch")
            if verify_hash:
                row["source_sha256"]=sha256(source);row["cache_sha256"]=sha256(target)
                if row["source_sha256"]!=row["cache_sha256"]:raise IOError("Copy SHA256 mismatch")
                row["sha256_verified"]=True
            t_read=time.perf_counter()
            ds=netCDF4.Dataset(str(target),"r");ds.set_auto_maskandscale(False)
            yield ds
            row["read_success"]=True
        except Exception as e:
            row["error"]=f"{type(e).__name__}: {e}";raise
        finally:
            if ds is not None:ds.close()
            if t_read is not None:row["read_seconds"]=time.perf_counter()-t_read
            after=source.stat()
            row["source_stat_unchanged"]=(before.st_size, before.st_mtime_ns)==(after.st_size,after.st_mtime_ns)
            if target in self.owned:
                resolved=target.resolve()
                if resolved.parent!=self.folder or not resolved.is_relative_to((PROJECT/"cache").resolve()):
                    raise RuntimeError("Unsafe cache cleanup rejected")
                try:
                    target.unlink();self.owned.remove(target);row["cleanup_success"]=True
                except OSError as error:
                    row["cleanup_error"]=str(error);logging.warning("Cache cleanup failed: %s",error)
            append_json(self.log,row)
            if not row["source_stat_unchanged"]:raise RuntimeError(f"Source changed during read: {source}")
