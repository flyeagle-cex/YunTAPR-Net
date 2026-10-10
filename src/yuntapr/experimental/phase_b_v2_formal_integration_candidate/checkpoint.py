"""Reuse atomic blob/receipt transport; bind the new B9 candidate envelope."""
from __future__ import annotations
from contextlib import contextmanager
import json
import os
import shutil
from pathlib import Path
import torch
from yuntapr.experimental.phase_b_v2_runner_candidate.checkpoint import SyntheticStore
from yuntapr.experimental.phase_b_v2_runner_candidate.optimizer import PrefixSchedule, check_finite
from yuntapr.experimental.phase_b_v2_runner_candidate import rng
from yuntapr.experimental.phase_b_v2_ablations.config import learning_rate_prefix
from .protocol import digest, sha_string, Profile
from .storage import Workspace, LOCAL
from .access import RejectingAuthority

SCHEMA='ISOLATED_FORMAL_INTEGRATION_B9_v1'

class Store(SyntheticStore):
    def __init__(self,workspace: Workspace):
        if type(workspace) is not Workspace: raise TypeError('Managed synthetic workspace')
        self.root=workspace.root
    @contextmanager
    def io(self): yield
    def save(self,name,payload,*,fault=None):
        def size(x):
            if isinstance(x,torch.Tensor):return x.numel()*x.element_size()
            if isinstance(x,dict):return sum(size(v) for v in x.values())
            if isinstance(x,(tuple,list)):return sum(size(v) for v in x)
            return 0
        total=size(payload)
        if total>256*1024**2 or shutil.disk_usage(self.root).free<2*total+64*1024**2:
            raise RuntimeError('Bounded checkpoint storage admission failed')
        return super().save(name,payload,fault=fault)
    def read(self,reference):
        # No resolve/stat of a supplied external path, even in rejection tests.
        if type(reference) not in (Path,type(self.root)) or reference.parent!=self.root:
            raise PermissionError('Only owned synthetic references')
        return super().read(reference)
    def resume_real(self,*args,**kwargs): RejectingAuthority().verify_resume(*args,**kwargs)

class Schedule(PrefixSchedule):
    def load_state_dict(self,state):
        expected=self.state_dict(); expected['completed']=state.get('completed')
        if state!=expected or type(state['completed']) is not int or not 0<=state['completed']<=47052:
            raise ValueError('S0 identity/range mismatch')
        self.completed=state['completed']

def validate(payload,identity,model_template,optimizer_template,initial_sha):
    required={'schema','identity','model','optimizer','scheduler','rng','initial_sha','epoch','update','train','validation','parent_last_sha','quota'}
    if type(payload) is not dict or set(payload)!=required or payload['schema']!=SCHEMA or payload['identity']!=identity:
        raise ValueError('Schema/code/protocol/data/seed/arm/authority ancestor mismatch')
    profile=Profile(**identity['profile']); epoch=payload['epoch']; u=payload['update']
    if (profile.name!='SYNTHETIC_SMALL' or type(epoch) is not int or not 1<=epoch<=9
        or type(u) is not int or u!=epoch*profile.steps or payload['initial_sha']!=initial_sha):
        raise ValueError('Complete synthetic epoch/update/fresh boundary required')
    sha_string(initial_sha)
    if epoch==1 and payload['parent_last_sha'] is not None: raise ValueError('Unexpected parent LAST')
    if epoch>1: sha_string(payload['parent_last_sha'])
    train=payload['train']
    if train.get('scenes')!=profile.train_scenes or train.get('batches')!=profile.steps or train.get('mode')!=profile.name:
        raise ValueError('Training completion receipt')
    from yuntapr.experimental.phase_b_v2_integration.controls import synthetic_epoch_order
    if train['ids_sha']!=digest(synthetic_epoch_order(profile.ids('train'),identity['run']['seed'],epoch-1)):
        raise ValueError('Training order identity')
    report=dict(payload['validation']); receipt=report.pop('receipt_sha',None)
    if (receipt!=digest(report) or report.get('complete') is not True or report.get('source_sha')!=digest(identity)
        or report.get('ids_sha')!=digest(profile.ids('development'))
        or report['summary']['scenes']!=profile.validation_scenes or report['summary']['n_valid']!=profile.validation_scenes*3430):
        raise ValueError('Validation completion identity')
    quota=payload['quota']
    if quota.get('FORMAL_OPTIMIZER_STEPS')!=0 or quota.get('hard_limit')!=4 or not 1<=quota.get('reserved',0)<=4:
        raise ValueError('Separate non-formal resource quota receipt')
    model=payload['model']
    if model.keys()!=model_template.keys(): raise ValueError('Model keys')
    for k,v in model.items():
        if not isinstance(v,torch.Tensor) or v.shape!=model_template[k].shape or v.dtype!=model_template[k].dtype:
            raise ValueError('Model tensor signature')
    schedule=Schedule(); schedule.load_state_dict(payload['scheduler'])
    if schedule.completed!=u: raise ValueError('Scheduler boundary')
    opt=payload['optimizer']
    if set(opt)!= {'state','param_groups'} or len(opt['param_groups'])!=len(optimizer_template['param_groups']): raise ValueError('Optimizer fields/groups')
    for group,template in zip(opt['param_groups'],optimizer_template['param_groups']):
        if set(group)!=set(template) or any(group[k]!=template[k] for k in template if k!='lr') or group['lr']!=learning_rate_prefix(u):
            raise ValueError('AdamW grouping/hyperparameters/LR')
    ids=[i for g in opt['param_groups'] for i in g['params']]
    if len(set(ids))!=len(ids) or set(opt['state'])!=set(ids): raise ValueError('Missing optimizer state')
    for i,state in opt['state'].items():
        if set(state)!= {'step','exp_avg','exp_avg_sq'}: raise ValueError('Missing moments')
        if state['step'].dtype!=torch.float32 or state['step'].shape!=() or float(state['step'])!=u: raise ValueError('AdamW step identity')
        for key in ('exp_avg','exp_avg_sq'):
            if state[key].dtype!=torch.float32 or tuple(state[key].shape)!=optimizer_template['_shapes'][i]: raise ValueError('Moment shape/dtype')
        if bool((state['exp_avg_sq']<0).any()): raise ValueError('Negative second moment')
    check_finite(model); check_finite(opt); rng.validate(payload['rng'])
