"""Verify only published metadata; stdlib only, no training or private inputs."""
import csv
import hashlib
import json
import math
from pathlib import Path
import re

ROOT=Path(__file__).resolve().parents[1]


def load(name):
    return json.loads((ROOT/name).read_text(encoding='utf-8-sig'))


def close(a,b):
    assert math.isclose(a,b,rel_tol=1e-12,abs_tol=1e-13),(a,b)


def main():
    records=load('evidence/experiments.json')['experiments'];by_id={r['experiment_id']:r for r in records}
    assert len(records)==len(by_id)==22
    with (ROOT/'EXPERIMENT_MATRIX.csv').open(encoding='utf-8',newline='') as f:matrix=list(csv.DictReader(f))
    assert len(matrix)==22 and {r['experiment_id'] for r in matrix}==set(by_id)
    for row in matrix:
        original=by_id[row['experiment_id']]
        assert int(row['epochs'])==original['epochs'] and int(row['global_steps'])==original['global_steps']
        assert row['seed']==str(original['seed']) and row['status']==original['status']
    epochs=load('evidence/epoch_receipts.json')['epochs'];assert len(epochs)==126
    for eid in [r['experiment_id'] for r in records if r['phase']=='PHASE_B_V2' or r['status']=='COMPLETE_TRAIN_AND_DEV_EVALUATION' and r['model_id'] in ('B3','B4')]:
        subset=[e for e in epochs if e['experiment_id']==eid]
        assert [e['epoch'] for e in subset]==list(range(1,10))
        endpoint=by_id[eid]['metrics'];last=subset[-1]['development']
        for k in ('brier','auroc','average_precision','conditional_pinball','q32_coverage'):close(last[k],endpoint[k])
    for e in epochs:
        s=e['development'];assert sum(r['n'] for r in s['rain_strata'])==s['n_rain']
        close(s['brier_sum']/s['n_valid'],s['brier'])
        close(s['s_qr']/s['n_rain'],s['conditional_pinball'])
        close((s['s_occ']+s['s_qr'])/s['n_valid'],s['core_fp64'])
        close(sum(r['pinball_sum'] for r in s['rain_strata'])/s['n_rain'],s['conditional_pinball'])
        assert len(s['tau'])==len(s['covered'])==len(s['coverage'])==32
        for i in range(32):
            assert s['tau'][i]==(i+.5)/32
            close(s['covered'][i]/s['n_rain'],s['coverage'][i])
        close(s['coverage'][-1]-.984375,s['q32_signed_bias'])
    for seed in (2026,2027):
        for arm in ('E0','E1','E2'):
            a=[e for e in epochs if e['experiment_id']==f'B0_MATCHED_V2__{arm}__s{seed}']
            b=[e for e in epochs if e['experiment_id']==f'B1_V2__{arm}__s{seed}']
            for x,y in zip(a,b):
                assert x['train']['ids_sha']==y['train']['ids_sha']
                assert x['development_ids_sha256']==y['development_ids_sha256']
    g=load('evidence/seed2029_groups.json');delta=load('evidence/seed2029_paired_difference.json')
    for group in g['B3']:
        a,b=(g[m][group] for m in ('B3','B4'))
        assert a['ids_sha256']==b['ids_sha256']
        assert a['summary']['n_valid']==b['summary']['n_valid']
        for k in ('brier','auroc','average_precision','conditional_pinball','q32_signed_bias','core_fp64'):
            close(b['summary'][k]-a['summary'][k],delta['groups'][group][k])
    execution=load('evidence/seed2029_execution.json')
    assert execution['actual_update_attempts']==execution['paired_effective_updates']+execution['approved_replayed_updates']==9120
    assert execution['actual_io']['opened_files']==299968
    assert execution['actual_io']['delivered_bytes']==1003563940849
    assert execution['actual_io']['reserved_bytes']==1003568959114
    assert execution['paired_initialization']['B3']['common_sha256']==execution['paired_initialization']['B4']['common_sha256']
    # Do not label implemented candidates as formal runs.
    assert not any(r['model_id'] in ('B2','B5','B6','B7','B8','B9') for r in records)
    paths=[p for p in ROOT.rglob('*') if p.is_file() and '.local' not in p.parts and '__pycache__' not in p.parts]
    sensitive=re.compile(r'(?<![A-Za-z0-9])[A-Za-z]:[\\/]|[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}|github_pat_[A-Za-z0-9_]{20,}|gh[pousr]_[A-Za-z0-9]{20,}|-----BEGIN (?:RSA |OPENSSH )?PRIVATE KEY-----')
    for p in paths:
        assert p.suffix.lower() not in ('.pt','.pth','.ckpt','.sqlite','.nc','.hdf5','.h5','.zip'),p.name
        assert not sensitive.search(p.read_text(encoding='utf-8-sig')),str(p.relative_to(ROOT))
    for name in ('CURRENT_STATUS.md','SCIENTIFIC_RESULTS.md','EVIDENCE_INDEX.md','EXPERIMENT_MATRIX.csv'):
        assert (ROOT/name).is_file()
    manifest=ROOT/'PUBLICATION_MANIFEST.json'
    if manifest.exists():
        for item in load('PUBLICATION_MANIFEST.json')['files']:
            raw=(ROOT/item['path']).read_bytes()
            assert len(raw)==item['bytes'] and hashlib.sha256(raw).hexdigest()==item['sha256']
    print(json.dumps(dict(status='PASS',experiments=22,numeric_epoch_receipts=126,
        exact_pairing_and_sufficient_statistics='PASS',privacy_and_scope='PASS',
        raw_weather_reads=0,checkpoint_payload_reads=0,new_optimizer_updates=0,
        limitation='Public metadata consistency only; does not independently replay private experiments.')))


if __name__=='__main__':main()
