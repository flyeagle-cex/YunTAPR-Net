"""Crash-safe sufficient statistics; no raw reader or production launch command.

One committed cache receipt per unique decoding job. A job may be one satellite
file or an identity-bound main/thermo pair. Final Train populations can change
before fitting without reading any completed job again.
"""
from dataclasses import asdict
from pathlib import Path
from collections import Counter
from datetime import timedelta
import json, re, sqlite3
import numpy as np
from . import VERSION
from .planning import digest, utc
from ..stage2 import CHANNELS, MEE_KEYS
from ..stage2.environment import EnvironmentScaler, UNITS
from ..stage2.population import TrainMoments

NEW_CHANNELS=tuple(c for c in CHANNELS if c!='B13')
V13_KEYS=(*MEE_KEYS,'temperature500','relative_humidity500')
V13_UNITS=(*UNITS,'K','%')


def moments(values, valid):
    x=np.asarray(values,dtype=np.float64);mask=np.asarray(valid)
    if x.shape!=mask.shape or mask.dtype!=bool or not np.isfinite(x[mask]).all():
        raise ValueError('Finite values and independent masks required')
    good=x[mask];n=good.size;mean=float(good.mean()) if n else 0.
    m2=float(((good-mean)**2).sum()) if n else 0.
    if not np.isfinite([mean,m2]).all():raise FloatingPointError('Moment overflow')
    return dict(n=int(n),total=int(x.size),mean=mean,m2=m2)


def merge(parts):
    n=0;total=0;mean=0.;m2=0.
    for p in parts:
        count=int(p['n']);total+=int(p['total'])
        if not 0<=count<=p['total'] or not np.isfinite([p['mean'],p['m2']]).all() or p['m2']<0:raise ValueError('Invalid sufficient statistics')
        if not count:continue
        delta=p['mean']-mean;combined=n+count
        m2+=p['m2']+delta**2*n*count/combined;mean+=delta*count/combined;n=combined
    return dict(n=n,total=total,mean=mean,m2=m2)


def satellite_statistics(values,valid,*,year,receipt):
    x=np.asarray(values);mask=np.asarray(valid)
    if year not in (2023,2024) or x.ndim!=3 or x.shape[0]!=7 or mask.shape!=x.shape or mask.dtype!=bool or not np.isfinite(x[mask]).all():
        raise ValueError('Seven-band decoded frame and authorized year required')
    qc=dict(receipt)
    # Dev contains QC only. B13 is checked for eligibility but never refitted.
    stats={c:moments(x[i],mask[i]) for i,c in enumerate(CHANNELS) if c!='B13'} if year==2023 else {}
    return dict(year=year,scope='Train' if year==2023 else 'Development',frame_receipt=qc,
                channels=NEW_CHANNELS,moments=stats,all_seven_valid=bool(mask.all()),shape=list(x.shape[-2:]))


def environment_statistics(frame,*,keys,target_grid):
    """Reuse stage2 mapping/above-ground masks. No new scientific transformation."""
    keys=tuple(keys)
    if keys not in (MEE_KEYS,V13_KEYS):raise ValueError('Explicit eleven or V1.3 thirteen-channel candidate required')
    if frame.identity.valid.year!=2023:raise PermissionError('Only 2023 Train environmental statistics')
    mapped=frame.on_grid(target_grid,operator='bilinear_point_candidate');values,valid=mapped.stack(keys)
    units=UNITS if keys==MEE_KEYS else V13_UNITS
    if any(mapped.fields[k].unit!=u for k,u in zip(keys,units)):raise ValueError('Canonical physical units required')
    pwat=values[keys.index('pwat')];pmask=valid[keys.index('pwat')]
    if np.any(pwat[pmask]<0):raise ValueError('Negative valid PWAT is not a positive reference source')
    positive=pwat[pmask&(pwat>0)]
    return dict(keys=keys,units=units,grid_id=target_grid.identity,year=2023,
        source_provenance=frame.provenance,
        forecast_identity=dict(init=frame.identity.init.isoformat(),valid=frame.identity.valid.isoformat(),lead_hours=frame.identity.lead.total_seconds()/3600),
        moments={k:moments(x,m) for k,x,m in zip(keys,values,valid)},
        pwat_positive_count=int(positive.size),pwat_positive_sum=float(positive.sum()),
        reference_rule='Final-2023-Train valid scene-pixel-exposure-weighted mean of strictly positive PWAT in kg m-2; candidate only')


class SourceCache:
    """Reserve -> decode once -> atomic COMPLETE; uncertain reads never retry.

    The grant is supplied by a human-authorized future driver. This library
    cannot grant access. This stage ships no real-data production driver.
    """
    def __init__(self,path,*,manifest,manifest_sha,grant,processor_id=VERSION):
        if digest(manifest)!=manifest_sha or not processor_id:raise ValueError('Exact source manifest and processor identity required')
        if not grant.get('authorized') or grant.get('manifest_sha')!=manifest_sha or not grant.get('decision_id'):
            raise PermissionError('Independent manifest-bound raw-reading grant required')
        if any(j['year'] not in (2023,2024) for j in manifest.values()):raise PermissionError('2025 forbidden')
        if any(type(j['bytes'])!=int or type(j['files'])!=int or min(j['bytes'],j['files'])<=0 for j in manifest.values()):raise ValueError('Positive exact indexed byte/file reservations required')
        self.manifest=manifest;self.grant=grant
        config=digest(dict(manifest_sha=manifest_sha,grant=grant,processor_id=processor_id))
        self.db=sqlite3.connect(Path(path));self.db.execute('PRAGMA synchronous=FULL')
        self.db.execute('CREATE TABLE IF NOT EXISTS settings (id INTEGER PRIMARY KEY, value TEXT)')
        self.db.execute('CREATE TABLE IF NOT EXISTS jobs (id TEXT PRIMARY KEY, state TEXT, bytes INTEGER, files INTEGER, payload TEXT)')
        old=self.db.execute('SELECT value FROM settings WHERE id=1').fetchone()
        if old and old[0]!=config:
            self.db.close();raise ValueError('Manifest/grant/processor changed; cache cannot be mixed')
        if not old:self.db.execute('INSERT INTO settings VALUES (1,?)',(config,));self.db.commit()

    def close(self):self.db.close()

    def __getitem__(self,source_id):
        row=self.db.execute('SELECT state,payload FROM jobs WHERE id=?',(source_id,)).fetchone()
        if not row or row[0]!='COMPLETE':raise ValueError('Completed sufficient statistics missing; do not reopen raw source')
        return json.loads(row[1])

    def read_once(self,source_id,loader):
        if source_id not in self.manifest:raise PermissionError('Unlisted raw source job')
        job=self.manifest[source_id]
        self.db.execute('BEGIN IMMEDIATE')
        try:
            old=self.db.execute('SELECT state,payload FROM jobs WHERE id=?',(source_id,)).fetchone()
            if old:
                self.db.rollback()
                if old[0]!='COMPLETE':raise RuntimeError('Uncertain prior read: no automatic retry')
                return json.loads(old[1])
            used=self.db.execute('SELECT COALESCE(SUM(bytes),0),COALESCE(SUM(files),0) FROM jobs').fetchone()
            if (used[0]+job['bytes']>self.grant['max_bytes'] or used[1]+job['files']>self.grant['max_files']):
                raise PermissionError('Independent raw read grant exhausted')
            self.db.execute('INSERT INTO jobs VALUES (?,?,?,?,NULL)',(source_id,'PENDING',job['bytes'],job['files']));self.db.commit()
        except BaseException:
            if self.db.in_transaction:self.db.rollback()
            raise
        try:
            payload=loader()
            actual=payload['source_sha256']
            if (payload['year']!=job['year'] or not re.fullmatch('[0-9a-f]{64}',actual)
                or (job.get('expected_sha256') is not None and actual!=job['expected_sha256'])
                or payload['raw_bytes_read']!=job['bytes']):
                raise ValueError('Decoded source identity differs from manifest')
            text=json.dumps(payload,sort_keys=True,allow_nan=False)
            with self.db:self.db.execute('UPDATE jobs SET state=?,payload=? WHERE id=?',('COMPLETE',text,source_id))
            return payload
        except BaseException:
            with self.db:self.db.execute('UPDATE jobs SET state=? WHERE id=?',('UNCERTAIN_NO_RETRY',source_id))
            raise


class CachedTrainMoments(TrainMoments):
    """Reuse frozen TrainMoments output policy; merge six cached slot summaries."""
    def update_cached(self,sample_id,frames):
        if sample_id not in self.expected or sample_id in self.seen or len(frames)!=6:
            raise ValueError('Exactly once per final Train scene, six ordered source receipts')
        if any(f['year']!=2023 or f['scope']!='Train' or not f['all_seven_valid'] for f in frames):
            raise ValueError('Final full-valid 2023 Train sources only')
        if len({tuple(f['shape']) for f in frames})!=1:raise ValueError('Native source shapes differ')
        analysis=utc(sample_id)+timedelta(minutes=30)
        expected=[analysis-timedelta(minutes=m) for m in (60,50,40,30,20,10)]
        if any(utc(f['frame_receipt']['nominal'])!=t for f,t in zip(frames,expected)):
            raise ValueError('Cached frame order differs from declared six-slot exposure rule')
        stats=[merge([f['moments'][c] for f in frames]) for c in NEW_CHANNELS]
        counts={p['n'] for p in stats}
        if len(counts)!=1 or any(p['n']!=p['total'] for p in stats):raise ValueError('Full-valid common pixel support required')
        count=stats[0]['n'];mean=np.array([p['mean'] for p in stats]);m2=np.array([p['m2'] for p in stats])
        delta=mean-self.mean;total=self.n+count
        self.m2+=m2+delta**2*self.n*count/total;self.mean+=delta*count/total;self.n=total;self.seen.add(sample_id)


def finalize_statistics(train_rows,cache,*,final_train_ids,final_dev_ids,final_population_sha,source_manifest_sha,frozen_b13,environment_keys,forecast_lead_hours):
    """cache maps source IDs to committed sufficient statistics; no raw I/O.

    Call only after final common Train AND Dev membership has been verified.
    Row fields are sample_id, frame_ids (six ordered), environment_id.
    """
    if not re.fullmatch('[0-9a-f]{64}',final_population_sha) or not re.fullmatch('[0-9a-f]{64}',source_manifest_sha):raise ValueError('Final population and source SHA required')
    if forecast_lead_hours not in (0,3,6):raise ValueError('Explicit fixed forecast lead required')
    ids=[r['sample_id'] for r in train_rows]
    if (not final_dev_ids or len(set(final_train_ids))!=len(final_train_ids) or len(set(final_dev_ids))!=len(final_dev_ids)
        or set(ids)!=set(final_train_ids) or len(ids)!=len(final_train_ids)
        or any(utc(s).year!=2024 for s in final_dev_ids)
        or digest(dict(Train=sorted(final_train_ids),Development=sorted(final_dev_ids)))!=final_population_sha):
        raise ValueError('Declared complete final Train/Dev membership and population SHA must match')
    fitter=CachedTrainMoments(final_train_ids,population_id=final_population_sha)
    env=[];used=[]
    for row in train_rows:
        fitter.update_cached(row['sample_id'],[cache[s] for s in row['frame_ids']])
        e=cache[row['environment_id']]
        if e['year']!=2023 or tuple(e['keys'])!=tuple(environment_keys):raise PermissionError('Matched 2023 Train environment only')
        identity=e['forecast_identity'];analysis=utc(row['sample_id'])+timedelta(minutes=30)
        if utc(identity['valid'])!=analysis or utc(identity['init'])>analysis or identity['lead_hours']!=forecast_lead_hours:
            raise ValueError('Wrong scene-valid binding or mixed fixed forecast vintage')
        env.append(e);used.extend([*row['frame_ids'],row['environment_id']])
    if len({e['grid_id'] for e in env})!=1 or len({tuple(e['units']) for e in env})!=1:raise ValueError('Environment grid/unit mismatch')
    spectral=fitter.finish(frozen_b13=frozen_b13);merged={k:merge([e['moments'][k] for e in env]) for k in environment_keys}
    scalers={}
    for key,p in merged.items():
        if p['n']==0 or p['m2']<=0:raise ValueError('Unidentifiable or constant environment scaler: '+key)
        scalers[key]=dict(mean=p['mean'],std=float(np.sqrt(p['m2']/p['n'])),count=p['n'],total=p['total'],valid_fraction=p['n']/p['total'])
    positive_count=sum(e['pwat_positive_count'] for e in env);positive_sum=sum(e['pwat_positive_sum'] for e in env)
    if positive_count<=0 or positive_sum<=0:raise ValueError('Positive Train PWAT reference unavailable')
    return dict(status='COMPUTED_CANDIDATE_REQUIRES_SCIENTIFIC_FREEZE',population_sha256=final_population_sha,
        source_manifest_sha256=source_manifest_sha,processor=VERSION,fit_role='Train',fit_years=[2023],ddof=0,
        scene_count=len(ids),scene_slot_exposures=6*len(ids),spectral_order=CHANNELS,
        spectral_scalers={k:asdict(s) for k,s in spectral.items()},new_band_count_each=fitter.n,new_band_valid_fraction=1.,
        B13_refitted=False,environment_order=tuple(environment_keys),environment_units=env[0]['units'],environment_scalers=scalers,
        environment_weighting='One mapped environment exposure per final Train scene; invalid/below-ground cells excluded',
        positive_PWAT_reference_kg_m2=positive_sum/positive_count,positive_PWAT_count=positive_count,
        source_ids=sorted(set(used)),source_exposure_counts=dict(sorted(Counter(used).items())),
        source_receipts={s:cache[s]['source_sha256'] for s in sorted(set(used))},
        adapter_status='EXISTING_11_CHANNEL_INTERFACE' if tuple(environment_keys)==MEE_KEYS else '13_CHANNEL_MODEL_ADAPTER_PENDING_RESEARCHER_APPROVAL')
