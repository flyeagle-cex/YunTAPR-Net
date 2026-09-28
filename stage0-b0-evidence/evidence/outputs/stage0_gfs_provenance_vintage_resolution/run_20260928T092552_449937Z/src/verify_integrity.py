import json,sys,importlib.metadata as metadata,importlib
from datetime import datetime,timezone
from pathlib import Path
import pandas as pd
from config import *
from common import sha256,write_json,write_csv,dumps
sys.stdout.reconfigure(encoding='utf-8')
before=pd.read_csv(OUT/'logs/selected_raw_manifest_before.csv',keep_default_na=False);rows=[]
for r in before.to_dict('records'):
 p=Path(r['path']);s=p.stat();after=sha256(p);rows.append(dict(path=str(p),case_id=r['case_id'],branch=r['branch'],size_bytes=s.st_size,mtime_ns=s.st_mtime_ns,sha256_after=after,size_unchanged=s.st_size==r['size_bytes'],mtime_unchanged=s.st_mtime_ns==r['mtime_ns'],sha256_unchanged=after==r['sha256_before']))
write_csv(OUT/'logs/selected_raw_manifest_after.csv',rows)
artifacts=pd.read_csv(OUT/'PROVENANCE/local_artifact_inventory.csv',keep_default_na=False);ar=[]
for r in artifacts.to_dict('records'):
 p=Path(r['path']);s=p.stat();h=sha256(p);ar.append(dict(path=str(p),size_unchanged=s.st_size==r['size'],mtime_unchanged=s.st_mtime_ns==r['mtime_ns'],sha256_unchanged=h==r['sha256_before'],sha256_after=h))
write_csv(OUT/'logs/artifact_integrity_after.csv',ar)
base=json.loads((OUT/'logs/reused_baseline_hashes_before.json').read_text(encoding='utf8'));br=[dict(path=r['path'],sha256_before=r['sha256'],sha256_after=sha256(r['path'])) for r in base]
write_json(OUT/'logs/reused_baseline_hashes_after.json',br)
env=json.loads((OUT/'logs/environment_before.json').read_text(encoding='utf8'));packages={x.metadata['Name']:x.version for x in metadata.distributions()}
imports={}
for name in ['zarr','numcodecs','pyarrow','netCDF4','xarray','numpy','pandas','pytest','torch','h5netcdf']:
 m=importlib.import_module(name);imports[name]={'import':'PASS','version':str(getattr(m,'__version__',metadata.version(name)))}
write_json(OUT/'logs/environment_after.json',dict(python=sys.executable,packages=packages,verified_imports=imports,checked_utc=datetime.now(timezone.utc).isoformat(),dependency_changes=packages!=env['packages']))
staging=[json.loads(x) for x in (OUT/'logs/staging_io.jsonl').read_text(encoding='utf8').splitlines()];remaining=list(CACHE.iterdir())
ss=dict(copy_count=len(staging),copied_bytes=sum(x['bytes'] for x in staging),copy_seconds=sum(x['copy_seconds'] for x in staging),read_seconds=sum(x['read_seconds'] for x in staging),cleanup_failures=sum(not x['cleanup_success'] for x in staging),remaining_staged_bytes=sum(p.stat().st_size for p in remaining if p.is_file()),remaining_file_count=len(remaining),all_copy_sha256_verified=all(x['sha256_verified'] for x in staging),all_source_stat_unchanged=all(x['source_stat_unchanged'] for x in staging),all_reads_success=all(x['read_success'] for x in staging),max_single_temporary_bytes=max(x['bytes'] for x in staging),bounded_limit_bytes=CONFIG['cache_max_bytes'])
write_json(OUT/'logs/staging_summary.json',ss)
result=dict(selected_raw_files_checked=len(rows),all_selected_raw_unchanged=all(all(r[k] for k in ['size_unchanged','mtime_unchanged','sha256_unchanged']) for r in rows),historical_artifacts_checked=len(ar),all_historical_artifacts_unchanged=all(all(r[k] for k in ['size_unchanged','mtime_unchanged','sha256_unchanged']) for r in ar),explicit_baselines_checked=len(br),all_baseline_hashes_unchanged=all(r['sha256_before']==r['sha256_after'] for r in br),dependencies_unchanged=packages==env['packages'],fixed_interpreter=str(Path(sys.executable).resolve()).lower()==str(PYTHON.resolve()).lower(),raw_write_operations=0,full_raw_rescan=False,scope='40 selected raw files plus explicitly inventoried old text artifacts; not whole raw-disk hash verification',staging=ss)
write_json(OUT/'logs/integrity_verification.json',result)
assert all(result[k] for k in ['all_selected_raw_unchanged','all_historical_artifacts_unchanged','all_baseline_hashes_unchanged','dependencies_unchanged','fixed_interpreter'])
assert ss['cleanup_failures']==ss['remaining_staged_bytes']==ss['remaining_file_count']==0
# Tables retain CSV text exactly (nullable native semantics are explicitly encoded in status columns).
par=[]
for p in sorted(OUT.rglob('*.csv')):
 try:
  df=pd.read_csv(p,dtype=str,keep_default_na=False);q=p.with_suffix('.parquet')
  if q.exists():raise FileExistsError(q)
  df.to_parquet(q,engine='pyarrow',index=False);loaded=pd.read_parquet(q,engine='pyarrow');pd.testing.assert_frame_equal(df,loaded)
  par.append(dict(csv=str(p.relative_to(OUT)),parquet=str(q.relative_to(OUT)),rows=len(df),columns=len(df.columns),schema='all CSV fields preserved as strings; empty stays empty, no UNKNOWN->False coercion',status='PASS',error=''))
 except Exception as e:par.append(dict(csv=str(p.relative_to(OUT)),parquet=str(p.with_suffix('.parquet').relative_to(OUT)),status='FAIL',error=repr(e)));raise
write_csv(OUT/'logs/parquet_validation.csv',par)
p=pd.read_csv(OUT/'logs/parquet_validation.csv',dtype=str,keep_default_na=False);p.to_parquet(OUT/'logs/parquet_validation.parquet',engine='pyarrow',index=False)
print(dumps({'integrity':result,'csv_parquet_tables':len(par),'imports':imports}))
