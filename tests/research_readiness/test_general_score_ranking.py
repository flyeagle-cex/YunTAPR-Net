"""Hand-verifiable artificial rankings only; no model or project data."""
import unittest

import numpy as np

from yuntapr.experimental.research_readiness.general_score_ranking import exact_score_ranking


def rank(scores, labels, semantics="ARTIFICIAL_CONDITIONAL_Q32_MM_H"):
    return exact_score_ranking(scores, labels, score_semantics=semantics)


class GeneralScoreRankingTests(unittest.TestCase):
    def test_scores_above_one_and_negative_scores_are_not_probabilities(self):
        result = rank([30., -4., 20., 0.], [True, False, True, False])
        self.assertEqual(result["AP"], 1.)
        self.assertEqual(result["AUROC"], 1.)
        self.assertIn("NOT_PROBABILITY", result["interpretation"])

    def test_exact_group_end_ap_and_half_credit_auc_have_hand_values(self):
        # Descending groups: (1P,1N), (1P), (1N).
        # AP=(1/2)*(1/2)+(1/2)*(2/3)=7/12; AUC=(1.5+1)/4=5/8.
        result = rank([2., 2., 1., 0.], [True, False, True, False])
        self.assertAlmostEqual(result["AP"], 7 / 12)
        self.assertEqual(result["AUROC"], 5 / 8)
        self.assertEqual(result["exact_score_groups"], 3)

    def test_all_tied_scores_return_prevalence_and_half_auc(self):
        result = rank([8., 8., 8., 8.], [True, False, False, False])
        self.assertEqual(result["AP"], .25)
        self.assertEqual(result["AUROC"], .5)
        self.assertEqual(result["exact_score_groups"], 1)

    def test_adjacent_float64_values_are_not_rounded_or_normalized(self):
        lower = np.float64(1000.)
        higher = np.nextafter(lower, np.float64(np.inf))
        result = rank(np.array([lower, higher]), [False, True])
        self.assertEqual(result["exact_score_groups"], 2)
        self.assertEqual(result["AP"], 1.)
        self.assertEqual(result["AUROC"], 1.)

    def test_integer_scores_do_not_overflow_on_descending_sort_or_merge(self):
        maximum = np.iinfo(np.int64).max
        values = np.array([np.iinfo(np.int64).min, maximum - 1, maximum], dtype=np.int64)
        result = rank(values, [False, False, True])
        self.assertEqual(result["AP"], 1.)
        self.assertEqual(result["AUROC"], 1.)
        self.assertEqual(result["exact_score_groups"], 3)

    def test_permuting_exact_ties_cannot_change_grouped_metrics(self):
        a = rank([5., 5., 5., 1.], [True, False, True, False])
        b = rank([5., 5., 5., 1.], [False, True, True, False])
        self.assertEqual((a["AP"], a["AUROC"]), (b["AP"], b["AUROC"]))

    def test_negative_only_groups_still_count_in_precision_denominators(self):
        result = rank([9., 8., 7., 6., 5., 4., 3.],
                      [False, False, True, False, False, True, False])
        self.assertAlmostEqual(result["AP"], 1 / 3)
        self.assertEqual(result["AUROC"], .4)
        self.assertEqual(result["exact_score_groups"], 7)

    def test_unequal_mixed_ties_have_independent_hand_values(self):
        result = rank([9., 9., 8., 8., 8., 7., 6., 6.],
                      [False, True, False, True, True, False, True, False])
        # AP=1/4*1/2+2/4*3/5+1/4*4/8=.55; pair wins=9 of16.
        self.assertAlmostEqual(result["AP"], .55)
        self.assertEqual(result["AUROC"], 9 / 16)

    def test_small_random_ties_match_full_group_ap_and_pairwise_auc(self):
        rng = np.random.default_rng(812)
        for _ in range(12):
            scores = rng.integers(-4, 5, 19)
            labels = rng.integers(0, 2, 19).astype(bool)
            if labels.all() or not labels.any():
                continue
            # Independent original full-group AP calculation. AUROC uses
            # explicit positive-negative pairs rather than cumulative groups.
            order = np.argsort(-scores, kind="stable")
            sorted_score, sorted_label = scores[order], labels[order]
            ends = np.r_[np.flatnonzero(sorted_score[:-1] != sorted_score[1:]), len(scores) - 1]
            tp = np.cumsum(sorted_label)[ends]
            ap = np.sum(np.diff(np.r_[0, tp]) / labels.sum() * tp / (ends + 1))
            auc = sum(float(p > n) + .5 * float(p == n)
                      for p in scores[labels] for n in scores[~labels]) / (labels.sum() * (~labels).sum())
            result = rank(scores, labels)
            self.assertAlmostEqual(result["AP"], ap, places=14)
            self.assertEqual(result["AUROC"], auc)

    def test_single_class_has_explicit_undefined_fields(self):
        none_positive = rank([2., 1.], [False, False])
        self.assertIsNone(none_positive["AP"])
        self.assertIsNone(none_positive["AUROC"])
        self.assertEqual(none_positive["undefined"]["AP"], "NO_POSITIVE")
        all_positive = rank([2., 1.], [True, True])
        self.assertEqual(all_positive["AP"], 1.)
        self.assertIsNone(all_positive["AUROC"])
        self.assertEqual(all_positive["undefined"]["AUROC"], "SINGLE_CLASS")

    def test_labels_must_be_explicit_bool_and_population_cannot_be_empty(self):
        for scores, labels in (([2., 1.], [1, 0]), ([2., 1.], [1., 0.]),
                               ([], np.array([], dtype=bool)), ([2., 1.], [True]),
                               ([[2., 1.]], [[True, False]]),
                               (np.ma.array([2., 1.], mask=[False, True]), [True, False]),
                               ([2., 1.], np.ma.array([True, False], mask=[False, True]))):
            with self.subTest(scores=scores, labels=labels), self.assertRaises(ValueError):
                rank(scores, labels)

    def test_nonfinite_nonreal_or_boolean_scores_are_rejected(self):
        for scores in ([1., np.nan], [np.inf, 1.], [1., -np.inf],
                       [1 + 1j, 2.], ["1", "2"], [True, False]):
            with self.subTest(scores=scores), self.assertRaises(ValueError):
                rank(scores, [True, False])

    def test_semantics_are_mandatory_and_preserved(self):
        with self.assertRaises(TypeError):
            exact_score_ranking([2., 1.], [True, False])
        for semantics in (None, "", " ", " ambiguous "):
            with self.subTest(semantics=semantics), self.assertRaises(ValueError):
                rank([2., 1.], [True, False], semantics)
        self.assertEqual(rank([2., 1.], [True, False], "DECLARED_TEST_SCORE")["score_semantics"],
                         "DECLARED_TEST_SCORE")


if __name__ == "__main__":
    unittest.main()
