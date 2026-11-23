"""Describe bounded candidate crossings on the frozen 2023 Train readout.

This is a descriptive engineering manifest only.  It performs one forward pass
over the same fixed 560-scene/70-batch Train subset as the MFC700 amplitude
arm, retains only strict ``p * q32 > 20`` pixels, and records the frozen
weak-preserving minimal-crossing witness.  It fits no coefficient, updates no
optimizer, accesses no 2025 data, and does not claim scientific verification.
"""

from pathlib import Path
import sys

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / "src")]

from tools.research_readiness import start_train_endpoint_screen as endpoint
from tools.research_readiness import start_train_rh700_separability as rh
from tools.research_readiness.stage45_candidate_manifest import (
    CANDIDATE_THRESHOLD,
    MAX_CANDIDATE_ROWS,
    SUPERVISION_PIXELS_PER_SCENE,
    CandidateManifest,
)


KIND = "BOUNDED_TRAIN_STAGE45_CANDIDATE_MANIFEST"
SCOPE = "COSINE9_E9_2023_TRAIN_STAGE45_CANDIDATE_MANIFEST"
STATUS = "COMPLETE_TRAIN_STAGE45_CANDIDATE_MANIFEST"
CAP = dict(rh.CAP)
DECISION = "DESCRIPTIVE_ENGINEERING_MANIFEST_ONLY"


def seal(source_root, run, commit):
    plan, paths, prepared = rh.seal(source_root, run, commit)
    plan, paths = endpoint.unsigned(plan), endpoint.unsigned(paths)

    ids = tuple(prepared["roles"]["Train"]["ids"])
    positives = tuple(paths["selected_strong_scenes"])
    if (len(ids) != CAP["train_scenes"] or len(set(ids)) != CAP["train_scenes"]
            or len(positives) != CAP["positive_scenes"] or not set(positives) <= set(ids)):
        raise ValueError("The frozen 560-scene/159-positive Train subset changed")
    paths["candidate_scene_ids"] = list(ids)

    plan.update(authorization_scope=SCOPE, budget=CAP)
    plan["scientific_choices"] = {
        **{field: plan["scientific_choices"][field] for field in ("DOTE", "modulation_limit")},
        "representation": "Unchanged fixed E9 per-pixel p and conditional qlog; no coefficient or gate fit",
        "support": "All 3430 supervised pixels of each fixed 560-scene subset scene; 70 batches",
        "candidate_rule": f"Strict FP64 p*expm1(qlog32)>{CANDIDATE_THRESHOLD}; no matching or cut",
        "action": "Weak-preserving maximum-mean vertex with fixed q32 and exact weak log Pinball, "
                  "then strict minimal ordered A>20 crossing along the original-to-vertex segment",
        "boundary": "Frozen FP32 point readout for strict A>20; near-equal boundaries unresolved",
        "retained_rows": "bounded candidate rows only",
        "row_cap": MAX_CANDIDATE_ROWS,
        "no_coefficient_fit": True,
        "full_train_false_positive_verified": False,
        "development_scientific_reads": 0,
        "final_2025_access": False,
    }
    for name in (Path(__file__).name, "stage45_candidate_manifest.py"):
        key = "tools/research_readiness/" + name
        plan["code_sha256"][key] = endpoint.sha(ROOT / key)
    plan["private_preparation_sha256"] = endpoint.digest(paths)
    plan["proposal_sha256"] = endpoint.digest(plan)
    paths["proposal_sha256"] = plan["proposal_sha256"]
    return plan, paths, prepared


class Summary:
    """Enforce the frozen 560-scene population and collect bounded candidate rows."""

    def __init__(self, positive_scenes, scene_ids):
        self.positive_scenes = set(positive_scenes)
        self.scene_ids = tuple(scene_ids)
        self.scene_set = set(self.scene_ids)
        if (len(self.scene_ids) != CAP["train_scenes"] or len(self.scene_set) != CAP["train_scenes"]
                or len(self.positive_scenes) != CAP["positive_scenes"]
                or not self.positive_scenes <= self.scene_set):
            raise ValueError("Frozen 560-scene/159-positive candidate population required")
        self.manifest = CandidateManifest()
        self.seen = set()
        self.all_pixels = 0
        self.all_strong = 0

    def add(self, ids, truth, valid, region, probability, qlog):
        shape = (len(ids), 1, 100, 100)
        if (any(item.shape != shape for item in (truth, valid, region, probability))
                or qlog.shape != (len(ids), 32, 100, 100)
                or truth.dtype != np.float32 or qlog.dtype != np.float64
                or valid.dtype != np.bool_ or region.dtype != np.bool_
                or len(set(ids)) != len(ids) or not set(ids) <= self.scene_set
                or self.seen.intersection(ids)
                or not np.isfinite(probability).all()):
            raise ValueError("Candidate prediction or fixed batch identity differs")
        for index, sid in enumerate(ids):
            mask = (valid & region)[index, 0]
            y = truth[index, 0, mask]
            strong = int(np.count_nonzero(y > np.float32(20.0)))
            if (len(y) != SUPERVISION_PIXELS_PER_SCENE
                    or bool(strong) != (sid in self.positive_scenes)):
                raise ValueError("Frozen Train supervision or strong-scene QC differs")
            self.manifest.update(
                probability[index, 0], qlog[index], truth[index, 0],
                valid[index, 0], region[index, 0], sid,
            )
            self.all_pixels += len(y)
            self.all_strong += strong
            self.seen.add(sid)

    def finish(self, output):
        expected_pixels = CAP["train_scenes"] * SUPERVISION_PIXELS_PER_SCENE
        if (len(self.seen) != CAP["train_scenes"] or self.seen != self.scene_set
                or len(self.positive_scenes) != CAP["positive_scenes"]
                or self.all_pixels != expected_pixels
                or self.all_strong != endpoint.CAP["strong_pixels"]):
            raise ValueError("The exact 560-scene candidate population must be fully evaluated")
        manifest = self.manifest.finish(output)
        if (manifest["evaluated_scenes"] != len(self.seen)
                or manifest["evaluated_supervised_pixels"] != self.all_pixels
                or manifest["evaluated_strong_pixels"] != self.all_strong
                or manifest["candidate_rows"] > manifest["row_cap"]):
            raise ValueError("The bounded manifest coverage differs from the frozen Train population")
        return dict(
            decision=DECISION,
            candidate_manifest=manifest,
            evaluated_scenes=len(self.seen),
            evaluated_supervised_pixels=self.all_pixels,
            true_strong=self.all_strong,
            true_nonstrong=self.all_pixels - self.all_strong,
            full_train_scenes=endpoint.CAP["train_scenes"],
            full_train_positive_scenes=CAP["positive_scenes"],
            omitted_train_scenes=endpoint.CAP["train_scenes"] - len(self.seen),
            full_train_false_positive_verified=False,
            scientific_status="NOT_VERIFIED",
            coefficient_fits=0,
            additional_gfs_reads=0,
            retained_rows_bounded=True,
        )


if __name__ == "__main__":
    rh.main(
        kind=KIND, scope=SCOPE, budget=CAP, binder=seal, entry=__file__,
        make_summary=lambda paths: Summary(paths["selected_strong_scenes"], paths["candidate_scene_ids"]),
        status=STATUS, description=__doc__,
    )
