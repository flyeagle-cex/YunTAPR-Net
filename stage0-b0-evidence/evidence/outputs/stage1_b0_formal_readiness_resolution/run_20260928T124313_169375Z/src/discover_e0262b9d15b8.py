"""Researcher-authorized volume-wide NAME discovery; no scientific array scan."""
from pathlib import Path
from datetime import datetime,timezone
from concurrent.futures import ThreadPoolExecutor
import os,json,csv,time,threading

ROOT=Path(r'F:\pytorch\Research\outputs\stage1_b0_formal_readiness_resolution')
SKIP={'$recycle.bin','system volume information','windows','program files','program files (x86)','.git','.venv','venv','node_modules','site-packages','__pycache__'}
LOCK=threading.Lock()
def scan(drive,run):
 stack=[Path(drive)];rows=[];skipped=[];errors=[];dirs=files=0;started=time.time()
 while stack:
  p=stack.pop()
  try:
   with os.scandir(p) as it:
    dirs+=1
    for e in it:
     low=e.name.lower();ep=Path(e.path)
     try:
      if e.is_dir(follow_symlinks=False):
       if low in SKIP:skipped.append({'path':str(ep),'reason':'SYSTEM_OR_DEPENDENCY_DIRECTORY'});continue
       if ep.is_relative_to(run):continue
       if e.is_symlink() or (hasattr(e,'is_junction') and e.is_junction()):skipped.append({'path':str(ep),'reason':'REPARSE_NO_RECURSION'});continue
       if 'imerg' in low or 'imerge' in low:rows.append({'path':str(ep),'kind':'IMERG_DIRECTORY','size_bytes':''})
       stack.append(ep)
      elif e.is_file(follow_symlinks=False):
       files+=1;suffix=ep.suffix.lower();kind=None
       related='imerg' in low or 'imerge' in low or '3b-hhr' in low or '3imerghh' in low
       if related and ('202510' in low or '2025-10' in low):kind='OCTOBER_2025_NAME_MATCH'
       elif related and suffix in {'.zip','.gz','.tar','.7z','.rar'}:kind='IMERG_ARCHIVE'
       elif suffix in {'.py','.ps1','.ipynb','.bat','.sh'} and (related or any(x in low for x in ['download','convert','harmony','yuntapr','precip'])):kind='SCRIPT_NAME_CANDIDATE'
       elif related and suffix in {'.json','.jsonl','.csv','.md','.txt','.pdf','.log'}:kind='LOCAL_DOCUMENT_OR_MANIFEST'
       elif ('3b-hhr' in low or '3imerghh' in low) and suffix in {'.h5','.hdf5','.hdf','.nc4','.nc'}:kind='NATIVE_GRANULE_NAME'
       if kind:rows.append({'path':str(ep),'kind':kind,'size_bytes':e.stat(follow_symlinks=False).st_size})
     except (OSError,PermissionError) as ex:errors.append({'path':str(ep),'error':str(ex)})
  except (OSError,PermissionError) as ex:errors.append({'path':str(p),'error':str(ex)})
  if dirs%2000==0:
   with LOCK:
    with (run/'logs/discovery_progress.jsonl').open('a',encoding='utf-8') as f:f.write(json.dumps({'drive':drive,'directories':dirs,'files_names_seen':files,'elapsed_seconds':time.time()-started})+'\n')
 result={'drive':drive,'directories':dirs,'files_names_seen':files,'matched_names':len(rows),'elapsed_seconds':time.time()-started,'errors':errors,'skipped':skipped,'raw_array_reads':0}
 (run/'logs'/('volume_'+drive[0]+'.json')).write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
 return rows,result

if __name__=='__main__':
 run=ROOT/('run_'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S_%fZ'));(run/'logs').mkdir(parents=True,exist_ok=False)
 (run/'DISCOVERY').mkdir();(run/'src').mkdir()
 (run/'src/discover.py').write_text(Path(__file__).read_text(encoding='utf-8'),encoding='utf-8')
 print('RUN='+str(run),flush=True)
 drives=[x+':\\' for x in 'CDEFGH' if Path(x+':\\').exists()]
 (run/'logs/discovery_authorization.json').write_text(json.dumps({'user_reply':'有，你扩大到全盘搜索吧','drives':drives,'scope':'File/directory NAME discovery only; no full raw data audit; skip documented OS/dependency folders and reparse recursion; no downloads','skip_names':sorted(SKIP)},ensure_ascii=False,indent=2),encoding='utf-8')
 with ThreadPoolExecutor(max_workers=3) as pool:results=list(pool.map(lambda d:scan(d,run),drives))
 rows=[r for group,_ in results for r in group]
 with (run/'DISCOVERY/file_name_candidates.csv').open('w',encoding='utf-8',newline='') as f:
  w=csv.DictWriter(f,fieldnames=['path','kind','size_bytes']);w.writeheader();w.writerows(rows)
 summary={'run':str(run),'drives':drives,'matched_names':len(rows),'directories':sum(x['directories'] for _,x in results),'files_names_seen':sum(x['files_names_seen'] for _,x in results),'access_errors':sum(len(x['errors']) for _,x in results),'skipped_directories':sum(len(x['skipped']) for _,x in results),'native_named_files':sum(r['kind']=='NATIVE_GRANULE_NAME' for r in rows),'october_name_matches':[r for r in rows if r['kind']=='OCTOBER_2025_NAME_MATCH']}
 (run/'logs/discovery_summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
 print(json.dumps(summary,ensure_ascii=False),flush=True)
