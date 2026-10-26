"""B5/B6 preparation and a once-only explicitly approved two-model launcher."""
from pathlib import Path
import argparse,json,os,subprocess,sys
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'src'));sys.dont_write_bytecode=True
os.environ.update(CUBLAS_WORKSPACE_CONFIG=':4096:8',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1',PYTHONUTF8='1')

def main():
    p=argparse.ArgumentParser();sub=p.add_subparsers(dest='mode',required=True)
    q=sub.add_parser('prepare');q.add_argument('--inherited',type=Path,required=True);q.add_argument('--terrain',type=Path,required=True);q.add_argument('--terrain-receipt',type=Path,required=True);q.add_argument('--output-root',type=Path,required=True);q.add_argument('--prior-failed-root',type=Path)
    for mode in ('execute','worker'):
        q=sub.add_parser(mode);q.add_argument('--researcher-approval',type=Path,required=True)
        if mode=='worker':q.add_argument('--task-index',type=int,required=True)
    for q in sub.choices.values():
        q.add_argument('--proposal',type=Path,required=True);q.add_argument('--private-preparation',type=Path,required=True)
    a=p.parse_args();os.chdir(ROOT)
    for field in ('proposal','private_preparation','researcher_approval'):
        if hasattr(a,field):setattr(a,field,getattr(a,field).resolve())
    from yuntapr.experimental.research_readiness.static_training import prepare,execute,worker
    from yuntapr.experimental.core_innovation.stage4.engine import write
    if a.mode=='prepare':
        if not a.private_preparation.is_relative_to(ROOT/'docs/research_readiness/.local'):raise PermissionError('Private paths stay ignored')
        proposal,private=prepare(ROOT,a.inherited,a.terrain,a.terrain_receipt,a.output_root,prior_failed_root=a.prior_failed_root)
        write(a.proposal,proposal);write(a.private_preparation,private)
        print(json.dumps({k:proposal[k] for k in ('status','proposal_sha256','budget','authorized')}));return
    if subprocess.check_output(['git','-C',str(ROOT),'status','--porcelain','--untracked-files=no'],text=True).strip():raise PermissionError('Reviewed execution copy must be clean')
    commit=subprocess.check_output(['git','-C',str(ROOT),'rev-parse','HEAD'],text=True).strip()
    if a.mode=='worker':worker(ROOT,a.proposal,a.private_preparation,a.researcher_approval,commit,a.task_index)
    else:execute(ROOT,a.proposal,a.private_preparation,a.researcher_approval,commit)

if __name__=='__main__':main()
