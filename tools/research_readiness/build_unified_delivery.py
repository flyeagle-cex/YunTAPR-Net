"""Export the five public research entry points from existing receipts only.

No torch, raw observations, checkpoint loading, training, or network access.
Default rebuild uses the dated status embedded in EVIDENCE_INDEX.md. A new
sanitized metadata snapshot may be supplied explicitly with --status-json.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import re
import statistics
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
READY = 'docs/research_readiness/20261025/'
PROGRESS = 'docs/research_progress/'
OLD = PROGRESS + 'evidence/experiments.json'
B2 = READY + 'evidence/b2_completion_and_paired_evidence.json'
B34 = READY + 'evidence/b3_b4_three_seed_completion.json'
FULL = READY + 'evidence/b3_b4_full_endpoint_metrics_20261027.json'
STATIC = READY + 'evidence/b5_b6_completion_and_paired_evidence.json'
INNOVATION = READY + 'evidence/b7_b8_training_proposal.json'
INNOVATION_LAUNCH = READY + 'evidence/b7_b8_approved_launch.json'
INNOVATION_TERMINAL = READY + 'evidence/b7_b8_terminal_20261028.json'
B8_RECOVERY = READY + 'evidence/b8_recovery_proposal_20261028.json'
B8_DIAGNOSTIC = READY + 'evidence/b8_source_diagnostic_20261028.json'
B8_CHECKS = READY + 'evidence/b8_recovery_checks_20261028.json'
B8_LAUNCH = READY + 'evidence/b8_recovery_approved_launch_20261028.json'
B8_COMPLETE = READY + 'evidence/b8_recovery_completion_20261028.json'
INNOVATION_MULTI = READY + 'evidence/b7_b8_multiseed_proposal_20261028.json'
INNOVATION_MULTI_CHECKS = READY + 'evidence/b7_b8_multiseed_checks_20261028.json'
INNOVATION_MULTI_SOURCE = READY + 'evidence/b7_b8_multiseed_source_admission_20261028.json'
INNOVATION_MULTI_LAUNCH = READY + 'evidence/b7_b8_multiseed_approved_launch_20261028.json'
INNOVATION_MULTI_STOP = READY + 'evidence/b7_b8_multiseed_interruption_20261028.json'
INNOVATION_MULTI_CAUSE = READY + 'evidence/b7_b8_multiseed_exit_cause_20261028.json'
INNOVATION_MULTI_RECOVERY = READY + 'evidence/b7_b8_multiseed_recovery_proposal_20261028.json'
INNOVATION_MULTI_RECOVERY_CHECKS = READY + 'evidence/b7_b8_multiseed_recovery_checks_20261028.json'
INNOVATION_MULTI_RECOVERY_LAUNCH = READY + 'evidence/b7_b8_multiseed_recovery_approved_launch_20261028.json'
GROUPS = PROGRESS + 'evidence/seed2029_groups.json'
BASE = READY + 'B0_B4_EXPERIMENT_MATRIX.csv'
FIELDS = ('record_type,experiment_id,model_id,seed,loss_arm,epoch,split,'
          'comparison_population,group,group_ids_sha256,metric,value,status,unit,'
          'comparison,reference_experiment_id,reference_value,n_seeds,'
          'improvement_direction,source_file,source_pointer,reference_source_file,'
          'reference_source_pointer,executed_commit,evaluation_script,checkpoint_sha256').split(',')
HEADLINE = ('brier', 'auroc', 'average_precision', 'conditional_pinball',
            'q32_coverage', 'q32_signed_bias', 'q32_absolute_error')


def read(name):
    return json.loads((ROOT / name).read_text(encoding='utf-8'))


def digest(name):
    return hashlib.sha256((ROOT / name).read_bytes()).hexdigest()


def write_csv(name, fields, rows):
    with (ROOT / name).open('w', encoding='utf-8', newline='') as f:
        w = csv.DictWriter(f, fields, lineterminator='\n')
        w.writeheader()
        w.writerows(rows)


def leaves(obj, path=''):
    if isinstance(obj, dict):
        for k, v in obj.items():
            yield from leaves(v, path + '/' + str(k).replace('~', '~0').replace('/', '~1'))
    elif isinstance(obj, list):
        for k, v in enumerate(obj):
            yield from leaves(v, path + '/' + str(k))
    else:
        yield path, obj


def favorable(metric):
    if metric in ('brier', 'conditional_pinball', 'q32_absolute_error') or metric.endswith('/conditional_pinball'):
        return 'LOWER'
    if metric in ('auroc', 'average_precision'):
        return 'HIGHER'
    if metric in ('q32_coverage', 'q32_signed_bias'):
        return 'CLOSER_TO_NOMINAL_0.984375'
    if metric.startswith('coverage/'):
        return 'CLOSER_TO_CORRESPONDING_TAU'
    return 'DESCRIPTIVE_ONLY'


def unit(metric):
    if metric.endswith('conditional_pinball') or metric.endswith('pinball_sum') or metric == 's_qr':
        return 'FROZEN_LOG1P_RAIN_PINBALL_SCALE'
    if metric in ('scenes', 'n_valid', 'n_rain', 'q32_covered') or metric.startswith('covered/'):
        return 'COUNT'
    return 'AS_RECORDED_SEE_SOURCE'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--status-json', type=Path)
    args = parser.parse_args()
    if args.status_json:
        snapshot = json.loads(args.status_json.read_text(encoding='utf-8'))
    else:
        text = (ROOT / 'EVIDENCE_INDEX.md').read_text(encoding='utf-8')
        snapshot = json.loads(re.search(r'<!-- STATUS_SNAPSHOT -->\s*```json\s*(.*?)\s*```', text, re.S)[1])
    assert snapshot['source_commit'] == 'b251fd9ea06c0c90f48d2ac0decba0454114669d'
    static = read(STATIC) if snapshot['state'] == 'COMPLETE' else None
    if static:
        assert static['status'] == 'VERIFIED_COMPLETE_STATIC_PAIR_TRAIN_AND_DEV'
        assert static['training_commit'] == snapshot['source_commit']
        assert snapshot['completed_models'] == 2
        assert all(r['state'] == 'COMPLETE' and r['returned'] == 4320 and r['sealed_epochs'] == 9 for r in snapshot['runs'])
    else:
        assert snapshot['state'] == 'RUNNING', 'Terminal state requires a new evidence-based closeout first.'
    assert {r['model'] for r in snapshot['runs']} == {'B5', 'B6'}
    as_of = snapshot['snapshot_utc']
    with (ROOT / BASE).open(encoding='utf-8-sig', newline='') as f:
        reader = csv.DictReader(f)
        original_fields = reader.fieldnames
        matrix = list(reader)
    assert len(matrix) == 29
    innovation = read(INNOVATION) if (ROOT / INNOVATION).is_file() else None
    innovation_launch = read(INNOVATION_LAUNCH) if (ROOT / INNOVATION_LAUNCH).is_file() else None
    innovation_terminal = read(INNOVATION_TERMINAL) if (ROOT / INNOVATION_TERMINAL).is_file() else None
    if innovation_terminal:
        assert innovation_terminal['status']=='VERIFIED_B7_COMPLETE_B8_FAILED_PARTIAL_PACKAGE'
        assert innovation_terminal['training_commit']=='b1f072e45fdd17b80106a774083995c350b28f04'
    if innovation:
        assert innovation['authorized'] is False and innovation['formal_training_started'] is False
        if innovation_launch:
            assert innovation_launch['status']=='APPROVED_PACKAGE_IN_PROGRESS'
            assert innovation_launch['proposal_sha256']==innovation['proposal_sha256']
            assert innovation_launch['authorization']['approved_by_researcher'] is True
            assert innovation_launch['budget']==innovation['budget']
        for model in ('B7', 'B8'):
            row = dict(next(r for r in matrix if r['model_id'] == 'B6'))
            row.update(model_id=model, experiment_id=f'{model}__E0__s2029__f006__dynamic',
                       phase='DYNAMIC_TERRAIN_PREPARED_NOT_TRAINED', config='DOTE_W_TRAIN_PWAT_SP04_' + ('CONCAT' if model == 'B7' else 'DTFM_LAMBDA_0.1'),
                       epochs='0', global_steps='0', status='NOT_STARTED', metrics_path='NOT_AVAILABLE_NO_FORMAL_TRAINING',
                       checkpoint_reference='NOT_AVAILABLE_NO_FORMAL_TRAINING', evidence_path='evidence/b7_b8_training_proposal.json',
                       verified_at='NOT_STARTED_NO_TRAINING_VERIFICATION', notes='Ready zero-step real check; pending explicit new science and budget approval; no E9 results.',
                       authorization_status='WAITING_EXPLICIT_NEW_SCIENCE_AND_BUDGET_APPROVAL',
                       protocol_reference='B7_B8_INNOVATION_PROTOCOL.md', source_snapshot_commit='5939933dfab85de0c9d22ef4074a9166734b44b4',
                       executed_commit='NOT_STARTED_NOT_EXECUTED', source_manifest_reference='evidence/b7_b8_training_proposal.json')
            matrix.append(row)
    experiments = {r['experiment_id']: r for r in matrix}
    assert len(experiments) == 29 + (2 if innovation else 0)
    old = read(OLD)
    b2, b34, groups29 = read(B2), read(B34), read(GROUPS)
    original_configs = {r['experiment_id']: ';'.join(r['source_ids']) for r in old['experiments']}
    runs = {r['model']: r for r in snapshot['runs']}
    for r in matrix:
        for key in ('protocol_reference', 'source_manifest_reference', 'evidence_path'):
            val = r[key]
            if val.startswith('../../research_progress/'):
                r[key] = PROGRESS + val.removeprefix('../../research_progress/')
            elif val.startswith('evidence/') or val.startswith('rechecked_snapshot/') or (ROOT / READY / val).is_file():
                r[key] = READY + val
        p = r['metrics_path']
        if p.startswith('evidence/experiments.json'):
            r['metrics_path'] = PROGRESS + p
        elif p.startswith('evidence/'):
            r['metrics_path'] = READY + p
        r.update(execution_state='NOT_STARTED' if r['status']=='NOT_STARTED' else 'CLOSED_SEE_STATUS', planned_epochs='SEE_ORIGINAL_PROTOCOL',
                 train_batch_size='NOT_VERIFIED_FROM_THIS_PUBLIC_EXTRACT',
                 dev_batch_size='NOT_VERIFIED_FROM_THIS_PUBLIC_EXTRACT',
                 optimizer='SEE_ORIGINAL_CONFIG', learning_rate_rule='SEE_ORIGINAL_CONFIG',
                 input_spec='SEE_MODEL_CONFIG', parameter_count='NOT_REEXTRACTED',
                 training_config_reference=original_configs.get(r['experiment_id'], r['protocol_reference']),
                 unified_metrics='METRICS.csv', status_as_of=r['verified_at'])
        if r['comparison_population'] == 'CORE_F006_959_963':
            r.update(planned_epochs='9', train_batch_size='2', dev_batch_size='8',
                     optimizer='AdamW(lr=1e-4;betas=0.9/0.999;eps=1e-8;conv_decay=1e-4;bias_GN_decay=0;clip=5)',
                     learning_rate_rule='480_WARMUP_THEN_ORIGINAL_24000_STEP_COSINE_PREFIX_TO_4320')
            specs = {'B2': ('7x1_HIMAWARI_t_minus_10min', 4332290),
                     'B3': ('7x6_HIMAWARI', 4349090),
                     'B4': ('7x6_HIMAWARI_PLUS_13_GFS_MEE', 4355986),
                     'B5': ('B4_PLUS_1_ELEVATION_WIDTH16_SP04_RESIDUAL', 4359426),
                     'B6': ('B4_PLUS_6_STATIC_WIDTH16_SP04_RESIDUAL', 4360866),
                     'B7': ('B6_PLUS_8_DOTE_SINGLE_SP04_CONCAT', 4411058),
                     'B8': ('B6_PLUS_SAME_DOTE_SINGLE_SP04_MATCHED_DTFM', 4411058)}
            r['input_spec'], params = specs[r['model_id']]
            r['parameter_count'] = str(params)
        if r['model_id'] in runs:
            s = runs[r['model_id']]
            r.update(status='IN_PROGRESS', execution_state=s['state'], epochs=str(s['sealed_epochs']),
                     global_steps=str(s['returned']), verified_at=as_of, status_as_of=as_of,
                     evidence_path='EVIDENCE_INDEX.md#当前训练状态快照',
                     notes='DATED_METADATA_SNAPSHOT_ONLY; E9 results unavailable; B6 queue PENDING is not completed training.')
            if static:
                task = next(t for t in static['tasks'] if t['model'] == r['model_id'])
                r.update(status=task['status'], phase='STATIC_TERRAIN_FORMAL_COMPLETE',
                         metrics_path=STATIC + '#endpoint_groups/' + r['model_id'] + '/all/summary',
                         checkpoint_reference=task['endpoint_sha256'], evidence_path=STATIC,
                         verified_at=static['verified_at'], status_as_of=static['verified_at'],
                         authorization_status='CORRECTED_START_APPROVED_CONSUMED_COMPLETE_NO_RETRY',
                         notes='Nine Train/Dev epochs and E9 LAST verified; mixed single-seed terrain results; not final generalization.')
        if innovation_launch and r['model_id'] in ('B7','B8'):
            run=next(s for s in innovation_launch['models'] if s['model']==r['model_id'])
            r.update(status='IN_PROGRESS',phase='DYNAMIC_TERRAIN_FORMAL_IN_PROGRESS',execution_state=run['execution_state'],
                     epochs=str(run['sealed_train_dev_epochs']),global_steps=str(run['returned_updates']),
                     verified_at=innovation_launch['as_of'],status_as_of=innovation_launch['as_of'],
                     metrics_path='NOT_AVAILABLE_FIXED_E9_IN_PROGRESS',checkpoint_reference='NOT_AVAILABLE_FIXED_E9',
                     evidence_path=INNOVATION_LAUNCH,authorization_status='APPROVED_EXACT_PACKAGE_CONSUMED_NO_REPLAY',
                     source_snapshot_commit=innovation_launch['training_commit'],
                     executed_commit=innovation_launch['training_commit'] if run['training_started'] else 'NOT_STARTED_PENDING_SERIAL_QUEUE',
                     notes='Dated approved launch snapshot; B7 running, B8 pending serial queue; neither fixed E9 or scientific result complete.')
        if innovation_terminal and r['model_id'] in ('B7','B8'):
            task=next(s for s in innovation_terminal['tasks'] if s['model']==r['model_id'])
            complete=task['status']=='COMPLETE_TRAIN_AND_DEV_EVALUATION'
            r.update(status=task['status'],phase='DYNAMIC_TERRAIN_FORMAL_COMPLETE' if complete else 'DYNAMIC_TERRAIN_STOPPED_PARTIAL',
                     execution_state='COMPLETE' if complete else 'FAILED',epochs=str(task['sealed_train_dev_epochs']),global_steps=str(task['returned_updates']),
                     verified_at=innovation_terminal['verified_at'],status_as_of=innovation_terminal['verified_at'],
                     metrics_path=INNOVATION_TERMINAL+'#endpoint_groups/B7/all/summary' if complete else 'NOT_AVAILABLE_FIXED_E9',
                     checkpoint_reference=task['fixed_E9_sha256'] if complete else 'NOT_AVAILABLE_FIXED_E9',
                     checkpoint_selection='FIXED_EPOCH_9_LAST' if complete else 'FIXED_E9_NOT_REACHED;LATEST_SAVED_E6_2880',
                     evidence_path=INNOVATION_TERMINAL,source_manifest_reference=INNOVATION_TERMINAL,
                     authorization_status='APPROVED_CONSUMED_NO_AUTOMATIC_REPLAY',executed_commit=innovation_terminal['training_commit'],
                     notes='B7 fixed E9 verified; single-seed mixed DOTE results.' if complete else 'B8 source-path WinError121 stop; 6 sealed epochs,2942 returned, E6/2880 saved,62 unsaved; no E9 comparison or authorized recovery.')
    b8_recovery=read(B8_RECOVERY) if (ROOT/B8_RECOVERY).exists() else None
    b8_launch=read(B8_LAUNCH) if (ROOT/B8_LAUNCH).exists() else None
    b8_complete=read(B8_COMPLETE) if (ROOT/B8_COMPLETE).exists() else None
    if b8_recovery:
        assert b8_recovery['authorized'] is False
        for r in matrix:
            if r['model_id']=='B8':
                r['notes']+=' Recovery E6-to-E9 READY_WAITING_EXPLICIT_APPROVAL;1440 new attempts include62 replay; not started.'
                if b8_launch:
                    task=b8_launch['tasks'][0]
                    assert b8_launch['authorization']['approved_by_researcher'] is True and b8_launch['proposal_sha256']==b8_recovery['proposal_sha256']
                    r.update(status='IN_PROGRESS',execution_state='RUNNING',epochs=str(task['sealed_epochs']),global_steps=str(task['cumulative_B8_attempts']),
                             executed_commit=b8_launch['training_commit'],evidence_path=B8_LAUNCH,source_manifest_reference=B8_RECOVERY,
                             authorization_status='APPROVED_CONSUMED_NO_ADDITIONAL_RETRY',verified_at=b8_launch['snapshot_utc'],status_as_of=b8_launch['snapshot_utc'],
                             notes=f"Recovery approved and started; inherited E1-E6 b1f072e, E7-E9 code {b8_launch['training_commit']}; startup snapshot new returned={task['segment_returned']},effective={task['effective_updates']},cumulative attempts include prior62; not a live counter or fixed E9 completion.")
    if b8_complete:
        assert b8_complete['status']=='VERIFIED_COMPLETE_B7_B8_FIXED_E9_TRAIN_AND_DEV'
        for r in matrix:
            if r['model_id']=='B8':
                r.update(status='COMPLETE_TRAIN_AND_DEV_EVALUATION',execution_state='COMPLETE',epochs='9',global_steps='4382',
                         checkpoint_reference=b8_complete['B8_fixed_E9_sha256'],checkpoint_selection='FIXED_EPOCH_9_LAST',
                         evidence_path=B8_COMPLETE,source_manifest_reference=B8_COMPLETE,executed_commit=b8_complete['training_commit'],
                         verified_at=b8_complete['verified_at'],status_as_of=b8_complete['completed_at'],
                         notes='Nine fixed E9 Train/Dev epochs verified; effective updates4320, actual B8 attempts4382 incl62 approved replay; E1-E6 b1f072e, E7-E9 ef11531; single-seed mixed DTFM results, not an independent extra seed.')
    innovation_multi=read(INNOVATION_MULTI) if (ROOT/INNOVATION_MULTI).exists() else None
    innovation_multi_launch=read(INNOVATION_MULTI_LAUNCH) if (ROOT/INNOVATION_MULTI_LAUNCH).exists() else None
    innovation_multi_stop=read(INNOVATION_MULTI_STOP) if (ROOT/INNOVATION_MULTI_STOP).exists() else None
    innovation_multi_cause=read(INNOVATION_MULTI_CAUSE) if (ROOT/INNOVATION_MULTI_CAUSE).exists() else None
    innovation_multi_recovery=read(INNOVATION_MULTI_RECOVERY) if (ROOT/INNOVATION_MULTI_RECOVERY).exists() else None
    innovation_multi_recovery_launch=read(INNOVATION_MULTI_RECOVERY_LAUNCH) if (ROOT/INNOVATION_MULTI_RECOVERY_LAUNCH).exists() else None
    if innovation_multi:
        assert innovation_multi['authorized'] is False and innovation_multi['status']=='READY_WAITING_EXPLICIT_FOUR_MODEL_TRAINING_APPROVAL'
        for task in innovation_multi['tasks']:
            kind,seed=task['model'],task['seed'];r=dict(next(x for x in matrix if x['model_id']==kind))
            r.update(seed=str(seed),experiment_id=f'{kind}__E0__s{seed}__f006__dynamic',phase='DYNAMIC_MULTI_SEED_PREPARED_NOT_TRAINED',
                     config=json.dumps(innovation_multi['training_configs'][f'{kind}_s{seed}']['config'],sort_keys=True),epochs='0',global_steps='0',
                     status='NOT_STARTED',execution_state='NOT_STARTED',metrics_path='NOT_AVAILABLE_NO_FORMAL_TRAINING',
                     checkpoint_reference='NOT_AVAILABLE_NO_FORMAL_TRAINING',checkpoint_selection='FIXED_EPOCH_9_LAST_PLANNED',
                     verified_at='NOT_STARTED_NO_TRAINING_VERIFICATION',status_as_of='NOT_STARTED_NO_APPROVAL',
                     authorization_status='WAITING_EXPLICIT_FOUR_MODEL_PACKAGE_APPROVAL',executed_commit='NOT_STARTED_NOT_EXECUTED',
                     evidence_path=INNOVATION_MULTI,source_manifest_reference=INNOVATION_MULTI,source_snapshot_commit=innovation_multi['execution_code_commit'],
                     training_config_reference=INNOVATION_MULTI+f'#/training_configs/{kind}_s{seed}',
                     notes='New independent initialization seed planned; no formal optimizer updates, E9 weight or Dev metric. Seed2029 including62 historical replay remains separate inherited evidence.')
            if innovation_multi_launch:
                assert innovation_multi_launch['training_commit']==innovation_multi['execution_code_commit'] and innovation_multi_launch['proposal_sha256']==innovation_multi['proposal_sha256']
                run=next(x for x in innovation_multi_launch['models'] if (x['model'],x['seed'])==(kind,seed))
                r.update(phase='DYNAMIC_MULTI_SEED_APPROVED_PACKAGE_IN_PROGRESS',status=run['status'],execution_state=run['execution_state'],
                         epochs=str(run['sealed_train_dev_epochs']),global_steps=str(run['returned_updates']),
                         verified_at=innovation_multi_launch['as_of'],status_as_of=innovation_multi_launch['as_of'],
                         authorization_status='APPROVED_EXACT_PACKAGE_CONSUMED_ONCE',evidence_path=INNOVATION_MULTI_LAUNCH,
                         executed_commit=innovation_multi_launch['training_commit'] if run['training_started'] else 'NOT_STARTED_PENDING_SERIAL_QUEUE',
                         metrics_path='NOT_AVAILABLE_NO_FIXED_E9_RESULTS',checkpoint_reference='NOT_AVAILABLE_NO_FIXED_E9_RESULTS',
                         notes='Approved startup snapshot only; queued tasks remain NOT_STARTED, no E9 metrics. Frozen controller serially dispatches four tasks; zero replay/extra retry. Seed2029 including62 historical replay remains inherited.')
            if innovation_multi_stop:
                assert innovation_multi_stop['training_commit']==innovation_multi['execution_code_commit']
                run=next(x for x in innovation_multi_stop['models'] if (x['model'],x['seed'])==(kind,seed))
                r.update(phase='DYNAMIC_MULTI_SEED_STOPPED_WITHOUT_TERMINAL_RECEIPT',status=run['status'],execution_state=run['execution_state'],
                         epochs=str(run['sealed_train_dev_epochs']),global_steps=str(run['returned_updates']),
                         verified_at=innovation_multi_stop['observed_at'],status_as_of=innovation_multi_stop['observed_at'],evidence_path=INNOVATION_MULTI_STOP,
                         notes='Controller and workers gone, no terminal receipt. B7/2030:3321 RETURNED, E6/2880 saved,441 unsaved. Remaining three NOT_STARTED. Original ledgers/journals preserved; monitor recovered private copies only. No restart/replay authorized, no fixed E9.')
            if innovation_multi_recovery_launch:
                ml=innovation_multi_recovery_launch;run=next(x for x in ml['models'] if (x['model'],x['seed'])==(kind,seed))
                r.update(phase='DYNAMIC_MULTI_SEED_APPROVED_E6_RECOVERY_IN_PROGRESS',status=run['status'],execution_state=run['execution_state'],
                         epochs=str(run['sealed_train_dev_epochs']),global_steps=str(run['returned_updates']),verified_at=ml['as_of'],status_as_of=ml['as_of'],
                         evidence_path=INNOVATION_MULTI_RECOVERY_LAUNCH,authorization_status='APPROVED_EXACT_E6_441_RECOVERY_CONSUMED_ONCE',
                         executed_commit=ml['training_commit'] if run['training_started'] else 'NOT_STARTED_PENDING_SERIAL_QUEUE',source_snapshot_commit=ml['training_commit'],
                         training_config_reference=INNOVATION_MULTI_RECOVERY+f'#/training_configs/{kind}_s{seed}',
                         notes=f"Startup snapshot only; effective_updates={run['effective_updates']},new_segment_returned={run['new_segment_returned']},replay_returned={run['replayed_updates']}. B7 E1-E6 inherited56aae5b; E7-E9 recoverye81c6e1. Original3321 attempts incl441 unsaved retained. No new fixedE9 results; queued tasks not yet started.")
            matrix.append(r);experiments[r['experiment_id']]=r
        assert len(matrix)==len(experiments)==35
    matrix_fields = original_fields + [k for k in matrix[0] if k not in original_fields]
    write_csv('EXPERIMENT_MATRIX.csv', matrix_fields, matrix)
    rows, seen = [], {}

    def add(eid, obj, source, pointer, *, group='all', ids='', epoch='ENDPOINT', kind='RAW_ENDPOINT', split='2024_Development'):
        exp = experiments[eid]
        for sub, value in leaves(obj):
            # SHA, paths and descriptive strings are provenance, not numeric metrics.
            if isinstance(value, str) and not value.startswith(('NOT_', 'UNDEFINED')):
                continue
            metric = sub.lstrip('/')
            key = (eid, str(epoch), split, group, metric)
            if key in seen:
                previous = seen[key]
                if isinstance(value, (int, float)) and not isinstance(value, bool):
                    assert math.isclose(float(previous['value']), value, rel_tol=1e-12, abs_tol=1e-12), (eid, metric)
                continue
            numeric = isinstance(value, (int, float)) and not isinstance(value, bool)
            if numeric:
                assert math.isfinite(value)
            row = dict.fromkeys(FIELDS, '')
            row.update(record_type=kind if numeric else 'MISSING_OR_NULL', experiment_id=eid,
                       model_id=exp['model_id'], seed=exp['seed'], loss_arm=exp['loss_arm'], epoch=str(epoch),
                       split=split, comparison_population=exp['comparison_population'], group=group,
                       group_ids_sha256=ids, metric=metric, value=repr(value) if numeric else '',
                       status='RECORDED' if numeric else ('NULL_AS_RECORDED' if value is None else str(value)),
                       unit=unit(metric), source_file=source, source_pointer=pointer + sub,
                       executed_commit=exp['executed_commit'], evaluation_script=exp['evaluation_script'],
                       checkpoint_sha256=exp['checkpoint_reference'] if epoch == 'ENDPOINT' else '')
            if b8_launch and exp['model_id']=='B8' and source!=B8_COMPLETE:
                # All currently exported B8 metrics still come from the old E1-E6.
                row['executed_commit']=innovation_terminal['training_commit']
            rows.append(row)
            seen[key] = row

    for i, exp in enumerate(old['experiments']):
        add(exp['experiment_id'], exp['metrics'], OLD, f'/experiments/{i}/metrics')
    for model, groups in groups29.items():
        for group, obj in groups.items():
            add(f'{model}__E0__s2029__f006', obj['summary'], GROUPS, f'/{model}/{group}/summary', group=group, ids=obj.get('ids_sha256', ''))
    for model, groups in b2['endpoint_groups'].items():
        for group, obj in groups.items():
            eid = f'{model}__E0__s2029__f006'
            add(eid, obj['summary'], B2, f'/endpoint_groups/{model}/{group}/summary', group=group, ids=obj['ids_sha'])
            add(eid, {'q32_coverage': obj['summary']['coverage'][-1]}, B2, f'/endpoint_groups/{model}/{group}/summary', group=group, ids=obj['ids_sha'])
            # The alias points at the actual numeric source, not an invented JSON field.
            alias = seen[(eid, 'ENDPOINT', '2024_Development', group, 'q32_coverage')]
            alias['source_file'] = B2
            alias['source_pointer'] = f'/endpoint_groups/{model}/{group}/summary/coverage/31'
    add('B2__E0__s2029__f006', b2['B2_tail_strata'], B2, '/B2_tail_strata', group='tail_diagnostics')
    add('B2__E0__s2029__f006', b2['epochs'][-1]['development'], B2, '/epochs/8/development')
    for i, item in enumerate(b2['epochs']):
        add('B2__E0__s2029__f006', item['development'], B2, f'/epochs/{i}/development', epoch=item['epoch'], kind='RAW_EPOCH')
        add('B2__E0__s2029__f006', item['train'], B2, f'/epochs/{i}/train', epoch=item['epoch'], kind='RAW_EPOCH', split='2023_Train')
    for seed, models in read(FULL)['groups'].items():
        for model, groups in models.items():
            for group, obj in groups.items():
                add(f'{model}__E0__s{seed}__f006', obj['summary'], FULL,
                    f'/groups/{seed}/{model}/{group}/summary', group=group, ids=obj['ids_sha256'])
    for seed, models in b34['endpoint_groups'].items():
        for model, groups in models.items():
            eid = f'{model}__E0__s{seed}__f006'
            for group, obj in groups.items():
                add(eid, obj, B34, f'/endpoint_groups/{seed}/{model}/{group}', group=group, ids=obj['ids_sha256'])
            add(eid, b34['summary']['endpoints'][seed][model], B34, f'/summary/endpoints/{seed}/{model}')
            add(eid, b34['tail_diagnostics'][seed][model], B34, f'/tail_diagnostics/{seed}/{model}', group='tail_diagnostics')
    if static:
        for model, groups in static['endpoint_groups'].items():
            eid = f'{model}__E0__s2029__f006' + ('__static' if model in ('B5', 'B6') else '')
            for group, obj in groups.items():
                pointer = f'/endpoint_groups/{model}/{group}/summary'
                add(eid, obj['summary'], STATIC, pointer, group=group, ids=obj['ids_sha256'])
                if (eid, 'ENDPOINT', '2024_Development', group, 'q32_coverage') not in seen:
                    add(eid, {'q32_coverage': obj['summary']['coverage'][-1]}, STATIC, pointer,
                        group=group, ids=obj['ids_sha256'])
                    seen[(eid, 'ENDPOINT', '2024_Development', group, 'q32_coverage')]['source_pointer'] = pointer + '/coverage/31'
            if model in static['tail_diagnostics']:
                add(eid, static['tail_diagnostics'][model], STATIC, f'/tail_diagnostics/{model}', group='tail_diagnostics')
        for i, item in enumerate(static['epochs']):
            eid = f"{item['model']}__E0__s2029__f006__static"
            add(eid, item['development'], STATIC, f'/epochs/{i}/development', epoch=item['epoch'], kind='RAW_EPOCH')
            add(eid, item['train'], STATIC, f'/epochs/{i}/train', epoch=item['epoch'], kind='RAW_EPOCH', split='2023_Train')
    if innovation_terminal:
        for model, groups in innovation_terminal['endpoint_groups'].items():
            if model!='B7':
                continue
            eid='B7__E0__s2029__f006__dynamic'
            for group,obj in groups.items():
                pointer=f'/endpoint_groups/{model}/{group}/summary'
                add(eid,obj['summary'],INNOVATION_TERMINAL,pointer,group=group,ids=obj['ids_sha256'])
                add(eid,{'q32_coverage':obj['summary']['coverage'][-1]},INNOVATION_TERMINAL,pointer,group=group,ids=obj['ids_sha256'])
                seen[(eid,'ENDPOINT','2024_Development',group,'q32_coverage')]['source_pointer']=pointer+'/coverage/31'
            add(eid,innovation_terminal['tail_diagnostics']['B7'],INNOVATION_TERMINAL,'/tail_diagnostics/B7',group='tail_diagnostics')
        for i,item in enumerate(innovation_terminal['epochs']):
            eid=f"{item['model']}__E0__s2029__f006__dynamic"
            add(eid,item['development'],INNOVATION_TERMINAL,f'/epochs/{i}/development',epoch=item['epoch'],kind='RAW_EPOCH')
            add(eid,item['train'],INNOVATION_TERMINAL,f'/epochs/{i}/train',epoch=item['epoch'],kind='RAW_EPOCH',split='2023_Train')
            add(eid,item['elevation_diagnostics'],INNOVATION_TERMINAL,f'/epochs/{i}/elevation_diagnostics',epoch=item['epoch'],kind='RAW_EPOCH',group='elevation_diagnostics')
    # Existing epoch CSV is inherited verbatim numerically; no historical receipt audit.
    if b8_complete:
        eid='B8__E0__s2029__f006__dynamic'
        for group,obj in b8_complete['endpoint_groups']['B8'].items():
            pointer=f'/endpoint_groups/B8/{group}/summary'
            add(eid,obj['summary'],B8_COMPLETE,pointer,group=group,ids=obj['ids_sha256'])
            add(eid,{'q32_coverage':obj['summary']['coverage'][-1]},B8_COMPLETE,pointer,group=group,ids=obj['ids_sha256'])
            seen[(eid,'ENDPOINT','2024_Development',group,'q32_coverage')]['source_pointer']=pointer+'/coverage/31'
        add(eid,b8_complete['summary']['values']['B8'],B8_COMPLETE,'/summary/values/B8')
        add(eid,b8_complete['tail_diagnostics']['B8'],B8_COMPLETE,'/tail_diagnostics/B8',group='tail_diagnostics')
        for i,item in enumerate(b8_complete['epochs']):
            add(eid,item['development'],B8_COMPLETE,f'/epochs/{i}/development',epoch=item['epoch'],kind='RAW_EPOCH')
            add(eid,item['train'],B8_COMPLETE,f'/epochs/{i}/train',epoch=item['epoch'],kind='RAW_EPOCH',split='2023_Train')
            add(eid,item['elevation_diagnostics'],B8_COMPLETE,f'/epochs/{i}/elevation_diagnostics',epoch=item['epoch'],kind='RAW_EPOCH',group='elevation_diagnostics')
    epoch_source = PROGRESS + 'epoch_metrics.csv'
    with (ROOT / epoch_source).open(encoding='utf-8-sig', newline='') as f:
        for i, item in enumerate(csv.DictReader(f)):
            for metric, value in item.items():
                if metric in ('experiment_id', 'epoch'):
                    continue
                obj = {metric: float(value)} if value not in ('NOT_AVAILABLE', '') else {metric: 'NOT_AVAILABLE'}
                split = '2023_Train' if metric == 'training_loss' else '2024_Development'
                add(item['experiment_id'], obj, epoch_source, f'/row/{i}', epoch=item['epoch'], kind='RAW_EPOCH', split=split)
    for r in matrix:
        if not any(x['experiment_id'] == r['experiment_id'] and x['epoch']=='ENDPOINT' for x in rows):
            add(r['experiment_id'], {'endpoint_metrics': 'NOT_AVAILABLE'}, 'EXPERIMENT_MATRIX.csv', '/experiment_id/' + r['experiment_id'])
    raw_rows = list(rows)
    by_exp = defaultdict(dict)
    for row in rows:
        if row['epoch'] == 'ENDPOINT' and row['status'] == 'RECORDED':
            by_exp[row['experiment_id']][(row['group'], row['metric'])] = row
    pairs = [(f'B1_V2__{arm}__s{seed}', f'B0_MATCHED_V2__{arm}__s{seed}', 'B1_MINUS_B0')
             for seed in (2026, 2027) for arm in ('E0', 'E1', 'E2')]
    pairs += [('B2__E0__s2029__f006', 'B3__E0__s2029__f006', 'B2_MINUS_B3')]
    pairs += [(f'B4__E0__s{seed}__f006', f'B3__E0__s{seed}__f006', 'B4_MINUS_B3') for seed in (2029, 2030, 2031)]
    if static:
        pairs += [(f'{target}__E0__s2029__f006__static',
                   f'{base}__E0__s2029__f006' + ('__static' if base == 'B5' else ''),
                   target + '_MINUS_' + base) for target, base in (('B5', 'B4'), ('B6', 'B4'), ('B6', 'B5'))]
    if innovation_terminal:
        pairs += [('B7__E0__s2029__f006__dynamic',f'{base}__E0__s2029__f006'+('__static' if base in ('B5','B6') else ''),'B7_MINUS_'+base) for base in ('B4','B5','B6')]
    if b8_complete:
        pairs += [('B8__E0__s2029__f006__dynamic',f'{base}__E0__s2029__f006'+('__static' if base in ('B5','B6') else '__dynamic' if base=='B7' else ''),'B8_MINUS_'+base) for base in ('B4','B5','B6','B7')]
    aggregates = defaultdict(list)
    for target, base, comparison in pairs:
        for key in sorted(by_exp[target].keys() & by_exp[base].keys()):
            group, metric = key
            eligible = metric in HEADLINE or metric.startswith('coverage/') or metric.endswith('/conditional_pinball') or metric.endswith('/q32_coverage')
            if comparison=='B8_MINUS_B7' and metric.endswith('/brier'):eligible=True
            if not eligible:
                continue
            t, b = by_exp[target][key], by_exp[base][key]
            assert experiments[target]['train_scenes'] == experiments[base]['train_scenes']
            assert experiments[target]['dev_scenes'] == experiments[base]['dev_scenes']
            if t['group_ids_sha256'] and b['group_ids_sha256']:
                assert t['group_ids_sha256'] == b['group_ids_sha256']
            delta = float(t['value']) - float(b['value'])
            row = dict(t, record_type='PAIRED_DELTA', value=repr(delta), reference_value=b['value'],
                       comparison=comparison, reference_experiment_id=base,
                       reference_source_file=b['source_file'], reference_source_pointer=b['source_pointer'],
                       improvement_direction=favorable(metric), n_seeds='1', status='DESCRIPTIVE_PAIRED')
            rows.append(row)
            aggregates[(comparison, t['loss_arm'], group, metric)].append(row)
    for (comparison, arm, group, metric), values in sorted(aggregates.items()):
        if comparison == 'B2_MINUS_B3' or len(values) < 2:
            continue
        nums = [float(r['value']) for r in values]
        seeds = ';'.join(r['seed'] for r in values)
        for kind, value in [('PAIRED_MEAN', statistics.mean(nums)), ('PAIRED_SAMPLE_SD', statistics.stdev(nums))]:
            row = dict(values[0], record_type=kind, experiment_id='AGGREGATE_' + comparison + '_' + arm,
                       seed=seeds, value=repr(value), reference_value='', n_seeds=str(len(values)),
                       reference_experiment_id=';'.join(r['reference_experiment_id'] for r in values),
                       source_file='METRICS.csv', source_pointer='PAIRED_DELTA:' + comparison + ':' + arm + ':' + group + ':' + metric,
                       reference_source_file='', reference_source_pointer='', executed_commit='SEE_CONSTITUENT_ROWS', checkpoint_sha256='')
            rows.append(row)
    # Check this export's seven headline differences against the existing closeout,
    # not the original training or the 126 inherited epoch receipts.
    for metric, result in b34['summary']['metrics'].items():
        vals = aggregates[('B4_MINUS_B3', 'E0', 'all', metric)]
        assert len(vals) == 3
        assert math.isclose(statistics.mean(float(r['value']) for r in vals), result['mean'], abs_tol=1e-15)
        assert math.isclose(statistics.stdev(float(r['value']) for r in vals), result['sample_sd'], abs_tol=1e-15)
    if static:
        for comparison, differences in static['summary']['differences'].items():
            for metric, expected in differences.items():
                actual = aggregates[(comparison.upper(), 'E0', 'all', metric)]
                assert len(actual) == 1 and math.isclose(float(actual[0]['value']), expected, abs_tol=1e-15)
    if innovation_terminal:
        for comparison,differences in innovation_terminal['summary']['differences'].items():
            for metric,expected in differences.items():
                actual=aggregates[(comparison.upper(),'E0','all',metric)]
                assert len(actual)==1 and math.isclose(float(actual[0]['value']),expected,abs_tol=1e-15)
    if b8_complete:
        for comparison,differences in b8_complete['summary']['differences'].items():
            for metric,expected in differences.items():
                actual=aggregates[(comparison.upper(),'E0','all',metric)]
                assert len(actual)==1 and math.isclose(float(actual[0]['value']),expected,abs_tol=1e-15)
    write_csv('METRICS.csv', FIELDS, rows)
    counts = Counter(r['record_type'] for r in rows)
    summary_table = '\n'.join(f"|{metric}|{data['B4_minus_B3_by_seed']['2029']:.12g}|{data['B4_minus_B3_by_seed']['2030']:.12g}|{data['B4_minus_B3_by_seed']['2031']:.12g}|{data['mean']:.12g}|{data['sample_sd']:.12g}|" for metric, data in b34['summary']['metrics'].items())
    phase_status = 'COMPLETE_TRAIN_AND_DEV_EVALUATION' if static else 'IN_PROGRESS'
    status_table = '\n'.join(f"|{r['model']}|2029|{phase_status}|{r['state']}|{r['returned']}|{r['sealed_epochs']}|" for r in snapshot['runs'])
    static_stage = ('|B5/B6|seed2029/E0/f006各九轮Train/Dev、4,320更新、固定E9权重身份与B4公平配对均完成|仅单seed；总体收益混合、q32和强雨仍有退化、DEM发布链未验证|训练/评价完成；探索性地形消融COMPLETE_WITH_LIMITATIONS|' if static else
                    '|B5/B6|真实地形准备、冻结方案、明确纠正启动批准；当前串行执行中|两模型各九轮完整Train/Dev、最终权重身份和公平配对尚未齐备|IN_PROGRESS，未通过结果验收|')
    static_text = ''
    innovation_text = ''
    if innovation:
        innovation_text = f'''\n## B7/B8核心创新：{'已获批准，正式训练IN_PROGRESS' if innovation_launch else '准备通过，正式训练NOT_STARTED'}

模型代码、DOTE原物理变量接入、单SP04尺度的B7 concat/B8 DTFM匹配活跃参数对照、13项新增及2项受影响旧入口检查、真实Train2/Dev1零更新检查已完成。初始输出与B6逐位相同、梯度有限、公共完整B6初始化保持；这些都是准备证据，不是科研训练结果。

{'研究者已集中明确批准' if innovation_launch else '待研究者集中批准'}：M采用windward_W、既有Train正PWAT均值31.85768219039871 kg/m²、1m/s显式尺度、width16/SP04单尺度、λ=0.1、上述配对关系及额外海拔诊断、两模型新预算。完整协议与反例边界见[核心创新协议]({READY}B7_B8_INNOVATION_PROTOCOL.md)，规范化机器提案SHA `{innovation['proposal_sha256']}`。旧B0–B6结果直接继承，不把其混合结果当工程失败。

{f"已单次启动的冻结执行提交为`{innovation_launch['training_commit']}`；[获批启动收据]({INNOVATION_LAUNCH})时点`{innovation_launch['as_of']}`记录B7 RUNNING、B8 PENDING，批准已消费。原提案authorized=false是准备时点，文件原字节不改写，实际批准见新收据。正式包8,640更新、955,143,907,680字节/285,626次、12小时；零重放/额外重试。" if innovation_launch else ''}

尚无B7/B8固定E9、完整Dev科研终点或创新有效性结论；CSV保留缺失状态，不把部分训练或少量未训练模型的前向/E0值充当完成。2025冻结；{'B8仅由同一控制器在B7完整封口后串行启动，不额外询问或重启失败任务。' if innovation_launch else '新增训练必须取得该新提案及准确代码提交的明确批准。'}
'''
    if static:
        v, d = static['summary']['values'], static['summary']['differences']
        table = '\n'.join(f"|{k}|{v['B4'][k]:.12g}|{v['B5'][k]:.12g}|{v['B6'][k]:.12g}|{d['B5_minus_B4'][k]:.12g}|{d['B6_minus_B4'][k]:.12g}|{d['B6_minus_B5'][k]:.12g}|" for k in HEADLINE)
        rain = []
        lower = .1
        for i, base in enumerate(static['endpoint_groups']['B4']['all']['summary']['rain_strata']):
            a = static['endpoint_groups']['B5']['all']['summary']['rain_strata'][i]['conditional_pinball']
            b = static['endpoint_groups']['B6']['all']['summary']['rain_strata'][i]['conditional_pinball']
            rain.append(f"|({lower},{base['upper'] if base['upper'] is not None else '∞'}]|{base['n']}|{base['conditional_pinball']:.12g}|{a:.12g}|{b:.12g}|{a-base['conditional_pinball']:.12g}|{b-base['conditional_pinball']:.12g}|")
            lower = base['upper']
        static_text = f'''\n### seed2029固定E9地形配对：已完成

|指标|B4|B5|B6|B5−B4|B6−B4|B6−B5|
|---|---|---|---|---|---|---|
{table}

B5在五项主指标中仅AUROC略有改善，Brier、AP、条件Pinball及q32覆盖均退化。B6相对B4的Brier和AUROC改善，AP下降、条件Pinball上升5.766171316340385e-06，q32覆盖更低；B6相对B5的前四项改善而q32进一步退化。不能写成地形全面有效、等效性通过或统计显著。

B4/B5/B6参数量分别4,355,986/4,359,426/4,360,866。B6−B5除了输入变量还改变适配器参数量，且静态输入同时携带固定空间信息；没有等参数或空间替代对照，不能把差异唯一归因于某个物理因子。Brier与AUROC/AP衡量的误差/排序口径不同，观察到方向分化应并列记录，不从单一指标推导整体获益。

|真实雨强mm/h|有雨像元时次|B4条件Pinball|B5|B6|B5−B4|B6−B4|
|---|---|---|---|---|---|---|
{chr(10).join(rain)}

B5在20–30及30–50 mm/h两层略改善，必须与其总体退化一并保留；B6在这两层分别退化+0.012595453497827092、+0.014700797800703214。B6在1–20 mm/h同样退化，0.1–1 mm/h改善抵消了部分总体损失。按同一总体有雨人口407,820加权，不把分层均值再作不等权平均。

B4/B5/B6的q32覆盖约93.6227%/93.4599%/93.1472%，较名义98.4375%分别欠4.8148/4.9776/5.2903个百分点。B5在两强雨层covered为80/564、9/147，B6为66/564、3/147；B4对应层covered未保存，不能由总体反推。真实雨强条件化分层不直接要求各层达到名义覆盖。B5与B6总体q32均比B4更差，不能用B5强雨场景子集覆盖小幅改善掩盖它。

四UTC：B5的Brier全部退化、AP全部下降，06UTC AUROC也下降；B6的Brier/AUROC四时次均改善，但00/12UTC AP下降，12/18UTC条件Pinball退化；两模型q32四时次均下降。强雨场景子集（scene_max_ge20）中B6仍有AP和条件Pinball退化。全部分组原值和配对差值保存在CSV。

证据：[本轮18轮、账本、预算、E9身份与完整分组]({STATIC})。这是单seed、同一开发年的探索性消融；不追加seed、E0变体或训练轮数，不据此决定解封2025。
'''
    innovation_analysis_text=innovation_text
    innovation_stage_rows=f"|B7/B8|{'已获明确批准并启动B7，B8同控制器串行等待' if innovation_launch else ('完整新模型、原物理DOTE接入、等活跃参数单尺度对照、必要及真实零更新检查通过' if innovation else '保留既有候选实现与工程证据')}|固定E9和完整Dev科研终点未齐备；{'批准已消费、零重放/额外重试' if innovation_launch else ('科学选择及精确预算待新批准' if innovation else '创新有效性未核实')}|{'IN_PROGRESS（B7运行，B8排队）' if innovation_launch else 'NOT_STARTED（正式训练未启动）'}|"
    if innovation_terminal:
        t=innovation_terminal;cost=t['budget_closure'];v=t['summary']['values'];delta=t['summary']['differences']
        innovation_stage_rows='|B7|seed2029九轮Train/2024 Dev、4,320更新和固定E9身份已核验|单seed；相对B6收益混合、强雨Pinball退化；机制/最终泛化未证明|COMPLETE_TRAIN_AND_DEV_EVALUATION；探索性结论带局限|\n|B8|六轮Train/Dev已封口，共2,942次RETURNED|第七轮源路径解析WinError121停止；最新E6/2880，62更新未保存，无固定E9|FAILED_INCOMPLETE_NO_FIXED_E9，DTFM对照未验收|'
        innovation_text=f'''\n## B7完成、B8停止：整包未完成

停止于`{t['package_stopped_at']}`，本次核查`{t['verified_at']}`。B8第七轮Train加载卫星数据时，`Path.resolve(strict=True)`抛出OSError WinError121（信号灯超时）；底层存储/连接原因NOT_VERIFIED，未重新探测或读取源。不是模型指标触发的停止。

B7九轮完整，E9 SHA `{t['tasks'][0]['fixed_E9_sha256']}`。B8六轮完整、2,942更新已RETURNED且无不确定优化器INTENT；最后E6/2,880已保存，62次更新未进检查点，E7–E9 Dev和E9权重不存在。**不得以E6替代E9，不得自动恢复。** 原批准零重放/额外重试，剩余上限不是恢复授权。

实际消耗7,262更新、799,430,612,283源字节/239,130次，均未超上限；失败pass和原件保留。B7可与B4/B5/B6作同人口固定E9比较，B8的固定终点比较及B7/B8整体验收仍NOT_VERIFIED。[完整新核查收据]({INNOVATION_TERMINAL})；[全部正负结果](SCIENTIFIC_ANALYSIS.md)。2025冻结，无新训练、推理或原始读取。
'''
        main_table='\n'.join(f"|{k}|{v['B4'][k]:.12g}|{v['B5'][k]:.12g}|{v['B6'][k]:.12g}|{v['B7'][k]:.12g}|NOT_AVAILABLE|" for k in HEADLINE)
        delta_table='\n'.join(f"|{k}|{delta['B7_minus_B4'][k]:.12g}|{delta['B7_minus_B5'][k]:.12g}|{delta['B7_minus_B6'][k]:.12g}|" for k in HEADLINE)
        rain_table=[];lo=.1
        for i,row in enumerate(t['endpoint_groups']['B7']['all']['summary']['rain_strata']):
            b4=t['endpoint_groups']['B4']['all']['summary']['rain_strata'][i]['conditional_pinball'];b6=t['endpoint_groups']['B6']['all']['summary']['rain_strata'][i]['conditional_pinball']
            rain_table.append(f"|({lo},{row['upper'] if row['upper'] is not None else '∞'}]|{row['n']}|{b4:.12g}|{b6:.12g}|{row['conditional_pinball']:.12g}|{row['conditional_pinball']-b6:.12g}|");lo=row['upper']
        time_table=[]
        for group,item in t['endpoint_groups']['B7'].items():
            if group=='all':continue
            s=item['summary'];b=t['endpoint_groups']['B6'][group]['summary']
            time_table.append(f"|{group}|{s['brier']-b['brier']:.12g}|{s['auroc']-b['auroc']:.12g}|{s['average_precision']-b['average_precision']:.12g}|{s['conditional_pinball']-b['conditional_pinball']:.12g}|{s['coverage'][-1]-b['coverage'][-1]:.12g}|")
        altitude=t['tail_diagnostics']['B7']['elevation_diagnostics']['bins']
        elevation_table='\n'.join(f"|{name}|{s['n_valid']}|{s['n_rain']}|{s['brier']:.12g}|{s['conditional_pinball']:.12g}|{s['q32_coverage']:.12g}|" for name,s in altitude.items())
        innovation_analysis_text=innovation_text+f'''\n### B4–B8固定E9总体结果

全部为相同959/963、seed2029/E0/f006、固定E9。B8缺少该终点，不能用E6与E9横比。表格便读舍入，CSV保留完整原值和差值。

|指标|B4|B5|B6|B7|B8固定E9|
|---|---|---|---|---|---|
{main_table}

|指标|B7−B4|B7−B5|B7−B6|
|---|---|---|---|
{delta_table}

B7相对B6的AUROC、AP和欠覆盖状态下q32方向改善，但Brier和条件Pinball退化；相对B4的Brier/AUROC/AP改善，条件Pinball和q32退化。DOTE及新增融合路径的整体收益混合，不能写成全面优于静态地形或证明地形抬升。参数额外增加50,192，仍不能把全部差异唯一归因于某个物理因子。B8因源I/O停止，不是DTFM被科学否定；其与concat的有效固定终点比较仍未获得。

### 强雨反例与上尾覆盖

|真实雨强mm/h|有雨像元时次|B4条件Pinball|B6|B7|B7−B6|
|---|---|---|---|---|---|
{chr(10).join(rain_table)}

B7对B6仅0.1–1及1–5 mm/h两层改善，其余5 mm/h以上各层退化；20–30和30–50分别+0.01650159247064409、+0.017778099416098758。对B4这两层分别+0.02909704596847118、+0.03247889721680197。>50仅6个像元时次，误差也上升；不能当独立暴雨事件数或稳定极端能力结论。

B7总体q32=0.9348241871413859，较98.4375%名义水平欠4.955081285861407个百分点。对B6改善约0.3351969005934041个百分点，仍不通过校准；对B4反而下降约0.14025795694178056个百分点。B7的20–30、30–50、>50 covered分别38/564、1/147、0/6。总体欠覆盖方向改善不能掩盖强雨尾部不足；按真实雨强分层不能要求各层直接达到同一名义覆盖。

### UTC与强雨场景：B7−B6

|既定分组|Brier差值|AUROC差值|AP差值|条件Pinball差值|q32覆盖差值|
|---|---|---|---|---|---|
{chr(10).join(time_table)}

B7对B6四UTC的Brier和条件Pinball均退化；06 UTC的AUROC/AP退化，12 UTC AP也退化。相对B4，四UTC Brier改善，但06 UTC AUROC/AP下降，00/12 UTC AP下降。强雨场景子集对B6仍有Brier/Pinball退化。以上均是重叠的既定描述性分组，不选择有利时次。

### B7海拔充分量（无历史基线配对）

|预设海拔区间|有效像元时次|有雨像元时次|Brier|条件Pinball|q32覆盖|
|---|---|---|---|---|---|
{elevation_table}

区间为<1000、[1000,2000)、≥2000米，仅补充同次前向统计，分母相加已与总体核对。B4/B5/B6没有同口径海拔充分量；B8 E6不能代替E9，所以没有DTFM海拔配对结论。分层AUROC/AP没有计算，NOT_COMPUTED不补零；不能用海拔与误差相关性证明地形因果。

### 失败和科研边界

30个完整气象读取账本及1个失败时部分账本、2个静态账本已核对。B8第七轮已完成计量1,108文件/3,477,251,607字节，另有1个SourceCache任务UNCERTAIN_NO_RETRY；文件I/O账本没有未完成字节保留，优化器账本无不确定INTENT。保留的是一次源路径失败，未验证该源当前可访问性或底层连接原因。两份最新实际权重（B7 E9、B8 E6）仅读取字节SHA，未反序列化或推理。

既有整包上限8,640更新、955,143,907,680字节/285,626次，实际7,262更新、799,430,612,283字节/239,130次；时间mtime代理26,715.136秒，少于12小时，不是GPU计费时间。失败不是额度耗尽。62个未保存更新意味着未来从E6恢复将涉及必要重放；原replay=0及未消费的数额均不授予恢复许可，本次不提出或执行新训练。

只保留单seed同一Dev年的探索性结论，不声称统计显著性、独立年份泛化或真实地形抬升机制；2025仍冻结。原B3/B4三seed、B5/B6全部混合及负面结果不变。B8 E1–E6只作为不完整轨迹保留在CSV（epoch=1–6），不选BEST、不生成B8 ENDPOINT数值或B8−B7差值。
'''
    recovery_text=''
    if b8_recovery:
        recovery_text=f'''\n## B8限额恢复准备：待新批准，未启动

仅对原WinError121源做五项有界操作，合计读取4,096字节/1文件；路径、大小及4KiB读取当前通过，卷报告本地exFAT，原故障原因仍NOT_VERIFIED。[原始诊断]({B8_DIAGNOSTIC})保留；其BLOCKED汇总来自大小写敏感的文件名判断，same_path=true及五项PASS支持Windows大小写等价解释，[提案]({B8_RECOVERY})明确修正且未重读。

冻结提案SHA `{b8_recovery['proposal_sha256']}`：仅B8/2029从E6/2880继续E7–E9，新执行1,440更新含62次重放；训练源159,190,547,004字节/47,604次，另静态包312,828字节/1次，新增合计159,190,859,832字节/47,605次；4KiB诊断已单列，后续额外诊断载荷0。最长8,316秒（2小时18分36秒），至少24GiB空闲，真实E6重哈希1次/反序列化1次，额外重试0。B8累计4,382尝试、B7/B8累计8,702；含已做诊断累计源958,621,476,211字节/286,736次。

恢复沿用原模型、E0/f006、959/963、全部RNG/AdamW/原24,000步轨迹及固定E9；代码与[针对性检查]({B8_CHECKS})已就绪，B7及E1–E6不重训。原停止状态及62次未保存账本保留；这不是新独立seed。研究者尚未批准本恢复包，不能填写批准或启动；2025、main不变。
'''
        innovation_text=innovation_text.replace('本次核查','停止收口核查')
        innovation_text=innovation_text.replace('2025冻结，无新训练、推理或原始读取。','该次停止收口无新训练、推理或原始读取；后续恢复源诊断单列，2025冻结。')
        innovation_text+=recovery_text
        innovation_analysis_text+='\n'+recovery_text
        if b8_launch:
            task=b8_launch['tasks'][0]
            active_text=f'''\n## B8限额恢复已获批准并运行（独立最新收据）

研究者直接回复“是，以及列出之前停止的原因”，已明确批准提交`{b8_launch['training_commit']}`、提案`{b8_launch['proposal_sha256']}`及62次重放。[独立获批启动收据]({B8_LAUNCH})确认真实优化器更新已返回：启动快照`{b8_launch['snapshot_utc']}`有{task['segment_returned']}次新RETURNED，其中{task['replayed_returned']}次属于必要重放，当前有效轨迹{task['effective_updates']}，含原失败段的B8累计尝试{task['cumulative_B8_attempts']}。这是启动时点，非实时进度或终态。

状态IN_PROGRESS；E1–E6继承，E7–E9由干净固定ef11531副本执行。保持原1,440更新/159,190,859,832字节/47,605次/8,316秒、至少24GiB、额外重试0；E9尚无，B7不重训，2025/main不变。准备提案中的authorized=false及下方待批准文字保留历史时点，由此独立新批准更新状态；不改写冻结提案。原E1–E6指标的执行身份仍为b1f072e，不能把新恢复代码记成旧指标执行代码。
'''
            innovation_text=active_text+innovation_text
            innovation_analysis_text=active_text+innovation_analysis_text
            innovation_stage_rows=innovation_stage_rows.replace('|B8|六轮Train/Dev已封口，共2,942次RETURNED|第七轮源路径解析WinError121停止；最新E6/2880，62更新未保存，无固定E9|FAILED_INCOMPLETE_NO_FIXED_E9，DTFM对照未验收|','|B8|继承六轮Train/Dev，已获批从E6恢复E7–E9；真实新更新已返回|固定E9与三轮新Dev尚未齐备；原62次未保存尝试保留且仅准重放62次|IN_PROGRESS，DTFM固定终点对照尚未验收|')
    if b8_complete:
        c=b8_complete;v=c['summary']['values'];g=c['endpoint_groups'];cost=c['budget_closure']
        innovation_stage_rows='|B7/B8|seed2029各九轮Train/2024 Dev和固定E9身份均完成；B8继承六轮并恢复三轮，4320有效更新/4382实际尝试|单seed、同Dev年；DTFM收益混合，Brier、强雨及上尾仍有反例；机制和最终泛化未证明|COMPLETE_TRAIN_AND_DEV_EVALUATION；首轮探索性消融COMPLETE_WITH_LIMITATIONS|'
        innovation_text=f'''\n## B7/B8固定E9完成，首轮探索性消融带局限交接

B8于北京时间`{c['completed_at']}`完成；本次核查`{c['verified_at']}`。九轮Train/2024 Dev齐备：E1–E6继承b1f072e，E7–E9由ef11531恢复执行；B7不重训。B8固定E9实际文件SHA256 `{c['B8_fixed_E9_sha256']}`，B7既有E9身份直接继承。独立[完成收据]({B8_COMPLETE})取代早期失败/启动快照作为最新判断，旧原件全部保留。

新增1,440次RETURNED含62次明确重放，无不确定优化器INTENT；有效B8轨迹4,320，实际B8尝试4,382，B7/B8累计8,702。新增源159,190,859,832字节/47,605次，含静态312,828字节/1次；另有准备诊断4,096字节/1次。累计源958,621,476,211字节/286,736次，与新批准一致；恢复mtime区间{cost['recovery_wall_seconds_mtime_proxy']:.3f}秒，小于8,316秒，额外重试0。该时间不是GPU计费时间。

B8对B7的AUROC/AP/条件Pinball及q32欠覆盖方向改善，Brier退化。B8的20–50 mm/h条件Pinball对B7改善，但相对B4仍稍差；q32总体仍欠名义水平约4.3833个百分点，不能宣称全面地形优势、物理因果、统计显著性或最终泛化。2025继续冻结。完整指标、UTC、雨强及海拔充分量见[科学分析](SCIENTIFIC_ANALYSIS.md)与[CSV](METRICS.csv)。
'''
        main_table='\n'.join('|'+k+'|'+'|'.join(f'{v[m][k]:.12g}' for m in ('B4','B5','B6','B7','B8'))+'|' for k in HEADLINE)
        delta_table='\n'.join('|'+k+'|'+'|'.join(f"{c['summary']['differences']['B8_minus_'+m][k]:.12g}" for m in ('B4','B5','B6','B7'))+'|' for k in HEADLINE)
        rain=[];lower=.1
        for i,item in enumerate(g['B8']['all']['summary']['rain_strata']):
            z={m:g[m]['all']['summary']['rain_strata'][i]['conditional_pinball'] for m in ('B4','B6','B7','B8')}
            rain.append(f"|({lower},{item['upper'] if item['upper'] is not None else '∞'}]|{item['n']}|{z['B4']:.12g}|{z['B6']:.12g}|{z['B7']:.12g}|{z['B8']:.12g}|{z['B8']-z['B7']:.12g}|{z['B8']-z['B4']:.12g}|");lower=item['upper']
        utc=[]
        for group,obj in g['B8'].items():
            if group=='all':continue
            s=obj['summary'];ref=g['B7'][group]['summary']
            utc.append('|'+group+'|'+'|'.join(f'{s[k]-ref[k]:.12g}' for k in ('brier','auroc','average_precision','conditional_pinball'))+f"|{s['coverage'][-1]-ref['coverage'][-1]:.12g}|")
        elevation=[];old_bins=innovation_terminal['tail_diagnostics']['B7']['elevation_diagnostics']['bins']
        for name,s in c['tail_diagnostics']['B8']['elevation_diagnostics']['bins'].items():
            ref=old_bins[name];assert s['n_valid']==ref['n_valid'] and s['n_rain']==ref['n_rain']
            elevation.append(f"|{name}|{s['n_valid']}|{s['n_rain']}|{s['brier']:.12g}|{s['brier']-ref['brier']:.12g}|{s['conditional_pinball']-ref['conditional_pinball']:.12g}|{s['q32_coverage']-ref['q32_coverage']:.12g}|")
        innovation_analysis_text=innovation_text+f'''
### B4–B8同人口固定E9全部主指标

2023 Train959、2024 Dev963、seed2029/E0/f006、同掩膜/发生阈值、精确AUROC/AP、固定E9 LAST；表为便读舍入，CSV保留未舍入值。Brier为布里尔分数，AUROC为ROC曲线下面积，AP为平均精确率，Conditional Pinball为条件分位数损失，q32 Coverage为最高分位数覆盖率。Pinball沿冻结log1p雨强尺度，表中mm/h仅表示真实雨强分组。coverage为比例，signed_bias=coverage−0.984375，absolute_error为其绝对值。

|指标|B4|B5|B6|B7|B8|
|---|---|---|---|---|---|
{main_table}

|指标|B8−B4|B8−B5|B8−B6|B8−B7|
|---|---|---|---|---|
{delta_table}

B7相对B6仍保留Brier+0.00035862515341900103、条件Pinball+0.00020184117435637083的退化，以及AUROC/AP/q32方向改善；B8相对B6仍有Brier+0.001677816954149175的反例。B8对B4的Brier也稍差（+0.00013183536933868145），不能按其他指标改善宣称全面优于非地形基线。排序指标与概率误差方向不同是观测事实；没有做额外Brier分解，不能据此确定具体校准/过拟合机制。

B7与B8共享输入条件和配对初始化/样本顺序，活跃参数量同为4,411,058；B8是concat融合替换为DTFM调制，不能写成在B7上只叠加一个独立模块。B6→B7还增加DOTE及融合路径/50,192参数，增量不能唯一归因于地形物理量。E6恢复不是B6 E9微调，也不是新增独立seed。

### 强雨层：改善与基线反例同时保留

|雨强mm/h|有雨像元时次|B4 Pinball|B6|B7|B8|B8−B7|B8−B4|
|---|---|---|---|---|---|---|---|
{chr(10).join(rain)}

B8对B7除0.1–1 mm/h层外，其余雨强层条件Pinball均改善；20–30、30–50分别改善约0.0290356、0.0307205。但这两层对B4仍略退化，B7对B6的原强雨退化也不改写。>50仅6个像元时次，不能当作6场独立暴雨，更不能据此声称稳定极端泛化。

B8 q32覆盖94.05423961551665%，较98.4375%名义值仍欠4.383260384483345个百分点；对B7增加约0.5718209013780617个百分点。20–30、30–50、>50的q32 covered为40/564、1/147、0/6，B7为38/564、1/147、0/6。总体方向改善不能掩盖强雨上尾不足；按真实雨强条件化分层也不能直接要求各层等于名义覆盖。未宣称32分位数整体校准已通过。

### UTC与强雨场景：B8−B7

|既定分组|Brier差值|AUROC差值|AP差值|条件Pinball差值|q32覆盖差值|
|---|---|---|---|---|---|
{chr(10).join(utc)}

四UTC的Brier均退化，AUROC和条件Pinball方向均改善，06 UTC AP仍退化；强雨场景scene_max_ge20也保留Brier退化。继承B7对B6四UTC的Brier/Pinball退化，以及06 UTC AUROC/AP、12 UTC AP反例。分组重叠，不选有利时次；全部分组原值和差值都在CSV。

### 海拔充分量：B7/B8同区间对照

|预设区间|有效像元时次|有雨像元时次|B8 Brier|B8−B7 Brier|B8−B7 Pinball|B8−B7 q32覆盖|
|---|---|---|---|---|---|---|
{chr(10).join(elevation)}

区间<1000、[1000,2000)、≥2000米及分母相加已核对，三个区间的Brier均退化、Pinball/q32方向改善。分层AUROC/AP从未计算，NOT_COMPUTED保持原状，不补零或追加推理。B4–B6没有同口径海拔充分量，不构造缺失配对，也不从海拔相关性推断地形因果。

### 完成范围与证据边界

本次只核对新增三轮Train/Dev、六气象读取账本、一静态账本、1,440次RETURNED与一次实际E9文件SHA；继承旧B7九轮、B8 E1–E6和所有B0–B6有效结果，不重做129来源/126轮核验。读取额度等于本次明确批准，62次重放与旧失败段单列，额外重试0。没有模型推理、权重反序列化、归一化重拟合或2025访问。

首轮核心创新消融训练/评价可按COMPLETE_WITH_LIMITATIONS交接：只覆盖单seed、同一Dev年，像元不独立，无事件级显著性检验或跨年独立泛化证据。DOTE是物理启发代理量，当前性能方向不证明真实地形抬升机制。结果支持进一步检验的动机，不自动授予新seed、损失变体、训练延长或最终测试解封。
'''
    latest_status_text = ('最新B7/B8九轮固定E9均完成，首轮核心创新消融可带局限交接；稳定创新优势和最终泛化仍未验证。' if b8_complete else ('最新B7完整、B8已获批限额恢复并IN_PROGRESS，核心创新整体验收尚未完成。' if b8_launch else ('最新B7完整、B8失败未完成，核心创新整体验收未通过。' if innovation_terminal else '')))
    completion_scope_text = ('B7/B8各九轮固定E9完整；B8有效4320更新、实际4382尝试含62重放。历史失败段与准备/启动快照保留，不计为新seed。' if b8_complete else ('B7九轮完整，B8仅六轮封口且失败，无固定E9；部分轨迹不冒充完成。' if innovation_terminal else ('B7/B8为获批进行中状态，B8排队不等于已训练，两者都没有固定E9终点。' if innovation_launch else ('其中B7/B8是待批准新行，均0更新/0轮，无正式指标。' if innovation else ''))))
    current_checks_text = ('本次只核对B8新增三轮、六气象账本、一静态账本、1440更新及实际E9文件SHA；全部历史结果继承，0新增推理/原始气象读取/旧审查。' if b8_complete else ('本轮只核对明确新批准、独立执行身份、新增真实更新及只读页面；原4KiB诊断、工程检查与历史结果继承，没有新增源诊断或全量重查。' if b8_launch else ('本轮仅新增一次4KiB源诊断、B8恢复入口检查、资源/限额绑定；停止收口和所有旧模型证据继承，不重跑训练/推理或旧审查。' if b8_recovery else ('本轮只核对新B7九轮、新B8六轮及第七轮部分读取、两个新权重SHA和实际预算；不运行训练、推理或原始数据读取，旧B0–B6检查直接继承。' if innovation_terminal else ('本轮直接继承B0–B6既有完成核查；仅对B7/B8新增路径做13项新检查、2项受影响入口检查及真实小缓存零更新检查。没有重跑历史模型、129来源、126轮或15项旧地形检查。' if innovation else ('本轮核对新增18轮Train/Dev、36气象读取账本、2静态账本、8,640次RETURNED和两份实际E9权重SHA，再导出数值及配对差值；没有重跑训练、模型推理、129来源、126轮或全量归一化。' if static else '本轮仅核对新CSV及差值，不重跑训练或历史审查。'))))))
    input_checks_text = ('仅核对B8恢复新增三轮、六气象账本、静态账本、1440更新和实际E9 SHA；此前停止、启动和B0–B7结果直接继承' if b8_complete else ('绑定新批准和启动快照，核实真实返回更新及只读页面；原恢复检查和4KiB诊断继承' if b8_launch else ('仅检查B8恢复入口、一次4KiB有界源诊断及精确额度，停止收口与B0–B7均直接继承' if b8_recovery else ('仅核对新B7九轮、新B8六轮和第七轮部分账本、实际更新/读取额度及两份最新权重字节SHA，继承全部旧B0–B6证据' if innovation_terminal else ('继承B0–B6原收口，仅对B7/B8新增代码、物理小缓存、零更新GPU检查及审批绑定进行核对' if innovation else ('先核对B5/B6新增18轮、36气象账本、2静态账本、8,640更新及2份实际E9 SHA，再校验数值导出和差值' if static else '仅校验新增导出及差值'))))))
    csv_scope_text = ('本轮补入B8 E7–E9轨迹、完整固定E9和B8对B4/B5/B6/B7全部配对差值；旧E1–E6执行身份保持b1f072e，新E7–E9及E9为ef11531。地形比较各单seed，不计算伪造样本标准差。' if b8_complete else ('本轮新增B7九轮、B8六轮轨迹与B7固定E9；B8固定E9缺失单列。地形比较各仅一个seed，不计算伪造的样本标准差。' if innovation_terminal else ''))
    publication_base = '651c250a90a60630176a9dfeb466a9b993642862' if b8_complete else 'ef11531a7cdeb35b767caebdb61e0e81c6123187'
    latest_science_text = (f'B7/B8固定E9及2024 Dev均已核实完成；DTFM对concat收益混合，仅单seed探索性结论，见[完成收据]({B8_COMPLETE})。' if b8_complete else (f'最新B7完成但收益混合；B8已获批从E6恢复E7–E9，状态IN_PROGRESS，固定E9与最终DTFM对照尚未获得，见[启动收据]({B8_LAUNCH})。' if b8_launch else (f'最新B7九轮完成但收益混合，B8因源路径超时停止且缺少固定E9；B7/B8整包未完成，DTFM融合对照NOT_VERIFIED。停止与核查证据见[本轮终态]({INNOVATION_TERMINAL})。' if innovation_terminal else '')))
    if innovation_multi:
        m=innovation_multi
        multi_text=f'''\n## 追加两seed：四模型准备就绪，正式训练NOT_STARTED

执行代码`{m['execution_code_commit']}`，规范化提案SHA256 `{m['proposal_sha256']}`；[唯一四模型提案]({INNOVATION_MULTI})、[新初始化/顺序及必要检查]({INNOVATION_MULTI_CHECKS})、[0载荷源路径入场]({INNOVATION_MULTI_SOURCE})。顺序B7/2030→B8/2030→B7/2031→B8/2031。目前只有seed2029完成，新四任务均0更新/0轮，三seed汇总尚无。

原模型、E0/f006、959/963、Train2/Dev8、九轮固定E9、AdamW和学习率轨迹、全部归一化/掩膜及lambda0.1不变；只变任务seed及seed+10000/20000派生初始化流。两seed公共路径/4,411,058活跃参数已实查，旧seed+epoch−1规则的八轮移位重叠已记录，不能视为独立天气年份。准备阶段11项针对性检查通过，真实缓存静态读取625,656字节/2次，当时正式更新/检查点加载/原始气象载荷为0；没有重跑历史来源、逐轮总结或GPU压力测试。

预算逐冻结清单重算：每模型4,320更新、477,571,953,840字节/142,813次（含静态312,828字节/1次）；四模型17,280更新、1,910,287,815,360字节/571,252次，每模型6小时/整包24小时，Replay=0、额外重试=0。F盘约93.02GiB不足初始96GiB；D盘约98.71GiB且全新命名空间权限通过，拟输出`{m['output']['directory_alias']}`。保持初始96GiB/每任务24GiB，D盘具体位置随集中批准确认，不删除或迁移历史文件。启动重核资源及一次15秒有界源元数据；路径异常留账并停止，不当缺测。

全部完成后公布B8−B7逐seed原值/差值、三seed均值及样本标准差ddof1，覆盖总体/四UTC/强雨场景/全部雨强层和已有海拔充分量。q32以距98.4375%的偏差及绝对误差评价，不简单看覆盖率高低；不按Dev结果改方案。新增训练尚无批准，2029混合/负面结果、原WinError121及62次重放证据保留，2025与main不变。
'''
        if innovation_multi_launch:
            ml=innovation_multi_launch
            multi_text=multi_text.replace('四模型准备就绪，正式训练NOT_STARTED','四模型已获批准并单次启动，IN_PROGRESS')
            multi_text=multi_text.replace('目前只有seed2029完成，新四任务均0更新/0轮，三seed汇总尚无。',f"[明确批准与真实启动收据]({INNOVATION_MULTI_LAUNCH})记录UTC `{ml['as_of']}`（北京时间加8小时）的启动快照：B7/2030有24次RETURNED，其余三任务排队未启动；不把此快照当实时计数。仅seed2029已完成固定E9，新增四模型均无固定E9，三seed汇总尚无。")
            multi_text=multi_text.replace('D盘具体位置随集中批准确认','D盘具体新位置已随本次整包批准确认')
            multi_text=multi_text.replace('新增训练尚无批准','研究者已对完整提案直接回复“批准”，该批准已消费并单次执行；启动有界源元数据/只读权限检查通过，0载荷，无重复模型测试。旧authorized=false提案保留准备时点，不改写其SHA')
        if innovation_multi_stop:
            multi_text=multi_text.replace('四模型已获批准并单次启动，IN_PROGRESS','四模型包意外中断，未恢复训练')
            multi_text=multi_text.replace('；不把此快照当实时计数。',f"；这是历史启动快照。最新[中断与页面修复收据]({INNOVATION_MULTI_STOP})记录控制器/子进程已退出且无终态收据，B7/2030为3,321 RETURNED、E6/2,880已保存、441未保存；其余三项未启动。退出原因NOT_VERIFIED，训练未恢复。")
        if innovation_multi_cause:
            multi_text=multi_text.replace('退出原因NOT_VERIFIED，训练未恢复。','后续诊断支持更新引发的宿主生命周期耦合归因，训练未恢复；历史逐PID终止调用仍未捕获。')
            multi_text+=f'''\n研究者直接确认“发生过更新”。[原因追踪与独立启动修复]({INNOVATION_MULTI_CAUSE})保留证据分级：14:09:46 Codex记录执行器停止，14:09:51.644 Windows记录容器销毁，与最后journal写入相差约0.137秒；旧进程的宿主生命周期耦合为高置信归因，具体哪个历史终止调用未捕获。纯探针复现Job关闭会结束无窗口子进程；新WMI监督器及实际页面均已验证不属于任何Job/应用包，3项新门控测试通过，旧消耗批准被拒绝，0次训练恢复。旧初核NOT_VERIFIED收据原样保留，不把后续诊断倒写到历史。\n'''
        if innovation_multi_recovery:
            rp=innovation_multi_recovery;rb=rp['budget']
            multi_text+=f'''\n### 最小限额恢复已准备，尚未执行

[唯一恢复提案]({INNOVATION_MULTI_RECOVERY})绑定执行代码`{rp['execution_code_commit']}`、规范化SHA256 `{rp['proposal_sha256']}`；[10项新恢复检查]({INNOVATION_MULTI_RECOVERY_CHECKS})仅用CPU夹具验证状态/LR/RNG、441重放账本、读范围、串行与失败即停，实际权重未加载、原始气象未读取。继续训练指令已收到，但旧零replay批准已消费，准确新增限额仍待一次明确批准。

顺序B7/2030从E6恢复E7–E9→B8/2030→B7/2031→B8/2031。新增14,400更新含441必要重放，1,591,906,721,352逻辑天气/静态源字节、476,044次；累计17,721更新、1,934,666,227,950字节/578,566次。恢复B7≤11,606秒、其余各21,600秒，新包≤76,406秒（21小时13分26秒）；对旧包保守计9,994秒后仍≤24小时、B7≤6小时，不加总时间预算。额外重试/额外重放0，初始96GiB/每任务24GiB，仍用D盘全新独立目录`{rp['output']['directory_alias']}`，入场实测约{rp['resources']['output_free_bytes']/1024**3:.2f}GiB。

旧E6只安排SHA核对1次、反序列化1次；文件53,902,917字节，107,805,834字节是两次逻辑归档体积，和天气/静态源账本分列，不声称torch/zip内部物理读取流量上限。恢复将保留模型、AdamW、学习率进度、全部必要RNG及九轮样本顺序，旧E1–E6和441未保存尝试原样保留。冻结E0/f006/959/963/固定E9及评价口径不变，2025继续冻结；目前没有恢复批准文件、新输出目录或新增科研结果。
'''
        if innovation_multi_recovery_launch:
            ml=innovation_multi_recovery_launch
            multi_text=multi_text.replace('## 追加两seed：四模型包意外中断，未恢复训练','## 历史原包：意外中断，当前已另批限额恢复')
            multi_text=multi_text.replace('### 最小限额恢复已准备，尚未执行','### 历史准备时点：最小限额恢复已准备')
            multi_text=f'''\n## 当前恢复包已明确批准并单次启动：IN_PROGRESS

研究者对完整e81c6e1/3314231a恢复包直接回复“是”，批准已消费。[真实启动收据]({INNOVATION_MULTI_RECOVERY_LAUNCH})记录UTC `{ml['as_of']}` 的一次启动快照：新增{ml['new_segment_returned']}次RETURNED，其中{ml['replay_returned']}次属于批准的441必要重放；累计{ml['cumulative_returned']}次实际尝试，旧E1–E6六轮封口保留，后三项仍PENDING。该快照不是实时计数，不冒充E9或三seed结果。

真实E6 SHA/状态恢复已跨过并产生新更新；训练与页面的监督器及目标共四角色均核实无Job/包身份，原网页已切新包。批准后仅核对必要身份/资源和两项只读页面计数，未重复模型检查。源读取由正式账本计量，导出器不另跑模型或读取气象。原authorized=false提案、原包停止及下文待批准文字保留历史时点，当前新批准以本段和独立启动收据为准。
'''+multi_text
        innovation_text=multi_text+innovation_text;innovation_analysis_text=multi_text+innovation_analysis_text
        innovation_analysis_text+='''\n### B6与独立DOTE验证：仅后续建议，不在本包内

本轮三seed只检验共享气象/地形信息下concat与DTFM的差异。B6仅seed2029，不能由此声称DOTE独立稳定增益。等本轮结果齐备后再决定是否补B6/2030、2031；两模型参考8,640更新、955,143,907,680字节/285,626次、12小时，仍混合了DOTE与融合/参数增量，须另案批准。

若论文需隔离动态地形值的贡献，可另案设计同结构/同总参数的DOTE空间对应关系对照：在同一有效性模式类别内，对8通道向量作预注册联合空间置乱，保留有效集合、跨通道关系和非零值分布，只破坏正确空间对应；不得根据Dev选择置乱规则。它检验正确对应信息的预测价值，仍不证明真实抬升机制，且实现/活跃响应尚未验证。最小单seed先导参考4,320更新、477,571,953,840字节/142,813次、6小时；三个seed控样则12,960更新、1,432,715,861,520字节/428,439次、18小时。这些仅预算估算，均NOT_STARTED、未授权，不追加到本轮四模型包。

最终测试准备仅可先冻结选模/报告规则及访问流程；2025载荷、推理和模型选择继续禁止。三个训练seed不是独立年份，大量像元也不是大量独立暴雨事件；不宣称显著性、物理因果或最终泛化。
'''
        innovation_stage_rows+='\n|B7/B8追加2030/2031|新seed初始化/顺序、入口及资源检查通过，四任务配置和预算冻结|尚无新增训练授权，四任务0轮/0更新，三seed统计尚无|NOT_STARTED；新增seed科学验证NOT_VERIFIED|'
        latest_status_text='当前完成范围仅B7/B8 seed2029；2030/2031四任务准备就绪但NOT_STARTED，三seed创新验证尚未完成。'
        latest_science_text='B7/B8目前仅seed2029完成固定E9对照且收益混合；追加2030/2031四模型NOT_STARTED，三seed创新统计尚未产生。'
        completion_scope_text='已完成条目仅seed2029；追加四任务均0轮/0更新、无E9，不把准备文件或CPU初始化记为训练完成。'
        csv_scope_text='本轮仅增加四条NOT_STARTED的终点缺失占位，已有全部原值及配对差值不变；没有新增B7/B8三seed均值或标准差。'
        current_checks_text='本轮仅检查新seed初始化/顺序、入口和资源，正式更新/检查点加载/原始气象载荷为0；旧结果直接继承。'
        input_checks_text='只新增多seed初始化/顺序、调度及资源元数据检查，继承全部B0–B8已完成结果'
        if innovation_multi_launch:
            innovation_stage_rows=innovation_stage_rows.replace('|尚无新增训练授权，四任务0轮/0更新，三seed统计尚无|NOT_STARTED；新增seed科学验证NOT_VERIFIED|','|整包已批准并单次启动；B7/2030运行、其余三项排队，无新增固定E9|IN_PROGRESS；三seed科学验证NOT_VERIFIED|')
            latest_status_text='当前完成范围仍仅B7/B8 seed2029；追加2030/2031四模型已批准并单次启动，整包IN_PROGRESS，三seed创新验证尚未完成。'
            latest_science_text='B7/B8目前仅seed2029完成固定E9对照且收益混合；追加四模型获批进行中，三seed创新统计尚未产生。'
            completion_scope_text='seed2029完整继承；新增四模型启动快照为B7/2030有24次RETURNED、其余三项排队，无新增固定E9或指标，不冒充科研完成。'
            csv_scope_text='仅更新四任务批准/启动状态及24次RETURNED带时点快照；既有原始指标与差值不变，四条终点缺失占位保持空值，没有新增三seed均值或标准差。'
            current_checks_text='批准后仅核对固定执行版本、真实资源与源路径有界元数据入场、实际优化器返回及独立只读页面；不重复旧模型或数据测试。'
            input_checks_text='继承已通过准备检查，仅新增精确批准/启动身份、实时资源及只读页面验证，不再次推理或重复旧审查'
        if innovation_multi_stop:
            innovation_stage_rows=innovation_stage_rows.replace('|整包已批准并单次启动；B7/2030运行、其余三项排队，无新增固定E9|IN_PROGRESS；三seed科学验证NOT_VERIFIED|','|B7/2030意外停止，六轮封口/3,321实际更新，441未保存；后三项未启动|STOPPED_UNEXPECTED；三seed科学验证NOT_VERIFIED|')
            latest_status_text='新增四模型包已意外中断：B7/2030有3,321 RETURNED，最新E6/2,880、441未保存，后三项未启动；训练未恢复，退出原因NOT_VERIFIED。'
            latest_science_text='B7/B8仍仅seed2029完成固定E9；新增四模型包意外中断，没有三seed创新结果。'
            completion_scope_text='新增B7/2030仅E1–E6 Train/Dev封口，E7有441未保存更新；后三项未启动。无新增固定E9，不能用E6替代终点。'
            csv_scope_text='只更新中断状态、六轮封口/3,321实际更新及441未保存说明；全部既有原值和差值保留，新终点继续空值，没有新增三seed均值或标准差。'
            current_checks_text='仅核对服务/训练进程退出、现有部分账本与E6收据，修复只读页面；热日志仅在私有副本解析，原账本SHA不变，0新训练/推理/原始气象读取。'
            input_checks_text='新增中断元数据及页面修复核对；不重复已完成模型审查，原训练目录和失败前账本不改写'
        if innovation_multi_cause:
            latest_status_text='新增四模型包仍停止；研究者确认发生更新，日志/事件及纯探针支持宿主生命周期耦合归因；独立页面修复已验证，训练未恢复。'
            current_checks_text='仅新增退出时间线、Windows Job纯探针和独立启动防重试门控；实际页面监督器/目标均无Job及包身份，0新训练/推理/原始气象读取，历史PID终止调用未捕获。'
            input_checks_text='新增宿主更新/容器时间线与独立启动修复证据；不重复模型测试或改写原中断账本'
        if innovation_multi_recovery:
            latest_status_text='最小恢复入口与精确441重放限额已准备，待一次准确新批准；当前训练仍停止，B7/2030为3,321次RETURNED、E6/2,880保存、441未保存，后三项未启动。'
            innovation_stage_rows+='\n|B7/2030 E6恢复及后三任务|10项新恢复检查通过，代码/检查点身份/准确新增预算冻结|原零replay批准不覆盖441重放，新限额未批准；没有实际恢复|NOT_STARTED（恢复包）；原科学验证NOT_VERIFIED|'
            current_checks_text='仅新增B7/2030恢复入口10项CPU夹具检查及实际资源/身份绑定；原独立启动和所有模型/数据检查继承，0真实权重加载/优化器更新/原始气象读取。'
            input_checks_text='新增恢复代码/CPU检查/准确预算身份；继承旧E1–E6、441未保存及所有模型结果，不重复旧审查'
        if innovation_multi_recovery_launch:
            latest_status_text='准确441重放限额已明确批准并单次执行，B7/2030从E6真实恢复，后三任务串行等待，整包IN_PROGRESS；尚无新增固定E9或三seed汇总。'
            innovation_stage_rows=innovation_stage_rows.replace('|B7/B8追加2030/2031|','|B7/B8追加2030/2031原包（历史中断）|')
            innovation_stage_rows=innovation_stage_rows.replace('|原零replay批准不覆盖441重放，新限额未批准；没有实际恢复|NOT_STARTED（恢复包）；原科学验证NOT_VERIFIED|','|新准确限额已批准并单次消费，B7/2030真实恢复，后三项排队|IN_PROGRESS；固定E9/三seed科学验证尚未完成|')
            latest_science_text='seed2029固定E9与混合结果完整继承；新增两seed恢复包进行中，尚无新增E9或三seed创新结论。'
            completion_scope_text='B7/2030继承六轮封口、E6/2880恢复，旧3321实际尝试及441未保存历史仍计入；新增实际RETURNED与重放见启动收据，后三项未启动，无新增固定E9。'
            current_checks_text='批准后仅核对冻结身份、实时资源、实际E6恢复与独立宿主证明，并验证两项只读页面计数；正式源读取由训练账本计量，不重复旧模型或源数据检查。'
            input_checks_text='新增准确批准和真实恢复启动快照；旧E1–E6及所有历史结果继承，不重新推理或重查旧证据'
            csv_scope_text='仅更新四任务批准/恢复启动状态及带时点实际尝试和执行版本，旧全部指标与配对差值不变；新E9终点占位仍为空值，没有三seed统计。'
        publication_base=m['execution_code_commit']
    stage = f'''# 阶段验收统一入口

B5/B6终态元数据时点：`{as_of}`。{'B7/B8后续状态由独立启动/终态收据和本次Git提交绑定，不把该旧时点冒充新训练时间。' if innovation else ''}B0–B4限定基线交接为 **COMPLETE_WITH_LIMITATIONS（带局限完成）**；B5/B6为 **{phase_status}**，地形单seed消融{'带局限完成' if static else '仍在进行'}；最终泛化验收为 **NOT_VERIFIED（未核实）**。{latest_status_text}不能把训练完成等同于全部科学假设通过。

|模型|已经完成|尚未完成或限制|本阶段判断|
|---|---|---|---|
|B0/B1|seed2026、2027，各E0/E1/E2固定九轮Train/2024 Dev|两seed；10,455/10,501人口；历史执行commit绑定不完整；历史不确定尝试未追认|限定人口内基线对照可交接|
|B2|seed2029/E0/f006，九轮、4,320更新及2024 Dev，固定E9 LAST|仅一seed；B2/B3指标方向混合，未证明时序增量全面改善|当前探索性配对条目完成|
|B3/B4|2029/2030/2031三个独立seed的九轮Train/Dev及固定E9配对|强雨和q32缺陷、同一开发年，未证明最终泛化或统计显著性|描述性随机性复现完成|
{static_stage}
{innovation_stage_rows}
|2025最终测试|继续冻结|没有当前最终模型推理与评价|NOT_STARTED，不得据此选模|

## 同人口比较范围

- B0/B1：同seed、同E臂的10,455 Train / 10,501 Dev，允许比较单通道时序增量。E0/E1/E2分别记录，损失臂及恢复不算新seed。
- B2/B3：seed2029，959/963，E0/f006、固定E9 LAST。B2为7通道×1时次t−10分钟，4,332,290参数；B3为7×6，4,349,090参数。槽位权重映射乘sqrt(6)，其余72个兼容张量同初始化，不宣称模型完全等价。
- B3/B4：三seed各自共享959/963、初始化兼容部分、顺序与评价掩膜；B4增加13变量GFS MEE（气象环境编码器）。跨seed改变初始化与排列，恢复重放仍属于原seed。
- B5/B6：{'已与B4 seed2029在同人口、同初始B4身份、同顺序、同评价口径下完成固定E9配对' if static else '将与B4 seed2029在同人口、同评价口径下比较，尚无固定E9结果'}。不得跨B0/B1与B2–B6的不同训练人口直接归因架构优势。

## 当前训练状态

以下为一次只读元数据快照，不是实时页面，也不把已封口的一轮当作九轮完成。

|模型|seed|阶段状态|执行状态|已返回更新|完整Train/Dev轮数|
|---|---|---|---|---|---|
{status_table}

## 本轮交付核对

五个根目录文件为统一入口，旧报告和实验收据保留。矩阵含{len(matrix)}条历史/当前记录；不是{len(matrix)}个独立seed或{len(matrix)}个已完成模型。{completion_scope_text}`epochs`表示该记录已封口轮数，`global_steps`为实际RETURNED计数，失败时可高于最新保存更新；训练完成须同时具备全部Train/Dev收据、账本、预算和固定E9身份。

{current_checks_text}

本轮出版基线：`{publication_base}`。文件所属最终提交由Git历史标识；实际训练代码另见[矩阵](EXPERIMENT_MATRIX.csv)和[证据索引](EVIDENCE_INDEX.md)，不得用本次文档commit替代执行commit。

[实验矩阵](EXPERIMENT_MATRIX.csv) · [完整数值与差值](METRICS.csv) · [科学分析](SCIENTIFIC_ANALYSIS.md) · [证据索引](EVIDENCE_INDEX.md)
{innovation_text}
'''
    (ROOT / 'STAGE_ACCEPTANCE.md').write_text(stage.rstrip()+'\n', encoding='utf-8')
    analysis = f'''# 科学分析统一入口

B0–B4在已限定范围内可作基线交接；当前证据支持开发集上的局部描述性结论。B5/B6{'九轮及固定E9配对完成，地形收益混合、校准退化，仅支持单seed探索性消融' if static else '仍IN_PROGRESS，地形增益尚未验证'}；最终泛化未验证。
{latest_science_text}

## B3/B4：全部三个seed

下表统一为 **B4−B3**。Brier Score（布里尔分数）及Conditional Pinball Loss（条件分位数损失）越低越好；AUROC（ROC曲线下面积）和AP（平均精确率）越高越好。q32 Coverage（最高分位数覆盖率）应接近名义0.984375，不能无条件理解为越大越好。表中仅为便读而舍入，CSV保存原始浮点精度。

|指标|2029差值|2030差值|2031差值|差值均值|样本标准差（ddof=1）|
|---|---|---|---|---|---|
{summary_table}

三个seed的总体Brier、AUROC、AP和条件Pinball均同向改善，支持本人口/开发年中MEE增量的描述性复现。它不能区分GFS信息、额外参数及融合结构各自的因果贡献，不能直接证明物理机制或全部雨强均获益。

## 必须保留的反例

- (20,30]与(30,50] mm/h条件Pinball的三seed平均B4−B3分别为+0.02284020139478345和+0.02926448537140706，均退化；(30,50]三个seed均退化。seed2031两层分别+0.06578915690489107、+0.08003864767502422。
- seed2029的06 UTC Brier退化+0.0001363967192149207；seed2030的18 UTC退化+0.0004587919574727817。不能用三seed平均改善掩盖单seed/时次反例。
- q32六个终点仅约93.5050%–94.6094%，低于98.4375%名义水平约3.8281–4.9325个百分点。seed2031 B4覆盖率比B3下降0.0015423471139228706；均值改善不等于校准通过。
- seed2030强雨q32 covered：B3为12/564、0/147，B4为5/564、0/147；seed2031 B3为109/564、12/147，B4为20/564、0/147。seed2029雨强层covered未保存，标记NOT_AVAILABLE，不补造或追加推理。按真实雨强分层是按结果条件化，不能要求每个层都达到同一名义分位覆盖。
- >50 mm/h在959/963人口中只有6个有雨像元时次，不能当作6场独立暴雨，也不能稳定评价极端尾部。

## B0/B1与B2/B3

B0/B1在10,455/10,501人口的两seed配对提供时序信息增量的限定证据；CSV分别保留六个同seed/同损失臂配对，禁止将损失臂当独立seed。旧Phase-A、BEST与FinalFit是不同协议，仅列示原记录，不纳入固定九轮配对均值。

B2相对B3（统一B2−B3）：Brier为−0.0009406648154928754，AUROC为−0.0026810498852304354，AP为−0.012892029278753436，条件Pinball为+0.0002321528279146945，q32覆盖为−0.004654014025795683。B2 Brier更好而B3区分能力及条件Pinball更好，单seed不支持时间增量全面改善；输入维度和参数差异已明确记录。

## B5/B6与结论边界

本轮地形实验采用已批准的WGS84面积聚合、原生米制梯度、目标footprint、width16 SP04残差融合；B5增加海拔，B6增加完整六静态通道。DEM本地源SHA固定，但供应商发布版本链NOT_VERIFIED；研究者接受该限制用于探索性消融。零输出残差保证起点行为与B4相同，不证明训练后一定获益。{'两模型均已取得固定E9结果，全部正负结果如下。' if static else '当前两个模型固定E9尚未齐备，地形正/负结果均不得预填。'}
{static_text}
{innovation_analysis_text}

三seed主要检验训练随机性；相邻seed按seed+epoch−1排列规则存在移位重叠，不能声称所有轮排列彼此独立。大量像元也不是大量独立事件。重复使用2024 Dev存在开发集选择影响，没有事件级独立性估计、置信区间或显著性声明。不同人口不可跨模型排名归因，2025最终测试继续冻结；旧catalogue/QC访问事实不改写为历史从未访问。

## CSV读取规范

`METRICS.csv`为长表（一个数值一行），共{len(rows)}行。`RAW_ENDPOINT`保存现有完整终点指标对象的数值叶子，包括总体、四UTC、强雨场景、七雨强层、已保存的32分位数及可靠性分箱/充分量；`RAW_EPOCH`继承已有逐轮公开数值与B2九轮摘要。此前为补齐新seed的完整终点字段，已摘录4份既有E9评价JSON的summary并核对原有字节SHA；本次继承该[完整终点摘录]({FULL})，不重做历史逐轮审查。未扩展发布的新seed逐轮完整数值仍按原收据ID索引。这里的“原始指标”指未舍入的已保存统计量，不是逐像元预测或原始气象载荷。

`PAIRED_DELTA`为目标值减reference_value；`PAIRED_MEAN`、`PAIRED_SAMPLE_SD`只对同口径seed差值计算，样本数在n_seeds，非独立事件数。不同E臂不混合聚合。`metric`中`/数字/`为源数组的零起始下标，32分位数中31即q32；雨强层upper=null表示无穷上界，其他null保持原含义。计数、分子、tau和边界只是充分量/元数据，不全是性能指标，不能对它们解释“提升”。coverage数组方向应看对应tau偏差。

`MISSING_OR_NULL`原样保留缺失/不可估计状态，value为空，不是零；{'继承B5/B6完整终点和18轮Train/Dev数值' if static else 'B5/B6不填最终数值'}。{csv_scope_text}源文件和JSON Pointer（JSON定位指针）或CSV零起始row可回查；q32别名指向coverage/31。共享内容只保留一个数值行；新增来源不能改写旧值。详细配置、Git执行身份、评价脚本和数据版本由experiment_id连接[矩阵](EXPERIMENT_MATRIX.csv)。
'''
    (ROOT / 'SCIENTIFIC_ANALYSIS.md').write_text(analysis, encoding='utf-8')
    input_names = [BASE, OLD, GROUPS, B2, B34, FULL, epoch_source,
                   READY + 'evidence/b5_b6_corrected_start_launch.json',
                   READY + 'evidence/b5_b6_initial_start_stop.json',
                   READY + 'evidence/b5_b6_terrain_production.json']
    if static:
        input_names.append(STATIC)
    if innovation:
        input_names += [INNOVATION, READY+'evidence/b7_b8_physical_cache_preparation.json',
                        READY+'evidence/b7_b8_physical_cache_correction.json',READY+'evidence/b7_b8_cached_real_check.json',
                        READY+'evidence/b7_b8_preparation_checks.json']
    if innovation_launch:
        input_names.append(INNOVATION_LAUNCH)
    if innovation_terminal:
        input_names.append(INNOVATION_TERMINAL)
    if b8_recovery:
        input_names += [B8_RECOVERY,B8_DIAGNOSTIC,B8_CHECKS]
    if b8_launch:
        input_names.append(B8_LAUNCH)
    if b8_complete:
        input_names.append(B8_COMPLETE)
    if innovation_multi:
        input_names += [INNOVATION_MULTI,INNOVATION_MULTI_CHECKS,INNOVATION_MULTI_SOURCE]
    if innovation_multi_launch:
        input_names.append(INNOVATION_MULTI_LAUNCH)
    if innovation_multi_stop:
        input_names.append(INNOVATION_MULTI_STOP)
    if innovation_multi_cause:
        input_names.append(INNOVATION_MULTI_CAUSE)
    if innovation_multi_recovery:
        input_names += [INNOVATION_MULTI_RECOVERY,INNOVATION_MULTI_RECOVERY_CHECKS]
    if innovation_multi_recovery_launch:
        input_names.append(INNOVATION_MULTI_RECOVERY_LAUNCH)
    source_table = '\n'.join(f'|[{name}]({name})|`{digest(name)}`|' for name in input_names)
    identity_table = '\n'.join(f"|{r['model_id']}|{r['seed']}|`{r['checkpoint_reference']}`|`{r['executed_commit']}`|" for r in matrix if r['comparison_population'] == 'CORE_F006_959_963' and 'failed' not in r['experiment_id'])
    output_table = '\n'.join(f'|[{name}]({name})|`{digest(name)}`|' for name in ['STAGE_ACCEPTANCE.md', 'EXPERIMENT_MATRIX.csv', 'METRICS.csv', 'SCIENTIFIC_ANALYSIS.md'])
    evidence = f'''# 统一证据索引

出版基线commit：`{publication_base}`。本五文件的版本由所属Git提交标识，不伪造自引用commit。实际模型代码独立绑定如下。研究者为主体，AI辅助摘录；公开SHA约束原件身份，不等于外部已独立复现未公开数据。

## 当前训练状态快照

此嵌入快照仅记录既有B5/B6收口时点，供继承和确定性重建；B7/B8最新终态见下方独立收据。状态时点是UTC（北京时间加8小时），不是页面实时值。{'B5/B6均COMPLETE_TRAIN_AND_DEV_EVALUATION，18轮完整收据、账本及实际E9文件SHA沿用既有收口' if static else 'B5/B6阶段均IN_PROGRESS，B6执行PENDING，终态须依完整新收据另行收口'}，不从checkpoint存在或部分轮次判完成。

<!-- STATUS_SNAPSHOT -->
```json
{json.dumps(snapshot, ensure_ascii=False, indent=2)}
```

## 训练日志与本地原件定位

公开脱敏ID与原件的映射沿用既有索引；不公开私人绝对路径、原始数据、权重或未脱敏账本。

|范围|训练日志/逐轮收据|模型、评价与本地原件身份|
|---|---|---|
|B0/B1，2026/2027及历史失败|[原实验摘录]({OLD})、[逐轮日志索引]({PROGRESS}evidence/epoch_receipts.json)、[历史campaign]({PROGRESS}evidence/historical_campaigns.json)|[原件source_id、bytes、SHA及可公开URL]({PROGRESS}evidence/source_manifest.json)；每实验source_ids连接原结果，矩阵保留历史执行commit NOT_VERIFIED|
|B2/2029|[完成证据]({B2})的epochs、checkpoint_metadata、ledger、actual_io|sources中B2_COMPLETION、B2_DEV_E*、B2_IO_*等脱敏ID/字节SHA；全部9轮原始JSON/SQLite/权重LOCAL_ONLY；E9文件曾实际重哈希|
|B3/B4，2029|[保留执行收据]({PROGRESS}evidence/seed2029_execution.json)、[原件清单]({PROGRESS}evidence/source_manifest.json)|[总体及分组指标]({GROUPS})、[三seed完成收据]({B34})的s2029/B3或B4/development_09.json字节SHA；继承既有权重核验|
|B3/B4，2030/2031|[原中止事实]({READY}evidence/b3_b4_multiseed_stop.json)、[三seed收口]({B34})的epochs/tasks/budget_closure|sources中s2030/s2031/{'{model}'}/development_09.json、训练日志、LAST receipt、updates.sqlite、读取账本分别有SHA；每个epoch/模型/seed定位，不把恢复段计为新seed|
|2030/2031完整终点字段|[本轮4份既有E9数值摘录]({FULL})|groups包含六评价分组的完整summary，sources字节SHA与既有三seed收口一致；仅补足数值出版，不重新推理或读取原始气象|
|B5/B6，2029|[一次纠正启动]({READY}evidence/b5_b6_corrected_start_launch.json)、[原失败]({READY}evidence/b5_b6_initial_start_stop.json)|[冻结纠正提案]({READY}evidence/b5_b6_corrected_start_proposal.json)、[地形源/网格/静态包SHA]({READY}evidence/b5_b6_terrain_production.json)；{'E9及18轮完整收据见下一行' if static else '当前E9身份NOT_AVAILABLE'}|
{f'|B5/B6本轮完整收口|[18轮、36读取账本、2静态账本及E9]({STATIC})|sources中B5或B6/train、development、tail、LAST receipt、reads.sqlite、updates.sqlite均有字节SHA；完整endpoint_groups和epochs仅公开脱敏统计，原件及权重LOCAL_ONLY|' if static else ''}
{f"|B7/B8{'历史准备时点' if innovation_launch else '准备，未训练'}|[科学协议]({READY}B7_B8_INNOVATION_PROTOCOL.md)、[精确提案]({INNOVATION})、[真实零更新]({READY}evidence/b7_b8_cached_real_check.json)|code/data SHA、3份新GFS原件身份及缓存纠正均已记录；准备时无正式批准或E9结果，实际新批准另列，不复用B6授权|" if innovation else ''}
{f"|B7/B8{'历史启动快照' if innovation_terminal else '最新获批启动'}|[新批准、真实更新和资源入场]({INNOVATION_LAUNCH})|b1f072e/64e8单次启动；当时B7 RUNNING、B8 PENDING，固定E9尚无；不把该快照当当前状态|" if innovation_launch else ''}
{f"|B7完成/B8停止的{'历史终态' if b8_complete else '最新终态'}|[15轮、31气象账本、2静态账本与权重身份]({INNOVATION_TERMINAL})|B7固定E9完成，B8源路径WinError121停止；B8最新E6 SHA {innovation_terminal['tasks'][1]['last_saved_sha256']}，E9缺失；不重试原始源或训练|" if innovation_terminal else ''}
{f"|B8恢复准备（未获批准）|[精确限额提案]({B8_RECOVERY})、[一次有界源诊断]({B8_DIAGNOSTIC})、[新增检查]({B8_CHECKS})|当前路径/4KiB可读，历史故障原因未验证；E6恢复入口就绪，1440新更新含62重放待新批准，0次正式恢复|" if b8_recovery else ''}
{f"|B8{'历史获批恢复启动' if b8_complete else '最新获批恢复启动'}|[明确批准与真实更新]({B8_LAUNCH})|实际执行ef11531，E1–E6指标仍绑定b1f072e；本轮恢复IN_PROGRESS，E9未完成；前一行仅历史准备时点|" if b8_launch else ''}
{f"|B8恢复完成的最新收口|[三轮、六气象账本、静态账本与实际E9 SHA]({B8_COMPLETE})|B8九轮Train/Dev及固定E9已验证；4382实际尝试含62必要重放，旧E1–E6不复核；前面停止/启动状态为历史时点|" if b8_complete else ''}
{f"|B7/B8追加两seed准备时点|[唯一四模型提案]({INNOVATION_MULTI})、[新初始化/顺序及检查]({INNOVATION_MULTI_CHECKS})、[0载荷源入场]({INNOVATION_MULTI_SOURCE})|执行代码56aae5b；准备时2030/2031四任务均NOT_STARTED；实际新批准/启动另列，不改写旧提案|" if innovation_multi else ''}
{f"|B7/B8追加两seed最新获批启动|[新批准、24次RETURNED快照与资源入场]({INNOVATION_MULTI_LAUNCH})|整包IN_PROGRESS，B7/2030运行、其余三任务排队；零重放/额外重试，无新增E9或三seed结果；只读页面身份已核实|" if innovation_multi_launch else ''}
{f"|B7/B8追加两seed最新中断|[进程退出、部分账本、E6及页面修复]({INNOVATION_MULTI_STOP})|上一行仅历史启动；当前B7/2030为3,321 RETURNED/E6保存2,880/441未保存，后三项未启动。无终态收据、原因未验证；原账本SHA不变，0新训练或重放|" if innovation_multi_stop else ''}
{f"|中断原因的后续追踪与工程修复|[宿主日志/事件SHA、研究者更新确认、Job探针与独立监督器]({INNOVATION_MULTI_CAUSE})|高置信归因为更新期间宿主生命周期耦合；实际监督器/页面均已核验无Job/包身份。具体历史PID终止调用未捕获，旧初核收据不改写，未恢复训练|" if innovation_multi_cause else ''}
{f"|B7/2030恢复及后三任务准备|[唯一限额提案]({INNOVATION_MULTI_RECOVERY})、[10项针对性检查]({INNOVATION_MULTI_RECOVERY_CHECKS})|拟执行e81c6e1，尚未执行；E6记录SHA仍84dbedbc2e0af537355aca71c6ad60c763a19821e7712fabb10aa45753399e11，正式恢复前重哈希/加载各1次；新14,400更新含441重放待新批准，原E1–E6及失败段保留|" if innovation_multi_recovery else ''}
{f"|当前准确限额恢复已批准并启动|[新研究者批准、实际RETURNED与四角色无Job/包身份]({INNOVATION_MULTI_RECOVERY_LAUNCH})|e81c6e1/3314231a已单次启动；上一行只记录历史准备。B7/2030恢复IN_PROGRESS，后三项PENDING，旧E1–E6和441未保存历史不变，没有新E9或三seed结果|" if innovation_multi_recovery_launch else ''}

本地原件由研究者保存，公开源ID不是可下载原件的承诺。旧缺口保留：seed2027历史未核验尝试、旧恢复授权边界，以及未直接绑定的B0/B1历史执行commit。原始validation规范化digest、文件字节SHA和权重SHA互不替代。旧记录中的状态是当时快照，由此统一入口给出当前判断；原件未改写。

## 当前核心模型的固定E9身份

|模型|seed|固定E9权重SHA256|实际执行commit或分段|
|---|---|---|---|
{identity_table}

B4/2030矩阵终点commit为943da95，其E1继承52a8e90，E2–9由943da95执行；累计4,710实际尝试含390必要重放，有效轨迹4,320，成本见三seed收口。历史原始失败段仍保留。B5/B6本次纠正批准已消费，不允许额外重试。

## 数据与评价绑定

当前959/963人口SHA256：`{b34['data_version']['population_sha256']}`；populations文件SHA：`{b34['data_version']['populations_sha256']}`；训练统计SHA：`{b34['data_version']['statistics_sha256']}`；target QC SHA：`{b34['data_version']['target_QC_sha256']}`。2023 Train / 2024 Development、四UTC、f006回顾估计；2025冻结。B13保持既有训练集scaler（mean=271.60515414265217 K，std=19.93959597783802 K，源身份656fe7a929cbd8617b08427e8d1fa7029b26512253efb44faa576796137d4a31），不声称它在当前959重新拟合。

核心评价脚本：[{b34['evaluation_script']}]({b34['evaluation_script']})，执行版SHA256 `{b34['evaluation_script_sha256']}`；精确AUROC/AP及冻结float32阈值>0.1 mm/h口径继承[metrics.py](src/yuntapr/experimental/phase_b_v2_formal_integration_candidate/metrics.py)。Dev有效像元3,303,090、有雨407,820；不同人口和旧终点逐行保留。脚本链接指工作分支，重现执行身份必须同时使用矩阵中的执行commit及上述SHA。

## 本轮输入身份与交付校验

本轮{input_checks_text}，不重复历史129来源/126轮审查；历史收据本身不被改为本轮重新核验。以下为直接采用的公开输入字节身份：

|公开输入|SHA256|
|---|---|
{source_table}

五个统一文件及[生成器](tools/research_readiness/build_unified_delivery.py)不读取原始气象、权重或2025。运行`python tools/research_readiness/build_unified_delivery.py`可按本页嵌入快照重建四个表/报告及本索引；它继承源收据，检查{len(matrix)}个唯一实验ID、原值一致性、人口/组ID配对和三seed均值/样本标准差。它不是训练或全量实验复核命令。

导出构成：`{json.dumps(dict(counts), ensure_ascii=False, sort_keys=True)}`。存在完整指标的每个源数值叶子都保留；旧逐轮摘要数值仅转录。缺失结果不补零，q32缺失分层不反推。公开输入与本索引嵌入快照足以重建本交付，不需要公开私有目录。

|统一交付|SHA256|
|---|---|
{output_table}

本索引自身身份由Git标识，不写自引用文件哈希。旧索引、历史PUBLICATION_MANIFEST与已批准实验收据保持原字节。当前工作分支提交/推送不构成main合并或新训练批准。
'''
    (ROOT / 'EVIDENCE_INDEX.md').write_text(evidence, encoding='utf-8')
    # Publication-only checks: no private absolute paths or accidental data blobs.
    for name in ['STAGE_ACCEPTANCE.md', 'SCIENTIFIC_ANALYSIS.md', 'EVIDENCE_INDEX.md', 'EXPERIMENT_MATRIX.csv', 'METRICS.csv']:
        text = (ROOT / name).read_text(encoding='utf-8')
        assert not re.search(r'[A-Za-z]:[\\/]|/Users/|/home/', text), name
    expected_status = 'COMPLETE_TRAIN_AND_DEV_EVALUATION' if static else 'IN_PROGRESS'
    assert all(r['status'] == expected_status for r in matrix if r['model_id'] in ('B5', 'B6'))
    if not static:
        assert not any(r['model_id'] in ('B5', 'B6') and r['status'] == 'RECORDED' for r in raw_rows)
    print(json.dumps(dict(status='PASS_PUBLIC_EXPORT_ONLY', experiments=len(matrix), metrics=len(rows), records=counts,
                          historical_audits_rerun=False, optimizer_updates=0, raw_weather_reads=0, status_as_of=as_of), ensure_ascii=False))


if __name__ == '__main__':
    main()
