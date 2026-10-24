"""Candidate population metadata join and independent budget, no raw data I/O."""
from check_connections import ROOT, MAIN_INDEX, THERMO_INDEX, FREEZE, PINS, pinned, parse_utc
from pathlib import Path
from datetime import datetime, timedelta, timezone
import argparse, csv, json, math, re, sys
from yuntapr.experimental.core_innovation.stage2.budget import paired_budget, resources


if __name__ == '__main__':
    p = argparse.ArgumentParser(); p.add_argument('--probe', type=Path, required=True); p.add_argument('--output', type=Path, required=True)
    p.add_argument('--validation-probe', type=Path)
    a = p.parse_args()
    if not a.output.resolve().is_relative_to(ROOT/'docs/core_stage2/.local') or a.output.exists():
        raise PermissionError('New metadata population results remain local')
    identities = {}
    for kind, path in (('main', MAIN_INDEX), ('thermo', THERMO_INDEX)):
        found = set()
        with (ROOT/path).open(encoding='utf-8-sig', newline='') as f:
            for row in csv.DictReader(f):
                name = Path(row['relative_path']).name
                m = re.fullmatch(r'gfs_(?:thermo_)?0p25_(202[34]\d{6})_f(000|003|006)\.nc', name)
                if m and int(row['size_bytes']) > 0:
                    init = datetime.strptime(m[1], '%Y%m%d%H').replace(tzinfo=timezone.utc)
                    if 3 <= init.month <= 10: found.add((init, int(m[2])))
        identities[kind] = found
    both = identities['main'] & identities['thermo']; by_valid = {}
    for init, lead in both: by_valid.setdefault(init+timedelta(hours=lead), []).append((init, lead))
    populations = {}; matched = {}
    for year in (2023, 2024):
        with pinned(ROOT/FREEZE/f'b1_{year}_formal_manifest.csv', PINS['B1', year]).open(encoding='utf-8-sig', newline='') as f:
            rows = list(csv.DictReader(f))
        candidates = [r for r in rows if any(init <= parse_utc(r['analysis_time']) for init, lead in by_valid.get(parse_utc(r['analysis_time']), []))]
        populations[year] = dict(inherited_B1_population=len(rows), exact_valid_time_GFS_metadata_upper_bound=len(candidates),
            fully_seven_band_verified_population=None, normalization_ready=False, status='UPPER_BOUND_ONLY_NOT_FORMAL_POPULATION')
        matched[year] = len(candidates)
    probe = json.loads(a.probe.read_text(encoding='utf-8'))
    if probe['status'] != 'PASS': raise ValueError('Measured synthetic model evidence required')
    validation_peaks = {}
    if a.validation_probe:
        vp = json.loads(a.validation_probe.read_text(encoding='utf-8'))
        if vp['status'] != 'PASS': raise ValueError('Validation probe did not pass')
        validation_peaks = {r['kind']: r['peak_allocated_bytes'] for r in vp['inference']}
    full_ceiling = paired_budget(train_population=10455, dev_population=10501, epochs=9, physical_batch=2, validation_batch=8)
    exact_ceiling = paired_budget(train_population=matched[2023], dev_population=matched[2024], epochs=9, physical_batch=2, validation_batch=8)
    entry_budget = paired_budget(train_population=matched[2023], dev_population=matched[2024], epochs=1, physical_batch=2, validation_batch=8)
    model_resources = {}
    for record in probe['candidates']:
        pilot = record['kind'] == 'B1_GFS_PILOT'
        model_resources[record['kind']] = resources(parameters=record['parameters'],
            measured_peak_allocated=record['peak_allocated_bytes'], measured_peak_reserved=record['peak_reserved_bytes'],
            measured_seconds=record['elapsed_seconds'], updates=32 if pilot else exact_ceiling['optimizer_updates_per_run'],
            validation_batches=2 if pilot else math.ceil(matched[2024]/8)*9,
            validation_peak_allocated=validation_peaks.get(record['kind']))
        if pilot:
            model_resources[record['kind']]['proxy_kind'] = '32_FORWARD_BACKWARD_INTERFACE_CALLS_ZERO_OPTIMIZER_UPDATES'
    result = dict(status='CANDIDATE_REQUIRES_RESEARCHER_FREEZE_AND_NEW_AUTHORIZATION', populations=populations,
        exact_valid_pair_9epoch_budget=exact_ceiling, exact_valid_pair_1epoch_entry_budget=entry_budget,
        inherited_population_9epoch_ceiling_if_hold_policy_approved=full_ceiling, model_resources=model_resources,
        A=dict(name='B3', input='7 channels x 6 slots, native 501x501', population='Must use the SAME verified B3/GFS joint IDs as B4 for paired inference'),
        B=dict(name='B4', input='B3 + 11 normalized GFS values and 11 masks', population='Intersection of joint seven-band evidence and approved vintage/time policy'),
        C=dict(name='B1_GFS_INTERFACE_PILOT_NOT_B4', proposed_scene_cap=64, proposed_dev_cap=16, optimizer_updates=0,
            training_authorization=False, required_new_raw_data_reads='Not performed; existing small-sample budget remains binding'),
        temporal_options=['exact_valid_equals_analysis: no temporal hold, smaller matched population',
                          'latest_valid_not_after_analysis_with_explicit_max_age: broader population, new stale-field assumption requiring freeze'],
        formal_ready=False, actual_training_launched=False, raw_weather_reads=0, raw_2025_reads=0,
        wall_time_basis='Synthetic single-pass compute proxy only. Add authorized measured I/O, scientific loss, optimizer, full validation, checkpoint overhead before a wall-clock commitment.')
    a.output.parent.mkdir(parents=True, exist_ok=True)
    with a.output.open('x', encoding='utf-8') as f: json.dump(result, f, indent=2, ensure_ascii=False)
    print(json.dumps(dict(populations=populations, nine_epoch_new_attempt_cap=exact_ceiling['new_independent_optimizer_attempt_cap'],
        one_epoch_new_attempt_cap=entry_budget['new_independent_optimizer_attempt_cap'], visibility='IGNORED_LOCAL_ONLY'), indent=2))
