"""All tracked regression modules plus new runner tests, with frozen fixture scope."""
from pathlib import Path
import argparse
import json
import os
import subprocess
import sys
import traceback
ROOT=Path(__file__).resolve().parents[2]
sys.path[:0]=[str(ROOT/'scripts'),str(ROOT/'src'),str(ROOT)]


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--run',required=True,type=Path)
    parser.add_argument('--suite',choices=['NEW_RUNNER','V2_NUMERICAL','V1_REGRESSION']);args=parser.parse_args()
    from yuntapr.training.phase_a_audit_v2 import atomic_json,identity
    from yuntapr.training.formal_phase_a_v2 import code_identity,progress
    run=args.run.resolve()
    if args.suite:
        import torch
        from quantile_head_v2 import governance,common as c
        from quantile_head_v2.test_gate import run_suite
        from yuntapr.training.phase_a_protocol import seed_reproducibility
        seed_reproducibility();torch.set_num_threads(2);governance.install()
        os.environ['YUNTAPR_PHASE_B_FORMAL_EVIDENCE']=str(ROOT/'docs/formal_training/b0_phase_b_finalfit/runs/run_20261002T035929_487644Z')
        os.environ['YUNTAPR_PHASE_B_PREPARATION_EVIDENCE']=str(ROOT/'docs/phase_b_finalfit_preparation/runs/run_20261002T014649_144967Z')
        c.progress=lambda _,phase,**values:progress(run.parent,status=values.pop('status','RUNNING'),phase=phase,**values)
        if args.suite=='NEW_RUNNER':
            paths=sorted((ROOT/'tests/formal_phase_a_v2').glob('test_*.py'));run_suite(run,args.suite,paths)
        elif args.suite=='V2_NUMERICAL':
            run_suite(run,args.suite,[ROOT/'tests/quantile_head_v2/test_v2.py'])
        else:
            files=subprocess.check_output(['git','ls-files','tests'],cwd=ROOT).decode().splitlines()
            paths=[ROOT/p for p in files if Path(p).name.startswith('test_') and p.endswith('.py') and '/quantile_head_v2/' not in p and '/formal_phase_a_v2/' not in p]
            from quantile_head_v2.regression_scope import historical_fixture_environment
            from paired_phase_a_v2.historical_scope import extended_artifact_scope
            with historical_fixture_environment(run),extended_artifact_scope(ROOT,run):
                run_suite(run,args.suite,paths)
        return
    run.mkdir(parents=True,exist_ok=False)
    code=code_identity();atomic_json(run/'executed_code_identity.json',code,immutable=True)
    summaries=[]
    try:
        for suite in ('NEW_RUNNER','V2_NUMERICAL','V1_REGRESSION'):
            dest=run/suite.lower();dest.mkdir()
            with (dest/'console.log').open('x',encoding='utf-8') as log:
                result=subprocess.run([sys.executable,'-B',str(Path(__file__).resolve()),'--run',str(dest),'--suite',suite],cwd=ROOT,stdout=log,stderr=subprocess.STDOUT)
            if result.returncode:raise RuntimeError(suite+' failed; original console preserved')
            summary=json.loads((dest/(suite.lower()+'_tests.json')).read_text(encoding='utf-8'))
            summaries.append({'suite':suite,'counts':summary['counts'],'evidence':identity(dest/(suite.lower()+'_tests.json'))})
        if code_identity()!=code:raise ValueError('Source changed while tests ran')
        atomic_json(run/'test_summary.json',{'status':'PASS','suites':summaries,'code_sha256':code,
            'total_tests':sum(x['counts']['run'] for x in summaries),'FORMAL_OPTIMIZER_STEPS':0,
            '2025_RAW_ACCESS':0,'TEST_FIXTURE_ONLY':True},immutable=True)
        progress(run,status='COMPLETE',phase='TESTS_COMPLETE',total_tests=sum(x['counts']['run'] for x in summaries),FORMAL_OPTIMIZER_STEPS=0)
    except BaseException as exc:
        atomic_json(run/'failure.json',{'status':'FAILED_STOP','error':repr(exc),'traceback':traceback.format_exc()},immutable=True)
        progress(run,status='FAILED_STOP',phase='TEST_GATE_FAILED',error=repr(exc));raise


if __name__=='__main__':main()
