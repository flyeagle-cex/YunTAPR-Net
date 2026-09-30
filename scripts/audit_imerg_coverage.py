"""IMERG V07 Final day/slot coverage audit; 2025 is inventory only."""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import csv
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import time

import netCDF4
import numpy as np

from yuntapr.contracts.loader import sha256
from yuntapr.data.development_audit import expected_month_slots
from yuntapr.data.imerg_v07 import decode_imerg, validate_final_provenance
from yuntapr.data.masks import read_frozen_yunnan_mask
from yuntapr.data.sample_schema import utc
from yuntapr.data.staging import BoundedEnglishStaging
from yuntapr.spatial.sp04_mapping import load_sp04


SLOT_FIELDS = ("month", "window_start", "analysis_time", "day_path", "index", "status",
               "valid_target_count", "valid_yunnan_count", "zero_yunnan_count",
               "rain_yunnan_count", "max_yunnan_mmhr", "error")


def month_keys():
    return [(y, m) for y in (2023, 2024) for m in range(3, 11)] + [(2025, m) for m in range(3, 10)]


def manifest_lookup(path: Path):
    rows = defaultdict(list)
    with path.open(encoding="utf-8") as stream:
        for line in stream:
            row = json.loads(line)
            if row.get("date", "")[:4] in ("2023", "2024", "2025"):
                rows[(row.get("date"), str(row.get("path", "")).casefold())].append(row)
    return rows


def audit(args):
    if not args.run_dir.is_dir() or not args.local_dir.is_dir():
        raise FileNotFoundError("B13 audit run must exist first")
    mapping = load_sp04()
    yunnan = read_frozen_yunnan_mask(args.mask, mapping)
    stage = BoundedEnglishStaging(args.staging_root, 16777216, True)
    manifest = manifest_lookup(args.manifest)
    slots = []
    months = []
    started = time.perf_counter()
    for year, month in month_keys():
        key = f"{year}{month:02d}"
        day_starts = expected_month_slots(year, month)[::144]
        counts = Counter()
        counts["expected_days"] = len(day_starts)
        counts["expected_30min_slots"] = len(day_starts) * 48
        for day in day_starts:
            path = args.imerg_root / str(year) / f"imerg_{day:%Y%m%d}.nc"
            file_rows = manifest.get((day.date().isoformat(), str(path).casefold()), [])
            complete_rows = [r for r in file_rows if r.get("status") == "complete" and r.get("granules") == 48]
            day_status = "MISSING"
            day_error = ""
            y = valid = times = None
            if path.is_file():
                counts["files"] += 1
                try:
                    with stage.local(path) as english:
                        with netCDF4.Dataset(str(english)) as ds:
                            ds.set_auto_maskandscale(False)
                            attrs = {name: str(ds.getncattr(name)) for name in ds.ncattrs()}
                            if not complete_rows:
                                raise ValueError("MISSING_COMPLETE_48_MANIFEST_ROW")
                            validate_final_provenance(attrs, complete_rows[-1], path.stat().st_size)
                            variable = ds["precipitation"]
                            if variable.dimensions != ("time", "lat", "lon") or variable.shape[1:] != (130, 140) or variable.units != "mm hr-1":
                                raise ValueError("WRONG_TARGET_SHAPE_UNITS")
                            mapping.assert_axes(mapping.axes["native_lat"], mapping.axes["native_lon"],
                                                np.asarray(ds["lat"][10:110]), np.asarray(ds["lon"][20:120]))
                            if variable.shape[0] != 48:
                                raise ValueError("WRONG_SLOT_COUNT")
                            raw = np.asarray(variable[:, 10:110, 20:120])
                            vattrs = {name: variable.getncattr(name) for name in variable.ncattrs()}
                            y, valid = decode_imerg(raw, vattrs)
                            t = ds["time"]
                            times = [utc(v.isoformat() + "Z") for v in netCDF4.num2date(
                                t[:], t.units, calendar=getattr(t, "calendar", "standard"),
                                only_use_cftime_datetimes=False)]
                    day_status = "READABLE_FINAL"
                    counts["readable_final_days"] += 1
                    if len(times) == 48:
                        counts["48_slot_complete_days"] += 1
                except Exception as error:
                    day_error = repr(error)[:500]
                    if "V07 Final" in day_error or "GPM_3IMERG" in day_error or "MISSING_COMPLETE" in day_error:
                        day_status = "WRONG_PRODUCT_OR_PROVENANCE"
                        counts["wrong_product_or_provenance_days"] += 1
                    elif "SLOT_COUNT" in day_error or "SHAPE" in day_error or "axis" in day_error:
                        day_status = "TIME_OR_GRID_MISMATCH"
                        counts["time_or_grid_mismatch_days"] += 1
                    else:
                        day_status = "CORRUPT_OR_UNREADABLE"
                        counts["corrupt_or_unreadable_days"] += 1
            else:
                counts["missing_days"] += 1
            for index in range(48):
                window = day + timedelta(minutes=index * 30)
                slot = dict(month=key, window_start=window.isoformat(),
                            analysis_time=(window + timedelta(minutes=30)).isoformat(),
                            day_path=str(path), index=index, status=day_status,
                            valid_target_count="", valid_yunnan_count="", zero_yunnan_count="",
                            rain_yunnan_count="", max_yunnan_mmhr="", error=day_error)
                if day_status == "READABLE_FINAL":
                    if times[index] != window:
                        slot["status"] = "TIME_MISMATCH"
                        slot["error"] = f"converted={times[index].isoformat()}"
                        counts["time_mismatch_slots"] += 1
                    else:
                        target_valid = valid[index]
                        yn_valid = target_valid & yunnan
                        count = int(target_valid.sum())
                        yn_count = int(yn_valid.sum())
                        slot.update(valid_target_count=count, valid_yunnan_count=yn_count)
                        if year != 2025:
                            values = y[index][yn_valid]
                            slot.update(zero_yunnan_count=int((values == 0).sum()),
                                        rain_yunnan_count=int((values > 0.1).sum()),
                                        max_yunnan_mmhr=float(values.max()) if values.size else "")
                        if not yn_count:
                            slot["status"] = "INVALID_TARGET_SLOT"
                            counts["invalid_target_slots"] += 1
                        else:
                            slot["status"] = "VALID_TARGET_SLOT"
                            counts["valid_target_slots"] += 1
                            if yn_count < 3430:
                                counts["partial_yunnan_target_slots"] += 1
                slots.append(slot)
        zero_fields = ("files", "48_slot_complete_days", "missing_days", "corrupt_or_unreadable_days",
                       "wrong_product_or_provenance_days", "time_or_grid_mismatch_days",
                       "time_mismatch_slots", "invalid_target_slots", "valid_target_slots",
                       "partial_yunnan_target_slots")
        months.append({"month": key, **{field: counts[field] for field in zero_fields},
                       "expected_days": counts["expected_days"],
                       "expected_30min_slots": counts["expected_30min_slots"],
                       "scope": "INTERNAL_FINAL_TEST_COVERAGE_ONLY" if year == 2025 else "DEVELOPMENT"})
        print(json.dumps({"imerg_month_done": key, "elapsed_seconds": round(time.perf_counter() - started, 1),
                          "files": counts["files"], "valid_target_slots": counts["valid_target_slots"]}), flush=True)
    with (args.local_dir / "imerg_per_slot.csv").open("x", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, SLOT_FIELDS)
        writer.writeheader()
        writer.writerows(slots)
    fields = ("month", "scope", "expected_days", "expected_30min_slots", "files", "48_slot_complete_days",
              "missing_days", "corrupt_or_unreadable_days", "wrong_product_or_provenance_days",
              "time_or_grid_mismatch_days", "time_mismatch_slots", "invalid_target_slots",
              "valid_target_slots", "partial_yunnan_target_slots")
    with (args.run_dir / "imerg_v07_coverage.csv").open("x", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(months)
    with (args.local_dir / "imerg_scan_internal.json").open("x", encoding="utf-8") as stream:
        json.dump({"slot_rows": len(slots), "slot_sha256": sha256(args.local_dir / "imerg_per_slot.csv"),
                   "manifest_sha256": sha256(args.manifest), "stage_copies": len(stage.records),
                   "stage_cleanup_failures": sum(not x.cleanup_success for x in stage.records),
                   "scan_seconds": time.perf_counter() - started}, stream, indent=2)
    print(json.dumps({"imerg_scan_complete": True, "slots": len(slots)}), flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("run-dir", "local-dir", "imerg-root", "manifest", "mask", "staging-root"):
        parser.add_argument("--" + name, type=Path, required=True)
    audit(parser.parse_args())


if __name__ == "__main__":
    main()
