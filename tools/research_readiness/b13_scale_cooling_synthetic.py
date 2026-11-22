"""Test apparent B13 cooling against geometry and cloud replacement using synthetic scenes."""

import itertools
import json

import numpy as np
from scipy.ndimage import map_coordinates


FRAME_SIZE = 17
CENTER = FRAME_SIZE // 2
WINDOW = 3
SHIFTS = range(-2, 3)
SCALES = (0.90, 0.95, 1.00, 1.05, 1.10)
MAX_CENTERED_MSE = 0.25  # K²
NUMERICAL_MARGIN = 0.10  # K over the 10-minute synthetic frame interval
ACTIVATION = 0.75  # K per 10 minutes, inherited from the translation-only screen


def bounds(previous, latest, previous_valid, latest_valid):
    """Return the median contrast envelope over all complete accepted alignments."""
    local = slice(CENTER - WINDOW, CENTER + WINDOW + 1)
    if not latest_valid[local, local].all():
        return None
    target = latest[local, local]
    window_coordinates = np.arange(-WINDOW, WINDOW + 1, dtype=np.float64)
    grid = np.stack(np.meshgrid(window_coordinates, window_coordinates, indexing="ij"))
    accepted = []
    for row_shift, col_shift, scale in itertools.product(SHIFTS, SHIFTS, SCALES):
        points = CENTER + grid * scale + np.array([row_shift, col_shift])[:, None, None]
        covered = map_coordinates(previous_valid.astype(np.float64), points, order=1, mode="constant", cval=0)
        if not np.all(covered >= 1.0 - 1e-12):
            continue
        aligned = map_coordinates(previous, points, order=1, mode="constant", cval=np.nan)
        difference = aligned - target
        centered = difference - difference.mean()
        if np.mean(centered ** 2) <= MAX_CENTERED_MSE:
            accepted.append(float(np.median(difference)))
    if not accepted:
        return None
    return {
        "accepted": len(accepted),
        "lower_with_margin_k": min(accepted) - NUMERICAL_MARGIN,
        "upper_with_margin_k": max(accepted) + NUMERICAL_MARGIN,
    }


def textured_temperature():
    x, y = np.meshgrid(np.arange(FRAME_SIZE) - CENTER, np.arange(FRAME_SIZE) - CENTER)
    return 247.0 + 0.30 * x + 0.16 * y + 0.012 * x * y


def radiance(temperature):
    """Monochromatic Planck radiance with the common factor omitted, at 10.4 µm."""
    return 1.0 / np.expm1(0.014387768775 / (10.4e-6 * temperature))


def brightness_temperature(radiance_value):
    return (0.014387768775 / 10.4e-6) / np.log1p(1.0 / radiance_value)


def sequence_bounds(frames, masks):
    adjacent = [bounds(old, new, old_valid, new_valid) for old, new, old_valid, new_valid
                in zip(frames, frames[1:], masks, masks[1:])]
    if any(result is None for result in adjacent):
        return None
    return {
        "adjacent": adjacent,
        "persistent_lower_k_per_10_min": min(result["lower_with_margin_k"] for result in adjacent),
    }


def experiment():
    texture = textured_temperature()
    valid = np.ones((6, FRAME_SIZE, FRAME_SIZE), dtype=bool)
    indices = np.arange(FRAME_SIZE, dtype=np.float64) - CENTER
    coordinates = np.stack(np.meshgrid(indices, indices, indexing="ij"))
    # Every adjacent frame's actual correspondence is in the candidate grid.
    offset = np.array([1.0, -1.0])[:, None, None]
    geometry = []
    for step in range(6):
        scale = 0.95 ** step
        offset_sum = (1 - scale) / (1 - 0.95)
        geometry.append(map_coordinates(
            texture, CENTER + scale * coordinates + offset * offset_sum,
            order=1, mode="nearest",
        ))
    geometry = np.asarray(geometry)
    moderate = np.stack([texture - 1.5 * step for step in range(6)])
    # Use a stronger cooling control as well so the geometry envelope is crossed.
    # An increasing cold fraction changes BT while both emitting layers stay fixed.
    # The resulting observations match that control by construction.
    cooling = np.stack([texture - 2.0 * step for step in range(6)])
    warm, cold = radiance(texture + 1), radiance(texture - 12)
    fractions = (warm - radiance(cooling)) / (warm - cold)
    assert 0 < fractions.min() <= fractions.max() < 1
    assert (np.diff(fractions, axis=0) > 0).all()
    replacement = brightness_temperature(warm * (1 - fractions) + cold * fractions)
    max_error = float(np.max(np.abs(replacement - cooling)))
    assert max_error < 1e-10

    missing = valid.copy()
    missing[2, CENTER, CENTER] = False
    outcomes = {
        "geometry": sequence_bounds(geometry, valid),
        "genuine_cooling_1_5": sequence_bounds(moderate, valid),
        "genuine_cooling": sequence_bounds(cooling, valid),
        "fixed_temperature_replacement": sequence_bounds(replacement, valid),
        "missing_support": sequence_bounds(cooling, missing),
    }
    assert outcomes["geometry"] is not None
    assert max(pair["lower_with_margin_k"] for pair in outcomes["geometry"]["adjacent"]) <= 0
    assert outcomes["genuine_cooling"]["persistent_lower_k_per_10_min"] > ACTIVATION
    assert outcomes["missing_support"] is None
    negative_activated = outcomes["fixed_temperature_replacement"]["persistent_lower_k_per_10_min"] > ACTIVATION
    return {
        "decision": "STOP_CLOUD_REPLACEMENT_NONIDENTIFIABILITY" if negative_activated else "SYNTHETIC_ONLY",
        "stage_3": "NOT_VERIFIED",
        "controls": outcomes,
        "activation_k_per_10_min": ACTIVATION,
        "max_control_observation_difference_k": max_error,
        "real_source_reads": 0,
        "checkpoint_loads": 0,
        "optimizer_updates": 0,
    }


if __name__ == "__main__":
    print(json.dumps(experiment(), indent=2, allow_nan=False))
