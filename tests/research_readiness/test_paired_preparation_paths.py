"""Regression checks for task references through alternate path spellings."""
from pathlib import Path
import tempfile
import unittest

from tools.research_readiness.prepare_paired_point_evaluation import canonical_task_bindings
from tools.research_readiness.start_paired_point_evaluation import LIMITS


class PreparationPathTests(unittest.TestCase):
    def test_corrective_allowances_include_consumed_preflight(self):
        limits = LIMITS
        roles = 2 * limits["metadata_bytes_per_preflight"] + limits["metadata_bytes_controller"] + 2 * limits["metadata_bytes_per_worker"]
        self.assertLessEqual(roles, limits["total_metadata_cap_bytes"])
        self.assertEqual(limits["total_source_cap_bytes"] + limits["previous_attempt_metadata_bytes"] + limits["previous_attempt_payload_bytes"],
                         limits["cumulative_source_cap_bytes"])
        opens = 2 * limits["metadata_opens_per_preflight"] + limits["metadata_opens_controller"] + 2 * limits["metadata_opens_per_worker"]
        self.assertLessEqual(opens + limits["previous_attempt_metadata_opens"], limits["cumulative_metadata_opens"])
        self.assertLessEqual(opens + limits["payload_open_instances"] + limits["previous_attempt_metadata_opens"] + limits["previous_attempt_payload_opens"], limits["cumulative_total_opens"])
        self.assertEqual(limits["maximum_seconds"] + limits["previous_attempt_seconds"], 7200)

    def test_alias_references_close_over_canonical_manifests(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "alias").mkdir()
            checkpoint, report = root / "weight.pt", root / "report.json"
            checkpoint.write_bytes(b"synthetic-not-a-model")
            report.write_text("{}", encoding="utf-8")
            tasks = {"CONTROL_E0": dict(checkpoint_path=str(root / "alias/../weight.pt"),
                                        dev_report_path=str(root / "alias/../report.json"))}
            scientific, metadata = {str(checkpoint.resolve()): {}}, {str(report.resolve()): {}}
            bound = canonical_task_bindings(tasks, scientific, metadata)["CONTROL_E0"]
            self.assertIn(bound["checkpoint_path"], scientific)
            self.assertIn(bound["dev_report_path"], metadata)
            self.assertEqual(tasks["CONTROL_E0"]["checkpoint_path"], str(root / "alias/../weight.pt"))
            for sources, reports in (({}, metadata), (scientific, {})):
                with self.assertRaisesRegex(ValueError, "absent"):
                    canonical_task_bindings(tasks, sources, reports)


if __name__ == "__main__":
    unittest.main()
