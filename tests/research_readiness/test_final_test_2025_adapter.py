"""Synthetic-only tests for the catalogue-gated 2025 final-test adapter.

No test in this file lists, stats or opens a 2025 raw path, a real checkpoint or
the real 2023/2024 frozen payload.  Authority binding, tensor assembly, metrics
and the descriptive comparison are exercised with in-memory fixtures.
"""
from __future__ import annotations

import json
import math
from datetime import timedelta
from types import SimpleNamespace

import numpy as np
import pytest

torch = pytest.importorskip('torch')

from yuntapr.experimental.core_innovation.multispectral import TrainNormalization
from yuntapr.experimental.core_innovation.stage2 import CHANNELS, MEE_V13_KEYS
from yuntapr.experimental.research_readiness import final_test_2025_adapter as adapter
from yuntapr.experimental.research_readiness import final_test_2025_catalogue as catalogue
from yuntapr.experimental.research_readiness import final_test_2025_manifest as manifest
from yuntapr.experimental.research_readiness import final_test_2025_planning as planning


def _sha(text: str) -> str:
    import hashlib
    return hashlib.sha256(text.encode('utf-8')).hexdigest()


def _authority(tmp_path, *, executed=False, authorized=True):
    protocol = tmp_path / 'protocol.yaml'
    protocol.write_text('draft\n', encoding='utf-8')
    implementation = [(tmp_path / 'impl.py', _sha('impl'))]
    (tmp_path / 'impl.py').write_text('impl\n', encoding='utf-8')
    files = [{'path': str(path), 'sha256': sha} for path, sha in implementation]
    checkpoints = []
    for model, seed in catalogue.CHECKPOINTS:
        meta = catalogue.CHECKPOINTS[(model, seed)]
        checkpoints.append({'model': model, 'seed': seed,
                            'path': str(tmp_path / f'{model}_{seed}.pt'),
                            'sha256': meta['sha256'],
                            'bytes': meta['bytes'] if meta['bytes'] is not None else 53903000 + seed})
    value = {
        'version': 'v1', 'AUTHORIZED_BY': 'RESEARCHER',
        'scope': adapter.SCOPE, 'FINAL_TEST_2025_AUTHORIZED': authorized,
        'FINAL_TEST_2025_EXECUTED': executed,
        'protocol': {'path': str(protocol), 'sha256': _sha('draft\n')},
        'implementation': {'files': files,
                           'sha256': manifest.canonical_sha(files)},
        'catalogue': {'path': str(tmp_path / 'cat.csv'), 'sha256': _sha('cat')},
        'population': {'path': str(tmp_path / 'pop.json'), 'sha256': _sha('pop')},
        'freeze': {'path': str(tmp_path / 'freeze.json'), 'sha256': _sha('freeze')},
        'checkpoints': checkpoints,
        'frozen_inputs': {
            'statistics': {'path': str(tmp_path / 'stats.json'), 'sha256': _sha('stats')},
            'static_pack': {'path': str(tmp_path / 'pack.npz'), 'sha256': _sha('pack')},
            'static_receipt': {'path': str(tmp_path / 'receipt.json'), 'sha256': _sha('receipt')},
            'yunnan_mask': {'path': str(tmp_path / 'mask.nc'), 'sha256': _sha('mask')},
        },
        'dote': {'pwat_reference_kg_m2': 31.85768219039871,
                 'reference_provenance': 'FROZEN_2023_TRAIN_POSITIVE_PWAT_MEAN',
                 'moisture_basis': 'windward_W', 'velocity_reference_m_s': 1.0},
        'inference': {'device': 'cpu', 'seed': 2026, 'threads': 2, 'scenes_per_batch': 1},
        'output_root': str(tmp_path / 'runs'),
        'created_utc': '2026-11-27T00:00:00+00:00',
    }
    path = tmp_path / 'authority.json'
    path.write_text(json.dumps(value), encoding='utf-8')
    return path, value


def _spectral(population_id='p' * 64):
    return {channel: TrainNormalization(channel=channel, mean=280.0, std=5.0, unit='K',
                                        fit_years=(2023,), fit_role='Train', ddof=0,
                                        population_id=population_id)
            for channel in CHANNELS}


def _fake_frozen():
    class Mapping:
        axes = {'native_lat': np.linspace(32, 19, 501, dtype='float32'),
                'native_lon': np.linspace(95, 109, 501, dtype='float32'),
                'target_lat': np.linspace(20, 29, 100, dtype='float32'),
                'target_lon': np.linspace(96, 108, 100, dtype='float32')}

        def assert_axes(self, *axes):
            assert len(axes) == 4

    region = np.zeros((100, 100), dtype=bool)
    region.reshape(-1)[:3430] = True
    return adapter.FrozenInputs(
        statistics={}, spectral=_spectral(), environment={}, pack=object(),
        terrain_scalers={}, mask=region, mapping=Mapping(), grid=object(),
        dote=None, definition=object())


def test_public_authorizers_deny():
    with pytest.raises(PermissionError):
        adapter.authorize_final_test()
    with pytest.raises(PermissionError):
        adapter.authorize_payload()


def test_authority_strict_binding(tmp_path):
    path, value = _authority(tmp_path)
    sha = _sha(path.read_text(encoding='utf-8'))
    loaded = adapter.FinalTest2025Authority.load(path, sha)
    loaded.require_final()
    assert len(loaded.checkpoint_records()) == 12
    assert loaded.checkpoints[('B4', 2029)]['bytes'] == 52913659
    with pytest.raises(PermissionError):
        loaded.require_catalogue()

    bad = json.loads(json.dumps(value, default=str))
    bad['FINAL_TEST_2025_EXECUTED'] = True
    with pytest.raises(PermissionError):
        adapter.FinalTest2025Authority(bad, sha)

    extra = dict(value, unexpected=True)
    with pytest.raises(ValueError):
        adapter.FinalTest2025Authority(extra, sha)

    wrong = json.loads(json.dumps(value))
    wrong['checkpoints'][0]['sha256'] = '0' * 64
    with pytest.raises(ValueError):
        adapter.FinalTest2025Authority(wrong, sha)


def test_authority_dry_run_reports_plan(tmp_path):
    path, _ = _authority(tmp_path)
    sha = _sha(path.read_text(encoding='utf-8'))
    plan = adapter.dry_run(path, sha)
    assert plan['status'] == 'DRY_RUN_AUTHORIZED_NO_PAYLOAD_IO'
    assert plan['payload_access'] == 'NOT_REQUESTED_NOT_OPENED'
    assert len(plan['models']) == 12
    assert plan['checkpoint_bytes_total'] == sum(
        int(adapter.FinalTest2025Authority.load(path, sha).checkpoints[(model, seed)]['bytes'])
        for model in adapter.MODELS for seed in adapter.SEEDS)


def test_paired_descriptions_are_three_seed_descriptive():
    metrics = {}
    for model in adapter.MODELS:
        for seed in adapter.SEEDS:
            metrics[(model, seed)] = {
                'Brier': 1.0 if model == 'B7' else 0.8 if model == 'B8' else 1.2,
                'conditional_mean_pinball': 0.5,
                'AUROC': None if (model, seed) == ('B8', 2030) else 0.7,
                'Average_Precision': 0.6,
                'q32_signed_bias': 0.01,
                'q32_absolute_error': 0.01,
                'mean_absolute_coverage_error': 0.02,
            }
    report = adapter.paired_descriptions(metrics)
    primary = report['pairs']['PRIMARY_B7_REAL_MINUS_B7_ZERO_DOTE']['metrics']['Brier']
    assert primary['direction'] == 'B7_REAL_MINUS_B7_ZERO_DOTE'
    assert primary['n_seeds'] == 3
    assert primary['mean'] == pytest.approx(-0.2)
    assert report['co_primary_metrics'] == ['Brier', 'conditional_mean_pinball']
    auroc = report['pairs']['SECONDARY_B8_MINUS_B7_REAL']['metrics']['AUROC']
    assert auroc['n_seeds'] == 2 and auroc['null_seeds'] == 1
    assert auroc['mean'] == pytest.approx(0.0)


def test_accumulator_matches_b0_metric_definitions():
    accumulator = adapter.FinalTest2025Accumulator()
    valid = torch.zeros((1, 1, 100, 100), dtype=torch.bool)
    valid[:, :, 0, 0:8] = True
    labels = torch.zeros((1, 1, 100, 100), dtype=torch.float64)
    labels[:, :, 0, 0] = 1.0
    labels[:, :, 0, 1] = 0.5
    rain_prob = torch.full_like(labels, 0.5)
    rain_logit = torch.zeros_like(labels)
    tau = (np.arange(1, 33) - .5) / 32
    physical = 1.0 + tau.reshape(1, 32, 1, 1) + 0.0 * np.zeros((1, 32, 100, 100))
    physical = torch.as_tensor(physical, dtype=torch.float64)
    qlog = torch.log1p(physical)
    output = SimpleNamespace(rain_logit=rain_logit, rain_prob=rain_prob,
                             conditional_quantiles_log=qlog,
                             conditional_quantiles_physical=physical)
    inputs = adapter.SceneInputs(
        sample_id='2025-03-01T00:00:00+00:00', analysis_time='2025-03-01T00:30:00+00:00',
        x=torch.zeros(1), native_valid=torch.zeros(1, dtype=torch.bool),
        environment=torch.zeros(1), environment_valid=torch.zeros(1, dtype=torch.bool),
        dynamic_real=torch.zeros(1), dynamic_zero=torch.zeros(1),
        dynamic_valid=torch.zeros(1, dtype=torch.bool),
        rate=labels, valid=valid, region=torch.ones_like(valid))
    accumulator.add(output, inputs)
    report = accumulator.report()
    assert report['N_valid'] == 8
    assert report['N_rain'] == 2
    assert report['Brier'] == pytest.approx(0.25)
    assert report['support_violation_count'] == 0
    assert report['crossing_count'] == 0
    assert len(report['coverage_error']['signed']) == 32
    assert all(value == pytest.approx(1.0) for value in report['32_tau_conditional_coverage'])
    assert report['q32_signed_bias'] == pytest.approx(1.0 - 31.5 / 32)
    expected_mae = float(np.mean(1.0 - tau))
    assert report['mean_absolute_coverage_error'] == pytest.approx(expected_mae)
    assert report['threshold_status'] == 'THRESHOLD_NOT_FROZEN'


def test_build_scene_inputs_synthetic(monkeypatch):
    layout = planning.PathLayout2025.default()
    scene = next(iter(planning.enumerate_scenes(layout, months=(3,)))).as_dict()
    frozen = _fake_frozen()

    analysis = planning.utc(scene['analysis_time'])
    frames = []
    for slot in range(6):
        nominal = planning.utc(scene[f'slot_{slot:02d}_nominal'])
        frames.append({'slot': slot, 'nominal': nominal.isoformat(),
                       'obs_start': (nominal - timedelta(minutes=2)).isoformat(),
                       'obs_end': (nominal + timedelta(minutes=2)).isoformat(),
                       'date_created': None, 'relative_path': scene[f'slot_{slot:02d}_relative_path'],
                       'bytes': 1, 'sha256': '0' * 64, 'channels': list(CHANNELS),
                       'full_valid': True})
    native_lat = np.linspace(32, 19, 501, dtype='float32')
    native_lon = np.linspace(95, 109, 501, dtype='float32')
    satellite = {'values': np.full((6, 7, 501, 501), 280.0, dtype=np.float32),
                 'frames': tuple(frames), 'native_lat': native_lat, 'native_lon': native_lon}
    target_lat = np.linspace(20, 29, 100, dtype='float32')
    target_lon = np.linspace(96, 108, 100, dtype='float32')
    rate = np.zeros((100, 100), dtype=np.float64)
    rate[0, 0] = 0.5
    target = {'rate': rate, 'valid': np.ones((100, 100), dtype=bool),
              'target_lat': target_lat, 'target_lon': target_lon}
    payload = {'scene': scene, 'satellite': satellite,
               'environment': {'environment': object()}, 'target': target}

    def fake_prepare_mee(frame, *, target_grid, scalers, keys=MEE_V13_KEYS):
        assert tuple(keys) == MEE_V13_KEYS
        return (np.zeros((13, 100, 100), dtype=np.float32),
                np.ones((13, 100, 100), dtype=bool), tuple(keys))

    monkeypatch.setattr(adapter, 'prepare_mee', fake_prepare_mee)
    monkeypatch.setattr(adapter, 'PhysicalDote', lambda pack, definition: (
        lambda frame: (np.zeros((8, 100, 100), dtype=np.float32),
                       np.ones((8, 100, 100), dtype=bool))))
    monkeypatch.setattr(adapter, 'ZeroNumericDote', lambda pack, definition: (
        lambda frame: (np.zeros((8, 100, 100), dtype=np.float32),
                       np.ones((8, 100, 100), dtype=bool))))

    inputs = adapter.build_scene_inputs(payload, frozen, device='cpu')
    assert inputs.x.shape == (1, 42, 501, 501)
    assert inputs.x.dtype == torch.float32
    assert inputs.environment.shape == (1, 13, 100, 100)
    assert inputs.dynamic_real.shape == (1, 8, 100, 100)
    assert inputs.dynamic_zero.shape == (1, 8, 100, 100)
    assert float(inputs.dynamic_zero.abs().sum()) == 0.0
    assert inputs.rate.dtype == torch.float64
    assert inputs.valid.dtype == torch.bool
    assert inputs.rate.shape == (1, 1, 100, 100)
    assert analysis == planning.utc(scene['analysis_time'])


def test_scene_population_requires_contiguous_indices():
    good = [{'candidate_index': 0, 'sample_id': 'a'}, {'candidate_index': 1, 'sample_id': 'b'}]
    assert adapter.validate_scene_population({'scene_records': good}) == good
    bad = [{'candidate_index': 0, 'sample_id': 'a'}, {'candidate_index': 2, 'sample_id': 'b'}]
    with pytest.raises(ValueError):
        adapter.validate_scene_population({'scene_records': bad})
    with pytest.raises(ValueError):
        adapter.validate_scene_population({'scene_records': []})
    with pytest.raises(ValueError):
        adapter.validate_scene_population({'scene_records': [good[0], good[0]]})
