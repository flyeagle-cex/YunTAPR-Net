"""Shared B1/B0-Matched Phase-A semantics. Updates are owned by entrypoints."""
from dataclasses import dataclass,asdict
from pathlib import Path
import datetime,json,math,os,uuid
import torch,yaml
from yuntapr.contracts.loader import REPO_ROOT,sha256
from yuntapr.data.dataset_b1 import FREEZE,SCALER_SHA,PINS,load_records,load_frames
from yuntapr.training.phase_a_protocol import (parameter_groups,lr_for_update,epoch_permutation,
    ValidationSelection,state_digest,capture_rng,restore_rng,head_pin)
from yuntapr.training.formal_phase_a import precision_check,atomic_json,assert_determinism
from yuntapr.training.formal_phase_b import compatible_states
from yuntapr.losses.total_loss import b0_core_loss

CONFIG=Path('config/training/b1_b0_matched_phase_a_protocol_v1.yaml')
TRAIN=10455; VAL=10501; STEPS=5228; W=5228; U=261400
ROOTS={m:Path(r'F:\pytorch\Research\outputs\formal_training')/leaf for m,leaf in
       [('B1','b1_phase_a'),('B0_MATCHED','b0_matched_phase_a')]}
COUNTS={'B1':{'DECAY_GROUP':4325232,'NO_DECAY_GROUP':6529,'total':4331761},
        'B0_MATCHED':{'DECAY_GROUP':4322832,'NO_DECAY_GROUP':6529,'total':4329361}}


def implementation_hashes(root=REPO_ROOT):
    # Include inherited dependency bytes: future code changes require a new authorization.
    paths=list((Path(root)/'src/yuntapr').rglob('*.py'))
    paths += [Path(root)/'scripts'/n for n in ('train_b1_phase_a_v1.py','train_b0_matched_phase_a_v1.py','paired_phase_a_entry.py')]
    return {p.relative_to(root).as_posix():sha256(p) for p in sorted(paths)}


def protocol_body(val_batch,identity):
    return {'version':'v1','status':'RESEARCHER_APPROVED_ENGINEERING_CLOSURE',
        'models':['B0_MATCHED','B1'],'identity':identity,'normalization_sha256':SCALER_SHA,
        'B0_MATCHED_CONTROL_NORMALIZATION':'USE_FROZEN_B1_SHARED_SCALER',
        'input':{'B1':[6,501,501],'B0_MATCHED':[1,501,501],'offset_minutes':[60,50,40,30,20,10],
                 'ordering':'OLDEST_TO_LATEST','missing_policy':'M1_STRICT_COMPLETE_REJECT_NO_FALLBACK'},
        'architecture':{'channels':[48,96,192,256],'heads':'DIRECT_1X1_48_TO_1_AND_32','SP04':'UNCHANGED',
                        'parameters':COUNTS,'only_shape_changes':['backbone.enc0.conv1.weight','backbone.enc0.skip.weight']},
        'initialization':{'seed':2026,'independent_reseed':True,'copy_same_name_same_shape_only':True,'historical_checkpoint_transfer':False},
        'loss':{'occurrence_threshold':.1,'occurrence_strict_greater':True,'focal_alpha':.5,'focal_gamma':2.,
                'quantiles':32,'tau':'(i-0.5)/32','formula':'L_occ+L_qr','quantile_axis_reduction':'mean','KD':0,'external':False},
        'optimizer':{'name':'AdamW','betas':[.9,.999],'eps':1e-8,'weight_decay':1e-4,'decay':'Conv2d.weight_only',
                     'amsgrad':False,'maximize':False,'capturable':False,'differentiable':False,'foreach':False,'fused':False},
        'gradient':{'global_clip_norm':5.,'error_if_nonfinite':True},
        'scheduler':{'base_lr':1e-4,'min_lr':1e-6,'W':W,'U':U,'fixed_horizon_epochs':50,
                     'rule':'ONE_BASED_LINEAR_WARMUP_THEN_FIXED_50_EPOCH_COSINE','apply_before_optimizer_step':True,
                     'min_lr_lower_bound':'COSINE_ONLY'},
        'training':{'scenes':TRAIN,'physical_batch':2,'accumulation':1,'steps_per_epoch':STEPS,'drop_last':False,
                    'tail_policy':'ALLOW_SINGLETON_NO_DROP_NO_DUPLICATE','max_epochs':50,
                    'epoch_seed':'2026+zero_based_epoch_index','every_scene_exactly_once':True},
        'validation':{'scenes':VAL,'batch':val_batch,'fixed_order':True,'shuffle':False,'drop_last':False,
                      'metric':'global_val_core_loss','accumulation':'(S_occ+S_qr)/N_valid_FLOAT64_RAW_SUM',
                      'BEST':'STRICT_LOWER_EARLIEST_TIE','early_stop_patience':8,'early_stop_min_delta':1e-4},
        'precision':{'forward':'BF16','parameters':'FP32','raw_quantiles':'FP32','transform_physical_pinball':'FP64','GradScaler':False,'TF32':False},
        'loader':{'num_workers':2,'pin_memory':False,'persistent_workers':False,'prefetch_factor':1,
                  'per_worker_staging':True,'max_temporary_bytes_per_worker':734003200,'verify_sha256_before_decode':True},
        'checkpoint':{'roots':{m:str(p) for m,p in ROOTS.items()},'boundary':'COMPLETED_TRAIN_AND_VALIDATION_EPOCH_ONLY',
                      'resume':'VERIFIED_LAST_TO_NEXT_COMPLETE_EPOCH','provenance_before_state_application':True,
                      'Git_binary_allowed':False},
        'authorization':{'B1_TRAINING_AUTHORIZED':False,'B0_MATCHED_CONTROL_TRAINING_AUTHORIZED':False,
                         'separate_researcher_authorization_required':True,'2025_raw_access':False}}


@dataclass
class RunnerContract:
    protocol:dict
    protocol_sha256:str
    records:dict
    code_hashes:dict
    root:Path

    @classmethod
    def load(cls,root=REPO_ROOT):
        root=Path(root);p=root/CONFIG;body=yaml.safe_load(p.read_text(encoding='utf-8'))
        batch=body.get('validation',{}).get('batch')
        if type(batch)!=int or batch<1 or body!=protocol_body(batch,body.get('identity')):raise ValueError('Frozen protocol altered')
        registry=json.loads((root/'config/training/b1_b0_matched_phase_a_freeze_registry_v1.json').read_text())
        if sha256(p)!=registry['protocol_sha256']:raise ValueError('Protocol registry hash mismatch')
        for name,ref in body['identity'].items():
            source=Path(ref['path']); source=source if source.is_absolute() else root/source
            if sha256(source)!=ref['sha256']:raise ValueError('Provenance identity mismatch: '+name)
        records={(m,y):load_records(m,y,root) for m in ('B0_MATCHED','B1') for y in (2023,2024)}
        for y in (2023,2024):
            left,right=records['B0_MATCHED',y],records['B1',y]
            keys=('sample_id','window_start','analysis_time','imerg_day_path','imerg_index','imerg_sha256','target_valid_yunnan_cells')
            if [[r[k] for k in keys] for r in left]!=[[r[k] for k in keys] for r in right]:raise ValueError('Paired sample/target identities differ')
        return cls(body,sha256(p),records,implementation_hashes(root),root)


@dataclass(frozen=True)
class Authorization:
    value:dict
    sha256:str

    @classmethod
    def load(cls,path,expected_sha,contract,model):
        # Called before model construction, dataset construction or raw source access.
        if not path or not expected_sha:raise PermissionError('Separate researcher authorization required')
        p=Path(path).resolve()
        if not p.is_relative_to(contract.root.resolve()) or p.suffix!='.json':
            raise PermissionError('Authorization must be a repository JSON artifact; raw/checkpoint paths rejected before open')
        if sha256(p)!=expected_sha:raise PermissionError('Authorization SHA mismatch')
        v=json.loads(p.read_text(encoding='utf-8'))
        expected={'scope':'FORMAL_PAIRED_PHASE_A','model':model,'AUTHORIZED':True,
                  'protocol_sha256':contract.protocol_sha256,'code_hashes':contract.code_hashes,
                  'normalization_sha256':SCALER_SHA,'train_manifest_sha256':PINS[model,2023],
                  'validation_manifest_sha256':PINS[model,2024], 'max_epochs':50,'2025_raw_access':False}
        if model not in ROOTS or any(v.get(k)!=x for k,x in expected.items()) or not v.get('researcher_approval_reference'):
            raise PermissionError('Explicit model-specific authorization provenance mismatch')
        return cls(v,expected_sha)


def optimizer_for(model,kind):
    groups,evidence=parameter_groups(model,check_counts=False);head_pin(model)
    if evidence['counts']!=COUNTS[kind]:raise ValueError('Parameter inventory mismatch')
    return torch.optim.AdamW(groups,lr=1e-4,betas=(.9,.999),eps=1e-8,amsgrad=False,maximize=False,
                            capturable=False,differentiable=False,foreach=False,fused=False),evidence


def batch_plan(epoch):
    order=epoch_permutation(epoch,count=TRAIN).tolist()
    return order,[order[i:i+2] for i in range(0,TRAIN,2)]


class EpochCoverage:
    def __init__(self,epoch):self.order,self.plan=batch_plan(epoch-1);self.seen=[];self.updates=0;self.denominator=0
    def add(self,indices,denominator):
        if self.updates>=STEPS or list(indices)!=self.plan[self.updates] or denominator!=len(indices)*3430:raise ValueError('Epoch coverage/order/denominator mismatch')
        self.seen.extend(indices);self.updates+=1;self.denominator+=denominator
    def complete(self):
        if self.seen!=self.order or self.updates!=STEPS or self.denominator!=TRAIN*3430:raise ValueError('Incomplete epoch boundary')
        return {'samples':TRAIN,'updates':STEPS,'denominator':self.denominator,'ordered_indices_sha256':state_digest(self.order),
                'exactly_once':True,'tail_size':1,'tail_denominator':3430}


def forward_loss(model,batch):
    raw=[];hook=model.heads.quantile.register_forward_hook(lambda m,i,o:raw.append(o.dtype))
    try:
        with torch.autocast(batch.x_b13.device.type,dtype=torch.bfloat16):
            out=model(batch.x_b13,batch.b13_valid_mask)
            loss=b0_core_loss(out,batch.y_imerg,batch.imerg_valid_mask,batch.yunnan_eval_mask,
                              focal_alpha=.5,focal_gamma=2.,quantile_axis_reduction='mean')
    finally:hook.remove()
    precision_check(model,raw[0],out)
    if loss.batch_skipped or loss.conditional_quantile.dtype!=torch.float64 or not torch.isfinite(loss.total):raise FloatingPointError('Loss invariant failed')
    if not bool(((out.rain_prob>=0)&(out.rain_prob<=1)).all()):raise FloatingPointError('Probability support failed')
    if loss.valid_supervised_count!=len(batch.sample_ids)*3430:raise ValueError('Actual denominator failed')
    return out,loss


def forward_backward_clip(model,optimizer,batch,update):
    assert_determinism();optimizer.zero_grad(set_to_none=True)
    lr=lr_for_update(update,steps_per_epoch=STEPS)
    for group in optimizer.param_groups:group['lr']=lr
    out,loss=forward_loss(model,batch);loss.total.backward()
    if any(p.grad is None or not torch.isfinite(p.grad).all() for p in model.parameters()):raise FloatingPointError('Nonfinite/missing gradient')
    pre=torch.nn.utils.clip_grad_norm_(model.parameters(),5.,error_if_nonfinite=True)
    post=torch.sqrt(sum(p.grad.detach().double().square().sum() for p in model.parameters()))
    if not torch.isfinite(post) or post>5.00001:raise FloatingPointError('Gradient clip failed')
    return {'LR':lr,'update':update,'actual_denominator':loss.valid_supervised_count,'loss':float(loss.total.detach()),
            'pre_clip_norm':float(pre),'post_clip_norm':float(post),'clipped':bool(pre>5),
            'quantile_crossing':0,'support_violation':0,'nonfinite':0,'probability_in_unit_interval':True,
            'raw_quantile_dtype':'torch.float32','quantile_pinball_dtype':'torch.float64'},out


def checkpoint_expected(contract,auth,kind,runid,environment,groups,initial):
    return {'scope':'FORMAL_PAIRED_PHASE_A','model':kind,'run_id':runid,'FORMAL_TRAINING_AUTHORIZED':True,
            'protocol_sha256':contract.protocol_sha256,'authorization_sha256':auth.sha256,
            'identity':contract.protocol['identity'],'code_hashes':contract.code_hashes,'environment':environment,
            'optimizer_groups':groups,'paired_initialization':initial,'normalization_sha256':SCALER_SHA,
            'EPOCH_BOUNDARY_RESUME_ONLY':True}


def payload_for(model,optimizer,expected,selection,epoch,coverage,validation,training=None):
    payload={**expected,'completed_epoch':epoch,'global_update':epoch*STEPS,'last_applied_lr':lr_for_update(epoch*STEPS,steps_per_epoch=STEPS),
             'training_completed':True,'validation_completed':True,'validation_samples':VAL,'coverage':coverage,
             'selection':asdict(selection),'validation':validation,'training_metrics':training,'model_state_dict':model.state_dict(),
             'optimizer_state_dict':optimizer.state_dict(),'rng_states':capture_rng()}
    for n in ('model_state_dict','optimizer_state_dict','rng_states'):payload[n+'_sha256']=state_digest(payload[n])
    return payload


def validate_payload(p,expected):
    for k,v in expected.items():
        if p.get(k)!=v:raise ValueError('Provenance before state application: '+k)
    ep=p.get('completed_epoch')
    if type(ep)!=int or not 1<=ep<=50 or p.get('global_update')!=ep*STEPS or p.get('training_completed') is not True or p.get('validation_completed') is not True or p.get('validation_samples')!=VAL:
        raise ValueError('Completed Train+Validation epoch boundary required')
    coverage=EpochCoverage(ep)
    for ix in coverage.plan:coverage.add(ix,len(ix)*3430)
    if p.get('coverage')!=coverage.complete() or p.get('last_applied_lr')!=lr_for_update(ep*STEPS,steps_per_epoch=STEPS):raise ValueError('Boundary coverage/LR mismatch')
    s=ValidationSelection(**p['selection'])
    if s.completed_epoch!=ep or type(s.selected_checkpoint_epoch)!=int or not 1<=s.selected_checkpoint_epoch<=ep or type(s.non_improvement_count)!=int or not 0<=s.non_improvement_count<=8:
        raise ValueError('Invalid selection boundary')
    if any(not math.isfinite(x) for x in (s.best_checkpoint_value,s.early_stop_best,p['validation']['global_val_core_loss'])):raise ValueError('Invalid finite selection metric')
    if p['validation']['D_valid']!=VAL*3430 or p['validation']['global_val_core_loss']!=(p['validation']['S_occ']+p['validation']['S_qr'])/(VAL*3430):raise ValueError('Full global validation required')
    if expected.get('TEST_FIXTURE_ONLY') is not True:
        t=p.get('training_metrics')
        if not t or t.get('N_valid')!=TRAIN*3430 or t.get('global_core_loss')!=(t['S_occ']+t['S_qr'])/(TRAIN*3430):raise ValueError('Complete training numerators required')
    for n in ('model_state_dict','optimizer_state_dict','rng_states'):
        if state_digest(p[n])!=p[n+'_sha256']:raise ValueError('State checksum mismatch: '+n)
    def finite(v):
        if isinstance(v,torch.Tensor) and not torch.isfinite(v).all():raise ValueError('Nonfinite checkpoint')
        if isinstance(v,dict):
            for x in v.values():finite(x)
        if isinstance(v,(tuple,list)):
            for x in v:finite(x)
    finite(p['model_state_dict']);finite(p['optimizer_state_dict'])
    # Independent RNG compatibility validation precedes global RNG mutation.
    import random,numpy as np
    r=p['rng_states'];random.Random().setstate(r['python']);np.random.RandomState().set_state(r['numpy']);torch.Generator().set_state(r['torch_cpu'].cpu())
    if len(r['torch_cuda'])!=torch.cuda.device_count():raise ValueError('CUDA RNG device count changed')
    for i,state in enumerate(r['torch_cuda']):torch.Generator(device=f'cuda:{i}').set_state(state.cpu())
    return s


def load_checkpoint(identity,expected,model,optimizer,*,fixture_root=None):
    root=Path(fixture_root) if fixture_root is not None else ROOTS[expected['model']]
    p=Path(identity['absolute_local_path']).resolve()
    if p.parent!=root.resolve()/expected['run_id'] or p.name!=f"epoch_{identity['epoch']:03d}.pt" or p.stat().st_size!=identity['bytes'] or sha256(p)!=identity['sha256']:raise ValueError('Checkpoint file identity mismatch before deserialization')
    data=torch.load(p,map_location='cpu',weights_only=False);validate_payload(data,expected)
    if identity['epoch']!=data['completed_epoch'] or identity['global_update']!=data['global_update']:raise ValueError('Registry boundary mismatch')
    compatible_states(data,model,optimizer)
    model.load_state_dict(data['model_state_dict'],strict=True);optimizer.load_state_dict(data['optimizer_state_dict']);restore_rng(data['rng_states'])
    return data


def save_checkpoint(public,payload,expected,registry,selected):
    validate_payload(payload,expected);local=(ROOTS[expected['model']]/expected['run_id']).resolve();local.mkdir(parents=True,exist_ok=True)
    dest=local/f"epoch_{payload['completed_epoch']:03d}.pt"
    if dest.exists():raise FileExistsError('Immutable completed checkpoint exists')
    temporary=local/(dest.name+'.tmp_'+uuid.uuid4().hex)
    with temporary.open('xb') as f:torch.save(payload,f);f.flush();os.fsync(f.fileno())
    digest=sha256(temporary);probe=torch.load(temporary,map_location='cpu',weights_only=False);validate_payload(probe,expected)
    if state_digest(probe)!=state_digest(payload):raise ValueError('Checkpoint roundtrip mismatch')
    del probe;os.replace(temporary,dest)
    identity={'absolute_local_path':str(dest),'bytes':dest.stat().st_size,'sha256':sha256(dest),
              'epoch':payload['completed_epoch'],'global_update':payload['global_update'],
              'protocol_sha256':expected['protocol_sha256'],'normalization_sha256':SCALER_SHA,
              'model':expected['model'],'binary_not_committed':True}
    if identity['sha256']!=digest:raise ValueError('Atomic checkpoint changed')
    registry={**registry,'LAST':identity,'BEST':identity if selected else registry.get('BEST')}
    for name,value in [('checkpoint_registry',registry),('last_checkpoint_identity',identity),('best_checkpoint_identity',registry['BEST'])]:atomic_json(Path(public)/(name+'.json'),value)
    return registry
