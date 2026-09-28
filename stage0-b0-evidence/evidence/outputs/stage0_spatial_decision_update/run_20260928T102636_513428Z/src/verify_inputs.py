import sys,json,importlib.metadata as metadata
from pathlib import Path
import pandas as pd
from config import *
from frozen_contract import sha,verify_frozen
sys.stdout.reconfigure(encoding='utf8')
before=json.loads((OUT/'logs/input_protection_before.json').read_text(encoding='utf8'));rows=[]
for path,r in before.items():
 p=Path(path);s=p.stat();h=sha(p) if r['sha256'] is not None else None
 rows.append({'path':path,'size_unchanged':s.st_size==r['size'],'mtime_unchanged':s.st_mtime_ns==r['mtime_ns'],'sha256_status':'PASS' if h is not None and h==r['sha256'] else 'NOT_SAMPLED' if h is None else 'FAIL','sha256_after':h or ''})
pd.DataFrame(rows).to_csv(OUT/'logs/input_integrity_after.csv',index=False,encoding='utf-8-sig')
packages={d.metadata['Name']:d.version for d in metadata.distributions()};env=json.loads((OUT/'logs/environment_before.json').read_text(encoding='utf8'));assert packages==env['packages']
result={'registered_inputs':len(rows),'all_size_mtime_unchanged':all(r['size_unchanged'] and r['mtime_unchanged'] for r in rows),'sha256_checked':sum(r['sha256_status']!='NOT_SAMPLED' for r in rows),'sha256_all_checked_unchanged':all(r['sha256_status']!='FAIL' for r in rows),'dependencies_unchanged':True,'raw_data_modified':False,'old_runs_modified':False,'scope':'237 SRTM files stat-checked against prior audit; sampled DEM hashes plus all adopted boundary/grid/candidate/code evidence hashes; no full DEM payload rescan','limitation':'size/mtime verification is not full content hash proof.','frozen_artifact_check':verify_frozen(OUT)}
assert result['all_size_mtime_unchanged'] and result['sha256_all_checked_unchanged']
(OUT/'logs/integrity_summary.json').write_text(json.dumps(result,indent=2),encoding='utf8')
(OUT/'logs/environment_after.json').write_text(json.dumps({'python':sys.executable,'packages':packages},indent=2),encoding='utf8')
print(json.dumps(result))
