"""Torch-free one-shot nine-gate Stage-45 Development acceptance readout.

The module only uses NumPy at import time.  The real satellite decoder imports
netCDF4 lazily inside :func:`_read_band`; tests inject the whole file reader.
"""

import csv
import hashlib
import io
import json
import time
from pathlib import Path

import numpy as np


KIND = "BOUNDED_STAGE45_DEV_ACCEPTANCE"
AUTHORIZATION_SCOPE = "COSINE9_E9_2024_DEV_STAGE45_NINE_GATE_ACCEPTANCE"
TASK = dict(role="Development", year=2024, evaluation="STAGE45_DEV_NINE_GATE_ACCEPTANCE")
TASK_NAME = "COSINE9_E9_2024_DEV_STAGE45_NINE_GATE_ACCEPTANCE"
FINAL_2025_ACCESS = False

NODES = 32
SLOTS = 6
BANDS = ("08", "13")
GRID = (100, 100)
NATIVE_GRID = (501, 501)
SUPERVISION_PIXELS_PER_SCENE = 3430
SCENE_BATCH_LIMIT = 8

CANDIDATE_THRESHOLD = 20.0
A0_THRESHOLD = 9.5373
SPLIT_THRESHOLD = 2.3612
TARGET_MASS = 20.01
TAU = (np.arange(NODES, dtype=np.float64) + .5) / NODES
THRESHOLD = np.float32(20.0)
RAIN_THRESHOLD = np.float32(.1)
WEAK_UPPER = np.float32(1.0)

BASELINE_METRICS = dict(
    strong_physical_pinball_over20=0.5068646309277546,
    q32_support_tp=160,
    q32_support_fp=5769,
    point_a_tp=0,
    point_a_fp=0,
    weak_log_pinball=0.08872231160181858,
    occurrence_brier=0.09233015567445307,
    occurrence_ap=0.6066547555865263,
    occurrence_auroc=0.8990243638708331,
)
BASELINE_COUNTS = dict(
    scenes=963,
    n_valid=3303090,
    n_rain=407820,
    n_strong=717,
    n_weak=246473,
    n_candidates=1912,
    n_candidate_strong=84,
    n_candidate_scenes=130,
)
FROZEN_EXPECTED = dict(
    metrics=dict(BASELINE_METRICS),
    counts=dict(BASELINE_COUNTS),
    arrays_bytes=881_894_762,
    satellite_bytes=3_593_008_460,
    arrays_files=121,
    satellite_files=780,
)

BUDGET = dict(
    maximum_scientific_file_opens=901,
    maximum_reference_bytes=4_474_903_222,
    maximum_seconds=900,
    array_reference_bytes=881_894_762,
    satellite_reference_bytes=3_593_008_460,
    scientific_passes=1,
    model_inference_passes=0,
    optimizer_updates=0,
    checkpoint_loads=0,
    retries=0,
    replay=0,
)

SP04_MANIFEST_SHA256 = "e1c5d8ab1b58407503db4b56124f4a34a360507280b0e7989e8b9e2f60888473"
SP04_MANIFEST = "config/spatial/sp04_coordinate_manifest_v1.json"
SP04_AXES = "config/spatial/sp04_coordinate_axes_v1.csv"
SP04_MEMBERSHIP = "config/spatial/sp04_target_cell_membership_v1.csv"
MAX_SELECTED_ROWS = 50
MAX_INFEASIBLE_ROWS = 50


def digest(value):
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    ).hexdigest()


def sha256_bytes(value):
    return hashlib.sha256(value).hexdigest()


def sha256_file(path):
    hasher = hashlib.sha256()
    with Path(path).open("rb") as stream:
        while chunk := stream.read(1024 * 1024):
            hasher.update(chunk)
    return hasher.hexdigest()


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, sort_keys=True, indent=2, ensure_ascii=False, allow_nan=False) + "\n",
        encoding="utf-8",
    )


def private_digest(private):
    return digest({key: value for key, value in private.items()
                   if key not in ("proposal_sha256", "private_preparation_sha256")})


def proposal_digest(proposal):
    return digest({key: value for key, value in proposal.items() if key != "proposal_sha256"})


class Deadline:
    def __init__(self, seconds, clock=time.monotonic):
        self.clock = clock
        self.started = clock()
        self.seconds = float(seconds)

    @property
    def elapsed(self):
        return self.clock() - self.started

    def remaining(self):
        remaining = self.seconds - self.elapsed
        if remaining <= 0:
            raise TimeoutError("Stage-45 acceptance deadline expired")
        return remaining

    def check(self):
        self.remaining()


def _pinball_zero(delta):
    return np.maximum(TAU * delta, (TAU - 1) * delta).mean(axis=-1)


def physical_pinball_over20(truth, qlog):
    """Per-row physical pinball / 20 with e = truth(mm/h) - node(mm/h)."""
    truth = np.asarray(truth, dtype=np.float64)
    nodes = np.expm1(np.asarray(qlog, dtype=np.float64))
    return _pinball_zero(truth[:, None] - nodes) / 20.0


def weak_log_pinball(truth, qlog):
    truth = np.asarray(truth, dtype=np.float64)
    delta = np.log1p(truth)[:, None] - np.asarray(qlog, dtype=np.float64)
    return _pinball_zero(delta)


def point_a(probability, qlog):
    """The project's fixed point readout, FP32 after an FP64 node mean."""
    return np.float32(float(probability) * float(np.expm1(np.asarray(qlog, dtype=np.float64)).mean()))


def rank_scores(score, strong):
    """Tie-aware AP and half-credit AUC copied from point_rank_readout.py."""
    score = np.asarray(score, dtype=np.float32)
    strong = np.asarray(strong, dtype=bool)
    if score.shape != strong.shape or score.ndim != 1 or not np.isfinite(score).all():
        raise ValueError("Ranking expects aligned finite FP32 scores and Boolean labels")
    n_pos, n_neg = int(strong.sum()), int((~strong).sum())
    if not n_pos or not n_neg:
        return None, None, n_pos, n_neg
    order = np.argsort(score)[::-1]
    ordered = score[order]
    ends = np.r_[np.flatnonzero(ordered[:-1] != ordered[1:]), len(order) - 1]
    cum_pos = np.cumsum(strong[order], dtype=np.int64)[ends]
    cum_neg = ends + 1 - cum_pos
    per_pos, per_neg = np.diff(cum_pos, prepend=0), np.diff(cum_neg, prepend=0)
    ap = float(np.dot(per_pos, cum_pos / (ends + 1)) / n_pos)
    auroc = float(np.dot(per_pos, n_neg - cum_neg + .5 * per_neg) / (n_pos * n_neg))
    return ap, auroc, n_pos, n_neg


def physical_pinball_nodes_over20(truth, nodes):
    """Per-row physical pinball / 20 from already transformed physical nodes."""
    truth = np.asarray(truth, dtype=np.float64)
    nodes = np.asarray(nodes, dtype=np.float64)
    return _pinball_zero(truth[:, None] - nodes) / 20.0


def blend_to_top(nodes, probability):
    """Move the 31 sub-top physical quantiles a fraction u toward the fixed top.

    The fraction is chosen so the FP32 point readout reaches TARGET_MASS while
    the top quantile and the occurrence probability stay unchanged.  A strict
    ordered blend always exists for a candidate whose point mass is below the
    target; otherwise the row is reported as infeasible instead of activated.
    """
    nodes = np.asarray(nodes, dtype=np.float64)
    if nodes.shape != (NODES,) or not np.all(np.isfinite(nodes)):
        return None, "NODES_NOT_FINITE"
    q32 = float(nodes[NODES - 1])
    mean_old = float(nodes.mean())
    mean31 = float(nodes[:NODES - 1].mean())
    target = TARGET_MASS / float(probability)
    denominator = ((NODES - 1) / NODES) * (q32 - mean31)
    if not denominator > 0.0:
        return None, "BLEND_DENOMINATOR_NOT_POSITIVE"
    fraction = (target - mean_old) / denominator
    if not 0.0 < fraction < 1.0:
        return None, "BLEND_FRACTION_OUTSIDE_OPEN_UNIT_INTERVAL"
    blended = nodes.copy()
    blended[:NODES - 1] = nodes[:NODES - 1] + fraction * (q32 - nodes[:NODES - 1])
    blended[NODES - 1] = q32
    if not np.all(np.diff(blended) > 0):
        return None, "NODES_NOT_STRICTLY_INCREASING"
    new_a = np.float32(float(probability) * float(blended.mean()))
    if not new_a > THRESHOLD:
        return None, "NEW_A_NOT_STRICTLY_ABOVE_20"
    return blended, float(fraction), new_a



def metrics_from_population(population):
    p32 = population["p"]
    truth = population["truth"]
    q32 = population["q32"]
    strong = truth > THRESHOLD
    rain = truth > RAIN_THRESHOLD
    a0 = population["a0"]
    values = dict(
        strong_physical_pinball_over20=float(
            physical_pinball_over20(truth[strong], population["strong_qlog"]).mean()),
        q32_support_tp=int(((q32 > 20.0) & strong).sum()),
        q32_support_fp=int(((q32 > 20.0) & ~strong).sum()),
        point_a_tp=int(((a0 > THRESHOLD) & strong).sum()),
        point_a_fp=int(((a0 > THRESHOLD) & ~strong).sum()),
        weak_log_pinball=float(
            weak_log_pinball(truth[population["weak"]], population["weak_qlog"]).mean()),
        occurrence_brier=float(np.square(p32.astype(np.float64) - rain.astype(np.float64)).mean()),
    )
    ap, auroc, _, _ = rank_scores(p32, rain)
    values["occurrence_ap"] = ap
    values["occurrence_auroc"] = auroc
    return values


def counts_from_population(population):
    truth = population["truth"]
    return dict(
        scenes=len(population["scene_ids"]),
        n_valid=int(len(truth)),
        n_rain=int((truth > RAIN_THRESHOLD).sum()),
        n_strong=int((truth > THRESHOLD).sum()),
        n_weak=int(population["weak"].sum()),
        n_candidates=int(len(population["candidate_rows"])),
        n_candidate_strong=int(population["candidate_strong"].sum()),
        n_candidate_scenes=len(population["candidate_scene_ids"]),
    )


class _ReadGuard:
    def __init__(self, verify_file, deadline, maximum_opens, maximum_bytes):
        self.verify_file = verify_file
        self.deadline = deadline
        self.maximum_opens = int(maximum_opens)
        self.maximum_bytes = int(maximum_bytes)
        self.opens = 0
        self.scientific_bytes = 0

    def __call__(self, path, expected_bytes, expected_sha256, expected_sha_type="scientific"):
        self.deadline.check()
        self.opens += 1
        if self.opens > self.maximum_opens:
            raise RuntimeError("Scientific file-open budget exceeded")
        content, digest_value = self.verify_file(Path(path))
        content = bytes(content)
        if len(content) != int(expected_bytes):
            raise ValueError(f"Input byte count changed: {Path(path).name}")
        actual = sha256_bytes(content)
        if actual != expected_sha256:
            raise ValueError(f"Input SHA256 changed: {Path(path).name}")
        if digest_value != actual:
            raise ValueError(f"Injected reader digest differs: {Path(path).name}")
        self.scientific_bytes += len(content)
        if self.scientific_bytes > self.maximum_bytes:
            raise RuntimeError("Scientific reference-byte budget exceeded")
        return content


def sp04_membership(code_root):
    """Torch-free exact parse of the frozen SP04 membership artifacts."""
    root = Path(code_root)
    manifest_path = root / SP04_MANIFEST
    manifest_bytes = manifest_path.read_bytes()
    if sha256_bytes(manifest_bytes) != SP04_MANIFEST_SHA256:
        raise ValueError("SP04 manifest SHA256 differs from pinned version")
    manifest = json.loads(manifest_bytes.decode("utf-8"))
    axes_path = root / SP04_AXES
    mapping_path = root / SP04_MEMBERSHIP
    if sha256_file(axes_path) != manifest["axes_csv_sha256"]:
        raise ValueError("SP04 axes SHA256 mismatch")
    if sha256_file(mapping_path) != manifest["mapping_csv_sha256"]:
        raise ValueError("SP04 mapping SHA256 mismatch")
    if (tuple(manifest.get("native_shape", ())) != NATIVE_GRID
            or tuple(manifest.get("target_shape", ())) != GRID):
        raise ValueError("SP04 shape differs")
    indices = []
    with mapping_path.open(newline="", encoding="utf-8") as stream:
        for row in csv.DictReader(stream):
            flat = len(indices)
            if (int(row["target_row"]), int(row["target_col"])) != divmod(flat, 100):
                raise ValueError("SP04 target order mismatch")
            if (int(row["target_full_row"]), int(row["target_full_col"])) != (10 + flat // 100, 20 + flat % 100):
                raise ValueError("SP04 full-grid target index mismatch")
            rows = [int(value) for value in row["native_source_rows"].split(";")]
            cols = [int(value) for value in row["native_source_cols"].split(";")]
            if (len(rows) * len(cols) != 25 or int(row["native_center_count"]) != 25
                    or any(value < 1 or value > 500 for value in rows)
                    or any(value < 0 or value > 499 for value in cols)):
                raise ValueError("SP04 membership count or bounds mismatch")
            indices.append([row_value * 501 + col_value for row_value in rows for col_value in cols])
    if len(indices) != 10000 or len({value for cell in indices for value in cell}) != 250000:
        raise ValueError("SP04 membership is not one-to-one over 250000 native centers")
    return np.asarray(indices, dtype=np.int64)


def decode_tbb(raw, attrs):
    """Exact copy of yuntapr.data.himawari_b13.decode_b13 semantics."""
    required = ("scale_factor", "add_offset", "valid_min", "valid_max")
    if any(key not in attrs for key in required) or not any(
            key in attrs for key in ("_FillValue", "missing_value")):
        raise ValueError("B13 packed scale/valid/missing metadata incomplete")
    raw = np.asarray(raw)
    valid = np.isfinite(raw) & (raw >= attrs["valid_min"]) & (raw <= attrs["valid_max"])
    for key in ("_FillValue", "missing_value"):
        if key in attrs:
            for missing in np.asarray(attrs[key]).reshape(-1):
                valid &= raw != missing
    value = raw.astype(np.float32) * np.float32(attrs["scale_factor"]) + np.float32(attrs["add_offset"])
    valid &= np.isfinite(value)
    value[~valid] = np.nan
    return value, valid


def read_band(content, band):
    """Decode one tbb band from an in-memory NetCDF payload."""
    import netCDF4

    if band not in BANDS:
        raise ValueError("Unexpected Stage-45 satellite band")
    with netCDF4.Dataset("stage45_satellite.nc", mode="r", memory=bytes(content)) as dataset:
        dataset.set_auto_maskandscale(False)
        variable = dataset[f"tbb_{band}"]
        attrs = {key: variable.getncattr(key) for key in variable.ncattrs()}
        raw = np.asarray(variable[:])
    if raw.shape != NATIVE_GRID:
        raise ValueError("Satellite band shape differs from 501x501")
    return decode_tbb(raw, attrs)


def sp04_area_mean(value, valid, indices):
    """25-center mean only where all 25 native centers are valid (probe rule)."""
    flat_value = np.asarray(value, dtype=np.float32).reshape(-1)
    flat_valid = np.asarray(valid, dtype=bool).reshape(-1)
    if flat_value.shape != (NATIVE_GRID[0] * NATIVE_GRID[1],):
        raise ValueError("Satellite band must cover the frozen 501x501 native grid")
    selected = indices.reshape(-1)
    weights = np.where(flat_valid[selected], flat_value[selected].astype(np.float64), 0.0)
    owner = np.repeat(np.arange(indices.shape[0], dtype=np.int64), indices.shape[1])
    totals = np.bincount(owner, weights=weights, minlength=indices.shape[0])
    counts = np.bincount(owner, weights=flat_valid[selected].astype(np.float64),
                         minlength=indices.shape[0])
    mean = np.full(indices.shape[0], np.nan, dtype=np.float64)
    full = counts == indices.shape[1]
    mean[full] = totals[full] / float(indices.shape[1])
    return mean.reshape(GRID).astype(np.float32)


def _validate_arrays_entry(entry, arrays_dir, position):
    if not isinstance(entry, dict):
        raise ValueError("Array-shard entry must be an object")
    name = entry.get("file")
    if not (isinstance(name, str) and len(name) == 13 and name.startswith("batch_")
            and name.endswith(".npz") and name[6:9].isdigit()):
        raise ValueError("Array shard name differs from batch_%03d.npz")
    if entry.get("scene_start") != position:
        raise ValueError("Array shard scene_start is not contiguous")
    scenes = int(entry.get("scenes", 0))
    if not 1 <= scenes <= SCENE_BATCH_LIMIT:
        raise ValueError("Array shard scene count is outside 1..8")
    if int(entry.get("n_valid", -1)) != scenes * SUPERVISION_PIXELS_PER_SCENE:
        raise ValueError("Array shard supervised pixel count differs")
    if not isinstance(entry.get("bytes"), int) or entry["bytes"] <= 0:
        raise ValueError("Array shard byte count malformed")
    sha = entry.get("sha256")
    if not (isinstance(sha, str) and len(sha) == 64 and all(c in "0123456789abcdef" for c in sha)):
        raise ValueError("Array shard SHA256 malformed")
    return Path(arrays_dir) / name


def load_population(entries, arrays_dir, read, deadline):
    """Read the 121 saved shards once and retain only what the gates need."""
    p_parts, truth_parts, q32_parts, a0_parts = [], [], [], []
    strong_qlog, weak_qlog, candidate_qlog = [], [], []
    candidate_meta = []
    scene_ids = []
    position = 0
    for entry in entries:
        path = _validate_arrays_entry(entry, arrays_dir, position)
        content = read(path, entry["bytes"], entry["sha256"])
        with np.load(io.BytesIO(content), allow_pickle=False) as archive:
            keys = set(archive.files)
            required = {"scene_ids", "supervision_mask", "p", "qlog", "truth_mm_h"}
            if keys != required:
                raise ValueError("Saved shard keys differ from the frozen readout")
            ids = archive["scene_ids"]
            mask = archive["supervision_mask"]
            p = archive["p"]
            qlog = archive["qlog"]
            truth = archive["truth_mm_h"]
        scenes = int(entry["scenes"])
        if ids.shape != (scenes,) or ids.dtype.kind != "U" or any(not str(value) for value in ids):
            raise ValueError("Saved scene_ids shape/dtype differs")
        ids = [str(value) for value in ids]
        if any(not value.startswith("2024-") for value in ids):
            raise ValueError("Only the 2024 Development population is admitted")
        if scene_ids and ids[0] <= scene_ids[-1]:
            raise ValueError("Saved scene order is not strictly increasing")
        if len(set(ids)) != len(ids):
            raise ValueError("Saved scene order contains duplicates")
        scene_ids.extend(ids)
        expected_mask = (scenes, GRID[0], GRID[1])
        if mask.shape != expected_mask or mask.dtype != np.bool_:
            raise ValueError("Saved supervision mask shape/dtype differs")
        if not np.array_equal(mask.sum(axis=(1, 2)), np.full(scenes, SUPERVISION_PIXELS_PER_SCENE)):
            raise ValueError("Saved supervision mask population differs")
        n = scenes * SUPERVISION_PIXELS_PER_SCENE
        if p.shape != (n,) or p.dtype != np.float32 or not np.isfinite(p).all() or np.any((p < 0) | (p > 1)):
            raise ValueError("Saved FP32 probability differs")
        if truth.shape != (n,) or truth.dtype != np.float32 or not np.isfinite(truth).all() or (truth < 0).any():
            raise ValueError("Saved FP32 truth differs")
        if (qlog.shape != (n, NODES) or qlog.dtype != np.float64 or not np.isfinite(qlog).all()
                or not np.all(np.diff(qlog, axis=1) > 0)):
            raise ValueError("Saved FP64 log-quantiles differ")
        physical = np.expm1(qlog)
        q32 = physical[:, -1]
        mean_i = physical.mean(axis=1)
        p64 = p.astype(np.float64)
        candidate = p64 * q32 > CANDIDATE_THRESHOLD
        a0 = np.float32(p64 * mean_i)
        strong = truth > THRESHOLD
        weak = (truth > RAIN_THRESHOLD) & (truth <= WEAK_UPPER)
        if not np.isfinite(a0).all():
            raise ValueError("A0 point readout is nonfinite")
        p_parts.append(p)
        truth_parts.append(truth)
        q32_parts.append(q32)
        a0_parts.append(a0)
        if strong.any():
            strong_qlog.append(qlog[strong])
        if weak.any():
            weak_qlog.append(qlog[weak])
        if candidate.any():
            candidate_qlog.append(qlog[candidate])
            scene_base = len(scene_ids) - scenes
            for index in range(scenes):
                ys, xs = np.nonzero(mask[index])
                local = np.flatnonzero(candidate[index * SUPERVISION_PIXELS_PER_SCENE:
                                               (index + 1) * SUPERVISION_PIXELS_PER_SCENE])
                for row in local:
                    row = int(row)
                    candidate_meta.append(dict(
                        scene_index=scene_base + index,
                        row=row,
                        y=int(ys[row]),
                        x=int(xs[row]),
                        global_row=(position + index) * SUPERVISION_PIXELS_PER_SCENE + row,
                    ))
        position += scenes
        deadline.check()
    if not p_parts:
        raise ValueError("No saved Development shards were supplied")
    p = np.concatenate(p_parts)
    truth = np.concatenate(truth_parts)
    q32 = np.concatenate(q32_parts)
    a0 = np.concatenate(a0_parts)
    candidate_rows = np.asarray([row["global_row"] for row in candidate_meta], dtype=np.int64)
    candidate_scene_ids = []
    seen = set()
    for row in candidate_meta:
        scene = scene_ids[row["scene_index"]]
        if scene not in seen:
            seen.add(scene)
            candidate_scene_ids.append(scene)
    population = dict(
        scene_ids=scene_ids,
        p=p,
        truth=truth,
        q32=q32,
        a0=a0,
        strong=truth > THRESHOLD,
        weak=(truth > RAIN_THRESHOLD) & (truth <= WEAK_UPPER),
        rain=truth > RAIN_THRESHOLD,
        candidate_rows=candidate_rows,
        candidate_meta=candidate_meta,
        candidate_scene_ids=candidate_scene_ids,
        strong_qlog=np.concatenate(strong_qlog) if strong_qlog else np.empty((0, NODES)),
        weak_qlog=np.concatenate(weak_qlog) if weak_qlog else np.empty((0, NODES)),
        candidate_qlog=np.concatenate(candidate_qlog) if candidate_qlog else np.empty((0, NODES)),
    )
    population["candidate_strong"] = population["strong"][candidate_rows]
    if position != len(scene_ids):
        raise ValueError("Saved shard scene accounting differs")
    return population


def _compare_expected(actual, expected, label):
    if isinstance(expected, dict):
        if not isinstance(actual, dict) or set(actual) != set(expected):
            raise ValueError(f"{label} keys differ from the frozen preparation")
        for key in expected:
            _compare_expected(actual[key], expected[key], f"{label}.{key}")
        return
    if isinstance(expected, bool) or actual is None or expected is None:
        if actual != expected:
            raise ValueError(f"{label} differs from the frozen preparation")
        return
    if isinstance(expected, int):
        if int(actual) != int(expected):
            raise ValueError(f"{label} differs from the frozen preparation")
        return
    if abs(float(actual) - float(expected)) > 1e-12:
        raise ValueError(f"{label} differs from the frozen preparation by {float(actual) - float(expected):.3e}")


def _satellite_index(private, population):
    entries = private.get("satellite_files")
    if not isinstance(entries, list):
        raise ValueError("Private satellite list missing")
    grouped = {}
    for entry in entries:
        if not isinstance(entry, dict):
            raise ValueError("Satellite entry must be an object")
        scene = entry.get("scene")
        slot = entry.get("slot")
        if scene not in population["candidate_scene_ids"]:
            raise ValueError("Satellite list references a non-candidate scene")
        if not isinstance(slot, int) or not 0 <= slot < SLOTS:
            raise ValueError("Satellite slot is outside 0..5")
        if slot in grouped.setdefault(scene, {}):
            raise ValueError("Duplicate satellite scene/slot")
        if not isinstance(entry.get("nominal"), str) or not entry["nominal"]:
            raise ValueError("Satellite nominal time missing")
        if not isinstance(entry.get("relative_path"), str) or not entry["relative_path"]:
            raise ValueError("Satellite relative path missing")
        if not isinstance(entry.get("bytes"), int) or entry["bytes"] <= 0:
            raise ValueError("Satellite expected byte count malformed")
        sha = entry.get("sha256")
        if not (isinstance(sha, str) and len(sha) == 64 and all(c in "0123456789abcdef" for c in sha)):
            raise ValueError("Satellite expected SHA256 malformed")
        grouped[scene][slot] = entry
    for scene in population["candidate_scene_ids"]:
        if set(grouped.get(scene, {})) != set(range(SLOTS)):
            raise ValueError("Candidate scene lacks one of the six causal satellite slots")
    return grouped


def _row_record(population, candidate_index, split_min, blend_fraction, new_a,
                activated_nodes, reason):
    meta = population["candidate_meta"][candidate_index]
    scene_index = meta["scene_index"]
    row = meta["row"]
    truth = float(population["truth"][meta["global_row"]])
    qlog = population["candidate_qlog"][candidate_index]
    q32 = float(np.expm1(qlog[-1]))
    record = dict(
        scene=population["scene_ids"][scene_index],
        row=int(row),
        y=int(meta["y"]),
        x=int(meta["x"]),
        truth=truth,
        p=float(population["p"][meta["global_row"]]),
        q32=q32,
        a0=float(population["a0"][meta["global_row"]]),
        split_min=None if not np.isfinite(split_min) else float(split_min),
        blend_fraction=None if blend_fraction is None else float(blend_fraction),
        new_A=None if new_a is None else float(new_a),
        activated=bool(activated_nodes is not None),
        strong=bool(truth > float(THRESHOLD)),
        weak=bool(float(RAIN_THRESHOLD) < truth <= float(WEAK_UPPER)),
        infeasible_reason=reason,
    )
    if activated_nodes is not None:
        nodes = np.expm1(qlog)
        old = float(physical_pinball_nodes_over20(np.asarray([truth]), nodes[None, :])[0])
        new = float(physical_pinball_nodes_over20(
            np.asarray([truth]), np.asarray(activated_nodes, dtype=np.float64)[None, :])[0])
        record["normalized_pinball_change"] = new - old
    else:
        record["normalized_pinball_change"] = None
    return record


def run(proposal, private, output, verify_file, *, expected=None, deadline=None):
    """Execute the deterministic nine-gate acceptance over the saved population."""
    expected = FROZEN_EXPECTED if expected is None else expected
    proposal = dict(proposal)
    private = dict(private)
    if proposal.get("kind") != KIND or private.get("kind") != KIND:
        raise ValueError("Unexpected Stage-45 acceptance kind")
    if proposal.get("authorization_scope") != AUTHORIZATION_SCOPE:
        raise ValueError("Stage-45 authorization scope differs")
    if proposal.get("tasks") != [TASK]:
        raise ValueError("Stage-45 task differs")
    if proposal.get("authorized") is not False or proposal.get("final_2025_access") is not False:
        raise ValueError("Stage-45 proposal must remain unauthorized and 2025-frozen")
    if proposal.get("budget") != BUDGET:
        raise ValueError("Stage-45 budget differs from the frozen caps")
    if proposal_digest(proposal) != proposal.get("proposal_sha256"):
        raise ValueError("Stage-45 proposal digest changed")
    if private.get("proposal_sha256") != proposal.get("proposal_sha256"):
        raise ValueError("Private preparation proposal digest differs")
    if private_digest(private) != proposal.get("private_preparation_sha256"):
        raise ValueError("Private preparation digest changed")
    if not Path(output).is_dir():
        raise ValueError("Acceptance output namespace must exist before the core runs")
    arrays_files = private.get("arrays_files")
    if not isinstance(arrays_files, list) or not arrays_files:
        raise ValueError("Private array-shard list missing")
    satellite_entries = private.get("satellite_files")
    if not isinstance(satellite_entries, list) or not satellite_entries:
        raise ValueError("Private satellite list missing")
    arrays_bytes = sum(int(entry["bytes"]) for entry in arrays_files)
    satellite_bytes = sum(int(entry["bytes"]) for entry in satellite_entries)
    if arrays_bytes != int(expected["arrays_bytes"]):
        raise ValueError("Declared array bytes differ from the frozen reference")
    if satellite_bytes != int(expected["satellite_bytes"]):
        raise ValueError("Declared satellite bytes differ from the frozen reference")
    if arrays_bytes + satellite_bytes > BUDGET["maximum_reference_bytes"]:
        raise ValueError("Declared reference bytes exceed the frozen cap")
    if len(arrays_files) + len(satellite_entries) > BUDGET["maximum_scientific_file_opens"]:
        raise ValueError("Declared scientific file opens exceed the frozen cap")
    deadline = deadline or Deadline(BUDGET["maximum_seconds"])
    guard = _ReadGuard(verify_file, deadline, BUDGET["maximum_scientific_file_opens"],
                       BUDGET["maximum_reference_bytes"])
    population = load_population(
        arrays_files, Path(private["arrays_dir"]),
        lambda path, size, sha: guard(path, size, sha), deadline)
    counts = counts_from_population(population)
    metrics = metrics_from_population(population)
    _compare_expected(counts, expected["counts"], "counts")
    _compare_expected(metrics, expected["metrics"], "baseline")
    if guard.scientific_bytes != arrays_bytes:
        raise ValueError("Array reads did not cover the declared array bytes")

    indices = sp04_membership(Path(private["code_root"]))
    satellite = _satellite_index(private, population)
    candidate_rows = population["candidate_rows"]
    split_min = np.full(len(population["p"]), -np.inf, dtype=np.float64)
    grouped = {}
    for candidate_index, meta in enumerate(population["candidate_meta"]):
        grouped.setdefault(meta["scene_index"], []).append(candidate_index)
    satellite_root = Path(private["satellite_root"])
    for scene in population["candidate_scene_ids"]:
        scene_index = population["scene_ids"].index(scene)
        candidate_indices = np.asarray(grouped[scene_index], dtype=np.int64)
        ys = np.asarray([population["candidate_meta"][index]["y"] for index in candidate_indices], dtype=np.int64)
        xs = np.asarray([population["candidate_meta"][index]["x"] for index in candidate_indices], dtype=np.int64)
        scene_values = np.full(len(candidate_indices), np.inf, dtype=np.float64)
        for slot in range(SLOTS):
            entry = satellite[scene][slot]
            path = satellite_root / entry["relative_path"].replace("\\", "/")
            content = guard(path, entry["bytes"], entry["sha256"])
            value08, valid08 = read_band(content, "08")
            value13, valid13 = read_band(content, "13")
            mean08 = sp04_area_mean(value08, valid08, indices)
            mean13 = sp04_area_mean(value13, valid13, indices)
            split = mean08 - mean13
            values = split[ys, xs].astype(np.float64)
            scene_values = np.minimum(scene_values, values)
        split_min[candidate_rows[candidate_indices]] = scene_values
        deadline.check()
    if guard.scientific_bytes != arrays_bytes + satellite_bytes:
        raise ValueError("Scientific reads did not cover the declared reference bytes")

    a0 = population["a0"]
    truth = population["truth"]
    p = population["p"]
    q32 = population["q32"]
    candidate_mask = np.zeros(len(p), dtype=bool)
    candidate_mask[candidate_rows] = True
    selected = (candidate_mask
                & (a0.astype(np.float64) >= A0_THRESHOLD)
                & (split_min >= SPLIT_THRESHOLD))
    row_to_candidate = {int(row): index for index, row in enumerate(candidate_rows)}
    selected_indices = np.asarray(
        [row_to_candidate[int(row)] for row in np.flatnonzero(selected)], dtype=np.int64)
    activated = {}
    infeasible = {}
    reasons = {}
    for index in selected_indices:
        index = int(index)
        meta = population["candidate_meta"][index]
        qlog = population["candidate_qlog"][index]
        nodes = np.expm1(qlog)
        probability = float(p[meta["global_row"]])
        blended = blend_to_top(nodes, probability)
        if blended[0] is None:
            infeasible[index] = blended[1]
            reasons[index] = (None, None, blended[1])
        else:
            activated[index] = blended
            reasons[index] = (blended[1], blended[2], None)
        deadline.check()

    new_a_all = a0.copy()
    strong = population["strong"]
    for index, (blended, fraction, new_a) in activated.items():
        new_a_all[population["candidate_meta"][index]["global_row"]] = new_a
    strong_pin = physical_pinball_over20(truth[strong], population["strong_qlog"])
    strong_rows = np.flatnonzero(strong)
    strong_position = {int(row): position for position, row in enumerate(strong_rows)}
    for index, (blended, fraction, new_a) in activated.items():
        meta = population["candidate_meta"][index]
        if not strong[meta["global_row"]]:
            continue
        position = strong_position[int(meta["global_row"])]
        strong_pin[position] = float(physical_pinball_nodes_over20(
            np.asarray([float(truth[meta["global_row"]])]), blended[None, :])[0])
    gate1_candidate = float(strong_pin.mean())
    gate1_baseline = float(metrics["strong_physical_pinball_over20"])
    gate1_passed = gate1_candidate < gate1_baseline

    new_tp = int(((new_a_all > THRESHOLD) & strong).sum())
    new_fp = int(((new_a_all > THRESHOLD) & ~strong).sum())
    gate2_passed = new_tp >= 1
    gate3_passed = new_fp == 0

    new_q32_tp = int(((q32 > 20.0) & strong).sum())
    new_q32_fp = int(((q32 > 20.0) & ~strong).sum())
    gate4_passed = new_q32_tp == metrics["q32_support_tp"]
    gate5_passed = new_q32_fp == metrics["q32_support_fp"]
    weak_pin = weak_log_pinball(truth[population["weak"]], population["weak_qlog"])
    weak_rows = np.flatnonzero(population["weak"])
    weak_position = {int(row): position for position, row in enumerate(weak_rows)}
    for index, (blended, fraction, new_a) in activated.items():
        row = int(population["candidate_meta"][index]["global_row"])
        if row not in weak_position:
            continue
        delta_log = np.log1p(float(truth[row])) - np.log1p(blended)
        weak_pin[weak_position[row]] = float(_pinball_zero(delta_log))
    weak_candidate = float(weak_pin.mean())
    gate6_passed = weak_candidate == metrics["weak_log_pinball"]

    selected_meta = [population["candidate_meta"][index] for index in selected_indices]
    weak_selected = int(sum(1 for meta in selected_meta if population["weak"][meta["global_row"]]))
    nonstrong_selected = int(sum(1 for meta in selected_meta if not population["strong"][meta["global_row"]]))
    by_construction = dict(
        equal=True,
        status="BY_CONSTRUCTION_EQUAL",
        reason="The action leaves p and q32 fixed, so Brier, AP and AUROC are unchanged without recomputation.",
    )
    gates = [
        dict(gate=1, name="strong_physical_pinball_over20", baseline=gate1_baseline,
             candidate=gate1_candidate, delta=gate1_candidate - gate1_baseline,
             comparator="lt", passed=bool(gate1_passed), status="RECOMPUTED"),
        dict(gate=2, name="point_a_detection_restored",
             baseline=dict(tp=metrics["point_a_tp"], fp=metrics["point_a_fp"]),
             candidate=dict(tp=new_tp, fp=new_fp), requirement="candidate_tp>=1",
             delta=dict(tp=new_tp - metrics["point_a_tp"], fp=new_fp - metrics["point_a_fp"]),
             comparator="ge", passed=bool(gate2_passed)),
        dict(gate=3, name="point_a_false_positive_removed",
             baseline=dict(tp=metrics["point_a_tp"], fp=metrics["point_a_fp"]),
             candidate=dict(tp=new_tp, fp=new_fp), requirement="candidate_fp==0",
             delta=dict(tp=new_tp - metrics["point_a_tp"], fp=new_fp - metrics["point_a_fp"]),
             comparator="le", passed=bool(gate3_passed)),
        dict(gate=4, name="q32_support_true_positive_unchanged",
             baseline=metrics["q32_support_tp"], candidate=new_q32_tp,
             comparator="eq", passed=bool(gate4_passed)),
        dict(gate=5, name="q32_support_false_positive_unchanged",
             baseline=metrics["q32_support_fp"], candidate=new_q32_fp,
             comparator="eq", passed=bool(gate5_passed)),
        dict(gate=6, name="weak_log_pinball_unchanged",
             baseline=metrics["weak_log_pinball"], candidate=weak_candidate,
             comparator="eq", passed=bool(gate6_passed)),
        dict(gate=7, name="occurrence_brier_unchanged", baseline=metrics["occurrence_brier"],
             candidate=metrics["occurrence_brier"], **by_construction, passed=True),
        dict(gate=8, name="occurrence_ap_unchanged", baseline=metrics["occurrence_ap"],
             candidate=metrics["occurrence_ap"], **by_construction, passed=True),
        dict(gate=9, name="occurrence_auroc_unchanged", baseline=metrics["occurrence_auroc"],
             candidate=metrics["occurrence_auroc"], **by_construction, passed=True),
    ]
    failing = [gate["name"] for gate in gates if not gate["passed"]]
    if weak_selected:
        failing.append("weak_rows_selected")
    if nonstrong_selected:
        failing.append("nonstrong_rows_selected")
    passed = bool(gate1_passed and gate2_passed and gate3_passed and gate4_passed
                  and gate5_passed and gate6_passed and not weak_selected and not nonstrong_selected)

    ordered = sorted(selected_indices.tolist())
    rows = []
    for index in ordered[:MAX_SELECTED_ROWS]:
        index = int(index)
        blend_fraction, new_a, reason = reasons[index]
        activation = activated.get(index)
        rows.append(_row_record(population, index, split_min[population["candidate_meta"][index]["global_row"]], blend_fraction, new_a,
                                None if activation is None else activation[0], reason))
    infeasible_rows = [rows[position] for position, index in enumerate(ordered[:MAX_SELECTED_ROWS])
                       if int(index) in infeasible]
    deadline.check()
    result = dict(
        status="COMPLETE_STAGE45_DEV_ACCEPTANCE",
        kind=KIND,
        authorization_scope=AUTHORIZATION_SCOPE,
        task=TASK,
        proposal_sha256=proposal["proposal_sha256"],
        private_preparation_sha256=proposal["private_preparation_sha256"],
        execution_code_commit=proposal["execution_code_commit"],
        decision="PASS" if passed else "FAIL",
        failing_gates=failing,
        gates=gates,
        baseline_metrics=metrics,
        candidate_metrics=dict(
            strong_physical_pinball_over20=gate1_candidate,
            point_a_tp=new_tp,
            point_a_fp=new_fp,
            q32_support_tp=new_q32_tp,
            q32_support_fp=new_q32_fp,
            weak_log_pinball=weak_candidate,
            occurrence_brier=metrics["occurrence_brier"],
            occurrence_ap=metrics["occurrence_ap"],
            occurrence_auroc=metrics["occurrence_auroc"],
        ),
        counts=counts,
        selection=dict(
            rule="candidate AND a0 >= 9.5373 AND split_min >= 2.3612",
            candidate_rows=int(len(candidate_rows)),
            selected_rows=int(len(selected_indices)),
            feasible_rows=int(len(activated)),
            infeasible_rows=int(len(infeasible)),
            weak_rows_selected=weak_selected,
            nonstrong_rows_selected=nonstrong_selected,
        ),
        selected_rows=rows,
        selected_rows_total=int(len(selected_indices)),
        selected_rows_omitted=int(max(0, len(selected_indices) - len(rows))),
        infeasible_rows=infeasible_rows,
        accounting=dict(
            scientific_file_opens=guard.opens,
            scientific_reference_bytes=guard.scientific_bytes,
            array_files_read=len(arrays_files),
            satellite_files_read=len(satellite_entries),
            array_bytes_read=arrays_bytes,
            satellite_bytes_read=satellite_bytes,
            maximum_scientific_file_opens=BUDGET["maximum_scientific_file_opens"],
            maximum_reference_bytes=BUDGET["maximum_reference_bytes"],
            metadata_config_opens=3,
        ),
        elapsed_seconds=deadline.elapsed,
        final_2025_access=False,
        optimizer_updates=0,
        model_inference_passes=0,
        automatic_retry=False,
        scientific_status="NOT_VERIFIED",
        notes=[
            "Gates 7/8/9 are BY_CONSTRUCTION_EQUAL because the action fixes p and q32.",
            "Baselines were recomputed from the loaded arrays and matched the frozen preparation within 1e-12.",
            "The real acceptance execution remains subject to a separate researcher approval file.",
        ],
    )
    return result
