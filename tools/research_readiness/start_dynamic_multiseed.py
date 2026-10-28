"""Prepare or execute the exact four-task grant; seed2029 is never dispatched."""
import argparse,json,os,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'src'));sys.dont_write_bytecode=True

def main():
    p=argparse.ArgumentParser();sub=p.add_subparsers(dest='mode',required=True)
    q=sub.add_parser('prepare');q.add_argument('--original-private',type=Path,required=True);q.add_argument('--seed-references',type=Path,required=True);q.add_argument('--output-root',type=Path,required=True)
    for mode in ('execute','worker'):
        q=sub.add_parser(mode);q.add_argument('--researcher-approval',type=Path,required=True)
        if mode=='worker':q.add_argument('--task-index',type=int,required=True)
    for q in sub.choices.values():q.add_argument('--proposal',type=Path,required=True);q.add_argument('--private-preparation',type=Path,required=True)
    a=p.parse_args();os.chdir(ROOT)
    from yuntapr.experimental.research_readiness import dynamic_multiseed as r
    if a.mode=='prepare':
        if not a.private_preparation.resolve().is_relative_to(ROOT/'docs/research_readiness/.local'):raise PermissionError('Keep private paths ignored')
        public,private=r.prepare(ROOT,a.original_private,a.seed_references,a.output_root);r.write(a.proposal,public);r.write(a.private_preparation,private)
        print(json.dumps({k:public[k] for k in ('status','execution_code_commit','proposal_sha256','budget','authorized')},ensure_ascii=False));return
    if subprocess.check_output(['git','-C',str(ROOT),'status','--porcelain'],text=True).strip():raise PermissionError('Clean approved execution checkout required')
    commit=subprocess.check_output(['git','-C',str(ROOT),'rev-parse','HEAD'],text=True).strip()
    if a.mode=='worker':r.worker(ROOT,a.proposal.resolve(),a.private_preparation.resolve(),a.researcher_approval.resolve(),commit,a.task_index)
    else:r.execute(ROOT,a.proposal.resolve(),a.private_preparation.resolve(),a.researcher_approval.resolve(),commit)
if __name__=='__main__':main()
