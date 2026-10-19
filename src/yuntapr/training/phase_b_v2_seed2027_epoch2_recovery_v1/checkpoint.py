"""Formal LAST envelope + P1 registered same-object, same-byte read algorithm.

Only registered checkpoints of this campaign can be inspected and adopted after
a verified clean pause. Failed transactions cannot use this continuation path.
"""
from __future__ import annotations
from contextlib import contextmanager
from copy import deepcopy
import hashlib
import io
import json
import os
from pathlib import Path
import re
import shutil
import torch
from yuntapr.experimental.phase_b_v2_runner_candidate.checkpoint import SyntheticStore
from yuntapr.experimental.phase_b_v2_runner_candidate.optimizer import check_finite
from yuntapr.experimental.phase_b_v2_runner_candidate import rng
from yuntapr.experimental.phase_b_v2_formal_integration_candidate.checkpoint import Schedule
from yuntapr.experimental.phase_b_v2_full_payload_integrity.winio import ReadHandle
from yuntapr.experimental.phase_b_v2_p1_integration_candidate.checkpoint import pairs
from yuntapr.experimental.phase_b_v2_ablations.config import learning_rate_prefix
from yuntapr.training.phase_a_protocol import state_digest
from .protocol import ROOT,LIMITS,LOCAL,CAMPAIGN,STEPS,TRAIN_N,DEV_N,TOTAL,SEED,digest,epoch_order,atomic_json

SCHEMA=f'FORMAL_PHASE_B_V2_SEED{SEED}_EPOCH2_RECOVERY_LAST_v1'
def sha(raw):return hashlib.sha256(raw).hexdigest()

def lexical(path: Path,root: Path) -> None:
    text=os.fspath(path).replace('\\','/')
    if ('2025' in text or not path.is_absolute() or '..' in text.split('/') or
        not path.is_relative_to(root) or path.parent!=root or root==LOCAL or not root.is_relative_to(LOCAL)):
        raise PermissionError('ONLY_OWNED_CURRENT_RUN_CHECKPOINT_CHILD')

class Contract:
    def __init__(self,identity,model,optimizer_template,initial_sha,train_ids,dev_ids):
        self.identity,self.model,self.opt,self.initial,self.train_ids,self.dev_ids=identity,model,optimizer_template,initial_sha,train_ids,dev_ids
        self.key=digest(identity)
    def validate(self,p):
        fields={'schema','identity','model','optimizer','scheduler','rng','initial_sha','epoch','update','train','validation','parent_last_sha','quota'}
        if type(p) is not dict or set(p)!=fields or p['schema']!=SCHEMA or p['identity']!=self.identity:
            raise ValueError('FORMAL_CHECKPOINT_COMPLETE_IDENTITY')
        epoch,u=p['epoch'],p['update']
        if type(epoch) is not int or not 1<=epoch<=9 or type(u) is not int or u!=epoch*STEPS or p['initial_sha']!=self.initial:
            raise ValueError('FORMAL_COMPLETE_EPOCH_UPDATE_INITIAL_IDENTITY')
        if (epoch==1 and p['parent_last_sha'] is not None) or (epoch>1 and not re.fullmatch('[0-9a-f]{64}',p['parent_last_sha'] or '')):
            raise ValueError('FORMAL_PARENT_LAST_CHAIN')
        train=p['train']
        if (train['scenes']!=TRAIN_N or train['batches']!=STEPS or train['ids_sha']!=digest(epoch_order(self.train_ids,epoch)) or
            train['n_valid']!=TRAIN_N*3430):raise ValueError('COMPLETE_TRAIN_COVERAGE_RECEIPT')
        report=dict(p['validation']);receipt=report.pop('receipt_sha',None)
        if (receipt!=digest(report) or not report['complete'] or report['source_sha']!=self.key or
            report['ids_sha']!=digest(self.dev_ids) or report['summary']['scenes']!=DEV_N or report['summary']['n_valid']!=DEV_N*3430):
            raise ValueError('COMPLETE_DEVELOPMENT_RECEIPT')
        q=p['quota'];run=self.identity['run_id']
        row=next((r for r in q['runs'] if r['id']==run),None)
        from .accounting import validate as validate_accounting
        validate_accounting(q,complete_transaction=True)
        if q['campaign']!=CAMPAIGN or q['limit']!=TOTAL or not row or row['updates']!=u:
            raise ValueError('PERSISTENT_ACTUAL_UPDATE_RECEIPT')
        if (q['old_ancestor_receipt_sha256']!=self.identity['code']['failed_ancestor_sha256']
            or q['old_campaign_reserved']!=85783 or q['old_campaign_returned_verified']!=85782 or q['abandoned_old_updates']!=75327):
            raise ValueError('NONREFUNDABLE_RECOVERY_ANCESTRY')
        m=p['model']
        if m.keys()!=self.model.keys():raise ValueError('MODEL_STATE_KEYS')
        for name,value in m.items():
            expected=self.model[name]
            if not isinstance(value,torch.Tensor) or value.device.type!='cpu' or (tuple(value.shape),str(value.dtype))!=expected:
                raise ValueError('MODEL_STATE_SHAPE_DTYPE')
        schedule=Schedule();schedule.load_state_dict(p['scheduler'])
        if schedule.completed!=u:raise ValueError('SCHEDULER_UPDATE_BOUNDARY')
        opt=p['optimizer']
        if set(opt)!= {'state','param_groups'} or len(opt['param_groups'])!=len(self.opt['param_groups']):raise ValueError('ADAMW_STATE_GROUPS')
        for group,expected in zip(opt['param_groups'],self.opt['param_groups'],strict=True):
            if set(group)!=set(expected) or any(group[k]!=expected[k] for k in expected if k!='lr') or group['lr']!=learning_rate_prefix(u):
                raise ValueError('ADAMW_PARAMETERS_OR_LR')
        ids=[i for g in opt['param_groups'] for i in g['params']]
        if set(opt['state'])!=set(ids) or len(set(ids))!=len(ids):raise ValueError('ADAMW_COVERAGE')
        for i,state in opt['state'].items():
            if set(state)!= {'step','exp_avg','exp_avg_sq'} or state['step'].shape!=() or state['step'].dtype!=torch.float32 or float(state['step'])!=u:
                raise ValueError('ADAMW_STEP_IDENTITY')
            for k in ('exp_avg','exp_avg_sq'):
                if state[k].dtype!=torch.float32 or tuple(state[k].shape)!=self.opt['_shapes'][i]:raise ValueError('ADAMW_MOMENT_SIGNATURE')
            if bool((state['exp_avg_sq']<0).any()):raise ValueError('NEGATIVE_SECOND_MOMENT')
        check_finite(m);check_finite(opt);rng.validate(p['rng'])

class Store(SyntheticStore):
    """Reuse atomic writer; never call old path-reopening reader or constructor."""
    def __init__(self,root: Path,contract):
        if not root.is_absolute() or not root.is_relative_to(LOCAL) or root==LOCAL or '2025' in str(root) or '..' in root.parts:
            raise PermissionError('FORMAL_STORE_ROOT_LEXICAL')
        root.mkdir(exist_ok=False)
        with ReadHandle(str(root),directory=True) as h:
            if os.path.normcase(h.final_path)!=os.path.normcase(str(root)):raise PermissionError('STORE_FINAL_ROOT_IDENTITY')
        self.root,self.contract=root,contract;self.registered={};self.failed=False
        self.directories=[]
        try:
            chain=[];parent=root
            while True:
                chain.append(parent)
                if parent==ROOT:break
                parent=parent.parent
            for path in reversed(chain):
                handle=ReadHandle(str(path),directory=True)
                if os.path.normcase(handle.final_path)!=os.path.normcase(str(path)):
                    handle.close();raise PermissionError('OWNED_CHECKPOINT_ANCESTOR_IDENTITY')
                self.directories.append(handle)
        except BaseException:
            for handle in reversed(self.directories):handle.close()
            raise
    @contextmanager
    def io(self):yield
    def _path(self,name):
        path=super()._path(name);lexical(path,self.root);return path
    def _bytes(self,path,maximum,expected=None):
        lexical(path,self.root)
        with ReadHandle(str(path),payload=True) as h:
            if os.path.normcase(h.final_path)!=os.path.normcase(str(path)) or (expected is not None and h.before!=expected):
                raise ValueError('REGISTERED_OBJECT_IDENTITY')
            if not 0<h.before['size']<=maximum:raise ValueError('CHECKPOINT_SIZE_BOUND')
            buf=bytearray(h.before['size']);n=0
            while n<len(buf):
                count=h.readinto(memoryview(buf)[n:])
                if not count:raise EOFError('CHECKPOINT_TRUNCATED')
                n+=count
            if h.readinto(bytearray(1)) or h.snapshot()!=h.before:raise ValueError('CHECKPOINT_CONCURRENT_CHANGE')
            return bytes(buf),dict(h.before)
    def save(self,name,payload,*,fault=None):
        if self.failed:raise PermissionError('NO_FAILED_CHECKPOINT_RETRY')
        try:
            self._path(name);self.contract.validate(payload)
            if shutil.disk_usage(self.root).free<LIMITS['minimum_disk_free_bytes']:raise OSError('CHECKPOINT_DISK_ADMISSION')
            buffer=io.BytesIO();torch.save(payload,buffer)
            if buffer.tell()>LIMITS['max_checkpoint_bytes']:raise MemoryError('CHECKPOINT_SERIALIZED_BOUND')
            expected=sha(buffer.getvalue());buffer.close()
            ref=super().save(name,payload,fault=fault);blob=self._path(name)
            raw,meta=self._bytes(blob,LIMITS['max_checkpoint_bytes'])
            old,_=self._bytes(ref,16384);old=json.loads(old,object_pairs_hook=pairs)
            if old!={'schema':'SYNTHETIC_B9_V0_CANDIDATE_v1','filename':blob.name,'bytes':len(raw),'sha256':expected} or sha(raw)!=expected:
                raise ValueError('SAVE_REGISTER_BYTE_IDENTITY')
            row=dict(schema=SCHEMA,filename=blob.name,bytes=len(raw),sha256=expected,contract_sha=self.contract.key,campaign=CAMPAIGN)
            atomic_json(ref,row);refraw,refmeta=self._bytes(ref,16384)
            self.registered[str(ref)]=dict(reference=ref,payload=blob,receipt_sha=sha(refraw),payload_sha=expected,
                                          receipt_object=refmeta,payload_object=meta)
            # Durable registry exists before inspection/epoch LAST acceptance.
            atomic_json(self.root/(name+'.registration.json'),dict(reference_name=ref.name,payload_name=blob.name,
                receipt_sha256=sha(refraw),payload_sha256=expected,receipt_object=refmeta,payload_object=meta,
                contract_sha=self.contract.key,campaign=CAMPAIGN))
            return ref
        except BaseException:
            self.failed=True;raise
    def read(self,ref):
        if self.failed:raise PermissionError('FAILED_STORE_NO_ORPHAN_ADOPTION')
        try:
            lexical(ref,self.root)
            if str(ref) not in self.registered:raise PermissionError('ONLY_THIS_EXECUTION_REGISTERED_CHECKPOINT')
            reg=self.registered[str(ref)];raw,_=self._bytes(ref,16384,reg['receipt_object'])
            if sha(raw)!=reg['receipt_sha']:raise ValueError('RECEIPT_SHA')
            row=json.loads(raw,object_pairs_hook=pairs)
            expected=dict(schema=SCHEMA,filename=reg['payload'].name,bytes=reg['payload_object']['size'],sha256=reg['payload_sha'],contract_sha=self.contract.key,campaign=CAMPAIGN)
            if row!=expected:raise ValueError('RECEIPT_FORMAT_SOURCE')
            verified,_=self._bytes(reg['payload'],LIMITS['max_checkpoint_bytes'],reg['payload_object'])
            if len(verified)!=row['bytes'] or sha(verified)!=row['sha256']:raise ValueError('CHECKPOINT_SAME_BYTES_SHA')
            result=torch.load(io.BytesIO(verified),map_location='cpu',weights_only=True)
            self.contract.validate(result);return result
        except BaseException:self.failed=True;raise
    def receipt(self,ref):
        reg=self.registered[str(ref)]
        return dict(reference_name=ref.name,payload_sha256=reg['payload_sha'],receipt_sha256=reg['receipt_sha'],
                    bytes=reg['payload_object']['size'],same_bytes_deserialized=True,weights_only=True,
                    validated_before_last=True,power_loss_directory_durability='NOT_VERIFIED')
    def close(self):
        for handle in reversed(self.directories):handle.close()
        self.directories.clear()
    def restore(self,*args,**kwargs):raise PermissionError('NEW_LAST_BOUND_HUMAN_RECOVERY_DECISION_REQUIRED')

    @classmethod
    def reopen_owned(cls,root,contract,epoch,last_sha):
        """Only a clean PAUSED same-campaign LAST selected by persistent ledger."""
        lexical(root/'sentinel',root)
        result=object.__new__(cls)
        result.root,result.contract,result.failed,result.registered,result.directories=root,contract,False,{},[]
        try:
            chain=[];parent=root
            while True:
                chain.append(parent)
                if parent==ROOT:break
                parent=parent.parent
            for path in reversed(chain):
                h=ReadHandle(str(path),directory=True);result.directories.append(h)
                if os.path.normcase(h.final_path)!=os.path.normcase(str(path)):raise ValueError('OWNED_RESUME_PARENT')
            if epoch:
                regraw,_=result._bytes(root/f'LAST_epoch_{epoch:02d}.registration.json',16384)
                reg=json.loads(regraw,object_pairs_hook=pairs)
                expected_name=f'LAST_epoch_{epoch:02d}.pt';ref=root/f'LAST_epoch_{epoch:02d}.ref.json'
                if (reg['payload_name']!=expected_name or reg['reference_name']!=ref.name
                        or reg['payload_sha256']!=last_sha or reg['contract_sha']!=contract.key or reg['campaign']!=CAMPAIGN):
                    raise ValueError('EXACT_PAUSED_LAST_REGISTRATION')
                result.registered[str(ref)]=dict(reference=ref,payload=root/expected_name,
                    payload_sha=last_sha,receipt_sha=reg['receipt_sha256'],
                    receipt_object=reg['receipt_object'],payload_object=reg['payload_object'])
            return result
        except BaseException:result.close();raise
