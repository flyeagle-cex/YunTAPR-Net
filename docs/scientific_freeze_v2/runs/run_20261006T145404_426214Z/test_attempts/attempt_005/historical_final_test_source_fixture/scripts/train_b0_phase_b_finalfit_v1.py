"""B0 FinalFit entrypoint: ENGINEERING_ONLY preflight, or separately authorized fit/resume.

This release must not start formal training. No default authorization, checkpoint
initialization option, epoch override, hyperparameter override or validation loop exists.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import gc
import importlib.metadata
import json
import os
from pathlib import Path
import sys
import subprocess
import time
import weakref
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "src"), str(ROOT / "scripts")]
import torch
from torch.utils.data import DataLoader
from yuntapr.contracts.loader import sha256
from yuntapr.data.masks import read_frozen_yunnan_mask
from yuntapr.spatial.sp04_mapping import load_sp04
from yuntapr.training.formal_phase_b import (
    RunnerContract, PhaseBAuthorization, FinalFitDataset, EpochCoverage, CONFIG,
    CHECKPOINT_ROOT, STAGING, SCOPE, SCENES, STEPS, EPOCHS, UPDATES,
    fresh_model, prepare_batch, forward_backward_clip, source_identity_preflight, checkpoint_expected,
    make_payload, save_checkpoint, apply_verified_checkpoint, implementation_hashes,
    worker_init, collate, atomic_json, adamw, state_digest, batch_plan, finalfit_lr, assert_determinism,
)

PUBLIC = ROOT / "docs/formal_training/b0_phase_b_finalfit/runs"


def environment():
    python = Path(r"F:\pytorch\Research\.venv-cuda\Scripts\python.exe")
    if (Path(sys.executable).resolve() != python.resolve() or not torch.cuda.is_available()
            or not torch.cuda.is_bf16_supported() or torch.__version__ != "2.11.0+cu128"
            or torch.version.cuda != "12.8"):
        raise RuntimeError("Verified CUDA interpreter/BF16 environment changed")
    return {"python": sys.executable, "python_version": sys.version.split()[0],
        "torch": torch.__version__, "cuda": torch.version.cuda,
        "numpy": importlib.metadata.version("numpy"), "netCDF4": importlib.metadata.version("netCDF4"),
        "PyYAML": importlib.metadata.version("PyYAML"), "gpu": torch.cuda.get_device_name(),
        "dedicated_bytes": torch.cuda.get_device_properties(0).total_memory,
        "driver": subprocess.check_output(["nvidia-smi", "--query-gpu=driver_version", "--format=csv,noheader"], text=True).strip(),
        "deterministic": True, "GradScaler": False, "num_workers": 2, "prefetch_factor": 1}


def now():
    return datetime.now(timezone.utc).isoformat()


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def exclusive_json(path, value):
    with Path(path).open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(value, stream, indent=2, allow_nan=False, ensure_ascii=False, default=str)
        stream.write("\n")


def make_dataset(contract, staging):
    mapping = load_sp04()
    mask_path = Path(contract.protocol["identity"]["yunnan_mask"]["path"])
    mask = read_frozen_yunnan_mask(mask_path, mapping)
    if int(mask.sum()) != 3430:
        raise ValueError("Frozen SP04 Yunnan mask count changed")
    return FinalFitDataset(contract, mapping, mask, mask_path, staging)


def no_checkpoint_load(*_args, **_kwargs):
    raise RuntimeError("Phase-A or other checkpoint initialization forbidden in fresh preflight")


def execute_update(model, optimizer, batch, update, authorization=None, *, engineering=False):
    started = time.perf_counter()
    result = forward_backward_clip(model, optimizer, batch, update, authorization, engineering=engineering)
    assert_determinism()
    optimizer.step()
    if (any(not bool(torch.isfinite(p).all()) for p in model.parameters())
            or any(not bool(torch.isfinite(v).all()) for s in optimizer.state.values() for v in s.values() if isinstance(v, torch.Tensor))):
        raise FloatingPointError("Nonfinite model/optimizer after update")
    torch.cuda.synchronize()
    result.update(optimizer_step_pass=True, wall_seconds=time.perf_counter()-started)
    return result


def preflight(out):
    """Exactly two independent temporary updates, no fit loop and no formal checkpoint."""
    out = Path(out).resolve()
    allowed = (ROOT / "docs/phase_b_formal_runner/runs").resolve()
    if out.parent != allowed or not out.name.startswith("run_") or not out.is_dir():
        raise ValueError("Preflight requires an existing independent audit run directory")
    contract = RunnerContract.load()
    permutation, batches = batch_plan(0)
    selections = [batches[0].tolist(), batches[-1].tolist()]
    exclusive_json(out / "preflight_sample_selection.json", {"scope": "ENGINEERING_ONLY",
        "declared_before_source_read": True, "epoch": 1, "permutation_sha256": state_digest(permutation),
        "selections": [{"indices": ids, "sample_ids": [contract.rows[i]["sample_id"] for i in ids],
            "scheduler_u": u} for ids, u in zip(selections, [1, STEPS])],
        "selection_rule": "first full batch and actual final singleton of frozen seed-2026 epoch-one permutation"})
    dataset = make_dataset(contract, STAGING / ("phase_b_runner_" + out.name) / "preflight")
    evidence = []
    torch.set_num_threads(2)
    with patch("torch.load", side_effect=no_checkpoint_load) as checkpoint_loader:
        for ids, u in zip(selections, [1, STEPS]):
            samples, details = collate([dataset[index] for index in ids])
            # A separate fresh initialization and optimizer for each smoke. Forced u
            # never means that preceding updates have been performed or restored.
            model = fresh_model("cuda")
            initial_sha = state_digest(model.state_dict())
            env = environment()
            optimizer, groups = adamw(model)
            batch = prepare_batch(samples, details, engineering=True)
            torch.cuda.reset_peak_memory_stats()
            result = execute_update(model, optimizer, batch, u, engineering=True)
            after_sha = state_digest(model.state_dict())
            if initial_sha == after_sha or any(float(s["step"]) != 1 for s in optimizer.state.values()):
                raise ValueError("Independent temporary smoke must execute exactly one actual update")
            if u == STEPS and (result["LR"] != 1e-4 or result["valid_denominator"] != 3430):
                raise ValueError("Singleton actual first-epoch tail LR/denominator failed")
            result.update(sample_ids=[s.sample_id for s in samples], source_read_audit=details,
                initial_model_state_sha256=initial_sha, updated_model_state_sha256=after_sha,
                actual_optimizer_steps_in_this_fixture=1, preceding_updates_executed=0,
                parameter_groups=groups, peak_GPU_allocated_bytes=torch.cuda.max_memory_allocated(),
                peak_GPU_reserved_bytes=torch.cuda.max_memory_reserved())
            model_ref, optimizer_ref = weakref.ref(model), weakref.ref(optimizer)
            del model, optimizer, batch, samples, details, groups
            gc.collect()
            torch.cuda.empty_cache()
            if model_ref() is not None or optimizer_ref() is not None:
                raise ValueError("Temporary model/optimizer not released")
            result["temporary_model_optimizer_released"] = True
            evidence.append(result)
            print("ENGINEERING_PREFLIGHT " + json.dumps({k: result[k] for k in
                ("scope", "scheduler_u", "LR", "batch_size", "valid_denominator", "loss")}), flush=True)
    if dataset.staging._owned or checkpoint_loader.call_count:
        raise ValueError("Preflight staging/checkpoint-load isolation failed")
    exclusive_json(out / "engineering_preflight.json", {"status": "PASS", "scope": "ENGINEERING_ONLY",
        "batches": evidence, "SINGLETON_ACTUAL_TAIL_LR_SMOKE_PASS": True,
        "environment": env, "runner_config_sha256": contract.config_sha256,
        "implementation_sha256": implementation_hashes(), "checkpoint_load_calls": checkpoint_loader.call_count,
        "temporary_checkpoint_binaries_created": 0, "owned_staging_files_remaining": len(dataset.staging._owned),
        "ENGINEERING_OPTIMIZER_STEPS": 2, "ENGINEERING_BACKWARD_CALLS": 2,
        "FORMAL_OPTIMIZER_STEPS": 0, "PHASE_B_AUTHORIZED": False,
        "PHASE_B_FORMAL_TRAINING_STARTED": False, "2025_PIXELS_READ": 0, "completed_utc": now()})


def train_epoch(model, optimizer, dataset, authorization, epoch, public, local):
    coverage = EpochCoverage(epoch)
    loader = DataLoader(dataset, batch_size=2, sampler=coverage.order, num_workers=2,
        prefetch_factor=1, persistent_workers=False, pin_memory=False, drop_last=False,
        worker_init_fn=worker_init, collate_fn=collate,
        generator=torch.Generator().manual_seed(2026+epoch-1))
    s_occ = s_qr = 0.
    nrain = 0
    io = {"copy_seconds": 0., "read_seconds": 0., "temporary_bytes_peak_per_worker": 0, "cleanup_success": True}
    started = time.perf_counter()
    with (local / "updates.jsonl").open("a", encoding="utf-8", newline="\n") as log:
        for index, (samples, details) in enumerate(loader):
            u = (epoch-1)*STEPS+index+1
            coverage.add([d["index"] for d in details], len(samples)*3430)
            batch = prepare_batch(samples, details, authorization)
            result = execute_update(model, optimizer, batch, u, authorization)
            s_occ += result["S_occ"]
            s_qr += result["S_qr"]
            nrain += result["rainy_count"]
            for detail in details:
                io["copy_seconds"] += detail["copy_seconds"]
                io["read_seconds"] += detail["read_seconds"]
                io["temporary_bytes_peak_per_worker"] = max(io["temporary_bytes_peak_per_worker"], detail["temporary_bytes_peak"])
                io["cleanup_success"] &= detail["cleanup_success"]
            entry = {**result, "epoch": epoch, "global_update": u,
                "sample_ids": [s.sample_id for s in samples], "finalfit_indices": [d["index"] for d in details], "utc": now()}
            log.write(json.dumps(entry, allow_nan=False)+"\n")
            log.flush()
            if index == 0 or u % 100 == 0 or index == STEPS-1:
                atomic_json(public / "progress.json", entry)
                print("FINALFIT " + json.dumps(entry), flush=True)
            del batch, samples, details
    receipt = coverage.complete()
    metrics = {"S_occ": s_occ, "S_qr": s_qr, "D_valid": receipt["denominator"], "N_rain": nrain,
        "training_core_loss": (s_occ+s_qr)/receipt["denominator"], "wall_seconds": time.perf_counter()-started,
        "IO": io, "checkpoint_selection_uses_training_metrics": False}
    return coverage, metrics


def formal_run(args, *, resume=False):
    # Reject current release BEFORE raw reads, model construction or creating formal directories.
    if args.authorization is None or not args.authorization_sha256:
        raise PermissionError("PHASE_B_AUTHORIZED=false; no formal training started")
    contract = RunnerContract.load()
    authorization = PhaseBAuthorization.load(args.authorization, args.authorization_sha256, contract)
    authorization.require()
    if resume:
        run_id = args.run_id
        if not run_id or Path(run_id).name != run_id or not run_id.startswith("run_"):
            raise ValueError("Explicit valid run-id required for epoch-boundary resume")
    else:
        if args.run_id:
            raise ValueError("Fresh training must create a new run; supplied run-id requires resume")
        run_id = "run_" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S_%fZ")
    public, local = PUBLIC / run_id, CHECKPOINT_ROOT / run_id
    if resume and (public / "final_status.json").exists():
        raise ValueError("Completed FinalFit cannot be restarted or reselected")
    source = source_identity_preflight(contract)
    torch.set_num_threads(2)
    model = fresh_model("cuda")
    optimizer, groups = adamw(model)
    env = environment()
    expected = checkpoint_expected(contract, authorization, run_id, env, groups, source)
    if resume:
        manifest = read(public / "run_manifest.json")
        if manifest["checkpoint_expected"] != expected or manifest["source_identity"] != source:
            raise ValueError("Resume run provenance changed before state application")
        registry = read(public / "checkpoint_registry.json")
        if ("BEST" in registry or registry["run_id"] != run_id
                or (registry.get("FINAL") is not None and registry["FINAL"] != registry["LAST"])):
            raise ValueError("Resume only verified LAST; no epoch selection")
        payload = apply_verified_checkpoint(registry["LAST"], expected, model, optimizer)
        completed_epoch = payload["completed_epoch"]
        if completed_epoch >= EPOCHS:
            if not registry.get("FINAL"):
                raise ValueError("Epoch eleven checkpoint must have matching FINAL identity")
            # Recover a crash after durable FINAL/registry but before the final status
            # write. This applies no optimizer update and never selects another epoch.
            exclusive_json(public / "final_status.json", {"state": "FINALFIT_COMPLETED",
                "completed_epoch": EPOCHS, "FORMAL_OPTIMIZER_STEPS": UPDATES,
                "FINAL": registry["FINAL"], "2025_PIXELS_READ": 0, "PHASE_B_AUTHORIZED": True,
                "PHASE_B_FORMAL_TRAINING_STARTED": True, "metadata_recovery_only": True,
                "additional_optimizer_steps": 0, "completed_utc": now()})
            return
        exclusive_json(public / ("resume_"+datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S_%fZ")+".json"),
            {"verified_LAST": registry["LAST"], "next_complete_epoch": completed_epoch+1,
             "provenance_checked_before_state_application": True, "partial_epoch_discarded": True})
        del payload
    else:
        public.mkdir(parents=True, exist_ok=False)
        local.mkdir(parents=True, exist_ok=False)
        registry = {"run_id": run_id, "LAST": None, "FINAL": None}
        completed_epoch = 0
        exclusive_json(public / "run_manifest.json", {"run_id": run_id, "scope": SCOPE,
            "checkpoint_expected": expected, "source_identity": source, "started_utc": now(),
            "fresh_model_initial_state_sha256": state_digest(model.state_dict()), "formal_checkpoint_root": str(local)})
    dataset = make_dataset(contract, STAGING / ("formal_phase_b_"+run_id))
    atomic_json(public / "run_status.json", {"PHASE_B_AUTHORIZED": True, "PHASE_B_FORMAL_TRAINING_STARTED": True,
        "state": "TRAINING", "resume_epoch": completed_epoch, "updated_utc": now()})
    try:
        for epoch in range(completed_epoch+1, EPOCHS+1):
            coverage, metrics = train_epoch(model, optimizer, dataset, authorization, epoch, public, local)
            payload = make_payload(model, optimizer, expected, epoch, coverage, metrics)
            registry = save_checkpoint(local, public, payload, expected, registry)
            del payload
            atomic_json(public / f"epoch_{epoch:03d}_history.json", {"epoch": epoch, "coverage": coverage.complete(),
                "training_metrics": metrics, "checkpoint": registry["LAST"], "validation_executed": False})
        atomic_json(public / "final_status.json", {"state": "FINALFIT_COMPLETED", "completed_epoch": EPOCHS,
            "FORMAL_OPTIMIZER_STEPS": UPDATES, "FINAL": registry["FINAL"], "2025_PIXELS_READ": 0,
            "PHASE_B_AUTHORIZED": True, "PHASE_B_FORMAL_TRAINING_STARTED": True, "completed_utc": now()})
    except Exception as error:
        atomic_json(public / "run_status.json", {"state": "INTERRUPTED", "error": repr(error),
            "LAST": registry["LAST"], "resume_policy": "next full epoch from verified LAST only", "updated_utc": now()})
        raise


def parser():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("action", choices=["preflight", "train", "resume"])
    p.add_argument("--run-dir", type=Path, help="existing independent engineering audit directory")
    p.add_argument("--run-id", help="existing formal run identity, resume only")
    p.add_argument("--authorization", type=Path, help="future separate researcher-approved authorization")
    p.add_argument("--authorization-sha256", help="researcher-approved authorization file SHA256")
    return p


if __name__ == "__main__":
    args = parser().parse_args()
    if args.action == "preflight":
        if args.run_dir is None or args.run_id or args.authorization or args.authorization_sha256:
            raise SystemExit("Preflight needs --run-dir only; formal authorization/run-id is not used")
        preflight(args.run_dir)
    else:
        if args.run_dir is not None:
            raise SystemExit("Formal execution does not accept an engineering run-dir")
        formal_run(args, resume=args.action == "resume")
