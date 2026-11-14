"""Internal fixed-E9 worker called by the approval-checked paired controller."""

import hashlib
import json
import math
import os
from pathlib import Path
import tempfile
from types import SimpleNamespace


def _runtime():
    import numpy as np
    import torch
    from yuntapr.experimental.core_innovation.stage3.planning import digest
    from yuntapr.experimental.core_innovation.stage4.data import PopulationPlan, read
    from yuntapr.experimental.core_innovation.stage4.engine import seed_all, forward
    from yuntapr.experimental.core_innovation.stage4.evaluation import Evaluation
    from yuntapr.experimental.core_innovation.stage4.launch import ReaderFactory
    from yuntapr.experimental.research_readiness.dynamic_terrain import (
        model_factory, PhysicalDote, DoteDefinition,
    )
    from yuntapr.experimental.research_readiness.static_training import unpack
    from tools.research_readiness.paired_point_metrics import PointMetricAccumulator
    from tools.research_readiness.paired_joint_amplitude import StrongJointAccumulator
    return SimpleNamespace(
        torch=torch, np=np, digest=digest, PopulationPlan=PopulationPlan, read=read,
        seed_all=seed_all, forward=forward, Evaluation=Evaluation,
        ReaderFactory=ReaderFactory, model_factory=model_factory,
        PhysicalDote=PhysicalDote, DoteDefinition=DoteDefinition, unpack=unpack,
        PointMetricAccumulator=PointMetricAccumulator,
        StrongJointAccumulator=StrongJointAccumulator,
    )


def _validate_runtime(runtime, expected):
    torch = runtime.torch
    actual = {
        "torch_version": str(torch.__version__),
        "cuda_build": torch.version.cuda,
        "numpy_version": runtime.np.__version__,
        "gpu_name": torch.cuda.get_device_name(0),
        "gpu_total_bytes": torch.cuda.get_device_properties(0).total_memory,
    }
    if actual != {key: expected[key] for key in actual}:
        raise ValueError("Approved Torch/CUDA/NumPy/GPU runtime identity differs")
    return actual


def _forbid_optimizer(*args, **kwargs):
    raise PermissionError("Forward-only evaluation forbids optimizer construction")


def _initialize_runtime(output, expected):
    scratch = Path(output).resolve() / "runtime"
    scratch.mkdir(exist_ok=False)
    for name in ("TMPDIR", "TEMP", "TMP"):
        os.environ[name] = str(scratch)
    tempfile.tempdir = str(scratch)
    os.environ["TORCHINDUCTOR_CACHE_DIR"] = str(scratch / "torchinductor")
    runtime = _runtime()
    identity = _validate_runtime(runtime, expected)
    runtime.torch.set_grad_enabled(False)
    runtime.torch.optim.Optimizer.__init__ = _forbid_optimizer
    runtime.torch.set_num_threads(1)
    runtime.seed_all(2029)
    return runtime, identity


def _write(path, value):
    with Path(path).open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write("\n")


def _checkpoint_sha(path, expected_bytes, expected_sha256, check):
    digest = hashlib.sha256()
    delivered = 0
    with Path(path).open("rb") as stream:
        while chunk := stream.read(1024 * 1024):
            check()
            digest.update(chunk)
            delivered += len(chunk)
    if delivered != expected_bytes or digest.hexdigest() != expected_sha256:
        raise ValueError("Fixed E9 checkpoint identity differs")


def _gate_report(actual, reference):
    for field in ("scope", "source_identity", "population_ids_sha256", "partition_sha256"):
        if actual[field] != reference[field]:
            raise ValueError(f"Recomputed report identity differs: {field}")
    if actual["groups"].keys() != reference["groups"].keys():
        raise ValueError("Recomputed report partitions differ")
    checked = {}
    for group, saved in reference["groups"].items():
        new = actual["groups"][group]
        if new["ids_sha"] != saved["ids_sha"] or not new["complete"]:
            raise ValueError(f"Recomputed scene identity/completeness differs: {group}")
        a, b = new["summary"], saved["summary"]
        for field in ("scenes", "n_valid", "n_rain"):
            if a[field] != b[field]:
                raise ValueError(f"Recomputed {group}/{field} differs")
        if a["covered"][-1] != b["covered"][-1]:
            raise ValueError(f"Recomputed q32 covered count differs: {group}")
        for field in ("brier", "auroc", "average_precision", "conditional_pinball"):
            x, y = a[field], b[field]
            matches = x is None and y is None
            if x is not None and y is not None:
                matches = math.isfinite(x) and math.isfinite(y) and math.isclose(
                    x, y, rel_tol=1e-12, abs_tol=1e-12,
                )
            if not matches:
                raise ValueError(f"Recomputed frozen metric differs: {group}/{field}")
        if not math.isclose(a["coverage"][-1], b["coverage"][-1],
                            rel_tol=1e-12, abs_tol=1e-12):
            raise ValueError(f"Recomputed q32 coverage differs: {group}")
        checked[group] = {"identity": "PASS", "counts": "PASS", "frozen_metrics": "PASS"}
    return {"passed": True, "groups": checked, "absolute_tolerance": 1e-12,
            "relative_tolerance": 1e-12}


def run_task(root, proposal, private, task, output, check):
    """Run one approved task with one forward per batch and no optimizer restore.

    The caller binds the proposal, code/runtime, input SHA identities, live claim,
    resource limits, and ScientificReadGuard before entering this function.
    """
    check()
    matches = [row for row in proposal["models"] if row["task"] == task]
    if len(matches) != 1 or matches[0]["model"] != "B7" or matches[0]["seed"] != 2029:
        raise PermissionError("One fixed B7 seed2029 task required")
    model_identity = matches[0]
    paths = private["tasks"][task]
    output = Path(output)
    output.mkdir(exist_ok=True)
    for name in ("task_result.json", "recomputed_report.json", "point_metrics.json",
                 "joint_summary.json", "strong_joint_pixels.npz"):
        if (output / name).exists():
            raise FileExistsError("Task output already exists")

    runtime, runtime_identity = _initialize_runtime(output, proposal["runtime"])
    torch = runtime.torch
    reference = runtime.read(paths["dev_report_path"])
    if reference["groups"]["all"]["summary"] != proposal["expected_summaries"][task]:
        raise ValueError("Saved E9 report summary differs from the approved proposal")
    prepared = runtime.read(private["preparation_path"])["prepared"]
    receipt = runtime.read(private["static_receipt"])
    check()
    raw = Path(private["static_source"]).read_bytes()
    if len(raw) != 312828 or hashlib.sha256(raw).hexdigest() != proposal["static_sha256"]:
        raise ValueError("Frozen B6 static package differs")
    pack = runtime.unpack(raw, "B6", receipt)
    del raw
    inputs = prepared["private_inputs"]
    plan = runtime.PopulationPlan(inputs["stage3_run"], inputs["request"], root=Path(root))
    ids = tuple(plan.ids("Development"))
    if (plan.identity != proposal["data_identity"] or len(ids) != 963
            or any(not sid.startswith("2024-") for sid in ids)
            or runtime.digest(ids) != reference["population_ids_sha256"]):
        raise ValueError("Frozen 2024 Development population differs")
    scope = prepared["roles"]["Development"]
    if (scope["file_count"], scope["bytes_per_pass"]) != (7950, 26639253112):
        raise ValueError("Frozen Development read scope differs")
    transform = runtime.PhysicalDote(pack, runtime.DoteDefinition(**proposal["scientific_choices"]["DOTE"]))
    models = runtime.model_factory(
        pack, receipt["scalers"], modulation_limit=proposal["scientific_choices"]["modulation_limit"],
    )(2029, Path(root))
    model = models["B7"]
    del models
    _checkpoint_sha(paths["checkpoint_path"], model_identity["checkpoint_bytes"],
                    model_identity["checkpoint_sha256"], check)
    # The inherited trusted archives include NumPy RNG and optimizer-state
    # dictionaries. Only their strictly SHA-bound model state is consumed here.
    payload = torch.load(paths["checkpoint_path"], map_location="cpu", weights_only=False)
    model.load_state_dict(payload["model"], strict=True)
    del payload
    model = model.to("cuda").eval()
    analyses = tuple(plan.rows["Development"][sid]["analysis_time"] for sid in ids)
    factory = runtime.ReaderFactory(
        plan, prepared, proposal.get("decision_id", "PAIRED_POINT_FIXED_E9"),
        allowed_models=("B7",), dynamic_transform=transform,
    )
    reader = evaluator = None
    try:
        reader = factory("Development", 9, ids, output / "B7_development_09_reads")
        evaluator = runtime.Evaluation(ids, analyses, plan.identity, output / "evaluation",
                                       strong_scene_ids=plan.strong_scene_ids)
        accumulator = runtime.PointMetricAccumulator(
            ids, expected_n_valid=3303090, expected_n_rain=407820,
        )
        joint = runtime.StrongJointAccumulator(
            ids, analyses, expected_valid=3303090, expected_rain=407820,
            expected_strong=717,
            output_path=output / "strong_joint_pixels.npz", max_batch_size=8,
            check_output=check,
        )
        batches = 0
        with torch.no_grad():
            for position in range(0, len(ids), 8):
                check()
                batch = reader.batch("Development", ids[position:position + 8]).to("cuda")
                with torch.autocast("cuda", dtype=torch.bfloat16):
                    prediction, _ = runtime.forward(model, batch)
                evaluator.add(prediction, batch)
                accumulator.add(
                    batch.ids, batch.rate.detach().cpu().numpy(),
                    batch.valid.detach().cpu().numpy(), batch.region.detach().cpu().numpy(),
                    prediction.rain_prob.detach().double().cpu().numpy(),
                    prediction.conditional_quantiles_log.detach().double().cpu().numpy(),
                )
                joint.add(
                    batch.ids, batch.analyses,
                    batch.rate.detach().cpu().numpy(),
                    batch.valid.detach().cpu().numpy(),
                    batch.region.detach().cpu().numpy(),
                    prediction.rain_prob.detach().cpu().numpy(),
                    prediction.conditional_quantiles_log.detach().double().cpu().numpy(),
                )
                batches += 1
                check()
        report = evaluator.finish()
        point_metrics = accumulator.finish()
        joint_summary = joint.finish(
            arm_id=task,
            checkpoint_sha256=model_identity["checkpoint_sha256"],
            population_sha256=proposal["data_identity"]["population_sha256"],
        )
        meter_totals = reader.reader.meter.totals()
    finally:
        try:
            if evaluator is not None:
                evaluator.close()
        finally:
            if reader is not None:
                reader.close()
    check()
    gate = _gate_report(report, reference)
    if (meter_totals["opened_files"], meter_totals["delivered_bytes"],
            meter_totals["reserved_bytes"], meter_totals["states"]) != (
                7950, 26639253112, 26639253112, {"READ_COMPLETE": 7950}):
        raise RuntimeError("Exact single Development pass accounting differs")
    summary = report["groups"]["all"]["summary"]
    result = {
        "task": task, "status": "COMPLETE", "model": "B7", "seed": 2029,
        "checkpoint_sha256": model_identity["checkpoint_sha256"], "gate": gate,
        "population": {key: summary[key] for key in ("scenes", "n_valid", "n_rain")},
        "meter_totals": meter_totals, "forward_calls": batches,
        "runtime_identity": runtime_identity,
        "joint_summary": joint_summary,
        "model_inference_passes": 1, "optimizer_updates": 0,
        "scientific_status": "NOT_VERIFIED", "researcher_knowledge": "NOT_ASSESSED",
    }
    _write(output / "recomputed_report.json", report)
    _write(output / "point_metrics.json", point_metrics)
    _write(output / "joint_summary.json", joint_summary)
    check()
    _write(output / "task_result.json", result)
    return result
