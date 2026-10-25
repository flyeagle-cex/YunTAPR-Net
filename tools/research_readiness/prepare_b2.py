"""Metadata-only B2 proposal and exact conservative budget. Never trains."""
from pathlib import Path
import argparse
import datetime
import hashlib
import json
import os
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.dont_write_bytecode = True
sys.path.insert(0, str(ROOT/'src'))
os.environ.update(OMP_NUM_THREADS='1', MKL_NUM_THREADS='1', CUBLAS_WORKSPACE_CONFIG=':4096:8', CUDA_VISIBLE_DEVICES='')


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('x', encoding='utf-8') as f:
        json.dump(value, f, ensure_ascii=False, indent=2, allow_nan=False)
        f.write('\n')


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--historical-preparation', required=True, type=Path)
    p.add_argument('--historical-b3-run', required=True, type=Path)
    p.add_argument('--output', required=True, type=Path)
    p.add_argument('--private-output', required=True, type=Path)
    a = p.parse_args()
    if not a.private_output.resolve().is_relative_to(ROOT/'docs/research_readiness/.local'):
        p.error('Private paths must remain in ignored local scope')
    if os.environ.get('PYTHONHASHSEED') != '2029':
        p.error('Set PYTHONHASHSEED=2029 before Python startup')

    raw_reads = []
    def audit(event, args):
        if event == 'open' and isinstance(args[0], (str, bytes, os.PathLike)):
            name = os.fsdecode(args[0]).lower()
            if name.endswith(('.nc', '.hgt', '.hgt.zip', '.h5', '.hdf5', '.pt', '.pth', '.ckpt')):
                raw_reads.append(name)
                raise PermissionError('Metadata preparation forbids weather/checkpoint payload reads')
    sys.addaudithook(audit)
    import torch
    torch.set_num_threads(1)
    from yuntapr.experimental.core_innovation.stage4.data import PopulationPlan, read, sha
    from yuntapr.experimental.core_innovation.stage4.launch import preparation
    from yuntapr.experimental.core_innovation.stage4.engine import epoch_order, lr_for_update
    from yuntapr.experimental.core_innovation.stage3.planning import digest, utc
    from yuntapr.experimental.research_readiness.b2 import fresh_b2, STEM_RULE

    old = read(a.historical_preparation)
    old_body = dict(old)
    old_hash = old_body.pop('preparation_sha256')
    if digest(old_body) != old_hash:
        raise ValueError('Historical preparation digest differs')
    inputs = old['private_inputs']
    plan = PopulationPlan(inputs['stage3_run'], inputs['request'], root=ROOT)
    prepared = preparation(plan, inputs['stage3_run'], inputs['request'], inputs['mask_read_ledger'])
    # JSON stores ID tuples as lists; compare the canonical identity, not types.
    if prepared['data'] != old['data'] or digest(prepared['roles']) != digest(old['roles']) or prepared['budget'] != old['budget']:
        raise ValueError('Historical data population or conservative read scopes drifted')
    train_ids, dev_ids = plan.ids('Train'), plan.ids('Development')
    if set(train_ids) & set(dev_ids):
        raise ValueError('Split overlap')
    time_checks = {}
    for role, year in (('Train', 2023), ('Development', 2024)):
        count = 0
        for sid, row in plan.rows[role].items():
            analysis = utc(row['analysis_time'])
            if utc(sid).year != year or analysis.year != year or analysis.hour not in (0, 6, 12, 18) or not 3 <= analysis.month <= 10:
                raise ValueError('Forbidden year/calendar or drifted f006 population')
            for i, offset in enumerate((60, 50, 40, 30, 20, 10)):
                _, source = plan.sat[row[f'slot_{i}_nominal']]
                nominal = utc(source['nominal'])
                if (analysis-nominal).total_seconds() != offset*60 or utc(source['obs_end']) > analysis:
                    raise ValueError('Observation timing crossed analysis endpoint')
                count += 1
        time_checks[role] = dict(scenes=len(plan.ids(role)), checked_observation_exposures=count, year=year)

    b2, init = fresh_b2(2029, stem_rule=STEM_RULE, root=ROOT)
    historical_init = read(a.historical_b3_run/'paired_initial_identity.json')
    if init['b3_reference_sha256'] != historical_init['B3']['full_state_sha256']:
        raise ValueError('Fresh B3 no longer reproduces actual seed2029 initializer')
    orders = read(a.historical_b3_run/'paired_orders.json')
    for e in range(1, 10):
        current = epoch_order(train_ids, 2029, e)
        if list(current) != orders[str(e)]['ids'] or digest(current) != orders[str(e)]['sha256']:
            raise ValueError('Sample-order drift')
    scales = {k: dict(mean=v.mean, std=v.std, fit_years=list(v.fit_years), fit_role=v.fit_role,
                      population_id=v.population_id) for k, v in plan.spectral.items()}
    per_role = {role: {k: value[k] for k in ('file_count', 'bytes_per_pass', 'source_manifest_sha256', 'by_kind')}
                for role, value in prepared['roles'].items()}
    model_bytes = sum(t.numel()*t.element_size() for t in b2.state_dict().values())
    budget = dict(status='PROPOSED_NOT_AUTHORIZED', optimizer_update_cap=4320, replay_allowance=0,
                  train_passes=9, development_passes=9,
                  logical_source_read_instances=9*sum(v['file_count'] for v in per_role.values()),
                  logical_source_bytes=9*sum(v['bytes_per_pass'] for v in per_role.values()),
                  cached_IMERG_limit_bytes=512*1024**2, scopes=per_role,
                  max_wall_seconds=21600, minimum_workspace_bytes=24*1024**3,
                  checkpoint_tensor_bytes_lower_bound_per_epoch=3*model_bytes,
                  nine_LAST_tensor_bytes_lower_bound=9*3*model_bytes,
                  checkpoint_python_rng_receipts_and_SQLite_overhead='NOT_INCLUDED_IN_LOWER_BOUND',
                  metric_SQLite_hard_ceiling_per_group=256*1024**2,
                  metric_groups_per_epoch=6, nine_epoch_metric_SQLite_sum_ceiling=9*6*256*1024**2,
                  notes=['Conservative inherited six-frame loader includes GFS for B2 without feeding it to the model.',
                         'No source verification pass, retry, replay, normalization refit or extra endpoint inference is included.',
                         'Byte cap describes source payload delivered to Python, not physical disk sectors or monetary cost.'])
    code_files = [p for folder in ('src/yuntapr/experimental/research_readiness', 'tools/research_readiness') for p in (ROOT/folder).glob('*.py')]
    code = {p.relative_to(ROOT).as_posix(): sha(p) for p in sorted(code_files)}
    proposal = dict(status='SCIENTIFIC_PROTOCOL_FROZEN_WAITING_FINAL_START', formal_training_status='NOT_STARTED',
                    as_of=datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).isoformat(timespec='seconds'),
                    base_commit=subprocess.check_output(['git', '-C', str(ROOT), 'rev-parse', 'HEAD'], text=True).strip(),
                    reference_execution_commit='7fa609e89bdb8b744bb0e7eebc9e7b5c3a703e35',
                    public_main_commit='6c505d0ec63ed39f679720b82a65f601139dcd35',
                    config=dict(model='B2', seed=2029, loss='E0', epochs=9, batch=2, validation_batch=8,
                                endpoint='FIXED_EPOCH_9_LAST', optimizer='AdamW', lead_hours=6, mode='retrospective',
                                input_channels=7, input_offset_before_analysis_minutes=10, stem_rule=STEM_RULE,
                                initialization_status='FROZEN_BY_RESEARCHER_20261025', normalization='REUSE_B3_TRAIN_ONLY_SCALERS_NO_REFIT',
                                lr_warmup_updates=480, lr_original_horizon_updates=24000,
                                lr_first=lr_for_update(1, steps_per_epoch=480), lr_last=lr_for_update(4320, steps_per_epoch=480)),
                    data=plan.identity, split_and_observation_timing=time_checks, spectral_scalers=scales,
                    input_dimension_difference=init, train_orders_9_epochs_match_historical_B3=True,
                    b2_parameter_count=sum(p.numel() for p in b2.parameters()),
                    dropout_modules=sum(isinstance(m, torch.nn.Dropout) for m in b2.modules()),
                    budget=budget, code_sha256=code, formal_authorization=False,
                    raw_weather_reads=0, checkpoint_loads=0, optimizer_updates=0,
                    remaining_runtime_checks=['Actual source availability/SHA under approved read budget',
                                              'Formal training/evaluation end-to-end not executed',
                                              'GPU resource admission and observed runtime forecast required at execution'])
    proposal['proposal_sha256'] = digest(proposal)
    private = dict(proposal_sha256=proposal['proposal_sha256'], historical_preparation=str(a.historical_preparation.resolve()),
                   historical_b3_run=str(a.historical_b3_run.resolve()), prepared=prepared)
    write(a.private_output, private)
    write(a.output, proposal)
    print(json.dumps(dict(status=proposal['status'], optimizer_updates=0, raw_weather_reads=0,
                          b3_initialization_match=True, all_nine_orders_match=True, budget=budget), indent=2))


if __name__ == '__main__':
    main()
