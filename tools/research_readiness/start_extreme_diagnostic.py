"""Once-only approval-bound 2023-label / nine-E9 2024 diagnostic controller.

Importing this module never imports torch or opens scientific payloads. All
approval, code, model, resource and lifetime gates precede those operations.
No training, replay, retries, smoke inference, or 2025 reader is available.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
SCOPE = "ONE_2023_LABEL_PASS_AND_NINE_FIXED_E9_2024_DIAGNOSTIC_PASSES"
ORDER = ("TRAIN_LABELS", "B7_s2029", "B8_s2029", "B4_s2029", "B7_s2030", "B8_s2030", "B4_s2030", "B7_s2031", "B8_s2031", "B4_s2031")
LIMITS = dict(weather_static_label_bytes=239935204070, weather_static_label_instances=71802,
              checkpoint_archive_bytes=482176887, checkpoint_sha_passes=9, checkpoint_loads=9,
              checkpoint_archive_reference_bytes=964353774, payload_archive_reference_bytes=240899557844,
              metadata_archive_cap_bytes=1024**3, metadata_open_cap=2048,
              worker_metadata_archive_cap_bytes=64*1024**2, worker_metadata_open_cap=128,
              total_source_reservation_cap_bytes=241973299668,
              maximum_seconds=21600, per_model_seconds=2400, label_seconds=600,
              output_storage_cap_bytes=16*1024**3, minimum_free_bytes=32*1024**3,
              minimum_host_available_bytes=8*1024**3, minimum_gpu_free_mib=5120,
              optimizer_updates=0, retries=0, replay=0)


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def write(path, value):
    with Path(path).open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write("\n")


def module(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    value = importlib.util.module_from_spec(spec)
    sys.modules[name] = value
    spec.loader.exec_module(value)
    return value


def validate_grant(proposal, private, approval):
    """Pure identity gate; never infer approval from a previous consumed grant."""
    if (proposal.get("authorization_scope") != SCOPE or proposal.get("tasks") != list(ORDER)
            or proposal.get("budget") != LIMITS
            or proposal.get("final_2025_access") is not False):
        raise PermissionError("Exact nontraining / no-2025 scope required")
    models = proposal.get("models", [])
    expected_models = {(model, seed) for model in ("B4", "B7", "B8") for seed in (2029, 2030, 2031)}
    if len(models) != 9 or {(m.get("model"), m.get("seed")) for m in models} != expected_models:
        raise PermissionError("Exactly nine inherited core models; no added seed or control")
    expected = dict(approved_by_researcher=True, authorization_scope=SCOPE,
                    proposal_sha256=proposal.get("proposal_sha256"),
                    code_commit=proposal.get("execution_code_commit"),
                    tasks=proposal.get("tasks"), scientific_choices=proposal.get("scientific_choices"),
                    budget=proposal.get("budget"), output_root=private.get("output_root"))
    if (not isinstance(approval, dict) or any(approval.get(k) != v for k, v in expected.items())
            or not isinstance(approval.get("decision_id"), str) or not approval["decision_id"].strip()
            or not isinstance(approval.get("researcher_instruction"), str)
            or not approval["researcher_instruction"].strip()):
        raise PermissionError("New researcher decision bound to exact method, commit and limits required")
    if digest({k: v for k, v in proposal.items() if k != "proposal_sha256"}) != proposal.get("proposal_sha256"):
        raise ValueError("Proposal bytes/normalized identity changed")
    if private.get("proposal_sha256") != proposal["proposal_sha256"]:
        raise ValueError("Private preparation does not bind this proposal")


def validate_only(proposal_path, private_path, approval_path, *, worker_task=None):
    if not Path(approval_path).is_file():
        raise PermissionError("No exact new approval; scientific payload access remains disabled")
    p, v, a = read(proposal_path), read(private_path), read(approval_path)
    validate_grant(p, v, a)
    validate_runtime_files(p, v)
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    dirty = subprocess.check_output(["git", "-c", "core.longpaths=true", "status", "--porcelain"], cwd=ROOT, text=True).strip()
    if head != p["execution_code_commit"] or dirty:
        raise PermissionError("Clean fixed execution checkout required")
    for name, expected in p["code_sha256"].items():
        if sha(ROOT / name) != expected:
            raise ValueError("Execution source changed")
    output = Path(v["output_root"])
    if worker_task is None:
        if output.exists():
            raise PermissionError("Consumed output namespace; no restart or recovery")
    else:
        if worker_task not in ORDER or not output.is_dir():
            raise PermissionError("Exact live serial controller required")
        binding = read(output / "binding.json")
        claim = read(output / (worker_task + "_claim.json"))
        expected = dict(controller_pid=os.getppid(), proposal_sha256=p["proposal_sha256"], task=worker_task)
        if (binding["controller_pid"] != os.getppid() or binding["approval_sha256"] != sha(approval_path)
                or claim != expected):
            raise PermissionError("Direct controller identity or once-only task claim differs")
    for name in ("engine", "registry"):
        if sha(v[name]) != p[name + "_sha256"]:
            raise ValueError("Frozen provider or registry changed")
    registry = read(v["registry"])
    runs = {r["run_id"]: r for r in registry["runs"]}
    for model in p["models"]:
        if worker_task is not None and model["run_id"] != ("B4_s2029" if worker_task == "TRAIN_LABELS" else worker_task):
            continue
        run = runs[model["run_id"]]
        if (run["model"] != model["model"] or int(run["seed"]) != model["seed"]
                or run["checkpoint_sha256"] != model["checkpoint_sha256"]
                or run["checkpoint_bytes"] != model["checkpoint_bytes"]
                or run["stored_summary"]["scenes"] != 963
                or run["read_scope"]["dev_pass_bytes"] != 26639253112
                or run["read_scope"]["dev_pass_files"] != 7950):
            raise ValueError("Fixed model/data scope changed")
        prep = Path(run["private_preparation"]["path"])
        if sha(prep) != model["preparation_sha256"]:
            raise ValueError("Frozen source/preparation metadata changed")
        manifest = v["provider_manifests"][run["code_root"]]
        if digest(manifest) != model["provider_manifest_sha256"]:
            raise ValueError("Inherited provider code manifest changed")
        validate_provider_files(run["code_root"], manifest)
    return p, v, a, runs


def validate_provider_files(root, manifest):
    """Check small provider code/config files, never scientific payloads."""
    root = Path(root).resolve()
    files = list((root / "src").rglob("*.py"))
    files.extend(p for p in (root / "config").rglob("*")
                 if p.is_file() and p.suffix in (".json", ".yaml", ".yml", ".csv"))
    current = {p.relative_to(root).as_posix(): sha(p) for p in sorted(files)}
    if current != manifest:
        raise ValueError("Inherited provider source/config changed; no model load permitted")


def validate_runtime_files(proposal, private):
    """Pin the original venv's native base, not its Windows redirector."""
    identity = proposal.get("runtime")
    if not identity or identity.get("direct_native_base_required") is not True:
        raise PermissionError("An explicitly bound native-base runtime is required")
    native, cfg = Path(private["runtime_python"]).resolve(), Path(private["inherited_venv_config"]).resolve()
    homes = [line.split("=", 1)[1].strip() for line in cfg.read_text(encoding="utf-8-sig").splitlines()
             if line.split("=", 1)[0].strip() == "home" and "=" in line]
    if (len(homes) != 1 or (Path(homes[0]) / "python.exe").resolve() != native
            or sha(native) != identity["executable_sha256"]
            or sha(cfg) != identity["inherited_venv_config_sha256"]):
        raise PermissionError("The inherited native interpreter/config binding differs")


def validate_running_runtime(proposal, private):
    validate_runtime_files(proposal, private)
    identity = proposal["runtime"]
    actual = dict(python_version=".".join(map(str, sys.version_info[:3])),
                  cache_tag=sys.implementation.cache_tag, implementation=sys.implementation.name)
    if (Path(sys.executable).resolve() != Path(private["runtime_python"]).resolve()
            or any(actual[k] != identity[k] for k in actual)):
        raise PermissionError("Controller/worker must use the exact bound native runtime")


class DualDeadline:
    def __init__(self, seconds, *, absolute_wall=None, monotonic=time.monotonic, wall=time.time):
        self.monotonic, self.wall = monotonic, wall
        self.mono_end = monotonic() + seconds
        self.wall_end = min(wall() + seconds, absolute_wall) if absolute_wall is not None else wall() + seconds

    def remaining(self):
        remaining = min(self.mono_end - self.monotonic(), self.wall_end - self.wall())
        if remaining <= 0:
            raise TimeoutError("Earlier wall/monotonic deadline reached; no retry")
        return remaining


class OutputLimit:
    def __init__(self, root, maximum, deadline):
        self.root, self.maximum, self.deadline = Path(root).resolve(), maximum, deadline

    def __call__(self, reserve=0):
        self.deadline.remaining()
        size = 0
        for path in self.root.rglob("*"):
            if path.is_symlink() or not path.resolve().is_relative_to(self.root):
                raise PermissionError("Output must not link outside its new namespace")
            if path.is_file():
                size += path.stat().st_size
        if size + reserve > self.maximum:
            raise MemoryError("New-output storage cap reached; preserve partial outputs")
        return size


class ScientificReadGuard:
    """Archive-length reservations before allowed scientific opens.

    The historical SourceMeter independently records actual delivered weather
    bytes and SHA. Torch/zip native internal reads are not claimed as measured
    disk-sector IO. Frozen metadata has a separate conservative archive cap.
    """
    RAW = (".nc", ".hgt", ".hgt.zip", ".h5", ".hdf5", ".pt", ".pth", ".ckpt", ".npz")

    def __init__(self, files, output, journal, *, metadata_cap, metadata_opens, metadata_roots, check):
        self.files = {os.path.normcase(str(Path(k).resolve())): v for k, v in files.items()}
        if len(self.files) != len(files):
            raise ValueError("Scientific manifest has multiple aliases of the same resolved file")
        self.output = Path(output).resolve()
        self.journal = Path(journal)
        self.metadata_cap, self.metadata_opens = metadata_cap, metadata_opens
        self.metadata_roots = tuple(Path(p).resolve() for p in metadata_roots)
        self.check = check
        self.counts, self.reserved = {}, {}
        self.meta_bytes = self.meta_count = 0
        self.active = False

    def _event(self, event, args):
        if not self.active or event not in ("open", "sqlite3.connect"):
            return
        if not args or not isinstance(args[0], (str, bytes, os.PathLike)):
            return
        value = os.fsdecode(args[0])
        if value == ":memory:" or value.startswith("file:"):
            # Read-only metadata SQLite uses a file URI; count its archive once
            # on connection below after stripping the URI query.
            if event == "open" or value == ":memory:":
                return
            from urllib.parse import unquote, urlsplit
            value = unquote(urlsplit(value).path)
            if os.name == "nt" and value.startswith("/"):
                value = value[1:]
        path = Path(value).resolve()
        if path.is_relative_to(self.output):
            return
        key = os.path.normcase(os.path.abspath(path))
        if key in self.files:
            self.check()
            entry = self.files[key]
            if event != "open":
                raise PermissionError("Scientific payload cannot be opened as an unmetered database")
            flags = args[2]
            if flags & (os.O_WRONLY | os.O_RDWR | os.O_APPEND | os.O_CREAT):
                raise PermissionError("Scientific inputs are read-only")
            count = self.counts.get(key, 0) + 1
            if count > entry["opens"] or path.stat().st_size != entry["bytes"]:
                raise PermissionError("Scientific source identity or one-pass/open allowance exceeded")
            self.counts[key] = count
            category = entry["category"]
            self.reserved[category] = self.reserved.get(category, 0) + entry["bytes"]
            with self.journal.open("a", encoding="utf-8") as stream:
                stream.write(json.dumps(dict(source_id=entry["source_id"], category=category,
                                             state="INTENT_BEFORE_OPEN", bytes=entry["bytes"], occurrence=count)) + "\n")
            return
        if str(path).lower().endswith(self.RAW):
            raise PermissionError("Unlisted scientific payload, including any 2025 data, is forbidden")
        if any(path.is_relative_to(root) for root in self.metadata_roots) and path.suffix.lower() in (".json", ".yaml", ".yml", ".csv", ".sqlite"):
            self.check()
            if event == "open" and args[2] & (os.O_WRONLY | os.O_RDWR | os.O_APPEND | os.O_CREAT):
                raise PermissionError("Frozen metadata cannot be modified")
            size = path.stat().st_size
            if self.meta_count + 1 > self.metadata_opens or self.meta_bytes + size > self.metadata_cap:
                raise PermissionError("Frozen metadata reservation cap exceeded")
            self.meta_count += 1; self.meta_bytes += size

    def install(self):
        sys.addaudithook(self._event)
        self.active = True

    def close(self):
        self.active = False
        return dict(payload_reserved_bytes=self.reserved,
                    payload_open_instances=sum(self.counts.values()),
                    metadata_archive_reserved_bytes=self.meta_bytes, metadata_open_instances=self.meta_count)


def resources(folder, budget):
    monitor = module(ROOT / "tools/core_stage4/monitor/server.py", "extreme_diagnostic_resource_monitor")
    status = monitor.resources(folder)
    gpu, memory = status.get("gpu") or {}, status.get("memory") or {}
    if (status["disk_free"] < budget["minimum_free_bytes"]
            or memory.get("available", 0) < budget["minimum_host_available_bytes"]
            or gpu.get("total_mib", 0) - gpu.get("used_mib", 0) < budget["minimum_gpu_free_mib"]):
        raise RuntimeError("Disk/host/GPU admission failed; do not change limits or retry")
    return status


def worker(proposal_path, private_path, approval_path, task):
    # First gate is before torch import, model loading or any science payload.
    p, v, a, runs = validate_only(proposal_path, private_path, approval_path, worker_task=task)
    validate_running_runtime(p, v)
    host = module(ROOT / "tools/research_readiness/start_independent_process.py", "extreme_host_worker")
    host.require_independent(host.host_identity())
    package = Path(v["output_root"])
    binding = read(package / "binding.json")
    seconds = p["budget"]["label_seconds"] if task == "TRAIN_LABELS" else p["budget"]["per_model_seconds"]
    clock = DualDeadline(seconds, absolute_wall=binding["absolute_wall_deadline"])
    check = OutputLimit(package, p["budget"]["output_storage_cap_bytes"], clock)
    output = package / task
    output.mkdir(exist_ok=False)
    run = runs["B4_s2029" if task == "TRAIN_LABELS" else task]
    prepared = read(run["private_preparation"]["path"])["prepared"]
    if task == "TRAIN_LABELS":
        scientific = {path: dict(info, category="labels", source_id=f"LABEL_{i:03d}", opens=1)
                      for i, (path, info) in enumerate(v["label_files"].items())}
    else:
        scientific = {path: dict(info, category="weather", source_id=f"WEATHER_{i:04d}", opens=1)
                      for i, (path, info) in enumerate(prepared["roles"]["Development"]["files"].items())}
        scientific[run["checkpoint_path"]] = dict(bytes=run["checkpoint_bytes"], opens=2, category="checkpoint", source_id="FIXED_E9")
        if run["model"] in ("B7", "B8"):
            scientific[v["static_source"]] = dict(bytes=312828, opens=1, category="static", source_id="STATIC_B6")
    metadata_roots = [Path(run["code_root"]) / "config", Path(run["code_root"]) / "docs",
                      Path(run["private_preparation"]["path"]).parent,
                      Path(prepared["private_inputs"]["stage3_run"]),
                      Path(prepared["private_inputs"]["request"]).parent,
                      Path(v["static_source"]).parent, Path(v["registry"]).parent]
    guard = ScientificReadGuard(scientific, package, output / "source_reservations.jsonl",
                metadata_cap=p["budget"]["worker_metadata_archive_cap_bytes"],
                metadata_opens=p["budget"]["worker_metadata_open_cap"], metadata_roots=metadata_roots, check=clock.remaining)
    guard.install()
    try:
        provider = module(ROOT / "tools/research_readiness/extreme_diagnostic_provider.py", "extreme_joint_provider")
        if task == "TRAIN_LABELS":
            result = provider.run_train_labels(run, v["label_files"], output, check)
            expected = dict(labels=180049094)
        else:
            engine = module(v["engine"], "pinned_extreme_inference_provider")
            engine.REGISTRY_PATH = v["registry"]
            result = provider.run_model(engine, run, output, package, check, v["static_source"], p["static_sha256"], sha)
            expected = dict(weather=26639253112, checkpoint=2 * run["checkpoint_bytes"])
            if run["model"] in ("B7", "B8"):
                expected["static"] = 312828
        check()
        accounting = guard.close()
        if accounting["payload_reserved_bytes"] != expected:
            raise RuntimeError("Exact scientific payload open reservation differs; no retry")
        write(output / "task_complete.json", dict(task=task, status="COMPLETE", accounting=accounting,
              verified_sha256=sha(output / "verified.json"), optimizer_updates=0, final_2025="FROZEN_NO_ACCESS"))
    finally:
        guard.active = False


def finalize(package, proposal):
    """Only new sealed outputs; no original data/weights or model access."""
    import statistics
    reference = read(package / "TRAIN_LABELS/verified.json")
    results = {rid: read(package / rid / "joint/joint_summary.json") for rid in ORDER[1:]}
    comparisons = {}
    for left, right in (("B8", "B7"), ("B7", "B4"), ("B8", "B4")):
        members = {}
        for seed in (2029, 2030, 2031):
            a, b = results[f"{left}_s{seed}"], results[f"{right}_s{seed}"]
            groups = {}
            for name in set(a["groups"]) | set(b["groups"]):
                ga, gb = a["groups"].get(name), b["groups"].get(name)
                if ga is None or gb is None:
                    groups[name] = dict(status="NOT_AVAILABLE"); continue
                if (ga["group_mask_sha256"], ga["n"], ga["n_rain"]) != (gb["group_mask_sha256"], gb["n"], gb["n_rain"]):
                    raise ValueError("Group populations differ; do not compare marginal counts")
                groups[name] = {key: None if ga[key] is None or gb[key] is None else ga[key] - gb[key]
                                for key in ("occurrence_brier", "conditional_pinball", "q32_coverage")}
                groups[name]["q32_note"] = "Truth-intensity-conditioned coverage is descriptive, not a per-stratum nominal calibration test"
            bounds = {}
            for threshold in ("5.0", "10.0", "20.0", "50.0"):
                pa, pb = a["probability"][threshold], b["probability"][threshold]
                if (pa["n"], pa["positive"]) != (pb["n"], pb["positive"]):
                    raise ValueError("Exceedance comparison populations differ")
                values = {}
                for metric in ("brier_bounds", "auroc_bounds"):
                    ia, ib = pa[metric], pb[metric]
                    values[metric + "_difference"] = None if ia is None or ib is None else [ia[0] - ib[1], ia[1] - ib[0]]
                climatology = reference["climatology"][threshold]
                prevalence = pa["positive"] / pa["n"]
                values["train_climatology_probability"] = climatology
                values["train_climatology_dev_brier"] = prevalence * (1 - climatology) ** 2 + (1 - prevalence) * climatology ** 2
                values["AP"] = "NOT_POINT_IDENTIFIED"
                bounds[threshold] = values
            point_errors = {}
            for name in set(a["point_errors"]) | set(b["point_errors"]):
                ea, eb = a["point_errors"].get(name), b["point_errors"].get(name)
                if ea is None or eb is None or ea["n"] != eb["n"]:
                    raise ValueError("Point-error populations differ")
                point_errors[name] = {key: None if ea[key] is None or eb[key] is None else ea[key] - eb[key]
                                      for key in ("MAE", "RMSE", "Bias")}
            contingency = {}
            for name, ca in a["point_contingency"].items():
                cb = b["point_contingency"][name]
                if sum(ca[k] for k in ("TP", "FP", "FN", "TN")) != sum(cb[k] for k in ("TP", "FP", "FN", "TN")):
                    raise ValueError("Point-detection populations differ")
                contingency[name] = {key: None if ca[key] is None or cb[key] is None else ca[key] - cb[key]
                                     for key in ("TP", "FP", "FN", "TN", "CSI", "POD", "FAR", "Precision")}
            members[str(seed)] = dict(groups=groups, probability=bounds,
                point_error_differences=point_errors, point_detection_differences=contingency)
        group_means = {}
        for name in members['2029']['groups']:
            groups = [members[str(seed)]['groups'][name] for seed in (2029, 2030, 2031)]
            group_means[name] = {}
            for metric in ('occurrence_brier', 'conditional_pinball', 'q32_coverage'):
                values = [g.get(metric) for g in groups]
                group_means[name][metric] = (dict(status='NOT_AVAILABLE_FOR_ALL_THREE_SEEDS') if any(v is None for v in values)
                    else dict(mean=statistics.mean(values), sample_sd=statistics.stdev(values), n_seeds=3))
        interval_means = {}
        for threshold in ('5.0', '10.0', '20.0', '50.0'):
            interval_means[threshold] = {}
            for metric in ('brier_bounds_difference', 'auroc_bounds_difference'):
                values = [members[str(seed)]['probability'][threshold][metric] for seed in (2029, 2030, 2031)]
                interval_means[threshold][metric] = (None if any(v is None for v in values)
                    else [statistics.mean(v[i] for v in values) for i in (0, 1)])
        comparisons[left + "_MINUS_" + right] = dict(by_seed=members,
            group_delta_mean_and_sample_sd=group_means, mean_identification_intervals=interval_means,
            interval_mean_note='Identification intervals for the mean paired difference, not confidence intervals')
    accounting = [read(package / task / "task_complete.json")["accounting"] for task in ORDER]
    reserved = sum(sum(row["payload_reserved_bytes"].values()) for row in accounting)
    meta = sum(row["metadata_archive_reserved_bytes"] for row in accounting)
    opens = sum(row["metadata_open_instances"] for row in accounting)
    if (reserved != proposal["budget"]["payload_archive_reference_bytes"]
            or meta > proposal["budget"]["metadata_archive_cap_bytes"]
            or opens > proposal["budget"]["metadata_open_cap"]):
        raise RuntimeError("Package source/metadata cap mismatch")
    write(package / "diagnostic_comparisons.json", dict(status="COMPLETE_DIAGNOSTIC_PENDING_RESEARCHER_SCIENTIFIC_REVIEW",
          comparisons=comparisons, aggregate_policy="Per-seed intervals are primary; no sign/significance invented from unresolved bounds",
          independent_events="NOT_IDENTIFIED", physics_causality="NOT_VERIFIED", final_2025="FROZEN_NO_ACCESS"))
    return dict(payload_archive_reference_bytes=reserved, metadata_archive_reserved_bytes=meta,
                metadata_open_instances=opens, optimizer_updates=0, new_model_passes=9,
                independent_events="NOT_IDENTIFIED", scientific_acceptance="PENDING_RESEARCHER_REVIEW")


def execute(proposal_path, private_path, approval_path):
    p, v, a, runs = validate_only(proposal_path, private_path, approval_path)
    validate_running_runtime(p, v)
    host = module(ROOT / "tools/research_readiness/start_independent_process.py", "extreme_host_controller")
    host.require_independent(host.host_identity())
    output = Path(v["output_root"])
    admission = resources(output.parent, p["budget"])
    clock = DualDeadline(p["budget"]["maximum_seconds"])
    output.mkdir(exist_ok=False)
    write(output / "binding.json", dict(controller_pid=os.getpid(), approval_sha256=sha(approval_path),
          proposal_sha256=p["proposal_sha256"], code_commit=p["execution_code_commit"],
          absolute_wall_deadline=clock.wall_end, admission=admission, retries=0, final_2025="FROZEN_NO_ACCESS"))
    child = None
    try:
        for task in ORDER:
            clock.remaining()
            resources(output, p["budget"])
            write(output / (task + "_claim.json"), dict(controller_pid=os.getpid(), proposal_sha256=p["proposal_sha256"], task=task))
            run = runs["B4_s2029" if task == "TRAIN_LABELS" else task]
            env = dict(os.environ, PYTHONPATH=str(Path(run["code_root"]) / "src") + os.pathsep + v["torch_site"],
                       PYTHONHASHSEED=str(run["seed"]), CUBLAS_WORKSPACE_CONFIG=":4096:8",
                       PYTHONUTF8="1", PYTHONDONTWRITEBYTECODE="1", OMP_NUM_THREADS="1", MKL_NUM_THREADS="1")
            command = [sys.executable, "-B", str(Path(__file__).resolve()), "worker", "--proposal", str(Path(proposal_path).resolve()),
                       "--private-preparation", str(Path(private_path).resolve()), "--researcher-approval", str(Path(approval_path).resolve()), "--task", task]
            seconds = p["budget"]["label_seconds"] if task == "TRAIN_LABELS" else p["budget"]["per_model_seconds"]
            task_clock = DualDeadline(seconds, absolute_wall=clock.wall_end)
            with (output / (task + "_console.log")).open("xb") as log:
                child = subprocess.Popen(command, cwd=ROOT, env=env, stdout=log, stderr=subprocess.STDOUT,
                                         creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
                while child.poll() is None:
                    clock.remaining(); task_clock.remaining()
                    try: child.wait(timeout=min(1., clock.remaining(), task_clock.remaining()))
                    except subprocess.TimeoutExpired: pass
            if child.returncode or read(output / task / "task_complete.json")["status"] != "COMPLETE":
                raise RuntimeError("Diagnostic task failed; all later tasks blocked and no automatic retry")
        clock.remaining()
        totals = finalize(output, p)
        OutputLimit(output, p["budget"]["output_storage_cap_bytes"], clock)()
        write(output / "completion.json", dict(status="COMPLETE_BOUNDED_EXTREME_DIAGNOSTIC", totals=totals,
              proposal_sha256=p["proposal_sha256"], automatic_retry=False, final_2025="FROZEN_NO_ACCESS"))
    except BaseException as error:
        if child is not None and child.poll() is None:
            child.kill(); child.wait()
        write(output / "failure.json", dict(status="STOP_PRESERVE_ALL_NO_RETRY", error_type=type(error).__name__,
              details=str(error), uncertain_IO="PRESERVED_IN_RESERVATIONS_AND_ORIGINAL_SOURCE_LEDGERS",
              optimizer_updates=0, final_2025="FROZEN_NO_ACCESS"))
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("validate", "execute", "worker"))
    parser.add_argument("--proposal", type=Path, required=True)
    parser.add_argument("--private-preparation", type=Path, required=True)
    parser.add_argument("--researcher-approval", type=Path, required=True)
    parser.add_argument("--task")
    args = parser.parse_args()
    if args.mode == "validate":
        validate_only(args.proposal, args.private_preparation, args.researcher_approval)
        print("EXACT_APPROVAL_VALID_NO_PAYLOAD_ACCESS")
    elif args.mode == "worker":
        worker(args.proposal, args.private_preparation, args.researcher_approval, args.task)
    else:
        execute(args.proposal, args.private_preparation, args.researcher_approval)


if __name__ == "__main__":
    main()
