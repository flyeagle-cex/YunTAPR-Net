"""Read-only raw access and independently owned English staging."""
from pathlib import Path
from contextlib import contextmanager
from datetime import datetime,timezone
import hashlib,json,math,shutil,time,uuid,logging
import numpy as np,pandas as pd,netCDF4
from config import OUT,CACHE,PROJECT,GFS,IMERG,CONFIG

def safe(v):
    if isinstance(v,dict):return {str(k):safe(x) for k,x in v.items()}
    if isinstance(v,(list,tuple)):return [safe(x) for x in v]
    if isinstance(v,np.ndarray):return safe(v.tolist())
    if isinstance(v,np.generic):return safe(v.item())
    if isinstance(v,float) and not math.isfinite(v):return str(v)
    if isinstance(v,(Path,datetime)):return str(v)
    return v
def dumps(v):return json.dumps(safe(v),ensure_ascii=False,allow_nan=False)
def output_path(p):
    p=Path(p).resolve()
    if not p.is_relative_to(OUT.resolve()):raise ValueError("Output must remain in new run directory")
    return p
def source_path(p):
    p=Path(p).resolve()
    allowed=p.is_relative_to(GFS.resolve()) or p in {(IMERG/relative).resolve() for relative in CONFIG["boundary_files"]}
    if not allowed:raise ValueError(f"Source outside active read scope: {p}")
    return p
def write_text(p,text):
    with output_path(p).open("x",encoding="utf-8") as f:f.write(text)
def write_json(p,value):write_text(p,dumps(value))
def append_json(p,value):
    with output_path(p).open("a",encoding="utf-8") as f:f.write(dumps(value)+"\n")
def write_csv(p,rows,columns=None):
    p=output_path(p)
    if p.exists():raise FileExistsError(p)
    df=rows if isinstance(rows,pd.DataFrame) else pd.DataFrame(rows)
    if not len(df) and columns is not None:df=pd.DataFrame(columns=columns)
    df.to_csv(p,index=False,encoding="utf-8-sig")
def attrs(v):return {k:v.getncattr(k) for k in v.ncattrs()}
def sha256(path):
    h=hashlib.sha256()
    with Path(path).open("rb") as f:
        for part in iter(lambda:f.read(1024*1024),b""):h.update(part)
    return h.hexdigest()
def iso(t):return t.astimezone(timezone.utc).isoformat().replace("+00:00","Z") if t else None
def parse_iso(s):
    d=datetime.fromisoformat(str(s).replace("Z","+00:00"))
    if d.tzinfo is None:raise ValueError("UTC/offset required")
    return d.astimezone(timezone.utc)
def decode_cf(raw,units,calendar="standard"):
    if not units:raise ValueError("Missing CF time units")
    a=np.asarray(raw)
    if not np.isfinite(a).all():raise ValueError("Nonfinite time")
    values=netCDF4.num2date(a.reshape(-1),units,calendar=calendar,
        only_use_cftime_datetimes=False,only_use_python_datetimes=True)
    return [v.replace(tzinfo=timezone.utc) if v.tzinfo is None else v.astimezone(timezone.utc) for v in values]
def coord_hash(values):
    a=np.asarray(values,dtype="<f8").copy();a[a==0]=0
    return hashlib.sha256(str(a.shape).encode()+a.tobytes()).hexdigest()
def coord_info(a):
    a=np.asarray(a)
    if a.ndim!=1 or not np.isfinite(a).all():raise ValueError("Nonfinite/non-1D coordinates")
    delta=np.diff(a.astype(float))
    direction="ascending" if np.all(delta>0) else "descending" if np.all(delta<0) else "non_monotonic"
    return dict(count=len(a),minimum=float(a.min()),maximum=float(a.max()),direction=direction,
                resolution=float(np.median(np.abs(delta))) if len(delta) else None,hash=coord_hash(a))
def format_signature(path):
    with Path(path).open("rb") as f:head=f.read(8)
    if head.startswith(b"GRIB"):return "GRIB"+str(head[7])
    if head.startswith(b"\x89HDF"):return "NetCDF/HDF5"
    if head.startswith(b"CDF"):return "NetCDF/classic"
    return "OTHER"

class Reader:
    def __init__(self):
        CACHE.mkdir(parents=True,exist_ok=True);self.created=set()
    @contextmanager
    def open(self,path,hash_check=False):
        p=source_path(path);before=p.stat()
        if sum(q.stat().st_size for q in CACHE.glob("*.nc"))+before.st_size>CONFIG["cache_max_bytes"]:
            raise RuntimeError("Staging byte limit exceeded")
        if shutil.disk_usage(CACHE).free<before.st_size+CONFIG["minimum_free_bytes"]:raise RuntimeError("Low staging disk space")
        local=CACHE/(uuid.uuid4().hex+".nc")
        record={"source_path":str(p),"cache_path":str(local),"bytes":before.st_size,"copy_seconds":None,
                "read_seconds":None,"cleanup_success":False,"read_success":False,"sha256_verified":False,"error":""}
        ds=None;tick_read=None
        try:
            tick=time.perf_counter()
            with p.open("rb") as a,local.open("xb") as b:
                self.created.add(local);shutil.copyfileobj(a,b,1024*1024)
            record["copy_seconds"]=time.perf_counter()-tick
            if local.stat().st_size!=before.st_size:raise IOError("Copy size mismatch")
            if hash_check:
                record["source_sha256"]=sha256(p)
                if record["source_sha256"]!=sha256(local):raise IOError("Copy hash mismatch")
                record["sha256_verified"]=True
            tick_read=time.perf_counter();ds=netCDF4.Dataset(str(local),"r");ds.set_auto_maskandscale(False)
            yield ds
            record["read_success"]=True
        except Exception as e:record["error"]=f"{type(e).__name__}: {e}";raise
        finally:
            if ds is not None:ds.close()
            if tick_read is not None:record["read_seconds"]=time.perf_counter()-tick_read
            after=p.stat();record["source_stat_unchanged"]=(before.st_size,before.st_mtime_ns)==(after.st_size,after.st_mtime_ns)
            if local in self.created:
                if local.resolve().parent!=CACHE.resolve() or not local.resolve().is_relative_to((PROJECT/"cache").resolve()):
                    raise RuntimeError("Unsafe cleanup refused")
                try:local.unlink();self.created.remove(local);record["cleanup_success"]=True
                except OSError as e:record["cleanup_error"]=str(e);logging.warning("Cleanup failed %s",e)
            append_json(OUT/"logs/staging_io.jsonl",record)
            if not record["source_stat_unchanged"]:raise RuntimeError("Source changed during read")
