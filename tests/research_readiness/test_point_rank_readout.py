"""Focused CPU checks for a saved-control, fixed-E9 point rank readout."""

import hashlib
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest

import numpy as np

from tools.research_readiness.point_rank_readout import PairedPointRankReadout, paired_batch, point_a, rank_scores


class PointRankTests(unittest.TestCase):
    def test_exact_ap_and_half_credit_auc_with_ties(self):
        scores = np.array([.5, .5, .9, .2], dtype=np.float32)
        strong = np.array([True, False, True, False])
        result = rank_scores(scores, strong)
        self.assertAlmostEqual(result["ap20"], 5 / 6)
        self.assertAlmostEqual(result["auroc20"], 7 / 8)
        self.assertEqual(result["score_overlap"]["strong_strictly_above_non_strong_max"], 1)
        self.assertEqual(result["score_overlap"]["strong_tied_with_non_strong_max"], 1)
        self.assertEqual(result, rank_scores(scores[::-1], strong[::-1]))

    def test_empty_class_has_no_rank_conclusion(self):
        result = rank_scores(np.array([20, 21], dtype=np.float32), np.array([True, True]))
        self.assertIsNone(result["ap20"])
        self.assertIsNone(result["auroc20"])

    def test_pair_rejects_order_mask_and_truth_mismatch(self):
        ids = ("2024-test-a",)
        mask = np.array([[[True, False]]])
        truth = np.array([20.0], dtype=np.float32)
        saved = dict(scene_ids=np.array(ids), supervision_mask=mask, truth_mm_h=truth,
                     p=np.array([.5], dtype=np.float32), qlog=np.full((1, 32), np.log1p(40.)))
        with self.assertRaisesRegex(ValueError, "order"):
            paired_batch(saved, ("2024-test-b",), mask, truth)
        with self.assertRaisesRegex(ValueError, "mask"):
            paired_batch(saved, ids, ~mask, truth)
        with self.assertRaisesRegex(ValueError, "truth"):
            paired_batch(saved, ids, mask, np.nextafter(truth, np.float32(np.inf)))
        bad_scores = dict(saved, p=np.array([], dtype=np.float32), qlog=np.empty((0, 32)))
        with self.assertRaisesRegex(ValueError, "shape"):
            paired_batch(bad_scores, ids, mask, truth)
        rank = point_a(saved["p"], saved["qlog"])
        self.assertEqual(rank.dtype, np.float32)
        self.assertEqual(float(rank[0]), 20.0)
        self.assertFalse(bool(rank[0] > np.float32(20)))

    def test_single_batch_retains_only_candidate_scores_and_requires_counts(self):
        with TemporaryDirectory(prefix="point-rank-synthetic-") as tmp:
            root = Path(tmp)
            control = root / "batch_000.npz"
            ids = ("2024-test-a",)
            rate = np.array([[[[25, 20, 30, 4]]]], dtype=np.float32)
            mask = np.ones((1, 1, 1, 4), dtype=bool)
            pack = SimpleNamespace(grid=SimpleNamespace(identity="SYNTHETIC"),
                                   values=np.array([[[2000, 2500, 1000, 1900]]]),
                                   valid=np.ones((1, 1, 4), dtype=bool), region=mask[0, 0])
            probability = np.full_like(rate, .5, dtype=np.float64)
            qlog = np.broadcast_to(np.log1p(np.array([[[[42., 40., 26., 18.]]]])), (1, 32, 1, 4))
            np.savez(control, scene_ids=np.array(ids), supervision_mask=mask[:, 0], truth_mm_h=rate.ravel(),
                     p=np.full(4, .5, dtype=np.float32), qlog=np.full((4, 32), np.log1p(35.)))
            manifest = [dict(file=control.name, bytes=control.stat().st_size,
                             sha256=hashlib.sha256(control.read_bytes()).hexdigest(),
                             scene_start=0, scenes=1, n_valid=4)]
            contract = dict(scenes=1,n_valid=4,n_strong=2,high_n_strong=1,
                            saved_control_bytes=control.stat().st_size, supervision_mask_sha256="MASK",
                            fixed_a_counts={"COSINE9": {"tp":0,"fp":0}, "A20": {"tp":1,"fp":0}})
            reader = PairedPointRankReadout(root / "candidate", root, manifest, pack, ids, contract, lambda reserve=0: None)
            reader.add(ids, rate, mask, mask, probability, qlog)
            result = reader.finish("MASK")
            self.assertTrue(result["a20_ap20_improved"])
            self.assertEqual(result["metrics"]["A20"]["elevation_ge_2000m"]["n_strong"], 1)
            self.assertEqual([p.name for p in (root / "candidate").iterdir()], ["batch_000.npy"])
            np.testing.assert_array_equal(np.load(root / "candidate" / "batch_000.npy"), [21, 20, 13, 9])
            contract["fixed_a_counts"]["A20"]["fp"] = 1
            with self.assertRaisesRegex(ValueError,"fixed A"):
                reader.finish("MASK")


if __name__ == "__main__":
    unittest.main()
