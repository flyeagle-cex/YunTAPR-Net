"""Read-only hooks around the unchanged numerical update; no replacement outputs.

All observations run without autograd. Existing expm1 and clip are delegated
exactly once. No observer value feeds back into the model, loss or optimizer.
"""
from contextlib import contextmanager
import math
import torch
from torch.nn import functional as F
from quantile_autopsy_v1 import common as c
from yuntapr.losses.focal import focal_bce_sum
from yuntapr.losses.pinball import pinball_sum

def number(x):
    value = float(x)
    return value if math.isfinite(value) else ('NaN' if math.isnan(value) else '+Inf' if value>0 else '-Inf')

@torch.no_grad()
def stats(x):
    y = x.to(torch.float64)
    return {'min':number(y.min()), 'max':number(y.max()), 'mean':number(y.mean()),
            'std':number(y.std(correction=0)), 'absmax':number(y.abs().max()),
            'all_finite':bool(torch.isfinite(y).all()), 'dtype':str(x.dtype)}

@torch.no_grad()
def norm(values):
    values = list(values)
    if not values:return 0.0
    return number(torch.sqrt(sum(v.to(torch.float64).square().sum() for v in values)))

def overflow_boundaries(qmax):
    result = {}
    for name,dtype in [('float32',torch.float32),('float64',torch.float64)]:
        maximum = torch.finfo(dtype).max
        boundary = math.log1p(maximum)
        result[name] = {'finfo_max':maximum, 'log1p_finfo_max':boundary,
                        'qlog_max':qmax, 'overflow_margin':qmax-boundary}
    return result

class Observer:
    def __init__(self,model):
        self.model = model
        self.raw = self.features = self.logit = None
        self.qlog = None
        self.current = {}
        self.failure = None
        self.batch = self.items = self.records = None

    def begin(self,batch,items,records,optimizer,update):
        self.raw = self.features = self.logit = self.qlog = None
        self.batch,self.items,self.records = batch,items,records
        self.current = {'update':update,'sample_ids':batch.sample_ids,'scope':c.SCOPE,
                        'parameters_before_update':self.parameters(),
                        'optimizer_before_update':self.moments(optimizer)}

    @torch.no_grad()
    def parameters(self):
        m=self.model
        return {'global':norm(m.parameters()),'quantile_weight':norm([m.heads.quantile.weight]),
                'quantile_bias':norm([m.heads.quantile.bias]),'last_decoder_block':norm(m.backbone.dec0.parameters())}

    @torch.no_grad()
    def moments(self,optimizer):
        params=list(self.model.heads.quantile.parameters())
        return {k:norm(optimizer.state[p][k] for p in params if k in optimizer.state.get(p,{}))
                for k in ('exp_avg','exp_avg_sq')}

    @torch.no_grad()
    def gradients(self):
        def group(params):return norm(p.grad for p in params if p.grad is not None)
        return {'global':group(self.model.parameters()),'quantile_head':group(self.model.heads.quantile.parameters()),
                'backbone':group(self.model.backbone.parameters())}

    @torch.no_grad()
    def see_qlog(self,qlog):
        if self.raw is None or self.features is None or self.logit is None:
            raise RuntimeError('Observation ordering failed')
        self.qlog=qlog
        increments=F.softplus(self.raw.to(qlog.dtype))+self.model.heads.epsilon_mono
        self.current.update({'raw_head':stats(self.raw),'target_features':stats(self.features),
            'rain_logits':stats(self.logit),'qlog':stats(qlog),'increments':stats(increments),
            'qlog_per_tau_max':qlog.amax(dim=(0,2,3)).tolist(),
            'qlog_per_tau_median':qlog.movedim(1,0).reshape(32,-1).cpu().median(dim=1).values.tolist(),
            'increments_per_tau_max':increments.amax(dim=(0,2,3)).tolist(),
            'increments_per_tau_mean':increments.mean(dim=(0,2,3)).tolist(),
            'raw_per_tau_max':self.raw.amax(dim=(0,2,3)).tolist()})
        qmax=float(qlog.max())
        if qmax>math.log1p(torch.finfo(qlog.dtype).max):
            self.failure=self.capture(qlog,increments)
        # increments is a separate observation; the model's accumulator is untouched.

    @torch.no_grad()
    def capture(self,qlog,increments):
        flat=int(qlog.argmax()); width=qlog.shape[-1];height=qlog.shape[-2]
        col=flat%width;flat//=width;row=flat%height;flat//=height;tau=flat%32;b=flat//32
        batch=self.batch;valid=batch.imerg_valid_mask&batch.yunnan_eval_mask
        clean=torch.where(valid,batch.y_imerg,torch.zeros_like(batch.y_imerg))
        rainy=clean>.1;n=int(valid.sum());nrain=int((rainy&valid).sum())
        # Independent read-only arithmetic on the observed log-domain tensors.
        # This does not bypass forward's expm1/guard, create a B0Output or run backward.
        with torch.autocast(qlog.device.type,dtype=torch.bfloat16):
            locc=focal_bce_sum(self.logit,rainy,valid,.5,2.)/n
            lqr=pinball_sum(qlog,torch.log1p(clean.to(qlog.dtype)),rainy&valid,'mean')/n if nrain else qlog.sum()*0
            log_total=locc+lqr
        position=(b,0,row,col)
        identities=[]
        for item in self.items:
            record=self.records[item['index']]
            identities.append({'sample_id':item['sample_id'],'index':item['index'],
                'window_start':record['window_start'],'analysis_time':record['analysis_time'],
                'frames':item['frames'],'imerg_sha256':item['target_sha256'],
                'imerg_source':record['imerg_day_path'],'imerg_index':int(record['imerg_index']),
                'normalization_sha256':item['normalization_sha256'],
                'B13_physical_stats':item['engineering_input_observation']['physical_K'],
                'normalized_stats':item['engineering_input_observation']['normalized']})
        return {'captured_before_expm1':True,'update':self.current['update'],
            'qlog_dtype':str(qlog.dtype),'qlog_all_finite':bool(torch.isfinite(qlog).all()),
            'raw_all_finite':bool(torch.isfinite(self.raw).all()),
            'qlog_max':float(qlog.max()),'location':{'batch_index':b,'tau_index_zero_based':tau,
                'tau_ordinal':tau+1,'tau':(tau+.5)/32,'row':row,'column':col},
            'raw_at_max_position':float(self.raw[b,tau,row,col]),
            'qlog_32_at_pixel':qlog[b,:,row,col].tolist(),'raw_32_at_pixel':self.raw[b,:,row,col].tolist(),
            'increments_32_at_pixel':increments[b,:,row,col].tolist(),
            'target_feature_48_at_pixel':self.features[b,:,row,col].to(torch.float64).tolist(),
            'rain_logit':float(self.logit[position]),'rain_prob':float(torch.sigmoid(self.logit)[position]),
            'target_IMERG_value':number(batch.y_imerg[position]),
            'target_rain':bool(batch.y_imerg[position]>.1),
            'IMERG_valid':bool(batch.imerg_valid_mask[position]),'Yunnan_mask':bool(batch.yunnan_eval_mask[position]),
            'actual_denominator':n,'rainy_valid_count':nrain,
            'read_only_log_objective_diagnostic':{'occurrence':number(locc),'quantile':number(lqr),
                'total':number(log_total),'all_finite':bool(torch.isfinite(log_total)),
                'backward_calls':0,'used_for_optimizer':False,'formal_loss_not_reached':True},
            'overflow_boundaries':overflow_boundaries(float(qlog.max())),
            'sample_identities':identities,'observation':self.current}

    @contextmanager
    def installed(self):
        def features(_m,_i,o):self.features=o
        def raw(_m,_i,o):self.raw=o
        def logit(_m,_i,o):self.logit=o
        handles=[self.model.projection.register_forward_hook(features),
                 self.model.heads.quantile.register_forward_hook(raw),
                 self.model.heads.occurrence.register_forward_hook(logit)]
        expm1=torch.expm1;clip=torch.nn.utils.clip_grad_norm_
        def observed_expm1(value,*args,**kwargs):
            if value.ndim==4 and value.shape[1:]==(32,100,100) and self.raw is not None:
                self.see_qlog(value)
                result=expm1(value,*args,**kwargs)
                with torch.no_grad():
                    self.current['qphysical_nonfinite_count']=int((~torch.isfinite(result)).sum())
                    if self.failure is not None:self.failure['qphysical_nonfinite_count']=self.current['qphysical_nonfinite_count']
                return result
            return expm1(value,*args,**kwargs)
        def observed_clip(*args,**kwargs):
            self.current['gradients_pre_clip']=self.gradients()
            result=clip(*args,**kwargs)
            self.current['gradients_post_clip']=self.gradients()
            return result
        torch.expm1=observed_expm1;torch.nn.utils.clip_grad_norm_=observed_clip
        try:yield self
        finally:
            torch.expm1=expm1;torch.nn.utils.clip_grad_norm_=clip
            for h in handles:h.remove()

    def release(self):
        self.raw=self.features=self.logit=self.qlog=self.batch=self.items=self.records=None
