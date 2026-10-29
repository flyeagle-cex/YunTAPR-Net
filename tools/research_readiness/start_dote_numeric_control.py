"""Execute one proposed B7 zero-numeric control only after an exact new approval."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'src'))
sys.dont_write_bytecode = True


def load(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def digest(obj):
    return hashlib.sha256(json.dumps(obj, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()).hexdigest()


def validate(approval, proposal, private, commit):
    expected = dict(code_commit=commit, proposal_sha256=proposal['proposal_sha256'], tasks=proposal['tasks'],
                    scientific_choices=proposal['scientific_choices'], budget=proposal['budget'], output_root=private['output_root'])
    if approval.get('approved_by_researcher') is not True or not approval.get('decision_id'):
        raise PermissionError('New researcher approval required; old B7/B8 grants are consumed')
    if proposal['execution_code_commit'] != commit or any(approval.get(k) != v for k,v in expected.items()):
        raise PermissionError('Exact candidate, code, budget and output must be approved once')
    if digest({k:v for k,v in proposal.items() if k != 'proposal_sha256'}) != proposal['proposal_sha256']:
        raise ValueError('Proposal content changed')
    if proposal['tasks'] != [dict(model='B7_ZERO_DOTE', seed=2029)]:
        raise PermissionError('Only the single minimum main control, not optional seeds or permutation')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode',choices=('execute','worker'))
    parser.add_argument('--proposal',type=Path,required=True)
    parser.add_argument('--private-preparation',type=Path,required=True)
    parser.add_argument('--researcher-approval',type=Path,required=True)
    args=parser.parse_args()
    proposal,private,approval=map(load,(args.proposal,args.private_preparation,args.researcher_approval))
    commit=subprocess.check_output(['git','-C',str(ROOT),'rev-parse','HEAD'],text=True).strip()
    validate(approval,proposal,private,commit)  # Before torch, GPU, source or output.
    started=time.monotonic()
    if subprocess.check_output(['git','-C',str(ROOT),'status','--porcelain'],text=True).strip():
        raise PermissionError('Clean approved execution checkout required')
    for name,sha in proposal['code_sha256'].items():
        if hashlib.sha256((ROOT/name).read_bytes()).hexdigest()!=sha:raise ValueError('Code changed: '+name)
    from yuntapr.experimental.research_readiness.multiseed import load_inherited
    from yuntapr.experimental.research_readiness.dynamic_training import run_task
    from yuntapr.experimental.research_readiness.dote_numeric_control import ZeroNumericDote
    from yuntapr.experimental.research_readiness.dynamic_multiseed import admit_source
    from yuntapr.experimental.core_innovation.stage4.engine import resources,write
    import shutil
    import importlib.util
    hostfile=ROOT/'tools/research_readiness/start_independent_process.py'
    spec=importlib.util.spec_from_file_location('independent_control_host',hostfile)
    host=importlib.util.module_from_spec(spec);spec.loader.exec_module(host)
    host.require_independent(host.host_identity())
    parent=load(private['inherited_private']);_,prepared=load_inherited(parent['inherited'])
    if prepared['data']!=proposal['data']:raise ValueError('Population changed')
    out=Path(private['output_root'])
    if args.mode=='worker':
        binding=load(out/'authorization_binding.json')
        if binding['controller_pid']!=os.getppid() or binding['approval']!=approval:
            raise PermissionError('Live once-only parent required')
        result=run_task(ROOT,proposal,dict(parent,output_root=str(out)),approval,prepared,commit,'B7',2029,
                        started=binding['started_monotonic'],pair_reference=Path(parent['historical_B7']),static_name='B7_ZERO_DOTE_static_source.sqlite',
                        dynamic_transform_factory=ZeroNumericDote)
        write(out/'control_task_complete.json',dict(result,control_id='B7_ZERO_DOTE'))
        return
    if out.exists():raise PermissionError('Output consumed; no retries/replay or overwrite')
    if shutil.disk_usage(out.parent).free<proposal['budget']['initial_free_bytes']:raise RuntimeError('Need24GiB; do not delete history')
    if os.environ.get('PYTHONHASHSEED')!='2029':raise RuntimeError('Frozen seed environment required')
    for name,sha in proposal['baseline_metadata_sha256'].items():
        if hashlib.sha256((Path(parent['historical_B7'])/name).read_bytes()).hexdigest()!=sha:raise ValueError('Existing B7 identity changed')
    # Reader budget is recomputed from the unchanged manifest, not guessed.
    weather=9*sum(x['bytes_per_pass'] for x in prepared['roles'].values())
    files=9*sum(x['file_count'] for x in prepared['roles'].values())
    if (weather+312828,files+1)!=(proposal['budget']['total_source_bytes'],proposal['budget']['total_source_files']):raise ValueError('Source budget changed')
    admission=resources();out.mkdir(exist_ok=False)
    write(out/'authorization_binding.json',dict(approval=approval,admission=admission,control='ZERO_NUMERIC_RETAIN_REAL_MASKS',code_commit=commit,
                                               controller_pid=os.getpid(),started_monotonic=started))
    child=None
    try:
        admit_source(prepared,out)  # One bounded metadata admission, zero payload.
        remaining=21600-(time.monotonic()-started)
        if remaining<=0:raise RuntimeError('Admission exhausted six-hour budget')
        command=[sys.executable,'-B',str(Path(__file__).resolve()),'worker','--proposal',str(args.proposal.resolve()),
                 '--private-preparation',str(args.private_preparation.resolve()),'--researcher-approval',str(args.researcher_approval.resolve())]
        from yuntapr.experimental.research_readiness.multiseed import worker_creation_flags
        with (out/'control_console.log').open('xb') as log:
            child=subprocess.Popen(command,cwd=ROOT,env=dict(os.environ),stdout=log,stderr=subprocess.STDOUT,creationflags=worker_creation_flags())
            try:rc=child.wait(timeout=remaining)
            except subprocess.TimeoutExpired:
                child.kill();child.wait();raise RuntimeError('Hard six-hour cap; no retry')
        if rc:raise RuntimeError('Control worker failed; no retry')
        result=load(out/'control_task_complete.json')
        if result['optimizer_updates']!=4320 or result['total_logical_source_bytes']!=proposal['budget']['total_source_bytes']:
            raise RuntimeError('Control closure differs')
        if time.monotonic()-started>21600:raise RuntimeError('Six-hour cap; no retry')
        write(out/'completion.json',dict(result,control_id='B7_ZERO_DOTE',proposal_sha256=proposal['proposal_sha256']))
    except BaseException as exc:
        if child is not None and child.poll() is None:child.kill();child.wait()
        write(out/'failure.json',dict(status='STOP_NO_RETRY_OR_REPLAY',error=type(exc).__name__+': '+str(exc),partial_counts='SEE_PRESERVED_LEDGERS_NOT_ZERO'))
        raise


if __name__=='__main__':main()
