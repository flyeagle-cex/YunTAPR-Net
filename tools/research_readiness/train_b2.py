"""Future guarded B2 execution. No default execution and no approval supplied."""
from pathlib import Path
import argparse
import json
import os
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.dont_write_bytecode = True
sys.path.insert(0, str(ROOT/'src'))


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--execute', action='store_true')
    p.add_argument('--proposal', required=True, type=Path)
    p.add_argument('--private-preparation', required=True, type=Path)
    p.add_argument('--researcher-approval', required=True, type=Path)
    p.add_argument('--output', required=True, type=Path)
    a = p.parse_args()
    if not a.execute:
        p.error('Training is NOT_STARTED. Explicit --execute plus reviewed approval is required')
    if os.environ.get('PYTHONHASHSEED') != '2029':
        p.error('PYTHONHASHSEED=2029 required before process startup')
    os.environ.update(CUBLAS_WORKSPACE_CONFIG=':4096:8', OMP_NUM_THREADS='1', MKL_NUM_THREADS='1')
    from yuntapr.experimental.research_readiness.b2_runner import execute
    commit = subprocess.check_output(['git', '-C', str(ROOT), 'rev-parse', 'HEAD'], text=True).strip()
    dirty = subprocess.check_output(['git', '-C', str(ROOT), 'status', '--porcelain', '--untracked-files=no'], text=True).strip()
    if dirty:
        p.error('Tracked changes differ from the reviewed code commit')
    print(json.dumps(execute(a.proposal, a.private_preparation, a.researcher_approval, a.output, root=ROOT, current_commit=commit)))


if __name__ == '__main__':
    main()
