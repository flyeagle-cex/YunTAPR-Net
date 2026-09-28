from pathlib import Path
from datetime import datetime,timezone
from contextlib import contextmanager
import json,hashlib,shutil,time,uuid
import numpy as np,pandas as pd
from config import *
def safe(v):
 if isinstance(v,dict):return {str(k):safe(x) for k,x in v.items()}
 if isinstance(v,(tuple,list)):return [safe(x) for x in v]
 if isinstance(v,np.ndarray):return safe(v.tolist())
 if isinstance(v,np.generic):return safe(v.item())
 if isinstance(v,Path):return str(v)
 if isinstance(v,float) and not np.isfinite(v):return str(v)
 return v
def writej(rel,value):
 p=OUT/rel;assert p.resolve().is_relative_to(OUT.resolve());p.write_text(json.dumps(safe(value),ensure_ascii=False,indent=2),encoding='utf8')
def readj(rel):return json.loads((OUT/rel).read_text(encoding='utf8'))
def md(rel,text):(OUT/rel).write_text(text.strip()+'\n',encoding='utf8')
def csv(rel,rows,columns=None):
 df=rows if isinstance(rows,pd.DataFrame) else pd.DataFrame(rows,columns=columns);df.to_csv(OUT/rel,index=False,encoding='utf-8-sig')
def hashfile(p):
 h=hashlib.sha256()
 with Path(p).open('rb') as f:
  for b in iter(lambda:f.read(1048576),b''):h.update(b)
 return h.hexdigest()
def coordhash(a):
 a=np.array(a,dtype='<f8');a[a==0]=0.;return hashlib.sha256(str(a.shape).encode()+a.tobytes()).hexdigest()
def protect(p,hash_sample=False):
 p=Path(p).resolve();records=readj('logs/input_protection_before.json') if (OUT/'logs/input_protection_before.json').exists() else {}
 if str(p) not in records:
  s=p.stat();records[str(p)]={'size':s.st_size,'mtime_ns':s.st_mtime_ns,'sha256':hashfile(p) if hash_sample else None};writej('logs/input_protection_before.json',records)
 return p
@contextmanager
def staging(p):
 p=protect(p);CACHE.mkdir(parents=True,exist_ok=True)
 assert p.stat().st_size<64*1024**2
 q=CACHE/(uuid.uuid4().hex+p.suffix);t=time.perf_counter();rec={'source':str(p),'temporary':str(q),'bytes':p.stat().st_size,'cleanup_success':False}
 try:
  with p.open('rb') as a,q.open('xb') as b:shutil.copyfileobj(a,b)
  rec['copy_seconds']=time.perf_counter()-t;assert q.stat().st_size==p.stat().st_size
  assert hashfile(p)==hashfile(q);rec['sha256_verified']=True
  yield q
 finally:
  assert q.resolve().parent==CACHE.resolve() and q.resolve().is_relative_to((PROJECT/'cache').resolve())
  try:q.unlink();rec['cleanup_success']=True
  except Exception as e:rec['cleanup_error']=repr(e)
  with (OUT/'logs/staging_io.jsonl').open('a',encoding='utf8') as f:f.write(json.dumps(rec)+'\n')
