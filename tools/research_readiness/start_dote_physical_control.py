"""One bounded B7_PERP_GRADIENT seed2029 run, after metric completion.

Reuse the successful Stage4 dynamic run_task, optimizer, schedule, evaluator,
accounting and once-only host. Only the PhysicalDote gradient argument rotates.
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

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'src'));sys.dont_write_bytecode=True
CONTROL='B7_PERP_GRADIENT'


def load(path):return json.loads(Path(path).read_text(encoding='utf-8'))
def digest(x):return hashlib.sha256(json.dumps(x,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()


def validate(approval,proposal,private,commit):
    expected=dict(code_commit=commit,proposal_sha256=proposal['proposal_sha256'],tasks=proposal['tasks'],
                  scientific_choices=proposal['scientific_choices'],budget=proposal['budget'],output_root=private['output_root'])
    if approval.get('approved_by_researcher') is not True or not approval.get('decision_id'):raise PermissionError('Exact new researcher grant required')
    if proposal['execution_code_commit']!=commit or any(approval.get(k)!=v for k,v in expected.items()):raise PermissionError('Exact code/science/budget/output approval required')
    if digest({k:v for k,v in proposal.items() if k!='proposal_sha256'})!=proposal['proposal_sha256']:raise ValueError('Proposal changed')
    if proposal['tasks']!=[dict(model=CONTROL,seed=2029)]:raise PermissionError('Only one new direction-projection candidate')
    if proposal['scientific_choices']['negative_control']['rotation_matrix_east_north']!=[[0,-1],[1,0]]:raise ValueError('Frozen90CCW definition required')
    if proposal['budget']['total_source_bytes']!=477571953840 or proposal['budget']['total_updates']!=4320:raise ValueError('Frozen single-run cap')
    if (proposal['budget']['total_source_files'],proposal['budget']['max_package_seconds'],proposal['budget']['replay_allowance'],proposal['budget']['additional_retry_allowance'])!=(142813,21600,0,0):raise ValueError('No expanded time/read/replay budget')


def dependency(private,proposal):
    d=load(private['metric_completion']);reg=load(private['metric_registry'])
    if hashlib.sha256(Path(private['metric_registry']).read_bytes()).hexdigest()!=proposal['metric_dependency']['registry_sha256']:raise ValueError('Metric matrix changed')
    if d['status']!='COMPLETE_19_E9_DEV_METRIC_BACKFILL' or d['registry_sha256']!=proposal['metric_dependency']['registry_sha256'] or len(d['results'])!=19:raise PermissionError('All19 metric runs must finish first')
    for r in reg['runs']:
        info=d['results'][r['run_id']];path=Path(info['path'])
        if hashlib.sha256(path.read_bytes()).hexdigest()!=info['sha256']:raise ValueError('Metric receipt changed')
        result=load(path)
        if result['status']!='COMPLETE' or result['gate']['passed'] is not True or result['checkpoint_identity']['expected_sha256']!=r['checkpoint_sha256']:raise ValueError('Incomplete metric dependency')


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('mode',choices=('execute','worker'));p.add_argument('--proposal',type=Path,required=True);p.add_argument('--private-preparation',type=Path,required=True);p.add_argument('--researcher-approval',type=Path,required=True);a=p.parse_args()
    proposal,private,approval=map(load,(a.proposal,a.private_preparation,a.researcher_approval))
    commit=subprocess.check_output(['git','-C',str(ROOT),'rev-parse','HEAD'],text=True).strip();validate(approval,proposal,private,commit);started=time.monotonic()
    if subprocess.check_output(['git','-C',str(ROOT),'status','--porcelain'],text=True).strip():raise PermissionError('Clean approved checkout required')
    for name,sha in proposal['code_sha256'].items():
        if hashlib.sha256((ROOT/name).read_bytes()).hexdigest()!=sha:raise ValueError('Code changed: '+name)
    dependency(private,proposal)  # Before torch, GPU, source reads or new output.
    from yuntapr.experimental.research_readiness.multiseed import load_inherited,worker_creation_flags
    from yuntapr.experimental.research_readiness.dynamic_training import run_task
    from yuntapr.experimental.research_readiness.dote_physical_controls import PerpendicularGradientDote
    from yuntapr.experimental.research_readiness.dynamic_multiseed import admit_source
    from yuntapr.experimental.core_innovation.stage4.engine import resources,write
    spec=importlib.util.spec_from_file_location('physical_host',ROOT/'tools/research_readiness/start_independent_process.py');host=importlib.util.module_from_spec(spec);spec.loader.exec_module(host);host.require_independent(host.host_identity())
    parent=load(private['inherited_private']);_,prepared=load_inherited(parent['inherited'])
    if prepared['data']!=proposal['data']:raise ValueError('Population changed')
    out=Path(private['output_root'])
    if a.mode=='worker':
        binding=load(out/'authorization_binding.json')
        if binding['controller_pid']!=os.getppid() or binding['approval']!=approval:raise PermissionError('Live once-only parent required')
        result=run_task(ROOT,proposal,dict(parent,output_root=str(out)),approval,prepared,commit,'B7',2029,
                        started=binding['started_monotonic'],pair_reference=Path(parent['historical_B7']),
                        static_name=CONTROL+'_static_source.sqlite',dynamic_transform_factory=PerpendicularGradientDote)
        write(out/'control_task_complete.json',dict(result,control_id=CONTROL));return
    if out.exists():raise PermissionError('Consumed output; no retries or overwrite')
    if shutil.disk_usage(out.parent).free<24*1024**3:raise RuntimeError('Need24GiB; preserve all history')
    if os.environ.get('PYTHONHASHSEED')!='2029':raise RuntimeError('Frozen seed environment required')
    for name,sha in proposal['baseline_metadata_sha256'].items():
        if hashlib.sha256((Path(parent['historical_B7'])/name).read_bytes()).hexdigest()!=sha:raise ValueError('B7 reference changed')
    weather=9*sum(x['bytes_per_pass'] for x in prepared['roles'].values());files=9*sum(x['file_count'] for x in prepared['roles'].values())
    if (weather+312828,files+1)!=(proposal['budget']['total_source_bytes'],proposal['budget']['total_source_files']):raise ValueError('Actual source budget changed')
    admission=resources();out.mkdir(exist_ok=False)
    write(out/'authorization_binding.json',dict(approval=approval,admission=admission,control='PERPENDICULAR_GRADIENT_REAL_MASKS',code_commit=commit,controller_pid=os.getpid(),started_monotonic=started))
    child=None
    try:
        admit_source(prepared,out)
        remaining=21600-(time.monotonic()-started)
        if remaining<=0:raise RuntimeError('Admission consumed time cap')
        command=[sys.executable,'-B',str(Path(__file__).resolve()),'worker','--proposal',str(a.proposal.resolve()),'--private-preparation',str(a.private_preparation.resolve()),'--researcher-approval',str(a.researcher_approval.resolve())]
        with (out/'control_console.log').open('xb') as log:
            child=subprocess.Popen(command,cwd=ROOT,env=dict(os.environ),stdout=log,stderr=subprocess.STDOUT,creationflags=worker_creation_flags())
            try:rc=child.wait(timeout=remaining)
            except subprocess.TimeoutExpired:child.kill();child.wait();raise RuntimeError('Six-hour cap; no retry')
        if rc:raise RuntimeError('Worker failed; stop without retry')
        result=load(out/'control_task_complete.json')
        if result['optimizer_updates']!=4320 or result['total_logical_source_bytes']!=477571953840 or result['total_logical_source_files']!=142813:raise RuntimeError('Exact closure differs')
        if time.monotonic()-started>21600:raise RuntimeError('Six-hour cap')
        write(out/'completion.json',dict(result,control_id=CONTROL,proposal_sha256=proposal['proposal_sha256']))
    except BaseException as exc:
        if child is not None and child.poll() is None:child.kill();child.wait()
        write(out/'failure.json',dict(status='STOP_NO_RETRY_OR_REPLAY',error=type(exc).__name__+': '+str(exc),partial_counts='SEE_PRESERVED_LEDGERS_NOT_ZERO'));raise


if __name__=='__main__':main()
