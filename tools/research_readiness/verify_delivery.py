"""Verify source identity, proposal, reports and delivered file checksums."""
from pathlib import Path
import ast
import csv
import hashlib
import json
import re

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT/'docs/research_readiness/20261025'


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    public = ROOT/'docs/research_progress'
    checked = OUT/'rechecked_snapshot'
    original = read(public/'evidence/experiments.json')['experiments']
    rechecked = read(checked/'evidence/experiments.json')['experiments']
    assert len(original) == len(rechecked) == 22
    for a, b in zip(original, rechecked):
        for k in ('experiment_id','metrics','status','seed','epochs','global_steps','checkpoint_reference'):
            assert a[k] == b[k], (a['experiment_id'], k)
    x, y = [read(p/'evidence/epoch_receipts.json')['epochs'] for p in (public, checked)]
    assert len(x) == len(y) == 126
    assert x == y, 'Original and rechecked epoch receipt extracts differ'
    x, y = [read(p/'evidence/source_manifest.json')['sources'] for p in (public, checked)]
    assert x == y and len(x) == 129
    proposal = read(OUT/'evidence/b2_proposal_v3.json')
    assert proposal['formal_training_status'] == 'NOT_STARTED' and proposal['formal_authorization'] is False
    assert proposal['optimizer_updates'] == proposal['raw_weather_reads'] == proposal['checkpoint_loads'] == 0
    for name, h in proposal['code_sha256'].items():
        assert sha(ROOT/name) == h, name
    assert proposal['train_orders_9_epochs_match_historical_B3']
    assert proposal['data']['train'] == 959 and proposal['data']['dev'] == 963
    assert proposal['budget']['optimizer_update_cap'] == 4320
    assert proposal['budget']['logical_source_bytes'] == 477571641012
    assert proposal['budget']['logical_source_read_instances'] == 142812
    approval = read(OUT/'B2_RESEARCHER_APPROVAL_TEMPLATE.json')
    assert approval['approved_by_researcher'] is False
    assert approval['proposal_sha256'] == proposal['proposal_sha256']
    with (OUT/'B0_B4_EXPERIMENT_MATRIX.csv').open(encoding='utf-8', newline='') as f:
        matrix = list(csv.DictReader(f))
    assert len(matrix) == 27
    pending = [r for r in matrix if r['authorization_status'] == 'NOT_AUTHORIZED']
    assert len(pending) == 5 and all(r['status']=='NOT_STARTED' and r['epochs']=='0' and r['global_steps']=='0' for r in pending)
    assert len({r['experiment_id'] for r in matrix}) == 27
    reports = ['B2_TRAINING_AND_EVALUATION_REPORT.md','B3_B4_MULTI_SEED_PLAN.md',
               'B0_B4_STAGE_ACCEPTANCE.md','B5_B6_READINESS_REPORT.md']
    for name in reports:
        text = (OUT/name).read_text(encoding='utf-8')
        assert any(v in text for v in ('NOT_STARTED','IN_PROGRESS','NOT_VERIFIED'))
        assert '2025' in text and '0ccb3e26' in text
        for link in re.findall(r'\]\(([^)]+)\)', text):
            if not link.startswith(('https://','http://')):
                assert (OUT/link).exists(), (name, link)
    sources = [p for folder in ('src/yuntapr/experimental/research_readiness','tools/research_readiness','tests/research_readiness')
               for p in (ROOT/folder).glob('*.py')]
    for path in sources:
        ast.parse(path.read_text(encoding='utf-8'), filename=path.name)
    paths = [p for p in OUT.rglob('*') if p.is_file() and '__pycache__' not in p.parts]
    sensitive = re.compile(r'(?<![A-Za-z0-9])[A-Za-z]:[\\/]|github_pat_[A-Za-z0-9_]{20,}|gh[pousr]_[A-Za-z0-9]{20,}|-----BEGIN (?:RSA |OPENSSH )?PRIVATE KEY-----')
    for path in paths:
        assert path.suffix.lower() not in ('.pt','.pth','.ckpt','.nc','.hgt','.h5','.hdf5','.sqlite'), path
        assert not sensitive.search(path.read_text(encoding='utf-8-sig')), path
    manifest = OUT/'DELIVERY_MANIFEST.json'
    if manifest.exists():
        for row in read(manifest)['files']:
            file = ROOT/row['path']
            assert file.stat().st_size == row['bytes'] and sha(file) == row['sha256'], row['path']
    result = dict(status='PASS', original_experiments_rechecked=22, numeric_epoch_receipts=126,
                  original_sources_rechecked=129, experiment_matrix_rows=27, pending_unapproved_runs=5,
                  b2_formal_training='NOT_STARTED', b3_b4_multiseed='IN_PROGRESS', b5_b6_production='NOT_VERIFIED',
                  source_consistency='PASS', code_and_proposal_identity='PASS', report_links_and_privacy='PASS',
                  formal_optimizer_updates=0, raw_weather_reads=0, checkpoint_loads=0,
                  limitation='Evidence and candidate consistency only. No new trained model or scientific acceptance.')
    print(json.dumps(result))


if __name__ == '__main__':
    main()
