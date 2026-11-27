"""2025 catalogue gate tests: inventory-only build, whitelist, authority ordering."""
import copy
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from yuntapr.experimental.research_readiness import final_test_2025_catalogue as c
from yuntapr.experimental.research_readiness import final_test_2025_manifest as m
from yuntapr.experimental.research_readiness import final_test_2025_planning as p

REPO_ROOT = Path(__file__).resolve().parents[2]
MEASUREMENT_RELPATH = ('docs/research_readiness/20261128_b4_b7_b8_2025_final_test/'
                       'inventory_runs/run_20261127T074800Z/inventory_measurement_v1.json')


def sha(text):
    return hashlib.sha256(text.encode()).hexdigest()


def identity():
    return {key: sha(key) for key in m.IDENTITY_FIELDS}


def fixture_rows(root, count=10):
    layout = p.synthetic_layout(root)
    rows = p.enumerate_scenes(layout, analysis_start='2025-03-01T00:00:00+00:00',
                              analysis_end='2025-03-03T12:00:00+00:00')
    assert len(rows) == count
    return [row.as_dict() for row in rows]


def inventory_for(scene_rows, *, imerg_override=None, drop_imerg_index=None):
    entries = {}
    for position, scene in enumerate(scene_rows):
        for slot in range(6):
            path = scene[f'slot_{slot:02d}_relative_path']
            entries[('himawari', path)] = {'modality': 'himawari', 'relative_path': path,
                                           'bytes': 7000 + position, 'sha256': sha(path), 'readable': True}
        for kind in ('gfs_main', 'gfs_thermo'):
            path = scene[f'{kind}_relative_path']
            entries[(kind, path)] = {'modality': kind, 'relative_path': path, 'bytes': 900 + position,
                                     'sha256': sha(path), 'readable': True}
        if drop_imerg_index is not None and position == drop_imerg_index:
            continue
        path = scene['imerg_day_relative_path']
        imerg = {'modality': 'imerg', 'relative_path': path, 'bytes': 5000 + position,
                 'sha256': sha(path), 'readable': True, 'product': c.IMERG_PRODUCT,
                 'version': c.IMERG_VERSION, 'run_type': c.IMERG_RUN_TYPE,
                 'time_grid_provenance_pass': True, 'valid_yunnan_count': 120}
        if imerg_override:
            imerg.update(imerg_override)
        entries[('imerg', path)] = imerg
    if drop_imerg_index is not None:
        entries.pop(('imerg', scene_rows[drop_imerg_index]['imerg_day_relative_path']), None)
    return list(entries.values())


def measurement_binding(created_utc=None):
    return {'path': str(REPO_ROOT / MEASUREMENT_RELPATH), 'sha256': sha('measurement'),
            'created_utc': created_utc or '2026-01-01T00:00:00+00:00'}


def real_authorization(created_utc, *, measurement_created_utc=None, measurement=None,
                       frozen_identity=None):
    return c.CatalogueAuthorization2025({
        'version': 'v1', 'decision_id': 'CATALOGUE_QC_2025_STAT_ONLY',
        'AUTHORIZED_BY': 'RESEARCHER', 'scope': c.CATALOGUE_SCOPE,
        'FINAL_TEST_CATALOGUE_AUTHORIZED': True, 'FINAL_TEST_2025_AUTHORIZED': False,
        'CATALOGUE_QC_PAYLOAD_AUTHORIZED': True,
        'protocol': {'path': c.PROTOCOL_FILENAME, 'sha256': sha('protocol')},
        'implementation': {'sha256': sha('implementation'),
                           'files': {'src/yuntapr/experimental/research_readiness/final_test_2025_catalogue.py': sha('impl')}},
        'checkpoint_catalog_sha256': c.CHECKPOINT_CATALOG_SHA256,
        'source_roots': {'himawari': p.HIMAWARI_ROOT, 'imerg': p.IMERG_ROOT,
                         'gfs': p.GFS_ROOT, 'gfs_thermo': p.GFS_THERMO_ROOT},
        'inventory_measurement': measurement or measurement_binding(measurement_created_utc),
        'identity': dict(frozen_identity or c.FROZEN_IDENTITY_2025),
        'created_utc': created_utc,
    })


class Catalogue2025Tests(unittest.TestCase):
    def test_checkpoint_catalog_is_exactly_twelve(self):
        self.assertEqual(len(c.CHECKPOINTS), 12)
        self.assertEqual(set(c.CHECKPOINTS), {(model, seed) for model in c.MODELS for seed in c.SEEDS})
        for (model, seed), item in c.CHECKPOINTS.items():
            self.assertEqual(len(item['sha256']), 64)
            if item['bytes'] is not None:
                self.assertGreater(item['bytes'], 0)
            self.assertEqual(len(item['execution_commit']), 40)
        self.assertEqual(c.CHECKPOINT_CATALOG_SHA256,
                         m.canonical_sha({f'{model}:{seed}': {'sha256': item['sha256'],
                                                              'bytes': item['bytes'],
                                                              'execution_commit': item['execution_commit']}
                                          for (model, seed), item in sorted(c.CHECKPOINTS.items())}))

    def test_eligible_catalogue_from_inventory_only(self):
        with tempfile.TemporaryDirectory() as root:
            scenes = fixture_rows(root)
            pop = m.build_population(scenes, identity(), fixture=True)
            rows = c.build_catalogue(pop, inventory_for(scenes), fixture=True)
            self.assertEqual(len(rows), len(scenes))
            self.assertTrue(all(row['eligible'] for row in rows))
            self.assertEqual(rows[0]['slot_00_relative_path'], scenes[0]['slot_00_relative_path'])
            self.assertEqual(rows[0]['imerg_product'], c.IMERG_PRODUCT)
            self.assertEqual(rows[0]['supervision_region_pixels'], 3430)

    def test_missing_and_unverified_entries_are_rejected(self):
        with tempfile.TemporaryDirectory() as root:
            scenes = fixture_rows(root)
            pop = m.build_population(scenes, identity(), fixture=True)
            rows = c.build_catalogue(pop, inventory_for(scenes, drop_imerg_index=2), fixture=True)
            self.assertEqual(rows[2]['rejection_reason'], 'MISSING_IMERG_DAY')
            self.assertFalse(rows[2]['inventory_complete'])
            rows = c.build_catalogue(pop, inventory_for(scenes, imerg_override={'valid_yunnan_count': 0}),
                                     fixture=True)
            self.assertEqual(rows[0]['rejection_reason'], 'IMERG_NO_YUNNAN_OVERLAP')
            rows = c.build_catalogue(pop, inventory_for(scenes, imerg_override={'run_type': 'Early'}),
                                     fixture=True)
            self.assertEqual(rows[0]['rejection_reason'], 'IMERG_METADATA_MISMATCH')
            rows = c.build_catalogue(pop, inventory_for(scenes, imerg_override={'readable': False}),
                                     fixture=True)
            self.assertEqual(rows[0]['rejection_reason'], 'UNREADABLE_IMERG')

    def test_inventory_rejects_unknown_fields_and_bad_paths(self):
        with self.assertRaises(ValueError):
            c.InventoryIndex([{'modality': 'imerg', 'relative_path': '2025/imerg_20250301.nc',
                               'bytes': 1, 'sha256': sha('x'), 'outcome': 1}])
        with self.assertRaises(ValueError):
            c.InventoryIndex([{'modality': 'imerg', 'relative_path': '../escape.nc',
                               'bytes': 1, 'sha256': sha('x')}])

    def test_unauthorized_paths_raise(self):
        with tempfile.TemporaryDirectory() as root:
            scenes = fixture_rows(root)
            pop = m.build_population(scenes, identity(), fixture=True)
            auth = c.CatalogueAuthorization2025.fixture_only(root)
            with self.assertRaises(PermissionError):
                auth.require_catalogue(allow_fixture=False)
            with self.assertRaises(PermissionError):
                auth.require_qc_payload()
            with self.assertRaises(PermissionError):
                c.build_catalogue_artefacts(auth, pop, inventory_for(scenes), Path(root) / 'out')
            with self.assertRaises(PermissionError):
                c.authorize_payload()

    def test_fixture_bundle_writes_whitelisted_csv_and_freeze(self):
        with tempfile.TemporaryDirectory() as root:
            scenes = fixture_rows(root)
            pop = m.build_population(scenes, identity(), fixture=True)
            auth = c.CatalogueAuthorization2025.fixture_only(Path(root) / 'fixture')
            bundle = c.build_catalogue_artefacts(auth, pop, inventory_for(scenes),
                                                 Path(root) / 'out', fixture=True)
            rows = c.read_csv(bundle['catalogue_path'])
            self.assertEqual(len(rows), len(scenes))
            population = json.loads(Path(bundle['population_path']).read_text(encoding='utf-8'))
            self.assertTrue(m.validate_population(population, require_fixture=True))
            freeze = json.loads(Path(bundle['freeze_path']).read_text(encoding='utf-8'))
            self.assertEqual(freeze['status'], 'CATALOGUE_FROZEN')
            self.assertTrue(freeze['fixture_only'])
            self.assertEqual(freeze['eligible_count'], len(scenes))
            self.assertEqual(bundle['catalogue_sha256'], c.sha256_file(bundle['catalogue_path']))
            self.assertTrue(c.verify_catalogue_bundle_readonly(bundle['catalogue_path'],
                                                               bundle['population_path'],
                                                               bundle['freeze_path']))
            with self.assertRaises(ValueError):
                c.write_csv(Path(root) / 'bad.csv',
                            [dict(row, model_score=1) for row in rows], c.COLUMNS)

    def test_final_authority_ordering_and_bundle_verification(self):
        with tempfile.TemporaryDirectory() as root:
            scenes = fixture_rows(root)
            pop = m.build_population(scenes, dict(c.FROZEN_IDENTITY_2025), fixture=False)
            auth = real_authorization('2026-01-01T00:00:00+00:00')
            bundle = c.build_catalogue_artefacts(auth, pop, inventory_for(scenes),
                                                 Path(root) / 'real-out')
            freeze = json.loads(Path(bundle['freeze_path']).read_text(encoding='utf-8'))
            self.assertFalse(freeze['fixture_only'])
            final = c.FinalAuthority2025({
                'version': 'v1', 'AUTHORIZED_BY': 'RESEARCHER', 'scope': c.FINAL_SCOPE,
                'FINAL_TEST_CATALOGUE_AUTHORIZED': True, 'FINAL_TEST_2025_AUTHORIZED': True,
                'protocol': auth.protocol, 'implementation': auth.implementation,
                'checkpoint_catalog_sha256': c.CHECKPOINT_CATALOG_SHA256,
                'catalogue_sha256': c.sha256_file(bundle['catalogue_path']),
                'population_sha256': c.sha256_file(bundle['population_path']),
                'freeze_record': {'sha256': c.sha256_file(bundle['freeze_path']),
                                  'created_utc': freeze['created_utc'],
                                  'status': 'CATALOGUE_FROZEN'},
                'created_utc': freeze['created_utc'],
            })
            self.assertTrue(final.require_final())
            checked = c.verify_catalogue_bundle(final, catalogue_path=bundle['catalogue_path'],
                                                population_path=bundle['population_path'],
                                                freeze_path=bundle['freeze_path'])
            self.assertEqual(checked['eligible_count'], len(scenes))
            with self.assertRaises(PermissionError):
                final.require_catalogue()
            with self.assertRaises(PermissionError):
                c.FinalAuthority2025({
                    'version': 'v1', 'AUTHORIZED_BY': 'RESEARCHER', 'scope': c.FINAL_SCOPE,
                    'FINAL_TEST_CATALOGUE_AUTHORIZED': True, 'FINAL_TEST_2025_AUTHORIZED': True,
                    'protocol': auth.protocol, 'implementation': auth.implementation,
                    'checkpoint_catalog_sha256': c.CHECKPOINT_CATALOG_SHA256,
                    'catalogue_sha256': c.sha256_file(bundle['catalogue_path']),
                    'population_sha256': c.sha256_file(bundle['population_path']),
                    'freeze_record': {'sha256': c.sha256_file(bundle['freeze_path']),
                                      'created_utc': freeze['created_utc'],
                                      'status': 'CATALOGUE_FROZEN'},
                    'created_utc': '2025-12-31T23:59:59+00:00',
                })

    def test_authorization_requires_exact_keys_and_checkpoint_digest(self):
        good = {'version': 'v1', 'decision_id': 'CATALOGUE_QC_2025_STAT_ONLY',
                'AUTHORIZED_BY': 'RESEARCHER', 'scope': c.CATALOGUE_SCOPE,
                'FINAL_TEST_CATALOGUE_AUTHORIZED': True, 'FINAL_TEST_2025_AUTHORIZED': False,
                'CATALOGUE_QC_PAYLOAD_AUTHORIZED': True,
                'protocol': {'path': c.PROTOCOL_FILENAME, 'sha256': sha('p')},
                'implementation': {'sha256': sha('i'), 'files': {'f': sha('f')}},
                'checkpoint_catalog_sha256': c.CHECKPOINT_CATALOG_SHA256,
                'source_roots': {'himawari': p.HIMAWARI_ROOT, 'imerg': p.IMERG_ROOT,
                                 'gfs': p.GFS_ROOT, 'gfs_thermo': p.GFS_THERMO_ROOT},
                'inventory_measurement': measurement_binding(),
                'identity': dict(c.FROZEN_IDENTITY_2025),
                'created_utc': '2026-01-01T00:00:00+00:00'}
        self.assertTrue(c.CatalogueAuthorization2025(good).require_catalogue())
        with self.assertRaises(ValueError):
            c.CatalogueAuthorization2025(dict(good, extra=1))
        with self.assertRaises(ValueError):
            c.CatalogueAuthorization2025(dict(good, checkpoint_catalog_sha256='0' * 64))
        with self.assertRaises(PermissionError):
            c.CatalogueAuthorization2025(dict(good, FINAL_TEST_2025_AUTHORIZED=True))

    def test_authorization_qc_grant_and_measurement_ordering(self):
        granted = real_authorization('2026-01-02T00:00:00+00:00',
                                     measurement_created_utc='2026-01-01T00:00:00+00:00')
        self.assertTrue(granted.require_qc_payload())
        self.assertEqual(granted.identity, c.FROZEN_IDENTITY_2025)
        self.assertEqual(granted.inventory_measurement['created_utc'],
                         '2026-01-01T00:00:00+00:00')
        with self.assertRaises(PermissionError):
            real_authorization('2026-01-02T00:00:00+00:00',
                               measurement_created_utc='2026-01-03T00:00:00+00:00')
        denied = real_authorization('2026-01-02T00:00:00+00:00')
        with self.assertRaises(ValueError):
            c.CatalogueAuthorization2025(dict(denied.as_dict(),
                                              CATALOGUE_QC_PAYLOAD_AUTHORIZED=False,
                                              identity=identity()))
        false_grant = real_authorization('2026-01-02T00:00:00+00:00')
        raw = false_grant.as_dict()
        raw['CATALOGUE_QC_PAYLOAD_AUTHORIZED'] = False
        with self.assertRaises(PermissionError):
            c.CatalogueAuthorization2025(raw).require_qc_payload()
        tampered = dict(false_grant.as_dict())
        tampered['identity'] = dict(c.FROZEN_IDENTITY_2025, static_sha256='0' * 64)
        with self.assertRaises(ValueError):
            c.CatalogueAuthorization2025(tampered)
        with self.assertRaises(PermissionError):
            c.CatalogueAuthorization2025(dict(false_grant.as_dict(),
                                              inventory_measurement={'path': r'F:\pytorch\Research\x.json',
                                                                     'sha256': '0' * 64,
                                                                     'created_utc': '2026-01-01T00:00:00+00:00'}))

    def test_population_identity_must_match_authorization(self):
        with tempfile.TemporaryDirectory() as root:
            scenes = fixture_rows(root)
            pop = m.build_population(scenes, identity(), fixture=False)
            auth = real_authorization('2026-01-01T00:00:00+00:00')
            with self.assertRaises(ValueError):
                c.build_catalogue_artefacts(auth, pop, inventory_for(scenes), Path(root) / 'out')

    def test_authorization_load_pins_file_digest(self):
        with tempfile.TemporaryDirectory() as root:
            auth = real_authorization('2026-01-02T00:00:00+00:00')
            path = Path(root) / 'authorization.json'
            path.write_text(json.dumps(auth.as_dict(), indent=2), encoding='utf-8')
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            loaded = c.CatalogueAuthorization2025.load(path, expected_sha256=digest)
            self.assertEqual(loaded.identity, auth.identity)
            with self.assertRaises(ValueError):
                c.CatalogueAuthorization2025.load(path, expected_sha256='0' * 64)

    def test_safe_artifact_path_blocks_payload_roots(self):
        for forbidden in (r'H:\葵花202303_202510\202503', r'F:\pytorch\Research\out',
                          r'F:\云南极端降水数据\raw\IMERG\out'):
            with self.assertRaises(PermissionError):
                c.safe_artifact_path(forbidden)


if __name__ == '__main__':
    unittest.main()
