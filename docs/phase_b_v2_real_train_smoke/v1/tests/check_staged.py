"""Check exact staged scope/digests; do not touch any private payload."""
import hashlib
import json
from pathlib import Path
import subprocess
ROOT=Path(__file__).absolute().parents[4]
OUT=ROOT/'docs/phase_b_v2_real_train_smoke/v1'
manifest=json.loads((OUT/'manifest.json').read_bytes())
names=subprocess.check_output(['git','diff','--cached','--name-only','-z'],cwd=ROOT).decode().split('\0')[:-1]
expected={r['path'] for r in manifest['files']}|{'docs/phase_b_v2_real_train_smoke/v1/manifest.json'}
assert set(names)==expected
rows=subprocess.check_output(['git','diff','--cached','--name-status'],cwd=ROOT).decode().splitlines()
assert all(r.startswith('A\t') for r in rows)
assert all('.local/' not in p and not p.endswith(('.pt','.pth','.ckpt','.sqlite')) for p in names)
for r in manifest['files']:
    raw=subprocess.check_output(['git','show',':'+r['path']],cwd=ROOT)
    assert hashlib.sha256(raw).hexdigest()==r['sha256'],r['path']
subprocess.run(['git','diff','--cached','--check'],cwd=ROOT,check=True,stdout=subprocess.DEVNULL)
print(json.dumps({'staged_allowed_files':len(names),'staged_sha_matched':len(manifest['files']),
    'private_payloads_staged':0,'only_added':True,'whitespace_check':'PASS'}))
