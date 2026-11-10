"""Closed nine-epoch cosine candidate with the historical schedule preserved."""

import math

from yuntapr.training.phase_a_protocol import lr_for_update

ORIGINAL_50 = "ORIGINAL_COSINE50"
COSINE9 = "COSINE9_V1"


def schedule_identity():
    return {
        "profile": COSINE9,
        "horizon_epochs": 9,
        "warmup_epochs": 1,
        "peak_lr": 1e-4,
        "minimum_lr": 1e-6,
        "steps_per_epoch": 480,
        "total_updates": 4320,
        "update_index": "ONE_BASED_LR_SET_BEFORE_OPTIMIZER_STEP",
    }


def scheduled_lr(update, *, steps_per_epoch=480, profile=ORIGINAL_50):
    if profile == ORIGINAL_50:
        return lr_for_update(update, steps_per_epoch=steps_per_epoch)
    if profile != COSINE9 or type(update) is not int or type(steps_per_epoch) is not int:
        raise ValueError("An explicit closed schedule and integer update are required")
    if steps_per_epoch != 480 or not 1 <= update <= 4320:
        raise ValueError("COSINE9_V1 is restricted to the frozen 480-step nine-epoch task")
    if update <= steps_per_epoch:
        return 1e-4 * (update / steps_per_epoch)
    progress = (update - steps_per_epoch) / (4320 - steps_per_epoch)
    return 1e-6 + (1e-4 - 1e-6) * (1 + math.cos(math.pi * progress)) / 2
