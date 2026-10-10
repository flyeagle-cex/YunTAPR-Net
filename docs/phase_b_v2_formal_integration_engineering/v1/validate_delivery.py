"""Read only public source/document paths; no tensor/optimizer/data execution."""
from pathlib import Path
import ast
import hashlib
import json
import subprocess

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
NS=ROOT/'src/yuntapr/experimental/phase_b_v2_formal_integration_candidate'

def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()

def public_files():
    return sorted(p for base in (NS,HERE) for p in base.rglob('*') if p.is_file()
                  and '.local' not in p.parts and '__pycache__' not in p.parts and p.suffix!='.pyc')

def validate():
    manifest=json.loads((HERE/'manifest.json').read_text(encoding='utf-8'))
    for item in manifest['files']:
        path=ROOT/item['path']
        assert path.is_relative_to(ROOT) and '.local' not in path.parts
        assert sha(path)==item['sha256'],item['path']
    inventory=json.loads((HERE/'source_identity.json').read_text(encoding='utf-8'))
    for item in inventory['public_source_files']:
        assert sha(ROOT/item['path'])==item['sha256'],item['path']
    for path in public_files():
        raw=path.read_bytes();assert b'\r' not in raw,path.name
        if path.suffix=='.py':ast.parse(raw.decode('utf-8'),filename=path.name)
        if path.suffix=='.json':json.loads(raw)
        tokens=(b'C:'+bytes([92])+b'Users'+bytes([92]),b'F:'+bytes([92])+b'pytorch'+bytes([92]),b'gh'+b'p_',b'github'+b'_pat_')
        assert not any(token in raw for token in tokens),path.name
    status=json.loads((HERE/'final_status.json').read_text())
    assert status['FORMAL_OPTIMIZER_STEPS']==0 and status['SYNTHETIC_OPTIMIZER_STEPS']==4
    assert not status['V2_PHASE_B_AUTHORIZED'] and status['historical_2025_path_attributes']=='NOT_INSTRUMENTED'
    baseline=manifest['baseline_commit']
    changes=subprocess.check_output(['git','diff','--name-only',baseline],cwd=ROOT,text=True).splitlines()
    allowed=('src/yuntapr/experimental/phase_b_v2_formal_integration_candidate/', 'docs/phase_b_v2_formal_integration_engineering/v1/')
    assert all(p.startswith(allowed) for p in changes),changes
    print(json.dumps({'status':'PASS','public_sources':len(inventory['public_source_files']),
                      'manifest_entries':len(manifest['files']),'formal_updates':0,'synthetic_updates':4}))

if __name__=='__main__':validate()
