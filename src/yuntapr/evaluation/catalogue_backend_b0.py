"""Catalogue-only raw QC readers: source identity, validity and time, no outcomes.

Only the authorized backend opens original sources. Reader helpers consume a
caller-owned English staging copy and return scalar QC metadata. IMERG decoded
values stay local to validity checking and are never returned or summarized.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from contextlib import contextmanager
import hashlib
import json
from pathlib import Path, PureWindowsPath
import stat
import time
import uuid

import netCDF4
import numpy as np
import yaml

from yuntapr.contracts.loader import REPO_ROOT, sha256
from yuntapr.data.himawari_b13 import decode_b13
from yuntapr.data.imerg_v07 import validate_final_provenance
from yuntapr.data.masks import read_frozen_yunnan_mask
from yuntapr.data.sample_schema import utc
from yuntapr.data.staging import BoundedEnglishStaging, StagingRecord
from yuntapr.evaluation.catalogue_gate_b0 import candidate_template, guard_paths, strict_schema, safe_artifact_path
from yuntapr.evaluation.catalogue_gate_b0 import legacy
from yuntapr.spatial.sp04_mapping import load_sp04


_QC_ERRORS = (ValueError, KeyError, AttributeError, IndexError, OSError, RuntimeError)
_B13_ATTRS = ("scale_factor", "add_offset", "valid_min", "valid_max", "_FillValue", "missing_value")
_IMERG_ATTRS = ("scale_factor", "add_offset", "valid_min", "valid_max", "_FillValue", "missing_value")


def _attrs(variable, allowed):
    names = set(variable.ncattrs())
    return {name: variable.getncattr(name) for name in allowed if name in names}


def _read_pixels(variable, selection, telemetry, kind):
    """Count the elements actually returned by this NetCDF pixel read."""
    raw = np.asarray(variable[selection])
    telemetry[kind + "_pixel_values_read"] += int(raw.size)
    telemetry["2025_PIXELS_READ"] += int(raw.size)
    return raw


def _cf_times(variable):
    converted = netCDF4.num2date(
        np.asarray(variable[:]), variable.units,
        calendar=getattr(variable, "calendar", "standard"),
        only_use_cftime_datetimes=False,
    )
    return tuple(utc(value.isoformat() + "Z") for value in np.asarray(converted).reshape(-1))


class CatalogueEnglishStaging(BoundedEnglishStaging):
    """Inherited bounded staging policy with actual source-read byte accounting."""

    def __init__(self, root, telemetry):
        super().__init__(root, 734003200, True, True)
        self.telemetry = telemetry

    def _source_open(self, source):
        self.telemetry["raw_source_open_events"] += 1
        return source.open("rb")

    def _digest(self, path, *, original=False):
        digest = hashlib.sha256()
        with (self._source_open(path) if original else path.open("rb")) as stream:
            for block in iter(lambda: stream.read(1024 * 1024), b""):
                if original:
                    self.telemetry["source_hash_bytes_read"] += len(block)
                digest.update(block)
        return digest.hexdigest()

    @contextmanager
    def local(self, source):
        source = source.resolve(strict=True)
        if self._active or self._owned or source.is_relative_to(self.root):
            raise ValueError("Staging permits only one external source at a time")
        size = source.stat().st_size
        if size > self.max_bytes:
            raise ValueError("Source exceeds bounded staging byte cap")
        destination = (self.root / ("yuntapr_b0_" + uuid.uuid4().hex + ".nc")).resolve()
        if destination.parent != self.root or destination in self._owned or destination.exists():
            raise ValueError("Unsafe staging destination")
        record = StagingRecord(str(source), size)
        self._active = True
        self._owned.add(destination)
        try:
            started = time.perf_counter()
            with self._source_open(source) as reader, destination.open("xb") as writer:
                while True:
                    block = reader.read(1024 * 1024)
                    if not block:
                        break
                    self.telemetry["source_copy_bytes_read"] += len(block)
                    self.telemetry["source_copy_bytes_written"] += writer.write(block)
            record.copy_seconds = time.perf_counter() - started
            record.size_match = destination.stat().st_size == size
            if not record.size_match:
                raise IOError("Staging copy size mismatch")
            record.source_sha256 = self._digest(source, original=True)
            record.sha256_match = record.source_sha256 == self._digest(destination)
            if not record.sha256_match:
                raise IOError("Staging SHA256 mismatch")
            started = time.perf_counter()
            try:
                yield destination
            finally:
                record.read_seconds = time.perf_counter() - started
        except Exception:
            # Fixed engineering code only: never serialize exception repr,
            # arbitrary source metadata or any source pixel array.
            record.error = "CATALOGUE_STAGING_ENGINEERING_FAILURE"
            raise
        finally:
            if destination in self._owned and destination.parent == self.root:
                try:
                    destination.unlink(missing_ok=True)
                    record.cleanup_success = True
                    self._owned.remove(destination)
                except OSError:
                    record.cleanup_error = "CATALOGUE_STAGING_CLEANUP_FAILED"
            self.records.append(record)
            self._active = False
            if not record.cleanup_success:
                raise IOError("STOP: catalogue staging cleanup required")


def read_b13_catalogue_qc(local_path, mapping, nominal_time, telemetry):
    """Return only B13 QC flags/count/time; never expose date_created."""
    result = dict(b13_readable=False, b13_metadata_valid=False,
                  full_valid_native_pixels=0, b13_finite=False,
                  obs_start="", obs_end="", selected_nominal="")
    try:
        with netCDF4.Dataset(str(local_path), "r") as ds:
            ds.set_auto_maskandscale(False)
            result["b13_readable"] = True
            variable = ds["tbb_13"]
            if (variable.dimensions != ("latitude", "longitude")
                    or variable.shape != (501, 501) or variable.units != "K"):
                raise ValueError("B13 dimension/shape/units mismatch")
            mapping.assert_axes(np.asarray(ds["latitude"][:]), np.asarray(ds["longitude"][:]),
                                mapping.axes["target_lat"], mapping.axes["target_lon"])
            packed_attrs = _attrs(variable, _B13_ATTRS)
            raw = _read_pixels(variable, np.s_[:], telemetry, "b13")
            decoded, valid = decode_b13(raw, packed_attrs)
            result["full_valid_native_pixels"] = int(np.count_nonzero(valid))
            result["b13_finite"] = bool(np.isfinite(decoded).all())
            del raw, decoded, valid
            start, end = _cf_times(ds["start_time"]), _cf_times(ds["end_time"])
            if len(start) != 1 or len(end) != 1:
                raise ValueError("B13 observation times must each contain one value")
            # Preserve the inherited reader's metadata-validity check. Creation
            # time is not a causal availability criterion or a catalogue field.
            created = str(ds.getncattr("date_created")) if "date_created" in ds.ncattrs() else None
            if created:
                utc(created)
            result.update(obs_start=start[0].isoformat(), obs_end=end[0].isoformat(),
                          selected_nominal=utc(nominal_time).isoformat(), b13_metadata_valid=True)
    except _QC_ERRORS as error:
        # Reader/metadata/QC failures are candidate rejections. Staging errors are
        # outside this helper, so copy/SHA/cleanup failures still stop execution.
        if isinstance(error, (OSError, RuntimeError)):
            result["b13_readable"] = False
    return result


def imerg_validity_only(raw, attrs):
    """The frozen decoder's validity semantics, without returning target values."""
    raw = np.asarray(raw)
    valid = np.isfinite(raw)
    for name in ("_FillValue", "missing_value"):
        if name in attrs:
            for missing in np.asarray(attrs[name]).reshape(-1):
                valid &= raw != missing
    if "valid_min" in attrs:
        valid &= raw >= attrs["valid_min"]
    if "valid_max" in attrs:
        valid &= raw <= attrs["valid_max"]
    if "scale_factor" in attrs or "add_offset" in attrs:
        if "scale_factor" not in attrs or "add_offset" not in attrs:
            raise ValueError("IMERG scale/offset metadata incomplete")
        decoded = raw.astype(np.float32) * np.float32(attrs["scale_factor"]) + np.float32(attrs["add_offset"])
    else:
        decoded = raw.astype(np.float32)
    valid &= np.isfinite(decoded) & (decoded >= 0)
    del decoded
    return valid


@dataclass(frozen=True)
class IMERGDayQC:
    """Bounded day cache containing only allowed QC information."""
    product: str = ""
    version: str = ""
    run_type: str = ""
    time_grid_provenance_pass: bool = False
    valid_yunnan_counts: tuple[int, ...] = (0,) * 48
    source_bytes: int = 0
    source_sha256: str = ""


def read_imerg_catalogue_qc(local_path, mapping, yunnan, day_start, manifest_row,
                           source_size, telemetry):
    """Read one 48-slot target crop and return only validity counts/provenance."""
    product = version = run_type = ""
    try:
        with netCDF4.Dataset(str(local_path), "r") as ds:
            ds.set_auto_maskandscale(False)
            global_attrs = {name: ds.getncattr(name) for name in ("source", "title") if name in ds.ncattrs()}
            if global_attrs.get("source") == "GPM_3IMERGHH_07":
                product, version = "IMERG", "V07"
            if "IMERG Final Run V07" in str(global_attrs.get("title", "")):
                run_type = "Final"
            validate_final_provenance(global_attrs, manifest_row or {}, source_size)
            variable = ds["precipitation"]
            if (variable.dimensions != ("time", "lat", "lon")
                    or variable.shape != (48, 130, 140) or variable.units != "mm hr-1"):
                raise ValueError("IMERG converted dimension/shape/units mismatch")
            mapping.assert_axes(mapping.axes["native_lat"], mapping.axes["native_lon"],
                                np.asarray(ds["lat"][10:110]), np.asarray(ds["lon"][20:120]))
            times = _cf_times(ds["time"])
            expected = tuple(utc(day_start) + timedelta(minutes=30 * index) for index in range(48))
            if times != expected:
                raise ValueError("IMERG complete half-hour time grid mismatch")
            if np.asarray(yunnan).dtype != np.dtype(bool) or np.asarray(yunnan).shape != (100, 100):
                raise ValueError("Frozen Yunnan target mask must be 100x100 bool")
            raw = _read_pixels(variable, np.s_[:, 10:110, 20:120], telemetry, "imerg")
            valid = imerg_validity_only(raw, _attrs(variable, _IMERG_ATTRS))
            counts = tuple(int(value) for value in np.count_nonzero(valid & yunnan[None], axis=(1, 2)))
            del raw, valid
            return IMERGDayQC(product, version, run_type, True, counts)
    except _QC_ERRORS:
        return IMERGDayQC(product, version, run_type)


def _manifest_key(date, path):
    return str(date), str(PureWindowsPath(str(path))).casefold()


def load_completion_manifest(path, expected_sha):
    """Verify the authorization-pinned JSONL/JSON manifest before provenance use."""
    path = Path(path)
    payload_bytes = path.read_bytes()
    if hashlib.sha256(payload_bytes).hexdigest() != expected_sha:
        raise ValueError("STOP: IMERG completion manifest SHA mismatch")
    payload = payload_bytes.decode("utf-8-sig")
    try:
        value = json.loads(payload)
    except json.JSONDecodeError:
        rows = [json.loads(line) for line in payload.splitlines() if line.strip()]
    else:
        if isinstance(value, list):
            rows = value
        elif isinstance(value, dict) and isinstance(value.get("rows"), list):
            rows = value["rows"]
        elif isinstance(value, dict) and "date" in value and "path" in value:
            rows = [value]
        else:
            raise ValueError("STOP: unsupported IMERG completion manifest schema")
    lookup = {}
    for row in rows:
        if not isinstance(row, dict) or "date" not in row or "path" not in row:
            raise ValueError("STOP: malformed completion manifest row")
        # Retain only fields needed for provenance, never unrelated manifest data.
        if row.get("status") == "complete" and row.get("granules") == 48:
            lookup[_manifest_key(row["date"], row["path"])] = {
                name: row.get(name) for name in ("status", "granules", "bytes")
            }
    return lookup


class RealCatalogueBackend:
    """Authorized exact-slot QC backend with one-file staging and one-day cache."""
    fixture_only = False

    def __init__(self, protocol, authority, staging_root):
        authority.require_catalogue()  # Before discovery, source open or mkdir.
        safe_artifact_path(staging_root)
        self.authority = authority
        self.protocol = protocol
        self.telemetry = {
            "2025_PIXELS_READ": 0, "2025_CATALOGUE_QC_ACCESS": False,
            "raw_source_open_events": 0, "b13_pixel_values_read": 0,
            "imerg_pixel_values_read": 0, "source_hash_bytes_read": 0,
            "source_copy_bytes_read": 0, "source_copy_bytes_written": 0,
            "copy_seconds": 0.0, "read_seconds": 0.0,
            "temporary_bytes_peak": 0, "cleanup_success": True,
        }
        self.mapping = load_sp04()
        loss_identity = protocol["identity"]["frozen_loss_protocol"]
        loss_path = REPO_ROOT / loss_identity["path"]
        if sha256(loss_path) != loss_identity["sha256"]:
            raise ValueError("STOP: frozen loss protocol SHA mismatch")
        loss_protocol = yaml.safe_load(loss_path.read_text(encoding="utf-8"))
        mask_identity = loss_protocol["identity"]["yunnan_mask"]
        mask_path = Path(mask_identity["path"])
        if sha256(mask_path) != mask_identity["sha256"]:
            raise ValueError("STOP: protocol-bound frozen Yunnan mask SHA mismatch")
        self.yunnan = read_frozen_yunnan_mask(mask_path, self.mapping)
        completion_path=Path(authority.value["imerg_completion_manifest_path"])
        self._original_location(completion_path,Path(str(legacy.IROOT)))
        self.manifest = load_completion_manifest(
            completion_path,
            authority.value["imerg_completion_manifest_sha256"],
        )
        self.staging = CatalogueEnglishStaging(Path(staging_root), self.telemetry)
        self._cached_day_path = None
        self._cached_day_qc = None

    def _records(self, start):
        records = self.staging.records[start:]
        try:
            for record in records:
                self.telemetry["2025_CATALOGUE_QC_ACCESS"] = True
                self.telemetry["copy_seconds"] += record.copy_seconds or 0.0
                self.telemetry["read_seconds"] += record.read_seconds or 0.0
                self.telemetry["temporary_bytes_peak"] = max(self.telemetry["temporary_bytes_peak"], record.temporary_bytes)
                self.telemetry["cleanup_success"] &= record.cleanup_success
                if not record.cleanup_success or not record.size_match or record.sha256_match is not True:
                    raise IOError("STOP: catalogue staging size/SHA/cleanup failed")
            if self.staging._owned:
                raise IOError("STOP: catalogue staging retained an owned temporary file")
        finally:
            del self.staging.records[start:]
        return records

    def _staged(self, source, reader):
        start = len(self.staging.records)
        try:
            with self.staging.local(source) as local:
                result = reader(local)
        finally:
            records = self._records(start)
        if len(records) != 1:
            raise IOError("STOP: catalogue staging operation count mismatch")
        return result, records[0]

    @staticmethod
    def _exists(source):
        try:
            info = source.stat()
        except FileNotFoundError:
            return False
        if not stat.S_ISREG(info.st_mode):
            raise IOError("STOP: catalogue source is not a regular file")
        return True

    @staticmethod
    def _original_location(source, root):
        # A per-month/day symlink must not redirect the frozen original root.
        resolved_root = root.resolve(strict=True)
        if source.resolve(strict=True) != resolved_root / source.relative_to(root):
            raise IOError("STOP: catalogue source redirects outside its frozen original location")

    def probe(self, candidate_index, window_start):
        self.authority.require_catalogue()
        row = candidate_template(candidate_index, window_start)  # Pure October/index guard first.
        nominal = utc(row["expected_nominal"])
        # Discover only the prescribed nominal in its exact month/day directory.
        # The inherited scientific eligibility does not restrict H08 versus H09.
        day_directory = Path(str(legacy.HROOT / nominal.strftime("%Y%m") / nominal.strftime("%d")))
        self.telemetry["2025_CATALOGUE_QC_ACCESS"] = True
        matches = tuple(day_directory.glob("NC_H*_" + nominal.strftime("%Y%m%d_%H%M") + "_*.nc"))
        if len(matches) > 1:
            raise IOError("STOP: ambiguous expected-nominal B13 source identity")
        if matches:
            row["b13_relative_path"] = str(PureWindowsPath(nominal.strftime("%Y%m")) / nominal.strftime("%d") / matches[0].name)
        hpath, ipath = guard_paths(row)
        if hpath is not None and self._exists(hpath):
            self._original_location(hpath, hpath.parents[2])
            row["expected_latest_available"] = "True"
            qc, record = self._staged(
                hpath, lambda local: read_b13_catalogue_qc(local, self.mapping, nominal, self.telemetry),
            )
            row.update({key: str(value) for key, value in qc.items()})
            row.update(b13_bytes=str(record.temporary_bytes), b13_sha256=record.source_sha256)
        else:
            row["b13_relative_path"] = ""
        if self._cached_day_path != ipath:
            day = utc(row["window_start"]).replace(hour=0, minute=0)
            if self._exists(ipath):
                self._original_location(ipath, ipath.parents[1])
                manifest_row = self.manifest.get(_manifest_key(day.date().isoformat(), ipath))
                source_size = ipath.stat().st_size
                qc, record = self._staged(
                    ipath, lambda local: read_imerg_catalogue_qc(
                        local, self.mapping, self.yunnan, day, manifest_row, source_size, self.telemetry,
                    ),
                )
                qc = IMERGDayQC(qc.product, qc.version, qc.run_type, qc.time_grid_provenance_pass,
                                qc.valid_yunnan_counts, record.temporary_bytes, record.source_sha256)
            else:
                qc = IMERGDayQC()
            self._cached_day_path, self._cached_day_qc = ipath, qc
        qc = self._cached_day_qc
        row.update(imerg_bytes=str(qc.source_bytes), imerg_sha256=qc.source_sha256,
                   imerg_product=qc.product, imerg_version=qc.version, imerg_run_type=qc.run_type,
                   imerg_time_grid_provenance_pass=str(qc.time_grid_provenance_pass),
                   imerg_valid_yunnan_count=str(qc.valid_yunnan_counts[int(row["imerg_index"])]))
        return strict_schema(row)
