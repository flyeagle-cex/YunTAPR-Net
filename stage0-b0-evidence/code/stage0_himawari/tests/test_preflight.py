"""Only preflight safety tests; not a substitute for the scientific test suite."""
import importlib.util
from pathlib import Path
import unittest
spec = importlib.util.spec_from_file_location("preflight", Path(__file__).parents[1] / "src/preflight.py")
p = importlib.util.module_from_spec(spec)
spec.loader.exec_module(p)

class GuardTests(unittest.TestCase):
    def test_output_h_drive_rejected(self):
        with self.assertRaises(ValueError):
            p.guard_output(p.SOURCE / "202407/output.csv")
    def test_output_outside_project_rejected(self):
        with self.assertRaises(ValueError):
            p.guard_output(Path("C:/temporary_output.csv"))
    def test_valid_output(self):
        self.assertTrue(p.guard_output(p.PROJECT / "stage0_himawari/outputs/test").is_relative_to(p.PROJECT.resolve()))
    def test_other_month_rejected(self):
        with self.assertRaises(ValueError):
            p.guard_source(p.SOURCE / "202408/test.nc", 2024, 7)
    def test_source_traversal_rejected(self):
        with self.assertRaises(ValueError):
            p.guard_source(p.SOURCE / "202407/../202406/test.nc", 2024, 7)
    def test_source_month_allowed(self):
        self.assertTrue(p.guard_source(p.SOURCE / "202407/01/test.nc", 2024, 7).is_relative_to((p.SOURCE / "202407").resolve()))
    def test_channel_order(self):
        self.assertEqual(p.CHANNELS, ("tbb_08","tbb_09","tbb_10","tbb_11","tbb_13","tbb_15","tbb_16"))
    def test_no_silent_overwrite(self):
        import tempfile
        with tempfile.TemporaryDirectory(dir=p.PROJECT / "stage0_himawari/tests") as folder:
            target = Path(folder) / "exclusive.txt"
            p.write_text(target, "original")
            with self.assertRaises(FileExistsError):
                p.write_text(target, "replacement")
            self.assertEqual(target.read_text(), "original")

if __name__ == "__main__":
    unittest.main(verbosity=2)
