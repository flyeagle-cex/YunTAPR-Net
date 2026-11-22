"""Test the run boundary and exact pixel alignment on generated arrays."""

from datetime import datetime, timedelta
from functools import partial
from hashlib import sha256
from io import BytesIO
import json
import math
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import numpy as np

from tools.research_readiness import run_orographic_separability as runner
from yuntapr.experimental.core_innovation.gfs import Field, ForecastIdentity, GFSFile
from yuntapr.experimental.core_innovation.grid import GridSpec
from yuntapr.experimental.core_innovation.terrain import TerrainFeatures


def synthetic_shard():
    scenes = np.array(["a", "b", "c"])
    mask = np.zeros((3, 100, 100), dtype=bool)
    mask[:, 0, 2] = mask[:, 1, 1] = True
    digest = sha256()
    for scene in scenes:
        digest.update((1).to_bytes(4, "big"))
        digest.update(str(scene).encode())
        digest.update(np.asarray((100, 100), dtype="<i8").tobytes())
        digest.update(mask[0].tobytes())
    stream = BytesIO()
    np.savez(stream, scene_ids=scenes, supervision_mask=mask,
             p=np.full(6, .64, dtype=np.float32),
             truth_mm_h=np.array([21, 2, 35, 65, 1, 2], dtype=np.float32),
             qlog=np.array([np.linspace(.2, math.log1p(q), 32) for q in (23, 22, 22, 20, 22, 20)]))
    ids = [{"sample_id": str(scene)} for scene in scenes]
    binding = dict(source_by_scene=ids, prediction_shards=[
        dict(file="batch_000.npz", scenes=3, scene_start=0, n_valid=6),
    ], receipt={"supervision_mask_sha256": digest.hexdigest()})
    return binding, stream.getvalue()


class OrographicExecutionTests(unittest.TestCase):
    def test_full_population_gates_feature_reads_and_preserves_pixel_order(self):
        binding, raw = synthetic_shard()
        batch, skipped = runner.scan_predictions(binding, lambda _: raw, cells_per_scene=2,
                                                  counts=(6, 3, 2, 2))
        self.assertEqual(tuple(batch), ("a",))
        np.testing.assert_array_equal(batch["a"][0], [2, 101])
        self.assertEqual(skipped, dict(strong=1, non_strong=1,
                                       strong_by_rainfall={"(20,30]": 0, "(30,50]": 1, "(50,inf)": 0}))
        shape = (100, 100)
        motion = np.full(shape, .1)
        motion[0, 2] = .3
        fields = (np.full(shape, 2100), np.full(shape, .1), np.full(shape, 30),
                  motion, np.ones(shape, dtype=bool))
        with patch.object(runner, "MIN_MATCHED", (1, 1)):
            result = runner.evaluate(batch, {"a": "one-source"}, lambda _: fields, fields[-1])
            self.assertEqual(runner.conclude(result), "DESCRIPTIVE_SIGNAL_ONLY")
            self.assertEqual(result["strong_coverage_by_rainfall"]["matched"]["(20,30]"], 1)
        with self.assertRaisesRegex(ValueError, "population"):
            runner.scan_predictions(binding, lambda _: raw, cells_per_scene=2, counts=(6, 3, 2, 3))

    def test_original_pressure_mask_excludes_at_ground(self):
        grid = GridSpec([25, 26], [100, 101])
        shape = grid.shape
        valid = np.ones(shape, dtype=bool)
        slope_x, slope_y = np.full(shape, .1), np.full(shape, .2)
        terrain = TerrainFeatures(grid, np.full(shape, 2100), valid, slope_x, slope_y,
                                  valid, np.zeros(shape), np.zeros(shape), valid)
        init = datetime.fromisoformat("2024-03-01T00:00:00+00:00")
        lead = timedelta(hours=6)
        pressure = np.full(shape, 90000.)
        pressure[0, 1] = 70000.
        forecast = GFSFile(ForecastIdentity(init, lead, init + lead), grid, {
            "u700": Field(np.full(shape, 3.), valid, "u", "m/s", 70000.),
            "v700": Field(np.full(shape, 4.), valid, "v", "m/s", 70000.),
            "ps": Field(pressure, valid, "surface_pressure", "Pa", None),
            "pwat": Field(np.full(shape, 35.), valid, "precipitable_water", "kg m-2", None),
        }, {})
        _, _, pwat, motion, mask = runner.physical_columns(forecast, terrain)
        np.testing.assert_allclose(motion[mask], 1.1)
        self.assertFalse(mask[0, 1])
        self.assertTrue(np.isnan(motion[0, 1]))
        np.testing.assert_allclose(pwat, 35.)

    def test_bad_hash_consumes_only_one_reserved_read(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "generated"
            path.write_bytes(b"data")
            meter = runner.Meter(dict(max_seconds=60, gfs_main_bytes_max=4, gfs_main_opens_max=1))
            with self.assertRaisesRegex(ValueError, "content differs"):
                meter.read(path, dict(bytes=4, sha256="a" * 64), "gfs_main")
            with self.assertRaisesRegex(ValueError, "quota"):
                meter.read(path, dict(bytes=4, sha256=sha256(b"data").hexdigest()), "gfs_main")
            self.assertEqual(meter.ledger, dict(gfs_main_bytes=4, gfs_main_opens=1))

    def test_stale_grant_rejected_before_allowlist_or_attempt(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder).resolve()
            plan = dict(authorization_scope=runner.SCOPE, budget={"max_seconds": 600},
                        proposal_sha256="new")
            (root / "OROGRAPHIC_EXECUTION_PROPOSAL_V1.json").write_text(json.dumps(plan), encoding="utf-8")
            grant = dict(plan, approved_by_researcher=True, decision_id="old", run_folder=str(root),
                         proposal_sha256="old")
            (root / "RESEARCHER_APPROVAL.json").write_text(json.dumps(grant), encoding="utf-8")
            with (
                patch.multiple(runner, DOCS=root, RUN=root, ALLOWLIST=root / "must-not-be-opened"),
                patch.object(runner, "build_proposal", return_value=plan),
            ):
                with self.assertRaisesRegex(PermissionError, "Separate approval"):
                    runner.execute()
            self.assertFalse((root / "output").exists())

    def test_authorized_generated_run_resolves_same_receipt_and_runs_once(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder).resolve()
            binding, shard = synthetic_shard()
            receipt = binding.pop("receipt")
            (root / "batch_000.npz").write_bytes(shard)
            static = b"synthetic terrain"
            (root / "static.npz").write_bytes(static)
            binding["prediction_shards"][0].update(bytes=len(shard), sha256=sha256(shard).hexdigest())
            for row in binding["source_by_scene"]:
                row["bytes"] = 1
            binding.update(prediction_folder=str(root), static_pack={
                "path": str(root / "static.npz"), "bytes": len(static), "sha256": sha256(static).hexdigest(),
            })
            receipt["private_allowlist_sha256"] = runner._digest(binding)
            binding["receipt"] = receipt
            allowlist = root / "allowlist.json"
            allowlist.write_text(json.dumps(binding), encoding="utf-8")
            plan = dict(authorization_scope=runner.SCOPE, proposal_sha256="generated",
                        source_binding_sha256=runner._digest(receipt), budget=dict(
                            max_seconds=60, saved_array_opens=1, saved_array_bytes=len(shard),
                            gfs_main_opens_max=1, gfs_main_bytes_max=1,
                            static_pack_opens_max=1, static_pack_bytes_max=len(static),
                        ))
            (root / "OROGRAPHIC_EXECUTION_PROPOSAL_V1.json").write_text(json.dumps(plan), encoding="utf-8")
            grant = dict(plan, approved_by_researcher=True, decision_id="generated", run_folder=str(root))
            (root / "RESEARCHER_APPROVAL.json").write_text(json.dumps(grant), encoding="utf-8")
            shape = (100, 100)
            region = np.ones(shape, dtype=bool)
            fields = (np.full(shape, 2100), np.full(shape, .1), np.full(shape, 30), np.full(shape, .25), region)
            with (
                patch.multiple(runner, DOCS=root, RUN=root, ALLOWLIST=allowlist, COUNTS=(6, 3, 2, 2)),
                patch.object(runner, "build_proposal", return_value=plan),
                patch.object(runner, "scan_predictions",
                             partial(runner.scan_predictions, counts=(6, 3, 2, 2), cells_per_scene=2)),
                patch.object(runner, "load_terrain", return_value=(None, region)),
                patch.object(runner, "_read_forecast", return_value=fields) as forecast,
            ):
                result = runner.execute()
                with self.assertRaises(FileExistsError):
                    runner.execute()
            self.assertEqual(result["actual_reads"]["saved_array_opens"], 1)
            self.assertEqual(result["actual_reads"]["static_pack_opens"], 1)
            self.assertEqual(forecast.call_count, 1)
            self.assertEqual(result["decision"], "STOP_INSUFFICIENT_MATCHED_COVERAGE")
            self.assertEqual({path.name for path in (root / "output").iterdir()}, {"completion.json"})


if __name__ == "__main__":
    unittest.main()
