"""One lifetime quota, append-only session identities, complete-LAST pauses."""
from __future__ import annotations
import json
import os
from pathlib import Path
import secrets
import sqlite3
from yuntapr.training.phase_b_v2_seed2026_resume_v2.quota import Ledger as BaseLedger
from .protocol import ROOT,OUT,LOCAL,DB,CAMPAIGN,ORDER,STEPS,TOTAL,MAX_NEW,OLD_RESERVED,ABANDONED,LAST_SHA,run_id,session_root,digest,owned_json

class PauseAtBoundary(Exception):pass

def ro():
    con=sqlite3.connect(DB.as_uri()+'?mode=ro',uri=True,timeout=1)
    con.execute('PRAGMA query_only=ON');return con

def carry():
    with ro() as con:
        row=con.execute("SELECT n,receipt FROM sessions WHERE status='PAUSED' ORDER BY n DESC LIMIT 1").fetchone()
    if row:
        resources=dict(json.loads(row[1])['resources'])
        term=owned_json(session_root(row[0])/'termination.json')
        if term['status']!='PAUSED' or not term['job_empty_and_handles_signaled']:raise PermissionError('PAUSE_JOB_NOT_CLOSED')
        resources['elapsed_seconds']=max(resources['elapsed_seconds'],term['elapsed_seconds'])
        return resources
    return json.loads((OUT/'ancestor.json').read_bytes())

class Ledger(BaseLedger):
    def __init__(self):
        if not DB.exists():raise PermissionError('CONTROL_INITIALIZATION_REQUIRED')
        self.path=DB;self.con=sqlite3.connect(DB,timeout=5,isolation_level=None)
        self.con.execute('PRAGMA synchronous=FULL')
        row=self.con.execute('SELECT id FROM campaign').fetchone()
        if row!=(CAMPAIGN,):raise PermissionError('OPERATOR_CAMPAIGN_IDENTITY')
        self.ancestor_sha=json.loads((OUT/'release.json').read_bytes())['ancestor_receipt_sha256']
    @classmethod
    def initialize(cls,release):
        if DB.exists():return cls()
        witness=ROOT/'.git/phase_b_v2_seed2026_epoch7_operator_v3.once'
        with witness.open('x',encoding='utf-8') as f:
            json.dump(dict(campaign=CAMPAIGN,release=release),f);f.flush();os.fsync(f.fileno())
        con=sqlite3.connect(DB,isolation_level=None)
        try:
            con.execute('PRAGMA journal_mode=DELETE');con.execute('PRAGMA synchronous=FULL')
            con.executescript('''CREATE TABLE campaign(id TEXT PRIMARY KEY,status TEXT,reason TEXT);
            CREATE TABLE runs(id TEXT PRIMARY KEY,ordinal INTEGER,status TEXT,epoch INTEGER,updates INTEGER,last_sha TEXT);
            CREATE TABLE attempts(n INTEGER PRIMARY KEY,run TEXT,update_no INTEGER,status TEXT,UNIQUE(run,update_no));
            CREATE TABLE epochs(run TEXT,epoch INTEGER,phase TEXT,train TEXT,validation TEXT,last_receipt TEXT,PRIMARY KEY(run,epoch));
            CREATE TABLE sessions(n INTEGER PRIMARY KEY,status TEXT,nonce TEXT,receipt TEXT);
            CREATE TABLE control(id INTEGER PRIMARY KEY,pause_requested INTEGER);INSERT INTO control VALUES(1,0);''')
            con.execute('INSERT INTO campaign VALUES(?,?,NULL)',(CAMPAIGN,'READY'))
            for i,(model,arm) in enumerate(ORDER):
                ident=run_id(model,arm)
                if i<3:
                    row=json.loads((ROOT/'docs/phase_b_v2_formal_execution/seed2026_v2'/(ident+'.json')).read_bytes())
                    values=(ident,i,'COMPLETE',9,47052,row['epochs'][-1]['checkpoint']['payload_sha256'])
                elif i==3:values=(ident,i,'PENDING',7,36596,LAST_SHA)
                else:values=(ident,i,'PENDING',0,0,None)
                con.execute('INSERT INTO runs VALUES(?,?,?,?,?,?)',values)
        finally:con.close()
        return cls()
    def claim_session(self):
        def work():
            state=self.con.execute('SELECT status FROM campaign').fetchone()[0]
            if state=='ACTIVE':raise PermissionError('ALREADY_RUNNING_NO_DUPLICATE_SESSION')
            if state not in ('READY','PAUSED'):raise PermissionError('FAILED_OR_COMPLETE_NO_AUTOMATIC_RESTART')
            if state=='PAUSED':
                n,receipt=self.con.execute("SELECT n,receipt FROM sessions WHERE status='PAUSED' ORDER BY n DESC LIMIT 1").fetchone()
                row=json.loads(receipt);path=session_root(n)
                actual=owned_json(path/'paused.json');term=owned_json(path/'termination.json')
                if actual!=row or not term['job_empty_and_handles_signaled'] or term['status']!='PAUSED':
                    raise PermissionError('PAUSE_CLOSING_OR_RECEIPT_NOT_VERIFIED')
                if self.snapshot()['reserved']!=row['quota']['reserved']:
                    raise PermissionError('PAUSED_QUOTA_ROLLBACK_OR_AMBIGUITY')
            n=self.con.execute('SELECT coalesce(max(n),0)+1 FROM sessions').fetchone()[0]
            if n>999:raise PermissionError('SESSION_ID_BOUND')
            nonce=secrets.token_hex(16)
            self.con.execute('INSERT INTO sessions VALUES(?,?,?,NULL)',(n,'CLAIMED',nonce))
            self.con.execute("UPDATE campaign SET status='ACTIVE',reason=NULL")
            self.con.execute('UPDATE control SET pause_requested=0')
            return n,nonce
        return self._atomic(work)
    def activate_session(self,n,nonce):
        def work():
            if self.con.execute('SELECT status,nonce FROM sessions WHERE n=?',(n,)).fetchone()!=('CLAIMED',nonce):
                raise PermissionError('SESSION_ALREADY_STARTED_OR_NONCE')
            self.con.execute("UPDATE sessions SET status='ACTIVE' WHERE n=?",(n,))
        self._atomic(work)
    def request_pause(self):
        def work():
            if self.con.execute('SELECT status FROM campaign').fetchone()!=('ACTIVE',):return False
            self.con.execute('UPDATE control SET pause_requested=1');return True
        return self._atomic(work)
    def verify_session(self,n,nonce):
        if self.con.execute('SELECT status,nonce FROM sessions WHERE n=?',(n,)).fetchone()!=('ACTIVE',nonce) or self.con.execute('SELECT status FROM campaign').fetchone()!=('ACTIVE',):
            raise PermissionError('CURRENT_ACTIVE_SESSION_AND_NONCE_REQUIRED')
    def pause_requested(self):return self.con.execute('SELECT pause_requested FROM control').fetchone()[0]==1
    def start_run(self,ident):
        def work():
            if self.pause_requested():raise PauseAtBoundary()
            row=self.con.execute('SELECT ordinal,status,epoch,updates,last_sha FROM runs WHERE id=?',(ident,)).fetchone()
            if not row or self.con.execute('SELECT status FROM campaign').fetchone()!=('ACTIVE',):raise PermissionError('INACTIVE_SCOPE')
            if self.con.execute("SELECT count(*) FROM runs WHERE ordinal<? AND status!='COMPLETE'",(row[0],)).fetchone()[0]:raise PermissionError('FIXED_ORDER')
            if row[1]=='PENDING':self.con.execute("UPDATE runs SET status='RUNNING' WHERE id=?",(ident,))
            elif row[1]=='RUNNING' and row[2:]==(0,0,None) and self.con.execute('SELECT count(*) FROM attempts WHERE run=?',(ident,)).fetchone()[0]==0:pass
            elif ident==run_id('B1_V2','E1') and row[1]=='RUNNING' and row[2:]==(7,36596,LAST_SHA) and self.con.execute('SELECT count(*) FROM attempts WHERE run=?',(ident,)).fetchone()[0]==0:pass
            elif row[1]=='RUNNING' and row[3]==row[2]*STEPS and row[4] and self.con.execute('SELECT phase FROM epochs WHERE run=? AND epoch=?',(ident,row[2])).fetchone()==('LAST_COMMITTED',):pass
            else:raise PermissionError('NO_UNFINISHED_TRANSACTION_RESTART')
        self._atomic(work)
    def run_row(self,ident):
        row=self.con.execute('SELECT * FROM runs WHERE id=?',(ident,)).fetchone()
        return dict(zip(('id','ordinal','status','epoch','updates','last_sha'),row))
    def begin_epoch(self,ident,epoch):
        if self.pause_requested():raise PauseAtBoundary()
        # Atomic boundary prevents a pause request racing the next epoch start.
        def work():
            if self.pause_requested():raise PauseAtBoundary()
            if self.con.execute('SELECT status,epoch,updates FROM runs WHERE id=?',(ident,)).fetchone()!=('RUNNING',epoch-1,(epoch-1)*STEPS):raise ValueError('B9_BOUNDARY')
            self.con.execute('INSERT INTO epochs VALUES(?,?,?,NULL,NULL,NULL)',(ident,epoch,'TRAINING'))
        self._atomic(work)
    def reserve(self,ident,update):
        def work():
            if self.con.execute('SELECT status FROM campaign').fetchone()!=('ACTIVE',):raise PermissionError('INACTIVE_NO_UPDATE')
            if self.con.execute('SELECT status,updates FROM runs WHERE id=?',(ident,)).fetchone()!=('RUNNING',update-1):raise PermissionError('UPDATE_IDENTITY_OR_AMBIGUITY')
            if not 1<=update<=47052:raise PermissionError('FIXED_RUN_CAP')
            if self.con.execute('SELECT phase FROM epochs WHERE run=? AND epoch=?',(ident,(update-1)//STEPS+1)).fetchone()!=('TRAINING',):raise PermissionError('NOT_TRAIN_PHASE')
            n=self.con.execute('SELECT count(*) FROM attempts').fetchone()[0]
            if n>=MAX_NEW:raise PermissionError('298474_COMBINED_HARD_CAP')
            self.con.execute('INSERT INTO attempts VALUES(?,?,?,?)',(n+1,ident,update,'RESERVED_BEFORE_CALL'));return n+1
        return self._atomic(work)
    def snapshot(self):
        counts=dict(self.con.execute('SELECT status,count(*) FROM attempts GROUP BY status').fetchall())
        n=sum(counts.values())
        return dict(campaign=CAMPAIGN,limit=TOTAL,reserved=OLD_RESERVED+n,new_reserved=n,
            returned_verified=OLD_RESERVED+counts.get('RETURNED_VERIFIED',0),old_campaign_reserved=OLD_RESERVED,
            abandoned_old_updates=ABANDONED,combined_authorized_attempt_cap=TOTAL,
            old_ancestor_receipt_sha256=self.ancestor_sha,
            runs=[dict(zip(('id','ordinal','status','epoch','updates','last_sha'),r)) for r in self.con.execute('SELECT * FROM runs ORDER BY ordinal')])
    def pause_boundary(self,n,nonce,resources):
        def work():
            s=self.snapshot()
            if s['reserved']!=s['returned_verified'] or self.con.execute("SELECT count(*) FROM epochs WHERE phase!='LAST_COMMITTED'").fetchone()[0]:raise ValueError('NO_PAUSE_AT_INCOMPLETE_TRANSACTION')
            if self.con.execute('SELECT status,nonce FROM sessions WHERE n=?',(n,)).fetchone()!=('ACTIVE',nonce):raise PermissionError('PAUSE_SESSION_IDENTITY')
            row=dict(status='PAUSED_VERIFIED',campaign=CAMPAIGN,session=n,nonce=nonce,quota=s,resources=resources)
            self.con.execute("UPDATE sessions SET status='PAUSED',receipt=? WHERE n=?",(json.dumps(row),n))
            self.con.execute("UPDATE campaign SET status='PAUSED'");return row
        return self._atomic(work)
    def complete(self):
        s=self.snapshot()
        if s['reserved']!=TOTAL or s['returned_verified']!=TOTAL or any(r['status']!='COMPLETE' for r in s['runs']):raise ValueError('INCOMPLETE_FIXED_SCOPE')
        self._atomic(lambda:self.con.execute("UPDATE campaign SET status='COMPLETE'"))
