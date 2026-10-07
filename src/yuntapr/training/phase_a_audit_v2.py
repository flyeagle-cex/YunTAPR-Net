"""Append-only v2 evidence and process-local, fail-closed source access."""
from contextlib import contextmanager
from dataclasses import asdict, dataclass
from pathlib import Path
import builtins
import hashlib
import io
import json
import os
import re
import sys
import time
import uuid


def digest(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(8 * 1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def identity(path):
    p = Path(path).resolve()
    return {'absolute_local_path': str(p), 'bytes': p.stat().st_size, 'sha256': digest(p)}


def read_json(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def atomic_json(path, value, *, immutable=False):
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    if immutable and p.exists():
        raise FileExistsError(p)
    tmp = p.with_name(p.name + '.' + uuid.uuid4().hex + '.tmp')
    with tmp.open('x', encoding='utf-8', newline='\n') as f:
        json.dump(value, f, ensure_ascii=False, indent=2, allow_nan=False)
        f.write('\n'); f.flush(); os.fsync(f.fileno())
    if immutable:
        # Windows rename refuses replacement; all formal execution is Windows.
        if p.exists():
            raise FileExistsError(p)
        tmp.rename(p)
    else:
        os.replace(tmp, p)


def append_event(log_path, event, **values):
    p = Path(log_path); p.parent.mkdir(parents=True, exist_ok=True)
    with p.open('a', encoding='utf-8', newline='\n') as f:
        f.write(json.dumps({'event': event, 'time_ns': time.time_ns(), 'pid': os.getpid(), **values},
                           ensure_ascii=False, allow_nan=False) + '\n')
        f.flush(); os.fsync(f.fileno())


@dataclass
class Counters:
    scope: str
    FORWARD_CALLS: int = 0
    TRAIN_FORWARDS: int = 0
    VALIDATION_FORWARDS: int = 0
    BACKWARD_CALLS: int = 0
    OPTIMIZER_STEP_ATTEMPTS: int = 0
    OPTIMIZER_STEPS: int = 0
    CHECKPOINT_WRITES: int = 0

    def __post_init__(self):
        if self.scope not in ('FORMAL', 'ENGINEERING_ONLY', 'TEST_FIXTURE_ONLY'):
            raise ValueError('Explicit counter scope required')

    def snapshot(self):
        return asdict(self)


def source_key(path):
    return str(Path(path).resolve()).replace('/', '\\').casefold()


class SourceFirewall:
    """Counts completed Python raw opens; audits native decode separately.

    Installed before source access in each parent/worker. Only managed staging
    copies or the pinned static mask may be decoded. No 2025 file is probed.
    """
    def __init__(self, sources, log_path, *, mask_path=None):
        self.sources = {source_key(p): v for p, v in sources.items()}
        self.log_path = Path(log_path)
        self.mask = source_key(mask_path) if mask_path else None
        self.active_staging = {}
        self.raw_opens = 0
        self.denied = 0
        self._logging = False
        self._active = False

    @staticmethod
    def is_raw(path):
        if not isinstance(path, (str, bytes, os.PathLike)):
            return False
        p = os.fsdecode(path).replace('/', '\\').casefold()
        return p.startswith('h:\\') or '\\云南极端降水数据\\raw\\' in p

    def check(self, path, mode='r'):
        if not self.is_raw(path):
            return False
        key = source_key(os.fsdecode(path))
        item = self.sources.get(key)
        writable = (any(c in mode for c in 'wa+x') if isinstance(mode, str)
                    else bool(mode & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC)))
        valid = item is not None and item['year'] in (2023, 2024) and 3 <= item['month'] <= 10
        relative = key.split('葵花202303_202510\\')[-1].split('raw\\imerg\\')[-1]
        if not valid or writable or re.search(r'2025', relative):
            self.denied += 1
            self.event('DENIED_BEFORE_OPEN', path=str(path))
            raise PermissionError('V2_SOURCE_FIREWALL_REJECT')
        return True

    def event(self, event, **kwargs):
        if self._logging:
            return
        self._logging = True
        try:
            append_event(self.log_path, event, **kwargs)
        finally:
            self._logging = False

    @contextmanager
    def installed(self):
        import netCDF4
        old_open, old_io, old_osopen, old_nc = builtins.open, io.open, os.open, netCDF4.Dataset
        self._active = True
        def wrap(original):
            def opened(file, *args, **kwargs):
                mode = args[0] if args else kwargs.get('mode', kwargs.get('flags', 'r'))
                raw = self.check(file, mode)
                handle = original(file, *args, **kwargs)
                if raw:
                    self.raw_opens += 1
                    try:
                        self.event('RAW_SOURCE_OPEN_COMPLETED', path=str(file), RAW_SOURCE_OPENS=self.raw_opens)
                    except BaseException:
                        if isinstance(handle, int): os.close(handle)
                        else: handle.close()
                        raise
                return handle
            return opened
        def audit(event, args):
            if not self._active or self._logging:
                return
            if event == 'open':
                self.check(args[0], args[1] if args[1] is not None else args[2])
            elif event in ('os.remove', 'os.rename', 'os.rmdir'):
                for p in args[:2]:
                    if self.is_raw(p):
                        raise PermissionError('RAW_MUTATION_FORBIDDEN')
        def dataset(path, *args, **kwargs):
            mode = kwargs.get('mode', args[0] if args else 'r')
            key = source_key(path)
            if mode != 'r' or key not in self.active_staging and key != self.mask:
                self.event('DENIED_NATIVE_DECODE', path=str(path))
                raise PermissionError('Only verified staging/static mask decode is allowed')
            self.event('NATIVE_DECODE', path=str(path), source=self.active_staging.get(key, 'FROZEN_STATIC_MASK'))
            return old_nc(path, *args, **kwargs)
        sys.addaudithook(audit)
        builtins.open, io.open, os.open = wrap(old_open), wrap(old_io), wrap(old_osopen)
        netCDF4.Dataset = dataset
        try:
            yield self
        finally:
            self._active = False
            builtins.open, io.open, os.open, netCDF4.Dataset = old_open, old_io, old_osopen, old_nc

    def register_copy(self, local, source):
        self.check(source, 'rb')
        item = self.sources[source_key(source)]
        if digest(local) != item['sha256']:
            raise ValueError('Frozen staging source SHA mismatch')
        self.active_staging[source_key(local)] = str(source)
        self.event('VERIFIED_STAGING', local=str(local), source=str(source), sha256=item['sha256'])


def reconcile_io(directory):
    files = sorted(Path(directory).rglob('raw_access_*.jsonl'))
    counts = {'RAW_SOURCE_OPENS': 0, 'NATIVE_DECODES': 0, 'DENIED_ATTEMPTS': 0,
              '2025_RAW_ACCESS': 0, '2025_PIXELS_READ': 0}
    for file in files:
        for line in file.read_text(encoding='utf-8').splitlines():
            event = json.loads(line)
            kind = event['event']
            if kind == 'RAW_SOURCE_OPEN_COMPLETED':
                counts['RAW_SOURCE_OPENS'] += 1
                relative = event['path'].replace('/', '\\').split('葵花202303_202510\\')[-1]
                if '2025' in relative: raise AssertionError('2025 source opened')
            elif kind == 'NATIVE_DECODE':
                counts['NATIVE_DECODES'] += 1
                relative = event['source'].replace('/', '\\').split('葵花202303_202510\\')[-1]
                if '2025' in relative: raise AssertionError('2025 source decoded')
            elif kind.startswith('DENIED'):
                counts['DENIED_ATTEMPTS'] += 1
    return {**counts, 'log_files': [identity(p) for p in files],
            'proof_scope': 'Controlled v2 parent/worker source opens and native decode, not unrelated OS processes'}
