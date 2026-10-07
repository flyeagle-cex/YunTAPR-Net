from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json

ROOT = Path(__file__).resolve().parents[2]
RUN_ROOT = ROOT / 'docs/scientific_freeze_v2/runs'
BASELINE = '26fb03894d8fc4099019279a3025ac7cdb541ec9'


def now():
    return datetime.now(timezone.utc).isoformat()


def digest(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(4 * 1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def read(path):
    return json.loads(Path(path).read_text(encoding='utf8'))


def write(path, value):
    with Path(path).open('x', encoding='utf8', newline='\n') as stream:
        json.dump(value, stream, indent=2, ensure_ascii=False, allow_nan=False)
        stream.write('\n')


def pin(path):
    p = Path(path).resolve()
    return {'path': str(p), 'bytes': p.stat().st_size, 'sha256': digest(p)}


def progress(run, phase, **values):
    import os
    temp = Path(run) / 'progress.tmp'
    with temp.open('w', encoding='utf8') as stream:
        json.dump({'utc': now(), 'phase': phase, **values}, stream, ensure_ascii=False, allow_nan=False)
    os.replace(temp, Path(run) / 'progress.json')


def verify_history(run):
    refs = read(Path(run) / 'historical_inventory_before.json')['files']
    for ref in refs:
        p = Path(ref['path'])
        if p.stat().st_size != ref['bytes'] or digest(p) != ref['sha256']:
            raise ValueError('Historical artifact changed: ' + str(p))
    return {'all_byte_identical': True, 'file_count': len(refs),
            'checkpoint_count': sum(Path(r['path']).suffix.lower() in ('.pt','.pth','.ckpt') for r in refs)}
