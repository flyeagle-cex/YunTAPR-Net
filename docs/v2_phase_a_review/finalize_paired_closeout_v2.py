"""Close the approved Phase-A goal only after real review, PDF and publication.

Read-only metadata and byte hashing of explicitly registered local artifacts;
no torch, checkpoint deserialization, source decoding, training or inference.
The containing final-status commit is verified separately to avoid a self hash.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess

from build_paired_decision_packet_v2 import FROZEN, KINDS, validate_inputs
from completion_gate import check_pair, resolve_authority

REPO = Path(__file__).resolve().parents[2]
ORIGIN_SHA = 'e32404d0d397dd62e1763d3fb16b4a8d8c72fb79ba52bae3f40ac095f4492869'
AUTH_SHA = '73d8e76649ac1310ff1a541cb7f0e7518c4ad527c8571113726b56312c7115a2'


def require(condition, message):
    if not condition:
        raise ValueError(message)


def digest(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def load(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def identity(path):
    path = Path(path).resolve()
    return {'absolute_local_path': str(path), 'bytes': path.stat().st_size, 'sha256': digest(path)}


def verify_ref(ref, allowed_roots):
    path = Path(ref['absolute_local_path']).resolve()
    require(any(path.is_relative_to(root.resolve()) for root in allowed_roots),
            'Unregistered artifact root; no raw source access allowed')
    require(path.stat().st_size == ref['bytes'] and digest(path) == ref['sha256'],
            'Artifact bytes changed: ' + str(path))
    return path


def verify_pdf(proof, roots):
    require(proof['status'] == 'REAL_PAIRED_REPORT_COMPILE_AND_VISUAL_PASS', 'Real PDF not verified')
    require(proof['TEST_FIXTURE_ONLY'] is False, 'Fixture PDF is not a scientific deliverable')
    require(proof['overfull_box_count'] == 0 and
            len(proof['compile_passes']) == 2 and
            all(p['exit_code'] == 0 for p in proof['compile_passes']), 'PDF compilation/layout failed')
    pages = proof['pages']
    require(len(pages) == proof['page_count'] > 0 and
            [p['page'] for p in pages] == list(range(1, len(pages) + 1)) and
            all(p['visually_checked'] is True for p in pages), 'Every real PDF page must be inspected')
    for ref in (proof['pdf'], proof['editable_latex'], proof['original_packet_latex']):
        verify_ref(ref, roots)
    for page in pages:
        verify_ref(page['rendered_image'], roots)
    require(proof['scientific_values_and_frozen_hashes_unchanged'] is True,
            'Layout must preserve scientific values and identities')


def verify_replay(proof):
    require(proof['status'] == 'B1_RETAINED_EPOCH_15_REPLAY_PREFIX_PASS', 'B1 replay not reconciled')
    require((proof['retained_trajectory_updates'], proof['all_attempt_updates'],
             proof['discarded_uncheckpointed_updates']) == (88876, 92353, 3477), 'B1 update reconciliation differs')
    require(proof['verified_resume_LAST']['epoch'] == 14 and
            proof['resume_retained_updates'] == 73192 and
            proof['retained_epoch_15_complete_updates'] == 5228, 'Wrong recovery boundary')
    require([p['completed_updates_compared'] for p in proof['comparisons']] == [3095, 382] and
            all(p['tolerance'] == 0 and not p['mismatches'] for p in proof['comparisons']),
            'Discarded-prefix zero-tolerance proof missing')
    require(proof['half_epoch_state_reused'] is False and proof['historical_sources_unchanged'] is True,
            'Historical trajectory preservation missing')
    require(all(proof[k] == 0 for k in ('FORMAL_OPTIMIZER_STEPS_ADDED', 'AUDIT_FORWARD_CALLS',
                                       'AUDIT_BACKWARD_CALLS', 'AUDIT_RAW_SOURCE_OPENS',
                                       '2025_RAW_ACCESS', '2025_PIXELS_READ')), 'Replay audit operation violation')
    require(proof['V2_PHASE_B_AUTHORIZED'] is False, 'Phase-B forbidden')


def verify_runtime_initialization(proof, expected_states):
    require(proof['status'] == 'BOTH_FORMAL_FIRST_ATTEMPT_FRESH_PAIRED_INITIALIZATION_MATCH_PREFLIGHT',
            'Formal runtime initialization receipt missing')
    require(set(proof['sources']) == set(KINDS), 'Both fresh initialization receipts required')
    for kind, ref in proof['sources'].items():
        require(ref['initial_model_sha256'] == expected_states[kind] and ref['seed'] == 2026 and
                ref['independent_reseed'] is True and ref['historical_checkpoint_loaded'] is False and
                ref['initialization_matches_preflight_full_tensor_identity'] is True,
                'Fresh paired initialization identity changed: ' + kind)


def git(*args, root=REPO):
    return subprocess.check_output(['git', '-c', 'core.longpaths=true', *args], cwd=root)


def published(path, commit):
    path = Path(path).resolve()
    require(path.is_relative_to(REPO), 'Only repository evidence may be published')
    relative = path.relative_to(REPO).as_posix()
    require(hashlib.sha256(git('show', commit + ':' + relative)).hexdigest() == digest(path),
            'Published bytes differ: ' + relative)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('authorization', 'packet-root', 'review-root', 'b0-audit', 'b1-audit',
                 'pdf-audit', 'source-policy', 'replay-audit', 'runtime-initialization',
                 'interruption-audit', 'closeout-root', 'output'):
        p.add_argument('--' + name, type=Path, required=True)
    p.add_argument('--artifact-commit', required=True)
    args = p.parse_args()
    require(digest(args.authorization) == AUTH_SHA, 'Completion authorization SHA changed')
    auth, origin = resolve_authority(args.authorization)
    require(origin == ORIGIN_SHA, 'Wrong pair scientific authority')
    gate = check_pair(args.authorization)
    require(gate['status'] == 'METADATA_COMPLETION_GATE_PASS', 'Formal models incomplete')
    require(not Path('F:/pytorch/Research/outputs/formal_training/paired_v2_gpu.lock').exists(),
            'Formal training still owns GPU')
    closeout = load(args.closeout_root / 'closeout_status.json')
    require(closeout['status'] == 'READ_ONLY_REVIEW_PASS_PDF_AND_PUBLICATION_PENDING',
            'Background review/packet not finished')
    for phase in ('B1_TERMINAL_AUDIT', 'FULL_2024_BEST_REVIEW', 'PAIRED_DECISION_PACKET'):
        require(load(args.closeout_root / (phase + '_exit.json'))['exit_code'] == 0,
                'Closeout child failed: ' + phase)
    require(git('status', '--porcelain', '--untracked-files=no').strip() == b'',
            'Tracked publication checkout must be clean')
    remote = git('ls-remote', 'origin', 'refs/heads/main').decode().split()[0]
    subprocess.run(['git', 'merge-base', '--is-ancestor', args.artifact_commit, remote],
                   cwd=REPO, check=True)
    execution = Path(auth['execution_checkout'])
    require(git('rev-parse', 'HEAD', root=execution).decode().strip() == auth['execution_commit'] and
            not git('status', '--porcelain', root=execution).strip(), 'Frozen execution checkout changed')
    for relative, sha in auth['code_sha256'].items():
        require(digest(execution / relative) == sha, 'Frozen runner code changed: ' + relative)
    protocol_path = execution / 'config/science_v2/phase_a_protocol_frozen_v1.json'
    head_path = execution / 'config/science_v2/quantile_head_v2_frozen_v1.json'
    require(digest(protocol_path) == FROZEN['protocol_sha256'] and
            digest(head_path) == FROZEN['head_sha256'], 'Frozen protocol/head SHA changed')
    data_refs = {}
    for name, ref in load(protocol_path)['identity'].items():
        path = Path(ref['path']); path = path if path.is_absolute() else execution / path
        require(path.drive.upper() != 'H:' and '\\raw\\' not in str(path).lower(),
                'Final audit may not open raw sources')
        require(digest(path) == ref['sha256'], 'Frozen config/data manifest changed: ' + name)
        data_refs[name] = identity(path)
    public = Path(auth['publication_root'])
    allowed = [REPO, *(Path(auth['checkpoint_roots'][k]) / auth['run_ids'][k] for k in KINDS)]
    review = load(args.review_root / 'paired_best_metrics.json')
    audits, early, counters, histories = {}, {}, {}, {}
    sources = [args.authorization, args.pdf_audit, args.source_policy, args.replay_audit,
               args.runtime_initialization, args.interruption_audit,
               args.closeout_root / 'closeout_status.json', args.review_root / 'paired_best_metrics.json',
               args.review_root / 'pre_inference_identity.json', Path(__file__)]
    for kind, root in zip(KINDS, (args.b0_audit, args.b1_audit)):
        audits[kind] = load(root / 'terminal_model_audit.json')
        early[kind] = load(root / 'early_stopping_reconciliation.json')
        counters[kind] = load(root / 'formal_counter_reconciliation.json')
        histories[kind] = load(public / kind / 'training_validation_history.json')
        for name in ('terminal_model_audit.json', 'early_stopping_reconciliation.json',
                     'formal_counter_reconciliation.json', 'epoch_audit.json', 'checkpoint_identity_audit.json'):
            sources.append(root / name)
        epochs = load(root / 'epoch_audit.json')
        cps = load(root / 'checkpoint_identity_audit.json')
        require(epochs['status'] == cps['status'] == 'PASS' and len(epochs['epochs']) ==
                len(cps['checkpoints']) == len(histories[kind]), 'Full per-epoch audit missing')
        require(all(row['status'] == 'PASS' and row['diagnostic_policy_affects_selection'] is False
                    for row in epochs['epochs']), 'Epoch/diagnostic audit failed')
        require(all(row['state_applied'] is False and set(row['verified_state_sha256']) ==
                    {'model', 'optimizer', 'rng', 'scheduler'} for row in cps['checkpoints']),
                'Checkpoint internal-state identity audit missing')
        sources.extend([public / kind / 'training_validation_history.json',
                        args.review_root / kind / 'final_review.json',
                        args.review_root / kind / 'inference_scope.json'])
    validate_inputs(review, audits, early, counters, histories)
    for kind in KINDS:
        for ref in review['models'][kind]['io']['log_files']:
            verify_ref(ref, allowed)
    manifest = load(args.packet_root / 'packet_manifest.json')
    for ref in manifest['artifacts'] + manifest['sources']:
        verify_ref(ref, allowed)
    pre = load(args.review_root / 'pre_inference_identity.json')
    for ref in pre['historical_checkpoint_and_epoch_artifacts']:
        verify_ref(ref, allowed)
    pdf = load(args.pdf_audit); verify_pdf(pdf, [REPO])
    replay = load(args.replay_audit); verify_replay(replay)
    for path, sha in replay['source_sha256'].items():
        require(any(Path(path).resolve().is_relative_to(r.resolve()) for r in allowed) and
                digest(path) == sha, 'Recovery evidence source changed')
    policy = load(args.source_policy)
    require(policy['status'] == 'FROZEN_SOURCE_POLICY_AND_PREFLIGHT_BINDING_PASS' and
            policy['paired_independent_reseed_2026_verified'] is True and
            policy['initial_model_states'] == auth['initial_state_sha256'], 'Fresh paired initialization proof missing')
    runtime = load(args.runtime_initialization)
    verify_runtime_initialization(runtime, auth['initial_state_sha256'])
    for ref in runtime['sources'].values():
        verify_ref(ref['formal_first_attempt_provenance'], allowed)
    interruption = load(args.interruption_audit)
    require(interruption['status'] == 'INTERRUPTED_READ_ONLY_REVIEW_PRESERVED' and
            interruption['partial_metrics_not_used_for_paired_comparison'] is True and
            args.review_root.resolve() != Path(interruption['original_review_root']).resolve(),
            'Interrupted review must be preserved; partial metrics may not replace the new full review')
    for ref in interruption['source_artifacts']:
        verify_ref(ref, [REPO])
    native_correction = args.interruption_audit.parent / 'native_event_label_reconciliation.json'
    require(load(native_correction)['status'] == 'ACTUAL_SAVED_EVENT_LABEL_COUNTS',
            'Interrupted native event-label correction missing')
    sources.append(native_correction)
    require(digest(auth['preflight_path']) == auth['preflight_sha256'] and
            digest(auth['test_summary_path']) == auth['test_summary_sha256'], 'Preflight/test identity changed')
    require(policy['preflight_source_files_verified'] == 67006 and
            sum(v['passed'] for v in policy['full_test_counts'].values()) == 770 and
            all(v['run'] == v['passed'] and not (v['failed'] or v['errors'] or v['skipped'])
                for v in policy['full_test_counts'].values()), 'Actual historical test suite differs')
    sources += [Path(auth['preflight_path']), Path(auth['test_summary_path'])]
    assets = [Path(ref['absolute_local_path']) for ref in manifest['artifacts']]
    assets += [args.packet_root / 'packet_manifest.json', Path(pdf['pdf']['absolute_local_path']),
               Path(pdf['editable_latex']['absolute_local_path'])]
    for path in set(sources + assets):
        published(path, args.artifact_commit)
    checks = {name: 'PASS' for name in (
        'both_formal_Phase_A_models_terminated', 'core_only_BEST_and_early_stop',
        'all_epochs_exact_train_validation_samples_and_counters', 'immutable_complete_epoch_checkpoints',
        'frozen_science_code_configs_normalization_data_manifests', 'fresh_paired_initialization_preflight_binding',
        'separate_retained_all_attempt_engineering_review_counters', 'B1_complete_discarded_prefix_reconciliation',
        'formal_runtime_fresh_initialization_receipts', 'interrupted_review_preserved_new_full_review',
        'full_2024_BEST_metrics_zero_tolerance_core_reconciliation', 'read_only_upper_tail_every_epoch_and_BEST',
        'full_model_optimizer_scheduler_RNG_permutation_identity_audit', 'all_registered_historical_bytes_unchanged',
        'real_editable_LaTeX_PDF_compile_and_all_page_visual_check', 'lightweight_artifacts_in_verified_GitHub_main',
        'no_Phase_B_no_2025_no_closeout_backward_or_optimizer')}
    result = {'status': 'V2_PAIRED_PHASE_A_COMPLETE_RESEARCHER_REVIEW_REQUIRED',
              'created_utc': datetime.now(timezone.utc).isoformat(), 'pair_id': auth['pair_id'],
              'requirement_checks': checks, 'models': gate['models'],
              'frozen_identities': {**FROZEN, 'scientific_commit': auth['scientific_commit'],
                                   'execution_commit': auth['execution_commit'], 'authorization_sha256': AUTH_SHA},
              'code_files_reverified': len(auth['code_sha256']), 'data_config_identities_reverified': data_refs,
              'historical_artifacts_rehashed': len(pre['historical_checkpoint_and_epoch_artifacts']),
              'publication': {'artifact_commit': args.artifact_commit, 'verified_remote_main': remote,
                              'containing_completion_commit_verified_separately': True},
              'source_evidence': [identity(path) for path in sorted(set(sources + assets))],
              'FORMAL_TRAINING_COMPLETED': True, 'FORMAL_TRAINING_RUNNING': False,
              'V2_SCIENTIFIC_FREEZE_APPROVED': True, 'FORMAL_TRAINING_AUTHORIZED': True,
              'V2_PHASE_A_AUTHORIZED': True, 'V2_PHASE_A_STARTED': True,
              'FORMAL_OPTIMIZER_STEPS_RETAINED': {k: gate['models'][k]['completed_epoch'] * 5228 for k in KINDS},
              'CLOSEOUT_OPTIMIZER_STEPS': 0, 'CLOSEOUT_BACKWARD_CALLS': 0,
              'FINAL_AUDIT_FORWARD_CALLS': 0, 'FINAL_AUDIT_RAW_SOURCE_OPENS': 0,
              'FINAL_AUDIT_CHECKPOINT_DESERIALIZATIONS': 0,
              'READ_ONLY_FINAL_2024_REVIEW_FORWARDS': {k: 1313 for k in KINDS},
              'READ_ONLY_ALL_ATTEMPT_COMPLETED_FORWARDS': {
                  k: 1313 + interruption['completed_read_only_work'][k]['completed_forwards_journal_records']
                  for k in KINDS},
              'review_counter_scope': 'Completed final review and interrupted earlier review remain separate; neither contributes formal optimizer updates',
              'PDF_VISUALLY_VERIFIED': True, 'FINAL_GITHUB_ARTIFACT_PUBLICATION_VERIFIED': True,
              'V2_PHASE_B_AUTHORIZED': False, 'B1_PHASE_B_STARTED': False,
              'FORMAL_RESUME_AUTHORIZED': False, '2025_RAW_ACCESS': 0, '2025_PIXELS_READ': 0,
              'RESEARCHER_PHASE_A_REVIEW_REQUIRED': True, 'AUTOMATIC_NEXT_STAGE': False,
              'STOP_AFTER_FINAL_STATUS_PUBLICATION': True}
    out = args.output.resolve()
    require(out.is_relative_to(REPO / 'docs/v2_phase_a_review/final_completion'), 'Independent final root required')
    out.mkdir(parents=True, exist_ok=False)
    with (out / 'FINAL_COMPLETION_AUDIT.json').open('x', encoding='utf-8', newline='\n') as stream:
        json.dump(result, stream, ensure_ascii=False, indent=2, allow_nan=False); stream.write('\n')
    print(json.dumps({'status': result['status'], 'output': str(out)}, ensure_ascii=False), flush=True)


if __name__ == '__main__':
    main()
