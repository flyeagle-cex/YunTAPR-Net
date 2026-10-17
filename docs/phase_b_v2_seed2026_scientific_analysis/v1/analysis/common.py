"""Fixed published sources, strict no-raw-data analysis paths."""
from pathlib import Path
import csv,hashlib,json,math
ROOT=Path(__file__).absolute().parents[4]
OUT=ROOT/'docs/phase_b_v2_seed2026_scientific_analysis/v1'
FORMAL=ROOT/'docs/phase_b_v2_formal_execution'
RUNS=[('B0','E0','seed2026_v2','B0_MATCHED_V2__E0__s2026'),('B1','E0','seed2026_v2','B1_V2__E0__s2026'),
      ('B0','E1','seed2026_v2','B0_MATCHED_V2__E1__s2026'),('B1','E1','seed2026_operator_v3','B1_V2__E1__s2026'),
      ('B0','E2','seed2026_operator_v3','B0_MATCHED_V2__E2__s2026'),('B1','E2','seed2026_operator_v3','B1_V2__E2__s2026')]
def read(path):return json.loads(path.read_bytes())
def sha(raw):return hashlib.sha256(raw).hexdigest()
def digest(v):return sha(json.dumps(v,sort_keys=True,separators=(',',':'),allow_nan=False).encode())
def save(name,value):
 p=OUT/name;p.parent.mkdir(parents=True,exist_ok=True)
 p.write_bytes((json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False)+'\n').encode())
def table(name,rows):
 p=OUT/'tables'/name;p.parent.mkdir(exist_ok=True)
 with p.open('w',encoding='utf-8',newline='') as f:
  w=csv.DictWriter(f,fieldnames=list(rows[0]),lineterminator='\n');w.writeheader();w.writerows(rows)
def load():return {(m,a):read(FORMAL/f/(r+'.json')) for m,a,f,r in RUNS}
def close(a,b,tol=2e-12):
 if not math.isclose(a,b,rel_tol=tol,abs_tol=tol):raise ValueError(f'NUMERICAL_IDENTITY: {a} != {b}')
