"""Isolated workspace and bounded durable SQLite transactions.

SQLite FULL synchronization/atomic replacement is engineering evidence, not a
claim of power-loss durability on all filesystems. No stale lock is auto-cleared.
"""
from __future__ import annotations
from contextlib import contextmanager
import contextvars
import os
from pathlib import Path
import re
import shutil
import sqlite3
import sys
import tempfile
import torch
from .protocol import OUT

LOCAL = OUT / ".local"
_active = contextvars.ContextVar("integration_candidate_optimizer",default=None)
_original_step = torch.optim.AdamW.step
_installed = False

class Workspace:
    def __init__(self):
        LOCAL.mkdir(parents=True,exist_ok=True)
        self.root = Path(tempfile.mkdtemp(prefix="session_",dir=LOCAL))
    def file(self,name: str) -> Path:
        if type(name) is not str or re.fullmatch("[A-Za-z0-9_.-]+",name) is None or name in (".",".."):
            raise PermissionError("Simple isolated filename only")
        return self.root/name

def _audit(event,args):
    if event!="open" or not args or not isinstance(args[0],(str,bytes,os.PathLike)): return
    raw=os.fsdecode(args[0])
    # Lexical rejection precedes resolution/stat, including Windows paths.
    if ("2025" in raw or any(s in raw.lower() for s in ("shared_scaler","yunnan_mask"))
        or raw.lower().endswith((".nc",".h5",".hdf5",".npy",".npz",".tif",".tiff"))):
        raise PermissionError("Observational artifacts/sealed year forbidden")
    if raw.lower().endswith((".pt",".pth",".ckpt",".part")):
        absolute=os.path.abspath(raw)
        if os.path.commonpath((absolute,str(LOCAL)))!=str(LOCAL):
            raise PermissionError("Only isolated synthetic checkpoint bytes allowed")

def install_guard():
    global _installed
    if _installed:return
    sys.addaudithook(_audit)
    def controlled_step(optimizer,*args,**kwargs):
        if _active.get() is not optimizer or type(optimizer) is not torch.optim.AdamW:
            raise PermissionError("Only durable, bounded synthetic AdamW transaction")
        return _original_step(optimizer,*args,**kwargs)
    # Other optimizer families are outside this task, not fallback routes.
    for cls in vars(torch.optim).values():
        if isinstance(cls,type) and issubclass(cls,torch.optim.Optimizer):
            cls.step=controlled_step
    _installed=True

@contextmanager
def optimizer_permit(optimizer):
    token=_active.set(optimizer)
    try: yield
    finally: _active.reset(token)

def database(path: Path, *, max_bytes: int=64*1024**2, min_free: int=64*1024**2):
    if not path.is_absolute() or not path.is_relative_to(LOCAL):
        raise PermissionError('Only managed candidate scratch databases')
    if type(max_bytes) is not int or max_bytes<16384:
        raise ValueError("Explicit bounded database budget")
    if shutil.disk_usage(path.parent).free<min_free:
        raise RuntimeError("Insufficient scratch storage; no fallback")
    con=sqlite3.connect(path,timeout=0,isolation_level=None)
    con.execute("PRAGMA journal_mode=DELETE")
    con.execute("PRAGMA synchronous=FULL")
    con.execute("PRAGMA cache_size=-1024")
    con.execute("PRAGMA temp_store=FILE")
    page=con.execute("PRAGMA page_size").fetchone()[0]
    con.execute(f"PRAGMA max_page_count={max_bytes//page}")
    return con

@contextmanager
def transaction(con):
    con.execute("BEGIN IMMEDIATE")
    try:
        yield
        con.execute("COMMIT")
    except BaseException:
        if con.in_transaction: con.execute("ROLLBACK")
        raise
