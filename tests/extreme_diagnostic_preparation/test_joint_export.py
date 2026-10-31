"""Joint identity, mask, uncertainty, original inputs and failure-boundary tests."""
import importlib.util
import json
import math
from pathlib import Path
import sys
import tempfile
import unittest

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from tools.research_readiness.extreme_diagnostic_export import JointCollector


def points(q, p):
    # Explicit test-only methods, not replacements for the pinned A/B/C.
    return dict(A=p * np.expm1(q).mean(axis=1),
                B=np.zeros(p.size), C=p * np.expm1(q.mean(axis=1)))


class JointExportTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.folder = Path(self.temp.name)
        self.ids = ("2024-05-01T05:30:00+00:00", "2024-05-01T11:30:00+00:00")
        self.analyses = ("2024-05-01T06:00:00+00:00", "2024-05-01T12:00:00+00:00")
        self.y = np.array([[[[20., 21.], [50., 51.]]], [[[0., .1], [1., 4.]]]], dtype=np.float32)
        self.p = np.full_like(self.y, .4)
        self.mask = np.ones_like(self.y, dtype=bool)
        self.q = np.broadcast_to(np.linspace(.2, 2., 32)[None, :, None, None], (2, 32, 2, 2)).copy()
        self.checks = []

    def new(self, name="run", **kwargs):
        return JointCollector(self.folder / name, self.ids, self.analyses,
                              pixels_per_scene=4, point_function=points,
                              check_limits=lambda reserve=0: self.checks.append(reserve), **kwargs)

    def add(self, collector, **kwargs):
        collector.add(self.ids, self.analyses, self.y, self.mask, self.mask, self.p, self.q, **kwargs)

    def test_joint_export_preserves_keys_native_precision_and_inputs(self):
        before = [a.copy() for a in (self.y, self.p, self.q, self.mask)]
        collector = self.new(); self.add(collector); result = collector.finish()
        self.assertEqual((result['scenes'], result['n_valid'], result['n_rain']), (2, 8, 6))
        with np.load(self.folder / 'run/chunk_0000.npz', allow_pickle=False) as data:
            self.assertEqual(data['conditional_quantiles_log'].dtype, np.float64)
            self.assertEqual(data['rate'].dtype, np.float32)
            np.testing.assert_array_equal(data['rate'], self.y.reshape(2, -1))
            np.testing.assert_array_equal(data['scene_id'], self.ids)
        for actual, expected in zip((self.y, self.p, self.q, self.mask), before):
            np.testing.assert_array_equal(actual, expected)
        self.assertGreater(max(self.checks), 0)

    def test_strict_truth_boundary_counts_and_missing_AP(self):
        collector = self.new(); self.add(collector); result = collector.finish()
        self.assertEqual(result['boundary_counts']['20.0']['truth_equal'], 1)
        self.assertEqual(result['boundary_counts']['50.0']['truth_equal'], 1)
        self.assertEqual(result['probability']['20.0']['positive'], 3)
        self.assertEqual(result['probability']['50.0']['positive'], 1)
        self.assertEqual(result['probability']['20.0']['AP'], 'NOT_POINT_IDENTIFIED')
        self.assertEqual(result['independent_events'], 'NOT_IDENTIFIED')

    def test_context_join_copies_only_matching_new_output(self):
        first = self.new('first')
        context = {'elevation_m': np.full((2, 1, 2, 2), 1200., dtype=np.float64),
                   'dynamic_values': np.ones((2, 8, 2, 2), dtype=np.float32),
                   'dynamic_valid': np.ones((2, 8, 2, 2), dtype=bool)}
        self.add(first, context=context); first.finish()
        second = self.new('second', reference_context=self.folder / 'first')
        self.add(second); result = second.finish()
        self.assertEqual(result['groups']['gt20__elevation_1000_2000']['n'], 3)
        self.assertEqual(result['groups']['gt50__O700_windward']['n'], 1)

    def test_context_join_rejects_truth_disagreement(self):
        first = self.new('first'); self.add(first); first.finish()
        second = self.new('second', reference_context=self.folder / 'first')
        self.y[0, 0, 0, 0] = 19
        with self.assertRaises(ValueError): self.add(second)

    def test_partial_run_never_seals(self):
        collector = self.new()
        collector.add(self.ids[:1], self.analyses[:1], self.y[:1], self.mask[:1], self.mask[:1], self.p[:1], self.q[:1])
        with self.assertRaises(PermissionError): collector.finish()
        self.assertTrue((self.folder / 'run/chunk_0000.npz').is_file())
        self.assertFalse((self.folder / 'run/joint_summary.json').exists())

    def test_reordered_scene_or_changed_supervision_rejected(self):
        collector = self.new()
        with self.assertRaises(ValueError):
            collector.add(self.ids[::-1], self.analyses[::-1], self.y, self.mask, self.mask, self.p, self.q)
        collector = self.new('second')
        self.mask[0, 0, 0, 0] = False
        with self.assertRaises(ValueError): self.add(collector)

    def test_original_outputs_cannot_be_overwritten(self):
        collector = self.new(); self.add(collector); collector.finish()
        with self.assertRaises(FileExistsError): self.new()
        with self.assertRaises(PermissionError): self.add(collector)

    def test_year_and_time_alignment_rejected_before_export(self):
        for ids, analyses in [(('2025-05-01T05:30:00+00:00',), ('2025-05-01T06:00:00+00:00',)),
                              (self.ids[:1], ('2024-05-01T07:00:00+00:00',))]:
            with self.subTest(ids=ids), self.assertRaises((PermissionError, ValueError)):
                JointCollector(self.folder / 'bad', ids, analyses, pixels_per_scene=4,
                               point_function=points, check_limits=lambda reserve=0: None)
        self.assertFalse((self.folder / 'bad').exists())

    def test_quota_failure_keeps_prior_chunk_and_no_completion(self):
        collector = self.new()
        def reject(reserve=0):
            if reserve: raise MemoryError('test quota')
        collector.check = reject
        with self.assertRaises(MemoryError): self.add(collector)
        self.assertFalse((self.folder / 'run/joint_summary.json').exists())
        collector.check = lambda reserve=0: None
        with self.assertRaises(PermissionError): self.add(collector)
        with self.assertRaises(PermissionError): collector.finish()


if __name__ == '__main__':
    unittest.main()
