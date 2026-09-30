"""Regression: a missing non-B13 band cannot exclude a B0 source file."""
from datetime import datetime, timedelta, timezone
from pathlib import Path
import unittest

from scripts.verify_b0_real_sample import b0_candidate_rows


class B13OnlyCandidateTests(unittest.TestCase):
    def test_missing_other_band_remains_b0_candidate(self):
        root = Path(__file__).parent
        start = datetime(2023, 3, 1, tzinfo=timezone.utc)
        rows = [{
            "relative_path": Path(__file__).name,
            "timestamp_filename_utc": (start + timedelta(minutes=20)).isoformat(),
            "read_success": "False", "has_all_7_channels": "False",
            "quality_class": "OTHER_CHANNEL_MISSING",
        }]
        self.assertEqual(b0_candidate_rows(rows, root, start, start + timedelta(minutes=30)), rows)


if __name__ == "__main__":
    unittest.main()
