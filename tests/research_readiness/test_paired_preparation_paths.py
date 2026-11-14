"""Regression checks for task references through alternate path spellings."""
from pathlib import Path
import tempfile
import unittest

from tools.research_readiness.prepare_paired_point_evaluation import canonical_task_bindings


class PreparationPathTests(unittest.TestCase):
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
