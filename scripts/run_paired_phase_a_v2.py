"""Explicit v2 engineering/formal CLI. No subcommand defaults to training."""
from pathlib import Path
import argparse
import os
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'src'),str(ROOT/'scripts'),str(ROOT)]


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    sub=parser.add_subparsers(dest='command',required=True)
    pre=sub.add_parser('preflight');pre.add_argument('--run',required=True,type=Path);pre.add_argument('--tests-summary',required=True,type=Path)
    proof=sub.add_parser('initialization-proof');proof.add_argument('--output',required=True,type=Path)
    for action in ('train','resume'):
        cmd=sub.add_parser(action);cmd.add_argument('--authorization',required=True,type=Path);cmd.add_argument('--authorization-sha256',required=True)
    mon=sub.add_parser('monitor');mon.add_argument('--run',required=True,type=Path);mon.add_argument('--port',type=int,default=8769)
    pub=sub.add_parser('publish');pub.add_argument('--repository',required=True,type=Path);pub.add_argument('--public',required=True,type=Path)
    args=parser.parse_args(argv)
    if args.command=='monitor':
        from paired_phase_a_v2.monitor import serve
        return serve(args.run,args.port)
    if args.command=='publish':
        from paired_phase_a_v2.publication import publish
        print(publish(args.repository,args.public));return
    from yuntapr.training import formal_phase_a_v2 as f
    if args.command=='initialization-proof':
        import torch
        torch.set_num_threads(2)
        contract=f.Contract.load();models,proof=f.paired_initialization(contract)
        f.atomic_json(args.output,proof,immutable=True);return
    if args.command=='preflight':
        from paired_phase_a_v2.preflight import execute
        return execute(args.run,args.tests_summary)
    # No raw/model/checkpoint construction before explicit authorization passes.
    contract=f.Contract.load()
    auth,gate=f.authorize(args.authorization,args.authorization_sha256,contract,resume=args.command=='resume')
    public=Path(auth['publication_root']).resolve()
    execution=ROOT.resolve()
    if public.is_relative_to(execution):
        raise PermissionError('Publication must use a separate checkout; execution stays immutable')
    if not public.is_relative_to(Path(auth['publication_repository']).resolve()/'docs'):
        raise PermissionError('Publication root must be in approved repository docs')
    public.mkdir(parents=True,exist_ok=args.command=='resume')
    lock=Path(r'F:\pytorch\Research\outputs\formal_training\paired_v2_gpu.lock')
    # Exclusive immutable lock. Crashed/stale locks are not automatically deleted.
    handle=lock.open('x',encoding='utf-8');handle.write(str(os.getpid()));handle.flush();os.fsync(handle.fileno())
    stop_file=public/('publication_stop_'+f.run_id()+'.json')
    try:
        import subprocess
        publisher = subprocess.Popen([sys.executable,'-B',str(ROOT/'scripts/paired_phase_a_v2/publisher_worker.py'),
            '--repository',auth['publication_repository'],'--public',str(public),
            '--stop-file',str(stop_file)],creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
        if args.command=='resume':
            kind=auth['resume_model']
            if kind not in f.KINDS: raise ValueError('Invalid resume model')
            if kind=='B1_V2' and f.read_json(public/'B0_MATCHED_V2/final_report.json')['status']!='COMPLETE':
                raise PermissionError('B0 must finish before B1')
            f.train_one(kind,contract,auth,gate,public,resume=True)
            kinds=['B1_V2'] if kind=='B0_MATCHED_V2' else []
        else: kinds=list(f.KINDS)
        for kind in kinds:
            f.train_one(kind,contract,auth,gate,public)
        f.atomic_json(public/'pair_training_completed.json',{'status':'TRAINING_COMPLETE_PUBLICATION_PENDING','V2_PHASE_B_AUTHORIZED':False,
                      '2025_RAW_ACCESS':0,'2025_PIXELS_READ':0},immutable=True)
    finally:
        f.atomic_json(stop_file,{'stop':True},immutable=True)
        handle.close();lock.unlink()  # exact lock created by this process only


if __name__=='__main__': main()
