"""Extract public, bounded evidence from existing results; no training imports.

Input directories are explicit CLI arguments. Only result JSON/CSV, receipts,
configuration metadata and read-only SQLite ledgers are opened. Never opens a
weather source or checkpoint payload. Original files are never written.
"""
from __future__ import annotations
import argparse
import csv
import hashlib
import json
from pathlib import Path
import re
import sqlite3
import subprocess
from contextlib import closing
from datetime import datetime, timedelta, timezone

REPO = 'https://github.com/flyeagle-cex/YunTAPR-Net'
SNAPSHOT_COMMIT = '0ccb3e26e2d50494aba07788fa94dd40ec89b4aa'
EXECUTION_COMMIT = '7fa609e89bdb8b744bb0e7eebc9e7b5c3a703e35'
AUDIT_AS_OF = datetime.now(timezone(timedelta(hours=8))).isoformat(timespec='seconds')
NA = 'NOT_AVAILABLE'
METRICS = ('core_fp64', 'brier', 'auroc', 'average_precision', 'conditional_pinball',
           'q32_coverage', 'q32_signed_bias', 'q32_absolute_error')


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'),
                                    allow_nan=False).encode()).hexdigest()


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def clean(value):
    """Exclude machine paths, traceback strings and other runtime-private fields."""
    if isinstance(value, dict):
        return {k: clean(v) for k, v in value.items()
                if not any(x in k.lower() for x in ('absolute_local_path', 'traceback', 'checkpoint_root', 'resume_journal'))
                and not (isinstance(v, str) and re.search(r'(?<![A-Za-z])[A-Za-z]:[\\/]', v))}
    if isinstance(value, list):
        return [clean(v) for v in value]
    return value


class Extractor:
    def __init__(self, source, launch, output):
        self.source, self.launch, self.output = map(lambda p: Path(p).resolve(), (source, launch, output))
        self.sources, self.rows, self.epochs, self.strata, self.quantiles = [], [], [], [], []
        self.evidence = self.output / 'evidence'
        self.evidence.mkdir(parents=True, exist_ok=True)

    def read(self, rel, *, base=None, alias=None):
        root = base or self.source
        path = root / rel
        if path.suffix.lower() not in ('.json', '.csv', '.sqlite'):
            raise ValueError('Only declared metadata sources are allowed')
        raw = path.read_bytes()
        sid = alias or rel
        private = alias is not None
        source = dict(source_id=sid, bytes=len(raw), sha256=sha(raw),
                      visibility='LOCAL_ONLY' if private else 'PUBLIC_EXISTING',
                      url=None if private else f'{REPO}/blob/{SNAPSHOT_COMMIT}/{rel}')
        if source not in self.sources:
            self.sources.append(source)
        if path.suffix == '.json':
            return json.loads(raw), source
        return list(csv.DictReader(raw.decode('utf-8-sig').splitlines())), source

    def write(self, rel, value):
        path = self.output / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + '\n', encoding='utf-8')

    def save_csv(self, rel, rows, fields):
        with (self.output / rel).open('w', encoding='utf-8', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=fields, extrasaction='ignore', lineterminator='\n')
            writer.writeheader()
            writer.writerows({k: NA if row.get(k) is None else row.get(k, NA) for k in fields} for row in rows)

    def summary(self, summary):
        result = clean(summary)
        if 'coverage' in result:
            result['q32_coverage'] = result['coverage'][-1]
        return result

    def legacy_metrics(self, m):
        return dict(core_fp64=m.get('global_val_core_loss'), brier=m.get('Brier_Score'),
                    auroc=m.get('AUROC'), average_precision=m.get('Average_Precision'),
                    conditional_pinball=m.get('conditional_mean_pinball'),
                    q32_coverage=(m.get('per_tau_conditional_coverage') or [None])[-1],
                    POD=m.get('POD', NA), FAR=m.get('FAR', NA), CSI=m.get('CSI', NA),
                    diagnostic_proxy_metric=m.get('DIAGNOSTIC_PROXY_METRIC', NA))

    def add_row(self, model, eid, seed, stage, epochs, steps, status, checkpoint, metrics,
                source_ids, *, arm='E0', train=10455, dev=10501, selection='FIXED_EPOCH_9', notes=''):
        self.rows.append(dict(model_id=model, experiment_id=eid, seed=seed, phase=stage,
            config=stage + '_' + arm, loss_arm=arm,
            dataset_split='2023_Train/2024_Development/2025_NOT_EVALUATED',
            train_scenes=train, dev_scenes=dev, epochs=epochs, global_steps=steps,
            status=status, metrics_path='evidence/experiments.json#' + eid,
            checkpoint_reference=checkpoint or NA, checkpoint_selection=selection,
            evidence_path='EVIDENCE_INDEX.md', source_ids=source_ids,
            verified_at=AUDIT_AS_OF, notes=notes, metrics=metrics))

    def append_numeric(self, eid, model, seed, arm, epoch, train, dev, checkpoint, source_id):
        s = self.summary(dev['summary'])
        self.epochs.append(dict(experiment_id=eid, model_id=model, seed=seed, loss_arm=arm,
            epoch=epoch, train=clean(train), development=s,
            development_ids_sha256=dev['ids_sha'], development_receipt_sha256=dev['receipt_sha'],
            checkpoint=clean(checkpoint), source_id=source_id))
        return s

    def phase_b(self):
        manifest, _ = self.read('docs/phase_b_v2_seed2026_scientific_analysis/v1/manifest.json')
        six26 = {n: h for n, h in manifest['public_sources_and_local_aggregate_receipt_sha256'].items()
                 if n.endswith('s2026.json')}
        assert len(six26) == 6
        receipt_audit, _ = self.read('docs/audits/20261021_completed_work_review/evidence/seed2026_receipt_audit.json')
        completed27, _ = self.read('docs/phase_b_v2_seed2027_completion/20261024/execution_status.json')
        quota26 = receipt_audit['completed_status']['quota']
        self.write('evidence/historical_campaigns.json', dict(seed2026=clean(receipt_audit['completed_status']),
                                                            seed2027=clean(completed27)))
        sources = [(n, h, 2026) for n, h in six26.items()]
        sources += [(f'docs/phase_b_v2_seed2027_completion/20261024/results/{r}.json', None, 2027)
                    for r in completed27['runs']]
        index27, _ = self.read('docs/phase_b_v2_seed2027_completion/20261024/epoch_receipt_index.json')
        reports26 = {r.get('run_id', r.get('id')): r for r in receipt_audit['reports']}
        # The source audit report names are inspected rather than inferred.
        if None in reports26:
            reports26 = {r.get('run', r.get('run_id', r.get('id'))): r for r in receipt_audit['reports']}
        for rel, expected, seed in sources:
            result, source = self.read(rel)
            if expected:
                assert source['sha256'] == expected, rel
            eid = result['run_id']; model = 'B0' if eid.startswith('B0') else 'B1'; arm = eid.split('__')[1]
            assert result['status'] == 'COMPLETE' and result['updates'] == 47052
            assert [e['epoch'] for e in result['epochs']] == list(range(1, 10))
            quota = quota26 if seed == 2026 else completed27['quota']
            final = next(r for r in quota['runs'] if r['id'] == eid)
            for e in result['epochs']:
                dev = e['development']; body = dict(dev); h = body.pop('receipt_sha')
                assert digest(body) == h, (eid, e['epoch'], 'validation digest')
                assert dev['complete'] and dev['summary']['scenes'] == 10501
                assert e['train']['scenes'] == 10455 and e['train']['batches'] == 5228
                if seed == 2027:
                    entry = next(x for x in index27['epochs'] if x['run_id'] == eid and x['epoch'] == e['epoch'])
                    assert entry['result_file_sha256'] == source['sha256']
                    assert entry['validation_receipt_sha256'] == h
                    assert entry['last_payload_sha256'] == e['checkpoint']['payload_sha256']
                s = self.append_numeric(eid, model, seed, arm, e['epoch'], e['train'], dev,
                                        e['checkpoint'], source['source_id'])
            assert final['last_sha'] == result['epochs'][-1]['checkpoint']['payload_sha256']
            self.add_row(model, eid, seed, 'PHASE_B_V2', 9, 47052, 'COMPLETE_TRAIN_AND_DEV_EVALUATION',
                         final['last_sha'], s, [source['source_id']], arm=arm,
                         notes='Nine-epoch retained trajectory; campaign-level abandoned/uncertain attempts are separate. Development only.')

    def seed2029(self):
        rel = 'docs/core_stage4/.local/seed2029_recovery1_20261024_v1'
        parent_rel = 'docs/core_stage4/.local/seed2029_formal_20261024_v1'
        completion, completion_source = self.read(rel + '/completion.json', alias='SEED2029_COMPLETION')
        assert completion['status'] == 'COMPLETE'
        assert (completion['updates'], completion['cumulative_attempts'], completion['replayed_updates']) == (8640, 9120, 480)
        ledger = self.source / rel / 'updates.sqlite'
        parent_ledger = self.launch / parent_rel / 'updates.sqlite'
        snapshots = {}
        for label, path in (('recovery', ledger), ('original_failed_segment', parent_ledger)):
            before = sha(path.read_bytes())
            with closing(sqlite3.connect(path.resolve().as_uri() + '?mode=ro', uri=True)) as db:
                db.execute('PRAGMA query_only=ON')
                snapshots[label] = dict(rows=[list(row) for row in db.execute(
                    'SELECT model,state,COUNT(*),MIN(u),MAX(u) FROM updates GROUP BY model,state')],
                    identity=clean(json.loads(db.execute('SELECT value FROM identity').fetchone()[0])))
            assert before == sha(path.read_bytes()), 'Read-only ledger changed'
            snapshots[label]['source_sha256'] = before
        assert snapshots['recovery']['rows'] == [['B3', 'RETURNED', 2880, 1441, 4320], ['B4', 'RETURNED', 4320, 1, 4320]]
        assert snapshots['original_failed_segment']['rows'] == [['B3', 'RETURNED', 1920, 1, 1920]]
        init, _ = self.read(rel + '/paired_initial_identity.json', alias='SEED2029_INITIAL_IDENTITIES')
        assert init['B3']['common_sha256'] == init['B4']['common_sha256']
        paired_epochs = {}
        final_groups = {}
        io = dict(opened_files=0, delivered_bytes=0, reserved_bytes=0, passes=0)
        for model in ('B3', 'B4'):
            eid = f'{model}__E0__s2029__f006'
            for epoch in range(1, 10):
                inherited = model == 'B3' and epoch <= 3
                base, folder = (self.launch, parent_rel) if inherited else (self.source, rel)
                dev, source = self.read(f'{folder}/{model}_development_{epoch:02d}.json', base=base,
                                        alias=f'SEED2029_{model}_DEV_E{epoch:02d}')
                train, _ = self.read(f'{folder}/{model}_train_{epoch:02d}.json', base=base,
                                     alias=f'SEED2029_{model}_TRAIN_E{epoch:02d}')
                receipt, _ = self.read(f'{folder}/{model}_LAST_epoch_{epoch:02d}.receipt.json', base=base,
                                       alias=f'SEED2029_{model}_LAST_E{epoch:02d}')
                assert digest(dev) == receipt['validation_receipt_sha256']
                assert receipt['epoch'] == epoch and receipt['updates'] == epoch * 480
                assert train['scenes'] == 959 and train['batches'] == 480 and train['updates'] == epoch * 480
                for name, group in dev['groups'].items():
                    body = dict(group); h = body.pop('receipt_sha')
                    assert digest(body) == h and group['complete']
                assert dev['groups']['all']['summary']['scenes'] == 963
                envelope = dict(summary=dev['groups']['all']['summary'], ids_sha=dev['population_ids_sha256'],
                                receipt_sha=digest(dev))
                s = self.append_numeric(eid, model, 2029, 'E0', epoch, train, envelope, receipt, source['source_id'])
                paired_epochs[model, epoch] = (train['train_order_sha256'], dev['population_ids_sha256'], dev['partition_sha256'])
                if epoch == 9:
                    final_groups[model] = {name: dict(summary=self.summary(group['summary']), ids_sha256=group['ids_sha'])
                                           for name, group in dev['groups'].items()}
            self.add_row(model, eid, 2029, 'CORE_F006_MEE13' if model == 'B4' else 'CORE_F006_SPECTRAL',
                         9, 4320, 'COMPLETE_TRAIN_AND_DEV_EVALUATION', receipt['checkpoint_sha256'], s,
                         [completion_source['source_id'], source['source_id']], train=959, dev=963,
                         notes='B3 7x6; B4 adds MEE13 width16 target residual. Paired actual attempts 9120 include 480 approved replay; no BEST.')
        assert all(paired_epochs['B3', e] == paired_epochs['B4', e] for e in range(1, 10))
        # Actual I/O includes the abandoned E4 passes, inherited E1..E3, all
        # recovery passes and the single authorized failed-source verification.
        for base, folder in ((self.launch, parent_rel), (self.source, rel)):
            for p in sorted((base / folder).glob('*_reads_*/pass_receipt.json')):
                v, _ = self.read(str(p.relative_to(base)).replace('\\', '/'), base=base,
                                  alias='SEED2029_IO_' + ('PARENT_' if base == self.launch else 'RECOVERY_') + p.parent.name)
                a = v['actual_reads']
                for key in ('opened_files', 'delivered_bytes', 'reserved_bytes'):
                    io[key] += a[key]
                io['passes'] += 1
        v, _ = self.read(rel + '_source_verification/source_verification_receipt.json', alias='SEED2029_SINGLE_SOURCE_VERIFICATION')
        for key in ('opened_files', 'delivered_bytes', 'reserved_bytes'):
            io[key] += v[key]
        assert (io['opened_files'], io['delivered_bytes'], io['reserved_bytes']) == (299968, 1003563940849, 1003568959114)
        checkpoint_metadata = {m: dict(present=(self.source/rel/f'{m}_LAST_epoch_09.pt').is_file(),
            bytes=(self.source/rel/f'{m}_LAST_epoch_09.pt').stat().st_size,
            sha_status='RECEIPT_SHA_INHERITED_NOT_REHASHED_IN_THIS_AUDIT') for m in ('B3','B4')}
        self.write('evidence/seed2029_execution.json', dict(completion=clean(completion), ledgers=snapshots,
            paired_initialization=init, all_nine_train_orders_and_dev_partitions_equal=True,
            paired_effective_updates=8640, approved_replayed_updates=480, actual_update_attempts=9120,
            actual_io=io, executed_commit=EXECUTION_COMMIT, new_optimizer_updates_in_this_audit=0,
            checkpoint_payloads_opened_in_this_audit=0, checkpoint_payload_file_metadata=checkpoint_metadata,
            original_sources='LOCAL_ONLY; public metadata extracts and hashes'))
        self.write('evidence/seed2029_groups.json', final_groups)
        difference, _ = self.read(rel + '/paired_difference_09.json', alias='SEED2029_PAIRED_DIFFERENCE_E09')
        for name in final_groups['B3']:
            a, b = (final_groups[m][name]['summary'] for m in ('B3', 'B4'))
            for metric in ('brier','auroc','average_precision','conditional_pinball','q32_signed_bias','core_fp64'):
                assert b[metric]-a[metric] == difference['groups'][name][metric]
        self.write('evidence/seed2029_paired_difference.json', difference)
        failed, failed_source = self.read(parent_rel + '/failure.json', base=self.launch, alias='SEED2029_ORIGINAL_FAILURE')
        self.add_row('B3', 'B3__E0__s2029__f006__original_failed_segment', 2029, 'CORE_F006_ORIGINAL_ATTEMPT',
            3, 1920, 'FAILED_SUPERSEDED_BY_APPROVED_LAST_RECOVERY',
            '9d4c8a4d3035c0b8327812466dc111afa72c074afb8612bf30f32a25bed7fc8e', {},
            [failed_source['source_id']], train=959, dev=963, selection='LAST_SEALED_EPOCH_3',
            notes='1920 returned attempts; only 1440 belong to sealed E3 trajectory. E4 validation failed; not a separate independent replicate.')

    def phase_a(self):
        packet, source = self.read('docs/v2_phase_a_review/paired_packets/run_20261009T072307_459014Z/paired_comparison_packet.json')
        closure, _ = self.read('docs/v2_phase_a_review/final_completion/run_20261009T083217_518899Z/FINAL_COMPLETION_AUDIT.json')
        assert closure['FORMAL_TRAINING_COMPLETED'] and not closure['FORMAL_TRAINING_RUNNING']
        for name, v in packet['models'].items():
            model = 'B0' if name.startswith('B0') else 'B1'; last = closure['models'][name]
            assert last['completed_epoch'] == 17 and last['BEST']['epoch'] == 9
            metrics = self.legacy_metrics(v['metrics'])
            self.add_row(model, name + '__PHASE_A_V2__s2026', 2026, 'PHASE_A_V2', 17, 88876,
                'COMPLETE_EARLY_STOP_AND_BEST_DEV_EVALUATION', last['BEST']['sha256'], metrics,
                [source['source_id']], selection='BEST_EPOCH_9_CORE_ONLY',
                notes='17 completed epochs; selected BEST epoch9. Same seed/config E0 figures are not a new independent seed relative to Phase-B E0.')
        self.write('evidence/phase_a_v2_closure.json', dict(status=closure['status'],
            models=clean(closure['models']), frozen_identities=closure['frozen_identities'],
            counter_reconciliation={k:clean(v['formal_counters']['all_attempt_optimizer_reconciliation'])
                                    for k,v in packet['models'].items()}))

    def legacy(self):
        folders = [('B0', 'b0_phase_a', 'run_20261001T035003_243409Z'),
                   ('B0', 'b0_phase_b_finalfit', 'run_20261002T035929_487644Z'),
                   ('B0', 'b0_matched_phase_a', 'run_20261003T093519_542831Z'),
                   ('B1', 'b1_phase_a', 'run_20261003T093522_417735Z'),
                   ('B0', 'b0_matched_phase_b_finalfit', 'run_20261005T103053_888886Z')]
        pair, pair_source = self.read('docs/paired_phase_a_authorized/runs/run_20261003T085834_735920Z/paired_comparison_metrics.json')
        for model, kind, run in folders:
            folder = f'docs/formal_training/{kind}/runs/{run}'
            status, source = self.read(folder + '/final_status.json')
            metrics = {}; steps = status.get('global_update', status.get('FORMAL_OPTIMIZER_STEPS'))
            epochs = status.get('completed_epoch', status.get('TOTAL_COMPLETED_EPOCHS'))
            checkpoint = status.get('BEST', {}).get('sha256', status.get('FINAL_CHECKPOINT_SHA256', status.get('BEST_CHECKPOINT_SHA256')))
            selection = 'BEST_NOT_AVAILABLE' if 'finalfit' in kind else 'BEST_EPOCH_' + str(status.get('selected_best_epoch', status.get('SELECTED_CHECKPOINT_EPOCH')))
            state = 'HISTORICAL_COMPLETE_TRAINING_ONLY' if 'finalfit' in kind else 'HISTORICAL_COMPLETE_AND_DEV_EVALUATION'
            train, dev = (11720,11727) if kind == 'b0_phase_a' else (10455,10501)
            seed = 2026 if 'phase_a' in kind else 'NOT_VERIFIED'
            if kind == 'b0_phase_a':
                training, _ = self.read(folder + '/training_history.csv')
                steps = int(training[-1]['global_update_end'])
                best, _ = self.read(folder + f"/epoch_{status['SELECTED_CHECKPOINT_EPOCH']:03d}.json")
                metrics = self.legacy_metrics(best['validation'])
            elif kind in ('b0_matched_phase_a', 'b1_phase_a'):
                metrics = self.legacy_metrics(pair['B0_MATCHED' if model == 'B0' else 'B1'])
            elif status.get('status') == 'FORMAL_EXECUTION_FAILED':
                state = 'HISTORICAL_FAILED_QUANTILE_OVERFLOW'; selection='LAST_VERIFIED_EPOCH_4'
                checkpoint = clean(status.get('last_verified_checkpoint'))
                train, dev = 'NOT_VERIFIED', 'NOT_AVAILABLE'
            elif kind == 'b0_phase_b_finalfit':
                train, dev = 23447, 'NOT_AVAILABLE'
            self.add_row(model, kind + '__' + run, seed, 'LEGACY_' + kind.upper(), epochs, steps, state,
                         checkpoint, metrics, [source['source_id']], train=train, dev=dev,
                         selection=selection, arm='LEGACY_NOT_EQUIVALENT_TO_V2_ARMS',
                         notes='Historical version; no direct comparison to current B3/B4. Full checkpoint payloads not reopened. FinalFit history is not a new authorization.')

    def data_and_modules(self):
        stage3, _ = self.read('docs/core_stage3/execution_summary/evidence.json')
        launch, _ = self.read('docs/core_stage4/launch_seed2029.json')
        catalogue, _ = self.read('docs/final_test_b0/catalogue_gate_v1_1/catalogue_only_runs/run_20261003T015507_526850Z/final_status.json')
        dem, _ = self.read('stage0-b0-evidence/evidence/outputs/stage0_spatial_static_closeout/run_20260928T095818_821492Z/DEM/dem_audit_summary.json')
        core, _ = self.read('docs/core_innovation/test_runs/20261024T015827Z/summary.json')
        delta, _ = self.read('docs/core_stage2/evidence_index_v2.json')
        assert core['success'] and core['tests_run']==52
        assert delta['unique_delta_tests']==20
        assert stage3['populations']['Train']['actual_scenes']==959
        assert stage3['populations']['Development']['actual_scenes']==963
        assert stage3['joint_population_sha256']==launch['config']['population_sha256']
        assert stage3['private_receipt_sha256']['train_statistics.json']==launch['data']['statistics_sha256']
        selected_catalogue = {k:v for k,v in catalogue.items() if not isinstance(v,(dict,list))}
        selected_catalogue['raw_access_telemetry']=catalogue['raw_access_telemetry']
        self.write('evidence/data_and_modules.json', dict(
            stage3=stage3, seed2029_configuration=launch['config'], seed2029_data_identity=launch['data'],
            historical_2025_catalogue_only=clean(selected_catalogue),
            all_modalities_2025_completeness='NOT_VERIFIED; old catalogue is not a B3/B4/MEE final-test population',
            inherited_dem_audit=dem, core_52_existing_checks=core, stage2_20_existing_delta_checks=delta,
            checks_rerun=False, DOTE_DTFM_formal_training=False, independent_physical_validation='NOT_AVAILABLE'))

    def finish(self):
        for row in self.rows:
            s = row['metrics']
            if 'rain_strata' in s:
                lower = .1
                for band in s['rain_strata']:
                    self.strata.append(dict(experiment_id=row['experiment_id'], lower=lower, upper=band['upper'] if band['upper'] is not None else 'inf',
                        n=band['n'], conditional_pinball=band['conditional_pinball']))
                    lower = band['upper']
            for i, tau in enumerate(s.get('tau', [])):
                self.quantiles.append(dict(experiment_id=row['experiment_id'], index=i+1, tau=tau,
                    n_rain=s['n_rain'], covered=s['covered'][i], coverage=s['coverage'][i], gap=s['coverage'][i]-tau))
        self.write('evidence/experiments.json', dict(as_of=AUDIT_AS_OF, scope='Completed and failed formal runs found in declared evidence roots',
                                                    experiments=self.rows))
        self.write('evidence/epoch_receipts.json', dict(scope='Numeric extracts; original full JSON and checkpoint payloads remain at their declared visibility',
                                                      epochs=self.epochs))
        self.write('evidence/source_manifest.json', dict(source_snapshot_commit=SNAPSHOT_COMMIT, sources=self.sources))
        fields = ('model_id','experiment_id','seed','phase','config','loss_arm','dataset_split','train_scenes','dev_scenes',
                  'epochs','global_steps','status','metrics_path','checkpoint_reference','checkpoint_selection','evidence_path','verified_at','notes')
        matrix = [{**r, 'checkpoint_reference': json.dumps(r['checkpoint_reference']) if isinstance(r['checkpoint_reference'],dict) else r['checkpoint_reference']} for r in self.rows]
        self.save_csv('EXPERIMENT_MATRIX.csv',matrix,fields)
        self.save_csv('endpoint_metrics.csv',[dict(experiment_id=r['experiment_id'], **{k:r['metrics'].get(k) for k in METRICS},
                    POD=r['metrics'].get('POD'), FAR=r['metrics'].get('FAR'), CSI=r['metrics'].get('CSI'),
                    diagnostic_proxy_metric=json.dumps(r['metrics'].get('diagnostic_proxy_metric',NA))) for r in self.rows],
                    ('experiment_id',*METRICS,'POD','FAR','CSI','diagnostic_proxy_metric'))
        self.save_csv('epoch_metrics.csv',[dict(experiment_id=e['experiment_id'], epoch=e['epoch'],
            training_loss=e['train'].get('weighted_training_mean',e['train'].get('weighted_mean')),
            **{k:e['development'].get(k) for k in METRICS}) for e in self.epochs], ('experiment_id','epoch','training_loss',*METRICS))
        self.save_csv('rain_strata.csv',self.strata,('experiment_id','lower','upper','n','conditional_pinball'))
        self.save_csv('quantile_calibration.csv',self.quantiles,('experiment_id','index','tau','n_rain','covered','coverage','gap'))
        print(json.dumps(dict(experiments=len(self.rows),numeric_epoch_receipts=len(self.epochs),sources=len(self.sources),
                              raw_weather_reads=0,checkpoint_payload_reads=0,new_optimizer_updates=0)))


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--source-repo',required=True,type=Path)
    p.add_argument('--launch-repo',required=True,type=Path)
    p.add_argument('--output',required=True,type=Path)
    a=p.parse_args()
    if subprocess.check_output(['git','-C',str(a.source_repo),'rev-parse','HEAD'],text=True).strip()!=SNAPSHOT_COMMIT:
        raise ValueError('Source evidence checkout identity differs')
    x=Extractor(a.source_repo,a.launch_repo,a.output)
    x.phase_b();x.seed2029();x.phase_a();x.legacy();x.data_and_modules();x.finish()


if __name__=='__main__':main()
