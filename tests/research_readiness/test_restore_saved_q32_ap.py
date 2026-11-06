"""Tiny temporary synthetic archives only; no actual V3 source is opened."""
from dataclasses import replace
from contextlib import contextmanager
import hashlib
import io
import json
from pathlib import Path
import shutil
from types import SimpleNamespace
import unittest
import uuid
from unittest import mock
import zipfile

import numpy as np
from tools.research_readiness import restore_saved_q32_ap as restore


def encoded(value):
    return json.dumps(value, ensure_ascii=False, allow_nan=False).encode("utf-8")


@contextmanager
def temporary():
    # tempfile's mode=0700 creates an unreadable directory for this sandbox
    # token. Inherit the ordinary workspace permissions on a new UUID leaf;
    # never change permissions on existing directories.
    parent = Path(__file__).parent.resolve(strict=True)
    folder = parent / ("artificial_restore_" + uuid.uuid4().hex)
    folder.mkdir(mode=0o777, exist_ok=False)
    try:
        yield folder
    finally:
        resolved = folder.resolve(strict=True)
        if resolved.parent != parent or not folder.name.startswith("artificial_restore_"):
            raise PermissionError("Refuse cleanup outside the owned artificial fixture")
        shutil.rmtree(resolved)


def arrays(*, different_rate=False):
    rate = np.array([[0., .2, 20.], [21., 50., .1]], dtype=np.float32)
    if different_rate:
        rate[0, 1] = .3  # Same categorical counts, different actual label bytes.
    scores = np.arange(1., 7.).reshape(2, 3)
    q = np.stack([np.linspace(np.log1p(.2), np.log1p(v), 32)
                  for v in scores.ravel()]).reshape(2, 3, 32)
    return dict(scene_id=np.array(["2024-06-30T23:30:00+00:00", "2024-07-01T05:30:00+00:00"]),
                analysis_time=np.array(["2024-07-01T00:00:00+00:00", "2024-07-01T06:00:00+00:00"]),
                pixel_index=np.array([[1, 3, 7], [1, 3, 7]], dtype=np.int32),
                rate=rate, conditional_quantiles_log=q.astype(np.float64))


def archive_bytes(values):
    stream = io.BytesIO()
    np.savez(stream, **values)
    return stream.getvalue()


def fixture(folder, *, changed_seed=None):
    source, output = folder / "source", folder / "new-output"
    source.mkdir(); output.mkdir()
    pins, total = [], 0
    for seed in restore.SEEDS:
        base = source / f"B7_s{seed}"; joint = base / "joint"
        joint.mkdir(parents=True)
        raw = archive_bytes(arrays(different_rate=seed == changed_seed))
        (joint / "chunk_0000.npz").write_bytes(raw)
        total += len(raw)
        item = dict(chunk=0, state="COMPLETE", filename="chunk_0000.npz", scenes=2,
                    pixel_times=6, bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest(), first_scene=0)
        summary = encoded(dict(status="COMPLETE_JOINT_EXPORT_PENDING_FROZEN_GATE_ACCEPTANCE",
                               scenes=2, n_valid=6, n_rain=4, chunks=[item]))
        (joint / "joint_summary.json").write_bytes(summary)
        pins.append((seed, hashlib.sha256(summary).hexdigest()))
        (joint / "chunks.jsonl").write_bytes(encoded(dict(chunk=0, state="INTENT", first_scene=0, scenes=2))
                                             + b"\n" + encoded(item) + b"\n")
        verified = dict(status="COMPLETE_FROZEN_GATE_AND_JOINT_EXPORT", run_id=f"B7_s{seed}",
                        checkpoint_sha256=restore.CHECKPOINTS[seed], joint_summary_sha256=pins[-1][1],
                        optimizer_updates=0, final_2025="FROZEN_NO_ACCESS",
                        original_gate=dict(counts={key: dict(passed=True, stored=value, recomputed=value)
                                                   for key, value in (("n_valid", 6), ("n_rain", 4))},
                                           metrics={"artificial": dict(passed=True)}))
        (base / "verified.json").write_bytes(encoded(verified))
    spec = restore._Spec(2, 3, 1, 2, 2, 1, 1, 4, total, tuple(pins))
    return source, output, spec


def zero_memory():
    return dict(working_set_bytes=0, peak_working_set_bytes=0)


def run_fixture(source, output, spec, **changes):
    return restore.restore_core(source, output, spec=spec, deadline=600,
                                memory_reader=zero_memory, now=lambda: 0., **changes)


class SavedQ32RestoreTests(unittest.TestCase):
    def test_complete_small_fixture_closes_io_and_returns_full_precision_ranking(self):
        with temporary() as folder:
            source, output, spec = fixture(Path(folder))
            result = run_fixture(source, output, spec)
            self.assertEqual(result["status"], "SUCCESS", result.get("failure"))
            self.assertEqual(result["scope"], "SYNTHETIC_FIXTURE_NOT_SCIENCE")
            self.assertEqual(result["io"]["open_attempts"], dict(metadata=9, archive=3))
            self.assertEqual(result["io"]["reserved_bytes"]["archive"], spec.archive_bytes)
            self.assertEqual(result["io"]["reserved_bytes"], result["io"]["delivered_bytes"])
            for row in result["models"]:
                self.assertAlmostEqual(row["ranking"]["AP"], 7 / 12)
                self.assertEqual(float.fromhex(row["AP_float64_hex"]), row["ranking"]["AP"])
            self.assertEqual({v["label_bytes_sha256"] for v in result["models"]}.__len__(), 1)
            records = [json.loads(line) for line in (output / "source_reads.jsonl").read_text().splitlines()]
            self.assertEqual(sum(row["state"] == "READ_INTENT" for row in records), 12)
            self.assertEqual(sum(row["state"] == "READ_COMPLETE" for row in records), 12)
            with self.assertRaises(FileExistsError):
                run_fixture(source, output, spec)

    def test_hash_failure_is_charged_once_and_stops_before_next_archive(self):
        with temporary() as folder:
            source, output, spec = fixture(Path(folder))
            path = source / "B7_s2029/joint/chunk_0000.npz"
            raw = bytearray(path.read_bytes()); raw[-1] ^= 1; path.write_bytes(raw)
            result = run_fixture(source, output, spec)
            self.assertEqual(result["status"], "FAIL")
            self.assertIn("SHA256", result["failure"]["error"])
            self.assertEqual(result["io"]["open_attempts"]["archive"], 1)
            self.assertEqual(result["io"]["retries"], 0)

    def test_cross_model_label_bytes_mismatch_not_rescued_by_equal_counts(self):
        with temporary() as folder:
            source, output, spec = fixture(Path(folder), changed_seed=2030)
            result = run_fixture(source, output, spec)
            self.assertEqual(result["status"], "FAIL")
            self.assertIn("byte identity", result["failure"]["error"])
            self.assertEqual(result["io"]["open_attempts"]["archive"], 2)

    def test_manifest_or_journal_failure_occurs_before_archive_reads(self):
        with temporary() as folder:
            source, output, spec = fixture(Path(folder))
            journal = source / "B7_s2029/joint/chunks.jsonl"
            journal.write_bytes(journal.read_bytes().splitlines()[0] + b"\n")
            result = run_fixture(source, output, spec)
            self.assertEqual(result["status"], "FAIL")
            self.assertEqual(result["io"]["open_attempts"]["archive"], 0)
        with temporary() as folder:
            source, output, spec = fixture(Path(folder))
            bad = replace(spec, summary_sha=((2029, "0" * 64),) + spec.summary_sha[1:])
            result = run_fixture(source, output, bad)
            self.assertEqual(result["status"], "FAIL")
            self.assertEqual(result["io"]["open_attempts"], dict(metadata=1, archive=0))

    def test_metadata_model_identity_cannot_be_rebound(self):
        with temporary() as folder:
            source, output, spec = fixture(Path(folder))
            path = source / "B7_s2029/verified.json"
            row = json.loads(path.read_bytes()); row["checkpoint_sha256"] = "0" * 64
            path.write_bytes(encoded(row))
            result = run_fixture(source, output, spec)
            self.assertEqual(result["status"], "FAIL")
            self.assertEqual(result["io"]["open_attempts"]["archive"], 0)

    def test_budget_timeout_memory_bytes_and_opens_refuse_before_source_open(self):
        with temporary() as folder:
            source = Path(folder)
            expired = restore.ReadBudget(source, lambda _: None, deadline=1,
                                          memory_reader=zero_memory, now=lambda: 1.)
            with self.assertRaises(TimeoutError):
                expired.admit("x", "metadata", 1)
            exhausted = restore.ReadBudget(source, lambda _: None, deadline=1,
                                            memory_reader=zero_memory, now=lambda: 0.)
            with self.assertRaises(MemoryError):
                exhausted.admit("x", "metadata", restore.METADATA_BYTES + 1)
            for i in range(restore.METADATA_OPENS):
                exhausted.admit(str(i), "metadata", 1)
            with self.assertRaises(MemoryError):
                exhausted.admit("overflow", "metadata", 1)
            with self.assertRaises(PermissionError):
                exhausted.admit("0", "metadata", 1)
            heavy = restore.ReadBudget(source, lambda _: None, deadline=1,
                                       memory_reader=lambda: dict(working_set_bytes=restore.RSS_LIMIT + 1,
                                                                  peak_working_set_bytes=restore.RSS_LIMIT + 1),
                                       now=lambda: 0.)
            with self.assertRaises(MemoryError):
                heavy.check()

    def test_zip_names_duplicates_and_uncompressed_size_are_checked_before_load(self):
        raw = archive_bytes(arrays())
        for bad_name in ("../rate.npy", "path/rate.npy", "rate.txt"):
            stream = io.BytesIO()
            with zipfile.ZipFile(stream, "w") as archive:
                archive.writestr(bad_name, b"fake")
            with self.subTest(name=bad_name), self.assertRaises(ValueError):
                restore.inspect_archive(stream.getvalue(), batch=2, spec=replace(restore.FORMAL, pixels=3, batch=2))
        with zipfile.ZipFile(io.BytesIO(raw)) as archive:
            members = archive.infolist()
        with mock.patch.object(zipfile.ZipFile, "infolist", return_value=members + members[:1]):
            with self.assertRaises(ValueError):
                restore.inspect_archive(raw, batch=2, spec=replace(restore.FORMAL, pixels=3, batch=2))
        oversized = [SimpleNamespace(filename=v.filename, file_size=restore.MAX_ZIP_BYTES + 1)
                     for v in members]
        with mock.patch.object(zipfile.ZipFile, "infolist", return_value=oversized):
            with self.assertRaises(ValueError):
                restore.inspect_archive(raw, batch=2, spec=replace(restore.FORMAL, pixels=3, batch=2))

    def test_wrong_numpy_header_dtype_or_shape_rejected_before_np_load(self):
        spec = replace(restore.FORMAL, pixels=3, batch=2)
        for key, bad in (("rate", np.ones((2, 3), dtype=np.float64)),
                         ("rate", np.ones((2, 3), dtype=object)),
                         ("conditional_quantiles_log", np.ones((2, 3, 31)))):
            values = arrays(); values[key] = bad
            with self.subTest(key=key), mock.patch.object(restore.np, "load") as loader:
                with self.assertRaises(ValueError):
                    restore.load_chunk(archive_bytes(values), batch=2, spec=spec)
                loader.assert_not_called()

    def test_bad_time_and_quantile_order_fail_without_repair(self):
        spec = replace(restore.FORMAL, pixels=3, batch=2)
        values = arrays(); values["analysis_time"][1] = "2024-07-01T06:00:00+01:00"
        with self.assertRaises(ValueError):
            restore.load_chunk(archive_bytes(values), batch=2, spec=spec)
        values = arrays(); values["conditional_quantiles_log"][0, 0, 10] = values["conditional_quantiles_log"][0, 0, 9]
        with self.assertRaises(ValueError):
            restore.load_chunk(archive_bytes(values), batch=2, spec=spec)

    def test_parent_monitor_stops_only_its_owned_job_on_timeout_or_memory(self):
        class FakeJob:
            def __init__(self): self.handles = {7: object()}; self.stopped = False
            def snapshot(self): return [7]
            def stop(self): self.stopped = True
        fake_win = SimpleNamespace(exited=lambda _: False,
                                   memory=lambda _: dict(working_set_bytes=restore.RSS_LIMIT + 1,
                                                         peak_working_set_bytes=restore.RSS_LIMIT + 1))
        job = FakeJob()
        with self.assertRaises(TimeoutError):
            restore.monitor_owned_job(job, fake_win, deadline=1., now=lambda: 1.)
        self.assertTrue(job.stopped)
        job = FakeJob()
        with self.assertRaises(MemoryError):
            restore.monitor_owned_job(job, fake_win, deadline=1., now=lambda: 0.)
        self.assertTrue(job.stopped)

    def test_formal_constants_are_not_cli_fixture_options(self):
        self.assertEqual((restore.FORMAL.scenes, restore.FORMAL.pixels, restore.FORMAL.chunks), (963, 3430, 121))
        self.assertEqual(restore.FORMAL.archive_bytes, 3182490198)
        with mock.patch("sys.stderr", io.StringIO()), self.assertRaises(SystemExit):
            restore.main(["--source-root", "fake", "--new-output-root", "fake-new", "--scenes", "2"])


if __name__ == "__main__":
    unittest.main()
