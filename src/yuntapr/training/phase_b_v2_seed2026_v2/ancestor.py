"""Bind immutable zero-update predecessor; never reuse its checkpoint/quota.

Receipt-relative paths are restricted to the exact prior audit namespace and
two fixed prior ledger witnesses. All are audit evidence, not model weights.
"""
from __future__ import annotations
import hashlib
import json
import os
from pathlib import Path
import sqlite3
from yuntapr.experimental.phase_b_v2_full_payload_integrity.winio import ReadHandle
from .protocol import ROOT,OUT

OLD = 'docs/phase_b_v2_formal_execution/seed2026_v1/'
WITNESSES = {'.git/phase_b_v2_seed2026_2131d576.once','.git/phase_b_v2_seed2026_2131d576.sqlite'}

class Guard:
    def __init__(self,expected_receipt_sha: str):
        self.handles=[];self.receipt=None
        try:
            raw=(OUT/'old_zero_update_ancestor.json').read_bytes()
            if hashlib.sha256(raw).hexdigest()!=expected_receipt_sha:raise ValueError('OLD_ANCESTOR_RECEIPT_SHA')
            row=json.loads(raw)
            if (row['optimizer_reserved']!=0 or row['optimizer_returned']!=0 or row['epochs']!=0 or row['adopted_last']!=0 or
                row['old_job_empty'] is not True or row['old_worker_native_identity_not_running'] is not True):
                raise ValueError('ONLY_ZERO_UPDATE_FAILED_PREDECESSOR')
            for relative,sha in row['pins'].items():
                text=relative.replace('\\','/')
                if ('..' in text.split('/') or ':' in text or text.startswith('/') or
                    not (text.startswith(OLD) or text in WITNESSES) or text.endswith(('.pt','.pth','.ckpt'))):
                    raise PermissionError('PRIOR_AUDIT_EVIDENCE_ONLY')
                path=ROOT/text;handle=ReadHandle(str(path),payload=True)
                self.handles.append(handle)
                if os.path.normcase(handle.final_path)!=os.path.normcase(str(path)):raise ValueError('PRIOR_EVIDENCE_NATIVE_OBJECT')
                h=hashlib.sha256();buf=bytearray(1024**2);count=0
                while True:
                    n=handle.readinto(buf)
                    if not n:break
                    count+=n;h.update(memoryview(buf)[:n])
                if count!=handle.before['size'] or handle.snapshot()!=handle.before or h.hexdigest()!=sha:
                    raise ValueError('PRIOR_EVIDENCE_CHANGED')
            p=ROOT/'.git/phase_b_v2_seed2026_2131d576.sqlite'
            with sqlite3.connect('file:'+str(p)+'?mode=ro',uri=True) as con:
                if con.execute('SELECT count(*) FROM attempts').fetchone()[0] or con.execute('SELECT count(*) FROM epochs').fetchone()[0]:
                    raise ValueError('OLD_ATTEMPTS_OR_EPOCH_EXIST')
                if con.execute('SELECT count(*) FROM runs WHERE updates!=0 OR epoch!=0 OR last_sha IS NOT NULL').fetchone()[0]:
                    raise ValueError('OLD_UPDATE_OR_LAST_EXIST')
            self.receipt=row
        except BaseException:self.close();raise
    def close(self):
        for h in reversed(self.handles):h.close()
        self.handles.clear()
