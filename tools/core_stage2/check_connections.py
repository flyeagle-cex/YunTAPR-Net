"""Predeclared 8 GFS pairs / 2 seven-band frames, local-only bounded evidence.

Uses existing inventories and B1 CF identities, not a raw archive scan. Dates
are fixed before source I/O; failures are retained without replacement samples.
"""
from pathlib import Path
from datetime import datetime, timedelta, timezone
import argparse, csv, hashlib, json, os, sys
import numpy as np
ROOT = Path(__file__).resolve().parents[2]
sys.dont_write_bytecode = True; sys.path.insert(0, str(ROOT/'src'))
os.environ['CUDA_VISIBLE_DEVICES'] = ''; os.environ['OMP_NUM_THREADS'] = '1'; os.environ['MKL_NUM_THREADS'] = '1'
from yuntapr.experimental.core_innovation.gfs import ForecastIdentity, VariableRequest, read_gfs_file, combine_environment, parse_utc
from yuntapr.experimental.core_innovation.grid import frozen_sp04_grid, GridSpec
from yuntapr.experimental.core_innovation.stage2 import MEE_KEYS
from yuntapr.experimental.core_innovation.stage2.coupling import TargetBinding, vintage_relation
from yuntapr.experimental.core_innovation.stage2.population import read_seven_band, joint_population
from yuntapr.data.dataset_b1 import FREEZE, AUDIT, PINS, FRAME_SHA, pinned
from yuntapr.spatial.sp04_mapping import load_sp04

MAIN_INDEX = Path('stage0-b0-evidence/evidence/outputs/stage0_continuous_engineering/run_20260928T041855_828904Z/logs/gfs_source_manifest_before.csv')
THERMO_INDEX = Path('stage0-b0-evidence/evidence/outputs/stage0_gfs_thermo_compatibility/run_20260928T084334_575397Z/THERMO/gfs_thermo_inventory.csv')


def selected_rows(path, predicate):
    with path.open(encoding='utf-8-sig', newline='') as f:
        return [r for r in csv.DictReader(f) if predicate(r)]


def requests():
    main = tuple(VariableRequest(f'{q}{p}', q, name, p*100.) for p in (850, 700)
        for q, name in (('u', 'u-component_of_wind_isobaric'), ('v', 'v-component_of_wind_isobaric'))) + (
        VariableRequest('ps', 'surface_pressure', 'Pressure_surface'),
        VariableRequest('pwat', 'precipitable_water', 'Precipitable_water_entire_atmosphere_single_layer'),
        VariableRequest('cape', 'cape', 'Convective_available_potential_energy_surface'))
    thermo = tuple(VariableRequest(f'{q}{p}', q, name, p*100.) for p in (850, 700)
        for q, name in (('temperature', 'Temperature_isobaric'), ('relative_humidity', 'Relative_humidity_isobaric')))
    return {'main': main, 'thermo': thermo}


def run(probe, output, himawari_root):
    if not output.resolve().is_relative_to(ROOT/'docs/core_stage2/.local'):
        raise PermissionError('Real evidence stays under ignored local directory')
    if output.exists(): raise FileExistsError('Never overwrite an earlier receipt')
    prior = json.loads(probe.read_text(encoding='utf-8'))['records']
    # Roots derive from the previously authorized two f000 pairs, no discovery.
    roots = {}
    for r in prior:
        path = Path(r['path'])
        if r['kind'] not in ('main', 'thermo'): raise ValueError('Unknown source kind')
        roots[r['kind']] = path.parents[2]
    plan = []
    for year in (2023, 2024):
        for hour, lead in ((0, 0), (0, 3), (0, 6), (6, 0)):
            init = datetime(year, 5, 1, hour, tzinfo=timezone.utc)
            identity = ForecastIdentity(init, timedelta(hours=lead), init+timedelta(hours=lead))
            paths = {}
            for kind in ('main', 'thermo'):
                prefix = 'gfs_' if kind == 'main' else 'gfs_thermo_'
                rel = Path(str(year))/init.strftime('%Y%m%d')/(prefix+'0p25_'+init.strftime('%Y%m%d%H')+f'_f{lead:03d}.nc')
                paths[kind] = {'relative': str(rel), 'path': str(roots[kind]/rel)}
            plan.append({'identity': identity, 'paths': paths})
    names = {kind: {p['paths'][kind]['relative'] for p in plan} for kind in ('main', 'thermo')}
    manifests = {}
    for kind, rel in (('main', MAIN_INDEX), ('thermo', THERMO_INDEX)):
        rows = selected_rows(ROOT/rel, lambda r: r['relative_path'] in names[kind])
        manifests[kind] = {r['relative_path']: r for r in rows}
        if len(rows) != 8 or len(manifests[kind]) != 8: raise ValueError('Fixed source missing/duplicated in existing inventory')
    reserved = 0
    for case in plan:
        for kind, p in case['paths'].items():
            size = int(manifests[kind][p['relative']]['size_bytes'])
            if not 0 < size <= 2*1024**2: raise ValueError('Per-file cap exceeded in existing inventory')
            p['expected_bytes'] = size; reserved += size
    if reserved > 8*1024**2: raise ValueError('Aggregate GFS budget exceeds inherited 8 MiB ceiling')
    targets, frames, all_candidates = {}, {}, []
    index_path = pinned(ROOT/AUDIT/'frame_identity_index.json', FRAME_SHA)
    index = json.loads(index_path.read_text(encoding='utf-8'))
    for year in (2023, 2024):
        valid_times = {c['identity'].valid for c in plan if c['identity'].init.year == year}
        path = pinned(ROOT/FREEZE/f'b1_{year}_formal_manifest.csv', PINS['B1', year])
        rows = selected_rows(path, lambda r: parse_utc(r['analysis_time']) in valid_times)
        all_candidates.extend(rows)
        targets.update({parse_utc(r['analysis_time']): r for r in rows})
        wanted = {r[f'slot_{i}_nominal'] for r in rows for i in range(6)}
        months = {parse_utc(t).strftime('%Y%m') for t in wanted}
        for month in months:
            rel = 'native_frames/'+month+'.csv'
            selected = selected_rows(pinned(ROOT/AUDIT/rel, index['files'][rel]), lambda r: r['nominal'] in wanted)
            frames.update({r['nominal']: r for r in selected})
    # Persist the immutable selection before any raw source access.
    output.parent.mkdir(parents=True, exist_ok=True)
    selection = {'GFS_max_bytes': 8*1024**2, 'GFS_reserved_bytes': reserved, 'Himawari_max_files': 2,
                 'Himawari_max_bytes': 16*1024**2, 'GFS_pairs': [dict(identity={
                     'init': c['identity'].init.isoformat(), 'valid': c['identity'].valid.isoformat(),
                     'lead_hours': c['identity'].lead.total_seconds()/3600}, paths=c['paths']) for c in plan],
                 'raw_2025_access': False}
    selection_path = output.with_name(output.stem+'_selection.json')
    with selection_path.open('x', encoding='utf-8') as f: json.dump(selection, f, indent=2, ensure_ascii=False)
    target_grid = frozen_sp04_grid(); req = requests(); checks = []; read_bytes = 0
    for case in plan:
        identity = case['identity']; record = dict(identity=selection['GFS_pairs'][len(checks)]['identity'])
        try:
            row = targets[identity.valid]
            ff = [frames[row[f'slot_{i}_nominal']] for i in range(6)]
            if any(f['status'] != 'FULL_VALID' for f in ff): raise ValueError('Inherited B1 frame is not full valid')
            binding = TargetBinding(parse_utc(row['window_start']), parse_utc(row['analysis_time']),
                tuple(parse_utc(f['nominal']) for f in ff), tuple(parse_utc(f['obs_start']) for f in ff),
                tuple(parse_utc(f['obs_end']) for f in ff))
            record['time_binding'] = binding.check_forecast(identity, valid_policy='valid_equals_analysis_retrospective_candidate')
            pair = {}
            for kind, p in case['paths'].items():
                source = Path(p['path'])
                if source.stat().st_size != p['expected_bytes']: raise IOError('Source size differs from audited inventory')
                # Reserve bytes even when subsequent decoding fails; no retries.
                read_bytes += p['expected_bytes']
                if read_bytes > 8*1024**2: raise ValueError('Aggregate cap exhausted')
                pair[kind] = read_gfs_file(source, identity, req[kind])
            environment = combine_environment(pair['main'], pair['thermo'], target_valid_time=identity.valid,
                                               decision_time=binding.analysis, mode='retrospective')
            mapped = environment.on_grid(target_grid, operator='bilinear_point_candidate')
            x, valid = mapped.stack(MEE_KEYS)
            if not np.isfinite(x[valid]).all() or not np.isnan(x[~valid]).all(): raise AssertionError('Mapped mask/value mismatch')
            ps = environment.fields['ps']
            for field in environment.fields.values():
                if field.level_pa is not None and np.any(field.valid & ~(ps.valid & (field.level_pa < ps.values))):
                    raise AssertionError('Underground pressure level passed')
            try:
                combine_environment(pair['main'], pair['thermo'], target_valid_time=identity.valid,
                                    decision_time=binding.analysis, mode='operational')
            except PermissionError: record['operational_without_release_evidence'] = 'REJECTED'
            else: raise AssertionError('Operational mode incorrectly admitted')
            record.update(status='PASS_BOUNDED_RETROSPECTIVE_CONNECTION', channel_order=list(MEE_KEYS), shape=x.shape,
                units={k: f.unit for k, f in mapped.fields.items()},
                native_valid_counts={k: int(f.valid.sum()) for k, f in environment.fields.items()},
                mapped_valid_counts={k: int(f.valid.sum()) for k, f in mapped.fields.items()},
                source_provenance=environment.provenance)
        except Exception as exc:
            record.update(status='FAIL_NO_RETRY', reason=type(exc).__name__+': '+str(exc))
        checks.append(record)
    # One predeclared slot from the 06Z binding in each year. This is deliberately
    # insufficient to promote an entire six-slot B3 population to verified.
    seven_checks = []; seven_evidence = {}; mapping = load_sp04(); hbytes = 0
    for year in (2023, 2024):
        analysis = datetime(year, 5, 1, 6, tzinfo=timezone.utc)
        try:
            row = targets[analysis]; fr = frames[row['slot_0_nominal']]
            source = Path(himawari_root)/fr['relative_path']
            if source.stat().st_size != int(fr['source_bytes']): raise IOError('Himawari audited size differs')
            hbytes += int(fr['source_bytes'])
            if hbytes > 16*1024**2: raise ValueError('Aggregate Himawari cap exceeded')
            x, mask, evidence = read_seven_band(source, nominal=fr['nominal'], mapping=mapping)
            if evidence['source_sha256'] != fr['source_sha256'] or parse_utc(evidence['obs_start']) != parse_utc(fr['obs_start']) or parse_utc(evidence['obs_end']) != parse_utc(fr['obs_end']):
                raise IOError('Inherited source/actual CF identity differs')
            if not mask.all(): raise ValueError('Seven-band joint full-valid rejection')
            seven_evidence[fr['nominal']] = evidence
            seven_checks.append(dict(year=year, status='PASS_ONE_FRAME_ONLY', evidence=evidence))
        except Exception as exc:
            seven_checks.append(dict(year=year, status='FAIL_NO_RETRY', reason=type(exc).__name__+': '+str(exc)))
    population = joint_population(all_candidates, seven_evidence,
        native_grid_id=GridSpec(mapping.axes['native_lat'], mapping.axes['native_lon']).identity)
    relations = []
    for i, a in enumerate(plan):
        for j, b in enumerate(plan[i+1:], i+1):
            if a['identity'].init.year == b['identity'].init.year:
                relations.append(dict(case_indices=[i, j], relation=vintage_relation(a['identity'], b['identity'])))
    report = dict(scope='FIXED_SMALL_SAMPLE_ENGINEERING_ONLY', GFS_checks=checks, vintage_relations=relations,
        seven_band_checks=seven_checks, selected_population_check=population, GFS_reserved_bytes=read_bytes,
        Himawari_reserved_bytes=hbytes, prior_probe_sha256=hashlib.sha256(probe.read_bytes()).hexdigest(),
        GPU_used=False, optimizer_updates=0, precipitation_payload_reads=0, raw_2025_reads=0,
        operational_NRT_ready=False, formal_population_or_scalers_ready=False,
        limitation='Fixed eight GFS pairs and two native seven-band frames do not validate archive-wide quality, complete B3 population, Train scalers or meteorological skill.')
    with output.open('x', encoding='utf-8') as f: json.dump(report, f, indent=2, ensure_ascii=False)
    print(json.dumps(dict(GFS_pass=sum(r['status'].startswith('PASS') for r in checks), GFS_fail=sum(r['status'].startswith('FAIL') for r in checks),
        seven_band_frame_pass=sum(r['status'].startswith('PASS') for r in seven_checks),
        GFS_reserved_bytes=read_bytes, Himawari_reserved_bytes=hbytes, result_visibility='IGNORED_LOCAL_ONLY'), indent=2))


if __name__ == '__main__':
    p = argparse.ArgumentParser(); p.add_argument('--probe', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True); p.add_argument('--himawari-root', type=Path, required=True)
    a = p.parse_args(); run(a.probe, a.output, a.himawari_root)
