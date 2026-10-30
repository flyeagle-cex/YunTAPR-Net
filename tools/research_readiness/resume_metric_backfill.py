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
def digest(value):return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()
def module(path,name):
    spec=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(spec);sys.modules[name]=m;spec.loader.exec_module(m);return m


def install_historical_b01_context(engine,torch):
    """Match the actual seeded Engine.run_one -> inference_mode validate scope.

    The pinned external adapter incorrectly assumed validate ran AFTER the
    seeded_environment exited. Preserve that historical file and wrap only
    B0/B1; the fifteen already-matched core-model results are unchanged.
    """
    original=engine._apply_historical_determinism
    def configure(family,seed,dry_check):
        if family!='b01' or dry_check:return original(family,seed,dry_check)
        torch.use_deterministic_algorithms(True,warn_only=False)
        torch.backends.cudnn.deterministic=True
        torch.backends.cudnn.benchmark=False
        torch.set_float32_matmul_precision('highest')
        torch.backends.cuda.matmul.allow_tf32=False
        torch.backends.cudnn.allow_tf32=False
    engine._apply_historical_determinism=configure
    batches=engine.B01Adapter.batches
    def historical_batches(adapter):
        # Model construction/state loading remains outside inference_mode, as
        # in the original Engine. Inputs, forward and evaluation stay inside.
        with torch.inference_mode():
            yield from batches(adapter)
    engine.B01Adapter.batches=historical_batches


def valid_result(path,run):
    x=read(path)
    if x.get('status')!='COMPLETE' or x.get('gate',{}).get('passed') is not True or x.get('run_id')!=run['run_id']:
        raise ValueError('No COMPLETE frozen-metric gate: '+run['run_id'])
    if x['checkpoint_identity']['expected_sha256']!=run['checkpoint_sha256'] or x['checkpoint_identity'].get('sha256_actual',run['checkpoint_sha256'])!=run['checkpoint_sha256']:
        raise ValueError('Checkpoint identity changed')
    return x


def correction_grant(s):
    """A failed pass is never retried using the consumed original namespace."""
    p=read(s['correction_proposal'])
    if digest({k:v for k,v in p.items() if k!='proposal_sha256'})!=p['proposal_sha256']:raise ValueError('Correction proposal changed')
    approval=read(s['researcher_approval'])
    expected=dict(proposal_sha256=p['proposal_sha256'],execution_code_commit=p['execution_code_commit'],tasks=p['tasks'],budget=p['budget'],output_root=s['new_output_root'])
    if approval.get('approved_by_researcher') is not True or not approval.get('decision_id') or any(approval.get(k)!=v for k,v in expected.items()):raise PermissionError('Exact corrective metric-read grant required')
    if p['tasks']!=s['remaining'] or p['budget']['caps']!=s['caps'] or p['budget']['maximum_seconds']!=s['maximum_seconds']:raise ValueError('Correction scope changed')
    if p['engine_sha256']!=s['engine_sha256'] or p['registry_sha256']!=s['registry_sha256']:raise ValueError('Correction source identity changed')
    for name,expected_sha in p['code_sha256'].items():
        if sha(ROOT/name)!=expected_sha:raise ValueError('Correction execution code changed: '+name)
    return p


def resource_admission(folder):
    status=module(ROOT/'tools/core_stage4/monitor/server.py','metric_admission_resources').resources(folder)
    gpu=status.get('gpu') or {};memory=status.get('memory') or {}
    if (gpu.get('total_mib',0)-gpu.get('used_mib',0))<5120:raise RuntimeError('Need5GiB free GPU; no parallel inference or training')
    if memory.get('available',0)<8*1024**3:raise RuntimeError('Need8GiB available host RAM')
    if status['disk_free']<2*1024**3:raise RuntimeError('Need2GiB free receipt workspace; preserve history')
    return status


def validate(s):
    if s.get('authorization_basis')!='CURRENT_USER_FINISH_EXISTING_METRIC_BACKFILL_20261030':
        raise PermissionError('Completion instruction required; never a training grant')
    for key in ('engine','registry'):
        if sha(s[key])!=s[key+'_sha256']:raise ValueError('Pinned backfill component changed: '+key)
    registry=read(s['registry']);runs={r['run_id']:r for r in registry['runs']}
    correction=s.get('correction_scope')=='B01_PRECISION_CORRECTION_4_20261030'
    if correction:
        correction_grant(s)
        if s['remaining']!=['B0_s2026_E0','B1_s2026_E0','B0_s2027_E0','B1_s2027_E0']:raise ValueError('Only the four unfinished B0/B1 passes')
    inherited_n,remaining_n=(15,4) if correction else (6,13)
    if len(runs)!=19 or len(s['inherited'])!=inherited_n or len(s['remaining'])!=remaining_n:
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
    m.OUTPUT_ROOT=str(out/'runs');m.LOG_ROOT=str(out/'logs');m.REGISTRY_PATH=s['registry']
    m.BATCH_SIZE=8  # The frozen historical Dev batches; ignore external env overrides.
    # Tighten the legacy inference-only BudgetStub's 32TiB default. Preserve
    # its original accounting and all readers/masks/precision/evaluation rules.
    old=m.FrozenBudgetStub;cap=s['caps'][rid]['source_bytes']
    budgets=[]
    class BoundedBudget(old):
        def __init__(self,*args,**kwargs):
            super().__init__(max_read_bytes=cap);self.content_reads=0;self.last_host_check=0;budgets.append(self)
        def check(self):
            status=super().check()
            if not s.get('correction_scope'):return status
            from yuntapr.training.phase_b_v2_seed2026_v2.resources import memory,system_memory
            status=memory()
            if status['working_set_bytes']>6*1024**3 or status['private_bytes']>12*1024**3:raise MemoryError('Original B0/B1 worker memory limits')
            if time.monotonic()-self.last_host_check>=2:
                host=system_memory()
                if host['available_phys']<6*1024**3 or host['available_page']<10*1024**3:raise MemoryError('Original B0/B1 available host limits')
                t=sys.modules.get('torch')
                if t is not None and t.cuda.is_initialized() and t.cuda.memory_reserved()>6*1024**3:raise MemoryError('Original B0/B1 GPU reservation limit')
                self.last_host_check=time.monotonic()
            return status
        def record(self,state,size):
            with (out/(rid+'_source_accounting.jsonl')).open('ab',buffering=0) as f:
                f.write((json.dumps(dict(at=now(),state=state,size=size,delivered_bytes=self.bytes,content_reads=self.content_reads))+'\n').encode())
        def admit_bytes(self,size):
            if self.content_reads>=s['caps'][rid].get('content_reads',2**63):raise MemoryError('Content-read-instance cap')
            result=super().admit_bytes(size);self.content_reads+=1;self.record('ADMITTED_BEFORE_READ',size);return result
        def account_bytes(self,size):
            super().account_bytes(size);self.record('DELIVERED',size)
    m.FrozenBudgetStub=BoundedBudget
    import torch
    install_historical_b01_context(m,torch)
    torch.set_num_threads(1);torch.set_grad_enabled(False)
    def forbidden(*args,**kwargs):raise PermissionError('Metric backfill cannot construct an optimizer')
    torch.optim.Optimizer.__init__=forbidden
    result=m.run_one(rid,verify_sha=True)
    if result['status']!='COMPLETE' or result['gate']['passed'] is not True:raise RuntimeError('Frozen metric gate failed')
    io=result['read_scope_actual'];actual=io.get('content_bytes_read',io.get('meter_totals',{}).get('delivered_bytes'))
    if actual is None or actual>cap:raise RuntimeError('Actual IO exceeds bounded completion scope')
    content_reads=sum(b.content_reads for b in budgets)
    if s.get('correction_scope') and (actual!=cap or content_reads!=s['caps'][rid]['content_reads']):raise RuntimeError('Exact corrected content-read accounting differs')
    write(out/(rid+'_verified.json'),dict(at=now(),result_sha256=sha(out/'runs'/rid/'result.json'),source_bytes=actual,
          source_cap_bytes=cap,content_read_instances=content_reads,read_events_are_log_events=True,optimizer_updates=0,gate_passed=True))


def execute(s,private):
    runs=validate(s);out=Path(s['new_output_root'])
    if out.exists():raise PermissionError('Consumed namespace; no automatic retry')
    if shutil.disk_usage(out.parent).free<2*1024**3:raise RuntimeError('Need2GiB for new inference receipts; preserve history')
    host=module(ROOT/'tools/research_readiness/start_independent_process.py','metric_host_controller')
    host.require_independent(host.host_identity())
    out.mkdir();write(out/'binding.json',dict(at=now(),private_sha256=sha(private),engine_sha256=s['engine_sha256'],
        inherited_complete=len(s['inherited']),new_tasks=len(s['remaining']),old_partial_io=s['old_partial_io'],training_authorized=False,
        automatic_retry=False,host=host.host_identity()))
    started=time.monotonic();child=None
    try:
        for rid in s['remaining']:
            remaining=s['maximum_seconds']-(time.monotonic()-started)
            if remaining<=0:raise RuntimeError('Serial completion time cap')
            write(out/(rid+'_resource_admission.json'),resource_admission(out))
            write(out/(rid+'_claim.json'),dict(at=now(),parent_pid=os.getpid(),automatic_retry=False))
            env=dict(os.environ,PYTHONPATH=str(Path(runs[rid]['code_root'])/'src')+os.pathsep+s['torch_site'],PYTHONHASHSEED='2026' if runs[rid]['family']=='b01' else str(runs[rid]['seed']),
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
             results=all_results,new_tasks=len(s['remaining']),inherited_tasks=len(s['inherited']),optimizer_updates=0,automatic_retry=False,final_2025='FROZEN_NO_ACCESS'))
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
