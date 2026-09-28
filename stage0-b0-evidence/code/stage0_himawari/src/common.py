"""Safe output, source scope, process-memory measurement, and serialization."""
from __future__ import annotations
import csv, ctypes, hashlib, json, os, threading, time
from pathlib import Path
from datetime import datetime, timezone
import numpy as np
import pandas as pd
from config import PROJECT, RAW, CONFIG

def jsonable(value):
    if isinstance(value, dict): return {str(k):jsonable(v) for k,v in value.items()}
    if isinstance(value,(list,tuple)): return [jsonable(v) for v in value]
    if isinstance(value,np.ndarray): return value.tolist()
    if isinstance(value,np.generic): return value.item()
    if isinstance(value,(Path,datetime)): return str(value)
    return value

def dumps(value): return json.dumps(jsonable(value),ensure_ascii=False,allow_nan=False)

def outpath(path: Path) -> Path:
    path=Path(path).resolve()
    if not path.is_relative_to(PROJECT.resolve()): raise ValueError(f"Output outside project: {path}")
    return path

def sourcepath(path: Path, year=2024, month=7) -> Path:
    path=Path(path).resolve()
    root=RAW.resolve()
    if not path.is_relative_to(root): raise ValueError("Raw source outside authorized H root")
    relative=path.relative_to(root)
    current=f"{year:04d}{month:02d}"
    from datetime import timedelta
    previous=datetime(year,month,1)-timedelta(days=1)
    allowed_previous=(relative.parts[0]==previous.strftime("%Y%m") and
                      len(relative.parts)>2 and relative.parts[1]==previous.strftime("%d"))
    if relative.parts[0]!=current and not allowed_previous: raise ValueError("Source outside month/boundary day")
    return path

def write_json(path,value):
    with outpath(path).open("x",encoding="utf-8") as f:f.write(dumps(value))

def write_text(path,text):
    with outpath(path).open("x",encoding="utf-8") as f:f.write(text)

def write_table(frame: pd.DataFrame, path: Path, parquet=False):
    path=outpath(path)
    if path.exists(): raise FileExistsError(path)
    frame.to_csv(path,index=False,encoding="utf-8-sig")
    if parquet:
        other=path.with_suffix(".parquet")
        if other.exists(): raise FileExistsError(other)
        # No alternate engine or dependency fallback.
        frame.to_parquet(other,engine="pyarrow",index=False)
        check=pd.read_parquet(other,engine="pyarrow")
        assert list(check.columns)==list(frame.columns) and len(check)==len(frame)

def append_json(path,value):
    with outpath(path).open("a",encoding="utf-8") as f:f.write(dumps(value)+"\n")

def sha256(path):
    h=hashlib.sha256()
    with Path(path).open("rb") as f:
        for b in iter(lambda:f.read(1024*1024),b""):h.update(b)
    return h.hexdigest()

class _Memory(ctypes.Structure):
    _fields_=[("cb",ctypes.c_ulong),("PageFaultCount",ctypes.c_ulong),
              ("PeakWorkingSetSize",ctypes.c_size_t),("WorkingSetSize",ctypes.c_size_t),
              ("QuotaPeakPagedPoolUsage",ctypes.c_size_t),("QuotaPagedPoolUsage",ctypes.c_size_t),
              ("QuotaPeakNonPagedPoolUsage",ctypes.c_size_t),("QuotaNonPagedPoolUsage",ctypes.c_size_t),
              ("PagefileUsage",ctypes.c_size_t),("PeakPagefileUsage",ctypes.c_size_t)]

def memory_bytes():
    info=_Memory();info.cb=ctypes.sizeof(info)
    kernel=ctypes.WinDLL("kernel32",use_last_error=True)
    kernel.GetCurrentProcess.restype=ctypes.c_void_p
    psapi=ctypes.WinDLL("psapi",use_last_error=True)
    psapi.GetProcessMemoryInfo.argtypes=[ctypes.c_void_p,ctypes.POINTER(_Memory),ctypes.c_ulong]
    if not psapi.GetProcessMemoryInfo(kernel.GetCurrentProcess(),ctypes.byref(info),info.cb):
        raise ctypes.WinError(ctypes.get_last_error())
    return int(info.WorkingSetSize),int(info.PeakWorkingSetSize)

class MemoryMonitor:
    """10-ms sampled working set, plus Windows process-lifetime high-water mark."""
    def __enter__(self):
        self.baseline,self.process_peak=memory_bytes();self.peak=self.baseline
        self.stop=threading.Event()
        def sample():
            while not self.stop.wait(CONFIG["memory_sample_interval_seconds"]):
                current,peak=memory_bytes();self.peak=max(self.peak,current);self.process_peak=max(self.process_peak,peak)
        self.thread=threading.Thread(target=sample,daemon=True);self.thread.start()
        return self
    def __exit__(self,*args):
        self.stop.set();self.thread.join()
        current,peak=memory_bytes();self.peak=max(self.peak,current);self.process_peak=max(self.process_peak,peak)
    def report(self):
        return {"memory_peak_mb":self.peak/2**20,"memory_baseline_mb":self.baseline/2**20,
                "memory_delta_mb":(self.peak-self.baseline)/2**20,
                "process_lifetime_peak_mb":self.process_peak/2**20}
