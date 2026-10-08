"""Read-only recovery gate and independent authorization evidence; no state application."""
import json, sys
from pathlib import Path
from datetime import datetime, timezone

REPO = Path(__file__).resolve().parents[2]
EXEC = REPO.parent / 'YunTAPR-Net-v2-phase-a-execution'
sys.path[:0] = [str(EXEC/'src'), str(EXEC/'scripts')]

def main():
    import torch
    torch.set_num_threads(2)
    from yuntapr.training import formal_phase_a_v2 as f
    from yuntapr.training.checkpoint_v2 import verify_file
    origin = REPO/'docs/v2_phase_a_authorized/pair_20261007T070503_825794Z/authorization.json'
    assert f.digest(origin) == 'e32404d0d397dd62e1763d3fb16b4a8d8c72fb79ba52bae3f40ac095f4492869'
    a = f.read_json(origin)
    c = f.Contract.load(EXEC)
    assert c.code == a['code_sha256']
    assert f.git('rev-parse', 'HEAD', root=EXEC) == a['execution_commit']
    assert not f.git('status', '--porcelain', '--untracked-files=normal', root=EXEC)
    for p, h in [('preflight_path', 'preflight_sha256'), ('test_summary_path', 'test_summary_sha256')]:
        assert f.digest(a[p]) == a[h]
    public = Path(a['publication_root'])/'B0_MATCHED_V2'
    local = Path(a['checkpoint_roots']['B0_MATCHED_V2'])/a['run_ids']['B0_MATCHED_V2']
    ref = f.read_json(public/'last_checkpoint_identity.json')
    assert ref['epoch'] == 16 and ref['global_update'] == 83648
    assert ref['sha256'] == '46addfa8a76f7ba278a592d4a8781b06a3805a28a1a19f4200ccb6c7006f5cad'
    marker = f.read_json(public/'epoch_016_complete.json')
    registry = f.read_json(public/'checkpoint_registry.json')
    assert marker['status'] == 'PASS' and marker['checkpoint'] == ref == registry['LAST']
    assert len(registry['epochs']) == 16
    prov = f.read_json(local/'audit/run_20261007T070818_003523Z/provenance.json')
    for key in ('protocol_sha256', 'head_sha256', 'normalization_sha256', 'code_sha256', 'execution_commit', 'pair_id'):
        assert prov[key] == a[key], key
    assert prov['identity'] == c.protocol['identity']
    assert prov['origin_authorization_sha256'] == f.digest(origin)
    assert prov['initialization'] == f.read_json(a['preflight_path'])['paired_initialization']
    payload = verify_file(ref, prov)
    assert payload['selection']['non_improvement_count'] == 7
    reconciliation = f.reconcile_attempts(local, 16)
    assert Path('H:/葵花202303_202510').is_dir(), 'Original H drive unavailable'
    sources = c.sources()
    sizes_checked = 0
    for p, item in sources.items():
        assert item['year'] in (2023, 2024)
        stat = Path(p).stat()
        if item['expected_bytes'] is not None:
            assert stat.st_size == item['expected_bytes'], p
            sizes_checked += 1
    # Recheck bytes of the next formal batch only. Remaining source SHA checks
    # remain mandatory in the unchanged guarded reader on each actual read.
    order = f.epoch_permutation(16, count=10455)
    hashes = []
    for idx in order[:2]:
        row = c.records['B0_MATCHED_V2', 2023][int(idx)]
        frame = c.frames[row['expected_nominal']]
        for p, expected in [(Path(row['imerg_day_path']), row['imerg_sha256']),
                            (f.data.H_ROOT/frame['relative_path'], frame['source_sha256'])]:
            actual = f.digest(p)
            assert actual == expected, str(p)
            hashes.append({'path': str(p), 'sha256': actual})
    now = datetime.now(timezone.utc)
    out = origin.parent/now.strftime('resume_%Y%m%dT%H%M%S_%fZ')
    out.mkdir()
    report = {'status': 'PASS', 'created_utc': now.isoformat(), 'checkpoint': ref,
        'verified_state_sha256': payload['state_sha256'], 'scheduler': payload['scheduler'],
        'selection': payload['selection'], 'completed_permutation_sha256': payload['completed_permutation_sha256'],
        'next_permutation_sha256': payload['next_permutation_sha256'], 'frozen_manifest_identities': c.protocol['identity'],
        'code_sha256_verified': True, 'paired_initialization_identity_verified': True,
        'source_files_exist': len(sources), 'source_size_checks': sizes_checked,
        'next_batch_source_sha_checks': hashes, 'all_source_sha_repeated': False,
        'source_sha_policy': 'Original completed preflight retained; unchanged reader verifies every actual source read.',
        'reconciliation': reconciliation, 'state_application_performed': False,
        'formal_optimizer_steps_added': 0, '2025_RAW_ACCESS': 0, '2025_PIXELS_READ': 0,
        'V2_PHASE_B_AUTHORIZED': False, 'resume_launched': False,
        'unclean_exit_note': 'Journal bounds retained. All uncheckpointed epoch 17 updates discarded. No original artifact changed.'}
    f.atomic_json(out/'resume_precheck.json', report, immutable=True)
    record = out/'RESEARCHER_RESUME_AUTHORIZATION_RECORD.md'
    record.write_text('# Researcher-authorized v2 Phase-A recovery\n\n'
        'On 2026-10-08 (Asia/Shanghai), the researcher said “继续” following the requested stop. '
        'This resumes the previously authorized paired Phase-A scope. Resume B0-Matched-v2 only from '
        'verified epoch 16 LAST (83,648 retained updates), discard all uncheckpointed epoch 17 updates, '
        'then start B1-v2 from the original frozen fresh paired initialization. No new scientific decision, '
        'Phase-B, 2025 access, hyperparameter change, or history replacement is authorized.\n\n'
        'The original process_exit.json and stop record remain immutable. Publish this recovery authority '
        'to remote main before invoking the unchanged pinned runner resume command.\n', encoding='utf-8')
    auth = dict(a)
    auth.update(created_utc=now.isoformat(), V2_PHASE_A_STARTED=True, resume_authorized=True,
        resume_model='B0_MATCHED_V2', resume_LAST_sha256=ref['sha256'],
        origin_authorization_path=str(origin), origin_authorization_sha256=f.digest(origin),
        researcher_approval_reference=str(record), researcher_approval_record_sha256=f.digest(record),
        launch_mode='VERIFIED_EPOCH_16_RESUME_THEN_FRESH_B1',
        resume_precheck_path=str(out/'resume_precheck.json'), resume_precheck_sha256=f.digest(out/'resume_precheck.json'))
    f.atomic_json(out/'authorization.json', auth, immutable=True)
    # Exercise the existing authorization gate, without constructing any model.
    f.authorize(out/'authorization.json', f.digest(out/'authorization.json'), c, resume=True)
    print(json.dumps({'directory': str(out), 'authorization_sha256': f.digest(out/'authorization.json'),
                      'reconciliation': reconciliation, 'source_files_exist': len(sources)}, ensure_ascii=False), flush=True)

if __name__ == '__main__':
    main()
