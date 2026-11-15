"""Fresh approval-bound REAL/ZERO mountain evaluation using the shared controller."""
import importlib.util
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / 'src')]
SCOPE = 'REAL_ZERO_COSINE9_MOUNTAIN_STRONG_EVALUATION_V1'
TASKS = ('REAL_COSINE9', 'ZERO_COSINE9')
MODEL_BINDINGS = (
    ('REAL_PHYSICAL_DOTE', 53906821, '1c9b5f8c595935674f6952da6b239a50e26ca4eb4d90a217ab5593866d5b319e'),
    ('ZERO_NUMERIC_RETAIN_REAL_MASKS', 53906757, 'e5689a573704145fa29b16c8e6ab4c9a1bd2e674a7e8888d2247c82958fb6fa9'),
)
INHERITED_CHOICES = dict(
    DOTE=dict(pwat_reference_kg_m2=31.85768219039871,
              reference_provenance='FROZEN_2023_TRAIN_POSITIVE_PWAT_MEAN_statistics_sha256=53ab2f07aabb02e66ad237452447a35e0e2896278eae9d2da179336c06fea980',
              moisture_basis='windward_W', velocity_reference_m_s=1.0),
    modulation_limit=.1, point_methods=['A', 'B', 'C'], thresholds_mm_h=[.1, 1., 5., 10., 20., 50.],
    classification_precision='FP32 strict > threshold, equality counts retained',
    continuous_precision='FP64 physical point proxies', cutoff_selection='FIXED_NO_OPTIMIZATION',
)
spec = importlib.util.spec_from_file_location('mountain_shared_controller', ROOT / 'tools/research_readiness/start_paired_point_evaluation.py')
gate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gate)
gate.SCOPE, gate.TASKS = SCOPE, TASKS
gate.ENTRY_PATH = Path(__file__).resolve()
gate.WORKER_PATH = 'tools/research_readiness/mountain_pair_worker.py'
gate.COMPLETION_STATUS = 'COMPLETE_REAL_ZERO_MOUNTAIN_EVALUATION'
LIMITS = dict(gate.LIMITS,
    payload_archive_reference_bytes=53494759036,
    metadata_bytes_per_worker=256 * 1024**2, metadata_opens_per_worker=2048,
    total_metadata_cap_bytes=788529152, total_metadata_opens=5632,
    total_source_cap_bytes=54283288188,
    previous_attempt_metadata_bytes=0, previous_attempt_metadata_opens=0,
    previous_attempt_payload_bytes=0, previous_attempt_payload_opens=0,
    previous_attempt_seconds=0, cumulative_source_cap_bytes=54283288188,
    cumulative_metadata_opens=5632, cumulative_total_opens=21538, cumulative_maximum_seconds=7200,
    maximum_seconds=7200, controller_seconds=7080,
)
gate.LIMITS = LIMITS
_validate = gate.validate_grant


def validate_grant(proposal, private, approval):
    from tools.research_readiness.mountain_pair_metrics import CONTRACT
    _validate(proposal, private, approval)
    if proposal['scientific_choices'] != dict(INHERITED_CHOICES, terrain_evaluation=CONTRACT):
        raise PermissionError('Frozen mountain/strong-rain diagnostic definition differs')
    for row, (control, size, sha) in zip(proposal['models'], MODEL_BINDINGS):
        if (row.get('dynamic_control'), row.get('checkpoint_bytes'), row.get('checkpoint_sha256')) != (control, size, sha) or row.get('endpoint') != 'FIXED_EPOCH_9_LAST':
            raise PermissionError('Exact original REAL/ZERO COSINE9 E9 weights required')


def finalize_pair(package, proposal):
    from tools.research_readiness.mountain_pair_metrics import CONTRACT, primary_contrast
    reports = {task: gate.read(package / task / 'terrain_metrics.json') for task in TASKS}
    contrast = primary_contrast(reports[TASKS[0]], reports[TASKS[1]])
    full = {task: gate.read(package / task / 'recomputed_report.json')['groups']['all']['summary'] for task in TASKS}
    cells = {}
    for name, group in reports[TASKS[0]]['elevation_groups'].items():
        a, b = group['cells'], reports[TASKS[1]]['elevation_groups'][name]['cells']
        cells[name] = [dict(n_rain=x['n_rain'], lower_exclusive=x['lower_exclusive'], upper_inclusive=x['upper_inclusive'],
                           real_log_pinball=x['log_pinball'], zero_log_pinball=y['log_pinball'],
                           real_physical_pinball_over20=x['physical_pinball_over20'], zero_physical_pinball_over20=y['physical_pinball_over20'])
                       for x, y in zip(a, b)]
    gate.write(package / 'paired_metrics.json', dict(
        status='DESCRIPTIVE_MATCHED_MOUNTAIN_EVALUATION', primary_contrast=contrast, cells=cells,
        full_population=full, point_metrics={task: gate.read(package / task / 'point_metrics.json') for task in TASKS},
        source_sha256={task: gate.sha(package / task / 'terrain_metrics.json') for task in TASKS},
        paired_population_sha256=reports[TASKS[0]]['paired_population_sha256'],
        evaluation_contract=CONTRACT, proposal_sha256=proposal['proposal_sha256'], scientific_status='NOT_VERIFIED'))


gate.validate_grant, gate.finalize_pair = validate_grant, finalize_pair
validate_entry = gate.validate_entry

if __name__ == '__main__':
    gate.main()
