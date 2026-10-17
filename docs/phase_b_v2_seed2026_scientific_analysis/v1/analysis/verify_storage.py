"""SHA-only six-LAST audit and bounded volume-wide backup filename search.

No torch import/deserialization. Directory enumeration requests NAMES ONLY;
forbidden 2025 names are discarded BEFORE any child attribute/open operation.
Only the six exact run identities/expected hashes qualify for payload hashing.
"""
from __future__ import annotations
import ctypes as C
from ctypes import wintypes as W
from datetime import datetime,timezone
import hashlib,json,ntpath,os,struct,sys,time
from pathlib import Path
from common import ROOT,OUT,FORMAL,RUNS,load,save,sha
sys.path.insert(0,str(ROOT/'src'))
from yuntapr.experimental.phase_b_v2_full_payload_integrity.winio import ReadHandle,K,info,final_name
K.GetFileAttributesW.argtypes=[W.LPCWSTR];K.GetFileAttributesW.restype=W.DWORD
K.GetLogicalDrives.restype=W.DWORD
N=C.WinDLL('ntdll');N.NtQueryDirectoryFile.restype=C.c_long
N.NtQueryDirectoryFile.argtypes=[W.HANDLE,C.c_void_p,C.c_void_p,C.c_void_p,C.c_void_p,C.c_void_p,W.ULONG,C.c_int,W.BOOLEAN,C.c_void_p,W.BOOLEAN]
class IOStatus(C.Structure):_fields_=[('status',C.c_void_p),('information',C.c_size_t)]
EXCLUDE={'windows','program files','program files (x86)','programdata','appdata','$recycle.bin','system volume information',
         'node_modules','.git','.cache','cache','site-packages','.venv','.venv-cuda','venv','__pycache__','recovery','windows.old'}
MAX_SECONDS=600;MAX_DIRS=120000;MAX_NAMES=2000000
def lexical(text):
 parts=text.replace('/','\\').split('\\')
 if not ntpath.isabs(text) or text.startswith('\\\\') or text.count(':')!=1 or any(x in ('.','..') or '2025' in x for x in parts):
  raise PermissionError('LEXICAL_SCOPE_BEFORE_NATIVE_ACCESS')
def names(directory):
 lexical(directory)
 h=K.CreateFileW(directory,0x81,7,None,3,0x02000000|0x00200000,None)
 if h==C.c_void_p(-1).value:raise C.WinError(C.get_last_error())
 try:
  if os.path.normcase(final_name(h))!=os.path.normcase(directory) or info(h)['attributes']&0x400:raise PermissionError('DIRECTORY_IDENTITY')
  first=True;buf=C.create_string_buffer(131072)
  while True:
   io=IOStatus();status=N.NtQueryDirectoryFile(h,None,None,None,C.byref(io),buf,len(buf),12,False,None,first)&0xffffffff;first=False
   if status==0x80000006:return
   if status not in (0,0x80000005):raise OSError('NT_DIRECTORY_STATUS_'+hex(status))
   raw=buf.raw[:io.information];offset=0
   while offset+12<=len(raw):
    nxt,index,size=struct.unpack_from('<III',raw,offset)
    yield raw[offset+12:offset+12+size].decode('utf-16-le')
    if not nxt:break
    offset+=nxt
 finally:K.CloseHandle(h)
def hash_payload(path,expected,size):
 lexical(str(path));parents=[];start=time.perf_counter()
 try:
  chain=list(path.parents);chain.reverse()
  for p in chain:
   lexical(str(p));h=ReadHandle(str(p),directory=True);parents.append(h)
   if os.path.normcase(h.final_path)!=os.path.normcase(str(p)):raise ValueError('PAYLOAD_PARENT_IDENTITY')
  with ReadHandle(str(path),payload=True) as h:
   if os.path.normcase(h.final_path)!=os.path.normcase(str(path)) or h.before['size']!=size:raise ValueError('PAYLOAD_IDENTITY_SIZE')
   digest=hashlib.sha256();count=0;buf=bytearray(4*1024**2)
   while n:=h.readinto(buf):digest.update(memoryview(buf)[:n]);count+=n
   if h.snapshot()!=h.before or count!=size:raise ValueError('PAYLOAD_CHANGED')
   actual=digest.hexdigest()
   return dict(path_key=sha(os.path.normcase(str(path)).encode()),bytes=count,expected_sha256=expected,actual_sha256=actual,
    status='PASS' if actual==expected else 'SHA_MISMATCH',volume=h.before['volume'],file_index=h.before['file_index'],
    elapsed_seconds=time.perf_counter()-start,handle_metadata_stable=True)
 finally:
  for h in reversed(parents):h.close()
def main():
 private=OUT/'.local';private.mkdir(parents=True,exist_ok=True)
 results=load();primary=[];expected={};primary_paths=set()
 for model,arm,folder,run in RUNS:
  cp=results[(model,arm)]['epochs'][-1]['checkpoint'];path=FORMAL/folder/'.local'/run/'checkpoints/LAST_epoch_09.pt'
  root=path.parent;ref=root/cp['reference_name'];registration=root/'LAST_epoch_09.registration.json'
  if sha(ref.read_bytes())!=cp['receipt_sha256']:raise ValueError('LAST_REFERENCE_SHA')
  r=json.loads(ref.read_bytes());reg=json.loads(registration.read_bytes())
  if r['sha256']!=cp['payload_sha256'] or reg['payload_sha256']!=cp['payload_sha256']:raise ValueError('LAST_REGISTRY_SHA')
  if '--search-only' in sys.argv:
   prior=json.loads((OUT/'CHECKPOINT_PAYLOAD_AUDIT.json').read_bytes())
   row=next(r for r in prior['primary'] if r['run_id']==run)
  else:
   row=hash_payload(path,cp['payload_sha256'],cp['bytes']);row.update(run_id=run,receipt_sha256=cp['receipt_sha256'])
  primary.append(row);expected[run]=(cp['payload_sha256'],cp['bytes']);primary_paths.add(os.path.normcase(str(path)))
  if '--search-only' not in sys.argv:save('CHECKPOINT_PAYLOAD_AUDIT.json',dict(primary=primary,complete=False,torch_loaded=False))
  if row['status']!='PASS':raise ValueError('PRIMARY_SHA_MISMATCH_STOP')
 mask=K.GetLogicalDrives();drives=[chr(65+i)+':\\' for i in range(26) if mask&(1<<i)]
 start=time.monotonic();stacks={d:[d] for d in drives};turn=0;per_drive={d[:2]:0 for d in drives};candidates=[];errors=[];directories=entries=forbidden=pruned=reparse=0;truncated=False
 while any(stacks.values()):
  if time.monotonic()-start>MAX_SECONDS or directories>=MAX_DIRS or entries>=MAX_NAMES:truncated=True;break
  drive=drives[turn%len(drives)];turn+=1
  if not stacks[drive]:continue
  directory=stacks[drive].pop();per_drive[drive[:2]]+=1
  try:
   for name in names(directory):
    entries+=1
    if name in ('.','..'):continue
    if '2025' in name:forbidden+=1;continue
    if name.lower() in EXCLUDE:pruned+=1;continue
    text=ntpath.join(directory,name);lexical(text)
    attr=K.GetFileAttributesW(text)
    if attr==0xffffffff:continue
    if attr&0x400:reparse+=1;continue
    if attr&0x10:stacks[drive].append(text);continue
    if not name.lower().endswith(('.pt','.pth','.ckpt')):continue
    matched=next((run for run,(s,size) in expected.items() if run.lower() in text.lower() or s in name.lower()),None)
    if matched and (name=='LAST_epoch_09.pt' or expected[matched][0] in name.lower()) and os.path.normcase(text) not in primary_paths:
     candidates.append(dict(path=text,run_id=matched))
    if entries>=MAX_NAMES or time.monotonic()-start>MAX_SECONDS:truncated=True;break
   directories+=1
  except OSError as e:
   if len(errors)<100:errors.append(dict(path_key=sha(directory.encode()),error_type=type(e).__name__,code=getattr(e,'winerror',None)))
  if truncated:break
 (private/'backup_candidates.json').write_text(json.dumps(candidates,ensure_ascii=False,indent=2),encoding='utf-8')
 backups=[]
 for c in candidates:
  s,size=expected[c['run_id']]
  try:r=hash_payload(Path(c['path']),s,size)
  except (OSError,ValueError) as e:r=dict(path_key=sha(c['path'].encode()),status='NOT_VERIFIED',reason=type(e).__name__)
  r['run_id']=c['run_id'];backups.append(r)
 public=dict(status='PRIMARY_SIX_PAYLOAD_SHA_PASS',audit_utc=datetime.now(timezone.utc).isoformat(),primary=primary,
  total_primary_bytes=sum(r['bytes'] for r in primary),backups=backups,backup_coverage=[run for run in expected if any(b['run_id']==run and b['status']=='PASS' and (b['volume'],b['file_index'])!=(p['volume'],p['file_index']) for b in backups for p in primary if p['run_id']==run)],
  search=dict(drives=[d[:2] for d in drives],directories=directories,entries=entries,forbidden_2025_names_rejected_before_attributes=forbidden,
   excluded_system_cache_directories=pruned,reparse_points_not_followed=reparse,errors=errors,limited=truncated,remaining_directory_count=sum(map(len,stacks.values())),directory_visits_by_drive=per_drive,
   elapsed_seconds=time.monotonic()-start,max_seconds=MAX_SECONDS,max_directories=MAX_DIRS,max_names=MAX_NAMES,enumeration='NT_FileNamesInformation_NO_ATTRIBUTES_FOR_FORBIDDEN_NAMES'),
  no_deserialization=True,optimizer_steps=0,pixels_2025_read=0,active_2025_child_attribute_queries=0,
  historical_2025_path_attribute_access='NOT_INSTRUMENTED',independent_offline_backup='NOT_VERIFIED')
 save('CHECKPOINT_PAYLOAD_AUDIT.json',public);print(json.dumps(dict(status=public['status'],backups=len(backups),backup_coverage=public['backup_coverage'],search=public['search']),ensure_ascii=False))
if __name__=='__main__':main()
