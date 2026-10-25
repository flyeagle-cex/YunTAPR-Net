"""Continue only the two preselected f003 pairs never read in the first check.

Absence from inherited B1 population is retained as a target eligibility block.
No previously decoded weather file or satellite payload is reread.
"""
from check_connections import *


if __name__ == '__main__':
    p = argparse.ArgumentParser(); p.add_argument('--previous', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True); a = p.parse_args()
    if not a.output.resolve().is_relative_to(ROOT/'docs/core_stage2/.local') or a.output.exists():
        raise PermissionError('New local-only receipt required')
    previous = json.loads(a.previous.read_text(encoding='utf-8'))
    selection_path = a.previous.with_name(a.previous.stem+'_selection.json')
    selection = json.loads(selection_path.read_text(encoding='utf-8'))
    result = []; bytes_read = 0; req = requests(); target = frozen_sp04_grid()
    index = json.loads(pinned(ROOT/AUDIT/'frame_identity_index.json', FRAME_SHA).read_text(encoding='utf-8'))
    for plan, prior in zip(selection['GFS_pairs'], previous['GFS_checks']):
        if not prior['status'].startswith('FAIL'): continue
        if plan['identity']['lead_hours'] != 3 or 'source_provenance' in prior or not prior.get('reason', '').startswith('KeyError: datetime.datetime('):
            raise PermissionError('Only unread f003 target-absence continuation allowed; no retry')
        info = plan['identity']; init = parse_utc(info['init']); valid_time = parse_utc(info['valid'])
        identity = ForecastIdentity(init, timedelta(hours=3), valid_time)
        record = {'identity': info, 'inherited_B1_target_eligible': False,
                  'target_status': 'BLOCKED_NOT_IN_FROZEN_B1_POPULATION',
                  'precipitation_payload_read': False, 'target_payload_validated': False}
        # Target/satellite metadata failure must not prevent the independent
        # GFS interface check. It still blocks admission to a paired population.
        try:
            nominal = tuple(valid_time-timedelta(minutes=m) for m in (60, 50, 40, 30, 20, 10))
            wanted = {t.isoformat() for t in nominal}; rel = 'native_frames/'+valid_time.strftime('%Y%m')+'.csv'
            selected = selected_rows(pinned(ROOT/AUDIT/rel, index['files'][rel]), lambda r: r['nominal'] in wanted)
            frames = {r['nominal']: r for r in selected}
            ordered = [frames[t.isoformat()] for t in nominal]
            if any(r['status'] != 'FULL_VALID' for r in ordered): raise ValueError('Satellite history metadata not full-valid')
            binding = TargetBinding(valid_time-timedelta(minutes=30), valid_time, nominal,
                tuple(parse_utc(f['obs_start']) for f in ordered), tuple(parse_utc(f['obs_end']) for f in ordered))
            record['candidate_time_binding'] = binding.check_forecast(identity, valid_policy='valid_equals_analysis_retrospective_candidate')
        except Exception as exc:
            record['time_binding_status'] = 'BLOCKED'
            record['time_binding_reason'] = type(exc).__name__+': '+str(exc)
        try:
            pair = {}
            for kind, source in plan['paths'].items():
                path = Path(source['path'])
                if path.stat().st_size != source['expected_bytes']: raise IOError('Audited size differs')
                bytes_read += source['expected_bytes']
                if previous['GFS_reserved_bytes']+bytes_read > selection['GFS_max_bytes']: raise ValueError('Original total budget exhausted')
                pair[kind] = read_gfs_file(path, identity, req[kind])
            environment = combine_environment(pair['main'], pair['thermo'], target_valid_time=valid_time,
                decision_time=valid_time, mode='retrospective')
            mapped = environment.on_grid(target, operator='bilinear_point_candidate')
            x, mask = mapped.stack(MEE_KEYS)
            if not np.isfinite(x[mask]).all() or not np.isnan(x[~mask]).all(): raise AssertionError('Mask mismatch')
            ps = environment.fields['ps']
            for field in environment.fields.values():
                if field.level_pa is not None and np.any(field.valid & ~(ps.valid & (field.level_pa < ps.values))):
                    raise AssertionError('Underground pressure level passed')
            record.update(status='PASS_GFS_INTERFACE_TARGET_STILL_BLOCKED', channel_order=list(MEE_KEYS),
                units={k: f.unit for k, f in mapped.fields.items()}, shape=x.shape,
                native_valid_counts={k: int(f.valid.sum()) for k, f in environment.fields.items()},
                mapped_valid_counts={k: int(f.valid.sum()) for k, f in mapped.fields.items()}, source_provenance=environment.provenance)
        except Exception as exc: record.update(status='FAIL_NO_RETRY', reason=type(exc).__name__+': '+str(exc))
        result.append(record)
    report = dict(previous_receipt_sha256=hashlib.sha256(a.previous.read_bytes()).hexdigest(), checks=result,
        newly_reserved_bytes=bytes_read, cumulative_GFS_reserved_bytes=previous['GFS_reserved_bytes']+bytes_read,
        original_max_GFS_bytes=selection['GFS_max_bytes'], original_selection_unchanged=True,
        formal_target_eligibility_unchanged=True, weather_payloads_reread=0, optimizer_updates=0,
        raw_2025_reads=0, operational_NRT_ready=False)
    with a.output.open('x', encoding='utf-8') as f: json.dump(report, f, indent=2, ensure_ascii=False)
    print(json.dumps(dict(checks=len(result), status=[r['status'] for r in result],
        cumulative_GFS_reserved_bytes=report['cumulative_GFS_reserved_bytes'], visibility='IGNORED_LOCAL_ONLY'), indent=2))
