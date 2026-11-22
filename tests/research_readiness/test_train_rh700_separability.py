import unittest

import numpy as np

from tools.research_readiness.train_rh700_separability import summarize


A = "2023-03-01T05:30:00Z"
B = "2023-03-25T05:30:00Z"


def calculate(rows):
    scenes, index, altitude, truth, prob, q32, rh, mask = zip(*rows)
    return summarize(np.array(scenes), np.array(index), np.array(altitude),
                     np.array(truth, dtype=np.float32), np.array(prob), np.log1p(q32),
                     np.array(rh), np.array(mask))


class TrainRH700Tests(unittest.TestCase):
    def test_fixed_tie_breaking_and_no_negative_reuse_or_other_population(self):
        rows = [
            (A, 2, 2200, 25, .65, 18, 80, True),
            (A, 3, 2200, 30, .65, 18, 90, True),
            (A, 4, 2200, 20, .65, 18, 50, True),
            (A, 5, 2200, 1, .66, 18, 90, True),
            (A, 6, 200, 2, .65, 18, 35, True),
            (A, 7, 2200, 2, .65, 21, 35, True),
            (B, 4, 2200, 2, .65, 18, 35, True),
        ]
        result = calculate(rows)
        self.assertEqual(result, calculate(rows[::-1]))
        self.assertEqual(result["valid_pairs"], 2)
        self.assertEqual(result["strict_win_fraction"], .5)

    def test_no_replacement_after_invalid_rh_and_utc_block_sensitivity(self):
        rows = [
            (A, 1, 2000, 30, .65, 20, 90, True),
            (A, 2, 2000, 10, .65, 20, np.nan, False),
            (A, 3, 2000, 2, .66, 20, 40, True),
            (B, 1, 2000, 25, .65, 19, 70, True),
            (B, 2, 2000, 2, .65, 19, 70, True),
        ]
        result = calculate(rows)
        self.assertEqual(result["valid_pairs"], 1)
        self.assertEqual(result["strict_win_fraction"], 0)
        self.assertEqual([v["matched"] for v in result["by_block"].values()], [1, 1])
        rows[1] = (A, 2, 2000, 10, .65, 20, 40, True)
        self.assertEqual(sorted(calculate(rows)["leave_one_block_out"].values()), [0., 1.])

    def test_rejects_other_year_and_duplicate_pixel(self):
        row = (A, 1, 2000, 30, .65, 20, 90, True)
        with self.assertRaises(ValueError):
            calculate([row, row])
        with self.assertRaises(ValueError):
            calculate([("2025-03-01T05:30:00Z", *row[1:])])


if __name__ == "__main__":
    unittest.main()
