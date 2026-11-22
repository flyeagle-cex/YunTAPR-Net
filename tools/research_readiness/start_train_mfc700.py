"""Prepare or run one fixed-E9 Train diagnostic for native 700-hPa convergence."""

from collections import Counter, defaultdict
from datetime import date, timedelta
import math
from pathlib import Path
import sys

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / "src")]

from tools.research_readiness import start_train_endpoint_screen as endpoint
from tools.research_readiness import start_train_rh700_separability as rh
from tools.research_readiness.mfc700_synthetic import convergence700
from tools.research_readiness.train_rh700_separability import scene_pairs
from yuntapr.experimental.core_innovation.gfs import EnvironmentFrame, Field, SPECIFIC_HUMIDITY_700
from yuntapr.experimental.core_innovation.stage3.planning import utc
from yuntapr.experimental.research_readiness.dynamic_terrain import ORDER


KIND = "BOUNDED_TRAIN_MFC700_MATCHED"
SCOPE = "COSINE9_E9_2023_TRAIN_MFC700_MATCHED"
STATUS = "COMPLETE_TRAIN_MFC700_MATCHED"
FEATURES = ("MFC700", "RH700", "W700")
WINDWARD_INDEX = ORDER.index("W700")
MIN_PAIRS = 80
MIN_BLOCKS = 10
CAP = dict(rh.CAP, aggregate_receipt_max_bytes=65536)


def seal(source_root, run, commit):
    plan, paths, prepared = rh.seal(source_root, run, commit)
    plan = endpoint.unsigned(plan)
    plan.update(authorization_scope=SCOPE, budget=CAP)
    plan["scientific_choices"].update(
        representation="Fixed E9 unchanged; decode native q700 from the existing thermo buffer",
        matching="Same scene and elevation bin, q32<=20 for both; nearest p then q32 then pixel index, "
                 "calipers .10 and 5 mm/h, no replacement or feature-dependent rematching",
        primary="MFC700 strict win fraction >1/2 and > both RH700 and positive DOTE W700 on the same pairs",
        valid_pair_minimum=MIN_PAIRS,
        valid_14day_block_minimum=MIN_BLOCKS,
        leave_one_block_is_descriptive=True,
        projection="Native spherical finite volume, then bilinear to SP04 with native and target pressure masks",
        diagnostic_rule="Any direction/control loss closes MFC700; coverage shortfall ends as unresolved",
    )
    for name in (Path(__file__).name, "mfc700_synthetic.py"):
        key = "tools/research_readiness/" + name
        plan["code_sha256"][key] = endpoint.sha(ROOT / key)
    plan["proposal_sha256"] = endpoint.digest(plan)
    paths["proposal_sha256"] = plan["proposal_sha256"]
    return plan, paths, prepared


def matched_scene(pixels, elevation, truth, p, q32_log, values, valid):
    """Select pairs by fixed-model outputs, then require common physical support."""
    strong = truth > np.float32(20)
    limit = math.log1p(20)
    low = q32_log <= limit
    q32 = np.expm1(np.minimum(q32_log, limit))
    altitude = np.searchsorted((1000, 2000), elevation, side="right")
    counts = Counter(low_q32_strong=int(np.count_nonzero(low & strong)))
    for band in range(3):
        members = np.flatnonzero(low & (altitude == band))
        for i, j in scene_pairs(members, strong, pixels, p, q32):
            counts["matched"] += 1
            paired_valid = valid[:, i] & valid[:, j]
            for name, available in zip(FEATURES, paired_valid):
                counts[name + "_invalid_pairs"] += int(not available)
            if paired_valid.all():
                counts["valid_pairs"] += 1
                positive, negative = values[:, i], values[:, j]
                if not np.isfinite([positive, negative]).all():
                    raise ValueError("Diagnostic features must be finite on marked-valid pairs")
                for name, win, tie in zip(FEATURES, positive > negative, positive == negative):
                    counts[name + "_wins"] += int(win)
                    counts[name + "_ties"] += int(tie)
    return counts


def outcome(blocks):
    total = Counter()
    for counts in blocks.values():
        total.update(counts)
    pairs = total["valid_pairs"]
    valid_blocks = sum(bool(counts["valid_pairs"]) for counts in blocks.values())

    def scores(counts):
        denominator = counts["valid_pairs"]
        return {name: counts[name + "_wins"] / denominator if denominator else None for name in FEATURES}

    if pairs < MIN_PAIRS or valid_blocks < MIN_BLOCKS:
        decision = "INSUFFICIENT_COMMON_COVERAGE"
    elif (2 * total["MFC700_wins"] <= pairs
          or total["MFC700_wins"] <= max(total["RH700_wins"], total["W700_wins"])):
        decision = "STOP_MFC_DIRECTION_OR_CONTROL"
    else:
        decision = "DESCRIPTIVE_TRAIN_SIGNAL_ONLY"
    return dict(
        decision=decision,
        counts=dict(total),
        valid_blocks=valid_blocks,
        strict_win_fraction=scores(total),
        by_block={str(block): dict(counts) for block, counts in sorted(blocks.items())},
        leave_one_block_out={str(block): scores(total - counts) for block, counts in sorted(blocks.items())
                             if 0 < counts["valid_pairs"] < pairs},
    )


class Summary:
    def __init__(self, positive_scenes):
        self.positive_scenes = set(positive_scenes)
        self.seen = set()
        self.pending = {}
        self.aligned = {}
        self.blocks = defaultdict(Counter)
        self.all_pixels = 0
        self.all_strong = 0

    def hooks(self, transform, population):
        self.pack = transform.pack
        self.scaler = population.environment[rh.FEATURE]
        return transform, self.verify_batch

    def capture(self, frame):
        analysis = frame.identity.valid
        target = (analysis - timedelta(minutes=30)).isoformat()
        if target not in self.positive_scenes:
            return
        if target in self.pending or target in self.seen:
            raise ValueError("Duplicate MFC forecast capture")
        if frame.mode != "retrospective" or frame.identity.lead != timedelta(hours=6):
            raise ValueError("MFC requires the frozen f006 analysis identity")
        keys = (SPECIFIC_HUMIDITY_700.key, "u700", "v700", "ps")
        q, u, v, ps = (frame.fields[key] for key in keys)
        if [(f.quantity, f.unit, f.level_pa) for f in (q, u, v, ps)] != [
            ("specific_humidity", "kg kg-1", 70000.), ("u", "m/s", 70000.),
            ("v", "m/s", 70000.), ("surface_pressure", "Pa", None),
        ]:
            raise ValueError("MFC physical field identities differ")
        mfc, _, _, valid = convergence700(frame.grid.lat, frame.grid.lon, q.values, u.values,
                                          v.values, ps.values, q.valid & u.valid & v.valid & ps.valid)
        diagnostic = EnvironmentFrame(
            frame.identity, frame.grid,
            {"mfc": Field(mfc, valid, "moisture_flux_convergence", "s-1", 70000.),
             "ps": ps, rh.FEATURE: frame.fields[rh.FEATURE]},
            frame.mode, frame.provenance,
        )
        mapped = diagnostic.on_grid(self.pack.grid, operator="bilinear_point_candidate")
        self.pending[target] = (analysis, mapped.fields["mfc"], mapped.fields[rh.FEATURE])

    def verify_batch(self, batch):
        expected = set(batch.ids) & self.positive_scenes
        if self.aligned or set(self.pending) != expected:
            raise ValueError("MFC forecast capture disagrees with the current batch")
        for index, sid in enumerate(batch.ids):
            if sid not in expected:
                continue
            analysis, mfc, humidity = self.pending.pop(sid)
            mean, std = self.scaler.mean, self.scaler.std
            normalized = ((np.where(humidity.valid, humidity.values, mean) - mean) / std).astype(np.float32)
            mee = batch.environment[index, rh.FEATURE_INDEX].numpy()
            if (analysis != utc(batch.analyses[index]) or mee.dtype != np.float32
                    or not np.array_equal(humidity.valid, batch.environment_valid[index, rh.FEATURE_INDEX].numpy())
                    or not np.array_equal(normalized.view(np.uint32), mee.view(np.uint32))):
                raise ValueError("Physical RH differs from the bit-verified existing MEE input")
            upslope = batch.dynamic[index, WINDWARD_INDEX].numpy()
            upslope_valid = batch.dynamic_valid[index, WINDWARD_INDEX].numpy()
            if np.any(upslope[upslope_valid] < 0):
                raise ValueError("DOTE W700 must be nonnegative")
            self.aligned[sid] = (np.stack((mfc.values, humidity.values, upslope)),
                                 np.stack((mfc.valid, humidity.valid, upslope_valid)))

    def add(self, ids, truth, valid, region, probability, qlog):
        for index, sid in enumerate(ids):
            mask = (valid & region)[index, 0]
            y = truth[index, 0, mask]
            strong = int(np.count_nonzero(y > np.float32(20)))
            if len(y) != 3430 or bool(strong) != (sid in self.positive_scenes):
                raise ValueError("Frozen strong scene or supervision pixel count differs")
            self.all_pixels += len(y)
            self.all_strong += strong
            if strong:
                values, physical_valid = self.aligned.pop(sid)
                block = (date.fromisoformat(sid[:10]) - date(2023, 1, 1)).days // 14
                match = matched_scene(np.flatnonzero(mask), self.pack.values[0][mask], y,
                                      probability[index, 0, mask], qlog[index, -1, mask],
                                      values[:, mask], physical_valid[:, mask])
                self.blocks[block].update(match)
                self.seen.add(sid)

    def finish(self, _output):
        if (self.aligned or self.pending or self.seen != self.positive_scenes or self.all_strong != 484
                or self.all_pixels != CAP["train_scenes"] * 3430):
            raise ValueError("Frozen Train diagnostic coverage differs")
        result = outcome(self.blocks)
        if (result["counts"].get("low_q32_strong"), result["counts"].get("matched")) != (350, 349):
            raise ValueError("Frozen E9 low-q32 coverage or raw pairing differs")
        return dict(**result, true_strong=self.all_strong, scientific_status="NOT_VERIFIED",
                    retained_individual_arrays=False, additional_gfs_reads=0, threshold_fits=0)


if __name__ == "__main__":
    rh.main(kind=KIND, scope=SCOPE, budget=CAP, binder=seal, entry=__file__,
            make_summary=lambda paths: Summary(paths["selected_strong_scenes"]), status=STATUS,
            diagnostic_hooks=rh.install_hooks,
            native_diagnostic_factory=lambda summary: (SPECIFIC_HUMIDITY_700, summary.capture),
            description=__doc__)
