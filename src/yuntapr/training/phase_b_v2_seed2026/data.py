"""Full frozen M1 data, consuming only SHA-verified immutable bytes.

Frozen B13/IMERG decoders, SP04 and scaler application are reused verbatim.
Caches contain immutable verified objects, have fixed byte bounds and are not
fitted statistics. Eviction causes another same-byte SHA check on next use.
"""
from __future__ import annotations
import ast
from collections import OrderedDict
import csv
from datetime import timedelta
import hashlib
import io
import json
import ntpath
from pathlib import Path
import time
import numpy as np
import torch
from yuntapr.experimental.phase_b_v2_real_forward_pilot.plan import (
    PublicPins,SOURCE,SOURCE_SHA,STATUS,STATUS_SHA,PROTOCOL,PROTOCOL_SHA,sha)
from yuntapr.experimental.phase_b_v2_real_forward_pilot.adapter import VerifiedReader, RealAdapter
from yuntapr.experimental.phase_b_v2_full_payload_integrity.audit import Scope,canonical,valid_sha
from yuntapr.experimental.phase_b_v2_full_payload_integrity.winio import ReadHandle
from yuntapr.experimental.phase_b_v2_real_data_preflight.audit import paired_ids,normalize_frozen
from yuntapr.data.sample_schema import utc
from yuntapr.data.himawari_b13 import read_b13_local
from yuntapr.data.imerg_v07 import read_imerg_local
from .protocol import ROOT,LIMITS,digest,TRAIN_N,DEV_N
from .resources import utcnow

class Plan:
    def __init__(self,budget):
        self.public=PublicPins(budget)
        status=json.loads(self.public.read(STATUS,STATUS_SHA))
        if status['overall_status']!='FULL_PAYLOAD_SHA_PASS' or status['sha_matched_files']!=67006:
            raise ValueError('FULL_PAYLOAD_BASELINE_IDENTITY')
        prior=json.loads(self.public.read(SOURCE,SOURCE_SHA))
        pins={r['path']:r['sha256'] for r in prior['public_source_pins']}
        source=self.public.read('src/yuntapr/data/dataset_b1.py',pins['src/yuntapr/data/dataset_b1.py'])
        constants={}
        for n in ast.parse(source).body:
            if isinstance(n,ast.Assign) and len(n.targets)==1 and isinstance(n.targets[0],ast.Name) and n.targets[0].id in ('H_ROOT','IMERG_ROOT','AUDIT'):
                constants[n.targets[0].id]=ast.literal_eval(n.value.args[0])
        if set(constants)!= {'H_ROOT','IMERG_ROOT','AUDIT'}: raise ValueError('FROZEN_ROOT_CONSTANTS')
        self.scope=Scope({'B13':constants['H_ROOT'],'IMERG':constants['IMERG_ROOT']})
        self.h_root=constants['H_ROOT']
        self.protocol=json.loads(self.public.read(PROTOCOL,PROTOCOL_SHA)); self.rows={}; desired=set()
        for year,n,role in ((2023,TRAIN_N,'Train'),(2024,DEV_N,'Validation')):
            records={}
            for model in ('B1','B0_MATCHED'):
                ref=self.protocol['identity'][f'{model}_{year}']
                records[model]=list(csv.DictReader(io.StringIO(self.public.read(ref['path'],ref['sha256']).decode('utf-8-sig'))))
            a,b=records['B1'],records['B0_MATCHED']; paired_ids(b,a)
            if len(a)!=n or len(b)!=n or len({r['sample_id'] for r in a})!=n: raise ValueError('M1_FROZEN_COUNTS')
            self.rows[year]=a
            for i,(row,anchor) in enumerate(zip(a,b)):
                start,analysis=utc(row['window_start']),utc(row['analysis_time'])
                if (int(row['index'])!=i or int(row['year'])!=year or start.year!=year or
                    analysis!=start+timedelta(minutes=30) or row['role']!=role or
                    row['eligibility']!='FORMAL_M1_COMMON_INTERSECTION' or int(row['target_valid_yunnan_cells'])!=3430):
                    raise ValueError('FROZEN_ROLE_POSITION_QUALIFICATION')
                if (ntpath.basename(row['imerg_day_path'])!='imerg_'+start.strftime('%Y%m%d')+'.nc' or
                    int(row['imerg_index'])!=start.hour*2+start.minute//30 or start.minute not in (0,30)):
                    raise ValueError('IMERG_TIME_INDEX_BINDING')
                for slot,offset in enumerate((60,50,40,30,20,10)):
                    nominal=row[f'slot_{slot}_nominal']
                    if utc(nominal)!=analysis-timedelta(minutes=offset): raise ValueError('CAUSAL_SIX_SLOT_ORDER')
                    desired.add(nominal)
        if set(self.ids(2023)) & set(self.ids(2024)): raise ValueError('TRAIN_DEVELOPMENT_ROLE_OVERLAP')
        index_path=constants['AUDIT']+'/frame_identity_index.json'
        index=json.loads(self.public.read(index_path,pins[index_path])); self.frames={}
        for relative,expected in index['files'].items():
            raw=self.public.read(constants['AUDIT']+'/'+relative,expected)
            for frame in csv.DictReader(io.StringIO(raw.decode('utf-8-sig'))):
                if frame['nominal'] in desired:
                    if frame['nominal'] in self.frames: raise ValueError('DUPLICATE_FRAME_IDENTITY')
                    self.frames[frame['nominal']]=frame
        if set(self.frames)!=desired: raise ValueError('INCOMPLETE_FRAME_INDEX')
        self.late_creation=0
        for year,rows in self.rows.items():
            ref=self.protocol['identity'][f'B0_MATCHED_{year}']
            anchors=list(csv.DictReader(io.StringIO(self.public.read(ref['path'],ref['sha256']).decode('utf-8-sig'))))
            for row,anchor in zip(rows,anchors):
                self.scope.register(row['imerg_day_path'],'IMERG',year,row['imerg_sha256'],None)
                for slot in range(6):
                    f=self.frames[row[f'slot_{slot}_nominal']]
                    if (any(f[k]!='True' for k in ('present','readable','decoded','full_valid','metadata_valid')) or
                        int(f['valid_count'])!=251001 or not utc(f['obs_start'])<=utc(f['obs_end'])<=utc(row['analysis_time'])):
                        raise ValueError('FROZEN_FRAME_VALIDITY_OR_CAUSALITY')
                    if slot==5 and (anchor['b13_sha256']!=f['source_sha256'] or anchor['b13_relative_path']!=f['relative_path']):
                        raise ValueError('B0_LATEST_FRAME_PAIR_IDENTITY')
                    self.late_creation+=int(utc(f['date_created'])>utc(row['analysis_time']))
                    self.scope.register(ntpath.join(self.h_root,f['relative_path']),'B13',year,f['source_sha256'],int(f['source_bytes']))
        if len(self.scope.entries)!=67006: raise ValueError('67006_UNIQUE_FROZEN_PAYLOADS_REQUIRED')
        self.mask_ref=self.protocol['identity']['yunnan_mask']; valid_sha(self.mask_ref['sha256'])
        rawmask=self.mask_ref['path'].replace('/','\\')
        if ('2025' in rawmask or not ntpath.isabs(rawmask) or rawmask.startswith('\\\\') or rawmask.count(':')!=1 or
            any(x in ('.','..') for x in rawmask.split('\\')) or not rawmask.endswith('.nc')):
            raise PermissionError('MASK_LEXICAL_IDENTITY')
        norm=self.protocol['identity']['normalization']; self.scaler=json.loads(self.public.read(norm['path'],norm['sha256']))
        if (self.scaler['fit_years']!=[2023] or self.scaler['fit_role']!='Train' or self.scaler['fit_scene_count']!=TRAIN_N or
            not self.scaler['all_six_slots_share_identical_scaler'] or self.protocol['B0_MATCHED_CONTROL_NORMALIZATION']!='USE_FROZEN_B1_SHARED_SCALER'):
            raise ValueError('FROZEN_SHARED_SCALER_IDENTITY')
        self.by_id={r['sample_id']:r for rows in self.rows.values() for r in rows}
        self.identity=dict(train_ids_sha=digest(self.ids(2023)),development_ids_sha=digest(self.ids(2024)),
            protocol_sha=PROTOCOL_SHA,source_inventory_sha=SOURCE_SHA,mask_sha=self.mask_ref['sha256'],
            scaler_sha=norm['sha256'],sp04_sha=self.protocol['identity']['SP04_mapping']['sha256'],
            public_pins=self.public.pins,unique_payload_files=67006,late_file_creation_references=self.late_creation)
        budget.emit('FULL_FROZEN_PLAN_VALIDATED',**self.identity)
    def ids(self,year: int) -> tuple[str,...]: return tuple(r['sample_id'] for r in self.rows[year])

class Reader(VerifiedReader):
    """P1 same-handle read algorithm with formal budgets and bounded retention."""
    def read(self,path: str) -> bytes:
        text,expected,frozen_size,group=self.authenticate(path) # before any filesystem operation
        key=sha((group+'\0'+text).encode()); start=time.perf_counter()
        record=dict(file_key=key,group=group,expected_sha256=expected,actual_sha256=None,bytes=0,
                    status='ATTEMPTED',opened_utc=utcnow())
        self.budget.emit('READ_RESERVED',**record)
        try:
            self.budget.check()
            with ReadHandle(text,payload=True) as handle:
                self.plan.scope.authenticate_final(text,handle.final_path); size=handle.before['size']
                if frozen_size is not None and size!=frozen_size: raise ValueError('FROZEN_CONTENT_SIZE')
                self.budget.admit_bytes(size)
                if self.budget.check()['working_set_bytes']+3*size+256*1024**2>LIMITS['max_working_set_bytes']:
                    raise MemoryError('IMMUTABLE_DECODE_MEMORY_ADMISSION')
                buf=bytearray(size); count=0; h=hashlib.sha256()
                while count<size:
                    self.budget.check(); n=handle.readinto(memoryview(buf)[count:count+min(8*1024**2,size-count)])
                    if not n: raise EOFError('FROZEN_PAYLOAD_TRUNCATED')
                    self.budget.account_bytes(n); h.update(memoryview(buf)[count:count+n]); count+=n;record['bytes']=count
                if handle.readinto(bytearray(1)) or handle.snapshot()!=handle.before: raise ValueError('PAYLOAD_CHANGED_DURING_HANDLE')
                record['actual_sha256']=h.hexdigest()
                if record['actual_sha256']!=expected: raise ValueError('SAME_CONSUMED_BYTES_SHA_MISMATCH')
                result=bytes(buf)
            record['status']='SHA_PASS'; return result
        except BaseException as exc:
            record['status']='FAILED'; record['error_type']=type(exc).__name__;self.budget.stopped=True; raise
        finally:
            record['closed_utc']=utcnow();record['read_sha_seconds']=time.perf_counter()-start
            self.budget.emit('READ_FINISHED',**record)
    def full_metadata_gate(self) -> dict:
        total=0; groups={}; count=0
        for path,(kind,year,expected,size) in self.plan.scope.entries.items():
            self.authenticate(path); self.budget.check()
            with ReadHandle(path) as handle:
                self.plan.scope.authenticate_final(path,handle.final_path)
                if handle.before['size']<=0 or (size is not None and handle.before['size']!=size): raise ValueError('FULL_METADATA_FILE_SIZE')
                total+=handle.before['size']; groups[kind]=groups.get(kind,0)+1; count+=1
        if count!=67006 or groups!={'IMERG':490,'B13':66516}: raise ValueError('FULL_METADATA_COUNTS')
        result=dict(files=count,groups=groups,current_total_payload_bytes=total,
                    payload_sha_policy='STRICT_SHA_ON_EVERY_CACHE_MISS_BEFORE_MEMORY_DECODING',
                    prior_full_payload_sha_pass=True,new_full_payload_rescan=False)
        self.budget.emit('FULL_METADATA_GATE_PASS',**result);return result

class Cache:
    def __init__(self,limit: int): self.limit=limit;self.bytes=0;self.items=OrderedDict()
    def get(self,key):
        if key not in self.items:return None
        self.items.move_to_end(key);return self.items[key][0]
    def put(self,key,value,size):
        if key in self.items:raise ValueError('CACHE_DUPLICATE')
        if size>self.limit:raise MemoryError('IMMUTABLE_CACHE_OBJECT_LIMIT')
        while self.bytes+size>self.limit:
            _,(_,n)=self.items.popitem(last=False);self.bytes-=n
        self.items[key]=(value,size);self.bytes+=size

class Adapter(RealAdapter):
    def __init__(self,plan: Plan,budget):
        self.plan,self.budget=plan,budget;self.owner=object();self.mapping=None
        self.reader=Reader(plan,budget)
        self.frames_cache=Cache(LIMITS['frame_cache_bytes']);self.target_cache=Cache(LIMITS['target_cache_bytes'])
        self.daily_cache=Cache(64*1024**2)
    def frame(self,nominal: str):
        frame=self.plan.frames[nominal];key=(nominal,frame['source_sha256'])
        hit=self.frames_cache.get(key)
        if hit is not None:return hit
        payload=self.reader.read(ntpath.join(self.plan.h_root,frame['relative_path']))
        with self.reader.view(payload,'pilot_b13_readonly.nc'):
            x,valid,actual=read_b13_local(Path('pilot_b13_readonly.nc'),self.mapping,nominal)
        if (x.shape!=(501,501) or x.dtype!=np.float32 or valid.dtype!=bool or not valid.all() or not np.isfinite(x).all() or
            actual.obs_start!=utc(frame['obs_start']) or actual.obs_end!=utc(frame['obs_end']) or actual.date_created!=utc(frame['date_created'])):
            raise ValueError('ACTUAL_B13_FROZEN_CONTRACT')
        normalized=normalize_frozen(x,self.plan.scaler)
        if normalized.dtype!=np.float32 or not np.isfinite(normalized).all(): raise ValueError('FROZEN_NORMALIZATION')
        normalized.setflags(write=False);self.frames_cache.put(key,normalized,normalized.nbytes)
        return normalized
    def target(self,row: dict):
        key=(row['sample_id'],row['imerg_sha256']);hit=self.target_cache.get(key)
        if hit is not None:return hit
        daykey=(canonical(row['imerg_day_path']),row['imerg_sha256']);payload=self.daily_cache.get(daykey)
        if payload is None:
            payload=self.reader.read(row['imerg_day_path']);self.daily_cache.put(daykey,payload,len(payload))
        alias='pilot_imerg_readonly.nc'
        with self.reader.view(payload,alias) as view:
            with view(alias) as ds:
                if ds.source!='GPM_3IMERGHH_07' or 'IMERG Final Run V07' not in ds.title or ds['precipitation'].shape!=(48,130,140):
                    raise ValueError('IMERG_FINAL_V07_SOURCE')
            y,valid,t=read_imerg_local(Path(alias),int(row['imerg_index']),self.mapping)
        if (t!=utc(row['window_start']) or y.shape!=(100,100) or y.dtype!=np.float32 or valid.dtype!=bool or
            int((valid & self.yunnan).sum())!=3430 or not np.isfinite(y[valid]).all() or (y[valid]<0).any() or np.isfinite(y[~valid]).any()):
            raise ValueError('ACTUAL_FROZEN_REFERENCE')
        y.setflags(write=False);valid.setflags(write=False)
        self.target_cache.put(key,(y,valid),y.nbytes+valid.nbytes);return y,valid
    def batch(self,ids: tuple[str,...],model: str,year: int):
        max_b=2 if year==2023 else 8
        if model not in ('B0_MATCHED_V2','B1_V2') or not 1<=len(ids)<=max_b or len(set(ids))!=len(ids): raise ValueError('BATCH_MODEL_OR_SIZE')
        x,y,v,source=[],[],[],[]
        for ident in ids:
            row=self.plan.by_id[ident]
            if int(row['year'])!=year:raise PermissionError('TRAIN_DEVELOPMENT_ROLE')
            slots=range(6) if model=='B1_V2' else (5,)
            x.append(np.stack([self.frame(row[f'slot_{s}_nominal']) for s in slots]))
            rate,valid=self.target(row);y.append(rate[None]);v.append(valid[None])
            source.append(dict(scene_key=sha(ident.encode()),b13_sha=[self.plan.frames[row[f'slot_{s}_nominal']]['source_sha256'] for s in slots],
                               imerg_sha=row['imerg_sha256']))
        x=torch.from_numpy(np.stack(x));rate=torch.from_numpy(np.stack(y));valid=torch.from_numpy(np.stack(v))
        region=torch.from_numpy(np.stack([self.yunnan[None]]*len(ids)))
        if (x.dtype!=torch.float32 or not bool(torch.isfinite(x).all()) or
            not bool(((valid & region).flatten(1).sum(1)==3430).all())):raise ValueError('FORMAL_BATCH_CONTRACT')
        self.budget.emit('BATCH_DECODED',model=model,year=year,scenes=source,shape=list(x.shape),
                         supervision_sha=sha(rate.numpy().tobytes()+valid.numpy().tobytes()+region.numpy().tobytes()))
        return tuple(t.to('cuda:0') for t in (x,torch.ones_like(x,dtype=torch.bool),rate,valid,region))
