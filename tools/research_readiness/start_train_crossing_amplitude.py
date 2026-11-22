"""Prepare one bounded pass over original Train batches for an amplitude diagnostic."""

import argparse
from collections import Counter
import csv
from datetime import date
from pathlib import Path
import sys
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / "src")]

import numpy as np

from tools.research_readiness import start_train_endpoint_screen as endpoint
from tools.research_readiness.a20_crossing_amplitude import crossing_amplitude
from tools.research_readiness.a20_fixed_endpoint_bounds import point
from yuntapr.experimental.core_innovation.stage4.launch import source_scope


KIND = "BOUNDED_TRAIN_CROSSING_AMPLITUDE"
SCOPE = "COSINE9_E9_2023_TRAIN_CROSSING_AMPLITUDE"
STATUS = "COMPLETE_TRAIN_CROSSING_AMPLITUDE"
DOCS = Path("docs/research_readiness/20261121_a20_negative_coverage")
QC = Path("docs/b0_pretraining_closure/runs/run_20260930T095416Z/formal_sample_eligibility_2023_2024.csv")
PARENT = "12d263de2baf99dca6b3216d4d05c6583c36e3565a555eae8c6bb063bfb11c3b"
TERMINAL_SHA = "d6faa0ecb5115c9c6c796bf3e52ff0fb37547d44525ca063b48bf6bb687d2dc2"
COUNTS = {11: 2, 13: 4, 15: 1, 16: 1, 18: 2}
TOLERANCE = 1e-10
MAX_INTERVALS = 4095
CAP = dict(
    **{k: endpoint.CAP[k] for k in ("static_bytes", "static_opens", "checkpoint_bytes",
                                  "checkpoint_source_opens", "checkpoint_hashes", "checkpoint_loads",
                                  "minimum_free_bytes", "batch_size", "optimizer_updates",
                                  "refits", "retries", "replay")},
    weather_and_supervision_bytes=7475570491, weather_and_supervision_opens=2117,
    total_scientific_source_bytes=7529790140, total_scientific_source_opens=2119,
    train_scenes=256, forward_batches=32, positive_scenes=86, crossing_cases=10,
    max_intervals_per_case=MAX_INTERVALS, max_seconds=1200,
)


def block_id(sid):
    return (date.fromisoformat(sid[:10]) - date(2023, 1, 1)).days // 14


def choose_batches(ids, strong):
    batches = [ids[i:i + CAP["batch_size"]] for i in range(0, len(ids), CAP["batch_size"])]
    return tuple(batch for batch in batches if strong.intersection(batch))


def restrict_scope(population, original, subset):
    mask, = ((path, item) for path, item in original.items() if item["kind"] == "static_mask")
    dates = {date.fromisoformat(Path(path).stem[-8:]).isoformat(): item["bytes"]
             for path, item in original.items() if item["kind"] == "IMERG"}
    restricted = SimpleNamespace(
        rows={"Train": {sid: population.rows["Train"][sid] for sid in subset}},
        ids=lambda role: subset, sat=population.sat, gfs=population.gfs, sources=population.sources,
    )
    bounds = source_scope(restricted, "Train", dates, mask)
    if any(original.get(path) != item for path, item in bounds["files"].items()):
        raise ValueError("One or more sources fall outside the frozen Train scope")
    return bounds


def seal(source_root, run, commit):
    plan, paths, prepared = endpoint.seal(source_root, run, commit)
    previous = endpoint.read(ROOT / DOCS / "A20_TRAIN_ENDPOINT_SCREEN_PROPOSAL.json")
    terminal_path = source_root / endpoint.LOCAL / "a20_train_endpoint_screen_20261122_v1/output/completion.json"
    if (previous["proposal_sha256"] != PARENT or endpoint.digest(endpoint.unsigned(previous)) != PARENT
            or endpoint.sha(terminal_path) != TERMINAL_SHA):
        raise ValueError("Frozen parent Train diagnostic changed")
    terminal = endpoint.read(terminal_path)
    expected = {int(k): v["new_strong"] for k, v in terminal["counts_by_time_block"].items() if v.get("new_strong")}
    if (terminal["proposal_sha256"] != PARENT or terminal["status"] != "COMPLETE_TRAIN_ENDPOINT_SCREEN"
            or expected != COUNTS or terminal["counts"]["baseline_tp"] != 0):
        raise ValueError("Frozen parent crossing coverage changed")
    changed = {"tools/research_readiness/start_train_endpoint_screen.py",
               "tools/research_readiness/start_independent_process.py"}
    for name, digest in previous["code_sha256"].items():
        if name not in changed and plan["code_sha256"].get(name) != digest:
            raise ValueError(f"Train inference dependency changed: {name}")
    for name in ("data", "runtime", "python_sha256", "checkpoint_sha256", "static_sha256", "static_receipt_sha256"):
        if plan[name] != previous[name]:
            raise ValueError(f"Parent detector identity changed: {name}")

    from yuntapr.experimental.core_innovation.stage4.data import PopulationPlan
    inputs = prepared["private_inputs"]
    population = PopulationPlan(inputs["stage3_run"], inputs["request"], root=ROOT)
    ids = tuple(population.ids("Train"))
    full = prepared["roles"]["Train"]
    qc = ROOT / QC
    if ids != tuple(full["ids"]) or population.identity != plan["data"] or endpoint.sha(qc) != plan["data"]["target_QC_sha256"]:
        raise ValueError("Frozen Train membership, batch order or label QC changed")
    with qc.open(encoding="utf-8-sig", newline="") as stream:
        strong = {row["window_start"] for row in csv.DictReader(stream)
                  if row["window_start"] in population.rows["Train"] and float(row["imerg_max_yunnan_mmhr"] or 0) > 20}
    selected = frozenset(sid for sid in strong if block_id(sid) in COUNTS)
    batches = choose_batches(ids, selected)
    subset = tuple(sid for batch in batches for sid in batch)
    if (len(strong) != endpoint.CAP["strong_scenes"] or len(selected) != CAP["positive_scenes"]
            or len(batches) != CAP["forward_batches"] or any(len(batch) != CAP["batch_size"] for batch in batches)
            or len(subset) != CAP["train_scenes"]):
        raise ValueError("The exact 32 original batches are required")
    bounds = restrict_scope(population, full["files"], subset)
    if (bounds["bytes_per_pass"], bounds["file_count"]) != (
            CAP["weather_and_supervision_bytes"], CAP["weather_and_supervision_opens"]):
        raise ValueError("The Train subset source identity or allowance differs")

    plan = endpoint.unsigned(plan)
    paths = endpoint.unsigned(paths)
    plan.update(authorization_scope=SCOPE, budget=CAP, parent_proposal_sha256=PARENT,
                parent_terminal_sha256=TERMINAL_SHA, original_batch_order_sha256=endpoint.digest(batches),
                train_manifest_sha256=bounds["source_manifest_sha256"],
                scientific_source_kinds=bounds["by_kind"])
    for name in ("a20_crossing_amplitude.py", Path(__file__).name):
        relative = "tools/research_readiness/" + name
        plan["code_sha256"][relative] = endpoint.sha(ROOT / relative)
    plan["scientific_choices"] = dict(
        DOTE=plan["scientific_choices"]["DOTE"],
        modulation_limit=plan["scientific_choices"]["modulation_limit"],
        geometry="Single original-to-maximum-A weak-loss-preserving line, fixed p and q32",
        parent_positive_crossings_by_block={str(k): v for k, v in COUNTS.items()},
        strict_f32_point_threshold_mm_h=20, pinball_decrease_tolerance=TOLERANCE,
        no_gate_fit=True, retain_individual_arrays=False, development_scientific_reads=0,
        final_2025_access=False,
    )
    paths["selected_strong_scenes"] = sorted(selected)
    plan["private_preparation_sha256"] = endpoint.digest(paths)
    plan["proposal_sha256"] = endpoint.digest(plan)
    paths["proposal_sha256"] = plan["proposal_sha256"]
    prepared = dict(prepared, roles={"Train": bounds})
    return plan, paths, prepared


class Summary:
    def __init__(self, selected):
        self.expected_scenes = frozenset(selected)
        self.strong_scenes = set()
        self.crossings = Counter()
        self.outcomes = Counter()
        self.cases = []
        self.best_delta = None
        self.valid_pixels = 0

    def add(self, ids, truth, valid, region, probability, qlog):
        shape = (len(ids), 1, 100, 100)
        if (any(x.shape != shape for x in (truth, valid, region, probability))
                or qlog.shape != (len(ids), 32, 100, 100) or truth.dtype != np.float32
                or valid.dtype != np.bool_ or region.dtype != np.bool_ or qlog.dtype != np.float64):
            raise ValueError("Train amplitude batch representation differs")
        for sid, y, mask, p, q in zip(ids, truth[:, 0], (valid & region)[:, 0], probability[:, 0], qlog):
            if int(mask.sum()) != 3430:
                raise ValueError("Frozen supervision mask differs")
            self.valid_pixels += 3430
            if block_id(sid) not in COUNTS:
                continue
            strong = mask & (y > 20)
            if bool(strong.any()) != (sid in self.expected_scenes):
                raise ValueError("Strong scene and frozen target QC disagree")
            if not strong.any():
                continue
            self.strong_scenes.add(sid)
            with np.errstate(over="raise", invalid="raise"):
                possible = strong & ((p * np.expm1(q[-1])).astype(np.float32) > 20)
            for row, column in np.argwhere(possible):
                log_nodes = q[:, row, column]
                prob = float(p[row, column])
                vertex = endpoint.weak_preserving_vertex(log_nodes)
                if point(prob, vertex) <= 20:
                    continue
                block = block_id(sid)
                if self.crossings[block] >= COUNTS[block]:
                    raise ValueError("More crossing cases than allowed by the frozen parent")
                result = crossing_amplitude(prob, log_nodes, float(y[row, column]),
                                            tolerance=TOLERANCE, max_intervals=MAX_INTERVALS, vertex=vertex)
                status = result["status"]
                if status not in {"AMPLITUDE_WITNESS", "NO_GAIN_BEYOND_TOLERANCE", "UNRESOLVED"}:
                    raise ValueError("Unexpected classification for an admitted crossing")
                self.crossings[block] += 1
                self.outcomes[status] += 1
                self.cases.append(dict(case_sha256=endpoint.digest([sid, int(row), int(column)]),
                                       time_block=block, **result))
                if status == "AMPLITUDE_WITNESS":
                    value = result["physical_pinball_delta"]
                    self.best_delta = value if self.best_delta is None else min(value, self.best_delta)

    def finish(self, output):
        if (self.valid_pixels != CAP["train_scenes"] * 3430 or self.strong_scenes != self.expected_scenes
                or self.crossings != COUNTS):
            raise ValueError("Expected ten parent crossings across five time blocks")
        decision = ("WITNESS_EXISTS_NO_GATE_ADMISSION" if self.outcomes["AMPLITUDE_WITNESS"] else
                    "UNRESOLVED_KEEP_ROUTE_PENDING" if self.outcomes["UNRESOLVED"] else
                    "CLOSE_THIS_LINE_AT_FIXED_TOLERANCE")
        endpoint._write(output / "private_cases.json", self.cases)
        return dict(decision=decision, valid_pixels=self.valid_pixels, gate_fits=0,
                    crossings_by_time_block=dict(self.crossings), outcomes=dict(self.outcomes),
                    best_witness_delta=self.best_delta, study_acceptance="NOT_VERIFIED")


def main(*, kind=KIND, scope=SCOPE, budget=CAP, binder=seal, entry=__file__,
         make_summary=lambda paths: Summary(paths["selected_strong_scenes"]), status=STATUS):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="mode", required=True)
    prep = sub.add_parser("prepare")
    run = sub.add_parser("execute")
    for command in (prep, run):
        command.add_argument("--proposal", required=True, type=Path)
        command.add_argument("--private-preparation", required=True, type=Path)
    prep.add_argument("--source-root", required=True, type=Path)
    prep.add_argument("--code-commit", required=True)
    run.add_argument("--researcher-approval", required=True, type=Path)
    args = parser.parse_args()
    if args.mode == "execute":
        if not args.researcher_approval.is_file():
            raise PermissionError("Separate exact Train amplitude approval required")
        plan, paths, grant = map(endpoint.read, (args.proposal, args.private_preparation, args.researcher_approval))
        endpoint.execute(plan, paths, grant, scope=scope, budget=budget, kind=kind, binder=binder,
                         summary_factory=lambda: make_summary(paths), complete_status=status)
        return
    source = args.source_root.resolve()
    namespace = args.private_preparation.resolve().parent
    if namespace.parent != (source / endpoint.LOCAL).resolve() or namespace.exists() or args.proposal.exists():
        raise ValueError("A fresh private namespace and proposal are required")
    plan, paths, _ = binder(source, namespace, args.code_commit)
    service = namespace / "service"
    service.mkdir(parents=True, exist_ok=False)
    endpoint._write(args.proposal, plan)
    endpoint._write(args.private_preparation, paths)
    endpoint._write(namespace / "EXECUTION_SPEC.json", dict(
        kind=kind, cwd=str(ROOT), service_dir=str(service), environment=endpoint.ENV,
        command=[paths["runtime_python"], "-B", str(Path(entry).resolve()), "execute",
                 "--proposal", str(args.proposal.resolve()), "--private-preparation", str(args.private_preparation.resolve()),
                 "--researcher-approval", str(namespace / "RESEARCHER_APPROVAL.json")]))
    print(plan["proposal_sha256"])


if __name__ == "__main__":
    main()
