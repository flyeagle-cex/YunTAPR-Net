"""Frozen REAL/ZERO treatment wiring for the shared forward-only worker."""
import math
import json
from pathlib import Path


def run_task(root, proposal, private, task, output, check):
    from tools.research_readiness import paired_point_worker as shared
    from tools.research_readiness.mountain_pair_metrics import MountainAccumulator, CONTRACT, ELEVATIONS
    row = next(item for item in proposal['models'] if item['task'] == task)
    if proposal['scientific_choices'].get('terrain_evaluation') != CONTRACT:
        raise PermissionError('Exact elevation/rainfall contract required')

    def transform(pack, definition):
        from yuntapr.experimental.research_readiness.dynamic_terrain import PhysicalDote
        from yuntapr.experimental.research_readiness.dote_numeric_control import ZeroNumericDote
        if row['dynamic_control'] == 'REAL_PHYSICAL_DOTE':
            return PhysicalDote(pack, definition)
        if row['dynamic_control'] == 'ZERO_NUMERIC_RETAIN_REAL_MASKS':
            return ZeroNumericDote(pack, definition)
        raise PermissionError('Unknown fixed DOTE treatment')

    result = shared.run_task(root, proposal, private, task, output, check,
                             diagnostics_factory=MountainAccumulator, transform_factory=transform,
                             include_joint=False)
    def read(path):
        return json.loads(Path(path).read_bytes())
    saved = read(private['tasks'][task]['tail_report_path'])['elevation_diagnostics']['bins']
    new = read(Path(output) / 'terrain_metrics.json')['elevation_groups']
    if read(Path(output) / 'terrain_metrics.json')['population']['n_strong'] != 717:
        raise ValueError('Frozen strong reference population differs')
    for name in ELEVATIONS:
        a, b = new[name], saved[name]
        if a['n_valid'] != b['n_valid'] or a['n_rain'] != b['n_rain']:
            raise ValueError('Saved elevation population differs')
        for actual, expected in (
            (a['brier_sum'] / a['n_valid'] if a['n_valid'] else None, b['brier']),
            (sum(cell['log_pinball_sum'] for cell in a['cells']) / a['n_rain'] if a['n_rain'] else None, b['conditional_pinball']),
        ):
            if actual is None and expected is None:
                continue
            if actual is None or expected is None or not math.isclose(actual, expected, rel_tol=1e-12, abs_tol=1e-12):
                raise ValueError('Saved elevation score does not reproduce')
    result['saved_elevation_gate'] = 'PASS'
    return result
