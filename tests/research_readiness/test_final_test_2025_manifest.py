"""2025 population manifest tests: identity binding, fixture tagging, digests."""
import copy
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from yuntapr.experimental.research_readiness import final_test_2025_manifest as m
from yuntapr.experimental.research_readiness import final_test_2025_planning as p


def fake_identity():
    return {key: hashlib.sha256(key.encode()).hexdigest() for key in m.IDENTITY_FIELDS}


def fixture_population(count=12):
    with tempfile.TemporaryDirectory() as root:
        layout = p.synthetic_layout(root)
        rows = p.enumerate_scenes(layout, analysis_start='2025-03-01T00:00:00+00:00',
                                  analysis_end='2025-03-04T00:00:00+00:00')
    self_expected = count
    if len(rows) != self_expected:
        raise AssertionError('fixture slice drifted')
    return m.build_population([row.as_dict() for row in rows], fake_identity(),
                              expected_count=self_expected, fixture=True)


class Manifest2025Tests(unittest.TestCase):
    def test_fixture_population_and_digests(self):
        pop = fixture_population()
        self.assertEqual(pop.document['status'], m.STATUS_FIXTURE)
        self.assertTrue(pop.document['fixture_only'])
        self.assertEqual(pop.document['scene_count'], 12)
        self.assertEqual(pop.document['supervision_region_pixels'], 3430)
        self.assertEqual(len(pop.csv_rows()), 12)
        self.assertEqual(tuple(pop.csv_rows()[0]), m.POPULATION_COLUMNS)
        self.assertTrue(m.validate_population(pop.document))
        self.assertEqual(pop.population_sha256, pop.document['population_sha256'])

    def test_tampering_is_rejected(self):
        pop = fixture_population()
        tampered = copy.deepcopy(pop.document)
        tampered['scene_records'][3]['slot_01_relative_path'] = tampered['scene_records'][3]['slot_02_relative_path']
        with self.assertRaises(ValueError):
            m.validate_population(tampered)
        tampered = copy.deepcopy(pop.document)
        tampered['identity']['static_sha256'] = '0' * 64
        with self.assertRaises(ValueError):
            m.validate_population(tampered)
        tampered = copy.deepcopy(pop.document)
        tampered['supervision_region_pixels'] = 0
        with self.assertRaises(ValueError):
            m.validate_population(tampered)
        with self.assertRaises(ValueError):
            m.validate_population(pop.document, require_fixture=False)

    def test_identity_shape_guard(self):
        pop = fixture_population()
        bad = copy.deepcopy(pop.document)
        bad['identity'] = {'sp04_grid_sha256': 'x'}
        with self.assertRaises(ValueError):
            m.validate_identity(bad['identity'])
        rows = [row.as_dict() for row in p.enumerate_scenes(
            analysis_start='2025-03-01T00:00:00+00:00', analysis_end='2025-03-01T06:00:00+00:00')]
        with self.assertRaises(ValueError):
            m.build_population(rows, {'sp04_grid_sha256': '0' * 64, 'supervision_mask_sha256': '1' * 64,
                                      'static_sha256': '2' * 64}, fixture=True)
        with self.assertRaises(ValueError):
            m.build_population(rows, fake_identity(), fixture=True, supervision_region_pixels=0)

    def test_duplicate_and_order_guards(self):
        with tempfile.TemporaryDirectory() as root:
            rows = [row.as_dict() for row in p.enumerate_scenes(
                p.synthetic_layout(root), analysis_start='2025-03-01T00:00:00+00:00',
                analysis_end='2025-03-01T12:00:00+00:00')]
        with self.assertRaises(ValueError):
            m.build_population([rows[0], rows[0]], fake_identity(), fixture=True)
        with self.assertRaises(ValueError):
            m.build_population([rows[1], rows[0]], fake_identity(), fixture=True)

    def test_append_only_write_and_read(self):
        pop = fixture_population()
        with tempfile.TemporaryDirectory() as root:
            path = Path(root) / 'population.json'
            digest = m.write_population(path, pop.document)
            self.assertEqual(digest, m.sha256_file(path))
            with self.assertRaises(FileExistsError):
                m.write_population(path, pop.document)
            self.assertEqual(m.read_population(path)['population_sha256'],
                             pop.document['population_sha256'])

    def test_frozen_identity_evidence_values(self):
        evidence = m.FROZEN_IDENTITY_EVIDENCE_2023_2024
        self.assertIsNone(evidence['sp04_grid_sha256'])
        for key in ('supervision_mask_sha256', 'static_sha256', 'train_scalers_sha256'):
            self.assertEqual(len(evidence[key]), 64)
        self.assertEqual(m.IDENTITY_FIELDS, tuple(m.FROZEN_IDENTITY_EVIDENCE_2023_2024))


if __name__ == '__main__':
    unittest.main()
