"""Seed-completion preparation, dry-run and once-only approval-gated launcher.

No default execution. All paths are explicit; the controller revalidates the
proposal, private preparation, approval, reviewed code and every input pin
before any subprocess is started. Training is never run by this file here.
"""
from pathlib import Path
import argparse
import json
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'src'))
sys.dont_write_bytecode = True


def _commit():
    return subprocess.check_output(['git', '-C', str(ROOT), 'rev-parse', 'HEAD'], text=True).strip()


def _require_clean_copy():
    dirty = subprocess.check_output(['git', '-C', str(ROOT), 'status', '--porcelain',
                                     '--untracked-files=no'], text=True).strip()
    if dirty:
        raise PermissionError('Reviewed execution copy has tracked changes; refusing to run')


def _output_paths(parser):
    parser.add_argument('--proposal', type=Path, required=True)
    parser.add_argument('--private-preparation', type=Path, required=True)


def _paths(parser):
    _output_paths(parser)
    parser.add_argument('--researcher-approval', type=Path, required=True)


def main():
    parser = argparse.ArgumentParser(description='B2/B5/B6 seed completion for seeds 2030/2031')
    modes = parser.add_subparsers(dest='mode', required=True)
    modes.add_parser('plan', help='print the six tasks and the frozen budget; no file I/O')
    prepare = modes.add_parser('prepare', help='write proposal and private preparation')
    prepare.add_argument('--output-root', type=Path, required=True)
    prepare.add_argument('--inherited', type=Path, required=True)
    prepare.add_argument('--terrain', type=Path, required=True)
    prepare.add_argument('--public-terrain', type=Path, required=True)
    _output_paths(prepare)
    dry = modes.add_parser('dry-run', help='validate everything without model/data/checkpoint reads')
    _paths(dry)
    run = modes.add_parser('execute', help='once-only serial six-task controller')
    _paths(run)
    run.add_argument('--worker-python', type=Path)
    work = modes.add_parser('worker', help=argparse.SUPPRESS)
    _paths(work)
    work.add_argument('--task-index', type=int, required=True)
    args = parser.parse_args()
    for field in ('proposal', 'private_preparation', 'researcher_approval', 'output_root',
                  'inherited', 'terrain', 'public_terrain', 'worker_python'):
        value = getattr(args, field, None)
        if value is not None:
            setattr(args, field, value.resolve())

    from yuntapr.experimental.research_readiness import seed_completion as module
    if args.mode == 'plan':
        print(json.dumps({'scope': module.SCOPE, 'kind': module.KIND, 'entry': module.ENTRY,
                          'version': module.VERSION,
                          'tasks': [dict(index=index, model=kind, seed=seed)
                                    for index, (kind, seed) in enumerate(module.TASKS)],
                          'budget': module.BUDGET}, indent=2, ensure_ascii=False))
        return
    if args.mode == 'prepare':
        proposal, private = module.prepare(ROOT, output_root=args.output_root,
                                           inherited=args.inherited, terrain=args.terrain,
                                           public_terrain=args.public_terrain)
        from yuntapr.experimental.core_innovation.stage4.engine import write
        write(args.proposal, proposal)
        write(args.private_preparation, private)
        print(json.dumps({key: proposal[key] for key in ('status', 'proposal_sha256', 'budget')},
                         indent=2, ensure_ascii=False))
        return
    _require_clean_copy()
    commit = _commit()
    if args.mode == 'dry-run':
        module.dry_run(ROOT, args.proposal, args.private_preparation, args.researcher_approval, commit)
        return
    if args.mode == 'worker':
        module.worker(ROOT, args.proposal, args.private_preparation, args.researcher_approval,
                      commit, args.task_index)
        return
    result = module.execute(ROOT, args.proposal, args.private_preparation, args.researcher_approval,
                            commit, worker_python=args.worker_python)
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == '__main__':
    main()
