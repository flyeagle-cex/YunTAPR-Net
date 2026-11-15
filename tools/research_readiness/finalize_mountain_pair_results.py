"""Verify saved mountain evaluation JSON receipts and publish aggregate results."""
import argparse
import hashlib
import json
import math
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / 'src')]
from tools.research_readiness import start_mountain_pair_evaluation as entry
from tools.research_readiness.mountain_pair_metrics import ELEVATIONS, primary_contrast
from tools.research_readiness.paired_point_worker import _gate_report


class Receipts:
    def __init__(self):
        self.cache = {}
        self.bytes = 0

    def read(self, path):
        path = Path(path).resolve()
        if path.suffix != '.json':
            raise ValueError('Saved JSON receipts only')
        if path not in self.cache:
            size = path.stat().st_size
            if size > 64 * 1024**2 or self.bytes + size > 256 * 1024**2:
                raise ValueError('Receipt inspection cap exceeded')
            raw = path.read_bytes()
            if len(raw) != size:
                raise ValueError('Receipt changed during verification')
            self.cache[path] = raw
            self.bytes += size
        return json.loads(self.cache[path])

    def sha(self, path):
        self.read(path)
        return hashlib.sha256(self.cache[Path(path).resolve()]).hexdigest()


def write(path, value):
    with path.open('x', encoding='utf-8', newline='\n') as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write('\n')


def verify(proposal_path, private_path, output):
    receipts = Receipts()
    proposal, private = receipts.read(proposal_path), receipts.read(private_path)
    approval_path = Path(private_path).parent / 'RESEARCHER_APPROVAL.json'
    approval = receipts.read(approval_path)
    entry.validate_grant(proposal, private, approval)
    package = Path(private['output_root'])
    completion = receipts.read(package / 'completion.json')
    paired_path = package / 'paired_metrics.json'
    paired = receipts.read(paired_path)
    assert completion['status'] == entry.gate.COMPLETION_STATUS
    assert completion['tasks'] == list(entry.TASKS)
    assert completion['proposal_sha256'] == paired['proposal_sha256'] == proposal['proposal_sha256']
    assert completion['paired_metrics_sha256'] == receipts.sha(paired_path)
    assert completion['optimizer_updates'] == 0 and completion['automatic_retry'] is False
    assert not (package / 'failure.json').exists()
    assert paired['scientific_status'] == 'NOT_VERIFIED'
    binding = receipts.read(package / 'binding.json')
    assert binding['approval_sha256'] == receipts.sha(approval_path)
    assert binding['proposal_sha256'] == proposal['proposal_sha256']
    assert binding['code_commit'] == proposal['execution_code_commit']
    launch = receipts.read(private['launch_spec_path'])
    exit_receipt = receipts.read(Path(launch['service_dir']) / 'target_exit.json')
    assert exit_receipt['return_code'] == 0 and exit_receipt['automatic_retry'] is False
    preflights = [receipts.read(Path(private['preflight_root']) / f'receipt_{i:02d}.json') for i in (1, 2)]
    assert all(row['status'] == 'PASS' and row['proposal_sha256'] == proposal['proposal_sha256']
               and row['approval_sha256'] == binding['approval_sha256'] for row in preflights)
    records, terrain = {}, {}
    for task, model in zip(entry.TASKS, proposal['models']):
        folder = package / task
        record = receipts.read(folder / 'task_complete.json')
        result = record['result']
        assert record['status'] == result['status'] == 'COMPLETE'
        assert record['proposal_sha256'] == proposal['proposal_sha256']
        assert result == completion['results'][task]
        assert result['checkpoint_sha256'] == model['checkpoint_sha256']
        assert result['forward_calls'] == 121 and result['model_inference_passes'] == 1
        assert result['saved_elevation_gate'] == 'PASS' and result['optimizer_updates'] == 0
        expected_bytes = sum(row['bytes'] * row['opens_per_task'] for row in private['scientific_files'].values() if task in row['tasks'])
        expected_opens = sum(row['opens_per_task'] for row in private['scientific_files'].values() if task in row['tasks'])
        assert record['accounting']['payload_archive_reserved_bytes'] == expected_bytes
        assert record['accounting']['payload_open_instances'] == expected_opens
        assert not (folder / 'task_failure.json').exists()
        actual = receipts.read(folder / 'recomputed_report.json')
        reference = receipts.read(private['tasks'][task]['dev_report_path'])
        assert _gate_report(actual, reference) == result['gate']
        assert len(result['gate']['groups']) == 6
        assert actual['groups']['all']['summary'] == paired['full_population'][task]
        assert receipts.read(folder / 'point_metrics.json') == paired['point_metrics'][task]
        terrain[task] = receipts.read(folder / 'terrain_metrics.json')
        assert receipts.sha(folder / 'terrain_metrics.json') == paired['source_sha256'][task]
        assert result['terrain_population_sha256'] == terrain[task]['paired_population_sha256']
        records[task] = record
    assert primary_contrast(*[terrain[t] for t in entry.TASKS]) == paired['primary_contrast']
    assert paired['paired_population_sha256'] == terrain[entry.TASKS[0]]['paired_population_sha256']
    real, zero = [terrain[t]['scene_statistics'] for t in entry.TASKS]
    assert [row['scene_id'] for row in real] == [row['scene_id'] for row in zero]
    assert len(real) == 963
    scene_counts = []
    for a, b in zip(real, zero):
        for x, y in zip(a['elevation_rainfall_cells'], b['elevation_rainfall_cells']):
            assert [c['n_rain'] for c in x] == [c['n_rain'] for c in y]
        scene_counts.append(sum(c['n_rain'] for c in a['elevation_rainfall_cells'][2][4:]))
    assert sum(scene_counts) == paired['primary_contrast']['n_strong']
    children = [row['accounting'] for row in preflights] + [row['accounting'] for row in records.values()]
    controller = {k: completion['accounting'][k] - sum(row[k] for row in children)
                  for k in ('metadata_archive_reserved_bytes', 'metadata_open_instances', 'payload_archive_reserved_bytes', 'payload_open_instances')}
    assert 0 <= controller['metadata_archive_reserved_bytes'] <= entry.LIMITS['metadata_bytes_controller']
    assert 0 <= controller['metadata_open_instances'] <= entry.LIMITS['metadata_opens_controller']
    assert controller['payload_archive_reserved_bytes'] == controller['payload_open_instances'] == 0
    account = entry.gate.totals(children + [controller])
    assert account == completion['accounting']
    assert completion['elapsed_since_first_preflight_seconds'] <= entry.LIMITS['maximum_seconds']
    storage = sum(path.stat().st_size for folder in (package, Path(private['preflight_root']))
                  for path in folder.rglob('*') if path.is_file())
    assert storage <= entry.LIMITS['output_storage_cap_bytes']
    contrasts = {}
    for name in ELEVATIONS:
        rows = paired['cells'][name]
        assert len(rows) == 7
        for a, b, cell in zip(terrain[entry.TASKS[0]]['elevation_groups'][name]['cells'],
                              terrain[entry.TASKS[1]]['elevation_groups'][name]['cells'], rows):
            assert a['n_rain'] == b['n_rain'] == cell['n_rain']
            for metric in ('log_pinball', 'physical_pinball_over20'):
                assert a[metric] == cell['real_' + metric] and b[metric] == cell['zero_' + metric]
        strong = rows[4:]
        count = sum(row['n_rain'] for row in strong)
        contrast = dict(n_strong=count, metrics={})
        for metric in ('log_pinball', 'physical_pinball_over20'):
            means = {arm: math.fsum(row['n_rain'] * (row[arm + '_' + metric] or 0) for row in strong) / count if count else None for arm in ('real', 'zero')}
            delta = means['real'] - means['zero'] if count else None
            contrast['metrics'][metric] = dict(means, real_minus_zero=delta, relative_percent=100 * delta / means['zero'] if count and means['zero'] else None)
        contrasts[name] = contrast
    verification = dict(status='VERIFIED_COMPLETE_SAVED_RECEIPTS', execution_code_commit=proposal['execution_code_commit'],
        proposal_sha256=proposal['proposal_sha256'], completion_sha256=receipts.sha(package / 'completion.json'),
        paired_metrics_sha256=receipts.sha(paired_path), accounting=account,
        elapsed_seconds=completion['elapsed_since_first_preflight_seconds'], finished=completion['finished'],
        output_storage_bytes=storage, budget=proposal['budget'], six_groups_per_arm='PASS', elevation_reproduction='PASS',
        supervisor_exit_code=exit_receipt['return_code'], controller_accounting_basis='DIFFERENCE_FROM_PACKAGE_AND_CHILD_RECEIPTS',
        primary_contrast=paired['primary_contrast'], strong_by_elevation=contrasts,
        primary_scene_count=sum(n > 0 for n in scene_counts), maximum_primary_pixels_in_one_scene=max(scene_counts),
        independent_event_count='NOT_IDENTIFIED', checkpoint_rehashes_in_verification=0,
        scientific_payload_reads_in_verification=0, new_inference=0, optimizer_updates=0, scientific_status='NOT_VERIFIED',
        metadata_inspection_bytes=receipts.bytes, metadata_inspection_opens=len(receipts.cache))
    output.mkdir(parents=True, exist_ok=False)
    write(output / 'TERMINAL_VERIFICATION.json', verification)
    write(output / 'PAIRED_METRICS.json', paired)
    print(json.dumps(dict(status=verification['status'], primary=paired['primary_contrast'], primary_scenes=verification['primary_scene_count'])))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--proposal', type=Path, required=True)
    parser.add_argument('--private-preparation', type=Path, required=True)
    parser.add_argument('--public-root', type=Path, required=True)
    args = parser.parse_args()
    verify(args.proposal, args.private_preparation, args.public_root)
