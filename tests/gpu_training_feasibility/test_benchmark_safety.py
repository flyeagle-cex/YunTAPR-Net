"""Engineering gates: avoid treating completion or an unrun case as safe."""
import math
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]/"scripts"))
from benchmark_b0_gpu_feasibility import can_advance, safe_memory, epoch_arithmetic


class BenchmarkSafetyTests(unittest.TestCase):
    def test_shared_memory_spill_is_not_safe(self):
        self.assertFalse(safe_memory(8768, 8150, 1000, .15))

    def test_background_gpu_consumers_count(self):
        self.assertFalse(safe_memory(4000, 8000, 500, .20))
        self.assertTrue(safe_memory(4000, 8000, 2400, .20))

    def test_fifteen_percent_safe_need_not_be_recommended(self):
        self.assertTrue(safe_memory(6400, 8000, 1400, .15))
        self.assertFalse(safe_memory(6400, 8000, 1400, .20))

    def test_progression_stops_on_oom_nonfinite_not_run_or_no_margin(self):
        for status in ("OOM", "ERROR", "NOT_RUN"):
            self.assertFalse(can_advance({"status": status, "safe_15pct": True}))
        self.assertFalse(can_advance({"status": "PASS", "safe_15pct": False}))
        self.assertTrue(can_advance({"status": "PASS", "safe_15pct": True}))

    def test_epoch_tail_and_validation_are_counted(self):
        result = epoch_arithmetic(2, 8, .2, .24, 30)
        self.assertEqual(result["steps_per_epoch"], 5860)
        self.assertEqual(result["validation_steps"], 1466)
        expected = (5860*.2+1466*.24)*30/3600
        self.assertAlmostEqual(result["wall_hours"], expected)
        self.assertEqual(result["status"], "ENGINEERING_ESTIMATE_ONLY")

    def test_zero_and_unknown_vram_never_pass(self):
        self.assertFalse(safe_memory(0, 0, 0, .2))
        self.assertFalse(safe_memory(1, math.nan, 1, .2))


if __name__ == "__main__":
    unittest.main()
