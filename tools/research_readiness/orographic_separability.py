"""In-memory diagnostic for the frozen q32-supported strong and hard-negative population."""

from collections import defaultdict
import math

import numpy as np


FEATURES = ("windward", "pwat", "slope", "reversed_wind")
PROBABILITY_EDGES = np.arange(1, 10, dtype=np.float64) / 10
ELEVATION_EDGES_M = (1000, 2000)


def summarize(scene_ids, truth_mm_h, probability, q32_log, elevation_m, slope, pwat,
              upslope700_m_s, physical_valid):
    """Compare one fixed physical feature and three controls on identical pairs.

    One row is one supervised pixel-time. Physical validity already intersects
    the frozen 700 hPa above-ground, terrain and PWAT masks. No source I/O.
    """
    arrays = (scene_ids, truth_mm_h, probability, q32_log, elevation_m, slope, pwat,
              upslope700_m_s, physical_valid)
    if (truth_mm_h.ndim != 1 or any(value.shape != truth_mm_h.shape for value in arrays)
            or scene_ids.dtype.kind != "U" or np.any(scene_ids == "")
            or physical_valid.dtype != bool or truth_mm_h.dtype != np.float32
            or q32_log.dtype != np.float64
            or not all(np.isfinite(value).all() for value in (truth_mm_h, probability, q32_log))
            or np.any(truth_mm_h < 0) or np.any((probability < 0) | (probability > 1))):
        raise ValueError("Aligned supervised pixel-time arrays and fixed truth/quantile formats required")

    support = q32_log > math.log1p(20.)
    strong = truth_mm_h > np.float32(20.)
    selected = np.flatnonzero(support & physical_valid)
    elevation, steepness, water, motion = (value[selected] for value in
                                             (elevation_m, slope, pwat, upslope700_m_s))
    if (not all(np.isfinite(value).all() for value in (elevation, steepness, water, motion))
            or np.any(steepness < 0) or np.any(water < 0)):
        raise ValueError("Finite physical features and nonnegative slope/PWAT required on the valid mask")
    with np.errstate(over="raise", invalid="raise"):
        scores = np.column_stack((water * np.maximum(motion, 0), water, steepness,
                                  water * np.maximum(-motion, 0)))

    altitude_bins = np.searchsorted(ELEVATION_EDGES_M, elevation, side="right")
    probability_bins = np.searchsorted(PROBABILITY_EDGES, probability[selected], side="right")
    groups = defaultdict(list)
    for index, key in enumerate(zip(scene_ids[selected], altitude_bins, probability_bins)):
        groups[key].append(index)

    selected_strong = strong[selected]
    concordance = []
    left_out_negative = matched_negative = comparisons = 0
    matched_scenes = set()
    above_all = np.zeros(len(FEATURES), dtype=int)
    for key, members in groups.items():
        is_positive = selected_strong[members]
        positive = scores[members][is_positive]
        negative = scores[members][~is_positive]
        if not len(positive) or not len(negative):
            left_out_negative += len(negative)
            continue
        matched_scenes.add(key[0])
        matched_negative += len(negative)
        comparisons += len(positive) * len(negative)
        for row in positive:
            concordance.append(((row > negative) + .5 * (row == negative)).mean(axis=0))
        above_all += (positive > negative.max(axis=0)).sum(axis=0)

    n_strong = int((support & strong).sum())
    n_negative = int((support & ~strong).sum())
    invalid_strong = int((support & strong & ~physical_valid).sum())
    invalid_negative = int((support & ~strong & ~physical_valid).sum())
    mean = np.mean(concordance, axis=0) if concordance else [None] * len(FEATURES)
    return dict(
        supported_strong=n_strong, supported_non_strong=n_negative,
        unsupported_strong=int((~support & strong).sum()),
        invalid_physics=dict(strong=invalid_strong, non_strong=invalid_negative),
        unmatched_valid=dict(strong=n_strong - invalid_strong - len(concordance),
                             non_strong=left_out_negative),
        matched=dict(strong=len(concordance), non_strong=matched_negative,
                     scenes=len(matched_scenes), comparisons=comparisons),
        positive_weighted_concordance={key: None if value is None else float(value)
                                      for key, value in zip(FEATURES, mean)},
        strong_strictly_above_own_group_negative_max=dict(zip(FEATURES, map(int, above_all))),
    )
