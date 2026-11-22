"""Apply one analytic RH700 amplitude bound to the frozen same-scene Train scope."""

from pathlib import Path
import sys

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / "src")]

from tools.research_readiness import start_train_endpoint_screen as endpoint
from tools.research_readiness import start_train_rh700_separability as rh
from tools.research_readiness.rh700_amplitude_feasibility import required_interval


KIND = "BOUNDED_TRAIN_RH700_AMPLITUDE"
SCOPE = "COSINE9_E9_2023_TRAIN_RH700_AMPLITUDE"
STATUS = "COMPLETE_TRAIN_RH700_AMPLITUDE_BOUNDS"


def seal(source_root, run, commit):
    plan, paths, prepared = rh.seal(source_root, run, commit)
    result_file = (
        ROOT / "docs/research_readiness/20261121_stage45_observation_feasibility/TRAIN_RH700_RESULTS_V1.json"
    )
    prior = endpoint.read(result_file)
    if (prior["proposal_sha256"] != "8d2e30c2650055b26b3716eb1a6d139120a4cccea3db292d2037de9eff4bd31a"
            or prior["status"] != rh.STATUS or prior["decision"] != "DESCRIPTIVE_TRAIN_SIGNAL_ONLY"
            or prior["valid_pairs"] != 339 or prior["valid_blocks"] != 17 or prior["final_2025_access"]):
        raise ValueError("Verified prior RH700 diagnostic required")

    plan = endpoint.unsigned(plan)
    plan.update(authorization_scope=SCOPE, prior_rh700_receipt_sha256=endpoint.sha(result_file))
    choices = plan["scientific_choices"]
    for key in ("matching", "feature_collision", "retained_features"):
        choices.pop(key)
    choices.update(
        representation="Fixed E9 and SP04 RH700; amplitude-only necessary interval",
        retained_rows="Aggregate bounds only; all valid negatives in the 159 selected positive scenes",
        diagnostic_rule="An open lower bound for any strong fixed-A hit, and both negative upper bounds",
        action="For original q32<=20 and valid RH700: add delta*clip(RH700/100,0,1) to all 32 physical nodes",
        boundary="Frozen FP32 midpoint for strict A>20; near-equal bounds unresolved",
        no_coefficient_fit=True,
    )
    for name in (Path(__file__).name, "rh700_amplitude_feasibility.py"):
        key = "tools/research_readiness/" + name
        plan["code_sha256"][key] = endpoint.sha(ROOT / key)
    plan["proposal_sha256"] = endpoint.digest(plan)
    paths["proposal_sha256"] = plan["proposal_sha256"]
    return plan, paths, prepared


def conclude(bounds):
    lower = bounds["first_hit"]
    stops = [value for key, value in bounds.items() if key != "first_hit" and value is not None]
    upper = min(stops, default=None)
    if lower is None:
        status = "STOP_NO_POTENTIAL_STRONG_HIT"
    elif upper is None:
        status = "LOCAL_NECESSARY_INTERVAL_NOT_EXCLUDED"
    else:
        tolerance = 128 * np.finfo(np.float64).eps * max(1., abs(lower), abs(upper))
        if abs(lower - upper) <= tolerance:
            status = "NUMERICAL_BOUNDARY_UNRESOLVED"
        elif lower > upper:
            status = "STOP_LOCAL_NEGATIVE_CEILING"
        else:
            status = "LOCAL_NECESSARY_INTERVAL_NOT_EXCLUDED"
    return dict(decision=status, first_hit=lower, upper=upper)


class Summary(rh.Summary):
    def __init__(self, positive_scenes):
        super().__init__(positive_scenes)
        self.bounds = dict(first_hit=None, point_stop=None, tail_stop=None)
        self.target_pixels = self.target_negative = 0

    def add(self, ids, truth, label_valid, region, probability, qlog):
        for index, sid in enumerate(ids):
            mask = (label_valid & region)[index, 0]
            y = truth[index, 0, mask]
            n_strong = int((y > np.float32(20.)).sum())
            if len(y) != 3430 or bool(n_strong) != (sid in self.positive_scenes):
                raise ValueError("Frozen per-scene supervision or label QC differs")
            self.all_pixels += len(y)
            self.all_strong += n_strong
            if not n_strong:
                continue
            _, humidity, valid = self.pending.pop(sid)
            nodes = qlog[index][:, mask].T
            response = required_interval(probability[index, 0, mask], nodes, y, humidity[mask], valid[mask])
            for key, previous in self.bounds.items():
                value = response[key]
                if value is not None:
                    self.bounds[key] = value if previous is None else min(value, previous)
            self.target_pixels += len(y)
            self.target_negative += len(y) - n_strong
            self.seen.add(sid)

    def finish(self, _output):
        if (self.pending or self.seen != self.positive_scenes or self.all_strong != 484
                or self.all_pixels != rh.CAP["train_scenes"] * 3430
                or self.target_pixels != rh.CAP["positive_scenes"] * 3430):
            raise ValueError("Frozen amplitude diagnostic coverage differs")
        return dict(**conclude(self.bounds), bound_components=self.bounds,
                    true_strong_total=self.all_strong, evaluated_target_pixels=self.target_pixels,
                    evaluated_target_negative=self.target_negative, matched_target_scenes=len(self.seen),
                    scientific_status="NOT_VERIFIED", coefficient_fits=0, additional_gfs_reads=0,
                    full_train_false_positive_verified=False, retained_individual_arrays=False)


if __name__ == "__main__":
    rh.main(kind=KIND, scope=SCOPE, budget=rh.CAP, binder=seal, entry=__file__,
            make_summary=lambda paths: Summary(paths["selected_strong_scenes"]), status=STATUS,
            diagnostic_hooks=rh.install_hooks)
