"""Synthetic tests for the bounded Stage-45 Dev nine-gate acceptance core."""

import hashlib
import io
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools" / "research_readiness"))

import stage45_dev_acceptance as core  # noqa: E402


def _sha(data):
    return hashlib.sha256(data).hexdigest()


def _expected_metrics(p, qlog, truth):
    nodes = np.expm1(qlog)
    strong = truth > np.float32(20.0)
    rain = truth > np.float32(0.1)
    weak = (truth > np.float32(0.1)) & (truth <= np.float32(1.0))
    strong_pinball = []
    for row in np.flatnonzero(strong):
        error = float(truth[row]) - nodes[row]
        strong_pinball.append(float(np.maximum(core.TAU * error, (core.TAU - 1) * error).mean()) / 20.0)
    weak_pinball = []
    for row in np.flatnonzero(weak):
        delta = np.log1p(float(truth[row])) - qlog[row]
        weak_pinball.append(float(np.maximum(core.TAU * delta, (core.TAU - 1) * delta).mean()))
    p64 = p.astype(np.float64)
    brier = float(np.square(p64 - rain.astype(np.float64)).mean())
    ap, auroc = _brute_rank(p, rain)
    q32 = nodes[:, -1]
    a0 = np.float32(p64 * nodes.mean(axis=1))
    return dict(
        strong_physical_pinball_over20=float(np.mean(strong_pinball)),
        q32_support_tp=int(((q32 > 20.0) & strong).sum()),
        q32_support_fp=int(((q32 > 20.0) & ~strong).sum()),
        point_a_tp=int(((a0 > np.float32(20.0)) & strong).sum()),
        point_a_fp=int(((a0 > np.float32(20.0)) & ~strong).sum()),
        weak_log_pinball=float(np.mean(weak_pinball)),
        occurrence_brier=brier,
        occurrence_ap=ap,
        occurrence_auroc=auroc,
    )


def _brute_rank(p, rain):
    score = p.astype(np.float32)
    order = np.argsort(score, kind="stable")[::-1]
    ordered = score[order]
    labels = rain[order]
    ends = np.r_[np.flatnonzero(ordered[:-1] != ordered[1:]), len(order) - 1]
    cumulative = np.cumsum(labels, dtype=np.int64)[ends]
    previous = 0
    ap = 0.0
    for position, end in enumerate(ends):
        positives = int(cumulative[position] - previous)
        ap += positives * float(cumulative[position]) / float(end + 1)
        previous = int(cumulative[position])
    n_pos = int(labels.sum())
    n_neg = int((~labels).sum())
    ap /= n_pos
    pos = np.flatnonzero(rain)
    neg = np.flatnonzero(~rain)
    wins = 0.0
    for index in pos:
        values = p[index] - p[neg]
        wins += float((values > 0).sum()) + .5 * float((values == 0).sum())
    return float(ap), float(wins / (n_pos * n_neg))


def _netcdf_temp_base():
    """Pick an ASCII temporary directory.

    netCDF4/HDF5 on this Windows build cannot create files under a path that
    contains non-ASCII characters, and the repository lives under one.  The
    surrounding tests only need a scratch file, so use an ASCII system temp
    directory for the NetCDF payload.
    """
    candidates = [tempfile.gettempdir()]
    system_root = os.environ.get("SystemRoot")
    if system_root:
        candidates.append(os.path.join(system_root, "Temp"))
    candidates.append(r"C:\Users\Public")
    for candidate in candidates:
        if candidate and str(candidate).isascii() and Path(candidate).is_dir():
            return candidate
    return None


def _nc_bytes(split_map):
    import netCDF4

    base = _netcdf_temp_base()
    if base is None:
        raise unittest.SkipTest("no ASCII temporary directory for netCDF4 output")
    indices = core.sp04_membership(ROOT)
    native13 = np.full((501, 501), 280.0, dtype=np.float32)
    native08 = native13.copy()
    owner = np.repeat(np.arange(indices.shape[0], dtype=np.int64), indices.shape[1])
    split_values = split_map.reshape(-1)[owner].astype(np.float32)
    native08.reshape(-1)[indices.reshape(-1)] = native13.reshape(-1)[indices.reshape(-1)] + split_values
    with tempfile.TemporaryDirectory(dir=base) as folder:
        path = Path(folder) / "scene.nc"
        with netCDF4.Dataset(str(path), "w", format="NETCDF4") as dataset:
            dataset.createDimension("y", 501)
            dataset.createDimension("x", 501)
            variables = {}
            for band, values in (("08", native08), ("13", native13)):
                variable = dataset.createVariable(f"tbb_{band}", "f4", ("y", "x"),
                                                  fill_value=np.float32(-9999.0))
                variable.scale_factor = np.float32(1.0)
                variable.add_offset = np.float32(0.0)
                variable.valid_min = np.float32(0.0)
                variable.valid_max = np.float32(1000.0)
                variable.missing_value = np.float32(-9999.0)
                variable[:] = values
                variables[band] = variable
        return path.read_bytes()


def _scene_id():
    return "2024-01-01T00:00:00+00:00"


def _case(tmp, rows, n_weak_fill=370):
    """rows: list of dict(q32, truth, p, split) placed at the first mask rows."""
    mask = np.zeros((100, 100), dtype=bool)
    mask.reshape(-1)[:3430] = True
    p = np.full(3430, .05, dtype=np.float32)
    truth = np.zeros(3430, dtype=np.float32)
    qlog = np.repeat(np.log1p(np.linspace(.01, 10.0, 32, dtype=np.float64))[None, :], 3430, axis=0)
    split = np.ones((100, 100), dtype=np.float32)
    ys, xs = np.nonzero(mask)
    for row_index, spec in enumerate(rows):
        p[row_index] = np.float32(spec["p"])
        truth[row_index] = np.float32(spec["truth"])
        nodes = np.linspace(1.0, 30.0, 31, dtype=np.float64)
        qlog[row_index] = np.log1p(np.r_[nodes, spec["q32"]])
        split[ys[row_index], xs[row_index]] = np.float32(spec["split"])
    fill = len(rows)
    weak = mask.reshape(-1).copy()
    weak[:fill] = False
    weak_positions = np.flatnonzero(weak)[:n_weak_fill]
    truth[weak_positions] = np.float32(.5)
    nc = _nc_bytes(split)
    arrays_buffer = io.BytesIO()
    np.savez(arrays_buffer, scene_ids=np.asarray([_scene_id()], dtype="<U25"),
             supervision_mask=mask[None, :, :], p=p, qlog=qlog, truth_mm_h=truth)
    arrays_bytes = arrays_buffer.getvalue()
    arrays_dir = tmp / "arrays"
    arrays_dir.mkdir()
    (arrays_dir / "batch_000.npz").write_bytes(arrays_bytes)
    satellite_root = tmp / "satellite"
    satellite_root.mkdir()
    satellite_files = []
    for slot in range(6):
        satellite_files.append(dict(
            scene=_scene_id(), slot=slot,
            nominal=f"2024-01-01T0{slot}:00:00+00:00",
            relative_path=f"sat/slot{slot}.nc",
            bytes=len(nc), sha256=_sha(nc),
        ))
    objects = {"batch_000.npz": arrays_bytes}
    for slot in range(6):
        objects[f"slot{slot}.nc"] = nc

    def verify_file(path):
        name = Path(path).name
        data = objects[name]
        return data, _sha(data)

    proposal = dict(
        kind=core.KIND, authorization_scope=core.AUTHORIZATION_SCOPE,
        tasks=[dict(core.TASK)], authorized=False, final_2025_access=False,
        budget=dict(core.BUDGET), execution_code_commit="0" * 40,
        proposal_sha256="", private_preparation_sha256="",
    )
    private = dict(
        kind=core.KIND, arrays_dir=str(arrays_dir), arrays_files=[dict(
            file="batch_000.npz", scene_start=0, scenes=1, n_valid=3430,
            bytes=len(arrays_bytes), sha256=_sha(arrays_bytes))],
        satellite_root=str(satellite_root), satellite_files=satellite_files,
        code_root=str(ROOT), proposal_sha256="",
    )
    proposal["private_preparation_sha256"] = core.private_digest(private)
    proposal["proposal_sha256"] = core.proposal_digest(proposal)
    private["proposal_sha256"] = proposal["proposal_sha256"]
    counts = dict(
        scenes=1, n_valid=3430,
        n_rain=int((truth > np.float32(.1)).sum()),
        n_strong=int((truth > np.float32(20.0)).sum()),
        n_weak=int((((truth > np.float32(.1)) & (truth <= np.float32(1.0))).sum())),
        n_candidates=int((p.astype(np.float64) * np.expm1(qlog[:, -1]) > 20.0).sum()),
        n_candidate_strong=int(((p.astype(np.float64) * np.expm1(qlog[:, -1]) > 20.0)
                                & (truth > np.float32(20.0))).sum()),
        n_candidate_scenes=1,
    )
    expected = dict(metrics=_expected_metrics(p, qlog, truth), counts=counts,
                    arrays_bytes=len(arrays_bytes), satellite_bytes=6 * len(nc))
    output = tmp / "output"
    output.mkdir()
    return proposal, private, output, verify_file, expected


def _run(tmp, rows, n_weak_fill=370):
    proposal, private, output, verify_file, expected = _case(tmp, rows, n_weak_fill)
    return core.run(proposal, private, output, verify_file, expected=expected)


class Stage45AcceptanceTests(unittest.TestCase):
    def test_pass_scenario_and_bounded_rows(self):
        with tempfile.TemporaryDirectory() as folder:
            rows = [dict(q32=40.0, truth=60.0, p=.8, split=10.0) for _ in range(60)]
            result = _run(Path(folder), rows)
        self.assertEqual(result["decision"], "PASS")
        self.assertTrue(result["gates"][0]["passed"])
        self.assertEqual(result["candidate_metrics"]["point_a_tp"], 60)
        self.assertEqual(result["candidate_metrics"]["point_a_fp"], 0)
        self.assertEqual(len(result["selected_rows"]), 50)
        self.assertEqual(result["selected_rows_total"], 60)
        self.assertEqual(result["selected_rows_omitted"], 10)
        self.assertTrue(all(row["activated"] for row in result["selected_rows"]))
        self.assertTrue(all(0 < row["blend_fraction"] < 1 for row in result["selected_rows"]))
        self.assertTrue(all(abs(row["new_A"] - 20.01) < 1e-3 for row in result["selected_rows"]))
        self.assertTrue(all(row["normalized_pinball_change"] < 0 for row in result["selected_rows"]))
        self.assertEqual(result["gates"][6]["status"], "BY_CONSTRUCTION_EQUAL")
        self.assertTrue(result["gates"][6]["equal"])
        json.dumps(result, allow_nan=False)

    def test_nonstrong_selected_fails_gate3(self):
        with tempfile.TemporaryDirectory() as folder:
            rows = [dict(q32=40.0, truth=60.0, p=.8, split=10.0),
                    dict(q32=40.0, truth=19.0, p=.8, split=10.0)]
            result = _run(Path(folder), rows)
        self.assertEqual(result["decision"], "FAIL")
        self.assertEqual(result["candidate_metrics"]["point_a_fp"], 1)
        self.assertFalse(result["gates"][2]["passed"])
        self.assertIn("nonstrong_rows_selected", result["failing_gates"])

    def test_no_selected_rows_fails_gate2(self):
        with tempfile.TemporaryDirectory() as folder:
            rows = [dict(q32=40.0, truth=60.0, p=.8, split=1.0) for _ in range(60)]
            result = _run(Path(folder), rows)
        self.assertEqual(result["selection"]["selected_rows"], 0)
        self.assertEqual(result["decision"], "FAIL")
        self.assertFalse(result["gates"][1]["passed"])
        self.assertIn("point_a_detection_restored", result["failing_gates"])

    def test_infeasible_action_is_reported_not_activated(self):
        with tempfile.TemporaryDirectory() as folder:
            rows = [dict(q32=40.0, truth=60.0, p=.8, split=10.0),
                    dict(q32=30.5, truth=60.0, p=.656, split=10.0)]
            result = _run(Path(folder), rows)
        self.assertEqual(result["selection"]["feasible_rows"], 1)
        self.assertEqual(result["selection"]["infeasible_rows"], 1)
        self.assertEqual(len(result["infeasible_rows"]), 1)
        infeasible = result["infeasible_rows"][0]
        self.assertFalse(infeasible["activated"])
        self.assertIsNone(infeasible["new_A"])
        self.assertIsNone(infeasible["blend_fraction"])
        self.assertEqual(infeasible["infeasible_reason"],
                         "BLEND_FRACTION_OUTSIDE_OPEN_UNIT_INTERVAL")
        self.assertEqual(result["decision"], "PASS")

    def test_tau_pinball_and_point_match_brute_force(self):
        rng = np.random.default_rng(2029)
        qlog = np.log1p(np.sort(rng.uniform(0.01, 60.0, size=(7, 32)), axis=1))
        truth = rng.uniform(0.0, 80.0, size=7)
        nodes = np.expm1(qlog)
        for index in range(7):
            error = truth[index] - nodes[index]
            brute = np.mean([max(tau * error[i], (tau - 1) * error[i])
                             for i, tau in enumerate((np.arange(32) + .5) / 32)]) / 20.0
            self.assertAlmostEqual(float(core.physical_pinball_over20(truth[index:index + 1],
                                                                      qlog[index:index + 1])[0]),
                                   float(brute), places=14)
        for index in range(7):
            self.assertEqual(float(core.point_a(np.float32(.8), qlog[index])),
                             float(np.float32(float(np.float32(.8)) * nodes[index].mean())))

    def test_candidate_global_rows_span_multiple_shards(self):
        with tempfile.TemporaryDirectory() as folder:
            tmp = Path(folder)
            arrays = tmp / "arrays"
            arrays.mkdir()
            mask = np.zeros((100, 100), dtype=bool)
            mask.reshape(-1)[:3430] = True
            base_qlog = np.repeat(
                np.log1p(np.linspace(1.0, 30.0, 32, dtype=np.float64))[None, :], 3430, axis=0)
            entries = []
            for scene_index, scene in enumerate(("2024-01-01T00:00:00+00:00",
                                                  "2024-01-02T00:00:00+00:00")):
                p = np.full(3430, .05, dtype=np.float32)
                truth = np.zeros(3430, dtype=np.float32)
                qlog = base_qlog.copy()
                if scene_index == 1:
                    p[7] = np.float32(.8)
                    truth[7] = np.float32(60.0)
                    qlog[7] = np.log1p(np.r_[np.linspace(1.0, 30.0, 31), 40.0])
                buffer = io.BytesIO()
                np.savez(buffer, scene_ids=np.asarray([scene], dtype="<U25"),
                         supervision_mask=mask[None, :, :], p=p, qlog=qlog, truth_mm_h=truth)
                data = buffer.getvalue()
                name = f"batch_{scene_index:03d}.npz"
                (arrays / name).write_bytes(data)
                entries.append(dict(file=name, scene_start=scene_index, scenes=1, n_valid=3430,
                                    bytes=len(data), sha256=_sha(data)))
            population = core.load_population(
                entries, arrays, lambda path, size, sha: Path(path).read_bytes(),
                core.Deadline(10))
        self.assertEqual(population["candidate_rows"].tolist(), [3430 + 7])
        self.assertEqual(population["candidate_meta"][0]["global_row"], 3430 + 7)
        self.assertEqual(population["candidate_meta"][0]["y"],
                         int(np.nonzero(mask)[0][7]))
        self.assertEqual(population["candidate_scene_ids"],
                         ["2024-01-02T00:00:00+00:00"])
        self.assertTrue(bool(population["candidate_strong"][0]))

    def test_result_is_json_serializable(self):
        with tempfile.TemporaryDirectory() as folder:
            rows = [dict(q32=40.0, truth=60.0, p=.8, split=10.0)]
            result = _run(Path(folder), rows)
        payload = json.dumps(result, allow_nan=False)
        self.assertIn('"decision"', payload)
        self.assertIn("BY_CONSTRUCTION_EQUAL", payload)


if __name__ == "__main__":
    unittest.main()
