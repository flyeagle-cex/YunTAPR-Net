"""2025 catalogue QC execution tests: synthetic payload roots, injected IMERG decoder.

Every test payload lives under a temporary directory.  No 2025 payload root is
opened, stat-ed or listed; the real measurement JSON is never used here.
"""
import hashlib
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from yuntapr.experimental.research_readiness import final_test_2025_catalogue as catalogue
from yuntapr.experimental.research_readiness import final_test_2025_catalogue_execution as execution
from yuntapr.experimental.research_readiness import final_test_2025_inventory as inventory
from yuntapr.experimental.research_readiness import final_test_2025_planning as planning

REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = REPO_ROOT / 'src'
CLI = REPO_ROOT / 'tools' / 'research_readiness' / 'run_b4_b7_b8_2025_catalogue_qc.py'
SIZES = {'himawari': 4096, 'gfs_main': 2048, 'gfs_thermo': 1024, 'imerg': 8192}
IMERG_COUNTS = (120,) * execution.IMERG_COUNT


def sha(text):
    return hashlib.sha256(text.encode()).hexdigest()


def synthetic_layout(root):
    root = Path(root)
    return planning.PathLayout2025(
        himawari_root=str(root / 'himawari'), imerg_root=str(root / 'imerg'),
        gfs_root=str(root / 'gfs'), gfs_thermo_root=str(root / 'gfs_thermo'))


def content(modality, relative_path):
    size = SIZES[modality]
    seed = hashlib.sha256((modality + '/' + relative_path).encode()).digest()
    return (seed * (size // len(seed) + 1))[:size]


def write_json(path, payload):
    path = Path(path)
    path.write_text(json.dumps(payload, indent=2), encoding='utf-8')
    return inventory.sha256_file(path)


class RecordingDecoder:
    def __init__(self, counts=IMERG_COUNTS, error=None):
        self.counts = tuple(counts)
        self.error = error
        self.calls = []

    def __call__(self, path, day_start):
        self.calls.append((Path(path).resolve(), day_start.isoformat()))
        if self.error is not None:
            raise self.error
        return {'product': catalogue.IMERG_PRODUCT, 'version': catalogue.IMERG_VERSION,
                'run_type': catalogue.IMERG_RUN_TYPE,
                'time_grid_provenance_pass': True,
                'valid_yunnan_counts': self.counts}


class RecordingOpener:
    def __init__(self):
        self.paths = []

    def __call__(self, path, mode):
        self.paths.append(Path(path).resolve())
        return execution._open_binary(path, mode)


class Fixture:
    """Synthetic March payload skeleton plus its stat-only measurement and grant."""

    def __init__(self, root, *, months=(3,), skip=()):
        self.root = Path(root)
        self.months = tuple(months)
        self.layout = synthetic_layout(self.root)
        self.scenes = planning.enumerate_scenes(self.layout, months=self.months)
        self.contents = {}
        for scene in self.scenes:
            for frame in scene.satellites:
                self.contents[('himawari', frame.relative_path)] = content('himawari', frame.relative_path)
            for kind, attribute in (('gfs_main', 'gfs_main_relative_path'),
                                    ('gfs_thermo', 'gfs_thermo_relative_path'),
                                    ('imerg', 'imerg_day_relative_path')):
                relative_path = getattr(scene, attribute)
                self.contents[(kind, relative_path)] = content(kind, relative_path)
        self.skip = {tuple(item) for item in skip}
        for (modality, relative_path), payload in self.contents.items():
            if (modality, relative_path) in self.skip:
                continue
            target = self.layout.root(modality) / relative_path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(payload)
        authorization = {
            'version': inventory.INVENTORY_VERSION,
            'decision_id': 'SYNTHETIC_QC_UNIT_TEST_MEASUREMENT',
            'AUTHORIZED_BY': 'RESEARCHER',
            'scope': inventory.INVENTORY_SCOPE,
            'INVENTORY_MEASUREMENT_2025_AUTHORIZED': True,
            'protocol_sha256': inventory.sha256_file(REPO_ROOT / inventory.PROTOCOL_RELPATH),
            'implementation_sha256': inventory.implementation_hashes(REPO_ROOT),
            'created_utc': '2026-01-01T00:00:00+00:00',
        }
        measurement_authorization = self.root / 'measurement_authorization.json'
        self.measurement_authorization_sha = write_json(measurement_authorization, authorization)
        run_root = self.root / 'measurement_run'
        inventory.run_measurement(measurement_authorization, self.measurement_authorization_sha,
                                  run_root, layout=self.layout, months=self.months)
        self.measurement_path = run_root / 'inventory_measurement_v1.json'
        self.measurement_sha = inventory.sha256_file(self.measurement_path)
        self.document = json.loads(self.measurement_path.read_text(encoding='utf-8'))
        self.catalogue_auth_path = self.root / 'catalogue_authorization.json'
        self.catalogue_auth_sha = write_json(self.catalogue_auth_path,
                                             self.catalogue_authorization())

    def catalogue_authorization(self, *, qc=True, measurement=None):
        return {
            'version': 'v1', 'decision_id': 'SYNTHETIC_QC_UNIT_TEST',
            'AUTHORIZED_BY': 'RESEARCHER', 'scope': catalogue.CATALOGUE_SCOPE,
            'FINAL_TEST_CATALOGUE_AUTHORIZED': True, 'FINAL_TEST_2025_AUTHORIZED': False,
            'CATALOGUE_QC_PAYLOAD_AUTHORIZED': qc,
            'protocol': {'path': inventory.PROTOCOL_RELPATH,
                         'sha256': self.document['protocol_sha256']},
            'implementation': execution.implementation_binding(REPO_ROOT),
            'checkpoint_catalog_sha256': catalogue.CHECKPOINT_CATALOG_SHA256,
            'source_roots': {'himawari': planning.HIMAWARI_ROOT, 'imerg': planning.IMERG_ROOT,
                             'gfs': planning.GFS_ROOT, 'gfs_thermo': planning.GFS_THERMO_ROOT},
            'inventory_measurement': measurement or {
                'path': str(self.measurement_path), 'sha256': self.measurement_sha,
                'created_utc': self.document['created_utc']},
            'identity': dict(catalogue.FROZEN_IDENTITY_2025),
            'created_utc': self.document['created_utc'],
        }

    def output(self, name='out'):
        return self.root / name

    def present_paths(self):
        return [execution.payload_path(self.layout, record['modality'], record['relative_path'])
                for record in self.document['files'] if record['exists']]

    def imerg_paths(self):
        return [record['relative_path'] for record in self.document['files']
                if record['modality'] == 'imerg' and record['exists']]


def run_qc(fixture, *, decoder=None, output=None, auth_path=None, auth_sha=None,
           measurement_path=None, measurement_sha=None, opener=None, chunk_bytes=1 << 20):
    return execution.run_catalogue_qc(
        auth_path or fixture.catalogue_auth_path,
        auth_sha or fixture.catalogue_auth_sha,
        measurement_path or fixture.measurement_path,
        measurement_sha or fixture.measurement_sha,
        output or fixture.output(),
        layout=fixture.layout, chunk_bytes=chunk_bytes,
        decoder=decoder or RecordingDecoder(), opener=opener)


class CatalogueQCExecutionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._tempdir = tempfile.TemporaryDirectory()
        cls.fixture = Fixture(cls._tempdir.name)

    @classmethod
    def tearDownClass(cls):
        cls._tempdir.cleanup()

    def temp_fixture(self, **kwargs):
        tempdir = tempfile.TemporaryDirectory()
        self.addCleanup(tempdir.cleanup)
        return Fixture(tempdir.name, **kwargs)

    def read_failure(self, output):
        failure = json.loads((Path(output) / execution.FAILURE_FILENAME).read_text(encoding='utf-8'))
        self.assertEqual(failure['status'], 'STOP_REQUIRED')
        self.assertFalse(failure['automatic_retry'])
        return failure

    def test_validate_measurement_rebuilds_the_scene_plan(self):
        facts = execution.validate_measurement(self.fixture.document, layout=self.fixture.layout)
        expected = self.fixture.document['expected']
        self.assertEqual(facts['scene_count'], 124)
        self.assertEqual(facts['scene_count'], expected['expected_scenes'])
        self.assertEqual(sum(facts['expected']['expected_unique'].values()),
                         expected['total_unique'])
        self.assertEqual(len(facts['files']), expected['total_unique'])
        self.assertEqual(len(facts['present']), expected['total_unique'])
        self.assertEqual(facts['missing'], [])
        self.assertEqual(facts['total_bytes'], self.fixture.document['observed']['total_bytes'])
        self.assertEqual(facts['expected']['expected_unique']['imerg'],
                         len(self.fixture.imerg_paths()))
        self.assertEqual(facts['inventory_sha256'],
                         self.fixture.document['integrity']['inventory_sha256'])

    def test_run_completes_and_binds_every_payload_hash(self):
        opener = RecordingOpener()
        decoder = RecordingDecoder()
        status = run_qc(self.fixture, decoder=decoder, opener=opener, chunk_bytes=7)
        self.assertEqual(status['status'], execution.STATUS_COMPLETED)
        self.assertEqual(status['payload_files_hashed'], len(self.fixture.present_paths()))
        self.assertEqual(status['payload_bytes_hashed'],
                         self.fixture.document['observed']['total_bytes'])
        self.assertEqual(status['scene_count'], 124)
        self.assertEqual(status['eligible_count'], 124)
        self.assertEqual(status['rejected_count'], 0)
        self.assertEqual(status['imerg_days_decoded'], len(self.fixture.imerg_paths()))
        self.assertFalse(status['final_test_2025_executed'])
        self.assertEqual(status['identity'], catalogue.FROZEN_IDENTITY_2025)
        self.assertEqual(status['inventory_measurement_sha256'], self.fixture.measurement_sha)
        self.assertEqual(set(opener.paths), {path.resolve() for path in self.fixture.present_paths()})
        self.assertEqual(sorted(call[0] for call in decoder.calls),
                         sorted(execution.payload_path(self.fixture.layout, 'imerg', path).resolve()
                                for path in self.fixture.imerg_paths()))
        self.assertTrue(all(value == 0 for key, value in status['guards'].items()
                            if key != 'final_test_2025_executed'))
        output = self.fixture.output()
        for name in (execution.ENTRIES_FILENAME, execution.SUMMARY_FILENAME,
                     execution.LEDGER_FILENAME, execution.FINAL_STATUS_FILENAME,
                     catalogue.CATALOGUE_FILENAME, catalogue.POPULATION_FILENAME,
                     catalogue.FREEZE_FILENAME):
            self.assertTrue((output / name).is_file(), name)
        self.assertFalse((output / execution.FAILURE_FILENAME).exists())
        ledger = [json.loads(line) for line in
                  (output / execution.LEDGER_FILENAME).read_text(encoding='utf-8').splitlines()]
        events = [event['event'] for event in ledger]
        self.assertEqual(events.count('PAYLOAD_HASH'), len(self.fixture.present_paths()))
        self.assertEqual(events.count('IMERG_DECODE'), len(self.fixture.imerg_paths()))
        self.assertEqual(events.count('MISSING_VERIFIED'), 0)
        entries = json.loads((output / execution.ENTRIES_FILENAME).read_text(encoding='utf-8'))
        self.assertEqual(entries['entry_count'], self.fixture.document['expected']['total_unique'])
        self.assertEqual(entries['present_count'], len(self.fixture.present_paths()))
        self.assertEqual(entries['missing_count'], 0)
        self.assertEqual(sum(1 for entry in entries['entries'] if entry['exists']),
                         len(self.fixture.present_paths()))
        freeze = json.loads((output / catalogue.FREEZE_FILENAME).read_text(encoding='utf-8'))
        self.assertEqual(freeze['status'], 'CATALOGUE_FROZEN')
        self.assertFalse(freeze['fixture_only'])
        self.assertFalse(freeze['payload_access_authorized'])
        self.assertEqual(freeze['identity'], catalogue.FROZEN_IDENTITY_2025)
        self.assertEqual(freeze['eligible_count'], 124)
        rows = catalogue.read_csv(output / catalogue.CATALOGUE_FILENAME)
        self.assertEqual(len(rows), 124)
        self.assertTrue(all(row['eligible'] for row in rows))
        summary = json.loads((output / execution.SUMMARY_FILENAME).read_text(encoding='utf-8'))
        self.assertEqual(summary['hashed_bytes'], status['payload_bytes_hashed'])
        self.assertEqual(summary['imerg_half_hours_checked'],
                         len(self.fixture.imerg_paths()) * execution.IMERG_COUNT)

    def test_hash_reflects_actual_file_content(self):
        fixture = self.temp_fixture()
        record = next(item for item in fixture.document['files'] if item['exists'])
        target = execution.payload_path(fixture.layout, record['modality'], record['relative_path'])
        replacement = b'x' * record['bytes']
        target.write_bytes(replacement)
        status = run_qc(fixture)
        entries = json.loads((fixture.output() / execution.ENTRIES_FILENAME).read_text(encoding='utf-8'))
        entry = next(item for item in entries['entries']
                     if item['modality'] == record['modality']
                     and item['relative_path'] == record['relative_path'])
        self.assertEqual(entry['sha256'], hashlib.sha256(replacement).hexdigest())
        self.assertEqual(status['payload_files_hashed'], len(fixture.present_paths()))

    def test_missing_payload_is_verified_and_rejected(self):
        tempdir = tempfile.TemporaryDirectory()
        self.addCleanup(tempdir.cleanup)
        layout = synthetic_layout(tempdir.name)
        scenes = planning.enumerate_scenes(layout, months=(3,))
        skipped = ('gfs_thermo', scenes[10].gfs_thermo_relative_path)
        fixture = Fixture(tempdir.name, skip=(skipped,))
        self.assertEqual(fixture.document['observed']['total_missing_unique'], 1)
        status = run_qc(fixture)
        self.assertEqual(status['rejected_count'], 1)
        self.assertEqual(status['eligible_count'], 123)
        self.assertEqual(status['payload_files_hashed'], len(fixture.present_paths()))
        rows = catalogue.read_csv(fixture.output() / catalogue.CATALOGUE_FILENAME)
        rejected = [row for row in rows if not row['eligible']]
        self.assertEqual([row['rejection_reason'] for row in rejected], ['MISSING_GFS_THERMO'])
        ledger = [json.loads(line) for line in
                  (fixture.output() / execution.LEDGER_FILENAME).read_text(encoding='utf-8').splitlines()]
        missing = [event for event in ledger if event['event'] == 'MISSING_VERIFIED']
        self.assertEqual(len(missing), 1)
        self.assertEqual(missing[0]['relative_path'], scenes[10].gfs_thermo_relative_path)

    def test_measured_missing_payload_now_present_stops(self):
        tempdir = tempfile.TemporaryDirectory()
        self.addCleanup(tempdir.cleanup)
        layout = synthetic_layout(tempdir.name)
        scenes = planning.enumerate_scenes(layout, months=(3,))
        skipped = ('gfs_main', scenes[3].gfs_main_relative_path)
        fixture = Fixture(tempdir.name, skip=(skipped,))
        target = fixture.layout.root('gfs_main') / skipped[1]
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(b'late')
        with self.assertRaises(RuntimeError):
            run_qc(fixture)
        failure = self.read_failure(fixture.output())
        self.assertGreater(failure['payload_files_hashed'], 0)

    def test_payload_size_drift_stops(self):
        fixture = self.temp_fixture()
        record = next(item for item in fixture.document['files'] if item['exists'])
        target = execution.payload_path(fixture.layout, record['modality'], record['relative_path'])
        with target.open('ab') as handle:
            handle.write(b'x')
        with self.assertRaises(RuntimeError):
            run_qc(fixture)
        failure = self.read_failure(fixture.output())
        self.assertEqual(failure['payload_files_hashed'], 0)

    def test_measurement_digest_mismatch_stops_before_payload(self):
        fixture = self.temp_fixture()
        opener = RecordingOpener()
        with self.assertRaises(PermissionError):
            run_qc(fixture, measurement_sha='0' * 64, opener=opener)
        failure = self.read_failure(fixture.output())
        self.assertEqual(failure['payload_files_hashed'], 0)
        self.assertEqual(opener.paths, [])

    def test_measurement_binding_mismatch_stops_before_payload(self):
        fixture = self.temp_fixture()
        auth = fixture.catalogue_authorization(
            measurement={'path': str(fixture.measurement_path), 'sha256': sha('other'),
                         'created_utc': fixture.document['created_utc']})
        auth_path = fixture.root / 'bad_binding_authorization.json'
        auth_sha = write_json(auth_path, auth)
        with self.assertRaises(PermissionError):
            run_qc(fixture, auth_path=auth_path, auth_sha=auth_sha,
                   output=fixture.output('bad-binding'))
        failure = self.read_failure(fixture.output('bad-binding'))
        self.assertEqual(failure['payload_files_hashed'], 0)

    def test_missing_qc_payload_grant_stops(self):
        fixture = self.temp_fixture()
        auth_path = fixture.root / 'no_grant_authorization.json'
        auth_sha = write_json(auth_path, fixture.catalogue_authorization(qc=False))
        with self.assertRaises(PermissionError):
            run_qc(fixture, auth_path=auth_path, auth_sha=auth_sha,
                   output=fixture.output('no-grant'))
        failure = self.read_failure(fixture.output('no-grant'))
        self.assertEqual(failure['payload_files_hashed'], 0)
        self.assertEqual(failure['payload_decode_opens'], 0)

    def test_implementation_drift_stops_before_payload(self):
        fixture = self.temp_fixture()
        auth = fixture.catalogue_authorization()
        auth['implementation'] = dict(auth['implementation'])
        tampered = dict(auth['implementation']['files'])
        tampered[execution.IMPLEMENTATION_FILES[0]] = '0' * 64
        auth['implementation']['files'] = tampered
        auth_path = fixture.root / 'drifted_implementation_authorization.json'
        auth_sha = write_json(auth_path, auth)
        opener = RecordingOpener()
        with self.assertRaises(PermissionError):
            run_qc(fixture, auth_path=auth_path, auth_sha=auth_sha,
                   output=fixture.output('drifted-implementation'), opener=opener)
        failure = self.read_failure(fixture.output('drifted-implementation'))
        self.assertEqual(failure['payload_files_hashed'], 0)
        self.assertEqual(opener.paths, [])

    def test_tampered_measurement_content_stops(self):
        document = json.loads(self.fixture.measurement_path.read_text(encoding='utf-8'))
        record = next(item for item in document['files'] if item['exists'])
        record['bytes'] = int(record['bytes']) + 1
        with self.assertRaises(ValueError):
            execution.validate_measurement(document, layout=self.fixture.layout)

    def test_decoder_contract_violation_stops(self):
        fixture = self.temp_fixture()
        with self.assertRaises(ValueError):
            run_qc(fixture, decoder=RecordingDecoder(counts=(120,) * 47))
        failure = self.read_failure(fixture.output())
        self.assertGreater(failure['payload_files_hashed'], 0)

    def test_decoder_exception_stops(self):
        fixture = self.temp_fixture()
        with self.assertRaises(OSError):
            run_qc(fixture, decoder=RecordingDecoder(error=OSError('synthetic decode failure')))
        failure = self.read_failure(fixture.output())
        self.assertGreater(failure['payload_decode_opens'], 0)

    @unittest.skipIf(importlib.util.find_spec('netCDF4') is not None,
                     'netCDF4 is installed; the lazy-import STOP cannot be exercised')
    def test_default_decoder_without_netcdf4_stops(self):
        fixture = self.temp_fixture()
        with self.assertRaises((ImportError, RuntimeError)):
            execution.run_catalogue_qc(
                fixture.catalogue_auth_path, fixture.catalogue_auth_sha,
                fixture.measurement_path, fixture.measurement_sha, fixture.output(),
                layout=fixture.layout)
        failure = self.read_failure(fixture.output())
        self.assertIn(failure['error_type'], ('ImportError', 'RuntimeError'))

    def test_append_only_output_directory(self):
        fixture = self.temp_fixture()
        run_qc(fixture)
        with self.assertRaises(FileExistsError):
            run_qc(fixture)
        self.assertFalse((fixture.output() / execution.FAILURE_FILENAME).exists())

    def test_extra_unmeasured_file_is_never_opened(self):
        fixture = self.temp_fixture()
        extra = fixture.layout.root('himawari') / '2025' / '0101' / 'NC_H09_20250101_0000_R21_FLDK.06001_06001.nc'
        extra.parent.mkdir(parents=True, exist_ok=True)
        extra.write_bytes(b'not-a-measured-payload')
        opener = RecordingOpener()
        status = run_qc(fixture, opener=opener, output=fixture.output('extra'))
        self.assertEqual(status['status'], execution.STATUS_COMPLETED)
        self.assertNotIn(extra.resolve(), opener.paths)
        self.assertEqual(set(opener.paths), {path.resolve() for path in fixture.present_paths()})

    def test_measurement_plan_reports_counts_without_payload_io(self):
        plan = execution.measurement_plan(self.fixture.document)
        self.assertEqual(plan['status'], 'PLAN_ONLY_NO_PAYLOAD_ACCESS')
        self.assertEqual(plan['expected_unique'],
                         self.fixture.document['expected']['expected_unique'])
        self.assertEqual(plan['payload_files_to_hash'], len(self.fixture.present_paths()))
        self.assertEqual(plan['payload_bytes_to_hash'],
                         self.fixture.document['observed']['total_bytes'])
        self.assertEqual(plan['imerg_days_to_decode'], len(self.fixture.imerg_paths()))

    def test_cli_plan_prints_counts_and_opens_no_payload(self):
        environment = dict(os.environ)
        environment['PYTHONPATH'] = os.pathsep.join(
            [str(SRC_ROOT), environment.get('PYTHONPATH', '')])
        result = subprocess.run(
            [sys.executable, str(CLI), 'plan',
             '--inventory-measurement', str(self.fixture.measurement_path)],
            cwd=str(REPO_ROOT), env=environment, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        plan = json.loads(result.stdout)
        self.assertEqual(plan['status'], 'PLAN_ONLY_NO_PAYLOAD_ACCESS')
        self.assertEqual(plan['payload_files_to_hash'], len(self.fixture.present_paths()))
        self.assertEqual(plan['inventory_measurement_sha256'], self.fixture.measurement_sha)

    def test_cli_run_fails_closed_without_default_layout(self):
        environment = dict(os.environ)
        environment['PYTHONPATH'] = os.pathsep.join(
            [str(SRC_ROOT), environment.get('PYTHONPATH', '')])
        output = self.fixture.output('cli-run')
        result = subprocess.run(
            [sys.executable, str(CLI), 'run',
             '--authorization', str(self.fixture.catalogue_auth_path),
             '--authorization-sha256', self.fixture.catalogue_auth_sha,
             '--inventory-measurement', str(self.fixture.measurement_path),
             '--inventory-measurement-sha256', self.fixture.measurement_sha,
             '--output-dir', str(output)],
            cwd=str(REPO_ROOT), env=environment, capture_output=True, text=True)
        self.assertEqual(result.returncode, 2)
        failure = self.read_failure(output)
        self.assertEqual(failure['payload_files_hashed'], 0)


if __name__ == '__main__':
    unittest.main()
