"""Bounded synthetic evaluator. Exact binary64 score groups stay on disk.

SQLite BLOB ordering is numeric ordering for finite, nonnegative big-endian
binary64 scores. Ties aggregate losslessly; reliability bins never feed ranking.
"""
from __future__ import annotations
from datetime import datetime, timezone
import math
import struct
import hashlib
import numpy as np
import torch
from yuntapr.experimental.phase_b_v2_ablations.metrics import common_validation_sums
from yuntapr.experimental.phase_b_v2_ablations.validation import supervision
from .protocol import SCOPE, digest
from .storage import Workspace, database, transaction

TAU=(np.arange(32,dtype=np.float64)+.5)/32
TAIL=(10.,50.,100.,500.,1000.)

def block_id(date: str) -> int:
    t=datetime.fromisoformat(date.replace('Z','+00:00'))
    if t.tzinfo is None or t.utcoffset().total_seconds()!=0: raise ValueError('Explicit UTC required')
    i=(t-datetime(2024,3,1,tzinfo=timezone.utc)).days//7
    if not 0<=i<35: raise ValueError('Frozen 2024 March-October blocks only')
    return i

def empty():
    return dict(scenes=0,n_valid=0,n_rain=0,s_occ=0.,s_qr=0.,brier_sum=0.,
                bin_n=np.zeros(10,dtype=np.int64),bin_p=np.zeros(10),bin_r=np.zeros(10,dtype=np.int64),
                covered=np.zeros(32,dtype=np.int64),rain_n=np.zeros(7,dtype=np.int64),rain_q=np.zeros(7),
                tail_n=np.zeros(5,dtype=np.int64),tail_r=np.zeros(5,dtype=np.int64),
                tail_scenes=np.zeros(5,dtype=np.int64),tail_grid=np.zeros((5,10000),dtype=bool),
                q32_log_min=None,q32_log_max=None,span_log_max=None)

class Evaluator:
    def __init__(self, ids: tuple[str,...], source_sha: str, workspace: Workspace, *, max_bytes=64*1024**2):
        from .protocol import sha_string
        sha_string(source_sha)
        if (type(workspace) is not Workspace or type(ids) is not tuple or not ids or len(ids)>10501
            or len(set(ids))!=len(ids) or any(not x.startswith(SCOPE+'/') for x in ids)):
            raise ValueError('Bounded, unique artificial identities only')
        self.ids,self.source,self.position,self.poisoned=ids,source_sha,0,False
        self.con=database(workspace.file('scores.sqlite'),max_bytes=max_bytes)
        self.con.execute('CREATE TABLE scores(block INTEGER,score BLOB,pos INTEGER,neg INTEGER,PRIMARY KEY(block,score)) WITHOUT ROWID')
        self.stats={-1:empty(),**{b:empty() for b in range(35)}}
        self.scene_blocks=[]

    @torch.no_grad()
    def add(self, ids, dates, logit, probability, qlog, rate, valid, mask):
        if self.poisoned: raise RuntimeError('Failed evaluator cannot resume or produce a receipt')
        try:
            b=logit.shape[0]
            if (not 1<=b<=8 or logit.shape[-1]*logit.shape[-2]>10000 or len(dates)!=b
                or tuple(ids)!=self.ids[self.position:self.position+b] or len(ids)!=b):
                raise ValueError('Coverage/order/batch/resource boundary')
            if (probability.shape!=logit.shape or probability.device!=logit.device
                or probability.dtype!=logit.dtype or not torch.equal(probability,torch.sigmoid(logit))):
                raise ValueError('Preserve native sigmoid score identity, including BF16 ties')
            blocks=[block_id(d) for d in dates]
            # Validate full tensors before adding any scene, including masked outputs.
            supervision(logit,qlog,rate,valid,mask)
            with transaction(self.con):
                for j,block in enumerate(blocks):
                    sl=slice(j,j+1)
                    sup=supervision(logit[sl],qlog[sl],rate[sl],valid[sl],mask[sl])
                    sums=common_validation_sums(logit[sl],qlog[sl],rate[sl],valid[sl],mask[sl])
                    v=sup.valid.flatten().cpu().numpy(); r=sup.rainy_valid.flatten().cpu().numpy()[v]
                    p=probability[sl].double().flatten().cpu().numpy()[v]
                    y=rate[sl].double().flatten().cpu().numpy()[v]
                    q=qlog[sl].reshape(32,-1).cpu().numpy()[:,v]
                    errors=np.log1p(y[r])[None,:]-q[:,r]
                    pin=np.maximum(TAU[:,None]*errors,(TAU[:,None]-1)*errors).mean(axis=0)
                    covered=(np.log1p(y[r])[None,:]<=q[:,r]).sum(axis=1)
                    bins=np.searchsorted(np.arange(1,10)/10,p,side='right')
                    strata=np.searchsorted(np.array([1,5,10,20,30,50,np.inf]),y[r],side='left')
                    score,inv=np.unique(p,return_inverse=True)
                    pos=np.bincount(inv,weights=r,minlength=len(score)).astype(np.int64)
                    total=np.bincount(inv,minlength=len(score))
                    rows=[(k,struct.pack('>d',float(s)+0.),int(a),int(n-a))
                          for k in (-1,block) for s,a,n in zip(score,pos,total)]
                    self.con.executemany('INSERT INTO scores VALUES(?,?,?,?) ON CONFLICT(block,score) DO UPDATE SET pos=pos+excluded.pos,neg=neg+excluded.neg',rows)
                    for k in (-1,block):
                        st=self.stats[k]; st['scenes']+=1; st['n_valid']+=sums.n_valid; st['n_rain']+=sums.n_rain
                        st['s_occ']+=sums.s_occ; st['s_qr']+=sums.s_qr; st['brier_sum']+=float(((p-r)**2).sum())
                        st['bin_n']+=np.bincount(bins,minlength=10); st['bin_p']+=np.bincount(bins,weights=p,minlength=10)
                        st['bin_r']+=np.bincount(bins,weights=r,minlength=10).astype(np.int64)
                        st['covered']+=covered; st['rain_n']+=np.bincount(strata,minlength=7)
                        st['rain_q']+=np.bincount(strata,weights=pin,minlength=7)
                        for i,t in enumerate(TAIL):
                            hit=q[-1]>math.log1p(t)
                            st['tail_n'][i]+=hit.sum(); st['tail_r'][i]+=(hit&r).sum()
                            st['tail_scenes'][i]+=int(hit.any()); st['tail_grid'][i,np.flatnonzero(v)[hit]]=True
                        low,high,span=float(q[-1].min()),float(q[-1].max()),float((q[-1]-q[0]).max())
                        st['q32_log_min']=low if st['q32_log_min'] is None else min(low,st['q32_log_min'])
                        st['q32_log_max']=high if st['q32_log_max'] is None else max(high,st['q32_log_max'])
                        st['span_log_max']=span if st['span_log_max'] is None else max(span,st['span_log_max'])
                    self.scene_blocks.append((ids[j],block))
            self.position+=b
        except BaseException:
            self.poisoned=True
            raise

    def score_groups(self, block=-1):
        if self.poisoned: raise RuntimeError('Failed evaluator')
        for score,pos,neg in self.con.execute('SELECT score,pos,neg FROM scores WHERE block=? ORDER BY score DESC',(block,)):
            yield struct.unpack('>d',score)[0],pos,neg

    def summary(self, block):
        s=self.stats[block]; nv,nr=s['n_valid'],s['n_rain']; nn=nv-nr
        tp=fp=0; auc=ap=0.
        for _,p,n in self.score_groups(block):
            auc+=p*(nn-fp-.5*n); tp+=p; fp+=n
            if nr: ap+=p/nr*tp/(tp+fp)
        coverage=(s['covered']/nr).tolist() if nr else [None]*32
        ratio=lambda x,n: float(x/n) if n else None
        return {**{k:v for k,v in s.items() if not isinstance(v,np.ndarray)},
            'core_fp64':ratio(s['s_occ']+s['s_qr'],nv),'conditional_pinball':ratio(s['s_qr'],nr),
            'brier':ratio(s['brier_sum'],nv),'auroc':auc/(nr*nn) if nr and nn else None,
            'average_precision':ap if nr else None,'tau':TAU.tolist(),'covered':s['covered'].tolist(),
            'coverage':coverage,'q32_signed_bias':float(coverage[-1]-TAU[-1]) if nr else None,
            'q32_absolute_error':float(abs(coverage[-1]-TAU[-1])) if nr else None,
            'reliability':[dict(n=int(n),rain=int(r),probability_sum=float(p),mean_probability=ratio(p,n),frequency=ratio(r,n)) for n,p,r in zip(s['bin_n'],s['bin_p'],s['bin_r'])],
            'rain_strata':[dict(upper=u if math.isfinite(u) else None,n=int(n),pinball_sum=float(q),conditional_pinball=ratio(q,n)) for u,n,q in zip([1,5,10,20,30,50,math.inf],s['rain_n'],s['rain_q'])],
            'tail':[dict(threshold_mm_h=t,exposures=int(n),rain=int(r),dry=int(n-r),scenes=int(c),unique_grid=int(g.sum())) for t,n,r,c,g in zip(TAIL,s['tail_n'],s['tail_r'],s['tail_scenes'],s['tail_grid'])],
            'not_estimable':{'auroc':'SINGLE_CLASS_OR_EMPTY' if not nr or not nn else None,'conditional':'NO_RAIN' if not nr else None}}

    def finish(self):
        if self.poisoned or self.position!=len(self.ids): raise ValueError('Incomplete/failed validation')
        score_digest=hashlib.sha256()
        for block,score,pos,neg in self.con.execute('SELECT block,score,pos,neg FROM scores ORDER BY block,score'):
            score_digest.update(struct.pack('>i',block)+score+struct.pack('>QQ',pos,neg))
        report={'scope':SCOPE,'source_sha':self.source,'ids_sha':digest(self.ids),'scene_blocks':self.scene_blocks,
                'complete':True,'summary':self.summary(-1),'blocks':[self.summary(i) for i in range(35)],
                'score_encoding':'native sigmoid promoted to exact binary64; grouped ties; SQLite BLOB index',
                'exact_score_table_sha256':score_digest.hexdigest(),
                'scientific_success':'NOT_AUTHORIZED_OR_ESTABLISHED'}
        report['receipt_sha']=digest(report)
        return report

    def close(self): self.con.close()
