"""One bounded diagnostic of the exact B8 WinError121 source; no retries."""
import argparse,ctypes,hashlib,json,os,subprocess,sys,time
from datetime import datetime,timezone
from pathlib import Path

BASENAME='NC_H09_20231025_2300_R21_FLDK.06001_06001.nc'

CHILD=r'''
import ctypes,hashlib,json,os,sys
from pathlib import Path
p=Path(sys.argv[1]);op=sys.argv[2]
try:
 if op=='volume':
  k=ctypes.windll.kernel32;root=p.anchor;fs=ctypes.create_unicode_buffer(256);device=ctypes.create_unicode_buffer(2048)
  drive_type=k.GetDriveTypeW(root)
  ok=k.GetVolumeInformationW(root,None,0,None,None,None,fs,256)
  q=k.QueryDosDeviceW(p.drive,device,2048)
  category='REMOTE_DEVICE' if q and ('Mup' in device.value or 'LanmanRedirector' in device.value) else 'LOCAL_DISK_DEVICE' if q and 'Harddisk' in device.value else 'OTHER_OR_UNKNOWN'
  result=dict(drive_type=drive_type,filesystem=fs.value if ok else None,volume_query_ok=bool(ok),device_category=category)
 elif op=='stat':
  s=p.stat();result=dict(bytes=s.st_size,mtime_ns=s.st_mtime_ns,is_regular_file=__import__('stat').S_ISREG(s.st_mode))
 elif op=='resolve':
  r=p.resolve(strict=True);result=dict(same_basename=os.path.normcase(r.name)==os.path.normcase(p.name),same_path=os.path.normcase(str(r))==os.path.normcase(str(p)))
 elif op=='access':result=dict(os_access_read=os.access(p,os.R_OK),advisory_only=True)
 elif op=='prefix':
  with p.open('rb',buffering=0) as f:
   a=os.fstat(f.fileno());raw=f.read(4096);b=os.fstat(f.fileno())
  result=dict(delivered_bytes=len(raw),prefix_sha256=hashlib.sha256(raw).hexdigest(),stable_metadata=(a.st_size,a.st_mtime_ns,a.st_ino)==(b.st_size,b.st_mtime_ns,b.st_ino),signature='HDF5' if raw.startswith(b'\x89HDF\r\n\x1a\n') else 'NETCDF' if raw.startswith(b'CDF') else 'OTHER',read_permission_proven_for_prefix=True)
 else:raise ValueError('Unknown operation')
 print(json.dumps(dict(status='PASS',result=result)))
except OSError as e:print(json.dumps(dict(status='OS_ERROR',exception=type(e).__name__,errno=e.errno,winerror=getattr(e,'winerror',None))))
'''

def main():
 p=argparse.ArgumentParser();p.add_argument('--original-private',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
 if a.output.exists():raise PermissionError('Diagnostic receipt is immutable; no implicit retry')
 v=json.loads(a.original_private.read_text(encoding='utf-8'));old=Path(v['output_root'])
 error=json.loads((old/'B8_s2029/failure.json').read_text(encoding='utf-8'))['error']
 if '[WinError 121]' not in error or BASENAME not in error:raise ValueError('Wrong failed source')
 frozen=json.loads(Path(v['inherited']).read_text(encoding='utf-8'))['prepared']
 matches=[(n,s) for n,s in frozen['roles']['Train']['files'].items() if Path(n).name.casefold()==BASENAME.casefold()]
 if len(matches)!=1 or matches[0][1]['year']!=2023:raise PermissionError('Exactly the frozen failed Train source required')
 name,source=matches[0];checks=[]
 for op in ('volume','stat','resolve','access','prefix'):
  started=time.monotonic()
  try:
   run=subprocess.run([sys.executable,'-B','-c',CHILD,name,op],capture_output=True,text=True,timeout=15,creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0,check=True)
   r=json.loads(run.stdout)
  except subprocess.TimeoutExpired:r=dict(status='TIMEOUT_STOP',delivered_byte_upper_bound=4096 if op=='prefix' else 0)
  checks.append(dict(operation=op,elapsed_seconds=time.monotonic()-started,**r))
  if r['status']!='PASS':break
 status='PASS_BOUNDED_CURRENT_ACCESS' if len(checks)==5 and all(c['status']=='PASS' for c in checks) and checks[1]['result']['bytes']==source['bytes'] and checks[2]['result']['same_basename'] and checks[-1]['result']['stable_metadata'] and checks[-1]['result']['delivered_bytes']==4096 else 'BLOCKED_SOURCE_DIAGNOSTIC'
 report=dict(status=status,checked_at=datetime.now(timezone.utc).isoformat(),source_basename=BASENAME,source_year=2023,
             inherited_full_source_sha256=source['sha'],expected_bytes=source['bytes'],checks=checks,
             limits=dict(max_operations=5,max_seconds_per_operation=15,max_payload_files=1,max_payload_bytes=4096,retries=0),
             actual_payload_files=1 if any(c['operation']=='prefix' for c in checks) else 0,
             actual_payload_bytes=sum(c.get('result',{}).get('delivered_bytes',0) for c in checks),
             original_failure_cause='NOT_VERIFIED_HISTORICAL_TRANSIENT_OR_STORAGE_CAUSE',full_payload_sha_reverified=False,
             scope='ONE_FAILED_SOURCE_ONLY; no scan, reconnect, repair or payload decoding',final_2025='FROZEN_NO_ACCESS')
 with a.output.open('x',encoding='utf-8') as f:json.dump(report,f,ensure_ascii=False,indent=2);f.write('\n')
 print(json.dumps(report,ensure_ascii=False))
if __name__=='__main__':main()
