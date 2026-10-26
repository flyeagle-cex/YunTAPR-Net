"""prepare is metadata-only; execute needs a real four-model researcher approval."""
from pathlib import Path
import argparse
import json
import os
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.dont_write_bytecode = True
sys.path.insert(0, str(ROOT/'src'))
os.environ.update(CUBLAS_WORKSPACE_CONFIG=':4096:8', OMP_NUM_THREADS='1', MKL_NUM_THREADS='1')


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='mode', required=True)
    prep = sub.add_parser('prepare')
    prep.add_argument('--inherited-b2-preparation', type=Path, required=True)
    prep.add_argument('--output-root', type=Path, required=True)
    prep.add_argument('--proposal', type=Path, required=True)
    prep.add_argument('--private-preparation', type=Path, required=True)
    for name in ('execute', 'worker'):
        p = sub.add_parser(name)
        p.add_argument('--proposal', type=Path, required=True)
        p.add_argument('--private-preparation', type=Path, required=True)
        p.add_argument('--researcher-approval', type=Path, required=True)
        if name == 'worker':
            p.add_argument('--task-index', type=int, required=True)
    args = parser.parse_args(argv)
    os.chdir(ROOT)
    args.proposal = args.proposal.resolve()
    args.private_preparation = args.private_preparation.resolve()
    if args.mode == 'prepare':
        def audit(event, values):
            if event == 'open' and isinstance(values[0], (str, bytes, os.PathLike)):
                if os.fsdecode(values[0]).lower().endswith(('.nc', '.h5', '.hdf5', '.grib', '.grb2', '.pt', '.pth', '.ckpt')):
                    raise PermissionError('Preparation cannot open raw payloads or checkpoints')
        sys.addaudithook(audit)
    from yuntapr.experimental.research_readiness.multiseed import prepare, run_package, run_worker
    from yuntapr.experimental.core_innovation.stage4.engine import write
    if args.mode == 'prepare':
        if not args.private_preparation.is_relative_to(ROOT/'docs/research_readiness/.local'):
            parser.error('Private preparation must stay in ignored local scope')
        if args.proposal.exists() or args.private_preparation.exists():
            parser.error('No preparation/proposal overwrite')
        public, private = prepare(ROOT, args.inherited_b2_preparation, args.output_root)
        args.private_preparation.parent.mkdir(parents=True, exist_ok=True)
        args.proposal.parent.mkdir(parents=True, exist_ok=True)
        write(args.private_preparation, private); write(args.proposal, public)
        print(json.dumps({k: public[k] for k in ('status', 'proposal_sha256', 'budget', 'authorized')}))
        return
    commit = subprocess.check_output(['git', '-C', str(ROOT), 'rev-parse', 'HEAD'], text=True).strip()
    if subprocess.check_output(['git', '-C', str(ROOT), 'status', '--porcelain', '--untracked-files=no'], text=True).strip():
        parser.error('Tracked code differs from the reviewed commit')
    args.researcher_approval = args.researcher_approval.resolve()
    call = run_package if args.mode == 'execute' else run_worker
    kwargs = {} if args.mode == 'execute' else dict(index=args.task_index)
    result = call(ROOT, args.proposal, args.private_preparation, args.researcher_approval, commit, **kwargs)
    print(json.dumps(result))


if __name__ == '__main__':
    main()
