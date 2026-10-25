"""Local, request-driven view of existing receipts; never imports training code."""
from __future__ import annotations

import argparse
from contextlib import closing
import ctypes
import hashlib
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import math
import os
import re
from pathlib import Path
import shutil
import sqlite3
import subprocess
import threading
import time
from urllib.parse import urlsplit

HERE = Path(__file__).resolve().parent
LIMITS = dict(updates=8640, per_model=4320, per_epoch=480, epochs=9,
              bytes=955143282024, files=285624)
COMMIT = "5b5298f41025db5b7b718fd736fc3fe6de516875"
POPULATION = "2f2cc75cfb6c209fd8195d3419207216c5c3f2a4fc8315b40a1d77cc537dedb8"


def read_json(path):
    with Path(path).open("rb") as f:
        before = os.fstat(f.fileno())
        if before.st_size > 2 * 1024**2:
            raise ValueError("Metadata exceeds size limit")
        raw = f.read(2 * 1024**2 + 1)
        after = os.fstat(f.fileno())
    if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
        raise ValueError("Metadata write in progress")
    return json.loads(raw)


def query(path, sql):
    # Ordinary read-only SQLite snapshot, including active journals; never immutable=1.
    with closing(sqlite3.connect(Path(path).resolve().as_uri() + "?mode=ro", uri=True,
                                timeout=0.08)) as db:
        db.execute("PRAGMA query_only=ON")
        return db.execute(sql).fetchall()


def process_token(pid):
    """Use only QUERY_LIMITED_INFORMATION; no control handle or process mutation."""
    if not pid or os.name != "nt":
        return None
    from ctypes import wintypes as w
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.OpenProcess.argtypes = [w.DWORD, w.BOOL, w.DWORD]
    kernel.OpenProcess.restype = w.HANDLE
    kernel.CloseHandle.argtypes = [w.HANDLE]
    kernel.GetExitCodeProcess.argtypes = [w.HANDLE, ctypes.POINTER(w.DWORD)]
    kernel.GetProcessTimes.argtypes = [w.HANDLE] + [ctypes.POINTER(w.FILETIME)] * 4
    handle = kernel.OpenProcess(0x1000, False, pid)
    if not handle:
        return None
    try:
        code = w.DWORD()
        stamps = [w.FILETIME() for _ in range(4)]
        if not kernel.GetExitCodeProcess(handle, ctypes.byref(code)) or code.value != 259:
            return None
        if not kernel.GetProcessTimes(handle, *(ctypes.byref(x) for x in stamps)):
            return None
        return stamps[0].dwHighDateTime << 32 | stamps[0].dwLowDateTime
    finally:
        kernel.CloseHandle(handle)


def resources(folder):
    result = dict(gpu=None, memory=None, disk_free=shutil.disk_usage(folder).free)
    if os.name == "nt":
        class Memory(ctypes.Structure):
            _fields_ = [("length", ctypes.c_ulong), ("load", ctypes.c_ulong)] + [
                (x, ctypes.c_ulonglong) for x in ("total_phys", "avail_phys", "total_page",
                                                 "avail_page", "total_virtual", "avail_virtual", "extended")]
        m = Memory()
        m.length = ctypes.sizeof(m)
        if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(m)):
            result["memory"] = dict(total=m.total_phys, available=m.avail_phys, commit_available=m.avail_page)
    try:
        flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
        output = subprocess.check_output([
            "nvidia-smi", "--query-gpu=name,memory.used,memory.total,utilization.gpu,temperature.gpu,power.draw",
            "--format=csv,noheader,nounits"], text=True, timeout=2, creationflags=flags,
            stderr=subprocess.DEVNULL).strip().splitlines()[0].split(",")
        def numeric(x):
            try:
                v = float(x)
                return v if math.isfinite(v) else None
            except ValueError:
                return None
        result["gpu"] = dict(zip(("name", "used_mib", "total_mib", "utilization", "temperature", "power"),
                                  [output[0].strip()] + [numeric(x) for x in output[1:]]))
    except (OSError, subprocess.SubprocessError, IndexError):
        pass
    return result


def metric_summary(report):
    result = {}
    for name, group in report["groups"].items():
        s = group["summary"]
        cov = s.get("coverage", [])
        result[name] = {k: s.get(k) for k in ("scenes", "n_valid", "n_rain", "core_fp64", "brier",
                      "auroc", "average_precision", "conditional_pinball", "q32_signed_bias", "q32_absolute_error")}
        result[name]["q32_coverage"] = cov[-1] if cov else None
        result[name]["ids_sha"] = group.get("ids_sha")
        result[name]["rain_strata"] = [{k: row.get(k) for k in ("upper", "n", "conditional_pinball")}
                                       for row in s.get("rain_strata", [])]
    return result


class Reader:
    def __init__(self, folder, pid=0, recovery_request=None, source_commit=None):
        self.folder = Path(folder).resolve()
        self.pid, self.token = pid, process_token(pid)
        self.cache = None
        self.cached_at = 0
        self.lock = threading.Lock()
        self.fixed = {}
        identity = json.loads(query(self.folder / "updates.sqlite", "SELECT value FROM identity")[0][0])
        d = identity["decision"]
        if d["seed"] != 2029 or d["cap"] != LIMITS["updates"] or d["population_sha256"] != POPULATION:
            raise ValueError("Seed2029 experiment identity mismatch")
        self.identity = identity
        self.source_commit = source_commit or COMMIT
        self.parent = None
        self.prior_updates = self.inherited = 0
        self.limits = dict(LIMITS)
        self.total_passes = 36
        self.base_io = dict(files=0, bytes=0, reserved_bytes=0, sealed=0)
        if "recovery" in identity:
            if not recovery_request:
                raise ValueError("Recovery monitor requires the pinned request")
            request = read_json(recovery_request)
            body = dict(request); expected = body.pop("request_sha256")
            actual = hashlib.sha256(json.dumps(body,sort_keys=True,separators=(",", ":"),allow_nan=False).encode()).hexdigest()
            if expected != actual or expected != identity["recovery"]["request_sha256"]:
                raise ValueError("Recovery request identity mismatch")
            self.parent = Path(request["parent"]).resolve()
            if self.parent != Path(identity["recovery"]["parent"]).resolve():
                raise ValueError("Recovery parent mismatch")
            self.prior_updates = request["prior_updates"]
            self.inherited = request["inherited_updates"]
            self.limits.update(updates=request["cumulative_update_cap"],bytes=request["cumulative_read_cap"],files=request["cumulative_file_cap"])
            self.total_passes = 38
            self.base_io.update(files=request["prior_file_instances"],bytes=request["prior_delivered_bytes"],
                                reserved_bytes=request["prior_reserved_bytes"],sealed=8)
            verified = read_json(self.folder.with_name(self.folder.name+"_source_verification")/"source_verification_receipt.json")
            if verified["states"] != {"READ_COMPLETE":1} or verified["delivered_bytes"] != request["source_verification_bytes"]:
                raise ValueError("Successful one-source verification required")
            for target, key in (("files","opened_files"),("bytes","delivered_bytes"),("reserved_bytes","reserved_bytes")):
                self.base_io[target] += verified[key]

    def document(self, name):
        if name not in self.fixed:
            path = self.folder / name
            # Only sealed E1..E3 metadata are inherited. Never show the lost
            # parent's E4 training loss as if it belonged to the replay.
            if not path.exists() and self.parent and re.fullmatch(r"B3_(?:train|development|LAST_epoch)_0[1-3](?:\.receipt)?\.json",name):
                path = self.parent / name
            if not path.exists():
                return None
            self.fixed[name] = read_json(path)
        return self.fixed[name]

    def snapshot(self, include_resources=True):
        with self.lock:
            if self.cache and time.monotonic() - self.cached_at < 12:
                return self.cache
            started = time.monotonic()
            rows = query(self.folder / "updates.sqlite",
                         "SELECT model,state,COUNT(*),MAX(u) FROM updates GROUP BY model,state")
            updates = {m: dict(returned=0, reserved=0, uncertain=0) for m in ("B3", "B4")}
            for model, state, count, last in rows:
                if model not in updates or state not in ("INTENT", "RETURNED"):
                    raise ValueError("Unexpected update identity/state")
                updates[model]["reserved"] += count
                updates[model]["returned" if state == "RETURNED" else "uncertain"] += count
            segment_returned = sum(v["returned"] for v in updates.values())
            total = self.prior_updates + sum(v["reserved"] for v in updates.values())
            if self.parent:
                updates["B3"]["returned"] += self.inherited
                updates["B3"]["reserved"] += self.inherited
            if total > self.limits["updates"] or any(v["reserved"] > LIMITS["per_model"] for v in updates.values()):
                raise ValueError("Update cap exceeded")
            io = dict(self.base_io, active=[], states={})
            runs = []
            for model in ("B3", "B4"):
                epochs = []
                for epoch in range(1, 10):
                    for role in ("train", "dev"):
                        name = f"{model}_{role}_reads_{epoch:02d}"
                        folder = self.folder / name
                        receipt = self.document(name + "/pass_receipt.json")
                        if receipt:
                            a = receipt["actual_reads"]
                            files, delivered = a["opened_files"], a["delivered_bytes"]
                            reserved, states = a.get("reserved_bytes", delivered), a["states"]
                            io["sealed"] += 1
                        elif (folder / "reads.sqlite").exists():
                            count = query(folder / "reads.sqlite",
                                          "SELECT COUNT(*),COALESCE(SUM(actual_bytes),0),COALESCE(SUM(expected_bytes),0) FROM file_io")[0]
                            files, delivered, reserved = count
                            states = dict(query(folder / "reads.sqlite", "SELECT state,COUNT(*) FROM file_io GROUP BY state"))
                            io["active"].append(dict(model=model, role=role, epoch=epoch, files=files, bytes=delivered))
                        else:
                            continue
                        io["files"] += files
                        io["bytes"] += delivered
                        io["reserved_bytes"] += reserved
                        for state, count in states.items():
                            io["states"][state] = io["states"].get(state, 0) + count
                    train = self.document(f"{model}_train_{epoch:02d}.json")
                    dev = self.document(f"{model}_development_{epoch:02d}.json")
                    last = self.document(f"{model}_LAST_epoch_{epoch:02d}.receipt.json")
                    done = min(480, max(0, updates[model]["returned"] - (epoch - 1) * 480))
                    phase = "SEALED" if last else "VALIDATED" if dev else "VALIDATION" if train else "TRAINING" if done or any(
                        a["model"] == model and a["epoch"] == epoch for a in io["active"]) else "PENDING"
                    epochs.append(dict(epoch=epoch, phase=phase, updates=done,
                                       training_loss=train.get("weighted_mean") if train else None,
                                       metrics=metric_summary(dev) if dev else None,
                                       checkpoint_sha256=last.get("checkpoint_sha256") if last else None))
                runs.append(dict(model=model, **updates[model], sealed_epochs=sum(e["phase"] == "SEALED" for e in epochs), epochs=epochs))
            failure = self.document("failure.json")
            complete = self.document("completion.json")
            live = self.token is not None and process_token(self.pid) == self.token
            returned = self.prior_updates + segment_returned
            effective = sum(v["returned"] for v in updates.values())
            state = "FAILED" if failure else "COMPLETE" if complete and effective == 8640 and returned == self.limits["updates"] else "RUNNING" if live else "UNKNOWN"
            initial = self.document("paired_initial_identity.json") or {}
            result = dict(snapshot_utc=datetime.now(timezone.utc).isoformat(), refresh_seconds=15,
                          read_only=True, state=state, process_observed=live, returned=returned, reserved=total,
                          uncertain=total-returned, limits=self.limits, io=io, runs=runs,
                          effective_updates=effective, prior_updates=self.prior_updates, inherited_updates=self.inherited,
                          segment_updates=segment_returned, total_passes=self.total_passes,
                          resources=resources(self.folder) if include_resources else {},
                          failure=failure, completion=bool(complete), source_commit=self.source_commit,
                          population_sha256=POPULATION, data_identity=self.identity["data"],
                          common_initialization=bool(initial) and initial["B3"]["common_sha256"] == initial["B4"]["common_sha256"],
                          high_altitude_status="NOT_ESTIMABLE_TARGET_DEM_AND_ALTITUDE_EDGES_NOT_FROZEN",
                          collection_ms=round((time.monotonic()-started)*1000, 1))
            self.cache, self.cached_at = result, time.monotonic()
            return result


def handler_for(reader):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_):
            pass

        def reply(self, code, content, mime):
            self.send_response(code)
            self.send_header("Content-Type", mime)
            self.send_header("Content-Length", str(len(content)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Referrer-Policy", "no-referrer")
            self.send_header("Content-Security-Policy", "default-src 'self'; script-src 'self'; style-src 'self'; connect-src 'self'; img-src 'self' data:; object-src 'none'; frame-ancestors 'none'; base-uri 'none'; form-action 'none'")
            self.end_headers()
            try:
                self.wfile.write(content)
            except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
                pass

        def do_GET(self):
            allowed = {f"127.0.0.1:{self.server.server_port}", f"localhost:{self.server.server_port}"}
            if self.headers.get("Host") not in allowed:
                self.reply(403, b"Loopback host required", "text/plain")
                return
            route = urlsplit(self.path).path
            static = {"/": ("index.html", "text/html; charset=utf-8"),
                      "/style.css": ("style.css", "text/css; charset=utf-8"),
                      "/app.js": ("app.js", "text/javascript; charset=utf-8")}
            if route == "/api/snapshot":
                try:
                    data = json.dumps(reader.snapshot(), ensure_ascii=False, allow_nan=False).encode("utf-8")
                    self.reply(200, data, "application/json; charset=utf-8")
                except (OSError, ValueError, KeyError, sqlite3.Error):
                    self.reply(503, b'{"error":"Receipt busy or incomplete; retain last snapshot and refresh."}', "application/json")
            elif route in static:
                name, mime = static[route]
                self.reply(200, (HERE / name).read_bytes(), mime)
            else:
                self.reply(404, b"Not found", "text/plain")

        def do_POST(self):
            self.reply(405, b"Read-only monitor", "text/plain")
        do_PUT = do_DELETE = do_PATCH = do_POST
    return Handler


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--experiment", type=Path, required=True)
    p.add_argument("--training-pid", type=int, default=0)
    p.add_argument("--port", type=int, default=0)
    p.add_argument("--recovery-request", type=Path)
    p.add_argument("--source-commit")
    a = p.parse_args()
    reader = Reader(a.experiment, a.training_pid, a.recovery_request, a.source_commit)
    with ThreadingHTTPServer(("127.0.0.1", a.port), handler_for(reader)) as server:
        service = dict(url=f"http://127.0.0.1:{server.server_port}/", pid=os.getpid(),
                       refresh_seconds=15, read_only=True)
        (HERE / "service.json").write_text(json.dumps(service, indent=2), encoding="utf-8")
        (HERE / "Seed2029 训练监测.url").write_text("[InternetShortcut]\nURL=" + service["url"] + "\n", encoding="utf-8")
        print(service["url"], flush=True)
        server.serve_forever(poll_interval=1)


if __name__ == "__main__":
    main()
