"""No archive, meteorology or weight reads are used in these fixtures."""

import unittest

import numpy as np

from tools.research_readiness.orographic_separability import summarize


def compute(*rows):
    scene, y, p, q32, elevation, slope, pwat, motion, valid = zip(*rows)
    return summarize(
        np.array(scene), np.array(y, dtype=np.float32), np.array(p), np.log1p(q32),
        np.array(elevation), np.array(slope), np.array(pwat), np.array(motion), np.array(valid),
    )


class OrographicSeparabilityTests(unittest.TestCase):
    def test_pairing_excludes_different_scene_elevation_and_probability(self):
        result = compute(
            ("a", 30, .64, 25, 2000, .1, 30, .3, True),
            ("a", 20, .61, 25, 2900, .1, 30, .2, True),
            ("b", 2, .61, 25, 2100, .3, 50, 1., True),
            ("a", 2, .61, 25, 1999, .3, 50, 1., True),
            ("a", 2, .72, 25, 2100, .3, 50, 1., True),
            ("a", 31, .61, 20, 2100, .3, 50, 1., True),
            ("b", 32, .61, 25, 2100, .3, np.nan, np.nan, False),
        )
        self.assertEqual(result["matched"], dict(strong=1, non_strong=1, scenes=1, comparisons=1))
        self.assertEqual(result["unsupported_strong"], 1)
        self.assertEqual(result["invalid_physics"], dict(strong=1, non_strong=0))
        self.assertEqual(result["unmatched_valid"], dict(strong=0, non_strong=3))
        self.assertEqual(result["positive_weighted_concordance"],
                         dict(windward=1., pwat=.5, slope=.5, reversed_wind=.5))

    def test_difficult_negatives_including_ties_can_falsify_the_feature(self):
        result = compute(
            ("a", 31, .64, 25, 2100, .2, 30, .2, True),
            ("a", 20, .64, 25, 2100, .2, 30, .2, True),
            ("a", .5, .64, 25, 2100, .2, 40, .3, True),
        )
        self.assertEqual(result["matched"]["comparisons"], 2)
        self.assertEqual(result["positive_weighted_concordance"]["windward"], .25)
        self.assertEqual(result["strong_strictly_above_own_group_negative_max"]["windward"], 0)

    def test_reversed_wind_is_a_directional_control(self):
        result = compute(
            ("a", 28, .64, 25, 2100, .2, 30, -.3, True),
            ("a", 20, .64, 25, 2100, .2, 30, .2, True),
        )
        self.assertEqual(result["positive_weighted_concordance"]["windward"], 0.)
        self.assertEqual(result["positive_weighted_concordance"]["reversed_wind"], 1.)

    def test_missing_match_means_unestimated_and_bad_valid_field_fails(self):
        row = ("a", 28, .64, 25, 2100, .2, 30, .3, True)
        result = compute(row)
        self.assertEqual(result["unmatched_valid"]["strong"], 1)
        self.assertIsNone(result["positive_weighted_concordance"]["windward"])
        with self.assertRaises(ValueError):
            compute((*row[:6], np.nan, *row[7:]))


if __name__ == "__main__":
    unittest.main()
