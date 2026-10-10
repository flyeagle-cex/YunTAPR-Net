"""Runnable synthetic integration, extending the existing EpochEngine utilities.

No dataset/reader injection exists. Every input is constructed internally. The
controller supports B9, while this campaign's separate quota permits four steps.
"""
from __future__ import annotations
import json
import torch
from yuntapr.training.phase_a_protocol import state_digest
from yuntapr.experimental.phase_b_v2_formal_runner_candidate.engine import EpochEngine
from yuntapr.experimental.phase_b_v2_formal_runner_candidate.protocol import fresh_models_without_observational_artifacts
from yuntapr.experimental.phase_b_v2_formal_runner_candidate.data import Batch, ROLES, to_cuda
from yuntapr.experimental.phase_b_v2_formal_runner_candidate.adapter import forward
from yuntapr.experimental.phase_b_v2_formal_runner_candidate.checkpoint import optimizer_template
from yuntapr.experimental.phase_b_v2_integration.synthetic import make_synthetic_pair
from yuntapr.experimental.phase_b_v2_integration.resources import resource_snapshot, require_resources
from yuntapr.experimental.phase_b_v2_runner_candidate.optimizer import new_adamw, clip_and_check, check_finite
from yuntapr.experimental.phase_b_v2_runner_candidate import rng
from .protocol import Profile, identity, digest
from .storage import Workspace, install_guard
from .state import B9State, ActualQuota
from .metrics import Evaluator
from .checkpoint import Schedule, Store, SCHEMA, validate
from .access import start_formal

class IntegratedEngine(EpochEngine):
    def __init__(self,spec):
        install_guard()
        if spec.seed!=2026 or spec.experiment_id!='E0': raise ValueError('Actual four-step campaign limited to seed2026/E0')
        self.spec=spec; self.profile=Profile('SYNTHETIC_SMALL',2,2)
        self.workspace=Workspace(); self.store=Store(self.workspace)
        self.resources=resource_snapshot(full_backward=True); require_resources(self.resources)
        models,self.fresh_proof=fresh_models_without_observational_artifacts(spec.seed)
        self.model=models[spec.model].to('cuda:0'); del models
        self.initial_sha=state_digest(self.model.state_dict())
        if self.initial_sha!=self.fresh_proof['state_sha256'][spec.model]: raise ValueError('Fresh identity')
        self.buffer_sha=state_digest(dict(self.model.named_buffers()))
        self.base=make_synthetic_pair()[spec.model]
        # Explicitly artificial artifact identities, never scientific source claims.
        self.artifacts={k:digest({'synthetic_artifact':k}) for k in ('data','qualification','scaler','mask','sp04','protocol','resource')}
        self.artifacts['data']=state_digest(vars(self.base))
        self.identity=identity(spec,self.profile,self.artifacts)
        self.state=B9State(self.workspace,self.identity); self.quota=ActualQuota()
        self.optimizer,self.group_evidence=new_adamw(self.model); self.schedule=Schedule()

    def _healthy(self):
        if (self.state.read()['phase']=='FAILED' or self.identity!=identity(self.spec,self.profile,self.artifacts)
            or self.buffer_sha!=state_digest(dict(self.model.named_buffers()))
            or self.artifacts['data']!=state_digest(vars(self.base))): raise ValueError('Failed/mutated run')

    def _batch(self,role,order):
        ids=self.profile.ids('train' if role==ROLES[0] else 'development')
        index=[ids.index(x) for x in order]
        return to_cuda(Batch(tuple(order),role,**{n:getattr(self.base,n)[index].clone() for n in ('x','rate','native_valid','reference_valid','region_mask')}))

    def train_epoch(self):
        self._healthy(); order=tuple(self.state.begin()); records=[]
        try:
            self.model.train()
            batch=self._batch(ROLES[0],order)
            self.optimizer.zero_grad(set_to_none=True); lr=self.schedule.prepare(self.optimizer)
            output,loss=forward(self.model,batch,self.spec.model,self.spec.experiment_id)
            loss.training_objective.backward(); clipping=clip_and_check(self.model)
            self.state.reserve()
            self.quota.perform(self.optimizer,self.spec.model)
            self.schedule.commit(); self.state.complete_step()
            check_finite(self.model.state_dict()); check_finite(self.optimizer.state_dict())
            records.append(dict(lr=lr,N_valid=loss.n_valid,N_rain=loss.n_rain,
                s_occ=float(loss.s_occ.detach()),s_qr=float(loss.s_qr.detach()),
                training_objective=float(loss.training_objective.detach()),**clipping))
            self.state.finish_train([order]); self.train_records=records
            return records
        except BaseException as exc:
            self.state.fail(type(exc).__name__); raise

    @torch.inference_mode()
    def validate_and_commit(self):
        self._healthy()
        if self.state.read()['phase']!='WAIT_VALIDATION': raise ValueError('Training must finish first')
        evaluator=None
        try:
            self.model.eval(); ids=self.profile.ids('development'); batch=self._batch(ROLES[1],ids)
            output,_=forward(self.model,batch,self.spec.model,self.spec.experiment_id)
            evaluator=Evaluator(ids,digest(self.identity),Workspace())
            evaluator.add(ids,('2024-03-01T00:00:00Z','2024-03-08T00:00:00Z'),output.rain_logit,output.rain_prob,
                output.conditional_quantiles_log,batch.rate,batch.reference_valid,batch.region_mask)
            report=evaluator.finish(); self.state.validate(report); s=self.state.read()
            payload=dict(schema=SCHEMA,identity=self.identity,model=self.model.state_dict(),optimizer=self.optimizer.state_dict(),
                scheduler=self.schedule.state_dict(),rng=rng.capture(),initial_sha=self.initial_sha,epoch=s['epoch']+1,
                update=s['updates'],train=s['train'],validation=report,parent_last_sha=s['last_sha'],quota=self.quota.report())
            self._validate(payload)
            reference=self.store.save('LAST_SYNTHETIC_EPOCH'+str(payload['epoch']),payload)
            # Read/SHA/deserialize verification before committing durable controller.
            self._validate(self.store.read(reference))
            sha=json.loads(reference.read_text())['sha256']; self.state.commit_last(sha)
            self.last_reference=reference
            return report,reference
        except BaseException as exc:
            self.state.fail(type(exc).__name__); raise
        finally:
            if evaluator is not None:evaluator.close()

    def _validate(self,payload):
        validate(payload,self.identity,self.model.state_dict(),optimizer_template(self.optimizer),self.initial_sha)

    def restore_completed_last(self,reference,expected_last_sha):
        self._healthy()
        if reference!=getattr(self,'last_reference',None): raise PermissionError('Only own committed synthetic LAST')
        record=json.loads(reference.read_text())
        if record['sha256']!=expected_last_sha: raise ValueError('LAST SHA mismatch')
        payload=self.store.read(reference); self._validate(payload)
        self.state.check_restore(expected_last_sha,payload['epoch'],payload['update'])
        try:
            self.model.load_state_dict(payload['model'],strict=True); self.optimizer.load_state_dict(payload['optimizer'])
            self.schedule.load_state_dict(payload['scheduler']); rng.restore(payload['rng'])
            actual=self.state_identity()
            if actual!={k:state_digest(payload[k]) for k in ('model','optimizer','scheduler','rng')}: raise ValueError('Restore state mismatch')
            return actual
        except BaseException as exc:
            self.state.fail(type(exc).__name__); raise

    def selected_endpoint(self): return self.state.endpoint()
    def start_formal(self,*args,**kwargs): start_formal(*args,**kwargs)
