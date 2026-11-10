"""Synthetic JSON/SQLite checks for the read-only single-model cosine9 page."""

import copy
from contextlib import closing
import importlib.util
import json
from pathlib import Path
import shutil
import sqlite3
import unittest
from unittest.mock import patch
from uuid import uuid4


ROOT = Path(__file__).resolve().parents[2]
definition = importlib.util.spec_from_file_location("cosine9_monitor", ROOT / "tools/b2_monitor/server.py")
monitor = importlib.util.module_from_spec(definition)
definition.loader.exec_module(monitor)

EXECUTION_COMMIT = "e54ccc16f988628e2dc6c4b91f76051ae94c4629"
PROPOSAL_SHA256 = "6e4910938eedca317d68cd047563b6c3e31868529d7fc52b52936b1c5e60642f"
TEMP_ROOT = ROOT / ".pytest_cache/cosine9_monitor_agent_20261110_01"


def write_json(path, value):
    path.write_text(json.dumps(value), encoding="utf-8")


class Cosine9MonitorTests(unittest.TestCase):
    def setUp(self):
        TEMP_ROOT.mkdir(parents=True, exist_ok=True)
        self.output = (TEMP_ROOT / ("synthetic_" + uuid4().hex)).resolve()
        self.output.mkdir()
        self.assertEqual(self.output.parent, TEMP_ROOT.resolve())
        self.addCleanup(self.cleanup_output)
        self.addCleanup(patch.stopall)
        patch.object(monitor.base, "process_token", return_value=134000000000000000).start()
        patch.object(monitor, "process_exited", return_value=False).start()
        self.resources = patch.object(monitor.base, "resources").start()

    def cleanup_output(self):
        self.assertEqual(self.output.resolve().parent, TEMP_ROOT.resolve())
        self.assertTrue(self.output.name.startswith("synthetic_"))
        shutil.rmtree(self.output)

    def fixture(self, returned=17, intents=0, sealed_epochs=0, completed=False):
        approval = {
            "code_commit": EXECUTION_COMMIT, "proposal_sha256": PROPOSAL_SHA256,
            "approved_by_researcher": True,
            "tasks": [{"model": "B7", "seed": 2029, "schedule_profile": "COSINE9_V1"}],
            "budget": {
                "models": 1, "updates_per_model": 4320, "total_updates": 4320,
                "source_bytes_per_model": 477571953840, "total_source_bytes": 477571953840,
                "source_files_per_model": 142813, "total_source_files": 142813,
                "max_model_seconds": 21600, "max_package_seconds": 21600,
                "initial_free_bytes": 24 * 1024**3, "minimum_task_free_bytes": 24 * 1024**3,
                "replay_allowance": 0, "additional_retry_allowance": 0, "checkpoint_loads": 0,
            },
        }
        binding = {"controller_pid": 123, "approval": approval}
        write_json(self.output / "authorization_binding.json", binding)
        folder = self.output / "B7_s2029"
        folder.mkdir()
        with closing(sqlite3.connect(folder / "updates.sqlite")) as db:
            db.execute("CREATE TABLE updates(model TEXT,u INTEGER,state TEXT)")
            db.executemany("INSERT INTO updates VALUES (?,?,?)",
                           [("B7", update, "RETURNED") for update in range(1, returned + 1)]
                           + [("B7", update, "INTENT") for update in range(returned + 1, returned + intents + 1)])
            db.commit()
        for path, size in ((self.output / "B7_static_source.sqlite", 312828),
                           (folder / "B7_train_reads_01/reads.sqlite", 1234)):
            path.parent.mkdir(exist_ok=True)
            with closing(sqlite3.connect(path)) as db:
                db.execute("CREATE TABLE file_io(actual_bytes INTEGER,expected_bytes INTEGER)")
                db.execute("INSERT INTO file_io VALUES (?,?)", (size, size))
                db.commit()
        for epoch in range(1, sealed_epochs + 1):
            write_json(folder / f"B7_LAST_epoch_{epoch:02d}.receipt.json",
                       {"checkpoint_sha256": f"SYNTHETIC_EPOCH_{epoch}"})
        if completed:
            completion = {"status": "COMPLETE_TRAIN_AND_DEV_EVALUATION"}
            write_json(folder / "completion.json", completion)
            write_json(self.output / "completion.json", completion)
        return binding

    def test_single_model_limits_updates_and_static_source_are_counted_once(self):
        self.fixture(returned=17, intents=1)
        reader = monitor.CampaignReader(self.output, 123)
        snapshot = reader.snapshot(include_resources=False)
        self.assertEqual(snapshot["state"], "RUNNING")
        self.assertTrue(snapshot["read_only"])
        self.assertTrue(snapshot["cosine9"])
        self.assertFalse(snapshot["upper_quantile"])
        self.assertEqual(snapshot["source_commit"], EXECUTION_COMMIT)
        self.assertEqual((snapshot["returned"], snapshot["reserved"], snapshot["uncertain"]), (17, 18, 1))
        self.assertEqual(len(snapshot["runs"]), 1)
        run = snapshot["runs"][0]
        self.assertEqual((run["model"], run["seed"], run["name"]), ("B7", 2029, "B7_s2029"))
        self.assertEqual(len(run["epochs"]), 9)
        self.assertEqual(snapshot["limits"], {
            "updates": 4320, "bytes": 477571953840, "files": 142813, "epochs": 9, "seconds": 21600,
        })
        self.assertEqual(snapshot["io"], {"files": 2, "bytes": 314062, "reserved_bytes": 314062, "sealed": 0})
        reader.cached_at = 0
        again = reader.snapshot(include_resources=False)
        self.assertEqual(again["io"], snapshot["io"])
        self.assertEqual(again["returned"], 17)
        self.resources.assert_not_called()

    def test_complete_requires_all_updates_and_nine_seals_and_displays_saved_summary(self):
        self.fixture(returned=4320, sealed_epochs=9, completed=True)
        summary = {"screen_passed": False, "scientific_acceptance": "NOT_VERIFIED", "synthetic": True}
        write_json(self.output / "paired_schedule_summary.json", summary)
        snapshot = monitor.CampaignReader(self.output, 123).snapshot(include_resources=False)
        self.assertEqual(snapshot["state"], "COMPLETE")
        self.assertEqual(snapshot["completed_models"], 1)
        self.assertEqual(snapshot["sealed_epochs"], 9)
        self.assertEqual((snapshot["returned"], snapshot["reserved"]), (4320, 4320))
        self.assertEqual(snapshot["runs"][0]["state"], "COMPLETE")
        self.assertTrue(all(epoch["phase"] == "SEALED" for epoch in snapshot["runs"][0]["epochs"]))
        self.assertEqual(snapshot["paired_summary"], summary)
        self.assertEqual(snapshot["io"]["bytes"], 312828 + 1234)

    def test_completion_json_alone_does_not_complete_an_unsealed_run(self):
        self.fixture(returned=4320, sealed_epochs=8, completed=True)
        snapshot = monitor.CampaignReader(self.output, 123).snapshot(include_resources=False)
        self.assertNotEqual(snapshot["state"], "COMPLETE")
        self.assertNotEqual(snapshot["runs"][0]["state"], "COMPLETE")
        self.assertEqual(snapshot["sealed_epochs"], 8)
        self.assertEqual(snapshot["completed_models"], 0)

    def test_saved_failure_marks_single_run_failed_without_losing_counters(self):
        self.fixture(returned=17, intents=1)
        write_json(self.output / "failure.json", {"status": "STOP_NO_AUTOMATIC_RETRY"})
        snapshot = monitor.CampaignReader(self.output, 123).snapshot(include_resources=False)
        self.assertEqual(snapshot["state"], "FAILED")
        self.assertEqual(snapshot["runs"][0]["state"], "FAILED")
        self.assertEqual((snapshot["returned"], snapshot["reserved"]), (17, 18))

    def test_changed_binding_is_rejected_before_ledger_queries(self):
        binding = self.fixture()
        changes = [
            ("binding", "controller_pid", 124),
            ("approval", "code_commit", "SYNTHETIC_WRONG"),
            ("approval", "proposal_sha256", "SYNTHETIC_WRONG"),
            ("task", "model", "B8"), ("task", "seed", 2030),
            ("task", "schedule_profile", "ORIGINAL_COSINE50"),
            ("budget", "total_updates", 8640),
            ("budget", "total_source_bytes", 477571953841),
            ("budget", "total_source_files", 142814),
            ("budget", "replay_allowance", 1),
            ("budget", "max_package_seconds", 21601),
        ]
        for section, key, value in changes:
            changed = copy.deepcopy(binding)
            if section == "binding":
                changed[key] = value
            elif section == "task":
                changed["approval"]["tasks"][0][key] = value
            elif section == "budget":
                changed["approval"]["budget"][key] = value
            else:
                changed["approval"][key] = value
            write_json(self.output / "authorization_binding.json", changed)
            with self.subTest(section=section, key=key), \
                    patch.object(monitor.base, "query", side_effect=AssertionError("No ledger query expected")) as query:
                with self.assertRaises(ValueError):
                    monitor.CampaignReader(self.output, 123)
                query.assert_not_called()


if __name__ == "__main__":
    unittest.main()
