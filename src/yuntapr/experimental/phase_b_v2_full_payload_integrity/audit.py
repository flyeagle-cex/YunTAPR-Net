"""Exact frozen inventory, metadata admission, durable bounded SHA receipts."""
from __future__ import annotations
import ast
import csv
from datetime import datetime,timezone
import hashlib
import io
import json
import ntpath
import os
from pathlib import Path
import re
import sqlite3
import shutil
import sys
import time

ROOT=Path(__file__).absolute().parents[4]
OUT=ROOT/'docs/phase_b_v2_full_payload_integrity/v1'
BASELINE='5da0a6081f9d3953cf59f7c6d71aedaf74e951f2'
PROTOCOL='config/science_v2/phase_a_protocol_frozen_v1.json'
PROTOCOL_SHA='a0141f21cfa997d5adb72dff5afb32b17dc7edcf5f3397fc9c4bfe2ea42048be'
HARDENED='src/yuntapr/experimental/phase_b_v2_real_data_preflight/audit.py'
HARDENED_SHA='c4d749c2190a0e23a44d86535a02a6ca0d51274f096418d935d2acd294507f35'
FRAME_SHA='a5054200d6bde11f2342c292ca72428d0558d5b5c5c640017844f0b4ed8c540e'
LIMIT_BYTES=500*1024**3
LIMIT_SECONDS=6*3600
CHUNK=8*1024**2
FLAGS={'V2_PHASE_B_AUTHORIZED':False,'FORMAL_SCIENTIFIC_EXECUTION_AUTHORIZED':False,
       'FORMAL_OPTIMIZER_STEPS':0,'HISTORICAL_RECOVERY_RATIFICATION':'NOT_GRANTED','2025_PIXELS_READ':0,
       'historical_2025_path_attributes':'NOT_INSTRUMENTED','model_forwards':0,'historical_checkpoint_reads':0}

def utcnow():return datetime.now(timezone.utc).isoformat()
def sha(data):return hashlib.sha256(data).hexdigest()
def canonical(text):return ntpath.normcase(ntpath.normpath(text))
def valid_sha(value):
    if type(value) is not str or re.fullmatch('[0-9a-f]{64}',value) is None:raise ValueError('Missing/noncanonical expected SHA')

class Scope:
    def __init__(self,roots):self.roots={k:canonical(v) for k,v in roots.items()};self.entries={};self.parents=set()
    def lexical(self,path,kind,year):
        if type(path) is not str or kind not in self.roots or type(year) is not int or year not in (2023,2024):
            raise PermissionError('Closed frozen years/kinds')
        raw=path.replace('/','\\');parts=raw.split('\\')
        if not ntpath.isabs(raw) or raw.startswith('\\\\') or any(x in ('.','..') for x in parts) or raw.count(':')!=1:
            raise PermissionError('Absolute drive path without traversal/device/stream syntax')
        text=canonical(raw);base=self.roots[kind]
        if not text.startswith(base+'\\'):raise PermissionError('Exact frozen root required before filesystem API')
        rel=text[len(base)+1:]
        if '2025' in rel or text.endswith(('.pt','.pth','.ckpt')):raise PermissionError('Sealed year/checkpoint rejected lexically')
        match=re.search(r'(202[0-9])(\d{2})',rel if kind=='B13' else ntpath.basename(rel))
        if not match or int(match[1])!=year or not 3<=int(match[2])<=10 or not text.endswith('.nc'):
            raise PermissionError('Frozen date/extension rejected before filesystem API')
        return text
    def register(self,path,kind,year,expected,size):
        key=self.lexical(path,kind,year);valid_sha(expected)
        if size is not None and (type(size) is not int or size<=0):raise ValueError('Frozen positive size required')
        value=(kind,year,expected,size)
        if key in self.entries and self.entries[key]!=value:raise ValueError('Conflicting deduplicated source identity')
        if key not in self.entries:
            self.entries[key]=value;p=ntpath.dirname(key)
            while p!=self.roots[kind]:self.parents.add(p);p=ntpath.dirname(p)
            self.parents.add(p)
        return key
    def authorized(self,path):
        text=canonical(path)
        if text not in self.entries:raise PermissionError('No unregistered source access')
        kind,year,_,_=self.entries[text];self.lexical(path,kind,year)
        return text
    def directory(self,path):
        text=canonical(path)
        if text not in self.parents:raise PermissionError('Only exact induced parent metadata')
        return text
    def authenticate_final(self,requested,actual):
        if canonical(requested)!=canonical(actual):raise PermissionError('Handle target differs from lexical frozen reference')

class Journal:
    def __init__(self,path):
        self.con=sqlite3.connect(path,isolation_level=None)
        self.con.execute('PRAGMA journal_mode=DELETE');self.con.execute('PRAGMA synchronous=FULL');self.con.execute('PRAGMA cache_size=-2048')
        self.con.execute('CREATE TABLE meta(key TEXT PRIMARY KEY,value TEXT)')
        self.con.execute('CREATE TABLE files(i INTEGER PRIMARY KEY,path TEXT UNIQUE,kind TEXT,year INTEGER,file_key TEXT,expected_sha TEXT,frozen_size INTEGER,size INTEGER,signature TEXT,status TEXT,actual_sha TEXT,read_bytes INTEGER DEFAULT 0,payload_attempts INTEGER DEFAULT 0,metadata_attempts INTEGER DEFAULT 0,payload_success INTEGER DEFAULT 0,metadata_success INTEGER DEFAULT 0,error TEXT,seconds REAL DEFAULT 0,opened_utc TEXT,closed_utc TEXT)')
    def set(self,key,value):self.con.execute('INSERT OR REPLACE INTO meta VALUES(?,?)',(key,json.dumps(value,allow_nan=False)))
    def get(self,key,default=None):
        row=self.con.execute('SELECT value FROM meta WHERE key=?',(key,)).fetchone();return json.loads(row[0]) if row else default

def memory():
    import ctypes
    from ctypes import wintypes
    class Counters(ctypes.Structure):
        _fields_=[('cb',wintypes.DWORD),('faults',wintypes.DWORD)]+[(n,ctypes.c_size_t) for n in ('peak','working','qpp','pp','qpnp','pnp','pagefile','peakpagefile','private')]
    k=ctypes.WinDLL('kernel32',use_last_error=True);k.GetCurrentProcess.restype=wintypes.HANDLE
    f=ctypes.WinDLL('psapi',use_last_error=True).GetProcessMemoryInfo
    f.argtypes=[wintypes.HANDLE,ctypes.POINTER(Counters),wintypes.DWORD];f.restype=wintypes.BOOL
    c=Counters();c.cb=ctypes.sizeof(c)
    if not f(k.GetCurrentProcess(),ctypes.byref(c),c.cb):raise ctypes.WinError(ctypes.get_last_error())
    return {'working_set_bytes':int(c.working),'peak_working_set_bytes':int(c.peak),'private_bytes':int(c.private),'peak_pagefile_bytes':int(c.peakpagefile)}

class Audit:
    def __init__(self,private):
        self.j=Journal(private/'journal.sqlite');self.start=time.monotonic();self.pins=[];self.handles=[];self.last_progress=0.;self.raw_bytes=0
        for k,v in dict(started_at_utc=utcnow(),stage='BUILDING_PLAN',raw_bytes=0,inflight_requested_bytes=0,directory_metadata_opens=0,public_metadata_bytes=0).items():self.j.set(k,v)
    def check(self):
        if time.monotonic()-self.start>=LIMIT_SECONDS:raise TimeoutError('SIX_HOUR_HARD_CAP')
        r=memory();self.j.set('resources',r)
        if r['working_set_bytes']>2*1024**3:raise MemoryError('TWO_GIB_WORKING_SET_CAP')
        if shutil.disk_usage(OUT).free<256*1024**2:raise OSError('AUDIT_SCRATCH_STORAGE_BELOW_256_MIB')
        self.j.set('elapsed_seconds',time.monotonic()-self.start)
    def progress(self,force=False):
        if force or time.monotonic()-self.last_progress>=30:
            self.check();self.last_progress=time.monotonic()
            counts=dict(self.j.con.execute('SELECT status,COUNT(*) FROM files GROUP BY status'))
            print(json.dumps({'stage':self.j.get('stage'),'counts':counts,'read_GiB':self.raw_bytes/1024**3,'elapsed_seconds':time.monotonic()-self.start,'expected_GiB':self.j.get('predicted_bytes',0)/1024**3}),flush=True)
    def public(self,relative,expected):
        # Repository metadata only, exactly pinned; never scaler/mask/checkpoint.
        valid_sha(expected);text=relative.replace('\\','/')
        if text.startswith('/') or ':' in text or any(x in ('','..','.') for x in text.split('/')) or not text.endswith(('.py','.json','.csv','.yaml')):
            raise PermissionError('Exact public metadata path')
        raw=(ROOT/text).read_bytes()
        if sha(raw)!=expected:raise ValueError('Public source identity mismatch')
        self.pins.append(dict(path=text,sha256=expected,bytes=len(raw)));self.j.set('public_metadata_bytes',self.j.get('public_metadata_bytes')+len(raw))
        return raw
    def build(self):
        import subprocess
        if subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()!=BASELINE:raise ValueError('Baseline mismatch')
        self.public(HARDENED,HARDENED_SHA)
        protocol=json.loads(self.public(PROTOCOL,PROTOCOL_SHA))
        contract=protocol['identity']['scientific_contract_v1.1'];self.public(contract['path'],contract['sha256'])
        source='src/yuntapr/data/dataset_b1.py'
        expected=next(e['sha256'] for e in json.loads((ROOT/'docs/phase_b_v2_formal_integration_engineering/v1/source_identity.json').read_text())['public_source_files'] if e['path']==source)
        tree=ast.parse(self.public(source,expected));constants={}
        for node in tree.body:
            if isinstance(node,ast.Assign) and len(node.targets)==1 and isinstance(node.targets[0],ast.Name):
                name=node.targets[0].id
                if name in ('H_ROOT','IMERG_ROOT','AUDIT') and isinstance(node.value,ast.Call):constants[name]=ast.literal_eval(node.value.args[0])
        self.scope=Scope({'B13':constants['H_ROOT'],'IMERG':constants['IMERG_ROOT']})
        index=json.loads(self.public(constants['AUDIT']+'/frame_identity_index.json',FRAME_SHA));frames={}
        for rel,expected in index['files'].items():
            for row in csv.DictReader(io.StringIO(self.public(constants['AUDIT']+'/'+rel,expected).decode('utf-8-sig'))):
                if row['nominal'] in frames:raise ValueError('Duplicate frame nominal')
                frames[row['nominal']]=row
        for year in (2023,2024):
            records={}
            for model in ('B1','B0_MATCHED'):
                ref=protocol['identity'][f'{model}_{year}'];records[model]=list(csv.DictReader(io.StringIO(self.public(ref['path'],ref['sha256']).decode('utf-8-sig'))))
            a,b=records['B1'],records['B0_MATCHED'];n=10455 if year==2023 else 10501
            if len(a)!=n or len(b)!=n or len({r['sample_id'] for r in a})!=n:raise ValueError('Frozen scene counts/identity')
            for i,(row,anchor) in enumerate(zip(a,b)):
                if int(row['index'])!=i or int(row['year'])!=year or row['frame_identity_index_sha256']!=FRAME_SHA or row['eligibility']!='FORMAL_M1_COMMON_INTERSECTION':raise ValueError('Frozen M1 metadata mismatch')
                keys=('sample_id','window_start','analysis_time','imerg_day_path','imerg_index','imerg_sha256','role','eligibility')
                if any(row[k]!=anchor[k] for k in keys) or anchor['expected_nominal']!=row['slot_5_nominal']:raise ValueError('B0/B1 pairing mismatch')
                self.scope.register(row['imerg_day_path'],'IMERG',year,row['imerg_sha256'],None)
                for slot in range(6):
                    frame=frames[row[f'slot_{slot}_nominal']]
                    if datetime.fromisoformat(frame['nominal']).year!=year:raise ValueError('Frame role year mismatch')
                    if slot==5 and (anchor['b13_sha256']!=frame['source_sha256'] or anchor['b13_relative_path']!=frame['relative_path'] or int(anchor['b13_bytes'])!=int(frame['source_bytes'])):raise ValueError('Latest frame identity')
                    self.scope.register(ntpath.join(constants['H_ROOT'],frame['relative_path']),'B13',year,frame['source_sha256'],int(frame['source_bytes']))
            self.progress()
        counts={k:sum(v[0]==k for v in self.scope.entries.values()) for k in ('B13','IMERG')}
        if counts!={'B13':66516,'IMERG':490}:raise ValueError('Exact 67006 deduplicated inventory required')
        for i,(path,(kind,year,expected,size)) in enumerate(self.scope.entries.items()):
            rel=path[len(self.scope.roots[kind])+1:];key=sha((kind+'\0'+str(year)+'\0'+rel).encode())
            self.j.con.execute('INSERT INTO files(i,path,kind,year,file_key,expected_sha,frozen_size,status) VALUES(?,?,?,?,?,?,?,?)',(i,path,kind,year,key,expected,size,'NOT_READ'))
        self.j.set('source_pins',self.pins);self.j.set('inventory_counts',counts);self.j.set('inventory_order','2023 then 2024; original B1 rows; IMERG then slots0..5; first occurrence dedup')
    def directories(self):
        from .winio import ReadHandle
        if len(self.scope.parents)>4096:raise RuntimeError('Directory handle resource cap')
        for path in sorted(self.scope.parents,key=lambda p:(p.count('\\'),p)):
            self.scope.directory(path);h=ReadHandle(path,directory=True)
            try:self.scope.authenticate_final(path,h.final_path)
            except BaseException:h.close();raise
            self.handles.append(h);self.j.set('directory_metadata_opens',len(self.handles));self.check()
    def estimate(self):
        from .winio import ReadHandle
        self.j.set('stage','METADATA');self.directories();total=0
        for i,path,kind,year,expected,size in self.j.con.execute('SELECT i,path,kind,year,expected_sha,frozen_size FROM files ORDER BY i'):
            try:
                self.check();self.scope.authorized(path);self.j.con.execute('UPDATE files SET metadata_attempts=1 WHERE i=?',(i,))
                with ReadHandle(path) as h:
                    self.j.con.execute('UPDATE files SET metadata_success=1 WHERE i=?',(i,))
                    self.scope.authenticate_final(path,h.final_path);signature=h.before
                if size is not None and signature['size']!=size:raise ValueError('Frozen B13 size mismatch')
                if signature['size']<=0:raise ValueError('Empty frozen payload')
                total+=signature['size'];self.j.con.execute('UPDATE files SET size=?,signature=? WHERE i=?',(signature['size'],json.dumps(signature),i))
                self.j.set('predicted_bytes_partial',total);self.progress()
            except BaseException as error:
                self.j.con.execute('UPDATE files SET status=?,error=? WHERE i=?',('METADATA_FAILED',json.dumps(reason(error)),i));raise
        self.j.set('predicted_bytes',total)
        if total+self.j.get('public_metadata_bytes')>LIMIT_BYTES:raise MemoryError('PREDICTED_BYTES_EXCEED_500_GIB_NO_PAYLOAD_OPEN')
    def hash_all(self):
        from .winio import ReadHandle
        self.j.set('stage','HASHING');buffer=bytearray(CHUNK)
        for i,path,expected,size,signature in self.j.con.execute('SELECT i,path,expected_sha,size,signature FROM files ORDER BY i'):
            start=time.monotonic();nread=0;hsh=hashlib.sha256();actual=None
            try:
                self.check();self.scope.authorized(path);self.j.con.execute('UPDATE files SET status=?,payload_attempts=1,opened_utc=? WHERE i=?',('READING',utcnow(),i))
                with ReadHandle(path,payload=True) as handle:
                    self.j.con.execute('UPDATE files SET payload_success=1 WHERE i=?',(i,))
                    self.scope.authenticate_final(path,handle.final_path)
                    if handle.before!=json.loads(signature):raise ValueError('File identity/size/mtime changed after metadata plan')
                    while nread<size:
                        self.check();request=min(CHUNK,size-nread)
                        if self.raw_bytes+request+self.j.get('public_metadata_bytes')>LIMIT_BYTES:raise MemoryError('ACTUAL_500_GIB_CAP')
                        self.j.set('inflight_requested_bytes',request)
                        n=handle.readinto(memoryview(buffer)[:request])
                        if not n:raise EOFError('Unexpected short frozen payload')
                        self.raw_bytes+=n;nread+=n;hsh.update(memoryview(buffer)[:n])
                        self.j.con.execute('BEGIN IMMEDIATE')
                        try:
                            self.j.con.execute('UPDATE files SET read_bytes=? WHERE i=?',(nread,i));self.j.set('raw_bytes',self.raw_bytes);self.j.set('inflight_requested_bytes',0);self.j.con.execute('COMMIT')
                        except BaseException:self.j.con.execute('ROLLBACK');raise
                        self.progress()
                    if handle.snapshot()!=handle.before:raise ValueError('Handle metadata changed during hashing')
                actual=hsh.hexdigest()
                if actual!=expected:raise ValueError('PAYLOAD_SHA_MISMATCH')
                self.j.con.execute('UPDATE files SET status=?,actual_sha=?,seconds=?,closed_utc=? WHERE i=?',('SHA_PASS',actual,time.monotonic()-start,utcnow(),i))
            except BaseException as error:
                self.j.con.execute('UPDATE files SET status=?,actual_sha=?,read_bytes=?,error=?,seconds=?,closed_utc=? WHERE i=?',('FAILED',actual,nread,json.dumps(reason(error)),time.monotonic()-start,utcnow(),i));raise
        self.j.set('stage','COMPLETE')
    def run(self):
        try:self.build();self.estimate();self.progress(True);self.hash_all()
        except BaseException as error:
            self.j.set('stage','STOPPED');self.j.set('failure',reason(error));print(json.dumps({'stage':'STOPPED','failure':reason(error)}),flush=True)
        finally:
            for h in reversed(self.handles):h.close()
            self.j.set('finished_at_utc',utcnow());self.j.set('elapsed_seconds',time.monotonic()-self.start);self.j.set('resources',memory());self.j.con.close()

def reason(error):
    text=str(error)
    safe=text if text.isascii() and ':\\' not in text and '/' not in text else 'See exception type and OS error; paths withheld'
    return {'type':type(error).__name__,'reason':safe,'errno':getattr(error,'errno',None),'winerror':getattr(error,'winerror',None)}
