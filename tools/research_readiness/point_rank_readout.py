"""Exact, tie-aware ranking of the fixed A point readout on aligned Dev pixels."""

import hashlib
from io import BytesIO
import os
from pathlib import Path

import numpy as np

from tools.research_readiness.mountain_pair_metrics import MountainAccumulator


def point_a(probability, qlog):
    if (probability.ndim != 1 or probability.dtype not in (np.float32, np.float64)
            or qlog.shape != (len(probability), 32) or qlog.dtype != np.float64
            or not np.isfinite(probability).all() or np.any((probability < 0) | (probability > 1))
            or not np.isfinite(qlog).all()):
        raise ValueError("Expected finite probability and 32 FP64 log quantiles per valid pixel")
    with np.errstate(over="raise", invalid="raise"):
        score = (probability.astype(np.float64) * np.expm1(qlog).mean(axis=1)).astype(np.float32)
    if not np.isfinite(score).all():
        raise FloatingPointError("Nonfinite fixed A score")
    return score


def rank_scores(score, strong):
    """Compute AP by distinct score and rank AUC with half credit for ties."""
    if score.shape != strong.shape or score.ndim != 1 or score.dtype != np.float32 or strong.dtype != bool:
        raise ValueError("Aligned FP32 scores and Boolean truth labels required")
    if not np.isfinite(score).all():
        raise ValueError("Ranking cannot use nonfinite scores")
    n_pos = int(strong.sum())
    n_neg = len(strong) - n_pos
    result = dict(n_strong=n_pos, n_non_strong=n_neg, ap20=None, auroc20=None, score_overlap=None)
    if not n_pos or not n_neg:
        return result
    order = np.argsort(score)[::-1]
    ordered = score[order]
    ends = np.r_[np.flatnonzero(ordered[:-1] != ordered[1:]), len(order) - 1]
    cum_pos = np.cumsum(strong[order], dtype=np.int64)[ends]
    cum_neg = ends + 1 - cum_pos
    per_pos, per_neg = np.diff(cum_pos, prepend=0), np.diff(cum_neg, prepend=0)
    result["ap20"] = float(np.dot(per_pos, cum_pos / (ends + 1)) / n_pos)
    result["auroc20"] = float(np.dot(per_pos, n_neg - cum_neg + 0.5 * per_neg) / (n_pos * n_neg))
    pos, neg = score[strong], score[~strong]
    neg_max = neg.max()
    result["score_overlap"] = dict(
        strong_range_mm_h=[float(pos.min()), float(pos.max())],
        non_strong_range_mm_h=[float(neg.min()), float(neg_max)],
        strong_strictly_above_non_strong_max=int((pos > neg_max).sum()),
        strong_tied_with_non_strong_max=int((pos == neg_max).sum()),
    )
    return result


def paired_batch(control, ids, mask, truth):
    saved_ids = control["scene_ids"]
    saved_mask = control["supervision_mask"]
    saved_truth = control["truth_mm_h"]
    if (saved_ids.dtype.kind != "U" or saved_ids.tolist() != list(ids)
            or saved_mask.dtype != bool or not np.array_equal(saved_mask, mask)
            or saved_truth.dtype != np.float32 or truth.dtype != np.float32
            or not np.array_equal(saved_truth.view(np.uint32), truth.view(np.uint32))):
        raise ValueError("Paired scene order, supervision mask or FP32 truth differs")
    score = point_a(control["p"], control["qlog"])
    if score.shape != truth.shape:
        raise ValueError("Saved COSINE9 predictions differ from the paired truth shape")
    return score


class PairedPointRankReadout:
    def __init__(self, output, control_folder, shards, pack, ids, contract, check):
        self.output = Path(output)
        self.control_folder = Path(control_folder)
        self.ids, self.shards = tuple(ids), tuple(shards)
        self.check = check
        self.contract = contract
        self.high = MountainAccumulator(pack, ids).masks[2]
        self.position = self.source_bytes = 0
        self.output_files = []
        self.a20, self.baseline, self.truth, self.elevation = [], [], [], []
        self.output.mkdir(exist_ok=False)

    def add(self, ids, rate, valid, region, probability, qlog):
        number = len(self.output_files)
        ids = tuple(ids)
        if not ids or ids != self.ids[self.position:self.position + len(ids)] or number >= len(self.shards):
            raise ValueError("Unexpected matched Development batch order or count")
        mask = (valid & region)[:, 0]
        truth = rate[:, 0][mask]
        if truth.dtype != np.float32 or not np.isfinite(truth).all():
            raise ValueError("Exact finite FP32 supervised truth required")
        item = self.shards[number]
        if (item["file"] != f"batch_{number:03d}.npz" or item["scene_start"] != self.position
                or item["scenes"] != len(ids) or item["n_valid"] != len(truth)):
            raise ValueError("Saved COSINE9 shard population differs")
        source = self.control_folder / item["file"]
        with source.open("rb") as stream:
            if os.fstat(stream.fileno()).st_size != item["bytes"]:
                raise ValueError("Saved COSINE9 shard size changed")
            content = stream.read(item["bytes"])
        if len(content) != item["bytes"] or hashlib.sha256(content).hexdigest() != item["sha256"]:
            raise ValueError("Saved COSINE9 shard SHA256 differs")
        self.source_bytes += len(content)
        with np.load(BytesIO(content), allow_pickle=False) as control:
            reference = paired_batch(control, ids, mask, truth)
        candidate = point_a(probability[:, 0][mask], qlog.transpose(0, 2, 3, 1)[mask])
        self.check(candidate.nbytes + 512)
        filename = f"batch_{number:03d}.npy"
        path = self.output / filename
        with path.open("xb") as stream:
            np.save(stream, candidate, allow_pickle=False)
        self.output_files.append(dict(
            file=filename, scene_start=self.position, scenes=len(ids), n_valid=len(truth),
            bytes=path.stat().st_size, sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
            paired_control_shard_sha256=item["sha256"],
        ))
        self.position += len(ids)
        self.a20.append(candidate)
        self.baseline.append(reference)
        self.truth.append(truth > np.float32(20))
        self.elevation.append(np.broadcast_to(self.high, mask.shape)[mask])

    def finish(self, mask_sha256):
        if (self.position != len(self.ids) or self.position != self.contract["scenes"]
                or len(self.output_files) != len(self.shards)
                or self.source_bytes != self.contract["saved_control_bytes"]
                or mask_sha256 != self.contract["supervision_mask_sha256"]):
            raise ValueError("Final paired readout identities differ")
        positive, elevated = np.concatenate(self.truth), np.concatenate(self.elevation)
        if (len(positive) != self.contract["n_valid"] or int(positive.sum()) != self.contract["n_strong"]
                or int((positive & elevated).sum()) != self.contract["high_n_strong"]):
            raise ValueError("Final full or high-elevation population differs")
        control, candidate = np.concatenate(self.baseline), np.concatenate(self.a20)
        result = {}
        for arm, score in (("COSINE9", control), ("A20", candidate)):
            flag = score > np.float32(20)
            counts = dict(tp=int((flag & positive).sum()), fp=int((flag & ~positive).sum()))
            if counts != self.contract["fixed_a_counts"][arm]:
                raise ValueError(f"{arm} fixed A 20 mm/h counts do not reproduce")
            self.check()
            result[arm] = dict(fixed_a_counts=counts, all=rank_scores(score, positive),
                               elevation_ge_2000m=rank_scores(score[elevated], positive[elevated]))
        return dict(status="MATCHED_RANKING_COMPLETE", population=self.contract["n_valid"],
                    mask_sha256=mask_sha256, saved_control_bytes=self.source_bytes,
                    metrics=result, a20_ap20_improved=result["A20"]["all"]["ap20"] > result["COSINE9"]["all"]["ap20"],
                    a20_score_files=self.output_files, scientific_status="NOT_VERIFIED")
