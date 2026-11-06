"""Exact-tie ranking for explicitly described real scores; no calibration API.

The AP/AUROC arithmetic follows phase_a_validation.grouped_occurrence_metrics
and the archived T12 rank_metrics: non-interpolated group-end AP and half-credit
AUROC ties. Unlike that occurrence-probability API, this interface accepts
general real-valued scores, including physical conditional q32 values. It does
not normalize, round, infer P20, choose a threshold, read data or run a model.
"""
import numpy as np


AP_CONVENTION = "NON_INTERPOLATED_END_OF_EXACT_EQUAL_SCORE_GROUP"
AUROC_CONVENTION = "GROUPED_ROC_HALF_CREDIT_EXACT_TIES"


def exact_score_ranking(scores, labels, *, score_semantics):
    """Return finite-population descriptive ranks for caller-supplied arrays.

    Labels must already be explicit bools on the same undivided population.
    Their event definition and the score meaning remain caller declarations.
    No probability or independent-event interpretation is assigned here.

    Real integer/floating dtypes are retained for comparisons; in particular,
    adjacent float64 scores and large distinct int64 scores are never rounded
    into ties. Sorting values ascending avoids integer-negation overflow and
    the full-size ordering-index and cumulative/group arrays. Only groups
    containing positives contribute to AP or the positive-negative AUROC pair
    count. Memory beyond the sorted values scales with positive support, not
    the total number of distinct scores. Floating reduction order can differ
    in the last bits from the former zero-padded full-group calculation.
    """
    if (not isinstance(score_semantics, str) or not score_semantics
            or score_semantics != score_semantics.strip()):
        raise ValueError("Explicit nonempty score_semantics required")
    if np.ma.isMaskedArray(scores) or np.ma.isMaskedArray(labels):
        raise ValueError("Apply the declared population mask explicitly; masked arrays are not accepted")
    try:
        score, truth = np.asarray(scores), np.asarray(labels)
    except (TypeError, ValueError, OverflowError) as error:
        raise ValueError("Explicit aligned real scores and bool labels required") from error
    if (score.ndim != 1 or not score.size or truth.shape != score.shape
            or score.dtype.kind not in "iuf" or truth.dtype != np.bool_
            or not np.isfinite(score).all()):
        raise ValueError("Finite nonempty real 1D scores and aligned bool labels required")
    ordered_score = np.sort(score, kind="stable")
    positive, negative = int(truth.sum()), int((~truth).sum())
    group_count = 1
    # Bounded bool comparisons also count groups containing no positive, while
    # avoiding an N-sized group-boundary index or mask allocation.
    for start in range(1, score.size, 65536):
        stop = min(score.size, start + 65536)
        group_count += int(np.count_nonzero(ordered_score[start:stop]
                                           != ordered_score[start - 1:stop - 1]))
    ap = auc = None
    if positive and negative:
        values, counts = np.unique(score[truth], return_counts=True)
        left = np.searchsorted(ordered_score, values, side="left")
        right = np.searchsorted(ordered_score, values, side="right")
        positive_below = np.cumsum(counts, dtype=np.int64) - counts
        # In descending order, this group's end has P-positive_below true
        # positives among N-left samples. Negative-only groups add exactly 0.
        ap = float(np.sum((counts.astype(np.float64) / positive)
                          * ((positive - positive_below) / (score.size - left)),
                          dtype=np.float64))
        lower_negative = left - positive_below
        tied_negative = right - left - counts
        auc = float(np.sum(counts.astype(np.float64)
                           * (lower_negative + .5 * tied_negative), dtype=np.float64)
                    / (positive * negative))
    elif positive:
        ap = 1.
    return {
        "AP": ap, "AUROC": auc,
        "n": int(score.size), "positive": positive, "negative": negative,
        "exact_score_groups": group_count,
        "score_semantics": score_semantics, "input_score_dtype": str(score.dtype),
        "AP_convention": AP_CONVENTION, "AUROC_convention": AUROC_CONVENTION,
        "undefined": {"AP": "NO_POSITIVE" if not positive else None,
                      "AUROC": "SINGLE_CLASS" if not positive or not negative else None},
        "interpretation": "DESCRIPTIVE_RANKING_NOT_PROBABILITY_CALIBRATION_OR_EVENT_INFERENCE",
    }
