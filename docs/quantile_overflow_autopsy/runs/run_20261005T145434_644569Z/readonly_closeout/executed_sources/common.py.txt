"""Immutable scope and small, strict artifact helpers (stdlib only)."""
from pathlib import Path
from datetime import datetime, timezone
import csv
import hashlib
import json
import os

ROOT = Path(__file__).resolve().parents[2]
BASELINE = '9303f1ec99f7623439583e6e1609fbde043213db'
FAILED_ID = 'run_20261005T103053_888886Z'
FAILED = ROOT / 'docs/formal_training/b0_matched_phase_b_finalfit/runs' / FAILED_ID
ATTACHMENT = Path(r'C:\Users\chenerxiao\.codex\attachments\6c98efe6-8a52-4850-8f06-e1f1a83c25e2\已粘贴的文本.txt')
SCOPE = 'ENGINEERING_OVERFLOW_REPLAY_ONLY'
SUCCESS = 8625
FAIL_BATCH = 8626
BOUNDARY = 41912
FORMAL_STEPS = 50537
CHECKPOINT_SHA = '5bda7d3fae1c0f6c44d4ec767f5a69749781e11ef3bb41aaa32e7d99355da8e0'
MODEL_SHA = 'c723e0d022964fbfcd4cc1603a04656eb16e68dda8e1a7795d602baba372fdc7'
ERROR = 'QUANTILE_PHYSICAL_OVERFLOW: expm1(qlog) nonfinite'

def now():
    return datetime.now(timezone.utc).isoformat()

def digest(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda: f.read(8 * 1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()

def read(path):
    return json.loads(Path(path).read_text(encoding='utf8'))

def write(path, value, exclusive=True):
    with Path(path).open('x' if exclusive else 'w', encoding='utf8', newline='\n') as f:
        json.dump(value, f, indent=2, ensure_ascii=False, allow_nan=False)
        f.write('\n')

def progress(run, value):
    p = Path(run) / 'progress.json'
    temp = p.with_suffix('.tmp')
    write(temp, {'utc': now(), **value}, exclusive=False)
    os.replace(temp, p)

def pin(path):
    p = Path(path).resolve()
    return {'path': str(p), 'bytes': p.stat().st_size, 'sha256': digest(p)}

def verify(ref):
    p = Path(ref['path'])
    if p.stat().st_size != ref['bytes'] or digest(p) != ref['sha256']:
        raise ValueError('Immutable identity changed: ' + str(p))
    return p

def csv_rows(path):
    with Path(path).open(encoding='utf8', newline='') as f:
        return list(csv.DictReader(f))

def historical_updates(epoch):
    p = FAILED / f'logs/epoch_{epoch:03d}/step_events.jsonl'
    with p.open(encoding='utf8') as f:
        for line in f:
            row = json.loads(line)
            if row['event'] == 'TRAIN_UPDATE_AUDITED':
                yield row

def exact_reconcile(reference, actual):
    keys = ('sample_ids', 'update', 'LR', 'actual_denominator', 'loss',
            'pre_clip_norm', 'post_clip_norm', 'clipped')
    mismatches = {k: {'expected': reference.get(k), 'actual': actual.get(k)}
                  for k in keys if reference.get(k) != actual.get(k)}
    if mismatches:
        raise ValueError('REPRODUCTION_FAILURE: ' + json.dumps(mismatches, allow_nan=False))
    return keys

def snapshot(run):
    manifest = read(FAILED / 'run_manifest.json')
    paths = {p.resolve() for p in FAILED.rglob('*') if p.is_file()}
    paths.update((ROOT / p).resolve() for p in manifest['code_hashes'])
    paths.update(Path(manifest[k]['path']).resolve() for k in
                 ('authority', 'protocol', 'normalization', 'manifest'))
    # All historical completed checkpoint identities, without deserialization.
    history = read(FAILED / 'training_history.json')
    paths.update(Path(row['checkpoint']['absolute_local_path']).resolve() for row in history)
    refs = [pin(p) for p in sorted(paths)]
    write(Path(run) / 'immutability_before.json', {'utc': now(), 'files': refs})
    return refs

def verify_snapshot(run):
    refs = read(Path(run) / 'immutability_before.json')['files']
    for ref in refs:
        verify(ref)
    return {'all_byte_identical': True, 'file_count': len(refs),
            'protocol_sha256': read(FAILED / 'run_manifest.json')['protocol']['sha256'],
            'normalization_sha256': read(FAILED / 'run_manifest.json')['normalization']['sha256'],
            'formal_optimizer_steps': read(FAILED / 'execution_counters.json')['FORMAL_OPTIMIZER_STEPS']}
