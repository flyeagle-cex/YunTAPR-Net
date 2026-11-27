"""Stat-only 2025 inventory tests: synthetic temp roots, zero payload I/O."""
import builtins
import importlib.util
import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from yuntapr.experimental.research_readiness import final_test_2025_inventory as inventory
from yuntapr.experimental.research_readiness import final_test_2025_planning as planning

REPO_ROOT = Path(__file__).resolve().parents[2]


def _layout(tmp_path):
    return planning.PathLayout2025(
        himawari_root=str(tmp_path / 'HIM'),
        imerg_root=str(tmp_path / 'IMERG'),
        gfs_root=str(tmp_path / 'GFS'),
        gfs_thermo_root=str(tmp_path / 'GFST'),
    )


def _window():
    return dict(
        months=(3,),
        analysis_start=datetime(2025, 3, 1, 0, 0, tzinfo=timezone.utc),
        analysis_end=datetime(2025, 3, 1, 12, 0, tzinfo=timezone.utc),
    )


def _mock_authorization():
    return {
        'version': inventory.INVENTORY_VERSION,
        'decision_id': 'TEST-2025-INVENTORY-MEASUREMENT',
        'AUTHORIZED_BY': 'RESEARCHER',
        'scope': inventory.INVENTORY_SCOPE,
        'INVENTORY_MEASUREMENT_2025_AUTHORIZED': True,
        'protocol_sha256': inventory.sha256_file(REPO_ROOT / inventory.PROTOCOL_RELPATH),
        'implementation_sha256': inventory.implementation_hashes(REPO_ROOT),
        'created_utc': datetime(2026, 11, 28, 0, 0, tzinfo=timezone.utc).isoformat(),
    }


def _make_tree(layout, expected, size=16):
    for kind in inventory.MODALITY_ORDER:
        for relpath in expected['unique_paths'][kind]:
            target = Path(layout.root(kind)) / Path(relpath)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(b'x' * size)


def test_plan_counts_full_and_small(tmp_path):
    plan = inventory.plan_counts()
    assert plan['expected_scenes'] == 856
    assert plan['expected_unique'] == {'himawari': 5136, 'gfs_main': 856,
                                       'gfs_thermo': 856, 'imerg': 215}
    assert plan['total_unique'] == 7063
    small = inventory.build_expected(_layout(tmp_path), **_window())
    assert small['expected_scenes'] == 2
    assert small['expected_unique'] == {'himawari': 12, 'gfs_main': 2,
                                        'gfs_thermo': 2, 'imerg': 2}


def test_scope_guard_allows_carry_in_and_rejects_october(tmp_path):
    inventory._assert_frozen_scope(
        '202502/28/NC_H09_20250228_2300_R21_FLDK.06001_06001.nc')
    inventory._assert_frozen_scope('2025/20250228/gfs_0p25_2025022818_f006.nc')
    inventory._assert_frozen_scope('2025/imerg_20250228.nc')
    with pytest.raises(PermissionError):
        inventory._assert_frozen_scope(
            '202510/01/NC_H09_20251001_0020_R21_FLDK.06001_06001.nc')
    with pytest.raises(PermissionError):
        inventory._assert_frozen_scope('2025/20250227/gfs_0p25_2025022718_f006.nc')
    with pytest.raises(ValueError):
        inventory._assert_frozen_scope('../2025/20250301/imerg_20250301.nc')


def test_measure_is_stat_only(tmp_path, monkeypatch):
    layout = _layout(tmp_path)
    expected = inventory.build_expected(layout, **_window())
    _make_tree(layout, expected)

    def _forbidden(*args, **kwargs):
        raise AssertionError('payload content must not be opened during measurement')

    monkeypatch.setattr(builtins, 'open', _forbidden)
    records, stat_calls, errors, elapsed = inventory.measure_files(layout, expected)
    monkeypatch.undo()
    assert errors == []
    assert stat_calls == 18
    summary = inventory.summarize(records, expected)
    assert summary['total_missing_unique'] == 0
    assert summary['total_bytes'] == 18 * 16
    assert summary['per_modality']['himawari']['present_unique'] == 12


def test_missing_files_are_counted(tmp_path):
    layout = _layout(tmp_path)
    expected = inventory.build_expected(layout, **_window())
    _make_tree(layout, expected)
    victim = Path(layout.root('himawari')) / Path(expected['unique_paths']['himawari'][0])
    victim.unlink()
    records, stat_calls, errors, elapsed = inventory.measure_files(layout, expected)
    summary = inventory.summarize(records, expected)
    assert errors == []
    assert summary['total_missing_unique'] == 1
    assert summary['missing_paths'][0]['modality'] == 'himawari'


def test_authorization_validation():
    payload = _mock_authorization()
    policy = inventory.validate_authorization(payload, REPO_ROOT)
    assert policy['authorized_by'] == 'RESEARCHER'
    assert policy['scope'] == inventory.INVENTORY_SCOPE
    with pytest.raises(ValueError):
        inventory.validate_authorization(dict(payload, scope='WRONG-SCOPE'), REPO_ROOT)
    with pytest.raises(PermissionError):
        inventory.validate_authorization(
            dict(payload, INVENTORY_MEASUREMENT_2025_AUTHORIZED=False), REPO_ROOT)
    with pytest.raises(ValueError):
        inventory.validate_authorization(dict(payload, extra='x'), REPO_ROOT)
    with pytest.raises(PermissionError):
        inventory.validate_authorization(dict(payload, protocol_sha256='0' * 64), REPO_ROOT)
    bad_impl = dict(payload['implementation_sha256'])
    bad_impl[next(iter(bad_impl))] = '0' * 64
    with pytest.raises(PermissionError):
        inventory.validate_authorization(dict(payload, implementation_sha256=bad_impl), REPO_ROOT)
    with pytest.raises(ValueError):
        inventory.validate_authorization(
            dict(payload, created_utc='2024-01-01T00:00:00+00:00'), REPO_ROOT)


def test_run_measurement_end_to_end(tmp_path):
    layout = _layout(tmp_path)
    expected = inventory.build_expected(layout, **_window())
    _make_tree(layout, expected)
    auth_path = tmp_path / 'authorization.json'
    auth_path.write_text(json.dumps(_mock_authorization()), encoding='utf-8')
    auth_sha = inventory.sha256_file(auth_path)
    output_root = tmp_path / 'run1'
    status = inventory.run_measurement(
        auth_path, auth_sha, output_root, repo_root=REPO_ROOT, layout=layout, **_window())
    assert status['INVENTORY_MEASUREMENT_2025_EXECUTED'] is True
    assert status['PAYLOAD_CONTENT_READS'] == 0
    assert status['FINAL_TEST_2025_EXECUTED'] is False
    run = json.loads((output_root / 'inventory_measurement_v1.json').read_text(encoding='utf-8'))
    assert run['observed']['total_missing_unique'] == 0
    assert run['observed']['total_bytes'] == 18 * 16
    assert run['guards']['payload_files_opened'] == 0
    assert run['guards']['checkpoint_loads'] == 0
    assert run['guards']['metrics_computed'] == 0
    assert run['runtime']['stat_calls'] == 18
    assert (output_root / 'inventory_measurement_summary.json').is_file()
    with pytest.raises(FileExistsError):
        inventory.run_measurement(
            auth_path, auth_sha, output_root, repo_root=REPO_ROOT, layout=layout, **_window())


def test_run_measurement_rejects_bad_authorization_digest(tmp_path):
    layout = _layout(tmp_path)
    _make_tree(layout, inventory.build_expected(layout, **_window()))
    auth_path = tmp_path / 'authorization.json'
    auth_path.write_text(json.dumps(_mock_authorization()), encoding='utf-8')
    with pytest.raises(PermissionError):
        inventory.run_measurement(
            auth_path, '0' * 64, tmp_path / 'run_bad', repo_root=REPO_ROOT,
            layout=layout, **_window())


def test_cli_plan(capsys):
    spec = importlib.util.spec_from_file_location(
        'measure_cli', REPO_ROOT / 'tools/research_readiness/measure_b4_b7_b8_2025_inventory.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert module.main(['plan']) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload['expected_scenes'] == 856
    assert payload['status'] == 'PLAN_ONLY_NO_PAYLOAD_ACCESS'
