"""Pure Train matching for a proposed fixed RH700 diagnostic."""

from collections import defaultdict
from datetime import datetime, timedelta
import math

import numpy as np


def summarize(scene_ids, pixel_ids, elevation, truth, probability, q32_log, rh700, rh_valid):
    """One-to-one same-scene matching before inspecting RH values or validity."""
    arrays = (scene_ids, pixel_ids, elevation, truth, probability, q32_log, rh700, rh_valid)
    if (truth.ndim != 1 or any(a.shape != truth.shape for a in arrays)
            or scene_ids.dtype.kind != "U" or pixel_ids.dtype.kind not in "iu"
            or truth.dtype != np.float32 or q32_log.dtype != np.float64 or rh_valid.dtype != bool
            or not all(np.isfinite(a).all() for a in (elevation, truth, probability, q32_log))
            or np.any(truth < 0) or np.any((probability < 0) | (probability > 1))
            or len(set(zip(scene_ids, pixel_ids))) != len(truth)):
        raise ValueError("Unique frozen scene/pixel identities and valid predictor arrays required")

    origin = datetime.fromisoformat("2023-01-01T00:00:00+00:00")
    blocks = {}
    for scene in sorted(set(scene_ids)):
        moment = datetime.fromisoformat(scene)
        if moment.year != 2023 or moment.utcoffset() != timedelta(0):
            raise ValueError("Only explicit 2023 UTC target windows are supported")
        blocks[scene] = (moment - origin).days // 14
    strong = truth > np.float32(20.)
    limit = math.log1p(20.)
    low_q32 = q32_log <= limit
    # Values above the limit never enter a match.
    q32 = np.expm1(np.minimum(q32_log, limit))
    altitude = np.searchsorted((1000, 2000), elevation, side="right")
    groups = defaultdict(list)
    for i in np.flatnonzero(low_q32):
        groups[(scene_ids[i], altitude[i])].append(i)
    results = defaultdict(lambda: dict(positive=0, matched=0, valid_pairs=0, wins=0, ties=0))
    for (scene, _), group in groups.items():
        tally = results[blocks[scene]]
        positive = sorted((i for i in group if strong[i]), key=lambda i: pixel_ids[i])
        negative = np.array([i for i in group if not strong[i]], dtype=int)
        unused = np.ones(len(negative), dtype=bool)
        tally["positive"] += len(positive)
        for i in positive:
            dp = np.abs(probability[negative].astype(np.float64) - float(probability[i]))
            dq = np.abs(q32[negative] - q32[i])
            eligible = np.flatnonzero(unused & (dp <= .10) & (dq <= 5.))
            if not len(eligible):
                continue
            # Closest in p, then q32, then the immutable row-major pixel index.
            order = np.lexsort((pixel_ids[negative[eligible]], dq[eligible], dp[eligible]))
            chosen = eligible[order[0]]
            j = negative[chosen]
            unused[chosen] = False
            tally["matched"] += 1
            if rh_valid[i] and rh_valid[j]:
                values = rh700[[i, j]]
                if not np.isfinite(values).all() or np.any(values < 0):
                    raise ValueError("RH700 must be percentage on the shared physical mask")
                tally["valid_pairs"] += 1
                tally["wins"] += int(values[0] > values[1])
                tally["ties"] += int(values[0] == values[1])

    valid = sum(b["valid_pairs"] for b in results.values())
    wins = sum(b["wins"] for b in results.values())
    leave_block_out = {
        block: (wins - b["wins"]) / (valid - b["valid_pairs"])
        for block, b in sorted(results.items()) if 0 < b["valid_pairs"] < valid
    }
    return dict(
        low_q32_strong=int((low_q32 & strong).sum()), valid_pairs=valid,
        strict_win_fraction=wins / valid if valid else None,
        by_block=dict(sorted(results.items())), leave_one_block_out=leave_block_out,
    )
