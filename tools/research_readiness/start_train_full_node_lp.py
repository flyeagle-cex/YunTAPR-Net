"""Prepare or run the six original batches containing the ten fixed Train cases."""

from collections import Counter
from hashlib import sha256
import json
import math
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / "src")]

import numpy as np
import scipy

from tools.research_readiness import start_train_crossing_amplitude as parent
from tools.research_readiness.a20_fixed_endpoint_bounds import point, weak_preserving_vertex
from tools.research_readiness.a20_full_node_lp import SOLVER_SECONDS, solve
from yuntapr.experimental.core_innovation.stage4.data import PopulationPlan


endpoint = parent.endpoint
KIND = "BOUNDED_TRAIN_FULL_NODE_LP"
SCOPE = "COSINE9_E9_2023_TRAIN_FULL_NODE_LP"
STATUS = "COMPLETE_TRAIN_FULL_NODE_LP"
PARENT_PROPOSAL = "6ac43a39e9d029ba13a8ad257291dd6e119f81c0b7b6a19c169cd8a7a7bf0685"
PARENT_CASES = "667bd0707d18ecdd98ff34e1aa428ab86da0fbca50f6d91e20bc495aff00a41f"
CAP = {key: value for key, value in parent.CAP.items() if key not in ("positive_scenes", "max_intervals_per_case")}
CAP.update(weather_and_supervision_bytes=1415367126, weather_and_supervision_opens=400,
           total_scientific_source_bytes=1469586775, total_scientific_source_opens=402,
           train_scenes=48, forward_batches=6, max_seconds=600,
           max_private_inputs_bytes=16 * 1024, solver_calls=10, solver_seconds_per_case=SOLVER_SECONDS)
PARENT_CASES_BYTES = 2036
SCIPY_VERSION = "1.17.1"


def locate_cases(targets, strong_scenes):
    """Resolve only existing private keys in the original strong-scene metadata."""
    matches = {}
    for sid in strong_scenes:
        block = parent.block_id(sid)
        for row in range(100):
            for column in range(100):
                key = endpoint.digest([sid, row, column])
                if key in targets:
                    if key in matches or targets[key] != block:
                        raise ValueError("Parent case identity is ambiguous")
                    matches[key] = [sid, row, column, block]
    if matches.keys() != targets.keys():
        raise ValueError("Could not recover all ten exact case identities")
    return matches


def seal(source_root, run, commit):
    if scipy.__version__ != SCIPY_VERSION:
        raise ValueError("Pinned SciPy runtime differs")
    plan, paths, prepared = parent.seal(source_root, run, commit)
    prior = endpoint.read(ROOT / parent.DOCS / "A20_TRAIN_CROSSING_AMPLITUDE_RESULTS.json")
    if (prior["proposal_sha256"] != PARENT_PROPOSAL or prior["source_private_cases_sha256"] != PARENT_CASES
            or prior["cases"] != {"NO_GAIN_BEYOND_TOLERANCE": 10}):
        raise ValueError("The fixed-line diagnostic identity or outcome differs")
    receipt = source_root / endpoint.LOCAL / "a20_train_crossing_amplitude_20261122_v1/output/private_cases.json"
    with receipt.open("rb") as stream:
        raw = stream.read(PARENT_CASES_BYTES + 1)
    if len(raw) != PARENT_CASES_BYTES or sha256(raw).hexdigest() != PARENT_CASES:
        raise ValueError("Parent private case receipt differs")
    cases = json.loads(raw)
    targets = {case["case_sha256"]: case["time_block"] for case in cases}
    if len(cases) != 10 or len(targets) != 10 or Counter(targets.values()) != parent.COUNTS:
        raise ValueError("Expected exactly ten parent cases in their original blocks")
    locations = locate_cases(targets, paths.pop("selected_strong_scenes"))
    full = prepared["roles"]["Train"]
    batches = parent.choose_batches(tuple(full["ids"]), {case[0] for case in locations.values()})
    subset = tuple(sid for batch in batches for sid in batch)
    if (len(batches) != CAP["forward_batches"] or len(subset) != CAP["train_scenes"]
            or any(len(batch) != CAP["batch_size"] for batch in batches)):
        raise ValueError("Only six intact original Train batches may be used")
    inputs = prepared["private_inputs"]
    population = PopulationPlan(inputs["stage3_run"], inputs["request"], root=ROOT)
    bounds = parent.restrict_scope(population, full["files"], subset)
    if (bounds["bytes_per_pass"], bounds["file_count"]) != (
            CAP["weather_and_supervision_bytes"], CAP["weather_and_supervision_opens"]):
        raise ValueError("Exact six-batch scientific source budget differs")
    plan, paths = endpoint.unsigned(plan), endpoint.unsigned(paths)
    plan.update(authorization_scope=SCOPE, budget=CAP, parent_proposal_sha256=PARENT_PROPOSAL,
                parent_private_case_receipt_sha256=PARENT_CASES, inherited_case_receipt_bytes=PARENT_CASES_BYTES,
                scipy_version=SCIPY_VERSION, original_batch_order_sha256=endpoint.digest(batches),
                train_manifest_sha256=bounds["source_manifest_sha256"], scientific_source_kinds=bounds["by_kind"])
    for name in ("a20_full_node_lp.py", Path(__file__).name):
        relative = "tools/research_readiness/" + name
        plan["code_sha256"][relative] = endpoint.sha(ROOT / relative)
    plan["scientific_choices"].update(
        geometry="All original admissible interior log quantile positions; LP moment box outer bound",
        retain_individual_arrays=True, private_retention="Only ten inputs, no raw coordinates or scene IDs",
        offline_research_only=True, no_attempts_outside_exact_cases=True,
    )
    paths["case_locations"] = locations
    plan["private_preparation_sha256"] = endpoint.digest(paths)
    plan["proposal_sha256"] = endpoint.digest(plan)
    paths["proposal_sha256"] = plan["proposal_sha256"]
    return plan, paths, dict(prepared, roles={"Train": bounds})


class Summary:
    def __init__(self, locations):
        self.by_scene = {}
        for key, (sid, row, column, block) in locations.items():
            self.by_scene.setdefault(sid, []).append((key, row, column, block))
        self.expected = set(locations)
        self.cases = {}
        self.valid_pixels = 0

    def add(self, ids, truth, valid, region, p, qlog):
        shape = (len(ids), 1, 100, 100)
        if (any(array.shape != shape for array in (truth, valid, region, p))
                or qlog.shape != (len(ids), 32, 100, 100) or truth.dtype != np.float32
                or qlog.dtype != np.float64 or valid.dtype != np.bool_ or region.dtype != np.bool_):
            raise ValueError("Frozen case representation differs")
        for i, sid in enumerate(ids):
            mask = valid[i, 0] & region[i, 0]
            if int(mask.sum()) != 3430:
                raise ValueError("Frozen supervision mask differs")
            self.valid_pixels += 3430
            for key, row, column, block in self.by_scene.get(sid, ()):
                if (key in self.cases or endpoint.digest([sid, row, column]) != key
                        or not mask[row, column] or parent.block_id(sid) != block):
                    raise ValueError("A frozen case is duplicated or outside its original valid area")
                y, prob = float(truth[i, 0, row, column]), float(p[i, 0, row, column])
                nodes = qlog[i, :, row, column]
                if (not math.isfinite(y) or y <= 20 or not 0 <= prob <= 1
                        or not np.isfinite(nodes).all() or np.any(nodes < 0) or np.any(np.diff(nodes) <= 0)
                        or point(prob, nodes) > 20 or point(prob, weak_preserving_vertex(nodes)) <= 20):
                    raise ValueError("The original strong crossing case was not reproduced")
                self.cases[key] = dict(case_sha256=key, time_block=block, p=prob,
                                       qlog=nodes.tolist(), truth_fp32=y)

    def finish(self, output):
        if self.cases.keys() != self.expected or self.valid_pixels != CAP["train_scenes"] * 3430:
            raise ValueError("The six-batch inference did not reproduce all ten cases")
        cases = [self.cases[key] for key in sorted(self.cases)]
        blocks = Counter(case["time_block"] for case in cases)
        if blocks != parent.COUNTS:
            raise ValueError("Frozen case-time counts differ")
        archive = output / "private_full_node_inputs.json"
        encoded = (json.dumps(cases, indent=2, allow_nan=False) + "\n").encode("utf-8")
        if len(encoded) > CAP["max_private_inputs_bytes"]:
            raise ValueError("Private input allowance exceeded")
        with archive.open("xb") as stream:
            stream.write(encoded)
        reports, outcomes, witness_blocks = [], Counter(), set()
        for case in cases:
            p, q, y = case["p"], case["qlog"], case["truth_fp32"]
            if y > 1000 or np.expm1(q[-1]) > 1000:
                result = dict(status="UNRESOLVED", reason="OUTSIDE_PREVALIDATED_NUMERIC_DOMAIN")
            else:
                result = solve(p, q, y)
            outcomes[result["status"]] += 1
            if result["status"] == "VERIFIED_WITNESS":
                witness_blocks.add(case["time_block"])
            reports.append(dict(case_sha256=case["case_sha256"], time_block=case["time_block"], **result))
        endpoint._write(output / "private_full_node_results.json", reports)
        decision = ("WITNESS_EXISTS_LOCAL_ONLY" if witness_blocks else
                    "UNRESOLVED_NO_EXTRA_SOURCE_READ" if outcomes["UNRESOLVED"] else
                    "EXCLUDE_FROZEN_DOMAIN_FOR_TEN_CASES")
        return dict(decision=decision, valid_pixels=self.valid_pixels, gate_fits=0,
                    crossings_by_time_block=dict(blocks), outcomes=dict(outcomes),
                    witness_time_blocks=len(witness_blocks), private_archive_bytes=len(encoded),
                    private_archive_sha256=sha256(encoded).hexdigest(), study_acceptance="NOT_VERIFIED")


if __name__ == "__main__":
    parent.main(kind=KIND, scope=SCOPE, budget=CAP, binder=seal, entry=__file__,
                make_summary=lambda paths: Summary(paths["case_locations"]), status=STATUS)
