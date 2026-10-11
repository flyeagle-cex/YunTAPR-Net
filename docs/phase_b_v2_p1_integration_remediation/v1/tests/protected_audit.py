"""Repository-only source/evidence SHA and sealed quota; all quota reads mode=ro."""
import hashlib
import json
from pathlib import Path
import sqlite3
import subprocess

ROOT=Path(__file__).absolute().parents[4]
OUT=ROOT/'docs/phase_b_v2_p1_integration_remediation/v1'


def capture():
    paths=subprocess.check_output(['git','ls-files','src','config','docs'],cwd=ROOT).decode().splitlines()
    tracked={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in paths}
    git_dir=Path(subprocess.check_output(['git','rev-parse','--absolute-git-dir'],cwd=ROOT).decode().strip())
    files=[git_dir/'yuntapr_real_train_smoke_20261010.once',git_dir/'yuntapr_real_train_smoke_20261010.sqlite',
           ROOT/'docs/phase_b_v2_real_train_smoke/v1/.local/real_train_smoke_20261010.once']
    anchors={str(i):hashlib.sha256(p.read_bytes()).hexdigest() for i,p in enumerate(files)}
    with sqlite3.connect(files[1].as_uri()+'?mode=ro',uri=True) as con:
        rows={t:[list(r) for r in con.execute('SELECT * FROM '+t)] for t in ('task','models')}
    return dict(tracked=tracked,anchors=anchors,rows=rows,
                baseline_commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT).decode().strip())


if __name__=='__main__':
    file=OUT/'.local/protected_baseline.json'
    if not file.exists():
        file.write_text(json.dumps(capture(),indent=2)+'\n',encoding='utf-8',newline='\n')
        print('Captured protected repository evidence and sealed read-only quota')
    else:
        before=json.loads(file.read_text()); after=capture()
        result=dict(preexisting_tracked_count=len(before['tracked']),
                    changed_paths=[p for p,sha in before['tracked'].items() if after['tracked'].get(p)!=sha],
                    sealed_anchors_unchanged=before['anchors']==after['anchors'],sealed_rows_unchanged=before['rows']==after['rows'],
                    baseline_snapshot_sha256=hashlib.sha256(file.read_bytes()).hexdigest())
        (OUT/'protected_validation.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8',newline='\n')
        print(json.dumps(result)); assert not result['changed_paths'] and result['sealed_anchors_unchanged'] and result['sealed_rows_unchanged']
