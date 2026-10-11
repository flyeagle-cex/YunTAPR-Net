"""Nonrefundable, fixed-identity cross-process optimizer and epoch ledger.

There is no restart/resume API. An ambiguous or failed attempt consumes quota.
The fixed .git witness prevents a renamed run or changed source from restarting.
"""
from __future__ import annotations
import json
import os
import sqlite3
from .protocol import ROOT, CAMPAIGN, ORDER, TOTAL, STEPS, EPOCHS, run_id

class Ledger:
    def __init__(self, release: dict):
        marker=ROOT/'.git/phase_b_v2_seed2026_a1863dc_republish_v2.once'
        with marker.open('x',encoding='utf-8',newline='\n') as stream:
            json.dump(dict(campaign=CAMPAIGN,release=release),stream); stream.flush(); os.fsync(stream.fileno())
        self.path=ROOT/'.git/phase_b_v2_seed2026_a1863dc_republish_v2.sqlite'
        if self.path.exists(): raise PermissionError('EXISTING_CAMPAIGN_NO_AUTOMATIC_RESTART')
        self.con=sqlite3.connect(self.path,timeout=5,isolation_level=None)
        self.con.execute('PRAGMA journal_mode=DELETE'); self.con.execute('PRAGMA synchronous=FULL')
        self.con.executescript('''CREATE TABLE campaign(id TEXT PRIMARY KEY,status TEXT,reason TEXT);
        CREATE TABLE runs(id TEXT PRIMARY KEY,ordinal INTEGER,status TEXT,epoch INTEGER,updates INTEGER,last_sha TEXT);
        CREATE TABLE attempts(n INTEGER PRIMARY KEY,run TEXT,update_no INTEGER,status TEXT,UNIQUE(run,update_no));
        CREATE TABLE epochs(run TEXT,epoch INTEGER,phase TEXT,train TEXT,validation TEXT,last_receipt TEXT,PRIMARY KEY(run,epoch));''')
        self.con.execute('INSERT INTO campaign VALUES(?,?,NULL)',(CAMPAIGN,'ACTIVE'))
        self.ancestor_sha=release['old_ancestor_receipt_sha256']
        for i,(model,arm) in enumerate(ORDER):
            self.con.execute('INSERT INTO runs VALUES(?,?,?,?,?,NULL)',(run_id(model,arm),i,'PENDING',0,0))
    def _atomic(self, fn):
        self.con.execute('BEGIN IMMEDIATE')
        try:
            result=fn(); self.con.execute('COMMIT'); return result
        except BaseException:
            self.con.execute('ROLLBACK'); raise
    def start_run(self, ident: str) -> None:
        def work():
            row=self.con.execute('SELECT ordinal,status FROM runs WHERE id=?',(ident,)).fetchone()
            if not row or row[1]!='PENDING' or self.con.execute("SELECT count(*) FROM runs WHERE ordinal<? AND status!='COMPLETE'",(row[0],)).fetchone()[0]:
                raise PermissionError('FIXED_RUN_ORDER_OR_NO_RESTART')
            if self.con.execute('SELECT status FROM campaign').fetchone()[0]!='ACTIVE': raise PermissionError('FAILED_CAMPAIGN')
            self.con.execute("UPDATE runs SET status='RUNNING' WHERE id=?",(ident,))
        self._atomic(work)
    def begin_epoch(self,ident: str,epoch: int):
        def work():
            row=self.con.execute('SELECT status,epoch,updates FROM runs WHERE id=?',(ident,)).fetchone()
            if row!=('RUNNING',epoch-1,(epoch-1)*STEPS) or not 1<=epoch<=EPOCHS: raise ValueError('B9_EPOCH_BOUNDARY')
            self.con.execute('INSERT INTO epochs VALUES(?,?,?,NULL,NULL,NULL)',(ident,epoch,'TRAINING'))
        self._atomic(work)
    def reserve(self, ident: str, update: int) -> int:
        def work():
            if self.con.execute('SELECT status FROM campaign').fetchone()[0]!='ACTIVE':raise PermissionError('FAILED_CAMPAIGN_NO_UPDATE')
            row=self.con.execute('SELECT status,updates FROM runs WHERE id=?',(ident,)).fetchone()
            if row!=('RUNNING',update-1) or not 1<=update<=STEPS*EPOCHS: raise PermissionError('UPDATE_SCOPE_OR_AMBIGUITY')
            epoch=(update-1)//STEPS+1
            if self.con.execute('SELECT phase FROM epochs WHERE run=? AND epoch=?',(ident,epoch)).fetchone()!=('TRAINING',): raise PermissionError('NOT_TRAIN_PHASE')
            count=self.con.execute('SELECT count(*) FROM attempts').fetchone()[0]
            if count>=TOTAL: raise PermissionError('282312_ATTEMPT_HARD_CAP')
            self.con.execute('INSERT INTO attempts VALUES(?,?,?,?)',(count+1,ident,update,'RESERVED_BEFORE_CALL'))
            return count+1
        return self._atomic(work)
    def returned(self,ident: str,update: int):
        def work():
            if self.con.execute('SELECT status FROM attempts WHERE run=? AND update_no=?',(ident,update)).fetchone()!=('RESERVED_BEFORE_CALL',): raise ValueError('UNRESERVED_RETURN')
            self.con.execute("UPDATE attempts SET status='RETURNED_VERIFIED' WHERE run=? AND update_no=?",(ident,update))
            self.con.execute('UPDATE runs SET updates=? WHERE id=?',(update,ident))
        self._atomic(work)
    def finish_train(self,ident: str,epoch: int,train: dict):
        def work():
            if self.con.execute('SELECT updates FROM runs WHERE id=?',(ident,)).fetchone()!=(epoch*STEPS,): raise ValueError('INCOMPLETE_UPDATE_BOUNDARY')
            if train['scenes']!=10455 or train['batches']!=STEPS: raise ValueError('INCOMPLETE_TRAIN_COVERAGE')
            self.con.execute("UPDATE epochs SET phase='WAIT_VALIDATION',train=? WHERE run=? AND epoch=?",(json.dumps(train),ident,epoch))
        self._atomic(work)
    def validated(self,ident: str,epoch: int,report: dict):
        if not report['complete'] or report['summary']['scenes']!=10501 or report['summary']['n_valid']!=10501*3430: raise ValueError('INCOMPLETE_VALIDATION')
        def work():
            if self.con.execute('SELECT phase FROM epochs WHERE run=? AND epoch=?',(ident,epoch)).fetchone()!=('WAIT_VALIDATION',): raise ValueError('VALIDATION_PHASE')
            self.con.execute("UPDATE epochs SET phase='VALIDATED',validation=? WHERE run=? AND epoch=?",(report['receipt_sha'],ident,epoch))
        self._atomic(work)
    def last(self,ident: str,epoch: int,receipt: dict):
        def work():
            if self.con.execute('SELECT phase FROM epochs WHERE run=? AND epoch=?',(ident,epoch)).fetchone()!=('VALIDATED',): raise ValueError('LAST_REQUIRES_COMPLETE_VALIDATION')
            self.con.execute("UPDATE epochs SET phase='LAST_COMMITTED',last_receipt=? WHERE run=? AND epoch=?",(json.dumps(receipt),ident,epoch))
            self.con.execute('UPDATE runs SET epoch=?,last_sha=?,status=? WHERE id=?',(epoch,receipt['payload_sha256'],'COMPLETE' if epoch==9 else 'RUNNING',ident))
        self._atomic(work)
    def parent(self,ident: str): return self.con.execute('SELECT last_sha FROM runs WHERE id=?',(ident,)).fetchone()[0]
    def snapshot(self) -> dict:
        return dict(campaign=CAMPAIGN,limit=TOTAL,reserved=self.con.execute('SELECT count(*) FROM attempts').fetchone()[0],
            old_campaign_reserved=0,combined_authorized_attempt_cap=TOTAL,old_ancestor_receipt_sha256=self.ancestor_sha,
            returned_verified=self.con.execute("SELECT count(*) FROM attempts WHERE status='RETURNED_VERIFIED'").fetchone()[0],
            runs=[dict(zip(('id','ordinal','status','epoch','updates','last_sha'),row)) for row in self.con.execute('SELECT * FROM runs ORDER BY ordinal')])
    def fail(self,reason: str):
        self._atomic(lambda:self.con.execute("UPDATE campaign SET status='FAILED_NO_RETRY',reason=?",(reason,)))
    def complete(self):
        s=self.snapshot()
        if s['reserved']!=TOTAL or s['returned_verified']!=TOTAL or any(r['status']!='COMPLETE' for r in s['runs']): raise ValueError('INCOMPLETE_SIX_RUN_CAMPAIGN')
        self._atomic(lambda:self.con.execute("UPDATE campaign SET status='COMPLETE'"))
    def close(self): self.con.close()
