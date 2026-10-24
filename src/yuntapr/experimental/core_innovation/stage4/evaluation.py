"""Reuse frozen exact-score metrics, adding explicit scene/spatial partitions."""
import hashlib,sqlite3
from pathlib import Path
import numpy as np
import torch
from yuntapr.experimental.phase_b_v2_formal_integration_candidate.metrics import Evaluator as NumericEvaluator,empty
from ..stage3.planning import digest,utc


class NumericEnvelope(NumericEvaluator):
    def __init__(self,ids,source_sha,path):
        if not ids or len(set(ids))!=len(ids) or any(utc(s).year!=2024 for s in ids):raise ValueError('Unique development IDs required')
        path=Path(path)
        if path.exists():raise PermissionError('No metric overwrite/resume')
        self.ids=tuple(ids);self.source=source_sha;self.position=0;self.poisoned=False
        self.con=sqlite3.connect(path,isolation_level=None)
        self.con.execute('PRAGMA synchronous=FULL');self.con.execute('PRAGMA temp_store=FILE');self.con.execute('PRAGMA cache_size=-8192')
        page=self.con.execute('PRAGMA page_size').fetchone()[0];self.con.execute(f'PRAGMA max_page_count={256*1024**2//page}')
        self.con.execute('CREATE TABLE scores(block INTEGER,score BLOB,pos INTEGER,neg INTEGER,PRIMARY KEY(block,score)) WITHOUT ROWID')
        self.stats={-1:empty(),**{b:empty() for b in range(35)}};self.scene_blocks=[]
    def finish(self):
        r=super().finish();r.pop('receipt_sha')
        r['scope']='STAGE4_2024_DEV_FIXED_F006_RETROSPECTIVE';r['scientific_success']='NOT_ESTABLISHED_BY_ENGINEERING_DRY_RUN'
        r['receipt_sha']=digest(r);return r


def elevation_groups(elevation,valid,*,edges_m,grid,expected_grid,source_sha):
    expected_grid.assert_same(grid);z=np.asarray(elevation);v=np.asarray(valid)
    edges=tuple(edges_m)
    if z.shape!=(100,100) or v.shape!=z.shape or v.dtype!=bool or not np.isfinite(z[v]).all() or len(source_sha)!=64:raise ValueError('Pinned metre target DEM and masks required')
    if len(edges)<2 or any(a>=b for a,b in zip(edges,edges[1:])):raise ValueError('Explicit ordered altitude edges required')
    return {f'elevation_{i}':dict(mask=v&(z>=lo)&(z<hi),rule=dict(lower_m=lo,upper_m=hi,source_sha256=source_sha)) for i,(lo,hi) in enumerate(zip(edges,edges[1:]))}


class Evaluation:
    def __init__(self,ids,analyses,source_identity,folder,*,strong_scene_ids=(),altitude=None):
        folder=Path(folder);folder.mkdir(exist_ok=False);self.ids=tuple(ids);self.source_identity=source_identity
        groups={'all':self.ids}
        for hour in (0,6,12,18):groups[f'analysis_UTC_{hour:02d}']=tuple(s for s,t in zip(ids,analyses) if utc(t).hour==hour)
        groups['scene_max_ge20']=tuple(s for s in ids if s in set(strong_scene_ids))
        self.altitude=altitude or {}
        for name,item in self.altitude.items():
            if np.asarray(item['mask']).shape!=(100,100) or np.asarray(item['mask']).dtype!=bool:raise ValueError('Independent target altitude masks')
            groups[name]=self.ids if item['mask'].any() else ()
        self.groups=groups;self.numeric={name:NumericEnvelope(group,digest(source_identity),folder/(name+'.sqlite')) for name,group in groups.items() if group}
        self.partition_sha=digest(dict(groups=groups,altitude={k:dict(rule=v['rule'],mask_sha256=hashlib.sha256(v['mask'].tobytes()).hexdigest()) for k,v in self.altitude.items()}))
    @torch.no_grad()
    def add(self,output,batch):
        if batch.role!='Development':raise PermissionError('Development evaluation only')
        for name,ev in self.numeric.items():
            for i,sid in enumerate(batch.ids):
                if sid not in self.groups[name]:continue
                sl=slice(i,i+1);region=batch.region[sl]
                if name in self.altitude:region=region&torch.as_tensor(self.altitude[name]['mask'],device=region.device)[None,None]
                ev.add((sid,),(batch.analyses[i],),output.rain_logit[sl],output.rain_prob[sl],output.conditional_quantiles_log[sl],batch.rate[sl],batch.valid[sl],region)
    def finish(self):
        result={name:ev.finish() for name,ev in self.numeric.items()}
        return dict(scope='2024_DEVELOPMENT_FIXED_F006_RETROSPECTIVE',source_identity=self.source_identity,
            population_ids_sha256=digest(self.ids),partition_sha256=self.partition_sha,groups=result,empty_groups=[k for k,v in self.groups.items() if not v],
            high_altitude_status='EXPLICIT_CANDIDATE_GRID_AND_EDGES' if self.altitude else 'NOT_ESTIMABLE_TARGET_DEM_AND_ALTITUDE_EDGES_NOT_FROZEN',
            occurrence_event='float32 rate > float32(0.1)',conditional_strata='(0.1,1],(1,5],(5,10],(10,20],(20,30],(30,50],(50,inf)',
            interpretation='No all-day NRT, 2025 independent-test or innovation-effectiveness claim')
    def close(self):
        for ev in self.numeric.values():ev.close()


def paired_difference(b3,b4):
    if b3['source_identity']!=b4['source_identity'] or b3['population_ids_sha256']!=b4['population_ids_sha256'] or b3['partition_sha256']!=b4['partition_sha256'] or b3['groups'].keys()!=b4['groups'].keys():raise ValueError('Unpaired evaluation populations/partitions')
    result={}
    for name,a in b3['groups'].items():
        b=b4['groups'][name]
        if a['ids_sha']!=b['ids_sha'] or a['summary']['n_valid']!=b['summary']['n_valid']:raise ValueError('Partition coverage differs')
        result[name]={k:(b['summary'][k]-a['summary'][k] if a['summary'][k] is not None and b['summary'][k] is not None else None) for k in ('brier','auroc','average_precision','conditional_pinball','q32_signed_bias','core_fp64')}
        result[name]['rain_strata_conditional_pinball_B4_minus_B3']=[b['conditional_pinball']-a['conditional_pinball'] if a['n'] and b['n'] else None for a,b in zip(a['summary']['rain_strata'],b['summary']['rain_strata'])]
    return dict(direction='B4_MINUS_B3',descriptive_only=True,groups=result)
