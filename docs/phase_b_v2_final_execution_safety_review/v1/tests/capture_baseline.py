"""Repository-only hashes and read-only sealed quota; never import training code."""
import hashlib
import json
from pathlib import Path
import sqlite3
import subprocess

ROOT = Path(__file__).absolute().parents[4]
OUT = ROOT / 'docs/phase_b_v2_final_execution_safety_review/v1'


def capture() -> dict:
    paths = subprocess.check_output(['git', 'ls-files', 'src', 'config', 'docs'], cwd=ROOT).decode().splitlines()
    records = {p: hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in paths}
    git_dir = Path(subprocess.check_output(['git', 'rev-parse', '--absolute-git-dir'], cwd=ROOT).decode().strip())
    names = ['yuntapr_real_train_smoke_20261010.once', 'yuntapr_real_train_smoke_20261010.sqlite']
    sealed = {n: hashlib.sha256((git_dir/n).read_bytes()).hexdigest() for n in names}
    witness = ROOT/'docs/phase_b_v2_real_train_smoke/v1/.local/real_train_smoke_20261010.once'
    sealed['secondary_witness'] = hashlib.sha256(witness.read_bytes()).hexdigest()
    with sqlite3.connect((git_dir/names[1]).as_uri()+'?mode=ro', uri=True) as con:
        # Normalize SQL tuples to JSON arrays before comparison with saved JSON.
        rows = {table: [list(row) for row in con.execute('SELECT * FROM '+table)] for table in ('task', 'models')}
    return dict(baseline_commit=subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT).decode().strip(),
                tracked_sha256=records, sealed_sha256=sealed, sealed_rows=rows)


if __name__ == '__main__':
    p = OUT/'protected_baseline.json'
    if p.exists():
        before = json.loads(p.read_text(encoding='utf-8')); after = capture()
        changed = [n for n, sha in before['tracked_sha256'].items() if after['tracked_sha256'].get(n) != sha]
        result = dict(changed_preexisting_tracked_paths=changed,
                      sealed_quota_unchanged=before['sealed_sha256']==after['sealed_sha256'],
                      sealed_rows_unchanged=before['sealed_rows']==after['sealed_rows'],
                      preexisting_tracked_count=len(before['tracked_sha256']))
        (OUT/'protected_validation.json').write_text(json.dumps(result, indent=2)+'\n', encoding='utf-8', newline='\n')
        print(json.dumps(result)); assert not changed and result['sealed_quota_unchanged'] and result['sealed_rows_unchanged']
    else:
        p.write_text(json.dumps(capture(), indent=2)+'\n', encoding='utf-8', newline='\n')
        print('Captured repository-only hashes and sealed read-only quota')
