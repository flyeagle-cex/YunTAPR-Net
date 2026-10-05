"""Final allowlist and immutable evidence checks; no model or raw-data execution."""
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from quantile_autopsy_v1 import common as c
import argparse
import json
import subprocess

REQUIRED=('QUANTILE_OVERFLOW_NUMERICAL_AUTOPSY_v1.md','QUANTILE_OVERFLOW_NUMERICAL_AUTOPSY_v1.json',
    'pre_failure_training_dynamics.csv','pre_failure_training_dynamics_report.md',
    'per_tau_growth_diagnostics.csv','failing_batch_identity.json','failing_tensor_diagnostics.json',
    'replay_reconciliation.json','solution_options.json','quantile_execution_dependency_graph.json')

def main():
    p=argparse.ArgumentParser();p.add_argument('--run',required=True,type=Path);args=p.parse_args();run=args.run.resolve()
    for name in REQUIRED:
        if not (run/name).is_file() or (run/name).stat().st_size==0:raise ValueError('Required output missing: '+name)
    report=c.read(run/'QUANTILE_OVERFLOW_NUMERICAL_AUTOPSY_v1.json')
    expected={'B0_MATCHED_PHASE_B_COMPLETED':False,'B1_PHASE_B_STARTED':False,'FORMAL_OPTIMIZER_STEPS':50537,
        'FORMAL_OPTIMIZER_STEPS_ADDED':0,'2025_RAW_ACCESS':0,'2025_PIXELS_READ':0,
        'FORMAL_RESUME_AUTHORIZED':False,'RESEARCHER_DECISION_REQUIRED':True,
        'NUMERICAL_REPRODUCTION_VERIFIED':True,'ORIGINAL_REPLAY_CLOSEOUT_PASS':False,'READ_ONLY_EVIDENCE_CLOSURE_PASS':True}
    if any(report['status'].get(k)!=v for k,v in expected.items()):raise ValueError('Final scientific status mismatch')
    immutable=c.verify_snapshot(run)
    closure=c.read(run/'readonly_closeout/readonly_reconciliation.json')
    c.verify(closure['original_terminal_error_preserved']);c.verify(closure['original_terminal_progress_preserved'])
    for ref in c.read(run/'readonly_closeout/original_replay_evidence_manifest.json')['files']:c.verify(ref)
    if (c.read(run/'observer_test_result.json')['status']!='PASS' or
        c.read(run/'readonly_closeout/readonly_test_result.json')['status']!='PASS'):
        raise ValueError('Actual test gates must pass')
    subprocess.run(['git','diff','--exit-code',c.BASELINE,'--','src','config'],cwd=c.ROOT,check=True)
    roots=[c.ROOT/'scripts/quantile_autopsy_v1',c.ROOT/'tests/quantile_overflow_autopsy',
           c.ROOT/'tests/quantile_autopsy_closeout',run]
    files=[];forbidden={'.pt','.pth','.ckpt','.safetensors','.nc','.h5','.hdf5','.npy','.npz'}
    dest=run/'publication_manifest.json'
    for root in roots:
        for path in sorted(root.rglob('*')):
            if not path.is_file() or '__pycache__' in path.parts or path.suffix=='.pyc' or path==dest:continue
            if path.is_symlink() or path.suffix.lower() in forbidden or path.stat().st_size>=100*1024*1024:
                raise ValueError('Forbidden/oversize publication artifact: '+str(path))
            files.append({'relative_path':path.relative_to(c.ROOT).as_posix(),**c.pin(path)})
    manifest={'utc':c.now(),'baseline':c.BASELINE,'scope':'NUMERICAL_AUTOPSY_ONLY',
        'publish_repository':'https://github.com/flyeagle-cex/YunTAPR-Net.git','publish_branch':'main',
        'required_outputs_all_present':True,'status':expected,'immutable_history':immutable,
        'original_replay_closeout_error_preserved':True,'numeric_fixes_implemented':False,
        'independent_readonly_evidence_postprocessor_added':True,'phase_b_or_B1_resume_authorized':False,
        'binary_payloads_excluded':True,'new_raw_source_reads_during_postprocessing':0,
        'postprocessing_forward_backward_optimizer_calls':0,
        'test_counts':{'observer_preflight':c.read(run/'observer_test_result.json')['counts'],
                       'readonly_closure':c.read(run/'readonly_closeout/readonly_test_result.json')['counts']},
        'engineering_counter_scope':'Actual disposable real epoch-5 replay only; independent synthetic preflight fixtures are excluded.',
        'new_file_count':len(files),'total_bytes':sum(f['bytes'] for f in files),'files':files,
        'manifest_self_hash_excluded':True}
    c.write(dest,manifest)
    print(json.dumps({k:manifest[k] for k in ('new_file_count','total_bytes','required_outputs_all_present')}))

if __name__=='__main__':main()
