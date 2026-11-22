"""Prepare or run a single metered 2023 Train RH700 diagnostic at fixed E9."""

from collections import Counter, defaultdict
from datetime import timedelta
from pathlib import Path
import sys

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / "src")]

from tools.research_readiness import start_train_endpoint_screen as endpoint
from tools.research_readiness.start_train_crossing_amplitude import main
from tools.research_readiness.train_rh700_separability import summarize
from yuntapr.experimental.core_innovation.gfs import EnvironmentFrame
from yuntapr.experimental.core_innovation.stage2 import MEE_V13_KEYS
from yuntapr.experimental.core_innovation.stage2.environment import validate_physical_fields
from yuntapr.experimental.core_innovation.stage3.planning import utc


KIND = "BOUNDED_TRAIN_RH700_SEPARABILITY"
SCOPE = "COSINE9_E9_2023_TRAIN_RH700_SEPARABILITY"
STATUS = "COMPLETE_TRAIN_RH700_SEPARABILITY"
FEATURE = "relative_humidity700"
FEATURE_INDEX = MEE_V13_KEYS.index(FEATURE)
MIN_PAIRS, MIN_BLOCKS = 30, 3
CAP = dict(
    **{k: endpoint.CAP[k] for k in ("static_bytes", "static_opens", "checkpoint_bytes",
                                   "checkpoint_source_opens", "checkpoint_hashes", "checkpoint_loads",
                                   "minimum_free_bytes", "batch_size", "optimizer_updates", "refits",
                                   "retries", "replay")},
    total_scientific_source_bytes=16066485320, total_scientific_source_opens=4637,
    weather_and_supervision_bytes=16012265671, weather_and_supervision_opens=4635,
    train_scenes=560, positive_scenes=159, forward_batches=70, max_seconds=2400,
)


def seal(source_root, run, commit):
    plan, paths, prepared = endpoint.seal(source_root, run, commit)
    folder = ROOT / "docs/research_readiness/20261121_stage45_observation_feasibility"
    receipt_path = folder / "TRAIN_RH700_SCOPE_V1.json"
    public = endpoint.read(receipt_path)
    bound = endpoint.read(source_root / endpoint.LOCAL / "train_separability_scope_v1.json")
    receipt = bound.pop("public_receipt")
    scope = bound["source_scope"]
    batches = bound["batches"]
    positives = bound["positive_scene_ids"]
    original = prepared["roles"]["Train"]
    subset = [sid for batch in batches for sid in batch]
    subset_ids = set(subset)
    if (receipt != public or endpoint.digest(bound) != public["private_scope_sha256"]
            or endpoint.digest(scope["files"]) != public["proposed_subset_source_sha256"]
            or endpoint.digest(batches) != public["fixed_batch_order_sha256"]
            or len(batches) != CAP["forward_batches"] or any(len(batch) != CAP["batch_size"] for batch in batches)
            or len(subset_ids) != CAP["train_scenes"] or scope["ids"] != subset
            or subset != [sid for sid in original["ids"] if sid in subset_ids]
            or len(set(positives)) != CAP["positive_scenes"] or not set(positives) <= subset_ids
            or any(not sid.startswith("2023-") for sid in subset)
            or any(v["year"] != 2023 or original["files"].get(k) != v for k, v in scope["files"].items())
            or any(public["budget"].get(k) != v for k, v in CAP.items() if k in public["budget"])
            or (scope["bytes_per_pass"], scope["file_count"]) != (
                CAP["weather_and_supervision_bytes"], CAP["weather_and_supervision_opens"])):
        raise ValueError("Frozen RH700 Train subset or budget differ")

    plan, paths = endpoint.unsigned(plan), endpoint.unsigned(paths)
    paths["selected_strong_scenes"] = positives
    plan.update(authorization_scope=SCOPE, budget=CAP, train_manifest_sha256=scope["source_manifest_sha256"],
                source_receipt_sha256=endpoint.sha(receipt_path), fixed_batch_order_sha256=public["fixed_batch_order_sha256"],
                private_preparation_sha256=endpoint.digest(paths))
    plan["scientific_choices"].update(
        representation="Fixed E9 predictions, pre-normalization SP04 RH700 only",
        retained_features=[], retained_rows="Private ephemeral pairs, aggregate-only receipt",
        matching="Same scene and elevation; unique nearest negative in p<=0.10 and physical q32<=5 mm/h; low q32 only",
        diagnostic_rule="At least 30 physically valid pairs and 3 blocks; strict RH win fraction >0.5 overall and after each valid block deletion",
        feature_collision="No matching by label other than cohorts; no RH values or masks used to choose negative",
        extra_gfs_opens=0,
    )
    for name in ("start_train_crossing_amplitude.py", "train_rh700_separability.py", Path(__file__).name):
        key = "tools/research_readiness/" + name
        plan["code_sha256"][key] = endpoint.sha(ROOT / key)
    plan["proposal_sha256"] = endpoint.digest(plan)
    paths["proposal_sha256"] = plan["proposal_sha256"]
    prepared = prepared | {"roles": prepared["roles"] | {"Train": scope}}
    return plan, paths, prepared


def mapped_rh700(frame, grid):
    validate_physical_fields(frame, (FEATURE, "ps"))
    physical = EnvironmentFrame(frame.identity, frame.grid, {k: frame.fields[k] for k in (FEATURE, "ps")},
                                frame.mode, frame.provenance)
    rh = physical.on_grid(grid, operator="bilinear_point_candidate").fields[FEATURE]
    return rh.values, rh.valid


def decision(blocks):
    available = [counts for counts in blocks.values() if counts["valid_pairs"]]
    valid = sum(counts["valid_pairs"] for counts in available)
    wins = sum(counts["wins"] for counts in available)
    sensitivity = {
        str(block): (wins - counts["wins"]) / (valid - counts["valid_pairs"])
        for block, counts in sorted(blocks.items()) if 0 < counts["valid_pairs"] < valid
    }
    if valid < MIN_PAIRS or len(available) < MIN_BLOCKS:
        status = "INSUFFICIENT_COVERAGE"
    elif 2 * wins <= valid or any(2 * (wins - c["wins"]) <= valid - c["valid_pairs"] for c in available):
        status = "STOP_RH700_DIRECTION"
    else:
        status = "DESCRIPTIVE_TRAIN_SIGNAL_ONLY"
    return dict(decision=status, valid_pairs=valid, valid_blocks=len(available),
                strict_win_fraction=wins / valid if valid else None, leave_one_block_out=sensitivity)


class Summary:
    def __init__(self, positive_scenes):
        self.positive_scenes = set(positive_scenes)
        self.pending = {}
        self.seen = set()
        self.all_pixels = self.all_strong = 0
        self.blocks = defaultdict(Counter)

    def hooks(self, original, population):
        self.elevation = original.pack.values[0]
        grid = original.pack.grid
        scaler = population.environment[FEATURE]

        def capture(frame):
            target = (frame.identity.valid - timedelta(minutes=30)).isoformat()
            if target in self.positive_scenes:
                if target in self.pending or target in self.seen:
                    raise ValueError("Duplicate RH700 capture for one target window")
                self.pending[target] = (frame.identity.valid, *mapped_rh700(frame, grid))
            return original(frame)

        def verify(batch):
            expected = set(batch.ids) & self.positive_scenes
            if set(self.pending) != expected:
                raise ValueError("RH700 capture does not agree with the current batch")
            for index, sid in enumerate(batch.ids):
                if sid not in expected:
                    continue
                valid_time, rh, mask = self.pending[sid]
                normalized = ((np.where(mask, rh, scaler.mean) - scaler.mean) / scaler.std).astype(np.float32)
                mee = batch.environment[index, FEATURE_INDEX].numpy()
                if (valid_time != utc(batch.analyses[index])
                        or not np.array_equal(mask, batch.environment_valid[index, FEATURE_INDEX].numpy())
                        or mee.dtype != np.float32
                        or not np.array_equal(normalized.view(np.uint32), mee.view(np.uint32))):
                    raise ValueError("RH700 time or bit-verified MEE correspondence differs")
        return capture, verify

    def add(self, ids, truth, label_valid, region, probability, qlog):
        for index, sid in enumerate(ids):
            mask = (label_valid & region)[index, 0]
            y = truth[index, 0, mask]
            n_strong = int((y > np.float32(20.)).sum())
            if len(y) != 3430 or bool(n_strong) != (sid in self.positive_scenes):
                raise ValueError("Frozen per-scene supervision or label QC differs")
            self.all_pixels += len(y)
            self.all_strong += n_strong
            if n_strong:
                _, rh, rh_valid = self.pending.pop(sid)
                report = summarize(np.repeat(sid, len(y)), np.flatnonzero(mask), self.elevation[mask], y,
                                   probability[index, 0, mask], qlog[index, -1, mask], rh[mask], rh_valid[mask])
                for block, counts in report["by_block"].items():
                    self.blocks[block].update(counts)
                self.seen.add(sid)

    def finish(self, _output):
        if (self.pending or self.seen != self.positive_scenes or self.all_strong != 484
                or self.all_pixels != CAP["train_scenes"] * 3430):
            raise ValueError("Final frozen RH700 target numerator or coverage differs")
        blocks = dict(sorted(self.blocks.items()))
        return dict(**decision(blocks), by_time_block=blocks, scientific_status="NOT_VERIFIED",
                    true_strong=484, low_q32_strong=sum(c["positive"] for c in blocks.values()),
                    additional_gfs_reads=0, threshold_fits=0, retained_individual_arrays=False)


def install_hooks(summary, transform, population):
    return summary.hooks(transform, population)


if __name__ == "__main__":
    main(kind=KIND, scope=SCOPE, budget=CAP, binder=seal, entry=__file__,
         make_summary=lambda paths: Summary(paths["selected_strong_scenes"]), status=STATUS,
         diagnostic_hooks=install_hooks)
