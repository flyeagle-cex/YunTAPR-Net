"""Serialize mutable JSON reads and replacements with a bounded Windows mutex.

Checkpoint/data readers retain their original strict sharing. This interface
accepts only bounded local JSON snapshots and confers no execution authority.
"""
from contextlib import ExitStack,contextmanager
from pathlib import Path
from ctypes import wintypes as W
import ctypes,hashlib,json,math,os
from yuntapr.experimental.phase_b_v2_full_payload_integrity.winio import K,ReadHandle,info
M=ctypes.WinDLL('kernel32',use_last_error=True)
M.CreateMutexW.argtypes=[ctypes.c_void_p,W.BOOL,W.LPCWSTR];M.CreateMutexW.restype=W.HANDLE
M.WaitForSingleObject.argtypes=[W.HANDLE,W.DWORD];M.WaitForSingleObject.restype=W.DWORD
M.ReleaseMutex.argtypes=[W.HANDLE];M.ReleaseMutex.restype=W.BOOL
M.CloseHandle.argtypes=[W.HANDLE];M.CloseHandle.restype=W.BOOL

def lexical(path:Path,root:Path):
    if (not path.is_absolute() or not root.is_absolute() or not path.is_relative_to(root)
        or path==root or path.suffix!='.json' or '..' in path.parts or '..' in root.parts
        or '2025' in str(path)):
        raise PermissionError('BOUNDED_MUTABLE_JSON_SCOPE_BEFORE_NATIVE_ACCESS')

@contextmanager
def serialized_status(path:Path,root:Path,timeout_ms=2000):
    lexical(path,root)
    if type(timeout_ms) is not int or not 1<=timeout_ms<=10000:raise ValueError('BOUNDED_STATUS_LOCK_WAIT')
    key=hashlib.sha256(os.path.normcase(str(path)).encode('utf-8')).hexdigest()
    handle=M.CreateMutexW(None,False,'Local\\YunTAPR_StatusIO_'+key)
    if not handle:raise ctypes.WinError(ctypes.get_last_error())
    owned=False
    try:
        code=M.WaitForSingleObject(handle,timeout_ms);owned=code in (0,0x80)
        if code==0x102:raise TimeoutError('STATUS_IO_MUTEX_TIMEOUT')
        if code==0x80:raise PermissionError('STATUS_IO_MUTEX_ABANDONED')
        if code!=0:raise ctypes.WinError(ctypes.get_last_error())
        yield
    finally:
        if owned:M.ReleaseMutex(handle)
        M.CloseHandle(handle)

@contextmanager
def parents(path,root):
    with ExitStack() as stack:
        parents=[];p=path.parent
        while True:
            parents.append(p)
            if p==root:break
            p=p.parent
        for p in reversed(parents):
            h=stack.enter_context(ReadHandle(str(p),directory=True))
            if os.path.normcase(h.final_path)!=os.path.normcase(str(p)):raise PermissionError('SNAPSHOT_PARENT_IDENTITY')
        yield

@contextmanager
def open_snapshot(path:Path,root:Path):
    with serialized_status(path,root),parents(path,root):
        with ReadHandle(str(path),payload=True) as h:
            if os.path.normcase(h.final_path)!=os.path.normcase(str(path)):raise PermissionError('SNAPSHOT_NATIVE_IDENTITY')
            yield h.reader,h.handle,h.before

def atomic_status_json(path:Path,value,root:Path,timeout_ms=2000):
    """One replacement attempt. Failure keeps .part and propagates; no retry."""
    raw=(json.dumps(value,indent=2,ensure_ascii=False,allow_nan=False)+'\n').encode('utf-8')
    if not 0<len(raw)<=16*1024**2:raise ValueError('STATUS_JSON_SIZE_BOUND')
    with serialized_status(path,root,timeout_ms),parents(path,root):
        temp=path.with_name(path.name+'.part')
        with temp.open('xb') as f:f.write(raw);f.flush();os.fsync(f.fileno())
        os.replace(temp,path)

def read_exact(reader,size):
    buf=bytearray(size);n=0
    while n<size:
        count=reader.readinto(memoryview(buf)[n:])
        if not count:raise EOFError('SNAPSHOT_TRUNCATED')
        n+=count
    if reader.read(1):raise ValueError('SNAPSHOT_GREW_IN_PLACE')
    return bytes(buf)

def pairs(items):
    result={}
    for key,value in items:
        if key in result:raise ValueError('DUPLICATE_STATUS_JSON_KEY')
        result[key]=value
    return result

def read_json_snapshot(path:Path,root:Path,maximum:int=16*1024**2):
    if type(maximum) is not int or not 0<maximum<=16*1024**2:raise ValueError('STATUS_JSON_SIZE_LIMIT')
    with open_snapshot(path,root) as (reader,handle,before):
        if not 0<before['size']<=maximum:raise ValueError('STATUS_JSON_SIZE_BOUND')
        raw=read_exact(reader,before['size'])
        if info(handle)!=before:raise ValueError('STATUS_JSON_CHANGED_IN_PLACE')
    def invalid(value):raise ValueError('NONFINITE_STATUS_JSON')
    def number(value):
        result=float(value)
        if not math.isfinite(result):raise ValueError('NONFINITE_STATUS_JSON')
        return result
    return json.loads(raw,object_pairs_hook=pairs,parse_constant=invalid,parse_float=number)
