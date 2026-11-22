from collections import Counter
import unittest

import numpy as np

from tools.research_readiness.start_train_mfc700 import matched_scene, outcome


class TrainMFC700Tests(unittest.TestCase):
    def test_invalid_nearest_negative_is_not_replaced(self):
        pixels = np.arange(5)
        altitude = np.array([2100, 2100, 2100, 1500, 2100])
        rates = np.array([25, 20, 0, 0, 0], dtype=np.float32)
        p = np.array([.50, .51, .52, .50, .50])
        q = np.log1p([20, 20, 20, 20, 21])
        values = np.array([[2, 1, 9, 9, 9], [90, 91, 0, 0, 0], [0, 0, 9, 9, 9]])
        valid = np.ones_like(values, dtype=bool)
        scores = matched_scene(pixels, altitude, rates, p, q, values, valid)
        self.assertEqual((scores["low_q32_strong"], scores["matched"], scores["valid_pairs"]), (1, 1, 1))
        self.assertEqual((scores["MFC700_wins"], scores["RH700_wins"], scores["W700_ties"]), (1, 0, 1))
        valid[0, 1] = False
        missing = matched_scene(pixels, altitude, rates, p, q, values, valid)
        self.assertEqual((missing["matched"], missing["valid_pairs"], missing["MFC700_invalid_pairs"]), (1, 0, 1))

    def test_gate_requires_block_coverage_and_strict_control_superiority(self):
        blocks = {block: Counter(valid_pairs=8, MFC700_wins=5, RH700_wins=4, W700_wins=4)
                  for block in range(10)}
        self.assertEqual(outcome(blocks)["decision"], "DESCRIPTIVE_TRAIN_SIGNAL_ONLY")
        for counts in blocks.values():
            counts["RH700_wins"] = 5
        self.assertEqual(outcome(blocks)["decision"], "STOP_MFC_DIRECTION_OR_CONTROL")
        del blocks[0]
        self.assertEqual(outcome(blocks)["decision"], "INSUFFICIENT_COMMON_COVERAGE")


if __name__ == "__main__":
    unittest.main()
