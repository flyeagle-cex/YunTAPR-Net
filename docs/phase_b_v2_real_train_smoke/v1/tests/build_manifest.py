"""Hash only these two public delivery namespaces, never local scratch data."""
from pathlib import Path
import hashlib
import json
ROOT=Path(__file__).absolute().parents[4]
OUT=ROOT/'docs/phase_b_v2_real_train_smoke/v1'
SRC=ROOT/'src/yuntapr/experimental/phase_b_v2_real_train_smoke'
# Only new public reports/logs: retain private originals and exact executed code.
targets=list(OUT.glob('*.md'))+list(OUT.glob('*.json'))+list(OUT.glob('*.jsonl'))
targets+=list((OUT/'tests').glob('*.redacted.log'))+list((OUT/'tests').glob('*.json'))
for path in targets:
    raw=path.read_bytes(); normalized=raw.replace(b'\r\r\n',b'\n').replace(b'\r\n',b'\n')
    if normalized!=raw: path.write_bytes(normalized)
files=[]
for directory in (OUT,SRC):
    # Explicit local/cache pruning, before listing any child contents.
    import os
    for parent,dirs,names in os.walk(directory):
        dirs[:]=[d for d in dirs if d not in ('.local','__pycache__')]
        for name in names:
            p=Path(parent)/name
            if p==OUT/'manifest.json': continue
            if p.suffix.lower() in ('.pt','.pth','.ckpt','.part','.sqlite'):
                raise AssertionError('NO_PRIVATE_PAYLOAD_IN_PUBLIC_MANIFEST')
            raw=p.read_bytes()
            files.append({'path':p.relative_to(ROOT).as_posix(),'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()})
files.sort(key=lambda r:r['path'])
manifest={'schema':'REAL_TRAIN_SMOKE_PUBLIC_DELIVERY_SHA256_v1',
    'baseline_commit':'86cf8ea0ab8410542997ced6e3689880f6e2e0e0','files':files,
    'excluded':['.local/','__pycache__/','manifest.json (self digest)'],
    'commit_identity':'git log -- docs/phase_b_v2_real_train_smoke/v1',
    'scientific_approval_granted':False}
(OUT/'manifest.json').write_bytes((json.dumps(manifest,indent=2)+'\n').encode())
print(json.dumps({'public_files':len(files),'public_total_bytes':sum(r['bytes'] for r in files)}))
