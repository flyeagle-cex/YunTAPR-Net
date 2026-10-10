"""Bounded real-data read-only audit; no model forward or training capability.

Raw sources are exact frozen references, never discovered by directory search.
Every controlled payload read is counted once and SHA checked before in-memory
netCDF decoding. C-library views read an already accounted byte buffer.
"""
from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
import csv
import gc
import hashlib
import io
import json
import ntpath
import os
from pathlib import Path
import re
import time
from unittest.mock import patch

import netCDF4
import numpy as np

SCOPE = "REAL_DATA_READ_ONLY_PREFLIGHT"
BASELINE = "e0920d9375e1f351bc30933cd83b4e7ea41a68ae"
PROTOCOL = "config/science_v2/phase_a_protocol_frozen_v1.json"
PROTOCOL_SHA = "a0141f21cfa997d5adb72dff5afb32b17dc7edcf5f3397fc9c4bfe2ea42048be"
ROOT = Path(__file__).resolve().parents[4]
OUT = ROOT / "docs/phase_b_v2_real_data_preflight/v1"
LIMITS = {"max_scenes": 72, "max_payload_file_bytes": 734003200,
          "max_total_data_bytes": 2 * 1024**3, "max_working_set_bytes": 2 * 1024**3,
          "max_elapsed_seconds": 900}
FLAGS = {"V2_PHASE_B_AUTHORIZED": False, "FORMAL_SCIENTIFIC_EXECUTION_AUTHORIZED": False,
         "RESEARCHER_SCIENTIFIC_APPROVAL_REQUIRED": True,
         "HISTORICAL_RECOVERY_RATIFICATION": "NOT_GRANTED", "FORMAL_OPTIMIZER_STEPS": 0,
         "2025_RAW_ACCESS": 0, "2025_PIXELS_READ": 0,
         "HISTORICAL_CHECKPOINT_READS": 0, "MODEL_FORWARDS": 0,
         "MODEL_PARAMETER_UPDATES": 0, "SCALER_FITS": 0}


def digest_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def select_monthly(rows: list[dict], year: int) -> tuple[list[dict], list[dict]]:
    """Freeze positional selection before any reference precipitation read.

    Use zero-based n//2 for the middle, in original manifest order. Months outside
    frozen March--October are explicitly out of scope, not empty replacements.
    """
    from yuntapr.data.sample_schema import utc
    chosen, monthly = [], []
    for month in range(3, 11):
        subset = [r for r in rows if utc(r["window_start"]).month == month]
        if len(subset) < 3:
            monthly.append({"year": year, "month": month, "count": len(subset),
                            "status": "STOPPED_MONTH_INSUFFICIENT_SCENES"})
            continue
        positions = (0, len(subset)//2, len(subset)-1)
        monthly.append({"year": year, "month": month, "count": len(subset),
                        "positions": positions, "status": "SELECTED_BEFORE_LABEL_ACCESS"})
        for label, position in zip(("FIRST", "MIDDLE", "LAST"), positions):
            row = subset[position]
            chosen.append({"year": year, "month": month, "position": label,
                           "index": int(row["index"]), "sample_id": row["sample_id"],
                           "analysis_time": row["analysis_time"]})
    return chosen, monthly


def memory() -> dict:
    """Windows process-lifetime peak working set, not sampled RSS inference."""
    if os.name != "nt":
        raise RuntimeError("This audited resource collector requires Windows")
    import ctypes
    from ctypes import wintypes
    class Counters(ctypes.Structure):
        _fields_ = [("cb", wintypes.DWORD), ("PageFaultCount", wintypes.DWORD)] + [
            (k, ctypes.c_size_t) for k in ("PeakWorkingSetSize", "WorkingSetSize",
            "QuotaPeakPagedPoolUsage", "QuotaPagedPoolUsage", "QuotaPeakNonPagedPoolUsage",
            "QuotaNonPagedPoolUsage", "PagefileUsage", "PeakPagefileUsage", "PrivateUsage")]
    handle = ctypes.windll.kernel32.GetCurrentProcess()
    values = Counters(); values.cb = ctypes.sizeof(values)
    fn = ctypes.windll.psapi.GetProcessMemoryInfo
    fn.argtypes = [wintypes.HANDLE, ctypes.POINTER(Counters), wintypes.DWORD]
    fn.restype = wintypes.BOOL
    if not fn(handle, ctypes.byref(values), values.cb):
        raise ctypes.WinError()
    return {"working_set_bytes": int(values.WorkingSetSize),
            "peak_working_set_bytes": int(values.PeakWorkingSetSize),
            "private_bytes": int(values.PrivateUsage), "peak_pagefile_bytes": int(values.PeakPagefileUsage)}


class ReadLedger:
    """Application read bytes, not physical storage traffic or OS open count."""
    def __init__(self, private: Path, limits: dict | None = None):
        self.private = private
        self.limits = dict(LIMITS if limits is None else limits)
        self.start = time.perf_counter()
        self.events: list[dict] = []
        self.allowed: dict[Path, dict] = {}
        self.total_data_bytes = 0
        self.total_metadata_bytes = 0
        self.views = 0
        self.stats = 0
        self.stat_failures = []
        self.original_dataset = netCDF4.Dataset

    def register(self, path: Path, kind: str, expected_sha: str, *,
                 year: int | None = None, size: int | None = None) -> Path:
        if kind not in ("PUBLIC_METADATA", "SCALER", "YUNNAN_MASK", "B13", "IMERG"):
            raise ValueError("Unknown read role")
        # Reject forbidden years BEFORE Path.resolve / any filesystem query.
        # Windows realpath may query attributes; it is not a lexical operation.
        if kind in ("B13", "IMERG"):
            if year not in (2023, 2024):
                raise PermissionError("Only frozen 2023/2024 inputs")
            from yuntapr.data.dataset_b1 import H_ROOT, IMERG_ROOT
            base = ntpath.normcase(ntpath.normpath(str(H_ROOT if kind == "B13" else IMERG_ROOT)))
            text = ntpath.normcase(ntpath.normpath(str(path)))
            if not text.startswith(base + "\\"):
                raise PermissionError("Frozen lexical raw source root required")
            relative = text[len(base)+1:]
            match = re.search(r"(202[0-9])(\d{2})", relative if kind == "B13" else ntpath.basename(relative))
            if not match or int(match[1]) != year or not 3 <= int(match[2]) <= 10:
                raise PermissionError("Raw lexical date rejected before filesystem resolution")
        p = path.resolve()
        if kind == "PUBLIC_METADATA" and (not p.is_relative_to(ROOT) or p.suffix.lower() in (".nc", ".npz", ".h5", ".hdf5")):
            raise PermissionError("Public metadata must be a repository artifact, never an observational payload")
        if kind in ("B13", "IMERG"):
            from yuntapr.data.dataset_b1 import guard_source
            guard_source(p, kind)
        if p.suffix.lower() in (".pt", ".pth", ".ckpt"):
            raise PermissionError("Checkpoint byte access forbidden")
        item = {"kind": kind, "sha256": expected_sha, "year": year, "size": size}
        if p in self.allowed and self.allowed[p] != item:
            # Reuse a public reference whose published size was not specified.
            old = self.allowed[p]
            if {k:v for k,v in old.items() if k != "size"} != {k:v for k,v in item.items() if k != "size"}:
                raise ValueError("Conflicting frozen path identity")
            if old["size"] is not None and size is not None and old["size"] != size:
                raise ValueError("Conflicting source size")
            item["size"] = old["size"] if old["size"] is not None else size
        self.allowed[p] = item
        return p

    def check(self):
        if time.perf_counter() - self.start > self.limits["max_elapsed_seconds"]:
            raise RuntimeError("PREFLIGHT_ELAPSED_CAP")
        if memory()["working_set_bytes"] > self.limits["max_working_set_bytes"]:
            raise MemoryError("PREFLIGHT_WORKING_SET_CAP")

    def read(self, path: Path, *, retain: bool = True) -> bytes | None:
        p = path.resolve()
        if p not in self.allowed:
            raise PermissionError("Unregistered path; no fallback or discovery")
        spec = self.allowed[p]
        self.check()
        size = p.stat().st_size
        data = spec["kind"] != "PUBLIC_METADATA"
        if spec["size"] is not None and size != spec["size"]:
            raise ValueError("Frozen source size mismatch")
        if data and (size > self.limits["max_payload_file_bytes"]
                     or self.total_data_bytes + size > self.limits["max_total_data_bytes"]):
            raise MemoryError("PREFLIGHT_BYTE_CAP")
        if data and memory()["working_set_bytes"] + 2*size > self.limits["max_working_set_bytes"]:
            raise MemoryError("PREFLIGHT_PREDICTED_MEMORY_CAP")
        event = {"kind": spec["kind"], "year": spec["year"],
                 "source_sha256": spec["sha256"], "opened_at_utc": utcnow(),
                 "read_open_attempts": 1, "read_open_success": False, "bytes_returned": 0,
                 "status": "STARTED", "file_key": digest_bytes(str(p).encode())}
        self.events.append(event)
        start = time.perf_counter(); h = hashlib.sha256(); pieces = []
        try:
            with p.open("rb") as reader:
                event["read_open_success"] = True
                while block := reader.read(1024*1024):
                    h.update(block)
                    event["bytes_returned"] += len(block)
                    if data: self.total_data_bytes += len(block)
                    else: self.total_metadata_bytes += len(block)
                    if retain: pieces.append(block)
                    self.check()
            if h.hexdigest() != spec["sha256"]:
                raise ValueError("Frozen SHA mismatch; never repair")
            if event["bytes_returned"] != size or p.stat().st_size != size:
                raise ValueError("Source size changed during read")
            event["status"] = "SHA_PASS"
            return b"".join(pieces) if retain else None
        except Exception as exc:
            event["status"] = "FAILED"
            event["exception_type"] = type(exc).__name__
            raise
        finally:
            event["seconds"] = time.perf_counter() - start
            event["closed_at_utc"] = utcnow()
            private_event = {**event, "private_path": str(p)}
            with (self.private / "file_access_private.jsonl").open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(private_event, ensure_ascii=False)+"\n")

    def stat_source(self, path: Path):
        p = path.resolve()
        if p not in self.allowed:
            raise PermissionError("Unregistered stat target")
        self.check(); self.stats += 1
        try:
            st = p.stat()
            if not p.is_file():
                raise FileNotFoundError("Frozen reference is not a regular file")
            expected = self.allowed[p]["size"]
            if expected is not None and st.st_size != expected:
                raise ValueError("Frozen source stat size mismatch")
            return st.st_size
        except Exception as exc:
            detail = {"kind": self.allowed[p]["kind"], "year": self.allowed[p]["year"],
                      "file_key": digest_bytes(str(p).encode()), "exception_type": type(exc).__name__}
            self.stat_failures.append(detail)
            return None

    @contextmanager
    def dataset(self, path, mode="r", *args, **kwargs):
        """No C-library raw path I/O. Disk bytes are read only by self.read."""
        p = Path(path).resolve()
        if mode != "r" or args or kwargs or p not in self.allowed:
            raise PermissionError("Read-only exact-reference netCDF memory view required")
        payload = self.read(p)
        self.views += 1
        with self.original_dataset("readonly_preflight.nc", mode="r", memory=payload) as ds:
            yield ds

    def summary(self) -> dict:
        groups = {}
        for event in self.events:
            key = event["kind"] + ("_"+str(event["year"]) if event["year"] else "")
            bucket = groups.setdefault(key, {"read_open_attempts": 0, "read_open_successes": 0,
                      "bytes_returned": 0, "unique_file_keys": set(), "sha_pass_reads": 0})
            bucket["read_open_attempts"] += 1
            bucket["read_open_successes"] += int(event["read_open_success"])
            bucket["bytes_returned"] += event["bytes_returned"]
            bucket["unique_file_keys"].add(event["file_key"])
            bucket["sha_pass_reads"] += int(event["status"] == "SHA_PASS")
        for bucket in groups.values():
            bucket["unique_files"] = len(bucket.pop("unique_file_keys"))
        return {"scope": SCOPE, "started_from_controlled_process": True, "groups": groups,
                "controlled_read_open_attempts": len(self.events),
                "controlled_read_open_successes": sum(e["read_open_success"] for e in self.events),
                "controlled_application_bytes_returned": sum(e["bytes_returned"] for e in self.events),
                "controlled_data_bytes": self.total_data_bytes,
                "controlled_public_metadata_bytes": self.total_metadata_bytes,
                "in_memory_netcdf_views": self.views, "frozen_reference_stat_checks": self.stats,
                "stat_failures": self.stat_failures, "events": self.events, "limits": self.limits,
                "preliminary_authorized_scaler_inspection": {
                    "tool": "PowerShell Get-Content", "invocations": 1,
                    "occurred_before_controlled_ledger": True,
                    "underlying_os_open_count_and_bytes": "NOT_INSTRUMENTED"},
                "measurement_limits": "Counts are controlled application file reads and returned bytes, not kernel opens, physical disk bytes or all earlier repository inspection. C netCDF consumes accounted memory buffers. Preliminary scaler inspection is separately disclosed.",
                **FLAGS}


def csv_rows(payload: bytes) -> list[dict]:
    return list(csv.DictReader(io.StringIO(payload.decode("utf-8-sig"))))


def audit_rows(model: str, year: int, rows: list[dict], frame_sha: str):
    """Reuse frozen temporal/source validators; check exact role/index binding."""
    from yuntapr.data.dataset_b1 import allowed_time, guard_source, OFFSETS
    from yuntapr.data.sample_schema import utc
    expected_count = 10455 if year == 2023 else 10501
    if len(rows) != expected_count or len({r["sample_id"] for r in rows}) != len(rows):
        raise ValueError("Frozen count/unique IDs mismatch")
    previous = None
    for index, row in enumerate(rows):
        start, analysis = allowed_time(row["window_start"]), utc(row["analysis_time"])
        if (int(row["index"]) != index or int(row["year"]) != year or start.year != year
                or row["sample_id"] != row["window_start"]
                or row["original_b0_sample_id"] != row["sample_id"]
                or analysis != start + timedelta(minutes=30)
                or row["role"] != ("Train" if year == 2023 else "Validation")
                or row["eligibility"] != "FORMAL_M1_COMMON_INTERSECTION"
                or int(row["target_valid_yunnan_cells"]) != 3430
                or row["frame_identity_index_sha256"] != frame_sha):
            raise ValueError("Frozen role/qualification/order identity mismatch")
        if previous is not None and start <= previous:
            raise ValueError("Frozen sample order not strictly chronological")
        previous = start
        guard_source(row["imerg_day_path"], "IMERG")
        if Path(row["imerg_day_path"]).name != "imerg_" + start.strftime("%Y%m%d") + ".nc":
            raise ValueError("IMERG day path not bound to target date")
        if int(row["imerg_index"]) != start.hour*2 + start.minute//30 or start.minute not in (0,30):
            raise ValueError("IMERG half-hour index mismatch")
        slots = [row[f"slot_{i}_nominal"] for i in range(6)] if model == "B1" else [row["expected_nominal"]]
        offsets = OFFSETS if model == "B1" else (10,)
        if any(allowed_time(s) != analysis-timedelta(minutes=o) for s,o in zip(slots,offsets)):
            raise ValueError("Causal slot definition mismatch")
        if model != "B1" and row["selected_slot"] != "5":
            raise ValueError("B0 latest selected slot mismatch")


def paired_ids(a: list[dict], b: list[dict]) -> None:
    keys = ("sample_id", "window_start", "analysis_time", "imerg_day_path", "imerg_index",
            "imerg_sha256", "target_valid_yunnan_cells", "role", "eligibility")
    if [[r[k] for k in keys] for r in a] != [[r[k] for k in keys] for r in b]:
        raise ValueError("B0/B1 paired identity mismatch")
    if any(x["expected_nominal"] != y["slot_5_nominal"] for x,y in zip(a,b)):
        raise ValueError("B0 does not select B1 latest slot")


def normalize_frozen(kelvin: np.ndarray, scaler: dict) -> np.ndarray:
    """Literal frozen dataset_b1.normalize formula, no fitting or clipping."""
    if kelvin.dtype != np.float32 or not np.isfinite(kelvin).all():
        raise ValueError("Frozen finite FP32 Kelvin required")
    if not np.isfinite(scaler["mean_K"]) or not np.isfinite(scaler["std_K"]) or scaler["std_K"] <= 0:
        raise ValueError("Frozen scaler invalid")
    return ((kelvin.astype(np.float64)-scaler["mean_K"])/scaler["std_K"]).astype(np.float32)


def write_json(path: Path, content):
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(content, stream, ensure_ascii=False, indent=2); stream.write("\n")


def run() -> dict:
    """One fixed attempt; any failed gate prevents decoding, no alternate data."""
    import subprocess
    from yuntapr.data import dataset_b1 as frozen
    from yuntapr.data.himawari_b13 import read_b13_local
    from yuntapr.data.imerg_v07 import read_imerg_local
    from yuntapr.data import masks
    from yuntapr.spatial.sp04_mapping import load_sp04
    from yuntapr.data.sample_schema import utc

    private = OUT / ".local" / "attempt_001"
    private.mkdir(parents=True, exist_ok=False)
    started = utcnow(); ledger = ReadLedger(private); results = {}; blockers = []
    decoded = []
    def block(stage, error):
        blockers.append({"stage": stage, "exception_type": type(error).__name__,
                         "reason": str(error) if str(error).isascii() and ":\\" not in str(error) else "See private exception log",
                         "status": "BLOCKED_NO_AUTOMATIC_REPAIR"})
        import traceback
        with (private / "errors_private.log").open("a", encoding="utf-8") as handle:
            handle.write(stage+"\n"+traceback.format_exc()+"\n")

    try:
        head = subprocess.check_output(["git","rev-parse","HEAD"],cwd=ROOT).decode().strip()
        if head != BASELINE:
            raise ValueError("Baseline changed; stop rather than choose another state")
        protocol_path = ledger.register(ROOT/PROTOCOL, "PUBLIC_METADATA", PROTOCOL_SHA)
        protocol = json.loads(ledger.read(protocol_path))
        old_inventory_path = ROOT/"docs/phase_b_v2_formal_runner_candidate/v1/source_identity.json"
        ledger.register(old_inventory_path,"PUBLIC_METADATA","d3daf9803a766648afe1cbdfc7c4add72018afeb1e921967e4a77bdf9cad6927")
        inv = json.loads(ledger.read(old_inventory_path))
        for item in inv["checked_public_files"]:
            ledger.register(ROOT/item["path"],"PUBLIC_METADATA",item["sha256"],size=item["bytes"])
            ledger.read(ROOT/item["path"],retain=False)
        prior_manifest = ROOT/"docs/phase_b_v2_formal_runner_candidate/v1/manifest.json"
        # The manifest and receipt are public Git blobs from the exact baseline.
        def committed_sha(path):
            content = subprocess.check_output(["git","show",BASELINE+":"+path.relative_to(ROOT).as_posix()],cwd=ROOT)
            return digest_bytes(content)
        ledger.register(prior_manifest,"PUBLIC_METADATA",committed_sha(prior_manifest))
        prior = json.loads(ledger.read(prior_manifest))
        for item in prior["files"]:
            ledger.register(ROOT/item["path"],"PUBLIC_METADATA",item["sha256"],size=item["bytes"])
            ledger.read(ROOT/item["path"],retain=False)
        for path in (ROOT/"docs/phase_b_v2_formal_runner_candidate/v1/publication_receipt.json",):
            ledger.register(path,"PUBLIC_METADATA",committed_sha(path)); ledger.read(path,retain=False)
        results["protected_sources"] = {"status":"PASS","prior_public_inventory_files":402,
                                       "prior_delivery_manifest_members":len(prior["files"]),
                                       "tracked_baseline":head}
        # Resolve only paths referenced by the frozen v2 protocol.
        records = {}
        for year in (2023,2024):
            for model,name in (("B1",f"B1_{year}"),("B0_MATCHED",f"B0_MATCHED_{year}")):
                ref = protocol["identity"][name]
                path = ROOT/ref["path"]
                ledger.register(path,"PUBLIC_METADATA",ref["sha256"])
                rows = csv_rows(ledger.read(path)); audit_rows(model,year,rows,frozen.FRAME_SHA)
                records[model,year] = rows
            paired_ids(records["B0_MATCHED",year],records["B1",year])
        if {r["sample_id"] for r in records["B1",2023]} & {r["sample_id"] for r in records["B1",2024]}:
            raise ValueError("Train/development role overlap")
        results["frozen_sample_identity"] = {"status":"PASS", "train_scenes":10455,"development_scenes":10501,
                                             "original_order_unique_disjoint":True,"B0_B1_M1_paired":True}
        selection = []; months = []
        for year in (2023,2024):
            s,m = select_monthly(records["B1",year],year); selection += s; months += m
        if len(selection)>LIMITS["max_scenes"]:
            raise ValueError("Scene cap exceeded")
        selection_payload = {"rule":"FROZEN_ORDER_FIRST_N_FLOOR_HALF_LAST",
                             "frozen_months":[3,4,5,6,7,8,9,10], "selected":selection,"monthly":months,
                             "created_before_reference_pixel_access":True}
        write_json(OUT/"DECODE_SELECTION.json",selection_payload)
        # Original frame index, exact sixteen CSV references, no directory glob.
        frame_index_path = ROOT/frozen.AUDIT/"frame_identity_index.json"
        ledger.register(frame_index_path,"PUBLIC_METADATA",frozen.FRAME_SHA)
        index = json.loads(ledger.read(frame_index_path)); frames = {}
        for rel,expected in index["files"].items():
            path = ROOT/frozen.AUDIT/rel
            if not path.resolve().is_relative_to((ROOT/frozen.AUDIT).resolve()):
                raise ValueError("Frame index escaping frozen directory")
            ledger.register(path,"PUBLIC_METADATA",expected)
            for row in csv_rows(ledger.read(path)):
                if row["nominal"] in frames: raise ValueError("Duplicate frozen nominal")
                frames[row["nominal"]] = row
        sources = {}; usages = 0; min_slack = None; created_after = 0
        for year in (2023,2024):
            for anchor, temporal in zip(records["B0_MATCHED",year], records["B1",year]):
                latest = frames[temporal["slot_5_nominal"]]
                if (anchor["b13_relative_path"] != latest["relative_path"]
                        or anchor["b13_sha256"] != latest["source_sha256"]
                        or int(anchor["b13_bytes"]) != int(latest["source_bytes"])
                        or any(utc(anchor[k]) != utc(latest[k]) for k in ("obs_start", "obs_end", "date_created"))):
                    raise ValueError("B0 latest file/CF identity differs from paired B1 slot5")
            for row in records["B1",year]:
                analysis = utc(row["analysis_time"])
                path = frozen.guard_source(row["imerg_day_path"],"IMERG")
                ledger.register(path,"IMERG",row["imerg_sha256"],year=year)
                sources[path] = ledger.allowed[path]
                for slot in range(6):
                    frame = frames[row[f"slot_{slot}_nominal"]]
                    frozen.check_frame(frame,row["analysis_time"])
                    actual_nominal = utc(frame["nominal"])
                    if "channel" in frame and frame["channel"] != "B13":
                        raise ValueError("Frozen channel changed")
                    path = frozen.guard_source(frozen.H_ROOT/frame["relative_path"],"B13")
                    if actual_nominal.year != year:
                        raise ValueError("Frame year differs from sample year")
                    ledger.register(path,"B13",frame["source_sha256"],year=year,size=int(frame["source_bytes"]))
                    sources[path] = ledger.allowed[path]; usages += 1
                    slack = (analysis-utc(frame["obs_end"])).total_seconds()
                    created_after += int(utc(frame["date_created"]) > analysis)
                    min_slack = slack if min_slack is None else min(min_slack,slack)
        results["temporal_metadata"] = {"status":"PASS","scene_slot_checks":usages,
                                        "nominals_in_index":len(frames),"minimum_obs_end_slack_seconds":min_slack,
                                        "offset_minutes":[60,50,40,30,20,10],"future_observation_count":0}
        results["temporal_metadata"]["file_created_after_analysis_scene_slot_exposures"] = created_after
        results["temporal_metadata"]["operational_realtime_availability"] = "NOT_VERIFIED_BY_OBSERVATION_CAUSALITY"
        by_kind = {k:sum(v["kind"]==k for v in sources.values()) for k in ("B13","IMERG")}
        # Exact reference stats, no drive or folder discovery.
        for path in sources: ledger.stat_source(path)
        results["source_reference_inventory"] = {"unique_files":len(sources),"by_kind":by_kind,
                                                 "stat_checks":ledger.stats,
                                                 "failures":len(ledger.stat_failures),
                                                 "status":"PASS" if not ledger.stat_failures else "BLOCKED",
                                                 "unselected_payload_SHA":"NOT_VERIFIED_LIMITED_READ_SCOPE"}
        if ledger.stat_failures:
            raise FileNotFoundError("Frozen exact references unavailable or sizes changed; decoding gate closed")
    except Exception as error:
        block("FROZEN_METADATA_AND_SOURCE_REFERENCES",error)

    # Independent scaler/geographic audits may complete after raw source failure.
    try:
        if "protocol" not in locals(): raise ValueError("Protocol identity not verified")
        ref = protocol["identity"]["normalization"]; scaler_path = ROOT/ref["path"]
        ledger.register(scaler_path,"SCALER",ref["sha256"])
        scaler = json.loads(ledger.read(scaler_path))
        if (scaler["fit_years"] != [2023] or scaler["fit_role"] != "Train"
                or scaler["fit_scene_count"] != 10455 or not scaler["all_six_slots_share_identical_scaler"]
                or protocol["B0_MATCHED_CONTROL_NORMALIZATION"] != "USE_FROZEN_B1_SHARED_SCALER"
                or not np.isfinite([scaler["mean_K"],scaler["std_K"]]).all() or scaler["std_K"]<=0):
            raise ValueError("Frozen shared train-only scaler contract mismatch")
        mapping = load_sp04(ROOT)
        ref = protocol["identity"]["yunnan_mask"]
        mask_path = Path(ref["path"])
        ledger.register(mask_path,"YUNNAN_MASK",ref["sha256"])
        # read_frozen_yunnan_mask computes SHA before open; use the same counted
        # verified payload in both SHA and the in-memory netCDF view.
        mask_payload = ledger.read(mask_path)
        @contextmanager
        def mask_view(path,*args,**kwargs):
            if Path(path).resolve()!=mask_path.resolve() or args or kwargs:
                raise PermissionError("Only exact frozen mask view")
            ledger.views += 1
            with ledger.original_dataset("mask_readonly.nc",memory=mask_payload) as ds: yield ds
        with patch.object(masks,"sha256",lambda p: digest_bytes(mask_payload) if Path(p).resolve()==mask_path.resolve() else (_ for _ in ()).throw(PermissionError("Mask SHA target mismatch"))), patch.object(netCDF4,"Dataset",mask_view):
            yunnan = masks.read_frozen_yunnan_mask(mask_path,mapping)
        with ledger.original_dataset("mask_metadata_readonly.nc",memory=mask_payload) as ds:
            ledger.views += 1
            mask_dimensions = list(ds["yunnan_mask"].dimensions)
            mask_dtype = str(ds["yunnan_mask"].dtype)
            if mask_dimensions != ["lat","lon"]:
                raise ValueError("Frozen mask axes differ from lat/lon")
        results["scaler_mask_sp04"] = {"status":"PASS","scaler_sha256":frozen.SCALER_SHA,
            "mean_K":scaler["mean_K"],"std_K":scaler["std_K"],"scaler_storage":"JSON number, parsed Python binary64",
            "normalization_calculation_dtype":"float64","normalization_output_dtype":"float32",
            "B0_B1_shared_scaler":True,"refit":False,"mask_sha256":ref["sha256"],
            "mask_native_shape":[130,140],"mask_target_shape":list(yunnan.shape),
            "mask_native_dtype":mask_dtype,"mask_dimensions":mask_dimensions,
            "mask_true_count":int(yunnan.sum()),"mask_distinct_from_observation_validity":True,
            "axes":{k:{"length":len(v),"dtype":str(v.dtype),"direction":"DESCENDING" if np.all(np.diff(v)<0) else "ASCENDING",
                       "first":float(v[0]),"last":float(v[-1]),"raw_bytes_sha256":digest_bytes(v.tobytes())}
                    for k,v in mapping.axes.items()},
            "sp04_indices_shape":list(mapping.indices.shape),"sp04_unique_native_members":int(np.unique(mapping.indices.numpy()).size)}
        del mask_payload
    except Exception as error:
        block("SCALER_MASK_SP04",error)

    if not blockers and "selection" in locals():
        try:
            for selected in selection:
                ledger.check(); start=time.perf_counter(); before=memory()
                row = records["B1",selected["year"]][selected["index"]]
                values=[]; frame_details=[]
                for slot in range(6):
                    frame = frames[row[f"slot_{slot}_nominal"]]
                    path = frozen.guard_source(frozen.H_ROOT/frame["relative_path"],"B13")
                    with patch.object(netCDF4,"Dataset",ledger.dataset):
                        x,valid,actual = read_b13_local(path,mapping,frame["nominal"])
                    if (x.dtype!=np.float32 or x.shape!=(501,501) or valid.dtype!=bool
                            or not valid.all() or not np.isfinite(x).all()):
                        raise ValueError("Actual M1 finite FP32 frame contract failed")
                    if (actual.obs_start!=utc(frame["obs_start"]) or actual.obs_end!=utc(frame["obs_end"])
                            or actual.date_created!=utc(frame["date_created"]) or actual.obs_end>utc(row["analysis_time"])):
                        raise ValueError("Actual CF identity or causal cutoff differs")
                    norm = normalize_frozen(x,scaler)
                    if norm.dtype!=np.float32 or not np.isfinite(norm).all():
                        raise ValueError("Frozen actual normalization nonfinite")
                    values.append(norm)
                    frame_details.append({"slot":slot,"nominal":frame["nominal"],"obs_start":actual.obs_start.isoformat(),
                                          "obs_end":actual.obs_end.isoformat(),"causal":True})
                temporal=np.stack(values); anchor=temporal[5:6]
                if temporal.shape!=(6,501,501) or anchor.shape!=(1,501,501) or not np.array_equal(anchor[0],temporal[5]):
                    raise ValueError("B0/B1 actual tensor assembly mismatch")
                path=frozen.guard_source(row["imerg_day_path"],"IMERG")
                # One counted read for metadata and exact frozen reference reader.
                payload=ledger.read(path)
                @contextmanager
                def imerg_view(candidate,*args,**kwargs):
                    if Path(candidate).resolve()!=path.resolve() or args or kwargs:
                        raise PermissionError("Exact IMERG frozen view required")
                    ledger.views+=1
                    with ledger.original_dataset("imerg_readonly.nc",memory=payload) as ds: yield ds
                with imerg_view(path) as ds:
                    if ds.source!="GPM_3IMERGHH_07" or "IMERG Final Run V07" not in ds.title:
                        raise ValueError("Actual IMERG product/version not frozen Final V07")
                    if ds["precipitation"].shape!=(48,130,140):
                        raise ValueError("Actual IMERG daily coverage differs")
                with patch.object(netCDF4,"Dataset",imerg_view):
                    y,valid,t=read_imerg_local(path,int(row["imerg_index"]),mapping)
                if (t!=utc(row["window_start"]) or y.dtype!=np.float32 or y.shape!=(100,100)
                        or valid.dtype!=bool or int((valid & yunnan).sum())!=3430
                        or not np.isfinite(y[valid]).all() or np.any(y[valid]<0)
                        or np.isfinite(y[~valid]).any()):
                    raise ValueError("Actual target time/eligibility/FP32 contract failed")
                if np.shares_memory(valid,yunnan): raise ValueError("Validity and geographic mask aliased")
                decoded.append({**selected,"status":"PASS","x_B1_shape":[1,6,501,501],"x_B0_shape":[1,1,501,501],
                    "input_dtype":"float32","b13_valid_count_per_slot":251001,"frames":frame_details,
                    "target_shape":[1,1,100,100],"target_dtype":"float32","target_units":"mm hr-1",
                    "IMERG_product":"GPM_3IMERGHH_07 Final V07","target_window_minutes":30,
                    "target_valid_grid_count":int(valid.sum()),"yunnan_valid_count":int((valid & yunnan).sum()),
                    "FP32_threshold":"y_float32 > float32(0.1)","normalization_finite":True,
                    "B0_latest_equals_B1_slot5":True,"seconds":time.perf_counter()-start,
                    "memory_before":before,"memory_after":memory()})
                del values,temporal,anchor,x,norm,y,valid,payload
                gc.collect()
            results["limited_decode"]={"status":"PASS","selected_scenes":len(selection),"decoded_scenes":len(decoded),
                                       "full_raw_dataset_decoded":False}
        except Exception as error:
            block("LIMITED_DECODE",error)
            results["limited_decode"]={"status":"BLOCKED","selected_scenes":len(selection),"decoded_scenes":len(decoded)}
    else:
        results["limited_decode"]={"status":"NOT_VERIFIED","reason":"Earlier prerequisite gate blocked"}
    # Full unselected source content SHA cannot be asserted by a limited decode.
    if results.get("source_reference_inventory",{}).get("status")=="PASS":
        blockers.append({"stage":"FULL_UNSELECTED_PAYLOAD_IDENTITIES","status":"NOT_VERIFIED",
                         "reason":"All frozen paths checked by stat; only deterministic selected payloads byte-hashed. No full raw-file sweep in limited preflight."})
    finished=utcnow()
    result={"scope":SCOPE,"baseline_commit":BASELINE,"started_at_utc":started,"finished_at_utc":finished,
            "elapsed_seconds":time.perf_counter()-ledger.start,"resources":memory(),"checks":results,
            "blockers":blockers,"decoded":decoded,"overall_status":"REAL_DATA_READ_ONLY_PREFLIGHT_PASS" if not blockers else "NOT_VERIFIED",
            "limits":LIMITS,"no_raw_pixels_published":True,**FLAGS}
    write_json(OUT/"audit_results.json",result)
    write_json(OUT/"DATA_ACCESS_LEDGER.json",ledger.summary())
    return result
