"""Once-only completion of the existing 2024 Dev metric backfill.

Retain six COMPLETE results and all interrupted directories. No training,
automatic retry, output replacement or changes to the scientific evaluator.
Private source paths and subprocess identifiers never enter public receipts.
"""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone

ROOT=Path(__file__).resolve().parents[2]


def read(path): return json.loads(Path(path).read_text(encoding='utf-8-sig'))
def sha(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def write(path,obj):
    with Path(path).open('x',encoding='utf-8') as f: json.dump(obj,f,ensure_ascii=False,indent=2,allow_nan=False)
def now(): return datetime.now(timezone.utc).isoformat()
def module(path,name):
    spec=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(spec);sys.modules[name]=m;spec.loader.exec_module(m);return m


def valid_result(path,run):
    x=read(path)
    if x.get('status')!='COMPLETE' or x.get('gate',{}).get('passed') is not True or x.get('run_id')!=run['run_id']:
        raise ValueError('No COMPLETE frozen-metric gate: '+run['run_id'])
    if x['checkpoint_identity']['expected_sha256']!=run['checkpoint_sha256']:
        raise ValueError('Checkpoint identity changed')
    return x


def validate(s):
    if s.get('authorization_basis')!='CURRENT_USER_FINISH_EXISTING_METRIC_BACKFILL_20261030':
        raise PermissionError('Completion instruction required; never a training grant')
    for key in ('engine','registry'):
        if sha(s[key])!=s[key+'_sha256']:raise ValueError('Pinned backfill component changed: '+key)
    registry=read(s['registry']);runs={r['run_id']:r for r in registry['runs']}
    if len(runs)!=19 or len(s['inherited'])!=6 or len(s['remaining'])!=13:
        raise ValueError('Expected exact 19-model backfill scope')
    if set(s['inherited']) & set(s['remaining']) or set(s['inherited'])|set(s['remaining'])!=set(runs):
        raise ValueError('Duplicate or omitted run')
    for rid,info in s['inherited'].items():
        if sha(info['result'])!=info['sha256']:raise ValueError('Inherited result changed')
        valid_result(info['result'],runs[rid])
    return runs


def worker(s,rid):
    runs=validate(s);run=runs[rid]
    if rid not in s['remaining']:raise PermissionError('Never rerun a successful result')
    out=Path(s['new_output_root']);claim=read(out/(rid+'_claim.json'))
    if claim['parent_pid']!=os.getppid():raise PermissionError('Live serial controller required')
    host=module(ROOT/'tools/research_readiness/start_independent_process.py','metric_host_worker')
    host.require_independent(host.host_identity())
    m=module(s['engine'],'pinned_metric_backfill')
    m.OUTPUT_ROOT=str(out/'runs');m.LOG_ROOT=str(out/'logs')
    # Tighten the legacy inference-only BudgetStub's 32TiB default. Preserve
    # its original accounting and all readers/masks/precision/evaluation rules.
    old=m.FrozenBudgetStub;cap=s['caps'][rid]['source_bytes']
    class BoundedBudget(old):
        def __init__(self,*args,**kwargs):super().__init__(max_read_bytes=cap)
        def record(self,state,size):
            with (out/(rid+'_source_accounting.jsonl')).open('ab',buffering=0) as f:
                f.write((json.dumps(dict(at=now(),state=state,size=size,delivered_bytes=self.bytes))+'\n').encode())
        def admit_bytes(self,size):
            result=super().admit_bytes(size);self.record('ADMITTED_BEFORE_READ',size);return result
        def account_bytes(self,size):
            super().account_bytes(size);self.record('DELIVERED',size)
    m.FrozenBudgetStub=BoundedBudget
    import torch
    torch.set_num_threads(1);torch.set_grad_enabled(False)
    def forbidden(*args,**kwargs):raise PermissionError('Metric backfill cannot construct an optimizer')
    torch.optim.Optimizer.__init__=forbidden
    result=m.run_one(rid,verify_sha=True)
    if result['status']!='COMPLETE' or result['gate']['passed'] is not True:raise RuntimeError('Frozen metric gate failed')
    io=result['read_scope_actual'];actual=io.get('content_bytes_read',io.get('meter_totals',{}).get('delivered_bytes'))
    if actual is None or actual>cap:raise RuntimeError('Actual IO exceeds bounded completion scope')
    write(out/(rid+'_verified.json'),dict(at=now(),result_sha256=sha(out/'runs'/rid/'result.json'),source_bytes=actual,
          source_cap_bytes=cap,optimizer_updates=0,gate_passed=True))


def execute(s,private):
    runs=validate(s);out=Path(s['new_output_root'])
    if out.exists():raise PermissionError('Consumed namespace; no automatic retry')
    if shutil.disk_usage(out.parent).free<2*1024**3:raise RuntimeError('Need2GiB for new inference receipts; preserve history')
    host=module(ROOT/'tools/research_readiness/start_independent_process.py','metric_host_controller')
    host.require_independent(host.host_identity())
    out.mkdir();write(out/'binding.json',dict(at=now(),private_sha256=sha(private),engine_sha256=s['engine_sha256'],
        inherited_complete=6,new_tasks=13,old_partial_io=s['old_partial_io'],training_authorized=False,
        automatic_retry=False,host=host.host_identity()))
    started=time.monotonic();child=None
    try:
        for rid in s['remaining']:
            remaining=s['maximum_seconds']-(time.monotonic()-started)
            if remaining<=0:raise RuntimeError('Serial completion time cap')
            free=int(subprocess.check_output(['nvidia-smi','--query-gpu=memory.free','--format=csv,noheader,nounits'],text=True).splitlines()[0])
            if free<5120:raise RuntimeError('Need5GiB free GPU; no parallel inference or training')
            write(out/(rid+'_claim.json'),dict(at=now(),parent_pid=os.getpid(),automatic_retry=False))
            env=dict(os.environ,PYTHONPATH=str(Path(runs[rid]['code_root'])/'src')+os.pathsep+s['torch_site'],PYTHONHASHSEED=str(runs[rid]['seed']),
                CUBLAS_WORKSPACE_CONFIG=':4096:8',PYTHONUTF8='1',PYTHONDONTWRITEBYTECODE='1',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1')
            with (out/(rid+'_console.log')).open('xb') as log:
                child=subprocess.Popen([sys.executable,'-B',str(Path(__file__).resolve()),'worker','--private',str(private.resolve()),'--run-id',rid],
                    cwd=ROOT,env=env,stdout=log,stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NO_WINDOW)
                try:rc=child.wait(timeout=min(remaining,s['caps'][rid]['seconds']))
                except subprocess.TimeoutExpired:child.kill();child.wait();raise RuntimeError('Run time cap; no retry')
            if rc:raise RuntimeError('Worker stopped: '+rid+'; no retry or later tasks')
            valid_result(out/'runs'/rid/'result.json',runs[rid])
        all_results={rid:dict(path=v['result'],sha256=v['sha256']) for rid,v in s['inherited'].items()}
        for rid in s['remaining']:
            path=out/'runs'/rid/'result.json';all_results[rid]=dict(path=str(path),sha256=sha(path))
        for rid,info in all_results.items():valid_result(info['path'],runs[rid])
        write(out/'completion.json',dict(status='COMPLETE_19_E9_DEV_METRIC_BACKFILL',at=now(),registry_sha256=s['registry_sha256'],
             results=all_results,new_tasks=13,inherited_tasks=6,optimizer_updates=0,automatic_retry=False,final_2025='FROZEN_NO_ACCESS'))
        # Only an independently approved, exact training specification can be
        # queued here. Absence of approval leaves this stage complete, not failed.
        armed=Path(s['after_completion_training_spec'])
        if armed.is_file():
            spec=read(armed)
            if spec.get('kind')!='APPROVAL_BOUND_EXECUTION':raise PermissionError('No unbound follow-on training')
            receipt=host.spawn(armed);write(out/'approved_follow_on_launch.json',receipt)
        else:write(out/'follow_on_waiting.json',dict(status='WAITING_EXACT_TRAINING_APPROVAL',at=now()))
    except BaseException as exc:
        if child is not None and child.poll() is None:child.kill();child.wait()
        write(out/'failure.json',dict(status='STOP_PRESERVE_ALL_NO_AUTO_RETRY',at=now(),error=type(exc).__name__+': '+str(exc),
             optimizer_updates=0,partial_IO='SEE_OLD_AND_NEW_LEDGERS_NOT_ZERO'))
        raise


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('mode',choices=('execute','worker'));p.add_argument('--private',type=Path,required=True);p.add_argument('--run-id');a=p.parse_args()
    s=read(a.private)
    if a.mode=='worker':worker(s,a.run_id)
    else:execute(s,a.private)
