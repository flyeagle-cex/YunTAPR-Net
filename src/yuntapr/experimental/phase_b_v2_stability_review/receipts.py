"""Append-only postmortem evidence. Never overwrite an old run or ledger."""
from __future__ import annotations
import hashlib,json,os,secrets
from contextlib import contextmanager,ExitStack
from pathlib import Path
from yuntapr.experimental.phase_b_v2_full_payload_integrity.winio import ReadHandle

ROOT=Path(__file__).absolute().parents[4]
LOCAL=ROOT/'docs/phase_b_v2_stability_review/v1/.local'

def canonical(value):return json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode()

@contextmanager
def directories(base: Path,*,create: bool):
    chain=[];current=base
    while True:
        chain.append(current)
        if current==ROOT:break
        if not current.is_relative_to(ROOT):raise PermissionError('RECEIPT_PARENT_SCOPE')
        current=current.parent
    with ExitStack() as stack:
        for p in reversed(chain):
            if create and p!=ROOT:
                try:p.mkdir()
                except FileExistsError:pass
            h=stack.enter_context(ReadHandle(str(p),directory=True))
            if os.path.normcase(h.final_path)!=os.path.normcase(str(p)):raise PermissionError('RECEIPT_PARENT_NATIVE_IDENTITY')
        yield

def save(record: dict,*,folder: Path|None=None,fault: str|None=None) -> Path:
    base=LOCAL/'receipts' if folder is None else folder
    if (not base.is_absolute() or not base.is_relative_to(LOCAL) or base==LOCAL or '..' in base.parts or
        '2025' in str(base) or fault not in (None,'after_fsync')):
        raise PermissionError('NEW_POSTMORTEM_RECEIPTS_ONLY')
    # These are deliberately not legacy termination.json or approval records.
    envelope=dict(schema='POSTMORTEM_OBSERVATION_v1',record=record,record_sha256=hashlib.sha256(canonical(record)).hexdigest(),
        original_termination_receipt=False,power_loss_directory_durability='NOT_VERIFIED')
    raw=(json.dumps(envelope,indent=2,allow_nan=False)+'\n').encode()
    name='observation_'+secrets.token_hex(12)+'.json';final=base/name;part=base/(name+'.part')
    with directories(base,create=True):
        with part.open('xb') as f:f.write(raw);f.flush();os.fsync(f.fileno())
        if fault=='after_fsync':raise OSError('SYNTHETIC_RECEIPT_FAULT_AFTER_FSYNC')
        # Atomic no-overwrite publication on NTFS. No replace() of old evidence.
        os.link(part,final)
        part.unlink()
    verify(final)
    return final

def verify(path: Path) -> dict:
    if not path.is_absolute() or not path.is_relative_to(LOCAL) or path.suffix!='.json' or '..' in path.parts or '2025' in str(path):
        raise PermissionError('OWNED_POSTMORTEM_JSON_ONLY')
    with directories(path.parent,create=False),ReadHandle(str(path),payload=True) as f:
        if os.path.normcase(f.final_path)!=os.path.normcase(str(path)) or not 0<f.before['size']<=2*1024**2:
            raise PermissionError('RECEIPT_NATIVE_OBJECT_OR_SIZE')
        buf=bytearray(f.before['size']);n=0
        while n<len(buf):
            count=f.readinto(memoryview(buf)[n:])
            if not count:raise EOFError('RECEIPT_TRUNCATED')
            n+=count
        if f.snapshot()!=f.before:raise ValueError('RECEIPT_CHANGED')
        raw=bytes(buf)
    if not 0<len(raw)<=2*1024**2:raise ValueError('RECEIPT_SIZE_LIMIT')
    row=json.loads(raw)
    if (row.get('schema')!='POSTMORTEM_OBSERVATION_v1' or row.get('original_termination_receipt') is not False or
        row.get('record_sha256')!=hashlib.sha256(canonical(row['record'])).hexdigest()):
        raise ValueError('POSTMORTEM_RECEIPT_INTEGRITY')
    return row
