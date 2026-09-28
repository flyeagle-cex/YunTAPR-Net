"""Read-only monthly scan, never assume expected file count."""
from pathlib import Path
import pandas as pd
from config import RAW
from common import sourcepath

def scan_files(year:int,month:int)->tuple[list[Path],pd.DataFrame]:
    paths=sorted((RAW/f"{year:04d}{month:02d}").rglob("*.nc"))
    rows=[]
    for p in paths:
        sourcepath(p,year,month);s=p.stat()
        rows.append(dict(relative_path=str(p.relative_to(RAW)),filename=p.name,size_bytes=s.st_size,mtime_ns=s.st_mtime_ns))
    return paths,pd.DataFrame(rows)
