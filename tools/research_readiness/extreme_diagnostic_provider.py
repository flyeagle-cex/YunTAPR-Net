"""Post-approval bridge to the pinned, already gate-verified inference provider.

No original provider/model/loss file is edited. Every original forward is called
exactly once and its original output object is returned to the frozen evaluator.
"""
from datetime import datetime, timezone
import io
import os
from pathlib import Path
import sys

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from tools.research_readiness.extreme_diagnostic_export import JointCollector, write_new


def array(tensor):
    return tensor.detach().cpu().numpy()


def stamp(value):
    return datetime.fromisoformat(str(value).replace("Z", "+00:00")).astimezone(timezone.utc).isoformat()


def attach_provider(engine, collector_factory, context_factory, check):
    """A narrow injectable seam, also exercised with a synthetic provider."""
    for family in ("b3b4", "b7b8"):
        original = engine.FAMILY_ADAPTERS[family]

        class SidecarAdapter(original):
            def __init__(self, *args, **kwargs):
                super().__init__(*args, **kwargs)
                self._joint_collector = collector_factory(self)
                self._joint_context = context_factory(self)

            def forward(self, item):
                check()
                out = super().forward(item)
                self._joint_collector.add(item["ids"], item["batch"].analyses,
                    array(item["rate"]), array(item["valid"]), array(item["region"]),
                    out.rain_prob.detach().float().cpu().numpy(), array(out.conditional_quantiles_log),
                    context=self._joint_context(item))
                check()
                return out

        engine.FAMILY_ADAPTERS[family] = SidecarAdapter


class PhysicalContext:
    """Observe the same decoded frame without rereading meteorological inputs."""
    def __init__(self, adapter, check):
        self.adapter, self.check = adapter, check
        self.frames = {}
        original = adapter.transform
        parent = self

        class CapturedTransform:
            def __call__(self, frame):
                parent.check()
                values, valid = original(frame)  # Exact original model input.
                from yuntapr.experimental.core_innovation.gfs import EnvironmentFrame, _above_ground
                native = EnvironmentFrame(frame.identity, frame.grid, _above_ground(frame.fields), frame.mode, frame.provenance)
                mapped = native if frame.grid.identity == adapter.model.grid.identity else native.on_grid(adapter.model.grid, operator="bilinear_point_candidate")
                water = mapped.fields["pwat"]
                parent.frames[stamp(frame.identity.valid)] = (
                    np.where(water.valid, water.values, 0.).astype(np.float64), water.valid.copy())
                return values, valid

        adapter.transform = CapturedTransform()

    def __call__(self, item):
        adapter, batch = self.adapter, item["batch"]
        waters, masks = [], []
        for analysis in batch.analyses:
            water, valid = self.frames.pop(stamp(analysis))
            waters.append(water[None]); masks.append(valid[None])
        n, shape = len(batch.ids), adapter.pack.grid.shape
        elevation = np.where(adapter.pack.valid[0], adapter.pack.values[0], 0.)
        return dict(elevation_m=np.broadcast_to(elevation[None, None], (n, 1, *shape)),
                    dynamic_values=array(batch.dynamic), dynamic_valid=array(batch.dynamic_valid),
                    pwat_kg_m2=np.stack(waters), pwat_valid=np.stack(masks))


def run_model(engine, run, output, package, check, static_source, static_sha256, file_sha):
    import torch
    torch.set_num_threads(1)
    torch.set_grad_enabled(False)
    def forbidden(*args, **kwargs):
        raise PermissionError("Diagnostic workers cannot construct an optimizer")
    torch.optim.Optimizer.__init__ = forbidden
    engine.BATCH_SIZE = 8
    engine.OUTPUT_ROOT = str(output / "frozen")
    engine.LOG_ROOT = str(output / "logs")
    # All three original B78 constructors read exactly this same static pack.
    original_open = open
    def provider_open(path, mode="r", *args, **kwargs):
        if os.path.normcase(os.path.abspath(path)) == os.path.normcase(os.path.abspath(static_source)):
            if mode != "rb":
                raise PermissionError("Static source is read-only")
            import hashlib
            with original_open(path, mode) as stream:
                raw = stream.read()
            if hashlib.sha256(raw).hexdigest() != static_sha256:
                raise ValueError("Static bytes differ from the inherited accepted source")
            return io.BytesIO(raw)
        return original_open(path, mode, *args, **kwargs)
    engine.open = provider_open
    collectors = []
    reference = package / "B7_s2029/joint"
    def new_collector(adapter):
        folder = output / "joint"
        collector = JointCollector(folder, adapter.ids, adapter.analyses,
                    point_function=engine.point_candidates_log, check_limits=check,
                    reference_context=reference if run["model"] == "B4" else None)
        collectors.append(collector)
        return collector
    def new_context(adapter):
        if run["model"] == "B4":
            return lambda item: None
        return PhysicalContext(adapter, check.deadline.remaining)
    attach_provider(engine, new_collector, new_context, check.deadline.remaining)
    result = engine.run_one(run["run_id"], verify_sha=True)
    if result["status"] != "COMPLETE" or result["gate"].get("passed") is not True:
        raise RuntimeError("Frozen original-metric gate failed; retain partial export and stop")
    scope = result["read_scope_actual"]["meter_totals"]
    if (scope["opened_files"] != 7950 or scope["delivered_bytes"] != 26639253112
            or scope["reserved_bytes"] != 26639253112
            or scope["states"] != {"READ_COMPLETE": 7950}):
        raise RuntimeError("Frozen one-pass weather accounting differs")
    if len(collectors) != 1:
        raise RuntimeError("Exactly one joint collector required")
    joint = collectors[0].finish()
    if (joint["scenes"], joint["n_valid"], joint["n_rain"]) != (963, 3303090, 407820):
        raise RuntimeError("Joint export population differs from the frozen evaluator")
    record = dict(status="COMPLETE_FROZEN_GATE_AND_JOINT_EXPORT", run_id=run["run_id"],
                  checkpoint_sha256=run["checkpoint_sha256"], original_gate=result["gate"],
                  frozen_result_sha256=file_sha(output / "frozen" / run["run_id"] / "result.json"),
                  joint_summary_sha256=file_sha(output / "joint/joint_summary.json"),
                  source_accounting=scope, new_inference_passes=1, optimizer_updates=0,
                  final_2025="FROZEN_NO_ACCESS")
    write_new(output / "verified.json", record)
    return record


def run_train_labels(run, files, output, check):
    """One shared label/mask pass; no satellite, GFS, model or optimizer."""
    sys.path.insert(0, str(Path(run["code_root"]) / "src"))
    import sqlite3
    import netCDF4
    from yuntapr.experimental.core_innovation.stage4.data import PopulationPlan, read, target_memory
    from yuntapr.experimental.core_innovation.stage3.metered_io import SourceMeter, path_key
    from yuntapr.spatial.sp04_mapping import load_sp04
    prepared = read(run["private_preparation"]["path"])["prepared"]
    inputs = prepared["private_inputs"]
    plan = PopulationPlan(inputs["stage3_run"], inputs["request"], root=run["code_root"])
    mapping = load_sp04(plan.root)
    ids = tuple(plan.ids("Train"))
    if len(ids) != 959 or any(not s.startswith("2023-") for s in ids):
        raise PermissionError("Only the exact 2023 Train population")
    db = sqlite3.connect(output / "label_reads.sqlite")
    db.execute("CREATE TABLE jobs(id TEXT PRIMARY KEY,state TEXT)")
    bound = {path: dict(info, job_id=str(i)) for i, (path, info) in enumerate(files.items())}
    db.executemany("INSERT INTO jobs VALUES (?, 'PENDING')", [(info["job_id"],) for info in bound.values()]); db.commit()
    meter = SourceMeter(db, bound, max_files=246, max_bytes=180049094)
    meter.install()
    positive, occurrence_positive = [], []
    counts = {str(r): 0 for r in (.1, 5., 10., 20., 50.)}
    n_valid = 0; visited = []
    def get(path):
        check(); meter.active = {path_key(path)}
        try:
            with meter.open(path, "rb") as stream: raw = stream.read()
        finally:
            meter.active = set()
        with db: db.execute("UPDATE jobs SET state='COMPLETE' WHERE id=?", (bound[path]["job_id"],))
        return raw
    try:
        mask_path = next(path for path, info in files.items() if info["kind"] == "static_mask")
        with netCDF4.Dataset("diagnostic_train_mask.nc", memory=get(mask_path)) as ds:
            region = np.asarray(ds["yunnan_mask"][:], dtype=bool)[10:110, 20:120]
            mapping.assert_axes(mapping.axes["native_lat"], mapping.axes["native_lon"], ds["lat"][10:110], ds["lon"][20:120])
        if region.shape != (100, 100) or int(region.sum()) != 3430:
            raise ValueError("Training label reference mask changed")
        days = {Path(path).stem.removeprefix("imerg_"): path for path, info in files.items() if info["kind"] != "static_mask"}
        by_day = {}
        for sid in ids:
            by_day.setdefault(sid[:10].replace("-", ""), []).append(sid)
        if set(days) != set(by_day):
            raise ValueError("Shared label manifest does not match all 959 scenes")
        for day, members in by_day.items():
            raw = get(days[day])
            for sid in members:
                check()
                y, valid = target_memory(raw, int(plan.rows["Train"][sid]["imerg_index"]), mapping, sid)
                values = y[valid & region].astype(np.float32)
                if values.size != 3430 or not np.isfinite(values).all() or (values < 0).any():
                    raise ValueError("Training reference label/QC count changed")
                positive.append(values[values > np.float32(0)])
                occurrence_positive.append(values[values > np.float32(.1)])
                for threshold in counts: counts[threshold] += int((values > np.float32(float(threshold))).sum())
                n_valid += int(values.size); visited.append(sid)
            del raw
        if set(visited) != set(ids) or len(visited) != len(ids):
            raise ValueError("Duplicate or omitted training reference scene")
        positive, occurrence_positive = np.concatenate(positive), np.concatenate(occurrence_positive)
        if (n_valid, positive.size, occurrence_positive.size) != (3289370, 388020, 345725):
            raise ValueError("Inherited 2023 label reference counts failed; do not refit scope")
        actual = meter.totals()
        if actual["delivered_bytes"] != 180049094 or actual["opened_files"] != 246 or actual["states"] != {"READ_COMPLETE": 246}:
            raise ValueError("Shared training-label one-pass accounting changed")
        result = dict(status="COMPLETE_SHARED_2023_LABEL_REFERENCE", scenes=959, n_valid=n_valid,
                      positive_R_gt0=int(positive.size), occurrence_R_gt0_1=int(occurrence_positive.size),
                      quantile_method="linear", P95_P99_R_gt0=np.quantile(positive, [.95, .99], method="linear").tolist(),
                      P95_P99_R_gt0_1_sensitivity=np.quantile(occurrence_positive, [.95, .99], method="linear").tolist(),
                      exceedance_counts=counts, climatology={r: n / n_valid for r, n in counts.items()},
                      source_accounting=actual, model_loads=0, optimizer_updates=0, final_2025="FROZEN_NO_ACCESS")
        write_new(output / "verified.json", result)
        return result
    finally:
        meter.uninstall(); db.close()
