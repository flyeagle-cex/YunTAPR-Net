"""Prepare or run the researcher-directed single B8 E2 E9 recovery."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'src'))
sys.dont_write_bytecode = True


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    subcommands = parser.add_subparsers(dest='mode',required=True)
    prepare = subcommands.add_parser('prepare')
    prepare.add_argument('--original-proposal',type=Path,required=True)
    prepare.add_argument('--original-private',type=Path,required=True)
    prepare.add_argument('--output-root',type=Path,required=True)
    for mode in ('execute','worker'):
        command = subcommands.add_parser(mode)
        command.add_argument('--researcher-approval',type=Path,required=True)
    for command in subcommands.choices.values():
        command.add_argument('--proposal',type=Path,required=True)
        command.add_argument('--private-preparation',type=Path,required=True)
    args = parser.parse_args()
    os.chdir(ROOT)
    from yuntapr.experimental.research_readiness import dynamic_loss_recovery as recovery
    if args.mode == 'prepare':
        if not args.private_preparation.resolve().is_relative_to(ROOT/'docs/research_readiness/.local'):
            raise PermissionError('Private bindings must stay in ignored storage')
        proposal, private = recovery.prepare(ROOT,args.original_proposal,args.original_private,args.output_root)
        recovery.write(args.proposal,proposal)
        recovery.write(args.private_preparation,private)
        print(json.dumps({key:proposal[key] for key in ('status','proposal_sha256','budget')},ensure_ascii=False))
        return
    if subprocess.check_output(['git','-C',str(ROOT),'status','--porcelain'],text=True).strip():
        raise PermissionError('Clean reviewed execution snapshot required')
    commit = subprocess.check_output(['git','-C',str(ROOT),'rev-parse','HEAD'],text=True).strip()
    getattr(recovery,args.mode)(ROOT,args.proposal.resolve(),args.private_preparation.resolve(),args.researcher_approval.resolve(),commit)


if __name__ == '__main__':
    main()
