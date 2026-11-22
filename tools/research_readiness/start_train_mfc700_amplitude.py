"""Prepare or run one metered MFC700 amplitude diagnostic on fixed Train batches."""

from pathlib import Path
import re
import sys

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / "src")]

from tools.research_readiness import start_train_endpoint_screen as endpoint
from tools.research_readiness import start_train_mfc700 as mfc
from tools.research_readiness import start_train_rh700_separability as rh
from tools.research_readiness.mfc700_amplitude_bounds import AmplitudeBounds


KIND = "BOUNDED_TRAIN_MFC700_AMPLITUDE"
SCOPE = "COSINE9_E9_2023_TRAIN_MFC700_AMPLITUDE"
STATUS = "COMPLETE_TRAIN_MFC700_AMPLITUDE_BOUNDS"
CAP = mfc.CAP
DOCS = Path("docs/research_readiness/20261121_stage45_observation_feasibility")
MATCHED_RESULT = DOCS / "MFC700_E9_MATCHED_RESULTS_V1.json"
MATCHED_PROPOSAL = DOCS / "MFC700_E9_MATCHED_EXECUTION_PROPOSAL_V1.json"
MATCHED_RESULT_SHA = "a73a6e00a0e1678542c3eabb9eb6f306d44873c45a0e8122da993863703cf6eb"
MATCHED_PROPOSAL_SHA = "7ad7c6096fd44d9d290e44a0aca9c6b8d8458ec8c4667e9c5fbe4b670cd00529"
SUPERVISION_PIXELS_PER_SCENE = 3430


def seal(source_root, run, commit):
    if not re.fullmatch("[0-9a-f]{40}", commit):
        raise ValueError("Bind the exact execution code commit")
    receipt_file = ROOT / MATCHED_RESULT
    if endpoint.sha(receipt_file) != MATCHED_RESULT_SHA:
        raise ValueError("The pinned MFC700 matched result changed")
    receipt = endpoint.read(receipt_file)
    reference = endpoint.read(ROOT / MATCHED_PROPOSAL)
    if (reference["proposal_sha256"] != MATCHED_PROPOSAL_SHA
            or endpoint.digest(endpoint.unsigned(reference)) != MATCHED_PROPOSAL_SHA
            or receipt["proposal_sha256"] != MATCHED_PROPOSAL_SHA
            or receipt["status"] != mfc.STATUS or receipt["decision"] != "DESCRIPTIVE_TRAIN_SIGNAL_ONLY"
            or receipt["forward_batches"] != CAP["forward_batches"]
            or receipt["true_strong"] != endpoint.CAP["strong_pixels"]
            or receipt["exit_code"] != 0 or receipt["optimizer_updates"] != 0
            or receipt["final_2025_access"] is not False):
        raise ValueError("A verified matched MFC700 Train result is required")

    plan, paths, prepared = mfc.seal(source_root, run, commit)
    inherited = ("tasks", "budget", "data", "runtime", "python_sha256", "checkpoint_sha256",
                 "static_sha256", "static_receipt_sha256", "train_manifest_sha256",
                 "source_receipt_sha256", "fixed_batch_order_sha256")
    if any(plan[field] != reference[field] for field in inherited):
        raise ValueError("The amplitude diagnostic must use the exact matched E9 and Train traversal")
    choices = ("DOTE", "modulation_limit", "projection", "extra_gfs_opens")
    if any(plan["scientific_choices"][field] != reference["scientific_choices"][field] for field in choices):
        raise ValueError("Native MFC or fixed-model input definitions differ")

    plan, paths = endpoint.unsigned(plan), endpoint.unsigned(paths)
    paths["amplitude_scene_ids"] = prepared["roles"]["Train"]["ids"]
    plan.update(authorization_scope=SCOPE, prior_mfc700_proposal_sha256=MATCHED_PROPOSAL_SHA,
                prior_mfc700_receipt_sha256=MATCHED_RESULT_SHA,
                private_preparation_sha256=endpoint.digest(paths))
    plan["scientific_choices"] = {
        **{field: reference["scientific_choices"][field] for field in choices},
        "representation": "Unchanged fixed E9 predictions and native-derived SP04 mapped MFC700",
        "support": "All supervised pixels of all 560 original scenes and 70 batches; no q32 cut or matching",
        "action": "Uniform positive delta times I(MFC700 valid and MFC700>0) added to all 32 physical nodes; p fixed",
        "diagnostic_rule": "Simultaneous open strong-A hit bound, no new nonstrong A or q32 crossings, "
                           "and strict mean strong physical Pinball/20 improvement",
        "fixed_readouts": "Strict FP32 A>20 and FP64 qlog32>log1p(20)",
        "retained_rows": "Aggregate bounds and cohort counts only",
        "no_coefficient_fit": True,
        "full_train_false_positive_verified": False,
        "development_scientific_reads": 0,
        "final_2025_access": False,
    }
    for name in (Path(__file__).name, "mfc700_amplitude_bounds.py", "rh700_amplitude_feasibility.py"):
        key = "tools/research_readiness/" + name
        plan["code_sha256"][key] = endpoint.sha(ROOT / key)
    plan["proposal_sha256"] = endpoint.digest(plan)
    paths["proposal_sha256"] = plan["proposal_sha256"]
    return plan, paths, prepared


class Summary(mfc.Summary):
    """Consume the existing native MFC callback on every scene of the fixed subset."""

    def __init__(self, positive_scenes, scene_ids):
        super().__init__(positive_scenes, capture_scenes=scene_ids)
        self.bounds = AmplitudeBounds()

    def add(self, ids, truth, valid, region, probability, qlog):
        shape = (len(ids), 1, 100, 100)
        if (any(item.shape != shape for item in (truth, valid, region, probability))
                or qlog.shape != (len(ids), 32, 100, 100) or truth.dtype != np.float32
                or qlog.dtype != np.float64 or valid.dtype != np.bool_ or region.dtype != np.bool_
                or set(ids) != set(self.aligned) or self.seen.intersection(ids)):
            raise ValueError("Amplitude prediction or native MFC capture differs from the current batch")
        for index, sid in enumerate(ids):
            mask = (valid & region)[index, 0]
            y = truth[index, 0, mask]
            strong = int(np.count_nonzero(y > np.float32(20)))
            if len(y) != SUPERVISION_PIXELS_PER_SCENE or bool(strong) != (sid in self.positive_scenes):
                raise ValueError("Frozen Train supervision or strong-scene QC differs")
            features, feature_valid = self.aligned.pop(sid)
            self.bounds.update(probability[index, 0, mask], qlog[index][:, mask].T, y,
                               features[0, mask], feature_valid[0, mask])
            self.all_pixels += len(y)
            self.all_strong += strong
            self.seen.add(sid)

    def finish(self, _output):
        if (self.pending or self.aligned or self.seen != self.capture_scenes
                or len(self.seen) != CAP["train_scenes"]
                or len(self.positive_scenes) != CAP["positive_scenes"]
                or self.all_pixels != CAP["train_scenes"] * SUPERVISION_PIXELS_PER_SCENE
                or self.all_strong != endpoint.CAP["strong_pixels"]):
            raise ValueError("The exact 560-scene amplitude population must be fully evaluated")
        bounds = self.bounds.finish()
        nonstrong = self.all_pixels - self.all_strong
        if (bounds["strong"], bounds["nonstrong"]) != (self.all_strong, nonstrong):
            raise ValueError("Analytic bound counts differ from the supervised Train population")
        return dict(
            decision=bounds["decision"], amplitude_bounds=bounds, evaluated_scenes=len(self.seen),
            evaluated_supervised_pixels=self.all_pixels, true_strong=self.all_strong,
            true_nonstrong=nonstrong, full_train_scenes=endpoint.CAP["train_scenes"],
            omitted_train_scenes=endpoint.CAP["train_scenes"] - len(self.seen),
            full_train_false_positive_verified=False, scientific_status="NOT_VERIFIED",
            retained_individual_arrays=False, coefficient_fits=0, additional_gfs_reads=0,
        )


if __name__ == "__main__":
    rh.main(kind=KIND, scope=SCOPE, budget=CAP, binder=seal, entry=__file__,
            make_summary=lambda paths: Summary(paths["selected_strong_scenes"], paths["amplitude_scene_ids"]),
            status=STATUS, diagnostic_hooks=rh.install_hooks,
            native_diagnostic_factory=lambda summary: (mfc.SPECIFIC_HUMIDITY_700, summary.capture),
            description=__doc__)
