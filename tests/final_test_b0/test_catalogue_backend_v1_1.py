"""Synthetic local NetCDF QC checks; no original source or checkpoint access."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path, PureWindowsPath
import shutil
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import uuid

import netCDF4
import numpy as np

from yuntapr.contracts.loader import REPO_ROOT, sha256
from yuntapr.data.imerg_v07 import decode_imerg
from yuntapr.evaluation import catalogue_backend_b0 as backend
from yuntapr.spatial.sp04_mapping import load_sp04


class CatalogueBackendFixtureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.mapping = load_sp04()

    def setUp(self):
        self.parent = (REPO_ROOT.parent / "tmp" / "catalogue_backend_fixture_tests").resolve()
        self.parent.mkdir(parents=True, exist_ok=True)
        self.root = self.parent / ("fixture_" + uuid.uuid4().hex)
        self.root.mkdir()
        self.stage_parent = Path(tempfile.gettempdir()) / "yuntapr_catalogue_backend_fixture_tests"
        self.stage_parent.mkdir(parents=True, exist_ok=True)
        self.stage_root = self.stage_parent / ("stage_" + uuid.uuid4().hex)
        self.netcdf_root = self.stage_parent / ("source_" + uuid.uuid4().hex)
        self.netcdf_root.mkdir()
        self.day = datetime(2024, 7, 1, tzinfo=timezone.utc)
        self.mask = np.zeros((100, 100), dtype=bool)
        self.mask.ravel()[:3430] = True
        self.telemetry = {
            "2025_PIXELS_READ": 0, "b13_pixel_values_read": 0, "imerg_pixel_values_read": 0,
            "raw_source_open_events": 0, "source_hash_bytes_read": 0,
            "source_copy_bytes_read": 0, "source_copy_bytes_written": 0,
        }

    def tearDown(self):
        for target, parent in ((self.root, self.parent), (self.stage_root, self.stage_parent), (self.netcdf_root, self.stage_parent)):
            if target.resolve().parent != parent.resolve():
                raise ValueError("Unsafe fixture cleanup target")
            if target.exists():
                shutil.rmtree(target)

    def b13_file(self, *, missing=False):
        path = self.netcdf_root / "synthetic_b13_20240701.nc"
        with netCDF4.Dataset(str(path), "w") as ds:
            for name, size in (("latitude", 501), ("longitude", 501), ("time", 1)):
                ds.createDimension(name, size)
            for name, axis in (("latitude", "native_lat"), ("longitude", "native_lon")):
                ds.createVariable(name, "f4", (name,))[:] = self.mapping.axes[axis]
            variable = ds.createVariable("tbb_13", "i2", ("latitude", "longitude"), fill_value=-9999)
            variable.setncatts(dict(units="K", scale_factor=np.float32(.01), add_offset=np.float32(0),
                                   valid_min=np.int16(0), valid_max=np.int16(32767)))
            variable.set_auto_maskandscale(False)
            values = np.full((501, 501), 27000, dtype=np.int16)
            if missing:
                values[0, 0] = -9999
            variable[:] = values
            for name, value in (("start_time", 20), ("end_time", 29)):
                time_var = ds.createVariable(name, "f8", ("time",))
                time_var.units = self.day.strftime("minutes since %Y-%m-%d 00:00:00")
                time_var[:] = [value]
            ds.date_created = self.day.isoformat()
        return path

    def imerg_file(self, *, bad_time=False, wrong_product=False):
        path = self.netcdf_root / "synthetic_imerg_20240701.nc"
        with netCDF4.Dataset(str(path), "w") as ds:
            for name, size in (("time", 48), ("lat", 130), ("lon", 140)):
                ds.createDimension(name, size)
            latitude, longitude = np.arange(130, dtype=np.float32), np.arange(140, dtype=np.float32)
            latitude[10:110], longitude[20:120] = self.mapping.axes["target_lat"], self.mapping.axes["target_lon"]
            ds.createVariable("lat", "f4", ("lat",))[:] = latitude
            ds.createVariable("lon", "f4", ("lon",))[:] = longitude
            time_var = ds.createVariable("time", "f8", ("time",))
            time_var.units = self.day.strftime("minutes since %Y-%m-%d 00:00:00")
            times = np.arange(48) * 30
            if bad_time:
                times[47] += 1
            time_var[:] = times
            variable = ds.createVariable("precipitation", "f4", ("time", "lat", "lon"), fill_value=-9999)
            variable.units = "mm hr-1"
            values = np.zeros((48, 130, 140), dtype=np.float32)
            values[1, 10, 20] = -9999
            values[2] = 125
            variable[:] = values
            ds.source = "OTHER_PRODUCT" if wrong_product else "GPM_3IMERGHH_07"
            ds.title = "IMERG Final Run V07"
        return path

    def test_b13_reader_scalar_only_and_actual_pixel_count(self):
        path = self.b13_file()
        result = backend.read_b13_catalogue_qc(path, self.mapping,
                                             "2024-07-01T00:20:00+00:00", self.telemetry)
        self.assertEqual(result["full_valid_native_pixels"], 251001)
        self.assertTrue(result["b13_metadata_valid"])
        self.assertTrue(result["b13_finite"])
        self.assertEqual(result["obs_end"], "2024-07-01T00:29:00+00:00")
        self.assertEqual(self.telemetry["2025_PIXELS_READ"], 251001)
        self.assertNotIn("date_created", result)
        self.assertFalse(any(isinstance(value, np.ndarray) for value in result.values()))

    def test_b13_missing_pixel_rejected_but_all_reads_counted(self):
        result = backend.read_b13_catalogue_qc(self.b13_file(missing=True), self.mapping,
                                             "2024-07-01T00:20:00+00:00", self.telemetry)
        self.assertEqual(result["full_valid_native_pixels"], 251000)
        self.assertFalse(result["b13_finite"])
        self.assertTrue(result["b13_metadata_valid"])
        self.assertEqual(self.telemetry["b13_pixel_values_read"], 251001)

    def test_malformed_date_created_preserves_metadata_rejection_without_exposure(self):
        path = self.b13_file()
        with netCDF4.Dataset(str(path), "a") as ds:
            ds.date_created = "SYNTHETIC_MALFORMED_CREATION_TIME"
        result = backend.read_b13_catalogue_qc(path, self.mapping,
                                             "2024-07-01T00:20:00+00:00", self.telemetry)
        self.assertFalse(result["b13_metadata_valid"])
        self.assertEqual(result["full_valid_native_pixels"], 251001)
        self.assertEqual(self.telemetry["b13_pixel_values_read"], 251001)
        self.assertNotIn("date_created", result)

    def test_creation_time_is_not_used_as_causal_availability_criterion(self):
        path = self.b13_file()
        with netCDF4.Dataset(str(path), "a") as ds:
            ds.date_created = "2025-01-01T00:00:00+00:00"
        result = backend.read_b13_catalogue_qc(path, self.mapping,
                                             "2024-07-01T00:20:00+00:00", self.telemetry)
        self.assertTrue(result["b13_metadata_valid"])
        self.assertEqual(result["obs_end"], "2024-07-01T00:29:00+00:00")
        self.assertNotIn("date_created", result)

    def test_corrupt_b13_is_qc_rejection(self):
        path = self.root / "corrupt.nc"
        path.write_bytes(b"SYNTHETIC_NOT_NETCDF")
        result = backend.read_b13_catalogue_qc(path, self.mapping,
                                             "2024-07-01T00:20:00+00:00", self.telemetry)
        self.assertFalse(result["b13_readable"])
        self.assertFalse(result["b13_metadata_valid"])
        self.assertEqual(self.telemetry["b13_pixel_values_read"], 0)

    def test_imerg_day_qc_preserves_valid_zero_and_returns_no_values(self):
        path = self.imerg_file()
        result = backend.read_imerg_catalogue_qc(path, self.mapping, self.mask, self.day,
                    {"status": "complete", "granules": 48, "bytes": path.stat().st_size},
                    path.stat().st_size, self.telemetry)
        self.assertTrue(result.time_grid_provenance_pass)
        self.assertEqual(result.valid_yunnan_counts[0], 3430)
        self.assertEqual(result.valid_yunnan_counts[1], 3429)
        self.assertEqual(result.valid_yunnan_counts[2], 3430)
        self.assertEqual(self.telemetry["imerg_pixel_values_read"], 480000)
        self.assertEqual(self.telemetry["2025_PIXELS_READ"], 480000)
        self.assertEqual(set(result.__dict__), {"product", "version", "run_type", "time_grid_provenance_pass",
                         "valid_yunnan_counts", "source_bytes", "source_sha256"})

    def test_imerg_time_grid_error_does_not_read_target_values(self):
        path = self.imerg_file(bad_time=True)
        result = backend.read_imerg_catalogue_qc(path, self.mapping, self.mask, self.day,
                    {"status": "complete", "granules": 48, "bytes": path.stat().st_size},
                    path.stat().st_size, self.telemetry)
        self.assertFalse(result.time_grid_provenance_pass)
        self.assertEqual(self.telemetry["imerg_pixel_values_read"], 0)

    def test_imerg_manifest_and_product_are_both_required(self):
        path = self.imerg_file()
        result = backend.read_imerg_catalogue_qc(path, self.mapping, self.mask, self.day,
                                                {}, path.stat().st_size, self.telemetry)
        self.assertFalse(result.time_grid_provenance_pass)
        self.assertEqual(self.telemetry["imerg_pixel_values_read"], 0)
        with netCDF4.Dataset(str(path), "a") as ds:
            ds.source = "OTHER_PRODUCT"
        result = backend.read_imerg_catalogue_qc(path, self.mapping, self.mask, self.day,
                    {"status": "complete", "granules": 48, "bytes": path.stat().st_size},
                    path.stat().st_size, self.telemetry)
        self.assertFalse(result.time_grid_provenance_pass)
        self.assertEqual(result.product, "")

    def test_validity_only_matches_frozen_decoder_without_target_return(self):
        raw = np.array([0, 1, 3, -9999, 12, np.nan], dtype=np.float32)
        for attrs in ({"_FillValue": -9999, "valid_min": 0, "valid_max": 10},
                      {"missing_value": -9999, "scale_factor": .5, "add_offset": -1}):
            _, expected = decode_imerg(raw, attrs)
            actual = backend.imerg_validity_only(raw, attrs)
            np.testing.assert_array_equal(actual, expected)
            self.assertEqual(actual.dtype, np.dtype(bool))

    def test_manifest_jsonl_json_and_sha(self):
        rows = [{"date": "2024-07-01", "path": "F:/synthetic/imerg_20240701.nc",
                 "status": "complete", "granules": 48, "bytes": 123},
                {"date": "2024-07-02", "path": "F:/synthetic/imerg_20240702.nc",
                 "status": "incomplete", "granules": 47, "bytes": 456}]
        for index, text in enumerate(("\n".join(json.dumps(row) for row in rows), json.dumps(rows),
                                      json.dumps({"rows": rows}))):
            path = self.root / (str(index) + ".json")
            path.write_text(text, encoding="utf-8")
            result = backend.load_completion_manifest(path, sha256(path))
            self.assertEqual(len(result), 1)
            self.assertEqual(next(iter(result.values())), {"status": "complete", "granules": 48, "bytes": 123})
            with self.assertRaisesRegex(ValueError, "manifest SHA"):
                backend.load_completion_manifest(path, "0" * 64)

    def test_authority_checked_before_static_reads_and_staging_creation(self):
        def deny():
            raise PermissionError("separate catalogue authority required")
        authority = SimpleNamespace(require_catalogue=deny)
        with patch.object(backend, "load_sp04") as mapping_load:
            with self.assertRaises(PermissionError):
                backend.RealCatalogueBackend({}, authority, self.stage_root)
            mapping_load.assert_not_called()
        self.assertFalse(self.stage_root.exists())

    def test_staging_actual_bytes_sha_and_cleanup(self):
        source = self.root / "synthetic_source.nc"
        contents = b"fixture source" * 100
        source.write_bytes(contents)
        staging = backend.CatalogueEnglishStaging(self.stage_root, self.telemetry)
        with staging.local(source) as temporary:
            self.assertEqual(temporary.read_bytes(), contents)
            owned = temporary
        self.assertFalse(owned.exists())
        self.assertEqual(self.telemetry["source_copy_bytes_read"], len(contents))
        self.assertEqual(self.telemetry["source_copy_bytes_written"], len(contents))
        self.assertEqual(self.telemetry["source_hash_bytes_read"], len(contents))
        self.assertEqual(self.telemetry["raw_source_open_events"], 2)
        self.assertTrue(staging.records[-1].cleanup_success)
        self.assertEqual(staging.records[-1].source_sha256, hashlib.sha256(contents).hexdigest())

    def test_staging_engineering_failure_keeps_byte_counts_and_cleans(self):
        source = self.root / "synthetic_source.nc"
        source.write_bytes(b"synthetic")
        staging = backend.CatalogueEnglishStaging(self.stage_root, self.telemetry)
        original_digest = staging._digest
        def corrupt_staged_digest(path, *, original=False):
            return original_digest(path, original=True) if original else "0" * 64
        with patch.object(staging, "_digest", side_effect=corrupt_staged_digest):
            with self.assertRaisesRegex(IOError, "SHA256 mismatch"):
                with staging.local(source):
                    self.fail("Reader must not be entered after copy SHA failure")
        self.assertEqual(self.telemetry["source_copy_bytes_read"], 9)
        self.assertEqual(self.telemetry["source_hash_bytes_read"], 9)
        self.assertFalse(staging._owned)
        self.assertTrue(staging.records[-1].cleanup_success)
        self.assertEqual(staging.records[-1].error, "CATALOGUE_STAGING_ENGINEERING_FAILURE")

    def fixture_backend(self):
        # Bypass constructor only for this isolated synthetic source hook. Both
        # frozen roots are patched before probe, so no original source is touched.
        instance = backend.RealCatalogueBackend.__new__(backend.RealCatalogueBackend)
        instance.authority = SimpleNamespace(require_catalogue=lambda: None)
        instance.mapping, instance.yunnan = self.mapping, self.mask
        instance.telemetry = dict(self.telemetry, **{
            "2025_CATALOGUE_QC_ACCESS": False, "copy_seconds": 0.0, "read_seconds": 0.0,
            "temporary_bytes_peak": 0, "cleanup_success": True,
        })
        instance.manifest = {}
        instance.staging = backend.CatalogueEnglishStaging(self.stage_root, instance.telemetry)
        instance._cached_day_path = instance._cached_day_qc = None
        hroot, iroot = self.netcdf_root / "himawari", self.netcdf_root / "imerg"
        (hroot / "202503" / "01").mkdir(parents=True)
        (iroot / "2025").mkdir(parents=True)
        return instance, hroot, iroot

    def test_probe_accepts_h08_at_exact_nominal_and_scalar_candidate_schema(self):
        instance, hroot, iroot = self.fixture_backend()
        source = hroot / "202503" / "01" / "NC_H08_20250301_0020_R21_FLDK.06001_06001.nc"
        shutil.copyfile(self.b13_file(), source)
        with patch.object(backend.legacy, "HROOT", PureWindowsPath(str(hroot))), \
                patch.object(backend.legacy, "IROOT", PureWindowsPath(str(iroot))):
            row = instance.probe(0, backend.legacy.START)
        self.assertEqual(row["expected_latest_available"], "True")
        self.assertIn("NC_H08", row["b13_relative_path"])
        self.assertEqual(row["full_valid_native_pixels"], "251001")
        self.assertEqual(instance.telemetry["b13_pixel_values_read"], 251001)
        self.assertEqual(set(row), set(backend.strict_schema(row)))
        self.assertNotIn("date_created", row)
        self.assertFalse(instance.staging._owned)
        self.assertFalse(instance.staging.records)

    def test_probe_missing_latest_never_reads_existing_older_frame(self):
        instance, hroot, iroot = self.fixture_backend()
        older = hroot / "202503" / "01" / "NC_H09_20250301_0010_R21_FLDK.06001_06001.nc"
        older.write_bytes(b"EXISTING_OLDER_MUST_NEVER_BE_OPENED")
        with patch.object(backend.legacy, "HROOT", PureWindowsPath(str(hroot))), \
                patch.object(backend.legacy, "IROOT", PureWindowsPath(str(iroot))):
            row = instance.probe(0, backend.legacy.START)
        self.assertEqual(row["b13_relative_path"], "")
        self.assertEqual(row["expected_latest_available"], "False")
        self.assertEqual(row["used_older_causal_frame"], "False")
        self.assertEqual(instance.telemetry["raw_source_open_events"], 0)

    def test_probe_multiple_expected_nominal_sources_stops_before_any_open(self):
        instance, hroot, iroot = self.fixture_backend()
        for platform in ("H08", "H09"):
            (hroot / "202503" / "01" / ("NC_" + platform + "_20250301_0020_R21_FLDK.06001_06001.nc")).write_bytes(b"fixture")
        with patch.object(backend.legacy, "HROOT", PureWindowsPath(str(hroot))), \
                patch.object(backend.legacy, "IROOT", PureWindowsPath(str(iroot))):
            with self.assertRaisesRegex(IOError, "ambiguous"):
                instance.probe(0, backend.legacy.START)
        self.assertEqual(instance.telemetry["raw_source_open_events"], 0)

    def test_probe_imerg_day_cache_retains_counts_without_reopening_or_values(self):
        instance, hroot, iroot = self.fixture_backend()
        self.day = backend.legacy.START
        source = iroot / "2025" / "imerg_20250301.nc"
        shutil.copyfile(self.imerg_file(), source)
        instance.manifest[backend._manifest_key("2025-03-01", source)] = {
            "status": "complete", "granules": 48, "bytes": source.stat().st_size,
        }
        with patch.object(backend.legacy, "HROOT", PureWindowsPath(str(hroot))), \
                patch.object(backend.legacy, "IROOT", PureWindowsPath(str(iroot))):
            first = instance.probe(0, backend.legacy.START)
            second = instance.probe(1, backend.legacy.START + backend.timedelta(minutes=30))
        self.assertEqual(first["imerg_valid_yunnan_count"], "3430")
        self.assertEqual(second["imerg_valid_yunnan_count"], "3429")
        self.assertEqual(instance.telemetry["imerg_pixel_values_read"], 480000)
        self.assertEqual(instance.telemetry["raw_source_open_events"], 2)
        self.assertEqual(first["imerg_sha256"], sha256(source))
        self.assertEqual(set(instance._cached_day_qc.__dict__), {
            "product", "version", "run_type", "time_grid_provenance_pass",
            "valid_yunnan_counts", "source_bytes", "source_sha256",
        })

    def test_probe_october_rejects_before_discovery(self):
        instance, _, _ = self.fixture_backend()
        with patch.object(Path, "glob") as discover:
            with self.assertRaisesRegex(ValueError, "October"):
                instance.probe(0, backend.legacy.END)
            discover.assert_not_called()
        self.assertEqual(instance.telemetry["raw_source_open_events"], 0)


if __name__ == "__main__":
    unittest.main()
