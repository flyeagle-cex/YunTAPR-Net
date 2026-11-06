"""One-shot B7/2024 saved-q32 ranking recovery; no model or inference entry.

CLI constants cannot be relaxed. Data IO means exactly nine named metadata
files and 363 complete archive reads; Python/code imports and new receipts are
outside that data-source counter. Preparation reads are not retroactively
claimed as execution reads. A launch never grants scientific authorization.
"""
from dataclasses import dataclass
from datetime import datetime, timezone
import argparse
import ctypes
import hashlib
import io
import json
import math
import os
from pathlib import Path
import re
import secrets
import stat
import sys
import time
import zipfile

ROOT = Path(__file__).resolve().parents[2]
for _entry in (ROOT / "src", ROOT):
    if str(_entry) not in sys.path:
        sys.path.insert(0, str(_entry))

import numpy as np
from yuntapr.experimental.research_readiness.general_score_ranking import exact_score_ranking

SEEDS = (2029, 2030, 2031)
SECONDS = 600
CLEANUP_RESERVE_SECONDS = 5
RSS_LIMIT = 1024 ** 3
METADATA_BYTES = 8 * 1024 ** 2
METADATA_OPENS = 12
ARCHIVE_BYTES = 3182490198
MAX_ZIP_BYTES = 32 * 1024 ** 2
MAX_MEMBER_BYTES = 8 * 1024 ** 2
MAX_HEADER_BYTES = 8192
MAX_STRING_CHARS = 80
CHECKPOINTS = {
    2029: "019a6dfabf2eef8eeb48bce993eaed64d86b78ea2da3e413e324f22f347f2e35",
    2030: "820796601fa0d0be5c11125171116c7548483b0e3e5ac45c102e5ca5d6ffc15d",
    2031: "4537be7af702efd96d357a64099eb9c55f5cd9d2a4018677908e989c4a730fc7",
}
SUMMARY_SHA = (
    (2029, "99cfadf91d321dc4c4e632225f7700c2af74a3437723e7e472a5e59654e353ae"),
    (2030, "d45e3dacd065e923063422f8657e4b5cb351e309174128c2a8f614ef9cf23f6f"),
    (2031, "746c9e02dcfbe54eeb54d418e51ae83fbac2e6570333fd4adf9e7aa460ddd7b3"),
)
_SHA = re.compile(r"[0-9a-f]{64}\Z")
_MEMBER = re.compile(r"[A-Za-z_][A-Za-z_0-9]*\.npy\Z")
REQUIRED = ("scene_id", "analysis_time", "pixel_index", "rate", "conditional_quantiles_log")


@dataclass(frozen=True)
class _Spec:
    scenes: int
    pixels: int
    chunks: int
    batch: int
    positive: int
    equal20: int
    ge50: int
    wet: int
    archive_bytes: int
    summary_sha: tuple

    @property
    def n(self):
        return self.scenes * self.pixels


FORMAL = _Spec(963, 3430, 121, 8, 717, 2, 6, 407820, ARCHIVE_BYTES, SUMMARY_SHA)


def _utcnow():
    return datetime.now(timezone.utc).isoformat()


def _json(path, value):
    with Path(path).open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(value, stream, ensure_ascii=False, allow_nan=False, indent=2)
        stream.write("\n"); stream.flush(); os.fsync(stream.fileno())


def _pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate JSON key")
        result[key] = value
    return result


def _decode(raw):
    return json.loads(raw.decode("utf-8", errors="strict"), object_pairs_hook=_pairs,
                      parse_constant=lambda value: (_ for _ in ()).throw(ValueError("Nonfinite JSON")))


class ReadBudget:
    """Charge before one complete read, including failed attempts; no refund."""
    def __init__(self, source, emit, *, deadline, memory_reader, archive_limit=ARCHIVE_BYTES,
                 now=time.monotonic):
        self.source = Path(source).resolve(strict=True)
        self.emit, self.deadline, self.memory_reader, self.now = emit, deadline, memory_reader, now
        self.archive_limit = archive_limit
        self.bytes = {"metadata": 0, "archive": 0}
        self.opens = {"metadata": 0, "archive": 0}
        self.delivered = {"metadata": 0, "archive": 0}
        self.seen = set(); self.peak_rss = 0

    def check(self):
        if self.now() >= self.deadline:
            raise TimeoutError("600-second execution deadline")
        memory = self.memory_reader()
        self.peak_rss = max(self.peak_rss, int(memory["working_set_bytes"]),
                            int(memory["peak_working_set_bytes"]))
        if self.peak_rss > RSS_LIMIT:
            raise MemoryError("One-GiB RSS limit")

    def admit(self, key, category, size):
        self.check()
        if category not in self.bytes or type(size) is not int or size <= 0:
            raise ValueError("Explicit positive source reservation required")
        if key in self.seen:
            raise PermissionError("Source already attempted; no retry or second pass")
        cap = METADATA_BYTES if category == "metadata" else self.archive_limit
        count_cap = METADATA_OPENS if category == "metadata" else 363
        if self.bytes[category] + size > cap or self.opens[category] + 1 > count_cap:
            raise MemoryError("Data source byte/open hard cap")
        self.seen.add(key); self.bytes[category] += size; self.opens[category] += 1

    def read(self, relative, category, *, expected_size=None, expected_sha=None):
        self.check()
        relative = Path(relative)
        if relative.is_absolute() or ".." in relative.parts:
            raise PermissionError("No absolute or traversing source member")
        target = self.source / relative
        resolved = target.resolve(strict=True)
        if not resolved.is_relative_to(self.source) or resolved != target:
            raise PermissionError("Source reparse, alias or escape")
        before = target.stat()
        if not stat.S_ISREG(before.st_mode):
            raise PermissionError("Regular source file required")
        if expected_size is not None and before.st_size != expected_size:
            raise ValueError("Source size differs from manifest")
        key = relative.as_posix()
        self.admit(key, category, before.st_size)
        self.emit(dict(state="READ_INTENT", source=key, category=category,
                       reserved_bytes=before.st_size, expected_sha256=expected_sha))
        raw = None
        try:
            with target.open("rb") as stream:
                opened = os.fstat(stream.fileno())
                if (opened.st_size, opened.st_mtime_ns, opened.st_ino) != (
                        before.st_size, before.st_mtime_ns, before.st_ino):
                    raise ValueError("Source changed before read")
                raw = stream.read(before.st_size)  # No extra EOF byte.
                after = os.fstat(stream.fileno())
                if (after.st_size, after.st_mtime_ns, after.st_ino) != (
                        opened.st_size, opened.st_mtime_ns, opened.st_ino):
                    raise ValueError("Source changed during read")
            if len(raw) != before.st_size:
                raise IOError("Short complete-source read")
            self.delivered[category] += len(raw)
            actual = hashlib.sha256(raw).hexdigest()
            if expected_sha is not None and actual != expected_sha:
                raise ValueError("Source SHA256 mismatch")
            self.check()
            self.emit(dict(state="READ_COMPLETE", source=key, category=category,
                           delivered_bytes=len(raw), sha256=actual))
            return raw
        except BaseException as error:
            self.emit(dict(state="READ_FAILED", source=key, category=category,
                           reserved_bytes=before.st_size,
                           observed_returned_bytes=None if raw is None else len(raw),
                           error=type(error).__name__))
            raise

    def receipt(self):
        return dict(reserved_bytes=dict(self.bytes), open_attempts=dict(self.opens),
                    delivered_bytes=dict(self.delivered), peak_rss_bytes=self.peak_rss,
                    retries=0, scope="NAMED_DATA_METADATA_AND_ARCHIVES_ONLY_NOT_CODE_OR_RECEIPTS")


def validate_metadata(summary_raw, journal_raw, verified_raw, *, seed, spec):
    if hashlib.sha256(summary_raw).hexdigest() != dict(spec.summary_sha)[seed]:
        raise ValueError("Pinned joint summary fingerprint mismatch")
    summary, verified = _decode(summary_raw), _decode(verified_raw)
    if (summary.get("status") != "COMPLETE_JOINT_EXPORT_PENDING_FROZEN_GATE_ACCEPTANCE"
            or summary.get("scenes") != spec.scenes or summary.get("n_valid") != spec.n
            or summary.get("n_rain") != spec.wet):
        raise ValueError("Frozen summary status or population changed")
    if (verified.get("status") != "COMPLETE_FROZEN_GATE_AND_JOINT_EXPORT"
            or verified.get("run_id") != f"B7_s{seed}"
            or verified.get("checkpoint_sha256") != CHECKPOINTS[seed]
            or verified.get("joint_summary_sha256") != dict(spec.summary_sha)[seed]
            or verified.get("optimizer_updates") != 0
            or verified.get("final_2025") != "FROZEN_NO_ACCESS"):
        raise ValueError("Frozen model metadata identity changed")
    gate = verified.get("original_gate", {})
    for name, expected in (("n_valid", spec.n), ("n_rain", spec.wet)):
        value = gate.get("counts", {}).get(name, {})
        if value.get("passed") is not True or value.get("stored") != expected or value.get("recomputed") != expected:
            raise ValueError("Original population gate not passed")
    if not gate.get("metrics") or any(v.get("passed") is not True for v in gate["metrics"].values()):
        raise ValueError("Original metric identity gate not passed")
    chunks = summary.get("chunks")
    if not isinstance(chunks, list) or len(chunks) != spec.chunks:
        raise ValueError("Complete fixed chunk manifest required")
    journal = [_decode(line) for line in journal_raw.splitlines()]
    if len(journal) != 2 * len(chunks):
        raise ValueError("Incomplete or additional chunk journal records")
    position = 0
    for number, row in enumerate(chunks):
        batch = min(spec.batch, spec.scenes - position)
        if (set(row) != {"chunk", "state", "filename", "scenes", "pixel_times", "bytes", "sha256", "first_scene"}
                or row["chunk"] != number or row["state"] != "COMPLETE"
                or row["filename"] != f"chunk_{number:04d}.npz"
                or row["first_scene"] != position or row["scenes"] != batch
                or row["pixel_times"] != batch * spec.pixels
                or type(row["bytes"]) is not int or not 0 < row["bytes"] <= MAX_ZIP_BYTES
                or not isinstance(row["sha256"], str) or not _SHA.fullmatch(row["sha256"])):
            raise ValueError("Invalid chunk identity, size, order or coverage")
        intent = dict(chunk=number, state="INTENT", first_scene=position, scenes=batch)
        if journal[2 * number] != intent or journal[2 * number + 1] != row:
            raise ValueError("Chunk journal does not exactly close its manifest")
        position += batch
    if position != spec.scenes:
        raise ValueError("Missing fixed scenes")
    return tuple(chunks)


def _timestamp(value):
    if not isinstance(value, str) or len(value) > MAX_STRING_CHARS:
        raise ValueError("Bounded explicit UTC timestamp required")
    stamp = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if stamp.tzinfo is None or stamp.utcoffset().total_seconds() != 0 or stamp.year != 2024:
        raise ValueError("Only explicit 2024 UTC identities admitted")
    return stamp


def inspect_archive(raw, *, batch, spec):
    """Reject unsafe ZIP/header layouts before np.load; do not read a path."""
    expected = {"scene_id": (batch,), "analysis_time": (batch,),
                "pixel_index": (batch, spec.pixels), "rate": (batch, spec.pixels),
                "conditional_quantiles_log": (batch, spec.pixels, 32)}
    q_cap = spec.batch * spec.pixels * 32 * 8 + MAX_HEADER_BYTES
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        members = archive.infolist(); names = [v.filename for v in members]
        if (not names or len(set(names)) != len(names)
                or any(not _MEMBER.fullmatch(name) for name in names)
                or not {name + ".npy" for name in REQUIRED}.issubset(names)
                or sum(v.file_size for v in members) > MAX_ZIP_BYTES):
            raise ValueError("Unsafe ZIP names, duplicate members or expanded size")
        for member in members:
            cap = q_cap if member.filename == "conditional_quantiles_log.npy" else MAX_MEMBER_BYTES
            if (member.is_dir() or member.flag_bits & 1 or member.file_size <= 0
                    or member.file_size > cap
                    or member.compress_type not in (zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED)):
                raise ValueError("Unsupported or oversized ZIP member")
        for name, shape_expected in expected.items():
            member = archive.getinfo(name + ".npy")
            with archive.open(member) as stream:
                version = np.lib.format.read_magic(stream)
                if version == (1, 0):
                    shape, _, dtype = np.lib.format.read_array_header_1_0(stream, max_header_size=MAX_HEADER_BYTES)
                elif version == (2, 0):
                    shape, _, dtype = np.lib.format.read_array_header_2_0(stream, max_header_size=MAX_HEADER_BYTES)
                else:
                    raise ValueError("Unfrozen NumPy header version")
                if shape != shape_expected or dtype.hasobject:
                    raise ValueError("NumPy header shape or object dtype rejected")
                required_dtype = {"rate": np.dtype("float32"), "pixel_index": np.dtype("int32"),
                                  "conditional_quantiles_log": np.dtype("float64")}.get(name)
                if required_dtype is not None and dtype != required_dtype:
                    raise ValueError("Frozen numeric dtype differs")
                if required_dtype is None and (dtype.kind != "U" or dtype.itemsize > MAX_STRING_CHARS * 4):
                    raise ValueError("Bounded Unicode scene/time fields required")
                if member.file_size != stream.tell() + math.prod(shape) * dtype.itemsize:
                    raise ValueError("NumPy payload byte count differs from safe header")


def load_chunk(raw, *, batch, spec):
    inspect_archive(raw, batch=batch, spec=spec)
    with np.load(io.BytesIO(raw), allow_pickle=False, max_header_size=MAX_HEADER_BYTES) as archive:
        ids, analyses, indices, rate, q = (archive[name] for name in REQUIRED)
    if (not np.isfinite(rate).all() or (rate < 0).any()
            or not np.isfinite(q).all() or not (np.diff(q, axis=-1) > 0).all()
            or not (q[..., 0] > math.log1p(.1)).all()
            or (indices < 0).any() or (indices >= 10000).any()
            or not (np.diff(indices, axis=1) > 0).all()):
        raise ValueError("Invalid frozen scientific array shape/support/order")
    for sid, analysis in zip(ids.tolist(), analyses.tolist()):
        start, end = _timestamp(sid), _timestamp(analysis)
        if ((end - start).total_seconds() != 1800 or end.hour not in (0, 6, 12, 18)
                or end.minute or end.second or end.microsecond):
            raise ValueError("Frozen half-hour/four-UTC identities differ")
    with np.errstate(over="raise", invalid="raise"):
        q32 = np.expm1(q[..., -1]).reshape(-1).copy()
    if not np.isfinite(q32).all():
        raise FloatingPointError("Physical q32 overflow; no clipping")
    return ids, analyses, indices, rate, q32


def restore_core(source, output, *, deadline, memory_reader, spec=FORMAL, now=time.monotonic, nonce="fixture"):
    """Fixture-injectable core. CLI always uses the identity-fixed FORMAL object."""
    output = Path(output)
    _json(output / "worker_once_claim.json", dict(nonce=nonce, pid=os.getpid(), at=_utcnow()))
    events = (output / "source_reads.jsonl").open("x", encoding="utf-8", newline="\n")
    def emit(value):
        events.write(json.dumps(dict(at=_utcnow(), **value), allow_nan=False) + "\n")
        events.flush(); os.fsync(events.fileno())
    budget = ReadBudget(source, emit, deadline=deadline, memory_reader=memory_reader,
                        archive_limit=spec.archive_bytes, now=now)
    started = now(); rows = []; failure = None
    try:
        manifests = {}
        for seed in SEEDS:
            base = Path(f"B7_s{seed}")
            summary = budget.read(base / "joint/joint_summary.json", "metadata", expected_sha=dict(spec.summary_sha)[seed])
            journal = budget.read(base / "joint/chunks.jsonl", "metadata")
            verified = budget.read(base / "verified.json", "metadata")
            manifests[seed] = validate_metadata(summary, journal, verified, seed=seed, spec=spec)
        if (sum(len(v) for v in manifests.values()) != 3 * spec.chunks
                or sum(r["bytes"] for chunks in manifests.values() for r in chunks) != spec.archive_bytes):
            raise ValueError("Fixed archive population or total byte declaration changed")
        reference = None
        for seed in SEEDS:
            budget.check(); scores = np.empty(spec.n, dtype=np.float64)
            if reference is None:
                reference = dict(rate=np.empty(spec.n, dtype=np.float32),
                                 indices=np.empty((spec.scenes, spec.pixels), dtype=np.int32),
                                 ids=[], analyses=[])
            ids_all, analyses_all, position = [], [], 0
            label_hash = hashlib.sha256(); index_hash = hashlib.sha256()
            for item in manifests[seed]:
                budget.check()
                relative = Path(f"B7_s{seed}") / "joint" / item["filename"]
                raw = budget.read(relative, "archive", expected_size=item["bytes"], expected_sha=item["sha256"])
                ids, analyses, indices, rate, score = load_chunk(raw, batch=item["scenes"], spec=spec)
                del raw
                offset, stop = item["first_scene"], item["first_scene"] + item["scenes"]
                flat_start, flat_stop = offset * spec.pixels, stop * spec.pixels
                if offset != position:
                    raise ValueError("Chunk sequence changed")
                if seed == SEEDS[0]:
                    reference["rate"][flat_start:flat_stop] = rate.reshape(-1)
                    reference["indices"][offset:stop] = indices
                    reference["ids"].extend(ids.tolist()); reference["analyses"].extend(analyses.tolist())
                elif (ids.tolist() != reference["ids"][offset:stop]
                      or analyses.tolist() != reference["analyses"][offset:stop]
                      or indices.tobytes() != reference["indices"][offset:stop].tobytes()
                      or rate.tobytes() != reference["rate"][flat_start:flat_stop].tobytes()):
                    raise ValueError("Cross-model scene/time/pixel/label byte identity mismatch")
                label_hash.update(rate.tobytes()); index_hash.update(indices.tobytes())
                ids_all.extend(ids.tolist()); analyses_all.extend(analyses.tolist())
                scores[flat_start:flat_stop] = score
                position = stop
                del ids, analyses, indices, rate, score
                budget.check()
            times = [_timestamp(v) for v in analyses_all]
            if (position != spec.scenes or len(set(ids_all)) != spec.scenes
                    or any(b <= a for a, b in zip(times, times[1:]))):
                raise ValueError("Missing, duplicate or reordered scene identity")
            rate = reference["rate"]
            truth = rate > np.float32(20)
            counts = dict(n=rate.size, positive=int(truth.sum()), equal20=int((rate == np.float32(20)).sum()),
                          ge50=int((rate >= np.float32(50)).sum()), wet=int((rate > np.float32(.1)).sum()))
            if counts != dict(n=spec.n, positive=spec.positive, equal20=spec.equal20, ge50=spec.ge50, wet=spec.wet):
                raise ValueError("Frozen strict/equality/rain population counts differ")
            budget.check()
            ranking = exact_score_ranking(scores, truth, score_semantics="CONDITIONAL_Q32_MM_H_R_GT20_LABEL")
            budget.check()
            rows.append(dict(seed=seed, checkpoint_sha256=CHECKPOINTS[seed], counts=counts,
                             joint_summary_sha256=dict(spec.summary_sha)[seed],
                             label_bytes_sha256=label_hash.hexdigest(), pixel_bytes_sha256=index_hash.hexdigest(),
                             ranking=ranking, AP_float64_hex=ranking["AP"].hex(),
                             AUROC_float64_hex=ranking["AUROC"].hex()))
            emit(dict(state="MODEL_COMPLETE", seed=seed, counts=counts))
            del scores, truth, rate
        if (budget.opens != {"metadata": 9, "archive": 3 * spec.chunks}
                or budget.bytes["archive"] != spec.archive_bytes
                or budget.delivered != budget.bytes):
            raise ValueError("Data-source meter did not close exactly")
    except BaseException as error:
        failure = dict(error_class=type(error).__name__, error=str(error))
    finally:
        events.close()
    result = dict(status="FAIL" if failure else "SUCCESS", at=_utcnow(), failure=failure,
                  scope="FORMAL_FIXED_V3" if spec is FORMAL else "SYNTHETIC_FIXTURE_NOT_SCIENCE",
                  models=rows, io=budget.receipt(), elapsed_seconds=now() - started,
                  new_inference_passes=0, optimizer_updates=0, extra_retries=0,
                  final_2025_access=0, scientific_acceptance="NOT_VERIFIED",
                  independent_events="NOT_IDENTIFIED")
    _json(output / "receipt.json", result)
    return result


def monitor_owned_job(job, win, *, deadline, now=time.monotonic, nap=time.sleep):
    peak = 0
    try:
        while True:
            if now() >= deadline:
                raise TimeoutError("600-second parent deadline")
            members = job.snapshot()
            if len(members) > 2:
                raise RuntimeError("Unexpected owned process count")
            tree = 0
            for pid in members:
                handle = job.handles[pid]
                if not win.exited(handle):
                    sample = win.memory(handle)
                    peak = max(peak, sample["peak_working_set_bytes"])
                    tree += sample["working_set_bytes"]
            peak = max(peak, tree)
            if peak > RSS_LIMIT:
                raise MemoryError("Owned Job RSS limit")
            if not members:
                codes = {str(pid): win.code(handle) for pid, handle in job.handles.items() if win.exited(handle)}
                if not codes or any(value != 0 for value in codes.values()):
                    raise RuntimeError("Owned worker failed")
                return dict(peak_sampled_rss_bytes=peak, exit_codes=codes)
            nap(.05)
    except BaseException:
        job.stop()
        raise


def launch(source, output):
    from yuntapr.experimental.phase_b_v2_execution_watchdog_candidate import winjob as win
    started = time.monotonic(); deadline = started + SECONDS - CLEANUP_RESERVE_SECONDS
    source, output = Path(source).resolve(strict=True), Path(output).resolve()
    if source.name != "extreme_diagnostic_execution_20261031_v3" or "2025" in str(source):
        raise PermissionError("Only the explicitly named existing V3 development output")
    if output == source or output.is_relative_to(source) or source.is_relative_to(output):
        raise PermissionError("New receipt root cannot overlap old source")
    output.mkdir(exist_ok=False)
    nonce = secrets.token_hex(24)
    argv = [sys.executable, "-B", str(Path(__file__).resolve()), "--source-root", str(source),
            "--new-output-root", str(output), "--worker", "--nonce", nonce,
            "--deadline-monotonic", repr(deadline)]
    _json(output / "parent_launch.json", dict(state="LAUNCH_INTENT_NOT_APPROVAL", at=_utcnow(),
          source_root=str(source), new_output_root=str(output), nonce=nonce, argv=argv,
          started_monotonic=started, deadline_monotonic=deadline, seconds=SECONDS,
          cleanup_reserve_seconds=CLEANUP_RESERVE_SECONDS,
          rss_bytes=RSS_LIMIT, metadata_bytes=METADATA_BYTES, metadata_opens=METADATA_OPENS,
          archive_bytes=ARCHIVE_BYTES, archive_opens=363, optimizer_updates=0, retries=0))
    job = None; failure = None; monitor = {}; clean = False
    try:
        job = win.Job()
        limits = win.ExtendedLimit()
        limits.basic.flags = 0x2000 | 0x8 | 0x200
        limits.basic.active_limit = 2; limits.job_memory = RSS_LIMIT
        win.checked(win.set_job(job.handle, 9, ctypes.byref(limits), ctypes.sizeof(limits)))
        job.spawn(argv, ROOT)
        monitor = monitor_owned_job(job, win, deadline=deadline)
        receipt = _decode((output / "receipt.json").read_bytes())
        if receipt.get("status") != "SUCCESS" or receipt.get("scope") != "FORMAL_FIXED_V3":
            raise RuntimeError("Worker receipt missing or unsuccessful")
    except BaseException as error:
        failure = dict(error_class=type(error).__name__, error=str(error))
    finally:
        if job is not None:
            try:
                job.stop()
                until = min(started + SECONDS, time.monotonic() + 3)
                while time.monotonic() < until:
                    if not job.pids() and all(win.exited(h) for h in job.handles.values()):
                        clean = True; break
                    time.sleep(.02)
                if not clean:
                    failure = failure or dict(error_class="CleanupFailure", error="Owned Job termination not verified")
            except BaseException as error:
                failure = failure or dict(error_class=type(error).__name__, error=str(error))
            finally:
                job.close()
        else:
            clean = True
        if time.monotonic() - started >= SECONDS:
            failure = failure or dict(error_class="TimeoutError", error="Whole package including cleanup exceeded 600 seconds")
        if not (output / "receipt.json").exists():
            _json(output / "receipt.json", dict(status="FAIL", emitter="PARENT_AFTER_ABNORMAL_CHILD",
                  failure=failure, source_io="SEE_DURABLE_SOURCE_READS_IF_PRESENT_NOT_INVENTED",
                  scientific_acceptance="NOT_VERIFIED"))
        _json(output / "parent_end.json", dict(status="FAIL" if failure else "SUCCESS", at=_utcnow(),
              failure=failure, elapsed_seconds=time.monotonic() - started, owned_cleanup_verified=clean,
              monitor=monitor, extra_retries=0, scientific_acceptance="NOT_VERIFIED"))
    return 1 if failure else 0


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-root", required=True)
    parser.add_argument("--new-output-root", required=True)
    parser.add_argument("--worker", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--nonce", help=argparse.SUPPRESS)
    parser.add_argument("--deadline-monotonic", type=float, help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    if not args.worker:
        if args.nonce is not None or args.deadline_monotonic is not None:
            parser.error("Internal worker arguments are not configurable execution limits")
        return launch(args.source_root, args.new_output_root)
    output = Path(args.new_output_root).resolve(strict=True)
    claim = _decode((output / "parent_launch.json").read_bytes())
    if (args.nonce != claim.get("nonce") or args.deadline_monotonic != claim.get("deadline_monotonic")
            or claim.get("seconds") != SECONDS
            or claim.get("cleanup_reserve_seconds") != CLEANUP_RESERVE_SECONDS
            or claim.get("deadline_monotonic") - claim.get("started_monotonic") != SECONDS - CLEANUP_RESERVE_SECONDS
            or str(Path(args.source_root).resolve(strict=True)) != claim.get("source_root")
            or str(output) != claim.get("new_output_root")):
        raise PermissionError("Worker must match the once-created parent launch")
    if "torch" in sys.modules:
        raise PermissionError("No Torch or model runtime in saved-output statistics")
    from yuntapr.experimental.phase_b_v2_real_forward_pilot.resources import memory
    result = restore_core(args.source_root, output, deadline=args.deadline_monotonic,
                          memory_reader=memory, nonce=args.nonce)
    return 0 if result["status"] == "SUCCESS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
