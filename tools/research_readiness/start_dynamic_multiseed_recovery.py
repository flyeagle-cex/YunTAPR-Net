"""Prepare exact E6/441-replay recovery, or dispatch only after a new approval."""
import argparse,json,os,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'src'));sys.dont_write_bytecode=True

def main():
    parser=argparse.ArgumentParser();sub=parser.add_subparsers(dest='mode',required=True)
    q=sub.add_parser('prepare');q.add_argument('--original-private',type=Path,required=True);q.add_argument('--output-root',type=Path,required=True)
    for mode in ('execute','worker'):
        q=sub.add_parser(mode);q.add_argument('--researcher-approval',type=Path,required=True)
        if mode=='worker':q.add_argument('--task-index',type=int,required=True)
    for q in sub.choices.values():q.add_argument('--proposal',type=Path,required=True);q.add_argument('--private-preparation',type=Path,required=True)
    args=parser.parse_args();os.chdir(ROOT)
    from yuntapr.experimental.research_readiness import dynamic_multiseed_recovery as r
    if args.mode=='prepare':
        if not args.private_preparation.resolve().is_relative_to(ROOT/'docs/research_readiness/.local'):raise PermissionError('Keep private paths ignored')
        proposal,private=r.prepare(ROOT,args.original_private,args.output_root);r.write(args.proposal,proposal);r.write(args.private_preparation,private)
        print(json.dumps({k:proposal[k] for k in ('status','execution_code_commit','proposal_sha256','budget','authorized')},ensure_ascii=False));return
    if subprocess.check_output(['git','-C',str(ROOT),'status','--porcelain'],text=True).strip():raise PermissionError('Clean approved checkout required')
    commit=subprocess.check_output(['git','-C',str(ROOT),'rev-parse','HEAD'],text=True).strip()
    if args.mode=='worker':r.worker(ROOT,args.proposal.resolve(),args.private_preparation.resolve(),args.researcher_approval.resolve(),commit,args.task_index)
    else:r.execute(ROOT,args.proposal.resolve(),args.private_preparation.resolve(),args.researcher_approval.resolve(),commit)
if __name__=='__main__':main()
