"""Read and verify the closed Git identity queries without creating console children.

This compatibility adapter preserves the existing source-pin and ancestry checks.
It reads real HEAD/ref/loose-commit objects, validates SHA-1 object integrity,
and refuses unsupported queries/layouts. It does not invent Git identities.
"""
from contextlib import contextmanager
from functools import wraps
from pathlib import Path
import hashlib,os,re,subprocess,threading,zlib
from yuntapr.experimental.phase_b_v2_full_payload_integrity.winio import ReadHandle
ROOT=Path(__file__).absolute().parents[4]
REPOSITORIES={os.path.normcase(str(p)):p for p in (ROOT,
    ROOT.parent/'YunTAPR-Net-push-chunks',ROOT.parent/'YunTAPR-Net-completed-review-20261021',
    ROOT.parent/'YunTAPR-Net-seed2027-b1-e1-recovery-20261022')}
LOCK=threading.RLock()
SHA=re.compile('[0-9a-f]{40}')

def small(path,root,maximum=1024**2):
    if not path.is_relative_to(root/'.git') or '..' in path.parts:raise PermissionError('CLOSED_GIT_METADATA_PATH')
    with ReadHandle(str(path),payload=True) as handle:
        if os.path.normcase(handle.final_path)!=os.path.normcase(str(path)) or not 0<handle.before['size']<=maximum:raise ValueError('GIT_METADATA_OBJECT_OR_SIZE')
        raw=bytearray(handle.before['size']);position=0
        while position<len(raw):
            n=handle.readinto(memoryview(raw)[position:])
            if not n:raise EOFError('GIT_METADATA_TRUNCATED')
            position+=n
        if handle.snapshot()!=handle.before:raise ValueError('GIT_METADATA_CONCURRENT_CHANGE')
    return bytes(raw)

def head(root):
    value=small(root/'.git/HEAD',root,4096).decode('ascii').strip()
    if value.startswith('ref: '):
        ref=value[5:]
        if not ref.startswith('refs/heads/') or any(x in ('','.','..') for x in ref.split('/')) or not re.fullmatch('[A-Za-z0-9_./-]+',ref):raise ValueError('EXACT_GIT_BRANCH_REF')
        try:value=small(root/'.git'/ref,root,4096).decode('ascii').strip()
        except FileNotFoundError:
            rows=small(root/'.git/packed-refs',root).decode('ascii').splitlines()
            matches=[line.split(' ',1)[0] for line in rows if line.endswith(' '+ref) and not line.startswith(('#','^'))]
            if len(matches)!=1:raise ValueError('GIT_REF_NOT_UNIQUE')
            value=matches[0]
    if not SHA.fullmatch(value):raise ValueError('GIT_HEAD_SHA')
    return value

def parents(root,sha):
    if not SHA.fullmatch(sha):raise ValueError('GIT_COMMIT_SHA')
    raw=small(root/'.git/objects'/sha[:2]/sha[2:],root)
    decoder=zlib.decompressobj();decoded=decoder.decompress(raw,1024**2+1)
    if len(decoded)>1024**2 or not decoder.eof or decoder.unused_data or decoder.unconsumed_tail:raise ValueError('GIT_COMMIT_DECOMPRESSION_BOUND')
    if hashlib.sha1(decoded).hexdigest()!=sha:raise ValueError('GIT_COMMIT_OBJECT_HASH')
    header,body=decoded.split(b'\0',1)
    if header!=b'commit '+str(len(body)).encode('ascii'):raise ValueError('GIT_OBJECT_NOT_COMMIT')
    result=[]
    for line in body.split(b'\n\n',1)[0].splitlines():
        if line.startswith(b'parent '):
            parent=line[7:].decode('ascii')
            if not SHA.fullmatch(parent):raise ValueError('GIT_PARENT_SHA')
            result.append(parent)
    return result

def ancestor(root,source,current):
    seen=set();pending=[current]
    while pending:
        sha=pending.pop()
        if sha in seen:continue
        if len(seen)>=256:raise ValueError('GIT_ANCESTRY_BOUND')
        seen.add(sha);chain=parents(root,sha)
        if sha==source:return True
        pending.extend(chain)
    return False

def evaluate(args,kwargs):
    if not isinstance(args,(list,tuple)) or not args or Path(str(args[0])).name.lower() not in ('git','git.exe'):raise PermissionError('GIT_METADATA_ADAPTER_ONLY')
    root=REPOSITORIES.get(os.path.normcase(str(kwargs.get('cwd'))))
    if root is None or kwargs.get('shell') or kwargs.get('creationflags',0):raise PermissionError('REGISTERED_GIT_REPO_NO_PROCESS_OPTIONS')
    argv=list(args[1:])
    if argv==['rev-parse','HEAD']:return 0,(head(root)+'\n').encode('ascii'),b''
    if len(argv)==4 and argv[:2]==['merge-base','--is-ancestor'] and all(SHA.fullmatch(x) for x in argv[2:]):
        try:return (0 if ancestor(root,*argv[2:]) else 1),b'',b''
        except FileNotFoundError:return 128,b'',b'Commit object unavailable for closed metadata reader\n'
    raise PermissionError('EXACT_READ_ONLY_GIT_IDENTITY_QUERIES')

def output(raw,kwargs):
    return raw.decode(kwargs.get('encoding') or 'utf-8',kwargs.get('errors') or 'strict') if kwargs.get('text') or kwargs.get('universal_newlines') or kwargs.get('encoding') else raw

@contextmanager
def no_console_git():
    with LOCK:
        old_output,old_run=subprocess.check_output,subprocess.run
        def check_output(args,*extra,**kwargs):
            if extra:raise PermissionError('GIT_METADATA_KEYWORD_ARGUMENTS_ONLY')
            code,out,err=evaluate(args,kwargs)
            if code:raise subprocess.CalledProcessError(code,args,output=output(out,kwargs),stderr=output(err,kwargs))
            return output(out,kwargs)
        def run(args,*extra,**kwargs):
            if extra:raise PermissionError('GIT_METADATA_KEYWORD_ARGUMENTS_ONLY')
            code,out,err=evaluate(args,kwargs)
            if kwargs.get('check') and code:raise subprocess.CalledProcessError(code,args,output=output(out,kwargs),stderr=output(err,kwargs))
            return subprocess.CompletedProcess(args,code,output(out,kwargs),output(err,kwargs))
        subprocess.check_output,subprocess.run=check_output,run
        try:yield
        finally:subprocess.check_output,subprocess.run=old_output,old_run

def without_console(function):
    @wraps(function)
    def run(*args,**kwargs):
        with no_console_git():return function(*args,**kwargs)
    return run
