"""Prepare, or execute once only with a separate explicit researcher approval."""
import argparse,json,os,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'src'));sys.dont_write_bytecode=True

def main():
 p=argparse.ArgumentParser();sub=p.add_subparsers(dest='mode',required=True)
 q=sub.add_parser('prepare');q.add_argument('--original-private',type=Path,required=True);q.add_argument('--output-root',type=Path,required=True)
 for mode in ('execute','worker'):
  q=sub.add_parser(mode);q.add_argument('--researcher-approval',type=Path,required=True)
 for q in sub.choices.values():q.add_argument('--proposal',type=Path,required=True);q.add_argument('--private-preparation',type=Path,required=True)
 a=p.parse_args();os.chdir(ROOT)
 from yuntapr.experimental.research_readiness import dynamic_recovery as r
 if a.mode=='prepare':
  if not a.private_preparation.resolve().is_relative_to(ROOT/'docs/research_readiness/.local'):raise PermissionError('Private paths must stay ignored')
  public,private=r.prepare(ROOT,a.original_private,a.output_root);r.write(a.proposal,public);r.write(a.private_preparation,private)
  print(json.dumps({k:public[k] for k in ('status','proposal_sha256','budget','authorized')},ensure_ascii=False));return
 if subprocess.check_output(['git','-C',str(ROOT),'status','--porcelain'],text=True).strip():raise PermissionError('Clean reviewed execution checkout required')
 commit=subprocess.check_output(['git','-C',str(ROOT),'rev-parse','HEAD'],text=True).strip()
 getattr(r,a.mode)(ROOT,a.proposal.resolve(),a.private_preparation.resolve(),a.researcher_approval.resolve(),commit)
if __name__=='__main__':main()
