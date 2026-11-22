"""Chronology and common-arm identity checks using synthetic metadata only."""

from copy import deepcopy
from datetime import datetime, timedelta
from hashlib import sha256
import unittest

from yuntapr.experimental.research_readiness.final_test_manifest import (
    IDENTITY_FIELDS,
    build_synthetic_common_manifest,
)


def digest(label):
    return sha256(label.encode()).hexdigest()


IDENTITY = {field: digest(field) for field in IDENTITY_FIELDS}


def fixture(analysis_time):
    analysis = datetime.fromisoformat(analysis_time)
    target = analysis - timedelta(minutes=30)
    satellite = []
    for offset in (60, 50, 40, 30, 20, 10):
        nominal = analysis - timedelta(minutes=offset)
        satellite.append(dict(nominal_time=nominal.isoformat(), obs_start=nominal.isoformat(),
                              obs_end=(nominal + timedelta(minutes=3)).isoformat(),
                              grid_sha256=digest("satellite grid"),
                              source_sha256=digest(f"satellite/{nominal}")))
    gfs = {
        role: dict(init_time=(analysis - timedelta(hours=6)).isoformat(),
                   valid_time=analysis.isoformat(), lead_hours=6, grid_sha256=digest("GFS grid"),
                   source_sha256=digest(f"GFS/{role}/{analysis}"))
        for role in ("main", "thermo")
    }
    return dict(
        synthetic_fixture=True, sample_id=f"fixture/{analysis.isoformat()}",
        analysis_time=analysis_time, target_start=target.isoformat(), satellite_shape=[7, 6],
        GFS_variables=13, lead_hours=6, DEM_channels=6, target_shape=[100, 100],
        supervised_points=3430, identity=dict(IDENTITY), satellite=satellite, gfs=gfs,
        imerg=dict(product="IMERG_V07_Final", units="mm/h", window_start=target.isoformat(),
                   window_end=analysis.isoformat(), source_date=target.date().isoformat(),
                   half_hour_index=target.hour * 2 + target.minute // 30,
                   source_sha256=digest(f"IMERG/{target.date()}")),
    )


def build(arms, anchor="target_start", end_month=9):
    return build_synthetic_common_manifest(
        arms, expected_identity=IDENTITY, range_anchor=anchor, end_month=end_month,
    )


class FinalTestManifestTests(unittest.TestCase):
    def test_common_population_counts_and_deterministic_digest(self):
        morning = fixture("2001-03-01T06:00:00+00:00")
        noon = fixture("2001-03-01T12:00:00+00:00")
        evening = fixture("2001-03-01T18:00:00+00:00")
        alternate = dict(morning, analysis_time="2001-03-01T06:00:00Z")
        report = build({"candidate": [noon, alternate], "control": [evening, morning, noon]})
        self.assertEqual(report, build({"control": [noon, morning, evening],
                                        "candidate": [morning, noon]}))
        self.assertEqual([x["sample_id"] for x in report["scenes"]],
                         [morning["sample_id"], noon["sample_id"]])
        self.assertEqual(report["missing_in_arm"], dict(candidate=[evening["sample_id"]], control=[]))
        self.assertEqual(report["common_source_counts"],
                         dict(satellite=12, gfs_main=2, gfs_thermo=2, imerg=1))
        self.assertEqual(report["actual_inference_adapter"], "NOT_IMPLEMENTED")
        self.assertEqual(report["real_population"], "NOT_VERIFIED")
        self.assertFalse(report["payload_access_authorized"])

    def test_month_boundary_and_midnight_use_target_day(self):
        start = fixture("2001-03-01T00:00:00+00:00")
        october = fixture("2001-10-01T00:00:00+00:00")
        november = fixture("2001-11-01T00:00:00+00:00")
        arms = dict(control=[start, october, november], candidate=[october, start, november])
        for anchor, month, expected in (
            ("target_start", 9, [october]),
            ("analysis_time", 9, [start]),
            ("target_start", 10, [october, november]),
            ("analysis_time", 10, [start, october]),
        ):
            with self.subTest(anchor=anchor, month=month):
                report = build(arms, anchor, month)
                self.assertEqual([row["sample_id"] for row in report["scenes"]],
                                 [row["sample_id"] for row in expected])
                self.assertEqual(len(report["outside_range_by_arm"]["control"]), 3 - len(expected))
        report = build(arms)
        scene = report["scenes"][0]
        self.assertEqual(scene["imerg"]["source_date"], "2001-09-30")
        self.assertEqual(scene["imerg"]["half_hour_index"], 47)
        self.assertEqual(scene["gfs"]["main"]["init_time"], "2001-09-30T18:00:00+00:00")
        self.assertEqual(scene["satellite"][-1]["nominal_time"], "2001-09-30T23:50:00+00:00")

    def test_reject_inconsistent_arm_and_duplicate_scene(self):
        base = fixture("2001-03-01T06:00:00+00:00")
        changed = deepcopy(base)
        changed["imerg"]["source_sha256"] = digest("other source")
        for row in (changed, dict(base, sample_id="other ID")):
            with self.assertRaises(ValueError):
                build(dict(control=[base], candidate=[row]))
        with self.assertRaises(ValueError):
            build(dict(control=[base, base], candidate=[base]))

    def test_reject_metadata_that_would_break_the_binding(self):
        base = fixture("2001-03-01T06:00:00+00:00")
        for section, field, value in (
            (("satellite", 5), "obs_end", "2001-03-01T06:00:01+00:00"),
            (("satellite", 5), "nominal_time", "2001-03-01T05:59:00+00:00"),
            (("satellite", 5), "source_sha256", base["satellite"][0]["source_sha256"]),
            (("gfs", "thermo"), "lead_hours", 0),
            (("gfs", "thermo"), "init_time", "2001-03-01T06:00:00+00:00"),
            (("gfs", "main"), "grid_sha256", digest("other grid")),
            (("imerg",), "half_hour_index", 12),
            (("imerg",), "source_date", "2001-02-28"),
            (("identity",), "train_scalers_sha256", digest("other scaler")),
        ):
            with self.subTest(section=section, field=field):
                row = deepcopy(base)
                entry = row
                for key in section:
                    entry = entry[key]
                entry[field] = value
                with self.assertRaises(ValueError):
                    build(dict(control=[row], candidate=[row]))

    def test_synthetic_year_is_enforced_inside_each_source(self):
        base = fixture("2001-03-01T06:00:00+00:00")
        with self.assertRaises(PermissionError):
            build(dict(control=[fixture("2025-03-01T06:00:00+00:00")], candidate=[base]))
        for section, field, value in (
            (("satellite", 0), "obs_start", "2025-03-01T05:00:00Z"),
            (("gfs", "main"), "init_time", "2025-03-01T00:00:00Z"),
            (("imerg",), "source_date", "2025-03-01"),
        ):
            with self.subTest(section=section):
                row = deepcopy(base)
                entry = row
                for key in section:
                    entry = entry[key]
                entry[field] = value
                with self.assertRaises(PermissionError):
                    build(dict(control=[row], candidate=[row]))


if __name__ == "__main__":
    unittest.main()
