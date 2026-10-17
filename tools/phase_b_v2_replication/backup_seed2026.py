"""One exclusive physical-disk backup of the six registered final LAST files.

No torch import, model loading, raw observations, directory search or ledger
mutation. Original native registrations are retained as provenance; a copied
file has a NEW native identity and cannot silently reuse a source registration.
"""
from __future__ import annotations
from contextlib import ExitStack
from datetime import datetime,timezone
from pathlib import Path
import argparse,hashlib,json,os,shutil,sys,traceback

ROOT=Path(__file__).absolute().parents[2]
OUT=ROOT/'docs/phase_b_v2_multiseed_preparation/v1'
FORMAL=ROOT/'docs/phase_b_v2_formal_execution'
sys.path.insert(0,str(ROOT/'src'))
from yuntapr.experimental.phase_b_v2_full_payload_integrity.winio import ReadHandle

RUNS=(('seed2026_v2','B0_MATCHED_V2__E0__s2026'),('seed2026_v2','B1_V2__E0__s2026'),
      ('seed2026_v2','B0_MATCHED_V2__E1__s2026'),('seed2026_operator_v3','B1_V2__E1__s2026'),
      ('seed2026_operator_v3','B0_MATCHED_V2__E2__s2026'),('seed2026_operator_v3','B1_V2__E2__s2026'))
BASE=ROOT/'docs/phase_b_v2_seed2026_scientific_analysis/v1'
def sha(raw):return hashlib.sha256(raw).hexdigest()
def dump(path,value):
    with path.open('xb') as f:
        f.write((json.dumps(value,ensure_ascii=False,indent=2)+'\n').encode());f.flush();os.fsync(f.fileno())
def lexical(path,root):
    if (not path.is_absolute() or '..' in path.parts or '2025' in str(path) or
        not path.is_relative_to(root) or str(path).startswith('\\\\')):
        raise PermissionError('BACKUP_PATH_SCOPE_BEFORE_NATIVE_ACCESS')
def opened(stack,path,root):
    lexical(path,root)
    for parent in reversed(path.parents):
        lexical(parent,Path(path.anchor))
        h=stack.enter_context(ReadHandle(str(parent),directory=True))
        if os.path.normcase(h.final_path)!=os.path.normcase(str(parent)):raise PermissionError('BACKUP_PARENT_OBJECT')
    h=stack.enter_context(ReadHandle(str(path),payload=True))
    if os.path.normcase(h.final_path)!=os.path.normcase(str(path)):raise PermissionError('BACKUP_FINAL_OBJECT')
    return h
def read_metadata(path):
    with ExitStack() as stack:
        h=opened(stack,path,ROOT)
        if not 0<h.before['size']<=32*1024**2:raise ValueError('BACKUP_METADATA_SIZE')
        raw=bytearray(h.before['size']);n=0
        while n<len(raw):
            k=h.readinto(memoryview(raw)[n:])
            if not k:raise EOFError('BACKUP_METADATA_TRUNCATED')
            n+=k
        if h.snapshot()!=h.before:raise ValueError('BACKUP_METADATA_CHANGED')
        return bytes(raw)
def inventory():
    audit=json.loads(read_metadata(BASE/'CHECKPOINT_PAYLOAD_AUDIT.json'))
    baseline=json.loads(read_metadata(BASE/'RECOMPUTATION_AUDIT.json'))['sources']
    entries=[]
    for namespace,run in RUNS:
        result_path=FORMAL/namespace/(run+'.json');raw=read_metadata(result_path)
        if sha(raw)!=baseline[result_path.relative_to(ROOT).as_posix()]:raise ValueError('PUBLISHED_RESULT_SHA_CHANGED')
        result=json.loads(raw);cp=result['epochs'][-1]['checkpoint'];directory=FORMAL/namespace/'.local'/run
        proof=next(r for r in audit['primary'] if r['run_id']==run)
        if result['status']!='COMPLETE' or result['updates']!=47052 or cp['payload_sha256']!=proof['actual_sha256']:
            raise ValueError('SIX_FINAL_REGISTRATION_REQUIRED')
        metas=[(directory/'checkpoints'/cp['reference_name'],'checkpoints/'+cp['reference_name']),
               (directory/'checkpoints/LAST_epoch_09.registration.json','checkpoints/LAST_epoch_09.registration.json'),
               (directory/'identity.json','identity.json'),(result_path,'published_result.json'),
               (directory/'development_epoch_09/report.json','development_epoch_09_report.json'),
               (FORMAL/namespace/'release.json','source_release.json')]
        for path,relative in metas:
            content=raw if path==result_path else read_metadata(path)
            if path.name==cp['reference_name'] and sha(content)!=cp['receipt_sha256']:raise ValueError('SOURCE_REFERENCE_SHA')
            entries.append(dict(source=path,relative=run+'/'+relative,sha256=sha(content),bytes=len(content),payload=False))
        entries.append(dict(source=directory/'checkpoints/LAST_epoch_09.pt',relative=run+'/checkpoints/LAST_epoch_09.pt',
            sha256=cp['payload_sha256'],bytes=cp['bytes'],payload=True))
    return entries
def execute(target):
    lexical(target,Path('H:/'))
    if target.parent!=Path('H:/YunTAPR-Net-checkpoint-backups'):raise PermissionError('FIXED_BACKUP_PARENT_ONLY')
    disks=json.loads((OUT/'.local/disk_identity.json').read_text(encoding='utf-8-sig'))
    parts={p['DriveLetter']:p for p in disks['partitions']}
    if parts['C']['DiskNumber']==parts['H']['DiskNumber']:raise PermissionError('PHYSICALLY_INDEPENDENT_DISK_REQUIRED')
    if (datetime.now(timezone.utc)-datetime.fromisoformat(disks['observed_utc'].replace('Z','+00:00'))).total_seconds()>1800:
        raise PermissionError('REFRESH_PHYSICAL_DISK_OBSERVATION')
    entries=inventory();required=sum(x['bytes'] for x in entries)
    if shutil.disk_usage('H:/').free<required+1024**3:raise OSError('BACKUP_SPACE_ADMISSION')
    target.parent.mkdir(exist_ok=True);target.mkdir(exist_ok=False)
    records=[];start=datetime.now(timezone.utc)
    dump(target/'backup_started.json',dict(status='INCOMPLETE',required_file_bytes=required,
         source_base_commit='3818118f069e910ca0073f03868f9ec1d9cfe483',no_overwrite=True))
    try:
        for entry in entries:
            dest=target/entry['relative'];lexical(dest,target);dest.parent.mkdir(parents=True,exist_ok=True)
            partial=dest.with_name(dest.name+'.part')
            with ExitStack() as stack:
                source=opened(stack,entry['source'],ROOT)
                if source.before['size']!=entry['bytes']:raise ValueError('SOURCE_SIZE_CHANGED')
                h=hashlib.sha256();count=0;buf=bytearray(4*1024**2)
                with partial.open('xb') as writer:
                    while n:=source.readinto(buf):
                        writer.write(memoryview(buf)[:n]);h.update(memoryview(buf)[:n]);count+=n
                    writer.flush();os.fsync(writer.fileno())
                if h.hexdigest()!=entry['sha256'] or count!=entry['bytes'] or source.snapshot()!=source.before:
                    raise ValueError('SOURCE_CONTENT_OR_OBJECT_CHANGED')
                os.rename(partial,dest) # Windows refuses an existing destination
                destination=opened(stack,dest,target);d=hashlib.sha256();nread=0
                while n:=destination.readinto(buf):d.update(memoryview(buf)[:n]);nread+=n
                if (d.hexdigest()!=entry['sha256'] or nread!=entry['bytes'] or destination.snapshot()!=destination.before or
                    destination.before['volume']==source.before['volume']):raise ValueError('BACKUP_CONTENT_OR_VOLUME_IDENTITY')
                records.append(dict(relative=entry['relative'],bytes=nread,sha256=d.hexdigest(),payload=entry['payload'],
                    source_object=dict(source.before),backup_object=dict(destination.before),status='PASS'))
            dump(target/(f'file_receipt_{len(records):03d}.json'),records[-1])
        result=dict(status='SIX_FINAL_LAST_PHYSICAL_BACKUP_SHA_PASS',started_utc=start.isoformat(),finished_utc=datetime.now(timezone.utc).isoformat(),
          files=records,total_file_bytes=required,payload_bytes=sum(x['bytes'] for x in records if x['payload']),
          source_read_bytes=required,backup_verification_read_bytes=required,source_disk_number=parts['C']['DiskNumber'],
          backup_disk_number=parts['H']['DiskNumber'],backup_filesystem='exFAT',independent_physical_device=True,
          torch_deserialization=False,model_optimizer_scheduler_rng='EXACT_FULL_CHECKPOINT_BYTES_RETAINED',
          native_registration_reuse='PROHIBITED_COPY_HAS_NEW_NATIVE_OBJECT_IDENTITY',
          power_loss_and_offline_backup='NOT_VERIFIED_ONLINE_USB_COPY_ONLY',original_files_modified=False,
          optimizer_updates=0,pixels_2025_read=0,historical_2025_path_attribute_access='NOT_INSTRUMENTED')
        dump(target/'backup_manifest.json',result)
        public=dict(result);public['backup_directory_key']=sha(str(target).encode())
        # Public provenance is relative; no private absolute path is published.
        (OUT/'BACKUP_VERIFICATION.json').write_bytes((json.dumps(public,ensure_ascii=False,indent=2)+'\n').encode())
        dump(OUT/'.local/backup_location.json',dict(path=str(target),manifest_sha256=sha((target/'backup_manifest.json').read_bytes())))
        print(json.dumps(dict(status=result['status'],files=len(records),payload_bytes=result['payload_bytes'],total_file_bytes=required,target=str(target))))
    except BaseException as exc:
        dump(target/'backup_failure.json',dict(status='FAILED_INCOMPLETE_DO_NOT_ADOPT',error=type(exc).__name__,verified_files=len(records)))
        (OUT/'.local/backup_failure.txt').write_text(traceback.format_exc(),encoding='utf-8')
        raise
def main():
    p=argparse.ArgumentParser();p.add_argument('--destination',type=Path,required=True);p.add_argument('--execute',action='store_true');a=p.parse_args()
    if a.execute:execute(a.destination)
    else:
        entries=inventory();print(json.dumps(dict(files=len(entries),required_file_bytes=sum(x['bytes'] for x in entries),payload_bytes=sum(x['bytes'] for x in entries if x['payload']),executed=False)))
if __name__=='__main__':main()
