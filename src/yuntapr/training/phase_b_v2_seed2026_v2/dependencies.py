"""Hash the actual installed dependency closure, not just version strings.

References are software-bucket-relative. No data directory is searched. Derived
pyc caches are excluded explicitly; Python validates/rebuilds them from pinned
source. Dynamic OS/driver state and loaded-memory equivalence are not claimed.
"""
from __future__ import annotations
import hashlib
from importlib import metadata
import os
from pathlib import Path
import sys
from .protocol import ROOT,OUT,digest,atomic_json

def roots() -> dict[str,Path]:
    return dict(venv=Path(sys.prefix),python=Path(sys.base_prefix),windows=Path(os.environ['WINDIR']))

def relative_key(path: Path) -> str:
    path=Path(os.path.normpath(str(path)))
    for bucket,base in roots().items():
        if path.is_relative_to(base):return bucket+'/'+path.relative_to(base).as_posix()
    raise PermissionError('DEPENDENCY_OUTSIDE_EXPLICIT_SOFTWARE_ROOTS')

def software_path(key: str) -> Path:
    bucket,relative=key.split('/',1)
    if bucket not in roots() or ':' in relative or any(p in ('','..','.') for p in relative.split('/')):
        raise PermissionError('SOFTWARE_BUCKET_LEXICAL')
    return roots()[bucket]/relative

def file_sha(path: Path) -> str:
    h=hashlib.sha256()
    with path.open('rb') as stream:
        while raw:=stream.read(1024**2):h.update(raw)
    return h.hexdigest()

def capture() -> dict:
    selected={};files={};byte_total=0
    # Pin the complete installed-distribution set. This avoids introducing a
    # dependency resolver (packaging is not installed in this frozen venv).
    # It is deliberately broader than the training import closure, but limited
    # strictly to installed software RECORD references, never research data.
    for dist in sorted(metadata.distributions(),key=lambda d:d.metadata['Name'].lower()):
        name=dist.metadata['Name'].lower().replace('_','-')
        selected[name]=dict(version=dist.version,requires=dist.requires or [])
        for relative in dist.files or []:
            if '__pycache__' in str(relative) or str(relative).endswith(('.pyc','.pyo')):continue
            path=Path(dist.locate_file(relative));key=relative_key(path)
            if key not in files:
                size=path.stat().st_size;files[key]=dict(bytes=size,sha256=file_sha(path));byte_total+=size
    # Complete stdlib source/extension set, excluding the separate package tree.
    base=Path(sys.base_prefix)
    for directory in (base/'Lib',base/'DLLs'):
        for path in directory.rglob('*'):
            if ('site-packages' in path.parts or '__pycache__' in path.parts or
                path.suffix.lower() not in ('.py','.pyd','.dll')):continue
            key=relative_key(path)
            if key not in files:
                size=path.stat().st_size;files[key]=dict(bytes=size,sha256=file_sha(path));byte_total+=size
    for path in (Path(sys.executable),Path(sys._base_executable),base/'python312.dll',
                 roots()['windows']/'System32/kernel32.dll',roots()['windows']/'System32/psapi.dll'):
        key=relative_key(path)
        if key not in files:
            size=path.stat().st_size;files[key]=dict(bytes=size,sha256=file_sha(path));byte_total+=size
    result=dict(packages=selected,python_version=sys.version,files=files,files_sha256=digest(files),
                file_count=len(files),hashed_software_bytes=byte_total,derived_pyc_excluded=True,
                package_scope='ALL_INSTALLED_DISTRIBUTION_RECORD_REFERENCES_PLUS_STDLIB',
                operating_system_driver_live_memory_equivalence='NOT_VERIFIED')
    atomic_json(OUT/'dependency_identity.json',result);return result

def verify(expected_manifest_sha: str) -> dict:
    raw=(OUT/'dependency_identity.json').read_bytes()
    if hashlib.sha256(raw).hexdigest()!=expected_manifest_sha:raise ValueError('DEPENDENCY_MANIFEST_SHA')
    result=__import__('json').loads(raw)
    if digest(result['files'])!=result['files_sha256']:raise ValueError('DEPENDENCY_FILE_REGISTRY_SHA')
    for key,row in result['files'].items():
        path=software_path(key)
        if path.stat().st_size!=row['bytes'] or file_sha(path)!=row['sha256']:raise ValueError('ACTUAL_DEPENDENCY_BYTES_CHANGED')
    return dict(file_count=result['file_count'],hashed_software_bytes=result['hashed_software_bytes'],
                files_sha256=result['files_sha256'])
