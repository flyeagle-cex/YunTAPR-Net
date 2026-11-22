"""One approved, bounded Development readout with no model inference."""

import argparse
from collections import Counter
from datetime import datetime, timedelta
from hashlib import sha256
from io import BytesIO
import json
import math
import os
from pathlib import Path
import subprocess
import sys
import time

import numpy as np

from tools.research_readiness.orographic_separability import rainfall_counts, summarize
from tools.research_readiness.orographic_source_binding import _digest


ROOT = Path(__file__).resolve().parents[2]
DOCS = ROOT / "docs/research_readiness/20261121_stage45_observation_feasibility"
RUN = ROOT / "docs/research_readiness/.local/orographic_separability_execution_v1"
ALLOWLIST = RUN.with_name("orographic_separability_source_v1.json")
SCOPE = "OROGRAPHIC_SEPARABILITY_V1_DEV_READOUT"
COUNTS = (3303090, 717, 160, 5769)
MAX_SECONDS = 600
MIN_MATCHED = (80, 10)


def build_proposal():
    bound = _json(DOCS / "OROGRAPHIC_SOURCE_BINDING_V1.json")
    code = (
        Path(__file__), Path(__file__).with_name("orographic_separability.py"),
        Path(__file__).with_name("orographic_source_binding.py"),
        *(ROOT / f"src/yuntapr/experimental/core_innovation/{name}.py"
          for name in ("gfs", "grid", "dote", "terrain")),
        ROOT / "src/yuntapr/spatial/sp04_mapping.py",
    )
    proposal = dict(
        authorization_scope=SCOPE, status="PROPOSAL_ONLY_REQUIRES_RESEARCHER_APPROVAL",
        source_binding_sha256=_digest(bound),
        code_sha256={path.relative_to(ROOT).as_posix(): sha256(path.read_bytes()).hexdigest() for path in code},
        budget=bound["budget"] | {"max_seconds": MAX_SECONDS, "total_payload_opens_max": 282},
        population=dict(scenes=963, supervised=COUNTS[0], strong=COUNTS[1],
                        supported_strong=COUNTS[2], supported_non_strong=COUNTS[3]),
        matched_minimum=dict(strong=MIN_MATCHED[0], scenes=MIN_MATCHED[1]),
        decision="Windward concordance must exceed 0.5 and each of PWAT, slope and reversed wind.",
        aggregate_only=True,
    )
    return proposal | {"proposal_sha256": _digest(proposal)}


def _json(path):
    return json.loads(path.read_bytes())


def _write(path, report):
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(report, stream, indent=2, allow_nan=False)
        stream.write("\n")


def scan_predictions(binding, read_shard, *, counts=COUNTS, cells_per_scene=3430):
    """Verify the complete mask and population before allowing any physical source."""
    ids = [row["sample_id"] for row in binding["source_by_scene"]]
    if len(set(ids)) != len(ids):
        raise ValueError("Duplicate Development scene identity")
    pos = 0
    total = np.zeros(4, dtype=np.int64)
    mask_digest = sha256()
    paired = {}
    skipped = Counter()
    skipped_rainfall = Counter(rainfall_counts(np.array([])))
    for index, spec in enumerate(binding["prediction_shards"]):
        if spec["file"] != f"batch_{index:03d}.npz" or spec["scene_start"] != pos:
            raise ValueError("Prediction shard sequence differs")
        with np.load(BytesIO(read_shard(spec)), allow_pickle=False) as arrays:
            scenes, mask = arrays["scene_ids"], arrays["supervision_mask"]
            p, truth, q = (arrays[key] for key in ("p", "truth_mm_h", "qlog"))
            n = spec["n_valid"]
            k = spec["scenes"]
            if (scenes.dtype.kind != "U" or scenes.tolist() != ids[pos:pos + k]
                    or mask.shape != (k, 100, 100) or mask.dtype != bool
                    or not np.all(mask.sum(axis=(1, 2)) == cells_per_scene)
                    or n != k * cells_per_scene or p.shape != (n,) or truth.shape != (n,)
                    or q.shape != (n, 32) or p.dtype != np.float32 or truth.dtype != np.float32
                    or q.dtype != np.float64 or not all(np.isfinite(x).all() for x in (p, truth, q))
                    or np.any((p < 0) | (p > 1)) or np.any(truth < 0) or np.any(np.diff(q, axis=1) <= 0)):
                raise ValueError("Frozen prediction shape, mask, values or scene identities differ")
            q32 = q[:, -1]
            support = q32 > math.log1p(20.)
            strong = truth > np.float32(20.)
            total += (n, strong.sum(), (support & strong).sum(), (support & ~strong).sum())
            for i, (scene, cell_mask) in enumerate(zip(scenes, mask)):
                key = str(scene).encode()
                mask_digest.update(len(key).to_bytes(4, "big"))
                mask_digest.update(key)
                mask_digest.update(np.asarray(cell_mask.shape, dtype="<i8").tobytes())
                mask_digest.update(cell_mask.tobytes(order="C"))
                bounds = slice(i * cells_per_scene, (i + 1) * cells_per_scene)
                hit = support[bounds]
                positive = strong[bounds][hit]
                if positive.any() and not positive.all():
                    paired[str(scene)] = (np.flatnonzero(cell_mask)[hit], truth[bounds][hit],
                                          p[bounds][hit], q32[bounds][hit])
                else:
                    skipped["strong"] += int(positive.sum())
                    skipped["non_strong"] += int(len(positive) - positive.sum())
                    skipped_rainfall.update(rainfall_counts(truth[bounds][hit][positive]))
        pos += k
    if pos != len(ids) or tuple(total) != counts or mask_digest.hexdigest() != binding["receipt"]["supervision_mask_sha256"]:
        raise ValueError("Full prediction population, q32 support or mask digest differs")
    return paired, dict(strong=skipped["strong"], non_strong=skipped["non_strong"],
                        strong_by_rainfall=dict(skipped_rainfall))


def physical_columns(forecast, terrain):
    """Use the same native and target above-ground masking as original DOTE."""
    from yuntapr.experimental.core_innovation.dote import dote_proxy
    from yuntapr.experimental.core_innovation.gfs import EnvironmentFrame, _above_ground

    frame = EnvironmentFrame(forecast.identity, forecast.grid, _above_ground(forecast.fields),
                             "retrospective", (forecast.provenance,))
    mapped = frame if frame.grid.identity == terrain.grid.identity else frame.on_grid(
        terrain.grid, operator="bilinear_point_candidate",
    )
    u, v, ps, pwat = (mapped.fields[k] for k in ("u700", "v700", "ps", "pwat"))
    if [(v.quantity, v.unit, v.level_pa) for v in (u, v, ps, pwat)] != [
        ("u", "m/s", 70000.), ("v", "m/s", 70000.), ("surface_pressure", "Pa", None),
        ("precipitable_water", "kg m-2", None),
    ]:
        raise ValueError("Canonical physical wind, pressure and PWAT identities required")
    proxy = dote_proxy(
        terrain, u.values[None], v.values[None], (u.valid & v.valid)[None],
        np.array([70000.]), ps.values, ps.valid,
        wind_grid=mapped.grid, wind_unit="m/s", pressure_unit="Pa", surface_pressure_unit="Pa",
    )
    slope = np.hypot(terrain.east_gradient, terrain.north_gradient)
    return terrain.elevation_m, slope, pwat.values, proxy.orographic_proxy_m_s[0], proxy.valid[0] & pwat.valid


def load_terrain(raw):
    from yuntapr.experimental.core_innovation.grid import GridSpec, frozen_sp04_grid
    from yuntapr.experimental.core_innovation.terrain import TerrainFeatures

    with np.load(BytesIO(raw), allow_pickle=False) as data:
        grid = GridSpec(data["lat"], data["lon"])
        values, mask, region = (data[key] for key in ("values", "valid", "region"))
    frozen_sp04_grid(ROOT).assert_same(grid)
    if (values.shape != (6, 100, 100) or mask.shape != values.shape or mask.dtype != bool
            or region.shape != (100, 100) or region.dtype != bool or int(region.sum()) != 3430
            or not np.isfinite(values[mask]).all() or not mask[:4, region].all()):
        raise ValueError("Frozen B6 terrain geometry or supervision differs")
    terrain = TerrainFeatures(grid, values[0], mask[0], values[1], values[2], mask[1] & mask[2],
                              values[3], np.zeros(grid.shape), mask[4] & mask[5])
    return terrain, region


def evaluate(batch, sources, read_columns, region):
    chunks = []
    for scene, (pixels, truth, p, q32) in batch.items():
        if not region.ravel()[pixels].all():
            raise ValueError("Prediction support lies outside frozen terrain region")
        columns = read_columns(sources[scene])
        chunks.append((np.repeat(scene, len(pixels)), truth, p, q32,
                       *(value.ravel()[pixels] for value in columns)))
    if chunks:
        return summarize(*(np.concatenate(values) for values in zip(*chunks)))
    return summarize(np.array([], dtype="U1"), np.array([], dtype=np.float32),
                     *(np.array([], dtype=np.float64) for _ in range(6)), np.array([], dtype=bool))


class Meter:
    """Count reserved payload access before I/O, including a failed attempt."""

    def __init__(self, budget):
        self.budget = budget
        self.started = time.monotonic()
        self.ledger = Counter()

    def check_time(self):
        if time.monotonic() - self.started > self.budget["max_seconds"]:
            raise TimeoutError("Diagnostic wall time exhausted")

    def reserve(self, path, spec, category):
        self.check_time()
        sizes, opens = category + "_bytes", category + "_opens"
        size = spec["bytes"]
        if (self.ledger[sizes] + size > self.budget.get(sizes + "_max", self.budget.get(sizes))
                or self.ledger[opens] + 1 > self.budget.get(opens + "_max", self.budget.get(opens))
                or path.stat().st_size != size):
            raise ValueError("Payload differs from exact source scope or quota")
        self.ledger[sizes] += size
        self.ledger[opens] += 1

    def read(self, path, spec, category):
        self.reserve(path, spec, category)
        with path.open("rb") as stream:
            if os.fstat(stream.fileno()).st_size != spec["bytes"]:
                raise ValueError("Opened payload size differs")
            raw = stream.read(spec["bytes"])
        if len(raw) != spec["bytes"] or sha256(raw).hexdigest() != spec["sha256"]:
            raise ValueError("Opened payload content differs")
        return raw


def _read_forecast(source, terrain, meter):
    from yuntapr.experimental.core_innovation.gfs import ForecastIdentity, VariableRequest, decode_gfs_bytes

    init = datetime.fromisoformat(source["init_time"])
    valid = datetime.fromisoformat(source["analysis_time"])
    path = Path(source["path"])
    if init.year != 2024 or valid.year != 2024 or path.name != f"gfs_0p25_{init:%Y%m%d%H}_f006.nc":
        raise PermissionError("Only listed 2024 main f006 sources allowed")
    identity = ForecastIdentity(init, timedelta(hours=6), valid)
    requests = (
        VariableRequest("u700", "u", "u-component_of_wind_isobaric", 70000.),
        VariableRequest("v700", "v", "v-component_of_wind_isobaric", 70000.),
        VariableRequest("ps", "surface_pressure", "Pressure_surface"),
        VariableRequest("pwat", "precipitable_water", "Precipitable_water_entire_atmosphere_single_layer"),
    )
    return physical_columns(decode_gfs_bytes(meter.read(path, source, "gfs_main"), identity, requests), terrain)


def conclude(result):
    matched = result["matched"]
    if matched["strong"] < MIN_MATCHED[0] or matched["scenes"] < MIN_MATCHED[1]:
        return "STOP_INSUFFICIENT_MATCHED_COVERAGE"
    scores = result["positive_weighted_concordance"]
    if scores["windward"] <= max(.5, scores["pwat"], scores["slope"], scores["reversed_wind"]):
        return "STOP_WINDWARD_DOES_NOT_BEAT_CONTROLS"
    return "DESCRIPTIVE_SIGNAL_ONLY"


def execute():
    proposal = _json(DOCS / "OROGRAPHIC_EXECUTION_PROPOSAL_V1.json")
    if proposal != build_proposal():
        raise PermissionError("Frozen execution proposal no longer matches")
    grant = _json(RUN / "RESEARCHER_APPROVAL.json")
    if (grant.get("approved_by_researcher") is not True or not grant.get("decision_id")
            or grant.get("run_folder") != str(RUN.resolve())
            or any(grant.get(k) != proposal[k] for k in ("authorization_scope", "budget", "proposal_sha256"))):
        raise PermissionError("Separate approval of this exact one-time diagnostic required")
    binding = _json(ALLOWLIST)
    receipt = binding.pop("receipt")
    if _digest(receipt) != proposal["source_binding_sha256"] or _digest(binding) != receipt["private_allowlist_sha256"]:
        raise PermissionError("Private source binding differs")
    binding["receipt"] = receipt
    output = RUN / "output"
    output.mkdir(exist_ok=False)
    meter = Meter(proposal["budget"])
    try:
        folder = Path(binding["prediction_folder"])
        batch, skipped = scan_predictions(
            binding, lambda spec: meter.read(folder / spec["file"], spec, "saved_array"),
        )
        sources = {row["sample_id"]: row for row in binding["source_by_scene"]}
        if (len(batch) > meter.budget["gfs_main_opens_max"]
                or sum(sources[scene]["bytes"] for scene in batch) > meter.budget["gfs_main_bytes_max"]):
            raise ValueError("Potential match population exceeds main-source cap")
        if batch:
            static = binding["static_pack"]
            terrain, region = load_terrain(meter.read(Path(static["path"]), static, "static_pack"))
            result = evaluate(batch, sources, lambda item: _read_forecast(item, terrain, meter), region)
        else:
            result = evaluate(batch, sources, None, None)
        meter.check_time()
    except Exception as exc:
        _write(output / "stopped.json", dict(status="STOPPED_NO_RETRY", failure_category=type(exc).__name__,
                                            reserved_reads=dict(meter.ledger), proposal_sha256=proposal["proposal_sha256"]))
        raise
    result.update(
        status="COMPLETE_OROGRAPHIC_SEPARABILITY_DIAGNOSTIC", scientific_status="NOT_VERIFIED",
        decision=conclude(result), unsupported_strong=COUNTS[1] - COUNTS[2],
        full_supported_positive=COUNTS[2], full_supported_non_strong=COUNTS[3],
        no_same_scene_opposite_class=skipped, actual_reads=dict(meter.ledger),
        elapsed_seconds=time.monotonic() - meter.started, proposal_sha256=proposal["proposal_sha256"],
        raw_inputs_other_than_gfs_main_and_b6=0, forwards=0, optimizer_updates=0, final_2025_access=False,
    )
    _write(output / "completion.json", result)
    return result


def supervise():
    try:
        return subprocess.run([sys.executable, "-B", "-m", __spec__.name, "_worker"],
                              timeout=MAX_SECONDS, check=False).returncode
    except subprocess.TimeoutExpired:
        output = RUN / "output"
        if output.is_dir() and not (output / "stopped.json").exists() and not (output / "completion.json").exists():
            _write(output / "stopped.json", dict(status="STOPPED_TIMEOUT_NO_RETRY",
                                               accounting="CONSERVATIVELY_CHARGE_FULL_APPROVED_PAYLOAD_CAP"))
        raise


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("proposal", "execute", "_worker"))
    args = parser.parse_args()
    if args.mode == "execute":
        raise SystemExit(supervise())
    print(json.dumps(build_proposal() if args.mode == "proposal" else execute(), indent=2, allow_nan=False))
