"""Bounded descriptive candidate manifest for the frozen 2023 Train readout.

The collector is deliberately torch-free.  It consumes one scene at a time,
keeps only supervised pixels whose fixed FP64 q32 readout crosses the
candidate rule ``p * expm1(qlog32) > 20``, and records the weak-preserving
minimal-crossing witness for each retained pixel.  Nothing here fits a
coefficient, changes a prediction, or grants scientific status.
"""

from pathlib import Path
from typing import NamedTuple

import numpy as np

from tools.research_readiness.a20_fixed_endpoint_bounds import (
    THRESHOLD,
    pinball,
    point,
    strict_hit,
    weak_preserving_vertex,
)


MAX_CANDIDATE_ROWS = 20000
NODES = 32
FIELD_SHAPE = (100, 100)
SUPERVISION_PIXELS_PER_SCENE = 3430
CANDIDATE_THRESHOLD = 20.0
OUTPUT_NAME = "stage45_candidate_manifest.npz"


class CandidateRow(NamedTuple):
    """One bounded descriptor row; ``row`` is the scene-local supervised index."""

    scene_id: str
    row: int
    y: int
    x: int
    truth: float
    p: float
    q32: float
    nodes_log: np.ndarray
    mean_intensity: float
    a0: float
    reachable: bool
    already_crossed: bool
    a_after: float
    delta: float
    strong: bool
    all_nodes_below_truth: bool


def _scene_arrays(p, qlog, truth, valid, region):
    p = np.asarray(p)
    qlog = np.asarray(qlog)
    truth = np.asarray(truth)
    valid = np.asarray(valid)
    region = np.asarray(region)
    if (p.shape != FIELD_SHAPE or truth.shape != FIELD_SHAPE
            or valid.shape != FIELD_SHAPE or region.shape != FIELD_SHAPE
            or qlog.shape != (NODES,) + FIELD_SHAPE):
        raise ValueError("Expected one 100x100 scene and 32 ordered qlog nodes")
    if (truth.dtype != np.float32 or valid.dtype != np.bool_ or region.dtype != np.bool_
            or not np.issubdtype(p.dtype, np.floating)
            or not np.issubdtype(qlog.dtype, np.floating)):
        raise ValueError("Expected float32 truth, floating readouts and boolean masks")
    mask = valid & region
    if int(np.count_nonzero(mask)) != SUPERVISION_PIXELS_PER_SCENE:
        raise ValueError("Frozen per-scene supervision must contain exactly 3430 pixels")
    p_rows = np.asarray(p[mask], dtype=np.float64)
    truth_rows = np.asarray(truth[mask], dtype=np.float64)
    q_rows = np.asarray(qlog[:, mask].T, dtype=np.float64)
    if (not np.isfinite(p_rows).all() or not np.isfinite(truth_rows).all()
            or not np.isfinite(q_rows).all()):
        raise ValueError("Non-finite supervised readout")
    if (np.any((p_rows < 0.0) | (p_rows > 1.0)) or np.any(truth_rows < 0.0)
            or np.any(q_rows < 0.0) or np.any(q_rows[:, 1:] <= q_rows[:, :-1])):
        raise ValueError("Expected probability in [0,1], nonnegative truth and strictly ordered qlog")
    return p_rows, truth_rows, q_rows


class CandidateManifest:
    """Collect bounded per-pixel crossing descriptors; never mutate predictions."""

    def __init__(self, max_rows=MAX_CANDIDATE_ROWS):
        if isinstance(max_rows, bool) or not isinstance(max_rows, int) or max_rows < 1:
            raise ValueError("max_rows must be a positive integer")
        self.max_rows = max_rows
        self.rows = []
        self.scenes = set()
        self.pixels = 0
        self.strong = 0

    def update(self, p, qlog, truth, valid, region, scene_id):
        """Consume one frozen scene and retain every strict candidate pixel."""
        if not isinstance(scene_id, str) or not scene_id.startswith("2023-"):
            raise ValueError("Only 2023 Train scenes are admissible")
        if scene_id in self.scenes:
            raise ValueError("Duplicate scene in the candidate manifest")
        p_rows, truth_rows, q_rows = _scene_arrays(p, qlog, truth, valid, region)

        with np.errstate(over="raise", invalid="raise"):
            physical = np.expm1(q_rows)
        q32 = physical[:, -1]
        candidate = p_rows * q32 > CANDIDATE_THRESHOLD
        indices = np.flatnonzero(candidate)
        if len(self.rows) + len(indices) > self.max_rows:
            raise ValueError(
                f"Candidate row cap {self.max_rows} exceeded: "
                f"{len(self.rows)} retained plus {len(indices)} new"
            )

        mean_intensity = physical.mean(axis=1)
        # The candidate rule and A0 use the same frozen FP64/FP32 readouts.
        a0 = np.float32(p_rows * mean_intensity).astype(np.float64)
        strong = truth_rows > CANDIDATE_THRESHOLD

        # All validation and the cap guard precede the first state mutation.
        self.scenes.add(scene_id)
        self.pixels += len(p_rows)
        self.strong += int(np.count_nonzero(strong))
        grid_y, grid_x = np.nonzero(valid & region)

        for index in indices:
            row = int(index)
            nodes_log = q_rows[row].copy()
            nodes = physical[row]
            probability = float(p_rows[row])
            truth_rate = float(truth_rows[row])
            a0_value = float(a0[row])
            is_strong = bool(strong[row])
            all_nodes_below_truth = bool(np.all(nodes < truth_rate))
            if a0_value > float(THRESHOLD):
                reachable, already_crossed = True, True
                a_after, delta = a0_value, 0.0
            else:
                already_crossed = False
                try:
                    vertex = weak_preserving_vertex(nodes_log)
                except ArithmeticError:
                    reachable, a_after, delta = False, float("nan"), float("nan")
                else:
                    ceiling = point(probability, vertex)
                    try:
                        matched = strict_hit(probability, nodes_log, vertex)
                    except ArithmeticError:
                        matched = None
                    if matched is None:
                        reachable, a_after, delta = False, ceiling, float("nan")
                    else:
                        reachable = True
                        a_after = point(probability, matched)
                        with np.errstate(over="raise", invalid="raise"):
                            delta = float(
                                pinball((truth_rate - np.expm1(matched)) / 20.0)
                                - pinball((truth_rate - nodes) / 20.0)
                            )
            self.rows.append(CandidateRow(
                scene_id=scene_id,
                row=row,
                y=int(grid_y[row]),
                x=int(grid_x[row]),
                truth=truth_rate,
                p=probability,
                q32=float(q32[row]),
                nodes_log=nodes_log,
                mean_intensity=float(mean_intensity[row]),
                a0=a0_value,
                reachable=reachable,
                already_crossed=already_crossed,
                a_after=a_after,
                delta=delta,
                strong=is_strong,
                all_nodes_below_truth=all_nodes_below_truth,
            ))

    def _arrays(self):
        rows = self.rows
        if not rows:
            empty = np.empty((0,), dtype=np.float64)
            return dict(
                scene_id=np.empty((0,), dtype="U32"), row=np.empty((0,), dtype=np.int32),
                y=np.empty((0,), dtype=np.int32), x=np.empty((0,), dtype=np.int32),
                truth=np.empty((0,), dtype=np.float32), p=empty.copy(), q32=empty.copy(),
                nodes_log=np.empty((0, NODES), dtype=np.float64),
                mean_intensity=empty.copy(), a0=np.empty((0,), dtype=np.float32),
                reachable=np.empty((0,), dtype=np.bool_), already_crossed=np.empty((0,), dtype=np.bool_),
                a_after=empty.copy(), delta=empty.copy(),
                strong=np.empty((0,), dtype=np.bool_), all_nodes_below_truth=np.empty((0,), dtype=np.bool_),
            )
        return dict(
            scene_id=np.asarray([row.scene_id for row in rows], dtype="U32"),
            row=np.asarray([row.row for row in rows], dtype=np.int32),
            y=np.asarray([row.y for row in rows], dtype=np.int32),
            x=np.asarray([row.x for row in rows], dtype=np.int32),
            truth=np.asarray([row.truth for row in rows], dtype=np.float32),
            p=np.asarray([row.p for row in rows], dtype=np.float64),
            q32=np.asarray([row.q32 for row in rows], dtype=np.float64),
            nodes_log=np.stack([row.nodes_log for row in rows]).astype(np.float64, copy=False),
            mean_intensity=np.asarray([row.mean_intensity for row in rows], dtype=np.float64),
            a0=np.asarray([row.a0 for row in rows], dtype=np.float32),
            reachable=np.asarray([row.reachable for row in rows], dtype=np.bool_),
            already_crossed=np.asarray([row.already_crossed for row in rows], dtype=np.bool_),
            a_after=np.asarray([row.a_after for row in rows], dtype=np.float64),
            delta=np.asarray([row.delta for row in rows], dtype=np.float64),
            strong=np.asarray([row.strong for row in rows], dtype=np.bool_),
            all_nodes_below_truth=np.asarray(
                [row.all_nodes_below_truth for row in rows], dtype=np.bool_),
        )

    def finish(self, output):
        """Write the bounded row table and return descriptive aggregate counts."""
        if len(self.rows) > self.max_rows:
            raise ValueError(f"Candidate row cap {self.max_rows} exceeded")
        output = Path(output)
        with (output / OUTPUT_NAME).open("xb") as stream:
            np.savez(stream, **self._arrays())
        rows = self.rows
        reachable = [row for row in rows if row.reachable]
        finite_delta = np.asarray(
            [row.delta for row in rows if row.reachable and np.isfinite(row.delta)],
            dtype=np.float64,
        )
        counts = dict(
            evaluated_scenes=len(self.scenes),
            evaluated_supervised_pixels=self.pixels,
            evaluated_strong_pixels=self.strong,
            candidate_scenes=len({row.scene_id for row in rows}),
            candidate_rows=len(rows),
            reachable_rows=len(reachable),
            unreachable_rows=len(rows) - len(reachable),
            already_crossed_rows=sum(row.already_crossed for row in rows),
            reachable_strong_rows=sum(row.reachable and row.strong for row in rows),
            reachable_nonstrong_rows=sum(row.reachable and not row.strong for row in rows),
            unreachable_strong_rows=sum(not row.reachable and row.strong for row in rows),
            unreachable_nonstrong_rows=sum(not row.reachable and not row.strong for row in rows),
            unreachable_with_ceiling_rows=sum(
                not row.reachable and np.isfinite(row.a_after) for row in rows),
            numerical_failure_rows=sum(
                not row.reachable and not np.isfinite(row.a_after) for row in rows),
            improving_rows=int(np.count_nonzero(finite_delta < 0.0)),
            unchanged_rows=int(np.count_nonzero(finite_delta == 0.0)),
            all_nodes_below_truth_rows=sum(row.all_nodes_below_truth for row in rows),
            all_nodes_below_truth_strong_rows=sum(
                row.all_nodes_below_truth and row.strong for row in rows),
            row_cap=self.max_rows,
            retained_rows_bounded=len(rows) <= self.max_rows,
            row_table_name=OUTPUT_NAME,
        )
        return {
            key: int(value) if isinstance(value, np.integer) else value
            for key, value in counts.items()
        }
