"""Candidate zero-numeric DOTE control; no new architecture or physical definition."""
import numpy as np
from .dynamic_terrain import PhysicalDote


class ZeroNumericDote:
    """Remove only eight numeric channels after the unchanged physical transform.

    All wind/terrain base inputs and the actual per-channel validity indicators
    remain. This tests explicit numeric feature utility conditional on masks;
    it neither removes every DOTE-related signal nor matches effective capacity.
    In the width16 terrain projection, the eight zero columns give 128 weights
    identically zero loss gradients (AdamW decay may still move their values).
    """
    def __init__(self, pack, definition):
        self.physical = PhysicalDote(pack, definition)

    def __call__(self, frame):
        values, valid = self.physical(frame)
        if values.shape != (8, 100, 100) or valid.shape != values.shape or valid.dtype != np.bool_:
            raise ValueError('Frozen eight-channel target grid and masks required')
        return np.zeros_like(values), valid.copy()
