"""Approval-bound, once-only E0/COSINE9 fixed-E9 point evaluation.

Import and synthetic validation do not load models or scientific payloads.
Archive reservations describe full input lengths per open, not disk-sector IO.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import stat
import subprocess
import sys
import time
from urllib.parse import parse_qs, unquote, urlsplit

ROOT = Path(__file__).resolve().parents[2]
SCOPE = "TWO_FIXED_E9_B7_2024_JOINT_AMPLITUDE_EVALUATION_V1"
TASKS = ("CONTROL_E0", "CANDIDATE_COSINE9")
MIB = 1024 ** 2
LIMITS = dict(
    payload_archive_reference_bytes=53494753532, payload_open_instances=15906,
    preflight_validations=2, metadata_bytes_per_preflight=80 * MIB,
    metadata_opens_per_preflight=512, metadata_bytes_controller=80 * MIB,
    metadata_opens_controller=512, metadata_bytes_per_worker=225858422,
    metadata_opens_per_worker=1832, total_metadata_cap_bytes=703375085,
    total_metadata_opens=5200, total_source_cap_bytes=54198128617,
    previous_attempt_metadata_bytes=475862623, previous_attempt_metadata_opens=361,
    previous_attempt_payload_bytes=297157300, previous_attempt_payload_opens=71,
    previous_attempt_seconds=51, cumulative_source_cap_bytes=54971148540,
    cumulative_metadata_opens=5632, cumulative_total_opens=21538, cumulative_maximum_seconds=7200,
    maximum_seconds=7149, preflight_seconds=60, controller_seconds=7029,
    per_model_seconds=3000, output_storage_cap_bytes=4 * 1024 ** 3,
    minimum_free_bytes=8 * 1024 ** 3, minimum_host_available_bytes=8 * 1024 ** 3,
    minimum_gpu_free_mib=5120, optimizer_updates=0, retries=0, replay=0,
)
BOOTSTRAP_CAP = 16 * MIB
RAW_SUFFIXES = (".nc", ".nc4", ".hgt", ".hgt.zip", ".h5", ".hdf5", ".hdf",
                ".pt", ".pth", ".ckpt", ".npz", ".npy", ".bin", ".dat",
                ".grib", ".grib2", ".grb", ".tif", ".tiff", ".zarr",
                ".parquet", ".arrow", ".feather", ".db", ".sqlite")
METADATA_SUFFIXES = (".json", ".yaml", ".yml", ".csv", ".md", ".txt", ".toml", ".ini")
POPULATION_SHA256 = "2f2cc75cfb6c209fd8195d3419207216c5c3f2a4fc8315b40a1d77cc537dedb8"
WRITE_FLAGS = os.O_WRONLY | os.O_RDWR | os.O_APPEND | os.O_CREAT | os.O_TRUNC


def now():
    return datetime.now(timezone.utc).isoformat()


def key(path):
    # Lexical normalization avoids thousands of network/source-drive stat calls.
    # Actual opened paths are resolved by the guard before lookup.
    return os.path.normcase(os.path.abspath(os.fsdecode(path)))


def unique_object(pairs):
    value = {}
    for name, item in pairs:
        if name in value:
            raise ValueError("Duplicate JSON key")
        value[name] = item
    return value


def decode(raw):
    return json.loads(raw.decode("utf-8-sig"), object_pairs_hook=unique_object)


def read(path):
    return decode(Path(path).read_bytes())


def sha(path):
    digest_value = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(MIB), b""):
            digest_value.update(chunk)
    return digest_value.hexdigest()


def digest(value):
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    return hashlib.sha256(raw).hexdigest()


def write(path, value):
    with Path(path).open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write("\n")


def module(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    result = importlib.util.module_from_spec(spec)
    sys.modules[name] = result
    spec.loader.exec_module(result)
    return result


class Deadline:
    def __init__(self, seconds, *, absolute_wall=None, monotonic=time.monotonic, wall=time.time):
        self.monotonic, self.wall = monotonic, wall
        self.mono_end = monotonic() + seconds
        self.wall_end = min(wall() + seconds, absolute_wall) if absolute_wall is not None else wall() + seconds

    def remaining(self):
        remaining = min(self.mono_end - self.monotonic(), self.wall_end - self.wall())
        if remaining <= 0:
            raise TimeoutError("Bound wall/monotonic deadline reached")
        return remaining


class OutputLimit:
    def __init__(self, root, maximum, deadline, *, extra_roots=()):
        self.root, self.maximum, self.deadline = Path(root).resolve(), maximum, deadline
        self.roots = (self.root,) + tuple(Path(path).resolve() for path in extra_roots)

    def __call__(self, reserve=0):
        self.deadline.remaining()
        size = 0
        pending = list(self.roots)
        reparse_attribute = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0)
        while pending:
            folder = pending.pop()
            self.deadline.remaining()
            try:
                info = os.lstat(folder)
                if stat.S_ISLNK(info.st_mode) or getattr(info, "st_file_attributes", 0) & reparse_attribute:
                    raise PermissionError("Output directory contains a link or reparse point")
                with os.scandir(folder) as entries:
                    for entry in entries:
                        try:
                            info = entry.stat(follow_symlinks=False)
                        except FileNotFoundError:
                            continue
                        if stat.S_ISLNK(info.st_mode) or getattr(info, "st_file_attributes", 0) & reparse_attribute:
                            raise PermissionError("Output entry contains a link or reparse point")
                        if stat.S_ISDIR(info.st_mode):
                            pending.append(entry.path)
                        else:
                            size += info.st_size
            except FileNotFoundError:
                # SQLite journals and runtime temporary files can disappear
                # during the snapshot. Their targets must never be resolved.
                continue
        if size + reserve > self.maximum:
            raise MemoryError("Output storage cap reached")
        return size


class ReadGuard:
    """Reserve exact metadata and per-task scientific files before each open."""
    def __init__(self, private, *, task=None, metadata_cap, metadata_opens,
                 check, output_roots=(), bootstrap=None, initial_bytes=0, initial_opens=0):
        self.metadata = self._normalize(private["metadata_files"])
        self.scientific = self._normalize(private["scientific_files"])
        if set(self.metadata) & set(self.scientific):
            raise ValueError("Metadata/scientific manifests overlap")
        self.task, self.check = task, check
        self.cap, self.open_cap = metadata_cap, metadata_opens
        self.meta_bytes, self.meta_opens = initial_bytes, initial_opens
        if initial_bytes > metadata_cap or initial_opens > metadata_opens:
            raise PermissionError("Bootstrap metadata exceeds process cap")
        self.bootstrap = bootstrap or {}
        if (set(self.bootstrap) & set(self.metadata)) or (set(self.bootstrap) & set(self.scientific)):
            raise ValueError("Bootstrap inputs must have a unique accounting category")
        self.source_roots = tuple(Path(p).resolve() for p in private["source_roots"])
        self.runtime_roots = tuple(Path(p).resolve() for p in private["runtime_roots"])
        self.output_roots = tuple(Path(p).resolve() for p in output_roots)
        self.engineering_files = {key(private["runtime_python"]), key(__file__)}
        self.null_device = key(Path(os.devnull).resolve())
        self.counts, self.payload_bytes, self.entries = {}, {}, []
        self.active = False
        self.block_subprocess = False

    @staticmethod
    def _normalize(files):
        result = {key(path): info for path, info in files.items()}
        if len(result) != len(files):
            raise ValueError("Input manifest contains duplicate resolved paths")
        for info in result.values():
            if (not isinstance(info.get("bytes"), int) or info["bytes"] < 0
                    or len(info.get("sha256", "")) != 64):
                raise ValueError("Input length and SHA256 must be explicitly bound")
        return result

    def _metadata(self, path, info):
        self.check()
        size = path.stat().st_size
        if size != info["bytes"]:
            raise PermissionError("Metadata length changed")
        if self.meta_bytes + size > self.cap or self.meta_opens + 1 > self.open_cap:
            raise PermissionError("Metadata reservation cap reached before open")
        self.meta_bytes += size
        self.meta_opens += 1
        self.entries.append(dict(category="metadata", source_id=hashlib.sha256(str(path).encode()).hexdigest(), bytes=size))

    def _event(self, event, args):
        if not self.active:
            return
        if self.block_subprocess and event in ("subprocess.Popen", "os.system", "os.fork", "os.posix_spawn", "os.spawn"):
            raise PermissionError("Evaluation workers cannot create subprocesses")
        if event not in ("open", "sqlite3.connect") or not args or not isinstance(args[0], (str, bytes, os.PathLike)):
            return
        value = os.fsdecode(args[0])
        if event == "sqlite3.connect" and value == ":memory:":
            return
        if value.startswith("file:"):
            parsed = urlsplit(value)
            options = parse_qs(parsed.query)
            if event != "sqlite3.connect" or options.get("mode") != ["ro"]:
                raise PermissionError("Only explicit read-only SQLite URIs are admitted")
            value = unquote(parsed.path)
            if os.name == "nt" and value.startswith("/"):
                value = value[1:]
        path = Path(value).resolve()
        identity = key(path)
        if event == "open" and identity == self.null_device:
            return
        if any(path.is_relative_to(root) for root in self.output_roots):
            return
        is_write = event == "open" and bool(args[2] & WRITE_FLAGS)
        if identity in self.scientific:
            self.check()
            info = self.scientific[identity]
            if event != "open" or is_write or self.task not in info["tasks"]:
                raise PermissionError("Scientific input is outside this task's read-only grant")
            count = self.counts.get(identity, 0) + 1
            if count > info["opens_per_task"] or path.stat().st_size != info["bytes"]:
                raise PermissionError("Scientific archive length/open cap changed")
            self.counts[identity] = count
            category = info["category"]
            self.payload_bytes[category] = self.payload_bytes.get(category, 0) + info["bytes"]
            self.entries.append(dict(category=category, source_id=hashlib.sha256(identity.encode()).hexdigest(), bytes=info["bytes"], occurrence=count))
            return
        if identity in self.metadata or identity in self.bootstrap:
            if is_write:
                raise PermissionError("Bound metadata is read-only")
            if event == "sqlite3.connect" and not os.fsdecode(args[0]).startswith("file:"):
                raise PermissionError("Metadata SQLite requires an explicit read-only URI")
            self._metadata(path, self.metadata.get(identity, self.bootstrap.get(identity)))
            return
        if identity in self.engineering_files:
            if is_write:
                raise PermissionError("Bound runtime/source is read-only")
            return
        in_code = any(path.is_relative_to(ROOT / name) for name in ("src", "tools"))
        if in_code and path.suffix.lower() in (".py", ".pyc", ".pyd"):
            if is_write:
                raise PermissionError("Execution code is read-only")
            return
        if any(path.is_relative_to(root) for root in self.source_roots):
            raise PermissionError("Unlisted file under a bound scientific/metadata root")
        if any(path.is_relative_to(root) for root in self.runtime_roots):
            if is_write:
                raise PermissionError("Runtime dependencies are read-only")
            return
        if str(path).lower().endswith(RAW_SUFFIXES + METADATA_SUFFIXES) or event == "sqlite3.connect":
            raise PermissionError("Unlisted scientific input")
        if is_write:
            raise PermissionError("Writes outside the claimed output namespace are forbidden")

    def install(self):
        sys.addaudithook(self._event)
        self.active = True

    def close(self):
        self.active = False
        return dict(metadata_archive_reserved_bytes=self.meta_bytes, metadata_open_instances=self.meta_opens,
                    payload_archive_reserved_bytes=sum(self.payload_bytes.values()),
                    payload_by_category=self.payload_bytes, payload_open_instances=sum(self.counts.values()),
                    reservations=self.entries)


def bootstrap(proposal_path, private_path, approval_path):
    paths = tuple(Path(path).resolve() for path in (proposal_path, private_path, approval_path))
    if len({key(path) for path in paths}) != 3 or not paths[2].is_file():
        raise PermissionError("A separate exact researcher approval is required")
    objects, identities = [], {}
    total = 0
    for path in paths:
        size = path.stat().st_size
        if size > BOOTSTRAP_CAP:
            raise PermissionError("Bootstrap file exceeds 16 MiB")
        with path.open("rb") as stream:
            raw = stream.read(BOOTSTRAP_CAP + 1)
        if len(raw) != size or len(raw) > BOOTSTRAP_CAP:
            raise PermissionError("Bootstrap file changed while reading")
        objects.append(decode(raw))
        identities[key(path)] = dict(bytes=size, sha256=hashlib.sha256(raw).hexdigest())
        total += size
    p, v, a = objects
    validate_grant(p, v, a)
    return p, v, a, identities, total


def validate_grant(p, v, a):
    if (p.get("authorization_scope") != SCOPE or p.get("tasks") != list(TASKS)
            or p.get("budget") != LIMITS or p.get("final_2025_access") is not False):
        raise PermissionError("Only the exact two-task nontraining grant is admitted")
    if digest({name: value for name, value in p.items() if name != "proposal_sha256"}) != p.get("proposal_sha256"):
        raise PermissionError("Proposal canonical identity changed")
    if (v.get("proposal_sha256") != p["proposal_sha256"]
            or digest({name: value for name, value in v.items() if name != "proposal_sha256"}) != p.get("private_preparation_sha256")):
        raise PermissionError("Private source bindings changed")
    expected = dict(approved_by_researcher=True, authorization_scope=SCOPE,
                    proposal_sha256=p["proposal_sha256"], code_commit=p["execution_code_commit"],
                    tasks=p["tasks"], scientific_choices=p["scientific_choices"], budget=LIMITS,
                    output_root=v["output_root"])
    if (not isinstance(a, dict) or any(a.get(name) != value for name, value in expected.items())
            or not str(a.get("decision_id", "")).strip()
            or not str(a.get("researcher_instruction", "")).strip()):
        raise PermissionError("Researcher approval must bind this method, version, data and budget")
    models = p.get("models", [])
    if (len(models) != 2 or [model.get("task") for model in models] != list(TASKS)
            or any(model.get("model") != "B7" or model.get("seed") != 2029 for model in models)):
        raise PermissionError("Exactly the two inherited B7 seed2029 E9 checkpoints are admitted")
    scope = p.get("data_scope", {})
    expected_scope = dict(year=2024, role="Development", scenes=963, n_valid=3303090, n_rain=407820)
    if any(scope.get(name) != value for name, value in expected_scope.items()) or p.get("data_identity", {}).get("population_sha256") != POPULATION_SHA256:
        raise PermissionError("Only frozen 2024 Development is admitted")
    output, preflight = Path(v["output_root"]).resolve(), Path(v["preflight_root"]).resolve()
    input_paths = [Path(path).resolve() for category in ("metadata_files", "scientific_files") for path in v[category]]
    if (output == preflight or output.is_relative_to(preflight) or preflight.is_relative_to(output)
            or any(path.is_relative_to(output) or path.is_relative_to(preflight) for path in input_paths)):
        raise PermissionError("New output/preflight namespaces must be separate from inputs")


def validate_bound_inputs(p, v, *, worker=False):
    for relative, expected in p["code_sha256"].items():
        path = (ROOT / relative).resolve()
        if not path.is_relative_to(ROOT) or sha(path) != expected:
            raise PermissionError("Bound execution source changed")
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    dirty = subprocess.check_output(["git", "-c", "core.longpaths=true", "status", "--porcelain"], cwd=ROOT, text=True).strip()
    if head != p["execution_code_commit"] or dirty:
        raise PermissionError("A clean fixed execution checkout is required")
    runtime = p["runtime"]
    expected_python_sha = runtime.get("executable_sha256", runtime.get("python_executable_sha256"))
    if sha(v["runtime_python"]) != expected_python_sha:
        raise PermissionError("Bound interpreter changed")
    if worker and (Path(sys.executable).resolve() != Path(v["runtime_python"]).resolve()
                   or runtime.get("python_version") != ".".join(map(str, sys.version_info[:3]))):
        raise PermissionError("Worker uses a different bound interpreter")
    for path, info in v["metadata_files"].items():
        if sha(path) != info["sha256"]:
            raise PermissionError("Frozen metadata SHA256 changed")
    validate_scientific_manifest(p, v)


def validate_scientific_manifest(p, v):
    seen = set()
    total_bytes = total_opens = 0
    for path, info in v["scientific_files"].items():
        identity = key(path)
        if identity in seen:
            raise PermissionError("Duplicate resolved scientific source")
        seen.add(identity)
        if info["category"] not in ("weather", "static", "checkpoint") or not info["tasks"] or len(set(info["tasks"])) != len(info["tasks"]) or not set(info["tasks"]).issubset(TASKS):
            raise PermissionError("Scientific source has an invalid category/task grant")
        opens = 2 if info["category"] == "checkpoint" else 1
        if info["opens_per_task"] != opens or (info["category"] != "weather" and Path(path).stat().st_size != info["bytes"]):
            raise PermissionError("Scientific input archive/open binding changed")
        total_bytes += info["bytes"] * opens * len(info["tasks"])
        total_opens += opens * len(info["tasks"])
    if (total_bytes, total_opens) != (LIMITS["payload_archive_reference_bytes"], LIMITS["payload_open_instances"]):
        raise PermissionError("Full source manifest exceeds or differs from the exact payload grant")
    for task in TASKS:
        categories = {}
        for info in v["scientific_files"].values():
            if task in info["tasks"]:
                count, size = categories.get(info["category"], (0, 0))
                categories[info["category"]] = (count + 1, size + info["bytes"])
        model = next(model for model in p["models"] if model["task"] == task)
        expected = dict(weather=(7950, 26639253112), static=(1, 312828), checkpoint=(1, model["checkpoint_bytes"]))
        if categories != expected:
            raise PermissionError("Each arm must retain its exact one-pass weather/static/checkpoint population")
    for model in p["models"]:
        paths = v["tasks"][model["task"]]
        info = v["scientific_files"][paths["checkpoint_path"]]
        report = v["metadata_files"][paths["dev_report_path"]]
        if (info["category"] != "checkpoint" or info["tasks"] != [model["task"]]
                or info["sha256"] != model["checkpoint_sha256"] or info["bytes"] != model["checkpoint_bytes"]
                or report["sha256"] != model["dev_report_sha256"] or report["bytes"] != model["dev_report_bytes"]):
            raise PermissionError("Checkpoint/report identity differs from the exact inherited arm")


def guard_for(v, bootstrap_identities, bootstrap_bytes, deadline, role, task=None):
    suffix = "per_preflight" if role == "preflight" else "per_worker" if role == "worker" else "controller"
    return ReadGuard(v, task=task, metadata_cap=LIMITS["metadata_bytes_" + suffix],
                     metadata_opens=LIMITS["metadata_opens_" + suffix], check=deadline.remaining,
                     output_roots=(v["output_root"], v["preflight_root"]), bootstrap=bootstrap_identities,
                     initial_bytes=bootstrap_bytes, initial_opens=3)


def reserve_preflight(folder, proposal_sha256):
    folder.mkdir(parents=True, exist_ok=True)
    if any((folder / f"failure_{index:02d}.json").exists() for index in (1, 2)):
        raise PermissionError("A failed preflight cannot be retried")
    for index in (1, 2):
        path = folder / f"claim_{index:02d}.json"
        if index == 2 and not (folder / "receipt_01.json").is_file():
            raise PermissionError("The first preflight is incomplete")
        try:
            write(path, dict(proposal_sha256=proposal_sha256, pid=os.getpid(), started=now()))
            return index
        except FileExistsError:
            continue
    raise PermissionError("Both preflight allowances have been consumed")


def package_start(private):
    value = read(Path(private["preflight_root"]) / "claim_01.json")["started"]
    started = datetime.fromisoformat(value)
    if started.tzinfo is None:
        raise PermissionError("The first preflight must have an explicit timezone")
    return started.timestamp()


def validate_entry(proposal_path, private_path, approval_path):
    proposal_path, private_path, approval_path = (Path(path).resolve() for path in (proposal_path, private_path, approval_path))
    deadline = Deadline(LIMITS["preflight_seconds"])
    p, v, a, identities, initial = bootstrap(proposal_path, private_path, approval_path)
    folder = Path(v["preflight_root"])
    index = reserve_preflight(folder, p["proposal_sha256"])
    guard = guard_for(v, identities, initial, deadline, "preflight")
    guard.install()
    try:
        deadline.wall_end = min(deadline.wall_end, package_start(v) + LIMITS["maximum_seconds"])
        deadline.remaining()
        validate_bound_inputs(p, v)
        if Path(v["output_root"]).exists():
            raise PermissionError("The formal output namespace has already been consumed")
        deadline.remaining()
        write(folder / f"receipt_{index:02d}.json", dict(status="PASS", index=index, proposal_sha256=p["proposal_sha256"],
              approval_sha256=identities[key(approval_path)]["sha256"], accounting=guard.close(), finished=now()))
    except BaseException as error:
        write(folder / f"failure_{index:02d}.json", dict(status="STOP_NO_RETRY", error_type=type(error).__name__,
              details=str(error), accounting=guard.close(), finished=now()))
        raise
    finally:
        guard.active = False
    return p, v


def require_preflights(v, p, approval_sha256):
    folder = Path(v["preflight_root"])
    receipts = []
    for index in (1, 2):
        receipt = read(folder / f"receipt_{index:02d}.json")
        if receipt.get("status") != "PASS" or receipt.get("proposal_sha256") != p["proposal_sha256"] or receipt.get("approval_sha256") != approval_sha256 or (folder / f"failure_{index:02d}.json").exists():
            raise PermissionError("Both distinct bounded preflight receipts must pass")
        receipts.append(receipt["accounting"])
    return receipts


def resources(folder):
    monitor = module(ROOT / "tools/core_stage4/monitor/server.py", "paired_point_resources")
    status = monitor.resources(folder)
    gpu, memory = status.get("gpu") or {}, status.get("memory") or {}
    if (status.get("disk_free", 0) < LIMITS["minimum_free_bytes"]
            or memory.get("available", 0) < LIMITS["minimum_host_available_bytes"]
            or gpu.get("total_mib", 0) - gpu.get("used_mib", 0) < LIMITS["minimum_gpu_free_mib"]):
        raise RuntimeError("Fixed disk/RAM/GPU admission failed " + json.dumps(status, sort_keys=True))
    return status


def require_host():
    host = module(ROOT / "tools/research_readiness/start_independent_process.py", "paired_point_host")
    host.require_independent(host.host_identity())


def worker(proposal_path, private_path, approval_path, task):
    proposal_path, private_path, approval_path = (Path(path).resolve() for path in (proposal_path, private_path, approval_path))
    if task not in TASKS:
        raise PermissionError("Unknown fixed task")
    deadline = Deadline(LIMITS["per_model_seconds"])
    p, v, a, identities, initial = bootstrap(proposal_path, private_path, approval_path)
    package = Path(v["output_root"])
    guard = guard_for(v, identities, initial, deadline, "worker", task=task)
    guard.install()
    output = package / task
    claimed = False
    try:
        binding, claim = read(package / "binding.json"), read(package / f"{task}_claim.json")
        expected = dict(task=task, controller_pid=os.getppid(), proposal_sha256=p["proposal_sha256"])
        if (claim != expected or binding["controller_pid"] != os.getppid()
                or binding["approval_sha256"] != identities[key(approval_path)]["sha256"]
                or binding["proposal_sha256"] != p["proposal_sha256"] or binding["code_commit"] != p["execution_code_commit"]):
            raise PermissionError("Worker approval, direct parent or task claim changed")
        if task == TASKS[1] and read(package / TASKS[0] / "task_complete.json")["status"] != "COMPLETE":
            raise PermissionError("Control arm must complete before candidate starts")
        output.mkdir(exist_ok=False)
        claimed = True
        deadline.wall_end = min(deadline.wall_end, binding["absolute_wall_deadline"])
        deadline.remaining()
        validate_bound_inputs(p, v, worker=True)
        guard.block_subprocess = True
        require_host()
        check = OutputLimit(package, LIMITS["output_storage_cap_bytes"], deadline, extra_roots=(v["preflight_root"],))
        provider = module(ROOT / "tools/research_readiness/paired_point_worker.py", "paired_point_provider")
        result = provider.run_task(ROOT, p, v, task, output, check)
        check()
        if result.get("status") != "COMPLETE":
            raise RuntimeError("Task/original-metric gate did not complete")
        accounting = guard.close()
        expected_bytes = sum(info["bytes"] * info["opens_per_task"] for info in v["scientific_files"].values() if task in info["tasks"])
        expected_opens = sum(info["opens_per_task"] for info in v["scientific_files"].values() if task in info["tasks"])
        if (accounting["payload_archive_reserved_bytes"], accounting["payload_open_instances"]) != (expected_bytes, expected_opens):
            raise RuntimeError("Actual scientific reservations differ from the exact task grant")
        write(output / "task_complete.json", dict(status="COMPLETE", task=task, accounting=accounting,
              result=result, proposal_sha256=p["proposal_sha256"], optimizer_updates=0, finished=now()))
    except BaseException as error:
        accounting = guard.close()
        if claimed:
            write(output / "task_failure.json", dict(status="STOP_NO_RETRY", task=task,
                  error_type=type(error).__name__, details=str(error), accounting=accounting, finished=now()))
        raise
    finally:
        guard.active = False


def terminate_child(child):
    if child is not None and child.poll() is None:
        child.kill()
        try:
            child.wait(timeout=10)
        except subprocess.TimeoutExpired as error:
            raise RuntimeError("Worker termination was not confirmed within ten seconds") from error


def totals(accounting):
    metadata_bytes = sum(row["metadata_archive_reserved_bytes"] for row in accounting)
    metadata_opens = sum(row["metadata_open_instances"] for row in accounting)
    payload_bytes = sum(row["payload_archive_reserved_bytes"] for row in accounting)
    payload_opens = sum(row["payload_open_instances"] for row in accounting)
    if (metadata_bytes > LIMITS["total_metadata_cap_bytes"] or metadata_opens > LIMITS["total_metadata_opens"]
            or payload_bytes != LIMITS["payload_archive_reference_bytes"] or payload_opens != LIMITS["payload_open_instances"]
            or metadata_bytes + payload_bytes > LIMITS["total_source_cap_bytes"]):
        raise RuntimeError("Package actual reservations do not match the bounded grant")
    return dict(metadata_archive_reserved_bytes=metadata_bytes, metadata_open_instances=metadata_opens,
                payload_archive_reserved_bytes=payload_bytes, payload_open_instances=payload_opens,
                total_source_reserved_bytes=metadata_bytes + payload_bytes,
                cumulative_source_reserved_bytes=metadata_bytes + payload_bytes + LIMITS["previous_attempt_metadata_bytes"] + LIMITS["previous_attempt_payload_bytes"],
                cumulative_metadata_open_instances=metadata_opens + LIMITS["previous_attempt_metadata_opens"],
                cumulative_total_open_instances=metadata_opens + payload_opens + LIMITS["previous_attempt_metadata_opens"] + LIMITS["previous_attempt_payload_opens"])


def metric_difference(candidate, control):
    if candidate is None or control is None:
        return None
    if (not isinstance(candidate, (int, float)) or isinstance(candidate, bool)
            or not isinstance(control, (int, float)) or isinstance(control, bool)
            or not math.isfinite(candidate) or not math.isfinite(control)):
        raise ValueError("Paired numeric metrics must be finite or explicitly null")
    return candidate - control


def finalize_pair(package, proposal):
    """Pair newly written summaries only, retaining the full reporting contract."""
    package = Path(package)
    summaries = {task: read(package / task / "point_metrics.json") for task in TASKS}
    joint_summaries = {task: read(package / task / "joint_summary.json") for task in TASKS}
    expected_population = dict(scenes=963, n_valid=3303090, n_rain=407820)
    thresholds = (0.1, 1.0, 5.0, 10.0, 20.0, 50.0)
    expected_continuous = ("MAE", "RMSE", "MeanBias", "Pearson_CC")
    expected_metrics = ("TP", "FP", "FN", "TN", "POD", "FAR", "CSI", "Precision", "F1", "ETS", "HSS", "frequency_bias", "truth_equal", "prediction_equal")
    expected_precision = "FP32 predictions and reference rates; strict > FP32 threshold"
    truth_counts = {}
    for task, summary in summaries.items():
        if any(summary.get(name) != value for name, value in expected_population.items()):
            raise ValueError("Fixed paired scene/valid/rain populations differ")
        if (set(summary["methods"]) != {"A", "B", "C"}
                or summary.get("classification_precision") != expected_precision
                or len(summary.get("supervision_mask_sha256", "")) != 64):
            raise ValueError("Point methods, FP32 convention or supervision-mask identity changed")
        for method in ("A", "B", "C"):
            result = summary["methods"][method]
            if any(name not in result["continuous"] for name in expected_continuous):
                raise ValueError("Continuous point metric is missing")
            rows = result["thresholds"]
            if tuple(row["threshold_mm_h"] for row in rows) != thresholds:
                raise ValueError("Exactly the six frozen thresholds in order are required")
            for row in rows:
                if any(name not in row for name in expected_metrics):
                    raise ValueError("Contingency metric or threshold-equality count is missing")
                counts = [row[name] for name in ("TP", "FP", "FN", "TN", "truth_equal", "prediction_equal")]
                if any(not isinstance(value, int) or isinstance(value, bool) or value < 0 for value in counts):
                    raise ValueError("Paired contingency and equality counts must be nonnegative integers")
                if sum(counts[:4]) != expected_population["n_valid"]:
                    raise ValueError("Paired contingency does not close over the fixed valid population")
                threshold = row["threshold_mm_h"]
                positive = row["TP"] + row["FN"]
                reference = truth_counts.setdefault(threshold, (positive, row["truth_equal"]))
                if reference != (positive, row["truth_equal"]):
                    raise ValueError("Truth event/equality counts differ between methods or arms")
                if threshold in (0.1, 20.0) and positive != (407820 if threshold == 0.1 else 717):
                    raise ValueError("Frozen occurrence or strong-rain positive count changed")
    control, candidate = (summaries[task] for task in TASKS)
    if control["supervision_mask_sha256"] != candidate["supervision_mask_sha256"]:
        raise ValueError("Paired supervision-mask digests differ")
    differences = {}
    for method in ("A", "B", "C"):
        left, right = control["methods"][method], candidate["methods"][method]
        differences[method] = dict(
            continuous={name: metric_difference(right["continuous"][name], left["continuous"][name]) for name in expected_continuous},
            thresholds=[dict(threshold_mm_h=a["threshold_mm_h"], **{name: metric_difference(b[name], a[name]) for name in expected_metrics})
                        for a, b in zip(left["thresholds"], right["thresholds"])],
        )
    result = dict(status="COMPLETE_PAIRED_JOINT_AMPLITUDE_DESCRIPTIVE", proposal_sha256=proposal["proposal_sha256"],
                  population=expected_population, supervision_mask_sha256=control["supervision_mask_sha256"],
                  thresholds_mm_h=list(thresholds), main_threshold_mm_h=20.0, classification_precision=expected_precision,
                  continuous_precision="FP64 original physical point proxies and reference rates",
                  difference_direction="CANDIDATE_COSINE9_MINUS_CONTROL_E0", null_difference_policy="Null if either arm is undefined",
                  arms=summaries, differences=differences, scientific_status="NOT_VERIFIED",
                  researcher_knowledge="NOT_ASSESSED", independent_event_count="NOT_IDENTIFIED",
                  source_sha256={task: sha(package / task / "point_metrics.json") for task in TASKS})
    for task, summary in joint_summaries.items():
        model = next(row for row in proposal["models"] if row["task"] == task)
        if (summary.get("status") != "COMPLETE_ARM_STRONG_JOINT_RECORDS"
                or summary.get("checkpoint_sha256") != model["checkpoint_sha256"]
                or summary.get("population_sha256") != POPULATION_SHA256
                or summary.get("n_valid") != expected_population["n_valid"]
                or summary.get("n_strong") != 717
                or summary.get("record_file") != "strong_joint_pixels.npz"):
            raise ValueError("Strong joint output differs from the frozen model/population binding")
        record = package / task / summary["record_file"]
        if record.stat().st_size != summary.get("record_bytes") or sha(record) != summary.get("record_sha256"):
            raise ValueError("Strong joint output file identity differs")
    joint_module = module(ROOT / "tools/research_readiness/paired_joint_amplitude.py", "paired_joint_amplitude_finalize")
    paired_joint = joint_module.pair_strong_records(
        package / TASKS[0] / joint_summaries[TASKS[0]]["record_file"],
        package / TASKS[1] / joint_summaries[TASKS[1]]["record_file"],
        expected_rows=717,
    )
    paired_joint.update({
        "proposal_sha256": proposal["proposal_sha256"],
        "population_sha256": POPULATION_SHA256,
        "arm_strong_joint_counts": {task: joint_summaries[task]["strong_joint_counts"] for task in TASKS},
        "source_sha256": {task: joint_summaries[task]["record_sha256"] for task in TASKS},
        "scientific_status": "NOT_VERIFIED",
        "interpretation": "DESCRIPTIVE_JOINT_EVIDENCE_ONLY",
    })
    for task, arm_name in zip(TASKS, ("E0", "COSINE9")):
        bins = joint_summaries[task].get("strong_probability_bins")
        if (not isinstance(bins, list) or len(bins) != 10
                or [row.get("index") for row in bins] != list(range(10))
                or any(any(type(row.get(key)) is not int or row[key] < 0
                           for key in ("n", "q32_ge_truth", "q32_gt20", "A_gt20", "B_gt20", "C_gt20"))
                       or any(row[key] > row["n"] for key in ("q32_ge_truth", "q32_gt20", "A_gt20", "B_gt20", "C_gt20"))
                       for row in bins)
                or sum(row["n"] for row in bins) != 717):
            raise ValueError("Strong-rain occurrence-probability bins do not close over the fixed population")
        if paired_joint["q32_gt20"].get(arm_name) != joint_summaries[task]["strong_joint_counts"].get("q32_gt20"):
            raise ValueError("Paired q32 threshold count differs from the arm summary")
    paired_joint["arm_strong_probability_bins"] = {
        task: joint_summaries[task]["strong_probability_bins"] for task in TASKS
    }
    write(package / "paired_joint_evidence.json", paired_joint)
    result["paired_joint_evidence_sha256"] = sha(package / "paired_joint_evidence.json")
    write(package / "paired_metrics.json", result)
    return result


def execute(proposal_path, private_path, approval_path):
    proposal_path, private_path, approval_path = (Path(path).resolve() for path in (proposal_path, private_path, approval_path))
    deadline = Deadline(LIMITS["controller_seconds"])
    p, v, a, identities, initial = bootstrap(proposal_path, private_path, approval_path)
    package = Path(v["output_root"])
    guard = guard_for(v, identities, initial, deadline, "controller")
    guard.install()
    child, claimed = None, False
    started_wall = time.time()
    try:
        preflight = require_preflights(v, p, identities[key(approval_path)]["sha256"])
        started_wall = package_start(v)
        deadline.wall_end = min(deadline.wall_end, started_wall + LIMITS["maximum_seconds"])
        deadline.remaining()
        validate_bound_inputs(p, v)
        require_host()
        if Path(sys.executable).resolve() != Path(v["runtime_python"]).resolve():
            raise PermissionError("Controller must use the bound native interpreter")
        admission = resources(package.parent)
        package.mkdir(exist_ok=False)
        claimed = True
        write(package / "binding.json", dict(controller_pid=os.getpid(), proposal_sha256=p["proposal_sha256"],
              approval_sha256=identities[key(approval_path)]["sha256"], code_commit=p["execution_code_commit"],
              absolute_wall_deadline=deadline.wall_end, package_started_wall=started_wall, admission=admission, started=now()))
        check = OutputLimit(package, LIMITS["output_storage_cap_bytes"], deadline, extra_roots=(v["preflight_root"],))
        for task in TASKS:
            check()
            resources(package)
            write(package / f"{task}_claim.json", dict(task=task, controller_pid=os.getpid(), proposal_sha256=p["proposal_sha256"]))
            command = [sys.executable, "-B", str(Path(__file__).resolve()), "worker", "--proposal", str(Path(proposal_path).resolve()),
                       "--private-preparation", str(Path(private_path).resolve()), "--researcher-approval", str(Path(approval_path).resolve()), "--task", task]
            environment = dict(os.environ, PYTHONDONTWRITEBYTECODE="1", PYTHONUTF8="1", PYTHONHASHSEED="2029",
                               CUBLAS_WORKSPACE_CONFIG=":4096:8", OMP_NUM_THREADS="1", MKL_NUM_THREADS="1")
            task_deadline = Deadline(LIMITS["per_model_seconds"], absolute_wall=deadline.wall_end)
            with (package / f"{task}_console.log").open("xb") as log:
                child = subprocess.Popen(command, cwd=ROOT, env=environment, stdout=log, stderr=subprocess.STDOUT,
                                         creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
                while child.poll() is None:
                    check()
                    remaining = min(deadline.remaining(), task_deadline.remaining())
                    try:
                        child.wait(timeout=min(1.0, remaining))
                    except subprocess.TimeoutExpired:
                        pass
            if child.returncode or read(package / task / "task_complete.json")["status"] != "COMPLETE":
                raise RuntimeError("Task failed, all later tasks blocked")
        check()
        worker_records = [read(package / task / "task_complete.json") for task in TASKS]
        finalize_pair(package, p)
        check()
        controller_accounting = guard.close()
        accounting = totals(preflight + [controller_accounting] + [row["accounting"] for row in worker_records])
        write(package / "completion.json", dict(status="COMPLETE_PAIRED_POINT_EVALUATION", tasks=list(TASKS),
              accounting=accounting, results={row["task"]: row["result"] for row in worker_records},
              paired_metrics_sha256=sha(package / "paired_metrics.json"),
              proposal_sha256=p["proposal_sha256"], automatic_retry=False, optimizer_updates=0,
              elapsed_since_first_preflight_seconds=time.time() - started_wall, finished=now()))
    except BaseException as error:
        termination_error = None
        try:
            terminate_child(child)
        except RuntimeError as stop_error:
            termination_error = str(stop_error)
        accounting = guard.close()
        failure_path = package / "failure.json" if claimed else Path(v["preflight_root"]) / "controller_failure.json"
        if failure_path.parent.is_dir():
            write(failure_path, dict(status="STOP_PRESERVE_ALL_NO_RETRY", error_type=type(error).__name__,
                  details=str(error), termination_error=termination_error, controller_accounting=accounting,
                  elapsed_since_first_preflight_seconds=time.time() - started_wall, finished=now()))
        raise
    finally:
        guard.active = False


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("validate", "execute", "worker"))
    parser.add_argument("--proposal", type=Path, required=True)
    parser.add_argument("--private-preparation", type=Path, required=True)
    parser.add_argument("--researcher-approval", type=Path, required=True)
    parser.add_argument("--task", choices=TASKS)
    args = parser.parse_args()
    if args.mode == "validate":
        validate_entry(args.proposal, args.private_preparation, args.researcher_approval)
        print("EXACT_APPROVAL_PREFLIGHT_COMPLETE")
    elif args.mode == "worker":
        worker(args.proposal, args.private_preparation, args.researcher_approval, args.task)
    else:
        execute(args.proposal, args.private_preparation, args.researcher_approval)


if __name__ == "__main__":
    main()
