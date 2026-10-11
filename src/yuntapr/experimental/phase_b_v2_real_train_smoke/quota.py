"""Permanent common-Git ledger, two witnesses, no refunds or restart path."""
from __future__ import annotations
import json
import os
from pathlib import Path
import sqlite3
import subprocess
from . import ROOT, OUT, MODELS, AUTHORIZATION_ID
from yuntapr.experimental.phase_b_v2_formal_integration_candidate.storage import transaction
from yuntapr.experimental.phase_b_v2_real_forward_pilot.resources import utcnow

class QuotaCore:
    """Private generic state machine, also tested without calling any optimizer."""
    def __init__(self, path: Path, *, create: bool, campaign: str):
        self.path, self.campaign = path, campaign
        if create:
            with path.open('xb'): pass  # existing ledger is never reset/reused
        elif not path.is_file(): raise PermissionError('MISSING_LEDGER_NO_RECREATION')
        self.con=sqlite3.connect(path, timeout=0, isolation_level=None)
        self.con.execute('PRAGMA journal_mode=DELETE'); self.con.execute('PRAGMA synchronous=FULL')
        self.con.execute('PRAGMA max_page_count=256')
        if create:
            with transaction(self.con):
                self.con.execute('CREATE TABLE task(campaign TEXT PRIMARY KEY, state TEXT, started TEXT)')
                self.con.execute('CREATE TABLE models(model TEXT PRIMARY KEY, forward_reserved INTEGER, backward_reserved INTEGER, step_reserved INTEGER, step_entered INTEGER, step_returned INTEGER, transaction_complete INTEGER)')
                self.con.execute('INSERT INTO task VALUES(?,?,?)',(campaign,'ACTIVE',utcnow()))
                self.con.executemany('INSERT INTO models VALUES(?,0,0,0,0,0,0)',[(m,) for m in MODELS])
        if self.con.execute('SELECT campaign FROM task').fetchone() != (campaign,):
            self.con.close(); raise PermissionError('QUOTA_AUTHORIZATION_IDENTITY_MISMATCH')
    def _active(self):
        if self.con.execute('SELECT state FROM task').fetchone() != ('ACTIVE',):
            raise PermissionError('SEALED_OR_FAILED_SMOKE_NO_CONTINUATION')
    def reserve(self, model: str, stage: str) -> None:
        column={'forward':'forward_reserved','backward':'backward_reserved','step':'step_reserved'}.get(stage)
        if model not in MODELS or column is None: raise PermissionError('CLOSED_E0_SEED2026_KEYS')
        with transaction(self.con):
            self._active()
            row=self.con.execute('SELECT * FROM models WHERE model=?',(model,)).fetchone()
            if model==MODELS[1] and self.con.execute('SELECT transaction_complete FROM models WHERE model=?',(MODELS[0],)).fetchone() != (1,):
                raise PermissionError('B0_COMPLETE_BEFORE_B1')
            index={'forward':1,'backward':2,'step':3}[stage]
            if row[index] or (stage=='backward' and not row[1]) or (stage=='step' and not row[2]):
                raise PermissionError('NO_DUPLICATE_OR_OUT_OF_ORDER_ATTEMPT')
            self.con.execute(f'UPDATE models SET {column}=1 WHERE model=?',(model,))
    def entered(self, model: str) -> None:
        with transaction(self.con):
            self._active()
            if self.con.execute('SELECT step_reserved,step_entered FROM models WHERE model=?',(model,)).fetchone() != (1,0):
                raise PermissionError('STEP_NOT_RESERVED_OR_ALREADY_ENTERED')
            self.con.execute('UPDATE models SET step_entered=1 WHERE model=?',(model,))
    def returned(self, model: str) -> None:
        with transaction(self.con):
            self._active()
            if self.con.execute('SELECT step_entered,step_returned FROM models WHERE model=?',(model,)).fetchone() != (1,0):
                raise PermissionError('STEP_RETURN_MISMATCH')
            self.con.execute('UPDATE models SET step_returned=1 WHERE model=?',(model,))
    def completed(self, model: str) -> None:
        with transaction(self.con):
            self._active()
            if self.con.execute('SELECT step_returned,transaction_complete FROM models WHERE model=?',(model,)).fetchone() != (1,0):
                raise PermissionError('COMPLETE_WITHOUT_STEP_OR_DUPLICATE')
            self.con.execute('UPDATE models SET transaction_complete=1 WHERE model=?',(model,))
    def seal(self, failed: bool) -> None:
        with transaction(self.con):
            if not failed and self.con.execute('SELECT SUM(transaction_complete) FROM models').fetchone() != (2,):
                raise PermissionError('CANNOT_SEAL_INCOMPLETE_SMOKE_AS_COMPLETE')
            self.con.execute('UPDATE task SET state=?',('FAILED_SEALED' if failed else 'COMPLETE_SEALED',))
    def snapshot(self) -> dict:
        cols=('forward_reserved','backward_reserved','step_reserved','step_entered','step_returned','transaction_complete')
        rows={r[0]:dict(zip(cols,r[1:])) for r in self.con.execute('SELECT * FROM models ORDER BY model')}
        return dict(campaign=self.campaign, state=self.con.execute('SELECT state FROM task').fetchone()[0],
            models=rows, reserved_step_attempts=sum(r['step_reserved'] for r in rows.values()),
            entered_optimizer_calls=sum(r['step_entered'] for r in rows.values()),
            returned_optimizer_calls=sum(r['step_returned'] for r in rows.values()),
            FORMAL_PHASE_B_OPTIMIZER_STEPS=0)
    def close(self): self.con.close()

class SmokeQuota(QuotaCore):
    def __init__(self, code_sha: str):
        common=Path(subprocess.check_output(['git','rev-parse','--git-common-dir'],cwd=ROOT,text=True).strip())
        if not common.is_absolute(): common=ROOT/common
        # Fixed names independent of source SHA, branch, temp dir, model/run name.
        self.marker=common/'yuntapr_real_train_smoke_20261010.once'
        self.witness=OUT/'.local/real_train_smoke_20261010.once'
        ledger=common/'yuntapr_real_train_smoke_20261010.sqlite'
        if self.marker.exists() or self.witness.exists() or ledger.exists():
            raise PermissionError('SINGLE_USE_CAMPAIGN_ALREADY_CLAIMED_NO_RESTART')
        self.witness.parent.mkdir(parents=True,exist_ok=True)
        initial=dict(campaign=AUTHORIZATION_ID,claimed_at_utc=utcnow(),code_sha256=code_sha,
            basis='Human task instruction: bounded engineering smoke only; no scientific approval')
        self.marker_bytes=json.dumps(initial).encode()
        for path in (self.marker,self.witness):
            with path.open('xb') as stream:
                stream.write(self.marker_bytes); stream.flush(); os.fsync(stream.fileno())
        super().__init__(ledger,create=True,campaign=AUTHORIZATION_ID)
    def _active(self):
        if not self.marker.is_file() or not self.witness.is_file() or not self.path.is_file():
            raise PermissionError('QUOTA_WITNESS_MISSING_NO_RESET')
        if self.marker.read_bytes()!=self.marker_bytes or self.witness.read_bytes()!=self.marker_bytes:
            raise PermissionError('QUOTA_WITNESS_CHANGED')
        super()._active()
