"""Exercise source metadata binding without accessing files."""

from datetime import datetime, timedelta
import unittest

from tools.research_readiness.orographic_source_binding import bind_main_sources


def fixtures():
    scenes, files, metadata = [], [], {}
    for hour, size in ((6, 30), (12, 50), (18, 40)):
        analysis = datetime.fromisoformat(f"2024-03-01T{hour:02d}:00:00+00:00")
        target = (analysis - timedelta(minutes=30)).isoformat()
        init = analysis - timedelta(hours=6)
        name = f"gfs_0p25_{init:%Y%m%d%H}_f006.nc"
        scenes.append(dict(sample_id=target, window_start=target, analysis_time=analysis.isoformat(),
                           year="2024", role="Validation"))
        files.append(dict(kind="main", valid=analysis.isoformat(), init=init.isoformat(),
                          lead=6, relative_path=name, bytes=size))
        metadata[name] = dict(year=2024, kind="GFS_main", bytes=size, sha="a" * 64)
    return [scene["sample_id"] for scene in scenes], scenes, files, metadata


class OrographicSourceBindingTests(unittest.TestCase):
    def test_order_and_largest_files_bound(self):
        ids, scenes, files, metadata = fixtures()
        rows, budget = bind_main_sources(ids, scenes[::-1], files[::-1], metadata,
                                         positive_support_count=2)
        self.assertEqual([row["sample_id"] for row in rows], ids)
        self.assertEqual(budget, dict(all_main_files=3, all_main_bytes=120, main_open_cap=2, main_byte_cap=90))

    def test_misalignment_other_year_and_different_archive_are_rejected(self):
        for field, wrong in (("lead", 0), ("init", "2025-03-01T00:00:00Z"), ("bytes", 31)):
            with self.subTest(field=field):
                ids, scenes, files, metadata = fixtures()
                files[0][field] = wrong
                with self.assertRaises(ValueError):
                    bind_main_sources(ids, scenes, files, metadata, positive_support_count=2)
        ids, scenes, files, metadata = fixtures()
        scenes[0]["analysis_time"] = scenes[0]["window_start"]
        with self.assertRaises(ValueError):
            bind_main_sources(ids, scenes, files, metadata, positive_support_count=2)


if __name__ == "__main__":
    unittest.main()
