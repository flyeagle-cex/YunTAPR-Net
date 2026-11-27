"""Pure 2025 planning tests: clock, scope, layout, no payload I/O."""
import tempfile
import unittest
from pathlib import Path

from yuntapr.experimental.research_readiness import final_test_2025_planning as p


class Planning2025Tests(unittest.TestCase):
    def test_frozen_clock_and_count(self):
        rows = p.enumerate_scenes()
        self.assertEqual(len(rows), 856)
        self.assertEqual(len(rows), p.expected_slot_count())
        self.assertEqual(len({row.sample_id for row in rows}), 856)
        first, last = rows[0], rows[-1]
        self.assertEqual(first.sample_id, '2025-02-28T23:30:00+00:00')
        self.assertEqual(first.analysis_time.isoformat(), '2025-03-01T00:00:00+00:00')
        self.assertEqual(first.gfs_init.isoformat(), '2025-02-28T18:00:00+00:00')
        self.assertEqual(first.imerg_index, 47)
        self.assertEqual(last.sample_id, '2025-09-30T17:30:00+00:00')
        self.assertEqual(last.satellites[-1].relative_path,
                         '202509/30/NC_H09_20250930_1750_R21_FLDK.06001_06001.nc')
        self.assertEqual(first.satellites[0].relative_path,
                         '202502/28/NC_H09_20250228_2300_R21_FLDK.06001_06001.nc')
        self.assertEqual([frame.channel for frame in first.satellites],
                         ['B08', 'B09', 'B10', 'B11', 'B13', 'B15'])
        self.assertEqual([(frame.nominal.minute) for frame in first.satellites], [0, 10, 20, 30, 40, 50])
        self.assertEqual(last.gfs_main_relative_path, '2025/20250930/gfs_0p25_2025093012_f006.nc')
        self.assertEqual(last.gfs_thermo_relative_path,
                         '2025/20250930/gfs_thermo_0p25_2025093012_f006.nc')
        self.assertEqual(last.imerg_day_relative_path, '2025/imerg_20250930.nc')

    def test_october_is_rejected_by_default(self):
        with self.assertRaises(PermissionError):
            p.enumerate_scenes(months=tuple(range(3, 11)))
        rows = p.enumerate_scenes(months=tuple(range(3, 11)), allow_october=True)
        self.assertEqual(rows[-1].month, 10)
        self.assertEqual(len(rows), p.expected_slot_count(tuple(range(3, 11))))

    def test_validate_scene_rejects_tampering(self):
        row = p.enumerate_scenes()[3].as_dict()
        self.assertTrue(p.validate_scene(row))
        for key, value in (('sample_id', '2025-03-01T05:00:00+00:00'),
                           ('slot_00_nominal', '2025-03-01T04:50:00+00:00'),
                           ('gfs_init', '2025-03-01T00:00:00+00:00'),
                           ('imerg_index', 12)):
            bad = dict(row, **{key: value})
            with self.assertRaises(ValueError):
                p.validate_scene(bad)
        bad = dict(row, analysis_time='2024-03-01T06:00:00+00:00',
                   window_start='2024-03-01T05:30:00+00:00',
                   sample_id='2024-03-01T05:30:00+00:00', month=3,
                   slot_00_nominal='2024-03-01T05:00:00+00:00',
                   slot_01_nominal='2024-03-01T05:10:00+00:00',
                   slot_02_nominal='2024-03-01T05:20:00+00:00',
                   slot_03_nominal='2024-03-01T05:30:00+00:00',
                   slot_04_nominal='2024-03-01T05:40:00+00:00',
                   slot_05_nominal='2024-03-01T05:50:00+00:00')
        with self.assertRaises(PermissionError):
            p.validate_scene(bad)

    def test_layout_is_configurable_and_defaults_are_frozen_evidence(self):
        default = p.PathLayout2025.default()
        self.assertEqual(default.himawari_template, p.HIMAWARI_TEMPLATE)
        alternate = p.PathLayout2025(himawari_template=p.HIMAWARI_ALTERNATE_TEMPLATE)
        self.assertIn('NC_H08_', p.render_relpath(alternate, 'himawari', p.utc('2025-03-01T00:00:00+00:00')))
        with self.assertRaises(ValueError):
            p.PathLayout2025(himawari_template='nested/file.nc')
        with self.assertRaises(ValueError):
            p.render_template('', p.utc('2025-03-01T00:00:00+00:00'))

    def test_synthetic_layout_never_points_at_2025_payloads(self):
        with tempfile.TemporaryDirectory() as root:
            layout = p.synthetic_layout(root)
            self.assertTrue(layout.himawari_root.startswith(str(Path(root))))
        for forbidden in ('H:\\葵花202303_202510', 'F:\\云南极端降水数据\\raw\\IMERG',
                          'F:\\pytorch\\Research'):
            with self.assertRaises(PermissionError):
                p.synthetic_layout(forbidden)

    def test_scope_manifest_matches_clock(self):
        scope = p.scope_manifest()
        self.assertEqual(scope['months'], list(range(3, 10)))
        self.assertEqual(scope['expected_candidate_slots'], 856)
        self.assertFalse(scope['october_authorized'])
        self.assertIn('analysis-30min', scope['clock_convention'])


if __name__ == '__main__':
    unittest.main()
