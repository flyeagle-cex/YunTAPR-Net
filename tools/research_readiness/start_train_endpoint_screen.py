"""Prepare or run one fixed E9 Train-only forward pass for endpoint feasibility."""

import argparse
from collections import Counter
from datetime import date
from io import BytesIO
import os
from pathlib import Path
import shutil
import sqlite3
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / "src")]

import numpy as np

from tools.research_readiness.a20_fixed_endpoint_bounds import (
    CHECKPOINT_SHA256, THRESHOLD, pinball, strict_hit, weak_preserving_vertex,
)
from tools.research_readiness.paired_point_worker import _initialize_runtime, _write
from tools.research_readiness.start_independent_process import host_identity, require_independent
from yuntapr.experimental.core_innovation.stage3.metered_io import SourceMeter, path_key
from yuntapr.experimental.core_innovation.stage3.planning import digest
from yuntapr.experimental.core_innovation.stage4.data import read, sha
from yuntapr.experimental.core_innovation.stage4.engine import resources
from yuntapr.experimental.research_readiness.multiseed import load_inherited
from yuntapr.experimental.research_readiness.static_training import validate_approval


KIND = "BOUNDED_TRAIN_ENDPOINT_SCREEN"
SCOPE = "COSINE9_E9_2023_TRAIN_ENDPOINT_SCREEN"
LOCAL = Path("docs/research_readiness/.local")
REFERENCE = Path("docs/research_readiness/20261110_cosine9/EXECUTION_PROPOSAL.json")
TRAIN_MANIFEST = "f0c0a9188e771bfbba7c1e8a8ffdbfabd2d4e927bd1428d353b290be236a13dc"
FEATURES = ("p", "q16", "q24", "q32", "mean", "point_a", "weak_preserving_max_a")
CAP = dict(
    weather_and_supervision_bytes=26424262556, weather_and_supervision_opens=7918,
    static_bytes=312828, static_opens=1, checkpoint_bytes=53906821,
    checkpoint_source_opens=1, checkpoint_hashes=1, checkpoint_loads=1,
    total_scientific_source_bytes=26478482205, total_scientific_source_opens=7920,
    train_scenes=959, valid_pixels=3289370, strong_pixels=484, strong_scenes=159,
    forward_batches=120, batch_size=8, max_seconds=3600,
    minimum_free_bytes=8 * 1024**3, retained_table_max_bytes=256 * 1024**2,
    optimizer_updates=0, refits=0, retries=0, replay=0,
)
ENV = dict(PYTHONHASHSEED="2029", PYTHONUTF8="1", OMP_NUM_THREADS="1", MKL_NUM_THREADS="1",
           CUBLAS_WORKSPACE_CONFIG=":4096:8")


def unsigned(document):
    return {key: value for key, value in document.items() if key != "proposal_sha256"}


def seal(source_root, run, code_commit):
    old = read(source_root / LOCAL / "a20_coverage_e5_recovery_20261122_v1/PRIVATE_PREPARATION.json")
    saved = source_root / LOCAL / "cosine9_seed2029_execution_v1/B7_s2029"
    previous = read(ROOT / REFERENCE)
    inherited = Path(old["inherited"])
    if sha(inherited) != old["inherited_file_sha256"]:
        raise ValueError("Archived Train preparation identity changed")
    _, prepared = load_inherited(inherited)
    scope = prepared["roles"]["Train"]
    if (digest(unsigned(previous)) != previous["proposal_sha256"]
            or previous["data"] != prepared["data"] or scope["source_manifest_sha256"] != TRAIN_MANIFEST
            or (scope["bytes_per_pass"], scope["file_count"], len(scope["ids"])) !=
               (CAP["weather_and_supervision_bytes"], CAP["weather_and_supervision_opens"], CAP["train_scenes"])
            or any(not sid.startswith("2023-") for sid in scope["ids"])):
        raise ValueError("Only the frozen 2023 Train population may be used")
    checkpoint = saved / "B7_LAST_epoch_09.pt"
    checkpoint_receipt = read(checkpoint.with_suffix(".receipt.json"))
    if (checkpoint.stat().st_size != CAP["checkpoint_bytes"]
            or checkpoint_receipt["checkpoint_sha256"] != CHECKPOINT_SHA256
            or checkpoint_receipt["epoch"] != 9 or checkpoint_receipt["updates"] != 4320):
        raise ValueError("Frozen B7 COSINE9 E9 checkpoint metadata differs")
    static = Path(old["terrain"]) / "B6_static.npz"
    if static.stat().st_size != CAP["static_bytes"]:
        raise ValueError("Frozen static source length differs")
    terminal = source_root / LOCAL / "b_readout_prepare_20261120_v2/readout/completion.json"
    runtime = read(terminal)["result"]["runtime_identity"]
    runtime_python = read(source_root / LOCAL / "a20_coverage_e5_recovery_20261122_v1/EXECUTION_SPEC.json")["command"][0]
    paths = dict(output_root=str(run / "output"), service_dir=str(run / "service"),
                 source_root=str(source_root), inherited=str(inherited), checkpoint=str(checkpoint),
                 static=str(static), runtime_python=runtime_python)
    code = set(previous["code_sha256"]) | {
        "tools/research_readiness/start_train_endpoint_screen.py",
        "tools/research_readiness/a20_fixed_endpoint_bounds.py",
        "tools/research_readiness/paired_point_worker.py",
        "tools/research_readiness/start_independent_process.py",
    }
    plan = dict(
        status="READY_WAITING_EXACT_TRAIN_READOUT_APPROVAL", authorized=False,
        authorization_scope=SCOPE, execution_code_commit=code_commit,
        tasks=[dict(model="B7", seed=2029, checkpoint="COSINE9_FIXED_E9", role="Train", year=2023)],
        code_sha256={name: sha(ROOT / name) for name in sorted(code)},
        runtime=runtime, python_sha256=previous["runtime_binding"]["python_executable_sha256"],
        budget=CAP, data=prepared["data"], train_manifest_sha256=TRAIN_MANIFEST,
        checkpoint_sha256=CHECKPOINT_SHA256, static_sha256=previous["static_source_sha256"]["B7"],
        static_receipt_sha256=sha(static.with_name("production_receipt.json")),
        scientific_choices=dict(
            DOTE=previous["scientific_choices"]["DOTE"],
            modulation_limit=previous["scientific_choices"]["modulation_limit"],
            representation="Fixed model outputs only; p and q32 remain unchanged",
            labels="Separate offline truth category; never a deployment feature",
            retained_features=list(FEATURES), retained_rows="Strict A crossing feasible or baseline already crosses",
            time_blocks="Deidentified contiguous 14-day bins starting 2023-01-01",
            calendar_blocks_are_independent_events=False, feature_collision="Exact equality of all retained features",
            no_gate_or_threshold_fit=True, development_scientific_reads=0, final_2025_access=False,
        ),
        private_preparation_sha256=digest(paths), final_2025_access=False,
    )
    plan["proposal_sha256"] = digest(plan)
    paths["proposal_sha256"] = plan["proposal_sha256"]
    return plan, paths, prepared


class Coverage:
    def __init__(self):
        self.total = Counter()
        self.blocks = {}
        self.rows = []
        self.origin = date(2023, 1, 1)

    def add(self, ids, truth, valid, region, p, qlog):
        shape = (len(ids), 1, 100, 100)
        if (any(x.shape != shape for x in (truth, valid, region, p))
                or qlog.shape != (len(ids), 32, 100, 100) or truth.dtype != np.float32
                or valid.dtype != np.bool_ or region.dtype != np.bool_ or qlog.dtype != np.float64):
            raise ValueError("Train batch fields differ")
        for scene_id, y, v, r, prob, logs in zip(ids, truth, valid, region, p, qlog):
            block = (date.fromisoformat(scene_id[:10]) - self.origin).days // 14
            if not 0 <= block <= 26:
                raise ValueError("Only 2023 Train scenes are admitted")
            counts = self.blocks.setdefault(block, Counter())
            mask = (v & r)[0]
            if int(mask.sum()) != 3430:
                raise ValueError("Train supervision mask count differs")
            y = y[0][mask]
            prob = prob[0][mask].astype(np.float64)
            logs = logs.transpose(1, 2, 0)[mask]
            if (not all(np.isfinite(x).all() for x in (y, prob, logs)) or (y < 0).any()
                    or ((prob < 0) | (prob > 1)).any() or (np.diff(logs, axis=1) <= 0).any()):
                raise ValueError("Invalid supervised prediction or truth")
            with np.errstate(over="raise", invalid="raise"):
                nodes = np.expm1(logs)
                mean = nodes.mean(axis=1)
                actual = (prob * mean).astype(np.float32)
                ceiling = (prob * nodes[:, -1]).astype(np.float32)
            strong = y > THRESHOLD
            counts.update(scenes=1, valid=len(y), strong=int(strong.sum()), strong_scenes=int(strong.any()),
                          baseline_tp=int(((actual > THRESHOLD) & strong).sum()),
                          baseline_fp=int(((actual > THRESHOLD) & ~strong).sum()))
            for index in np.flatnonzero(ceiling > THRESHOLD):
                vertex = weak_preserving_vertex(logs[index])
                maximum = float(np.float32(prob[index] * np.expm1(vertex).mean()))
                if maximum <= THRESHOLD:
                    continue
                existing = bool(actual[index] > THRESHOLD)
                witness = None if existing else strict_hit(float(prob[index]), logs[index], vertex)
                if not existing and witness is None:
                    raise ArithmeticError("Reachable endpoint lacks a strict witness")
                label = int(strong[index])
                counts["reachable_strong" if label else "reachable_nonstrong"] += 1
                if not existing:
                    counts["new_strong" if label else "new_nonstrong"] += 1
                    if label:
                        change = pinball((y[index] - np.expm1(witness)) / 20) - pinball((y[index] - nodes[index]) / 20)
                        counts["new_strong_with_own_physical_improvement"] += int(change < 0)
                self.rows.append((block, label, int(existing), float(prob[index]), float(nodes[index, 15]),
                                  float(nodes[index, 23]), float(nodes[index, -1]), float(mean[index]),
                                  float(actual[index]), maximum))

    def finish(self, output):
        for counts in self.blocks.values():
            self.total.update(counts)
        for key, limit in (("scenes", "train_scenes"), ("valid", "valid_pixels"),
                           ("strong", "strong_pixels"), ("strong_scenes", "strong_scenes")):
            if self.total[key] != CAP[limit]:
                raise RuntimeError("Frozen Train population coverage differs")
        rows = np.asarray(self.rows, dtype=np.float64).reshape(-1, 3 + len(FEATURES))
        groups = {}
        for row in rows:
            groups.setdefault(tuple(row[3:]), set()).add(int(row[1]))
        new_strong_blocks = sum(c["new_strong"] > 0 for c in self.blocks.values())
        mixed = sum(len(labels) > 1 for labels in groups.values())
        if rows.nbytes + 4096 > CAP["retained_table_max_bytes"]:
            raise RuntimeError("Retained table exceeds the fixed output allowance")
        with (output / "reachable_features.npz").open("xb") as stream:
            np.savez(stream, block=rows[:, 0].astype(np.int16), strong=rows[:, 1].astype(bool),
                     baseline_hit=rows[:, 2].astype(bool), features=rows[:, 3:])
        if new_strong_blocks == 0:
            decision = "NO_NEW_REACHABLE_STRONG_TRAIN_EXAMPLES"
        elif new_strong_blocks == 1:
            decision = "REACHABLE_SUPPORT_IN_ONLY_ONE_TIME_BLOCK"
        else:
            decision = "SUPPORT_EXISTS_TEST_FIXED_BLOCKED_GATE_SEPARATELY"
        return dict(decision=decision, counts=dict(self.total), new_strong_time_blocks=new_strong_blocks,
                    counts_by_time_block={str(k): dict(v) for k, v in sorted(self.blocks.items())},
                    mixed_label_feature_groups=mixed, feature_columns=FEATURES, gate_fits=0)


def recheck(plan, private, approval, expected_commit):
    if approval.get("authorization_scope") != SCOPE:
        raise PermissionError("Separate Train-only approval required")
    validate_approval(approval, plan, private, expected_commit)
    if (plan["authorization_scope"] != SCOPE or plan["budget"] != CAP or plan["final_2025_access"]
            or plan["proposal_sha256"] != digest(unsigned(plan))
            or private["proposal_sha256"] != plan["proposal_sha256"]
            or digest(unsigned(private)) != plan["private_preparation_sha256"]
            or any(sha(ROOT / name) != value for name, value in plan["code_sha256"].items())):
        raise PermissionError("Pinned Train-only approval or code differs")


def execute(plan, private, approval):
    start = time.monotonic()
    require_independent(host_identity())
    recheck(plan, private, approval, plan["execution_code_commit"])
    service = Path(private["service_dir"])
    launch, claim = (read(service / f) for f in ("target_launch.json", "independent_launch_claim.json"))
    if ((launch["pid"], launch["supervisor_pid"]) != (os.getpid(), os.getppid())
            or launch["kind"] != KIND or launch["automatic_retry"] is not False
            or claim["automatic_retry"] is not False or launch["spec_sha256"] != claim["spec_sha256"]
            or sha(sys.executable) != plan["python_sha256"]
            or any(os.environ.get(key) != value for key, value in ENV.items())):
        raise PermissionError("A live once-only Train supervisor and pinned runtime are required")
    output = Path(private["output_root"])
    if shutil.disk_usage(output.parent).free < CAP["minimum_free_bytes"]:
        raise RuntimeError("Insufficient workspace space for Train diagnostic")
    run = output.parent
    parent_proposal, binding, prepared = seal(Path(private["source_root"]), run, plan["execution_code_commit"])
    if parent_proposal != plan or binding != private:
        raise PermissionError("Train source binding changed after preparation")
    output.mkdir(exist_ok=False)

    def deadline():
        if time.monotonic() - start >= CAP["max_seconds"]:
            raise TimeoutError("Train screen deadline reached")

    try:
        runtime, runtime_identity = _initialize_runtime(output, plan["runtime"])
        torch = runtime.torch
        resources(backward=False)
        deadline()
        inputs = prepared["private_inputs"]
        population = runtime.PopulationPlan(inputs["stage3_run"], inputs["request"], root=ROOT)
        ids = tuple(population.ids("Train"))
        if population.identity != plan["data"] or ids != tuple(prepared["roles"]["Train"]["ids"]):
            raise ValueError("Train population or ordering differs")
        static = Path(private["static"])
        checkpoint = Path(private["checkpoint"])
        receipt = read(static.with_name("production_receipt.json"))
        # Account for both remaining scientific files independently of the weather reader.
        with sqlite3.connect(output / "fixed_sources.sqlite") as ledger:
            ledger.execute("CREATE TABLE jobs(id TEXT PRIMARY KEY,state TEXT)")
            ledger.execute("INSERT INTO jobs VALUES ('fixed','PENDING')")
            meter = SourceMeter(ledger, {
                str(static): dict(bytes=CAP["static_bytes"], sha=plan["static_sha256"], job_id="fixed"),
                str(checkpoint): dict(bytes=CAP["checkpoint_bytes"], sha=plan["checkpoint_sha256"], job_id="fixed"),
            }, max_files=2, max_bytes=CAP["static_bytes"] + CAP["checkpoint_bytes"])
            meter.active = {path_key(static), path_key(checkpoint)}
            with meter.open(static, "rb") as stream:
                raw = stream.read()
            pack = runtime.unpack(raw, "B6", receipt)
            with meter.open(checkpoint, "rb") as stream:
                raw = stream.read()
            # SourceMeter verified size and SHA on close. Load that same buffer.
            fixed = meter.totals()
            fixed_bytes = CAP["static_bytes"] + CAP["checkpoint_bytes"]
            if fixed != dict(opened_files=2, delivered_bytes=fixed_bytes, reserved_bytes=fixed_bytes,
                             states={"READ_COMPLETE": 2}):
                raise RuntimeError("Fixed-source ledger differs")
            with BytesIO(raw) as memory:
                state = torch.load(memory, map_location="cpu", weights_only=False)["model"]
            del raw
            ledger.execute("UPDATE jobs SET state='COMPLETE'")
        model = runtime.model_factory(pack, receipt["scalers"], modulation_limit=plan["scientific_choices"]["modulation_limit"])(2029, ROOT)["B7"]
        model.load_state_dict(state, strict=True)
        del state
        model = model.to("cuda").eval()
        transform = runtime.PhysicalDote(pack, runtime.DoteDefinition(**plan["scientific_choices"]["DOTE"]))
        factory = runtime.ReaderFactory(population, prepared, approval["decision_id"],
                                        allowed_models=("B7",), dynamic_transform=transform)
        summary = Coverage()
        reader = factory("Train", 9, ids, output / "B7_train_09_reads")
        batches = 0
        try:
            with torch.no_grad():
                for position in range(0, len(ids), CAP["batch_size"]):
                    deadline()
                    batch = reader.batch("Train", ids[position:position + CAP["batch_size"]]).to("cuda")
                    if batch.role != "Train" or batch.identity != plan["data"]:
                        raise ValueError("Unexpected role or train batch identity")
                    with torch.autocast("cuda", dtype=torch.bfloat16):
                        result, _ = runtime.forward(model, batch)
                    summary.add(batch.ids, batch.rate.cpu().numpy(), batch.valid.cpu().numpy(),
                                batch.region.cpu().numpy(), result.rain_prob.double().cpu().numpy(),
                                result.conditional_quantiles_log.cpu().numpy())
                    batches += 1
        finally:
            reader.close()
        deadline()
        if batches != CAP["forward_batches"]:
            raise RuntimeError("Train-pass forward count differs")
        stats = summary.finish(output)
        weather = read(output / "B7_train_09_reads/pass_receipt.json")["actual_reads"]
        _write(output / "completion.json", dict(status="COMPLETE_TRAIN_ENDPOINT_SCREEN", **stats,
                                               proposal_sha256=plan["proposal_sha256"], runtime=runtime_identity,
                                               forward_batches=batches, fixed_source_reads=fixed, train_reads=weather,
                                               optimizer_updates=0, final_2025_access=False))
    except BaseException as exc:
        _write(output / "failure.json", dict(status="STOP_NO_RETRY", error_type=type(exc).__name__, details=str(exc)))
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="mode", required=True)
    prep, run = sub.add_parser("prepare"), sub.add_parser("execute")
    for command in (prep, run):
        command.add_argument("--proposal", required=True, type=Path)
        command.add_argument("--private-preparation", required=True, type=Path)
    prep.add_argument("--source-root", required=True, type=Path)
    prep.add_argument("--code-commit", required=True)
    run.add_argument("--researcher-approval", required=True, type=Path)
    args = parser.parse_args()
    if args.mode == "prepare":
        source = args.source_root.resolve()
        namespace = args.private_preparation.resolve().parent
        if (namespace.parent != (source / LOCAL).resolve() or namespace.exists() or args.proposal.exists()):
            raise ValueError("Use a fresh private namespace and proposal")
        plan, paths, _ = seal(source, namespace, args.code_commit)
        service = namespace / "service"
        service.mkdir(parents=True, exist_ok=False)
        _write(args.proposal, plan)
        _write(args.private_preparation, paths)
        _write(namespace / "EXECUTION_SPEC.json", dict(
            kind=KIND, cwd=str(ROOT), service_dir=str(service), environment=ENV,
            command=[paths["runtime_python"], "-B", str(Path(__file__).resolve()), "execute",
                     "--proposal", str(args.proposal.resolve()), "--private-preparation", str(args.private_preparation.resolve()),
                     "--researcher-approval", str(namespace / "RESEARCHER_APPROVAL.json")]))
        print(plan["proposal_sha256"])
    else:
        if not args.researcher_approval.is_file():
            raise PermissionError("Separate exact Train-only researcher approval required")
        execute(read(args.proposal), read(args.private_preparation), read(args.researcher_approval))


if __name__ == "__main__":
    main()
