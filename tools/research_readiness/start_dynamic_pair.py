"""Prepare or run the explicitly approved B7 -> B8 package, never infer approval."""
import argparse,json,os,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'src'));sys.dont_write_bytecode=True

def main():
    p=argparse.ArgumentParser();sub=p.add_subparsers(dest='mode',required=True)
    q=sub.add_parser('prepare');q.add_argument('--static-private',type=Path,required=True);q.add_argument('--output-root',type=Path,required=True)
    for mode in ('execute','worker'):
        q=sub.add_parser(mode);q.add_argument('--researcher-approval',type=Path,required=True)
        if mode=='worker':q.add_argument('--task-index',type=int,required=True)
    for q in sub.choices.values():
        q.add_argument('--proposal',type=Path,required=True);q.add_argument('--private-preparation',type=Path,required=True)
    a=p.parse_args();os.chdir(ROOT)
    for key in ('proposal','private_preparation','researcher_approval','static_private'):
        if hasattr(a,key):setattr(a,key,getattr(a,key).resolve())
    from yuntapr.experimental.research_readiness.dynamic_training import prepare,execute,worker
    from yuntapr.experimental.core_innovation.stage4.engine import write
    if a.mode=='prepare':
        if not a.private_preparation.is_relative_to(ROOT/'docs/research_readiness/.local'):raise PermissionError('Private paths stay ignored')
        public,private=prepare(ROOT,a.static_private,a.output_root);write(a.proposal,public);write(a.private_preparation,private)
        print(json.dumps({k:public[k] for k in ('status','proposal_sha256','budget','authorized')}));return
    if subprocess.check_output(['git','-C',str(ROOT),'status','--porcelain'],text=True).strip():raise PermissionError('Exact reviewed execution copy must be clean')
    commit=subprocess.check_output(['git','-C',str(ROOT),'rev-parse','HEAD'],text=True).strip()
    if a.mode=='worker':worker(ROOT,a.proposal,a.private_preparation,a.researcher_approval,commit,a.task_index)
    else:execute(ROOT,a.proposal,a.private_preparation,a.researcher_approval,commit)
if __name__=='__main__':main()
