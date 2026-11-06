"""Artificial metadata only; no project data, file I/O or model execution."""
import unittest
from yuntapr.experimental.research_readiness.evaluation_alignment_candidate import (
    EVENT_ID_STATUS, METHOD_STATUS, validate_alignment,
)


def row(scene="scene-1", when="2024-07-01T00:00:00Z",
        start="2024-07-01T00:00:00Z", end="2024-07-01T00:30:00Z", **changes):
    result = dict(scene_id=scene, scene_time_utc=when, window_start_utc=start,
                  window_end_utc=end,
                  window_convention="START_INCLUSIVE_END_EXCLUSIVE",
                  grid_sha256="a" * 64, mask_sha256="b" * 64,
                  pixel_order_sha256="c" * 64, pixel_count=3, rate_unit="mm/h")
    result.update(changes)
    return result


def aligned(predictions, labels=None, first="2024-07-01", last="2024-07-03", expected=None):
    if expected is None:
        expected = [item.get("scene_id", "invalid") for item in predictions
                    if isinstance(item, dict)]
    return validate_alignment(predictions, predictions if labels is None else labels,
                              expected_scene_ids=expected,
                              first_day_utc=first, last_day_utc=last)


class AlignmentCandidateTests(unittest.TestCase):
    def test_identity_and_actual_time_preserved(self):
        value = row()
        result = aligned([value])
        self.assertEqual(result.scenes[0].scene_id, value["scene_id"])
        self.assertEqual(result.scenes[0].scene_time_utc, value["scene_time_utc"])
        self.assertEqual(result.event_id_status, EVENT_ID_STATUS)
        self.assertEqual(result.event_id_status, "NOT_IDENTIFIED")
        self.assertEqual(result.method_status, METHOD_STATUS)
        self.assertEqual(result.evidence_scope, "CALLER_METADATA_ONLY_NOT_PAYLOAD_VERIFIED")
        self.assertFalse(result.contiguous_half_hour_windows)
        self.assertEqual(result.calendar_group_basis, "SCENE_TIMESTAMP_UTC")
        self.assertEqual(result.scene_timestamp_role,
                         "CALLER_MATCHING_KEY_NOT_BOUND_TO_REFERENCE_ENDPOINT")
        self.assertFalse(result.reference_window_extent_verified)
        self.assertFalse(result.reference_window_timestamp_relation_verified)

    def test_empty_calendar_days_are_retained_without_zero_rain_labels(self):
        result = aligned([row()])
        self.assertEqual([d.date_utc for d in result.calendar_days],
                         ["2024-07-01", "2024-07-02", "2024-07-03"])
        self.assertEqual([d.scene_indices for d in result.calendar_days], [(0,), (), ()])

    def test_six_hour_sampling_does_not_become_half_hour_sequence(self):
        later = row("scene-2", "2024-07-01T06:00:00Z",
                    "2024-07-01T06:00:00Z", "2024-07-01T06:30:00Z")
        result = aligned([row(), later])
        self.assertEqual(result.adjacent_scene_gaps_seconds, (21600,))
        self.assertFalse(result.contiguous_half_hour_windows)
        self.assertEqual(result.event_id_status, "NOT_IDENTIFIED")

    def test_adjacent_windows_are_still_not_independent_weather_events(self):
        later = row("scene-2", "2024-07-01T00:30:00Z",
                    "2024-07-01T00:30:00Z", "2024-07-01T01:00:00Z")
        result = aligned([row(), later])
        self.assertTrue(result.contiguous_half_hour_windows)
        self.assertEqual(result.event_id_status, "NOT_IDENTIFIED")

    def test_timestamp_spacing_alone_does_not_prove_adjacent_reference_windows(self):
        later = row("scene-2", "2024-07-01T00:30:00Z",
                    "2024-07-01T06:00:00Z", "2024-07-01T06:30:00Z")
        result = aligned([row(), later])
        self.assertEqual(result.adjacent_scene_gaps_seconds, (1800,))
        self.assertFalse(result.contiguous_half_hour_windows)

    def test_2024_leap_day_is_retained_in_calendar(self):
        leap = row(when="2024-02-29T00:00:00Z", start="2024-02-29T00:00:00Z",
                   end="2024-02-29T00:30:00Z")
        result = aligned([leap], first="2024-02-28", last="2024-03-01")
        self.assertEqual([d.date_utc for d in result.calendar_days],
                         ["2024-02-28", "2024-02-29", "2024-03-01"])
        self.assertEqual([d.scene_indices for d in result.calendar_days], [(), (0,), ()])

    def test_identity_mismatches_fail_without_pair_rejoining(self):
        for key, value in {"scene_id": "different", "scene_time_utc": "2024-07-01T00:01:00Z",
                           "grid_sha256": "d" * 64, "mask_sha256": "e" * 64,
                           "pixel_order_sha256": "f" * 64, "pixel_count": 4}.items():
            with self.subTest(key=key), self.assertRaises(ValueError):
                aligned([row()], [row(**{key: value})])

    def test_different_reference_windows_fail(self):
        changed = row(start="2024-07-01T00:30:00Z", end="2024-07-01T01:00:00Z")
        with self.assertRaises(ValueError):
            aligned([row()], [changed])

    def test_units_and_window_conventions_are_not_silently_converted(self):
        for key, value in (("rate_unit", "mm/30min"), ("rate_unit", "mm/hr"),
                           ("window_convention", "END_INCLUSIVE")):
            with self.subTest(key=key, value=value), self.assertRaises(ValueError):
                aligned([row(**{key: value})])

    def test_bad_duration_rejected_even_when_both_sides_agree(self):
        for end in ("2024-07-01T01:00:00Z", "2024-07-01T00:00:00Z"):
            with self.subTest(end=end), self.assertRaises(ValueError):
                aligned([row(end=end)])

    def test_missing_extra_and_invalid_fields_are_rejected(self):
        missing = row(); del missing["mask_sha256"]
        for item in (missing, row(event_id="invented"), row(pixel_count=True),
                     row(pixel_count=0), row(scene_id=" "), row(grid_sha256="bad")):
            with self.subTest(item=item), self.assertRaises(ValueError):
                aligned([item])

    def test_missing_rows_and_empty_inputs_fail(self):
        for a, b in (([row()], []), ([], []), ("metadata", "metadata")):
            with self.subTest(a=a), self.assertRaises(ValueError):
                aligned(a, b)

    def test_same_missing_scene_on_both_sides_fails_against_declared_manifest(self):
        with self.assertRaises(ValueError):
            aligned([row()], expected=["scene-1", "scene-2"])
        with self.assertRaises(ValueError):
            aligned([row()], expected=["other-scene"])

    def test_manifest_must_be_explicit_unique_and_ordered(self):
        for expected in ([], "scene-1", ["scene-1", "scene-1"], [" "]):
            with self.subTest(expected=expected), self.assertRaises(ValueError):
                aligned([row()], expected=expected)
        with self.assertRaises(TypeError):
            validate_alignment([row()], [row()],
                               first_day_utc="2024-07-01", last_day_utc="2024-07-03")

    def test_duplicate_scene_ids_fail(self):
        later = row(when="2024-07-01T06:00:00Z", start="2024-07-01T06:00:00Z",
                    end="2024-07-01T06:30:00Z")
        with self.assertRaises(ValueError):
            aligned([row(), later])

    def test_unsorted_and_equal_timestamps_fail(self):
        later = row("scene-2", "2024-07-01T06:00:00Z",
                    "2024-07-01T06:00:00Z", "2024-07-01T06:30:00Z")
        with self.assertRaises(ValueError):
            aligned([later, row()])
        with self.assertRaises(ValueError):
            aligned([row(), row("scene-2")])
        with self.assertRaises(ValueError):
            aligned([row(), later], [later, row()])

    def test_overlapping_windows_fail(self):
        overlap = row("scene-2", "2024-07-01T06:00:00Z",
                      "2024-07-01T00:15:00Z", "2024-07-01T00:45:00Z")
        with self.assertRaises(ValueError):
            aligned([row(), overlap])

    def test_noncanonical_and_impossible_times_fail(self):
        for value in ("2024-07-01T00:00:00+00:00", "2024-07-01T08:00:00+08:00",
                      "2024-02-30T00:00:00Z", "2024-07-01T00:00Z"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                aligned([row(when=value)])

    def test_only_2024_metadata_admitted(self):
        # Literal fake metadata only; no path, directory listing or payload access.
        with self.assertRaises(ValueError):
            aligned([row(when="2025-01-01T00:00:00Z")])
        with self.assertRaises(ValueError):
            aligned([row()], first="2025-01-01", last="2025-01-02")
        with self.assertRaises(ValueError):
            aligned([row(start="2023-12-31T23:30:00Z", end="2024-01-01T00:00:00Z")])

    def test_calendar_extent_is_explicit_and_cannot_drop_scene(self):
        for first, last in (("2024-07-03", "2024-07-01"),
                            ("2024-07-02", "2024-07-03"),
                            ("2024-02-30", "2024-07-03")):
            with self.subTest(first=first, last=last), self.assertRaises(ValueError):
                aligned([row()], first=first, last=last)


if __name__ == "__main__":
    unittest.main()
