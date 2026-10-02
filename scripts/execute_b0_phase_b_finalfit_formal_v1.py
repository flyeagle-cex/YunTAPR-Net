"""Researcher-authorized FinalFit execution telemetry; baseline numerical runner unchanged.

This adapter delegates every numerical update and epoch to the SHA-pinned runner.
It adds source-open guards and metadata only; it never selects/recomputes a protocol.
"""
from __future__ import annotations
import argparse
import csv
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import subprocess
import sys
import time
import traceback

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT/"src"), str(ROOT/"scripts")]
import torch
import yaml
from yuntapr.contracts.loader import sha256
from yuntapr.training import formal_phase_b as b
import train_b0_phase_b_finalfit_v1 as runner

BASELINE = "4de37ac087183bddf3b9f8c7d548a0f976a50e91"
AUTH = ROOT/"config/training/b0_phase_b_finalfit_formal_authorization_v1.yaml"
AUTH_DOC = ROOT/"docs/formal_training_authorization/B0_PHASE_B_FINALFIT_FORMAL_AUTHORIZATION_v1.md"
ATTACHMENT = Path(r"C:\Users\chenerxiao\.codex\attachments\474af59f-e09c-41aa-8128-e2f697c12272\已粘贴的文本.txt")
PREPARATION = ROOT/"docs/phase_b_finalfit_preparation/runs/run_20261002T014649_144967Z"
PREFLIGHT = ROOT/"docs/phase_b_formal_runner/runs/run_20261002T031500_884240Z"
REVIEW = ROOT/"docs/scientific_review/b0_phase_a/runs/run_20261002T005448_798068Z"
ACCEPTANCE = ROOT/"config/decisions/b0_phase_a_acceptance_v1.yaml"
EXECUTION = ROOT/"docs/formal_training/b0_phase_b_finalfit/executions"
PRIVATE = Path(r"F:\pytorch\Research\outputs\formal_execution\b0_phase_b_finalfit")


def read(path): return json.loads(Path(path).read_text(encoding="utf-8"))
def save(path, value): runner.exclusive_json(path, value)


def baseline_inventory():
    entries = subprocess.check_output(["git", "ls-tree", "-r", "-z", BASELINE], cwd=ROOT).decode().rstrip("\0").split("\0")
    pins = {}
    for entry in entries:
        meta, name = entry.split("\t", 1)
        data = (ROOT/name).read_bytes()
        digest = hashlib.sha1(b"blob "+str(len(data)).encode()+b"\0"+data).hexdigest()
        if digest != meta.split()[2]: raise ValueError("Baseline file changed: "+name)
        pins[name] = hashlib.sha256(data).hexdigest()
    return pins


def verify_reference(reference):
    path = Path(reference["path"])
    if not path.is_absolute(): path = ROOT/path
    if sha256(path) != reference["sha256"]: raise ValueError("Authorization identity mismatch: "+str(path))


def initialize_authorization():
    if subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip() != BASELINE:
        raise ValueError("Wrong authorized baseline")
    baseline_inventory()
    contract = b.RunnerContract.load()
    if not b.HROOT.is_dir(): raise FileNotFoundError("Original H root unavailable; no fallback")
    for directory in (PREPARATION, PREFLIGHT, REVIEW):
        for name, ref in read(directory/"artifact_sha256.json").items():
            if sha256(directory/name) != ref["sha256"]: raise ValueError("Prior evidence hash changed: "+name)
    ready = read(PREFLIGHT/"final_status.json")
    if (not ready["PHASE_B_FORMAL_RUNNER_READY"] or ready["TOTAL_REGRESSION_TESTS_EXECUTED"] != 242
            or not ready["SINGLETON_ACTUAL_TAIL_LR_SMOKE_PASS"]):
        raise ValueError("Runner preflight closure incomplete")
    if contract.normalizer.mu != 270.5900486586461 or contract.normalizer.sigma != 20.368583874067266:
        raise ValueError("Approved normalization values changed")
    identities = {}
    for name, path in {"phase_a_acceptance": ACCEPTANCE, "scientific_review": REVIEW/"review_manifest.json",
            "scientific_review_final_status": REVIEW/"final_status.json",
            "phase_b_preparation": PREPARATION/"preparation_manifest.json",
            "phase_b_preparation_final_status": PREPARATION/"final_status.json",
            "phase_b_runner_preflight": PREFLIGHT/"runner_manifest.json",
            "phase_b_runner_preflight_final_status": PREFLIGHT/"final_status.json",
            "formal_phase_b_module": ROOT/"src/yuntapr/training/formal_phase_b.py",
            "formal_entrypoint": ROOT/"scripts/train_b0_phase_b_finalfit_v1.py",
            "telemetry_adapter": Path(__file__), "runner_config": ROOT/b.CONFIG}.items():
        identities[name] = {"path": path.relative_to(ROOT).as_posix(), "sha256": sha256(path)}
    document = f"""# B0 Phase-B FinalFit formal authorization v1

The researcher explicitly authorizes B0_PHASE_B_FINALFIT_ONLY in the attached
AUTHORIZE AND EXECUTE task. Baseline: `{BASELINE}`. Authority attachment SHA256:
`{sha256(ATTACHMENT)}`. Authorization is run-level and does not change historical
preparation, runner configuration or their PHASE_B_AUTHORIZED=false fields.

PHASE_B_AUTHORIZED=true. Fresh seed 2026 only; no Phase-A model, optimizer or
scheduler state. FinalFit consists of 23,447 frozen identities (2023:11,720;
2024:11,727; 2025:0), each exactly once per epoch. Physical batch2, accumulation1,
drop_last=false, singleton allowed without drop/duplication. Fixed eleven epochs,
11,724 updates per epoch, total128,964. Stateless LR preserves W=11,724/U=586,200,
base LR1e-4 and min LR1e-6. No cosine compression or scientific parameter change.

Normalization SHA256: `{b.NORMALIZATION_SHA}`; mean270.5900486586461K,
std20.368583874067266K, no refit. Manifest SHA256: `{b.MANIFEST_SHA}`.
All approved architecture/loss/AdamW/precision/clipping rules inherit the frozen
protocol. Every original source SHA is verified before model initialization and
again during staged runtime reads. Source/QC/causality/numerical failure stops execution.

No early stopping, BEST, validation selection, epoch reselection, 2025 read,
threshold calibration, hyperparameter tuning or B1-B8 execution is authorized.
Only completed epoch boundaries produce checkpoints. LAST and epoch11 FINAL are
registered; payloads remain at `{b.CHECKPOINT_ROOT}` and never enter Git.
Resume is only from verified completed LAST after provenance-before-state application.

The exact current baseline runner/module/config SHA values below are unchanged.
A separately SHA-pinned adapter adds source-open auditing and requested epoch
telemetry while delegating numerical updates/epochs to the baseline functions.

```json
{json.dumps(identities, indent=2)}
```

After eleven epochs: verify FINAL read-only; rerun all242 current tests and legal
new tests; verify FINAL SHA unchanged; publish text evidence; STOP. Final Test2025,
B1-B8 and subsequent stages remain unauthorized.
"""
    with AUTH_DOC.open("x", encoding="utf-8", newline="\n") as stream: stream.write(document)
    value = {"version": "v1", "AUTHORIZED_BY": "RESEARCHER", "AUTHORIZED_SCOPE": "B0_PHASE_B_FINALFIT_ONLY",
        "PHASE_B_AUTHORIZED": True, "PHASE_B_FORMAL_TRAINING_STARTED": False,
        "baseline_commit": BASELINE, "PHASE_B_MODEL_INITIALIZATION": b.INITIALIZATION,
        "PRIMARY_SEED": 2026, "FINALFIT_EPOCHS": 11, "FINALFIT_SCENES": 23447,
        "population_counts": {2023:11720, 2024:11727, 2025:0}, "PHYSICAL_BATCH": 2,
        "gradient_accumulation": 1, "DROP_LAST": False, "FINALFIT_TAIL_BATCH_POLICY": b.TAIL_POLICY,
        "STEPS_PER_EPOCH": 11724, "TOTAL_UPDATES": 128964, "W": 11724, "U": 586200,
        "base_lr": 1e-4, "min_lr": 1e-6, "normalization_mean_K": contract.normalizer.mu,
        "normalization_std_K": contract.normalizer.sigma, "NORMALIZATION_SHA256": b.NORMALIZATION_SHA,
        "manifest_sha256": b.MANIFEST_SHA, "runner_config_sha256": contract.config_sha256,
        "checkpoint_root": str(b.CHECKPOINT_ROOT), "implementation_sha256": b.implementation_hashes(),
        "identity": identities, "authorization_document": {"path": AUTH_DOC.relative_to(ROOT).as_posix(), "sha256": sha256(AUTH_DOC)},
        "authority_attachment_sha256": sha256(ATTACHMENT), "2025_access": False,
        "B1_TO_B8_AUTHORIZED": False, "FINAL_TEST_2025_AUTHORIZED": False,
        "early_stopping": False, "BEST_selection": False, "epoch_reselection": False,
        "created_utc": runner.now()}
    with AUTH.open("x", encoding="utf-8", newline="\n") as stream: yaml.safe_dump(value, stream, sort_keys=False)
    print("AUTHORIZATION_CREATED "+sha256(AUTH), flush=True)


class EpochTelemetry:
    def __init__(self, epoch):
        self.epoch = epoch
        self.updates = self.samples = self.valid = self.rainy = self.clipped = 0
        self.norm_sum = 0.
        self.norm_min, self.norm_max = math.inf, -math.inf
        self.first_lr = self.last_lr = None
        self.singleton = None

    def record(self, result, sample_ids):
        expected_u = (self.epoch-1)*b.STEPS+self.updates+1
        size = len(sample_ids)
        expected_size = 1 if self.updates == b.STEPS-1 else 2
        if (result["scope"] != b.SCOPE or result["scheduler_u"] != expected_u
                or size != expected_size or result["batch_size"] != size
                or result["valid_denominator"] != size*3430 or result["LR"] != b.finalfit_lr(expected_u)):
            raise ValueError("Formal telemetry counter/tail/LR mismatch")
        norm = result["pre_clip_norm"]
        if not math.isfinite(norm): raise ValueError("Nonfinite telemetry norm")
        self.updates += 1; self.samples += size; self.valid += result["valid_denominator"]
        self.rainy += result["rainy_count"]
        self.clipped += int(5./(norm+1e-6) < 1.)
        self.norm_sum += norm; self.norm_min = min(self.norm_min, norm); self.norm_max = max(self.norm_max, norm)
        if self.first_lr is None: self.first_lr = result["LR"]
        self.last_lr = result["LR"]
        if size == 1:
            self.singleton = {"sample_id": sample_ids[0], "actual_denominator": result["valid_denominator"],
                "LR": result["LR"], "global_update": expected_u}

    def complete(self, original, coverage, gpu_allocated, gpu_reserved):
        receipt = coverage.complete()
        if (self.samples != 23447 or self.updates != 11724 or self.valid != 80423210
                or self.valid != original["D_valid"] or self.rainy != original["N_rain"]
                or receipt["updates"] != self.updates or self.singleton is None):
            raise ValueError("Incomplete formal telemetry epoch")
        return {"epoch": self.epoch, "samples": self.samples, "updates": self.updates,
            "global_update_start": (self.epoch-1)*b.STEPS+1, "global_update_end": self.epoch*b.STEPS,
            "global_train_occurrence_loss": original["S_occ"]/self.valid,
            "global_train_quantile_loss": original["S_qr"]/self.valid,
            "global_train_core_loss": (original["S_occ"]+original["S_qr"])/self.valid,
            "N_valid": self.valid, "N_rain": self.rainy, "LR_start": self.first_lr, "LR_end": self.last_lr,
            "gradient_norm_min": self.norm_min, "gradient_norm_max": self.norm_max,
            "gradient_norm_mean": self.norm_sum/self.updates, "clip_count": self.clipped,
            "clip_fraction": self.clipped/self.updates, "GPU_peak_allocated_bytes": gpu_allocated,
            "GPU_peak_reserved_bytes": gpu_reserved, "IO_copy_seconds": original["IO"]["copy_seconds"],
            "IO_read_seconds": original["IO"]["read_seconds"], "wall_seconds": original["wall_seconds"],
            "singleton_sample_id": self.singleton["sample_id"], "singleton_actual_denominator": self.singleton["actual_denominator"],
            "singleton_LR": self.singleton["LR"], "identities_exactly_once": True,
            "aggregation": "GLOBAL_RAW_NUMERATORS_DIVIDED_BY_TOTAL_ACTUAL_VALID_PIXELS_NOT_BATCH_AVERAGE"}


def install_source_guard():
    roots = [b.HROOT.resolve(), b.IROOT.resolve()]
    phase_a = Path(r"F:\pytorch\Research\outputs\formal_training\b0_phase_a").resolve()
    def audit(event, args):
        if event != "open" or not isinstance(args[0], (str, bytes, os.PathLike)): return
        path = Path(os.fsdecode(args[0])).resolve()
        mode = args[1] or ""; flags = args[2] if len(args)>2 else 0
        writing = any(c in str(mode) for c in "wax+") or bool(flags & (os.O_WRONLY|os.O_RDWR|os.O_CREAT|os.O_TRUNC))
        if path.is_relative_to(phase_a): raise PermissionError("Phase-A checkpoint/state access prohibited in FinalFit")
        for root in roots:
            if path.is_relative_to(root):
                parts = path.relative_to(root).parts
                if writing or not parts or parts[0][:4] not in ("2023", "2024"):
                    raise PermissionError("Read-only authorized 2023/2024 source guard: "+str(path))
    sys.addaudithook(audit)


def guarded_worker_init(worker_id):
    install_source_guard()
    b.worker_init(worker_id)


def csv_history(public):
    entries = [read(p) for p in sorted(public.glob("epoch_*_summary.json"))]
    if not entries: return
    destination = public/"training_history.csv"
    temporary = destination.with_name(destination.name+".tmp_metadata")
    with temporary.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(entries[0]), lineterminator="\n")
        writer.writeheader(); writer.writerows(entries); stream.flush(); os.fsync(stream.fileno())
    os.replace(temporary, destination)


def execute(resume_run_id=None):
    contract = b.RunnerContract.load()
    auth_value = yaml.safe_load(AUTH.read_text(encoding="utf-8"))
    for ref in [*auth_value["identity"].values(), auth_value["authorization_document"]]: verify_reference(ref)
    b.PhaseBAuthorization.load(AUTH, sha256(AUTH), contract)
    pins = baseline_inventory()
    execution_id = "execution_"+datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S_%fZ")
    out, private = EXECUTION/execution_id, PRIVATE/execution_id
    out.mkdir(parents=True, exist_ok=False); private.mkdir(parents=True, exist_ok=False)
    save(out/"execution_manifest.json", {"baseline_commit": BASELINE, "authorization_sha256": sha256(AUTH),
        "telemetry_adapter_sha256": sha256(Path(__file__)), "baseline_files_sha256": pins,
        "private_directory": str(private), "PHASE_B_AUTHORIZED": True, "created_utc": runner.now()})
    os.environ.update(TEMP=str(private), TMP=str(private), TORCHINDUCTOR_CACHE_DIR=str(private/"torchinductor"))
    import tempfile
    tempfile.tempdir = str(private)
    install_source_guard()
    original_hash = b.sha256
    source_counts = {"B13": 0, "IMERG": 0}; source_started = time.perf_counter()
    preflight_active = {"enabled": True}
    def measured_hash(path):
        value = original_hash(path)
        p = Path(path).resolve()
        kind = "B13" if p.is_relative_to(b.HROOT.resolve()) else "IMERG" if p.is_relative_to(b.IROOT.resolve()) else None
        if preflight_active["enabled"] and kind:
            source_counts[kind] += 1
            if source_counts["B13"] % 500 == 0 or source_counts["B13"] == 23447:
                item = {"state": "SOURCE_SHA_PREFLIGHT", "verified": dict(source_counts),
                    "elapsed_seconds": time.perf_counter()-source_started, "utc": runner.now()}
                b.atomic_json(out/"execution_progress.json", item); print("SOURCE_PREFLIGHT "+json.dumps(item), flush=True)
        return value
    b.sha256 = measured_hash
    original_source = runner.source_identity_preflight
    def checked_source(c):
        result = original_source(c)
        preflight_active["enabled"] = False
        save(out/"source_identity_preflight.json", {**result, "wall_seconds": time.perf_counter()-source_started})
        return result
    runner.source_identity_preflight = checked_source
    runner.worker_init = guarded_worker_init
    original_update, original_epoch = runner.execute_update, runner.train_epoch
    current = {"telemetry": None, "public": None, "formal_updates_this_execution": 0, "optimizer": None}
    def tracked_update(model, optimizer, batch, update, authorization=None, *, engineering=False):
        if engineering: raise ValueError("This formally authorized execution is not an engineering smoke")
        current["optimizer"] = optimizer
        result = original_update(model, optimizer, batch, update, authorization)
        current["formal_updates_this_execution"] += 1
        current["telemetry"].record(result, [s.sample_id for s in batch.formal_samples])
        return result
    def tracked_epoch(model, optimizer, dataset, authorization, epoch, public, local):
        current["public"] = public; current["telemetry"] = EpochTelemetry(epoch)
        if not (public/"formal_run_manifest.json").exists():
            original = read(public/"run_manifest.json")
            save(public/"formal_run_manifest.json", {**original, "baseline_commit": BASELINE,
                "initial_model_state_sha256": original["fresh_model_initial_state_sha256"],
                "execution_manifest": out.relative_to(ROOT).as_posix(), "authorization_path": AUTH.relative_to(ROOT).as_posix(),
                "telemetry_adapter_sha256": sha256(Path(__file__)), "scientific_parameters_changed": False,
                "2025_PIXELS_READ": 0, "B1_TO_B8_AUTHORIZED": False, "FINAL_TEST_2025_AUTHORIZED": False})
        b.atomic_json(out/"execution_progress.json", {"state": "FORMAL_TRAINING", "run_id": public.name,
            "epoch": epoch, "formal_run_directory": str(public), "utc": runner.now()})
        torch.cuda.reset_peak_memory_stats()
        coverage, metrics = original_epoch(model, optimizer, dataset, authorization, epoch, public, local)
        summary = current["telemetry"].complete(metrics, coverage,
            torch.cuda.max_memory_allocated(), torch.cuda.max_memory_reserved())
        save(public/f"epoch_{epoch:03d}_summary.json", summary)
        csv_history(public)
        metrics["formal_epoch_telemetry"] = summary
        print("EPOCH_COMPLETE "+json.dumps(summary), flush=True)
        return coverage, metrics
    runner.execute_update, runner.train_epoch = tracked_update, tracked_epoch
    args = argparse.Namespace(authorization=AUTH, authorization_sha256=sha256(AUTH), run_id=resume_run_id)
    try:
        runner.formal_run(args, resume=resume_run_id is not None)
        public = current["public"]
        if public is None and resume_run_id: public = runner.PUBLIC/resume_run_id
        status = read(public/"final_status.json")
        if status["completed_epoch"] != 11 or status["FORMAL_OPTIMIZER_STEPS"] != 128964:
            raise ValueError("Formal runner did not complete the frozen eleven-epoch budget")
        registry = read(public/"checkpoint_registry.json")
        expected = read(public/"run_manifest.json")["checkpoint_expected"]
        payload = b.load_verified_checkpoint(registry["FINAL"], expected)
        del payload
        save(public/"runtime_summary.json", {"PHASE_B_AUTHORIZED": True, "PHASE_B_FORMAL_TRAINING_STARTED": True,
            "training_runner_completed": True, "post_training_closure_pending": True,
            "TOTAL_COMPLETED_EPOCHS": 11, "FORMAL_OPTIMIZER_STEPS": 128964,
            "formal_updates_this_execution": current["formal_updates_this_execution"], "FINAL": registry["FINAL"],
            "FINAL_readable_sha_provenance_PASS": True, "2025_PIXELS_READ": 0, "B1_STARTED": False,
            "B1_TO_B8_AUTHORIZED": False, "FINAL_TEST_2025_AUTHORIZED": False,
            "FINAL_TEST_2025_EXECUTED": False, "finished_utc": runner.now()})
        save(out/"execution_result.json", {"state": "TRAINING_COMPLETED_POST_TESTS_PENDING",
            "formal_run_directory": str(public), "formal_updates_this_execution": current["formal_updates_this_execution"]})
        print("FORMAL_RUN_DIRECTORY "+str(public), flush=True)
    except Exception as error:
        actual_counter = max((int(float(s["step"])) for s in current["optimizer"].state.values()), default=0) if current["optimizer"] else 0
        save(out/"execution_failure.json", {"error": repr(error), "traceback": traceback.format_exc(),
            "formal_run_directory": str(current["public"]) if current["public"] else None,
            "formal_updates_this_execution": current["formal_updates_this_execution"],
            "actual_optimizer_global_step_counter_at_failure": actual_counter, "2025_PIXELS_READ": 0,
            "PHASE_B_AUTHORIZED": True, "STOP_required": True, "failed_utc": runner.now()})
        raise


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["authorize", "train", "resume"])
    parser.add_argument("--run-id")
    args = parser.parse_args()
    if args.action == "authorize":
        if args.run_id: raise SystemExit("Authorization does not accept a run-id")
        initialize_authorization()
    elif args.action == "resume":
        if not args.run_id: raise SystemExit("Epoch-boundary resume requires --run-id")
        execute(args.run_id)
    else:
        if args.run_id: raise SystemExit("Fresh training creates its own independent run")
        execute()
