"""Pure index operations; no source path stat/open, no forecast-vintage default."""
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import PureWindowsPath
import hashlib, json, re


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()).hexdigest()


def utc(text):
    t = datetime.fromisoformat(text.replace('Z', '+00:00'))
    if t.tzinfo is None: raise ValueError('Timezone required')
    return t.astimezone(timezone.utc)


def forecast_index(rows, *, kind):
    """Only 2023/24 March-October indexed sources; duplicates fail closed."""
    result = {}
    for row in rows:
        path = PureWindowsPath(row['relative_path'])
        m = re.fullmatch(r'gfs_'+('thermo_' if kind == 'thermo' else '')+r'0p25_(202[34]\d{6})_f(000|003|006)\.nc', path.name)
        if not m: continue
        init = datetime.strptime(m[1], '%Y%m%d%H').replace(tzinfo=timezone.utc)
        if not 3 <= init.month <= 10: continue
        lead = int(m[2]); key = (init.isoformat(), lead)
        if ((row.get('init_time') and utc(row['init_time'])!=init)
            or (row.get('valid_time') and utc(row['valid_time'])!=init+timedelta(hours=lead))
            or (row.get('lead_time') and float(row['lead_time'])!=lead)):
            raise ValueError('Filename and existing inventory forecast identity conflict')
        if key in result: raise ValueError('Duplicate forecast identity in source inventory')
        size = int(row['size_bytes'])
        result[key] = dict(relative_path=str(path), bytes=size, kind=kind, init=init.isoformat(), lead=lead,
                           valid=(init+timedelta(hours=lead)).isoformat(), readable=row.get('read_success', 'NOT_IN_INDEX'))
    return result


def pair_index(main, thermo):
    pairs = {}; rejects = Counter()
    for key in sorted(set(main) | set(thermo)):
        if key not in main or key not in thermo:
            rejects['MISSING_MAIN_OR_THERMO'] += 1; continue
        a, b = main[key], thermo[key]
        if min(a['bytes'], b['bytes']) <= 0 or b['readable'] == 'False':
            rejects['INDEX_SIZE_OR_READ_FAILURE'] += 1; continue
        if max(a['bytes'], b['bytes']) > 2*1024**2:
            rejects['EXCEEDS_INHERITED_PER_FILE_CAP'] += 1; continue
        if a['valid'] != b['valid']: raise ValueError('Inventory init/lead identity conflict')
        pair = dict(main=a, thermo=b, init=a['init'], valid=a['valid'], lead=a['lead'])
        pair['id'] = digest(pair); pairs[key] = pair
    return pairs, dict(rejects)


def scene_options(rows, pairs):
    by_valid = {}
    for p in pairs.values(): by_valid.setdefault(utc(p['valid']), []).append(p)
    result = []; seen = set()
    for row in rows:
        sid = row['sample_id']; start, analysis = utc(row['window_start']), utc(row['analysis_time'])
        if sid in seen: raise ValueError('Duplicate inherited scene')
        seen.add(sid)
        if start.year not in (2023, 2024) or not 3 <= start.month <= 10 or analysis != start+timedelta(minutes=30):
            raise PermissionError('Authorized inherited target identity required')
        options = [p for p in by_valid.get(analysis, []) if utc(p['init']) <= analysis]
        result.append(dict(record=row, options=sorted(options, key=lambda p: p['lead']),
                           status='INDEX_UPPER_BOUND' if options else 'NO_EXACT_VALID_GFS_PAIR'))
    return result


def select_by_lead(scenes, lead):
    """lead=None means union for planning ONLY, never a mixed-vintage training policy."""
    return [s for s in scenes if any(lead is None or p['lead'] == lead for p in s['options'])]


def satellite_manifest(scenes, frames):
    sources = {}; missing = []; exposures = 0
    for s in scenes:
        row = s['record']
        for slot in range(6):
            nominal = row[f'slot_{slot}_nominal']; exposures += 1
            if nominal not in frames: missing.append(dict(scene=row['sample_id'], slot=slot)); continue
            f = frames[nominal]; rel = str(PureWindowsPath(f['relative_path']))
            item = dict(nominal=nominal, relative_path=rel, expected_bytes=int(f['source_bytes']),
                        expected_sha256=f['source_sha256'], inherited_B13_status=f['status'],
                        obs_start=f['obs_start'], obs_end=f['obs_end'], exposure_count=0,
                        seven_band_status='UNVERIFIED', year=utc(nominal).year)
            previous = sources.setdefault(rel, item)
            if any(previous[k] != item[k] for k in item if k != 'exposure_count'):
                raise ValueError('Conflicting source identity for shared frame')
            previous['exposure_count'] += 1
    return dict(files=sorted(sources.values(), key=lambda f: f['relative_path']), missing=missing,
                scene_slot_exposures=exposures, bytes=sum(f['expected_bytes'] for f in sources.values()),
                formal_population_verified=False)


def rainfall_summary(scenes, target_index):
    rows = [s['record'] for s in scenes]; missing = [r['sample_id'] for r in rows if r['sample_id'] not in target_index]
    # Reuse historical descriptive scene-max >=20 mm/h flag. This is NOT an
    # extreme-event definition and cannot count >=20 mm/h pixels from maxima.
    known = [target_index[r['sample_id']] for r in rows if r['sample_id'] in target_index]
    return dict(scenes=len(rows), qc_evidence_missing=len(missing),
        valid_target_pixels=sum(int(r['imerg_valid_yunnan_count']) for r in known),
        rain_pixels_gt_0p1=sum(int(r['imerg_rain_yunnan_count']) for r in known),
        scenes_with_rain=sum(int(r['imerg_rain_yunnan_count']) > 0 for r in known),
        scenes_max_ge_20_mm_h=sum(float(r['imerg_max_yunnan_mmhr'] or 0) >= 20 for r in known),
        high_intensity_pixel_count=None, monthly=dict(sorted(Counter(utc(r['analysis_time']).strftime('%Y%m') for r in rows).items())),
        analysis_utc_hour=dict(sorted(Counter(utc(r['analysis_time']).strftime('%H') for r in rows).items())))


def training_budget(*, final_train_ids=None, final_dev_ids=None, final_population_sha=None):
    if final_train_ids is None or final_dev_ids is None or final_population_sha is None:
        return dict(status='WAITING_FOR_VERIFIED_FINAL_POPULATION', exact_optimizer_attempt_cap=None,
            formula='2 models * 9 epochs * ceil(N_final_2023_Train/2)', seed_count=1, loss_arm_candidate='E0',
            validation_batch=8, inherited_allowance=0, replay_allowance=0, training_authorized=False)
    if not final_train_ids or not final_dev_ids or any(utc(t).year != 2023 for t in final_train_ids) or any(utc(t).year != 2024 for t in final_dev_ids):
        raise ValueError('Separate final Train/Dev IDs required')
    if len(set(final_train_ids)) != len(final_train_ids) or len(set(final_dev_ids)) != len(final_dev_ids): raise ValueError('Duplicate IDs')
    if not re.fullmatch('[0-9a-f]{64}', final_population_sha): raise ValueError('Population SHA required')
    return dict(status='CANDIDATE_NOT_AUTHORIZED', exact_optimizer_attempt_cap=18*((len(final_train_ids)+1)//2),
                population_sha256=final_population_sha, inherited_allowance=0, replay_allowance=0)
