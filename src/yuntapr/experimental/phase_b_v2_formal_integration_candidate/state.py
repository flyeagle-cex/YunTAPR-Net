"""Durable B9 transactions and a separate, non-refundable four-step campaign.

LOGICAL_B9 verifies integer budgets without executing an optimizer. Synthetic
reservations commit before the step; an interrupted reservation stays consumed.
"""
from __future__ import annotations
import json
import torch
from yuntapr.experimental.phase_b_v2_integration.controls import synthetic_epoch_order
from .protocol import Profile, digest, code_sha, sha_string
from .storage import Workspace, LOCAL, database, transaction, optimizer_permit, install_guard

class B9State:
    def __init__(self, workspace: Workspace, identity: dict):
        if type(workspace) is not Workspace: raise TypeError('Managed synthetic workspace')
        self.profile=Profile(**identity['profile']); self.identity=identity
        self.con=database(workspace.file('state.sqlite'))
        self.con.execute('CREATE TABLE IF NOT EXISTS state(id INTEGER PRIMARY KEY,document TEXT)')
        self.con.execute('CREATE TABLE IF NOT EXISTS events(id INTEGER PRIMARY KEY,event TEXT)')
        with transaction(self.con):
            row=self.con.execute('SELECT document FROM state WHERE id=1').fetchone()
            if row is None:
                self._write(dict(identity_sha=digest(identity),phase='READY',epoch=0,updates=0,pending=False,last_sha=None,train=None,validation=None),'CREATE')
            elif json.loads(row[0])['identity_sha']!=digest(identity): raise ValueError('Existing run identity mismatch')

    def read(self): return json.loads(self.con.execute('SELECT document FROM state WHERE id=1').fetchone()[0])

    def _write(self,s,event):
        self.con.execute('INSERT OR REPLACE INTO state VALUES(1,?)',(json.dumps(s,sort_keys=True,allow_nan=False),))
        self.con.execute('INSERT INTO events(event) VALUES(?)',(event,))

    def begin(self):
        with transaction(self.con):
            s=self.read()
            if s['phase']!='READY' or s['epoch']>=9 or s['pending']: raise ValueError('No partial restart or budget extension')
            s['phase']='TRAINING'; s['train']=None; s['validation']=None; self._write(s,'BEGIN_EPOCH')
        return synthetic_epoch_order(self.profile.ids('train'),self.identity['run']['seed'],s['epoch'])

    def reserve(self):
        with transaction(self.con):
            s=self.read()
            if self.profile.name!='SYNTHETIC_SMALL' or s['phase']!='TRAINING' or s['pending'] or s['updates']>=(s['epoch']+1)*self.profile.steps:
                raise ValueError('Reservation outside epoch budget')
            s['pending']=True; s['updates']+=1; self._write(s,'STEP_RESERVED_NONREFUNDABLE')

    def complete_step(self):
        with transaction(self.con):
            s=self.read()
            if s['phase']!='TRAINING' or not s['pending']: raise ValueError('Missing step reservation')
            s['pending']=False; self._write(s,'STEP_COMPLETED')

    def finish_train(self,batches):
        with transaction(self.con):
            s=self.read(); expected=synthetic_epoch_order(self.profile.ids('train'),self.identity['run']['seed'],s['epoch'])
            actual=tuple(i for batch in batches for i in batch)
            if (s['phase']!='TRAINING' or s['pending'] or actual!=tuple(expected)
                or len(batches)!=self.profile.steps or any(len(b)!=min(2,len(expected)-2*j) for j,b in enumerate(batches))):
                raise ValueError('Incomplete, duplicated, dropped or reordered training scenes')
            if self.profile.name=='LOGICAL_B9': s['updates']+=self.profile.steps
            if s['updates']!=(s['epoch']+1)*self.profile.steps: raise ValueError('Epoch update boundary')
            s['train']={'ids_sha':digest(actual),'scenes':len(actual),'batches':len(batches),'mode':self.profile.name}
            s['phase']='WAIT_VALIDATION'; self._write(s,'TRAIN_COMPLETE')

    def validate(self,receipt):
        with transaction(self.con):
            s=self.read(); r=dict(receipt); claimed=r.pop('receipt_sha',None)
            if (s['phase']!='WAIT_VALIDATION' or claimed!=digest(r) or r.get('complete') is not True
                or r.get('ids_sha')!=digest(self.profile.ids('development'))
                or r.get('source_sha')!=s['identity_sha'] or r['summary']['scenes']!=self.profile.validation_scenes
                or r['summary']['n_valid']!=self.profile.validation_scenes*3430):
                raise ValueError('Full validation identity/count/receipt required before LAST')
            s['validation']=receipt; s['phase']='VALIDATED'; self._write(s,'VALIDATION_COMPLETE')

    def commit_last(self,last_sha):
        sha_string(last_sha)
        with transaction(self.con):
            s=self.read()
            if s['phase']!='VALIDATED' or s['pending']: raise ValueError('LAST before complete validation')
            s['epoch']+=1; s['last_sha']=last_sha; s['phase']='COMPLETE' if s['epoch']==9 else 'READY'
            self._write(s,'LAST_COMMITTED')

    def fail(self,reason):
        with transaction(self.con):
            s=self.read(); s['phase']='FAILED'; self._write(s,'STOP:'+str(reason))

    def check_restore(self,last_sha,epoch,updates):
        s=self.read()
        if (s['phase'] not in ('READY','COMPLETE') or s['pending'] or (s['last_sha'],s['epoch'],s['updates'])!=(last_sha,epoch,updates)):
            raise ValueError('No budget rollback, incomplete boundary recovery, or orphan adoption')

    def endpoint(self):
        s=self.read()
        return {'fixed_epoch':9,'selected_synthetic_epoch':9 if s['phase']=='COMPLETE' else None,'BEST_used':False,'formal_selected_epoch':None}

    def close(self): self.con.close()

class ActualQuota:
    """One fixed persistent campaign; no reset/refund or user-supplied path."""
    def __init__(self):
        install_guard(); LOCAL.mkdir(parents=True,exist_ok=True)
        self.con=database(LOCAL/'actual_campaign.sqlite')
        self.con.execute('CREATE TABLE IF NOT EXISTS quota(id INTEGER PRIMARY KEY,model TEXT,status TEXT,source TEXT)')

    def perform(self,optimizer,model):
        if model not in ('B0_MATCHED_V2','B1_V2') or type(optimizer) is not torch.optim.AdamW: raise ValueError('Closed E0 campaign')
        source=code_sha()
        with transaction(self.con):
            rows=self.con.execute('SELECT model,status,source FROM quota').fetchall()
            # Every reservation retains its code SHA. A new isolated engine may
            # use repaired code, but can never reset/refund previous consumption.
            # Within an engine, _healthy() independently pins the code identity.
            if (len(rows)>=4 or sum(r[0]==model for r in rows)>=2 or any(r[1]!='COMPLETED' for r in rows)):
                raise PermissionError('Four-step quota exhausted/ambiguous; no retry')
            cursor=self.con.execute('INSERT INTO quota(model,status,source) VALUES(?,?,?)',(model,'RESERVED',source)); key=cursor.lastrowid
        with optimizer_permit(optimizer): optimizer.step()
        with transaction(self.con): self.con.execute('UPDATE quota SET status=? WHERE id=?',('COMPLETED',key))
        return key

    def report(self):
        rows=self.con.execute('SELECT model,status,source FROM quota ORDER BY id').fetchall()
        return {'hard_limit':4,'reserved':len(rows),'SYNTHETIC_OPTIMIZER_STEPS':sum(s=='COMPLETED' for _,s,_ in rows),'FORMAL_OPTIMIZER_STEPS':0,'events':rows}
