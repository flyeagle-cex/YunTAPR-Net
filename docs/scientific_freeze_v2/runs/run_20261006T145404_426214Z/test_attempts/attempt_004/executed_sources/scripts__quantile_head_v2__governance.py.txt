"""Development-only I/O guard. Synthetic fixture state is never formal state."""
from pathlib import Path
import os
import sys
from contextlib import contextmanager

COUNTERS = {'RAW_SOURCE_OPENS':0, '2025_RAW_ACCESS':0, 'FORMAL_CHECKPOINT_DESERIALIZATIONS':0,
            'FORMAL_CHECKPOINT_STATE_APPLICATIONS_TO_V2':0,
            'FORMAL_OPTIMIZER_STEPS_ADDED':0, 'blocked_raw_attempts':0}
_readonly_legacy_checkpoints = {}


@contextmanager
def readonly_legacy_checkpoint_validation(references):
    """Only existing completed-Phase-A artifact tests; never v2 initialization."""
    global _readonly_legacy_checkpoints
    if _readonly_legacy_checkpoints:raise PermissionError('No nested historical state scopes')
    _readonly_legacy_checkpoints = {str(Path(p).resolve()):ref for p,ref in references.items()}
    try:yield
    finally:_readonly_legacy_checkpoints = {}


def check_raw_path(path):
    if not isinstance(path,(str,bytes,os.PathLike)): return
    text = os.fsdecode(path).replace('/','\\').lower()
    if text.startswith('h:\\') or '\\云南极端降水数据\\raw\\' in text:
        COUNTERS['blocked_raw_attempts'] += 1
        raise PermissionError('V2_DEVELOPMENT_RAW_ACCESS_FORBIDDEN: synthetic fixtures only')


def install():
    import netCDF4
    import torch
    def audit(event,args):
        if event == 'open': check_raw_path(args[0])
        if event in ('os.remove','os.rename','os.rmdir'):
            for value in args[:2]: check_raw_path(value)
    sys.addaudithook(audit)
    original_nc = netCDF4.Dataset
    def dataset(path,*args,**kwargs):
        check_raw_path(path)
        return original_nc(path,*args,**kwargs)
    netCDF4.Dataset = dataset
    original_load, original_save = torch.load, torch.save
    def guard_checkpoint(path):
        if isinstance(path,(str,bytes,os.PathLike)) and '\\outputs\\formal_training\\' in os.fsdecode(path).replace('/','\\').lower():
            raise PermissionError('V2_FORMAL_CHECKPOINT_STATE_ACCESS_FORBIDDEN')
    def load(path,*args,**kwargs):
        if isinstance(path,(str,bytes,os.PathLike)) and '\\outputs\\formal_training\\' in os.fsdecode(path).replace('/','\\').lower():
            p=Path(path).resolve();ref=_readonly_legacy_checkpoints.get(str(p))
            if ref is None:guard_checkpoint(path)
            from quantile_head_v2.common import digest
            if p.stat().st_size!=ref['bytes'] or digest(p)!=ref['sha256']:
                raise PermissionError('Historical SHA/size verification before read-only deserialization')
            value=original_load(path,*args,**kwargs)
            COUNTERS['FORMAL_CHECKPOINT_DESERIALIZATIONS']+=1
            return value
        return original_load(path,*args,**kwargs)
    def save(value,path,*args,**kwargs):
        guard_checkpoint(path)
        return original_save(value,path,*args,**kwargs)
    torch.load, torch.save = load, save
