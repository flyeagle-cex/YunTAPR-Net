"""Explicit researcher-authorized B0 Phase-A, seed 2026, frozen Protocol v1.0.

No Phase-B, 2025 source access, fitting normalization, or automatic protocol edits.
Initialize first; then execute --run-id. Resume is only from a verified LAST epoch.
"""
from __future__ import annotations
import argparse
import csv
from dataclasses import asdict
from datetime import datetime, timezone
import gc
import hashlib
import importlib.metadata
import json
import math
import os
from pathlib import Path
import platform
import subprocess
import sys
import time
import traceback
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "src"), str(ROOT / "scripts")]
import numpy as np
import torch
import yaml
from torch.utils.data import DataLoader
from yuntapr.contracts.loader import sha256
from yuntapr.data.dataset_b0 import B0Record
from yuntapr.data.masks import read_frozen_yunnan_mask
from yuntapr.data.sample_schema import HimawariFrame, utc
from yuntapr.models.b0 import B0Model
from yuntapr.spatial.sp04_mapping import load_sp04
from yuntapr.training.phase_a_protocol import (load_protocol, head_pin, adamw, seed_reproducibility,
    phase_a_lr_for_update, epoch_permutation, ValidationSelection, state_digest)
from yuntapr.training.phase_a_validation import GlobalValidationAccumulator
from yuntapr.training.formal_phase_a import (AUTH_PATH, CHECKPOINT_ROOT, SCOPE, MU, SIGMA,
    NORMALIZATION_SHA, FormalAuthorization, FormalDataset, formal_worker_init, formal_collate,
    formal_batch, formal_forward, formal_loss, precision_check, train_numerators,
    atomic_json, guard_record, assert_determinism, make_payload, save_checkpoint,
    load_verified_checkpoint, apply_verified_checkpoint)

BASELINE = "aa65a5b4b33f04d7adddd1ca832963dcb21e4487"
PYTHON = Path(r"F:\pytorch\Research\.venv-cuda\Scripts\python.exe")
PRIOR = ROOT / "docs/b0_pretraining_closure/runs/run_20260930T095416Z"
DRYRUN = ROOT / "docs/phase_a_optimizer_dryrun/runs/run_20261001T030242Z"
STAGING_ROOT = Path(r"F:\pytorch\Research\stage0_himawari\cache\staging")
HROOT = Path(r"H:\葵花202303_202510")
PUBLIC_ROOT = ROOT / "docs/formal_training/b0_phase_a/runs"
PROTOCOL_SHA = "dcacbe34050da7e777ad0cb72c53b5b51b48ce57eb9260b09fd283d96de12a4a"
PROTOCOL_DOC = "docs/training_protocol/PHASE_A_TRAINING_PROTOCOL_v1.0.md"
PROTOCOL_DOC_SHA = "3480baca7e7dd1839a534660fef5e7a41a9e013107954cdef44574e110631e2c"
SCHEDULER_PATH = "src/yuntapr/training/phase_a_protocol.py"
SCHEDULER_SHA = "95ed5a182590a8a84ee7659720a89ea7e36687800cb7e7441f60d30d795a8b19"
SUITES = ("scientific_freeze", "b0_skeleton", "development_qc", "scientific_freeze_v1_1",
    "quantile_numerical_closure", "training_environment_audit", "gpu_training_feasibility",
    "phase_a_protocol_prefreeze", "phase_a_protocol_v1", "phase_a_optimizer_resume")


def now():
    return datetime.now(timezone.utc).isoformat()


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def rows(path):
    with Path(path).open(encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def table(path, records, empty_fields=()):
    keys = list(dict.fromkeys(k for record in records for k in record)) or list(empty_fields)
    with Path(path).open("x", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=keys, lineterminator="\n")
        writer.writeheader()
        writer.writerows(records)


def immutable_inventory():
    entries = subprocess.check_output(["git", "ls-tree", "-r", "-z", BASELINE], cwd=ROOT).decode("utf-8")
    expected = {}
    for entry in entries.rstrip("\0").split("\0"):
        metadata, name = entry.split("\t", 1)
        if name != ".gitignore":
            expected[name] = metadata.split()[2]
    names = list(expected)
    observed = subprocess.run(["git", "hash-object", "--stdin-paths"], cwd=ROOT, text=True,
        encoding="utf-8", input="\n".join(names) + "\n", capture_output=True, check=True).stdout.splitlines()
    if len(observed) != len(names) or any(expected[n] != v for n, v in zip(names, observed)):
        raise RuntimeError("STOP: baseline historical file changed")
    return {n: sha256(ROOT / n) for n in names}


def assert_protocol(config):
    checks = {
        "version": "v1.0", "model.name": "B0", "loss.core": "L_occ + L_qr",
        "loss.occurrence.alpha": .5, "loss.occurrence.gamma": 2., "loss.quantile.count": 32,
        "loss.quantile.axis_reduction": "mean", "loss.quantile.epsilon_mono": .0001,
        "optimizer.type": "AdamW", "optimizer.betas": [.9, .999], "optimizer.eps": 1e-8,
        "optimizer.weight_decay": 1e-4, "optimizer.foreach": False, "optimizer.fused": False,
        "optimizer.amsgrad": False, "optimizer.maximize": False, "optimizer.capturable": False,
        "optimizer.differentiable": False,
        "optimizer.expected_parameter_counts": {"DECAY_GROUP": 4322832, "NO_DECAY_GROUP": 6529, "total": 4329361},
        "batch.train_physical": 2, "batch.gradient_accumulation_steps": 1, "batch.effective": 2,
        "batch.validation": 8, "batch.drop_last": False, "precision.AMP": "BF16",
        "precision.GradScaler": False, "precision.model_parameters": "float32",
        "precision.raw_quantile": "float32", "precision.qlog": "float64",
        "precision.qphysical": "float64", "precision.pinball": "float64", "precision.TF32": False,
        "data_loader.num_workers": 2, "data_loader.prefetch_factor": 1,
        "data_loader.pin_memory": False, "data_loader.persistent_workers": False,
        "data_loader.max_temporary_bytes_per_worker": 734003200,
        "data_loader.SHA_verification": True, "data_loader.cleanup_required": True,
        "sampling.train_count": 11720, "sampling.validation_count": 11727,
        "sampling.train_year": 2023, "sampling.validation_year": 2024,
        "sampling.train_once_per_epoch": True, "sampling.augmentation": "NONE",
        "sampling.rain_oversampling": False, "sampling.dry_undersampling": False,
        "sampling.class_balanced_sampler": False, "sampling.rate_based_sampler": False,
        "sampling.train_shuffle": True, "sampling.validation_shuffle": False,
        "scheduler.base_lr": 1e-4, "scheduler.min_lr": 1e-6, "scheduler.steps_per_epoch": 5860,
        "scheduler.max_epochs": 50, "scheduler.warmup_epochs": 1, "scheduler.W": 5860,
        "scheduler.U": 293000, "scheduler.apply_before_optimizer_step": True,
        "epochs.max_epochs": 50, "epochs.full_2024_validation_every_completed_epoch": True,
        "epochs.early_stopping.patience": 8, "epochs.early_stopping.min_delta_absolute": 1e-4,
        "epochs.early_stopping.separate_from_checkpoint_best": True,
        "gradient_clipping.global_norm": 5., "gradient_clipping.error_if_nonfinite": True,
        "reproducibility.primary_seed": 2026, "checkpoint.metric": "global_val_core_loss",
        "checkpoint.EPOCH_BOUNDARY_RESUME_ONLY": True, "checkpoint.raw_numerator_dtype": "float64"}
    for path, wanted in checks.items():
        actual = config
        for component in path.split("."):
            actual = actual[component]
        if actual != wanted:
            raise ValueError("Frozen protocol parameter mismatch: " + path)
    boundary = {str(u): phase_a_lr_for_update(u) for u in (1, 5860, 5861, 293000)}
    if boundary["1"] != 1.7064846416382254e-08 or boundary["5860"] != .0001 or not boundary["5861"] < .0001 or boundary["293000"] != 1e-6:
        raise ValueError("Corrected frozen scheduler boundary failure")
    return {"asserted_values": checks, "scheduler_boundaries": boundary, "status": "PASS"}


def initialize():
    if subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip() != BASELINE:
        raise RuntimeError("Unexpected Git baseline")
    config = load_protocol(expected_sha256=PROTOCOL_SHA)
    preserved = immutable_inventory()
    assert_protocol(config)
    identity = dict(config["identity"])
    identity["protocol"] = {"path": "config/training/phase_a_training_protocol_v1.yaml", "sha256": PROTOCOL_SHA}
    identity["protocol_document"] = {"path": PROTOCOL_DOC, "sha256": PROTOCOL_DOC_SHA}
    identity["scheduler_implementation"] = {"path": SCHEDULER_PATH, "sha256": SCHEDULER_SHA}
    for name, ref in identity.items():
        path = Path(ref["path"])
        if sha256(path if path.is_absolute() else ROOT / path) != ref["sha256"]:
            raise ValueError("Initialization identity mismatch: " + name)
    auth = {"version": "v1", "AUTHORIZED_BY": "RESEARCHER", "AUTHORIZED_SCOPE": "B0_PHASE_A_ONLY",
        "FORMAL_TRAINING_AUTHORIZED": True, "B0_FORMAL_TRAINING_STARTED": False,
        "PHASE_B_AUTHORIZED": False, "B1_TO_B8_AUTHORIZED": False, "baseline_commit": BASELINE,
        "seed": 2026, "protocol_version": "v1.0", "train_year": 2023, "validation_year": 2024,
        "months": list(range(3, 11)), "train_count": 11720, "validation_count": 11727,
        "FORMAL_CHECKPOINT_ROOT": str(CHECKPOINT_ROOT), "identity": identity,
        "forbidden": ["2025 source access", "Phase-B", "Phase-B normalization", "B1-B8",
            "hyperparameter search", "protocol changes", "normalization fitting", "mid-epoch resume"],
        "authority": "Researcher's B0 PHASE-A FORMAL DEVELOPMENT TRAINING v1 attachment and F-drive checkpoint-root confirmation",
        "authorization_document": "docs/formal_training_authorization/B0_PHASE_A_FORMAL_AUTHORIZATION_v1.md"}
    auth_path = ROOT / AUTH_PATH
    with auth_path.open("x", encoding="utf-8", newline="\n") as stream:
        yaml.safe_dump(auth, stream, allow_unicode=True, sort_keys=False)
    doc = ROOT / auth["authorization_document"]
    doc.parent.mkdir(parents=True, exist_ok=True)
    doc.write_text("# B0 Phase-A formal run authorization v1\n\n"
        "Researcher authorization is limited to B0 Phase-A, seed 2026, Protocol v1.0. "
        "Train: 11720 frozen eligible 2023 March–October identities; Validation: 11727 frozen eligible "
        "2024 March–October identities in pinned order. No 2025 sources, Phase-B, normalization fitting, "
        "B1–B8, search, or protocol edits are authorized.\n\n"
        "The protocol's historical false authorization fields remain immutable. The separate run overlay "
        "records FORMAL_TRAINING_AUTHORIZED=true, B0_FORMAL_TRAINING_STARTED=false at authorization time; "
        "run status records the actual start only after all preflight gates pass. "
        "AUTHORIZED_BY=RESEARCHER; AUTHORIZED_SCOPE=B0_PHASE_A_ONLY; PHASE_B_AUTHORIZED=false; "
        "B1_TO_B8_AUTHORIZED=false.\n\n"
        f"Baseline: `{BASELINE}`. Authorization YAML SHA256: `{sha256(auth_path)}`.\n\n"
        f"FORMAL_CHECKPOINT_ROOT: `{CHECKPOINT_ROOT}`. BEST/LAST only; binaries and optimizer states "
        "are never committed. SHA, size, absolute paths, histories, reports and manifests are public evidence.\n\n"
        "All inherited scientific, protocol, normalization, population, SP04 and mask identities, plus "
        "the corrected scheduler implementation, are pinned in the YAML identity map. "
        "Validation source hashes absent from the historical identity-only manifest are separately established "
        "at this run's preflight; no historical manifest or eligibility decision is replaced. "
        "All runtime reads must match that additional ledger and the frozen QC identities.\n\n"
        "Epoch-boundary resume requires verified LAST and all provenance before applying model, optimizer "
        "and RNG states. Any scientific protocol, numerical, identity or QC failure stops this run. "
        "No automatic remediation or next-stage execution is authorized.\n", encoding="utf-8", newline="\n")
    run_id = "run_" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S_%fZ")
    out = PUBLIC_ROOT / run_id
    out.mkdir(parents=True, exist_ok=False)
    manifest = {"run_id": run_id, "created_utc": now(), "baseline_commit": BASELINE,
        "scope": SCOPE, "authorization_manifest_sha256": sha256(auth_path),
        "authorization_document_sha256": sha256(doc), "public_directory": str(out),
        "local_checkpoint_directory": str(CHECKPOINT_ROOT / run_id), "identity": identity,
        "baseline_files_disk_sha256": preserved,
        "formal_implementation_sha256": {p: sha256(ROOT / p) for p in
            ("scripts/train_b0_phase_a_formal_v1.py", "src/yuntapr/training/formal_phase_a.py")},
        "FORMAL_TRAINING_AUTHORIZED": True, "B0_FORMAL_TRAINING_STARTED": False,
        "CHECKPOINT_BINARY_NOT_COMMITTED_TO_GIT": True, "2025_PIXELS_READ": 0,
        "PHASE_B_AUTHORIZED": False, "B1_TO_B8_AUTHORIZED": False}
    atomic_json(out / "formal_run_manifest.json", manifest)
    atomic_json(out / "run_status.json", {"run_id": run_id, "state": "INITIALIZED",
        "FORMAL_TRAINING_AUTHORIZED": True, "B0_FORMAL_TRAINING_STARTED": False, "updated_utc": now()})
    print("INITIALIZED " + str(out), flush=True)


def load_populations(config):
    train = rows(ROOT / config["identity"]["eligible_train_manifest"]["path"])
    val = rows(ROOT / config["identity"]["eligible_validation_manifest"]["path"])
    if len(train) != 11720 or len(val) != 11727:
        raise ValueError("Frozen Train/Validation population changed")
    pair_rows = rows(ROOT / config["identity"]["combined_eligibility_source"]["path"])
    pairs = {r["window_start"]: r for r in pair_rows if r["formal_supervised_eligible"] == "True" and r["month"][:4] in ("2023", "2024")}
    development = read(PRIOR / "manifest.json")
    prior_path = ROOT / "docs/development_qc/runs/run_20260930T075627Z/manifest.json"
    if sha256(prior_path) != development["prior_development_manifest_sha256"]:
        raise ValueError("Prior development QC provenance mismatch")
    prior = read(prior_path)
    info = prior["local_evidence"]["b13_per_frame.csv"]
    if sha256(Path(info["local_path"])) != info["sha256"]:
        raise ValueError("Frozen per-frame QC ledger SHA mismatch")
    frames = {r["relative_path"]: r for r in rows(info["local_path"]) if r["month"][:4] in ("2023", "2024")}
    day_file = PRIOR / "imerg_development_revalidation.json"
    if sha256(day_file) != development["public_files_sha256"][day_file.name]:
        raise ValueError("IMERG daily source provenance mismatch")
    days = {r["day_path"]: r["sha256"] for r in read(day_file)["days"]}
    groups = []
    for role, manifest_rows, year in (("Train", train, 2023), ("Validation", val, 2024)):
        records, identities = [], []
        for index, row in enumerate(manifest_rows):
            start = utc(row["window_start"])
            if start.year != year or start.month not in range(3, 11):
                raise ValueError("Unauthorized population role")
            pair = pairs[row["window_start"]]
            relative = row.get("b13_relative_path", row.get("selected_b13_relative_path"))
            if (relative != pair["selected_b13_relative_path"] or row["analysis_time"] != pair["analysis_time"]
                    or row["imerg_day_path"] != pair["imerg_day_path"] or row["imerg_index"] != pair["imerg_index"]
                    or pair["b13_full_valid"] != "True" or pair["selected_nominal"] != pair["expected_nominal"]):
                raise ValueError("Frozen cross-source sample identity mismatch")
            frame_row = frames[relative]
            if frame_row["status"] != "FULL_VALID" or int(frame_row["valid_count"]) != 251001:
                raise ValueError("Frozen B13 full-valid QC mismatch")
            frame = HimawariFrame(HROOT / relative, utc(frame_row["nominal"]), utc(frame_row["obs_start"]),
                utc(frame_row["obs_end"]), utc(frame_row["date_created"]) if frame_row["date_created"] else None)
            sample_id = row.get("sample_id", row["window_start"])
            record = B0Record(sample_id, start, (frame,), Path(row["imerg_day_path"]), int(row["imerg_index"]), "IMERG", "V07", "Final", True)
            guard_record(record)
            records.append(record)
            identities.append({"role": role, "index": index, "sample_id": sample_id, "year": year,
                "window_start": row["window_start"], "b13_relative_path": relative,
                "b13_sha256": row.get("source_sha256", ""), "b13_bytes": row.get("source_bytes", ""),
                "imerg_day_path": row["imerg_day_path"], "imerg_index": int(row["imerg_index"]),
                "imerg_sha256": days[row["imerg_day_path"]],
                "imerg_valid_yunnan_count": int(pair["imerg_valid_yunnan_count"]),
                "imerg_rain_yunnan_count": int(pair["imerg_rain_yunnan_count"]),
                "b13_sha_scope": "HISTORICALLY_PINNED_TRAIN" if role == "Train" else "RUN_PREFLIGHT_IDENTITY"})
        if len({r.sample_id for r in records}) != len(records):
            raise ValueError("Duplicate frozen population identity")
        groups.append((records, identities))
    return groups, {"per_frame_QC_sha256": info["sha256"], "IMERG_day_ledger_sha256": sha256(day_file)}


def run_tests(out, suffix):
    # Execute every test anew; historical evidence is fixture input, never a substitute for execution.
    os.environ["YUNTAPR_PROTOCOL_DRYRUN_EVIDENCE"] = str(DRYRUN)
    suite_rows = []
    with (out / f"test_results_{suffix}.txt").open("x", encoding="utf-8", newline="\n") as stream:
        for name in (*SUITES, "formal_phase_a"):
            stream.write("\nSUITE " + name + "\n")
            result = unittest.TextTestRunner(stream=stream, verbosity=2).run(unittest.TestLoader().discover(str(ROOT / "tests" / name)))
            row = {"suite": name, "executed": result.testsRun, "failures": len(result.failures),
                "errors": len(result.errors), "skipped": len(result.skipped), "pass": result.wasSuccessful() and not result.skipped}
            suite_rows.append(row)
            stream.flush()
            print("TEST " + json.dumps(row), flush=True)
            if not row["pass"]:
                break
    count = sum(r["executed"] for r in suite_rows[:10])
    passed = len(suite_rows) == 11 and count == 162 and all(r["pass"] for r in suite_rows)
    report = {"status": "PASS" if passed else "FAIL", "suites": suite_rows,
        "current_162_tests_actually_executed": count, "new_formal_tests": suite_rows[-1]["executed"] if len(suite_rows) == 11 else 0,
        "historical_evidence_substituted_for_execution": False, "additional_formal_optimizer_steps": 0,
        "formal_checkpoint_states_modified": False, "pass": passed}
    atomic_json(out / f"test_summary_{suffix}.json", report)
    if not passed:
        raise RuntimeError("STOP: regression/formal preflight tests failed")
    return report


def identity_preflight(out, groups):
    known_val = {r["sample_id"]: r["read_evidence"]["readers"]["b13"]["source_sha256"]
        for r in read(ROOT / "docs/phase_a_protocol_prefreeze/runs/run_20261001T014523Z/loss_scale_smoke.json")["samples"] if r["year"] == 2024}
    all_identities = []
    checked_days = set()
    began = time.perf_counter()
    for records, identities in groups:
        for record, identity in zip(records, identities):
            guard_record(record)
            path = record.frames[0].path
            actual = sha256(path)
            size = path.stat().st_size
            if identity["b13_sha256"] and (actual != identity["b13_sha256"] or size != int(identity["b13_bytes"])):
                raise ValueError("Preflight frozen Train source SHA/size mismatch: " + record.sample_id)
            if identity["year"] == 2024 and record.sample_id in known_val and actual != known_val[record.sample_id]:
                raise ValueError("Historical Validation spot-check SHA mismatch")
            identity.update(b13_sha256=actual, b13_bytes=size)
            if identity["imerg_day_path"] not in checked_days:
                if sha256(record.imerg_path) != identity["imerg_sha256"]:
                    raise ValueError("Preflight frozen IMERG source SHA mismatch")
                checked_days.add(identity["imerg_day_path"])
            all_identities.append(identity)
            if len(all_identities) % 250 == 0:
                print(f"PREFLIGHT_SOURCE_SHA {len(all_identities)}/23447 elapsed_seconds={time.perf_counter()-began:.1f}", flush=True)
    table(out / "source_identity_preflight.csv", all_identities)
    return {"status": "PASS", "Train_sources_checked": 11720, "Validation_sources_checked": 11727,
        "IMERG_days_checked": len(checked_days), "historical_validation_SHA_checks": len(known_val),
        "source_identity_ledger_sha256": sha256(out / "source_identity_preflight.csv"),
        "Validation_SHA_scope": "Additional run-preflight hashes; historical identity-only manifest remains unchanged",
        "source_bytes_read": sum(int(r["b13_bytes"]) for r in all_identities),
        "wall_seconds": time.perf_counter()-began, "2025_PIXELS_READ": 0}


def environment():
    if Path(sys.executable).resolve() != PYTHON.resolve() or not torch.cuda.is_available() or not torch.cuda.is_bf16_supported():
        raise RuntimeError("Verified CUDA interpreter/BF16 unavailable")
    if torch.__version__ != "2.11.0+cu128" or torch.version.cuda != "12.8":
        raise RuntimeError("CUDA training environment identity changed")
    driver = subprocess.check_output(["nvidia-smi", "--query-gpu=driver_version", "--format=csv,noheader"], text=True).strip()
    return {"python": sys.executable, "python_version": platform.python_version(), "torch": torch.__version__,
        "numpy": np.__version__, "netCDF4": importlib.metadata.version("netCDF4"), "PyYAML": importlib.metadata.version("PyYAML"),
        "cuda_runtime": torch.version.cuda, "driver": driver, "gpu": torch.cuda.get_device_name(),
        "capability": list(torch.cuda.get_device_capability()), "dedicated_bytes": torch.cuda.get_device_properties(0).total_memory,
        "torch_threads": torch.get_num_threads(), "worker_threads": 1, "deterministic": True, "GradScaler": False}


def checkpoint_expected(manifest, protocol, groups, env, source_sha):
    refs = protocol["identity"]
    aliases = {"scientific_contract_sha256": "scientific_contract_v1.1", "engineering_config_sha256": "engineering_v4",
        "normalization_artifact_sha256": "phase_a_normalization_artifact", "train_manifest_sha256": "eligible_train_manifest",
        "validation_manifest_sha256": "eligible_validation_manifest", "SP04_mapping_sha256": "SP04_mapping", "Yunnan_mask_sha256": "yunnan_mask"}
    return {"scope": SCOPE, "checkpoint_kind": "FORMAL_COMPLETED_EPOCH", "run_id": manifest["run_id"],
        "FORMAL_TRAINING_AUTHORIZED": True, "authorization_manifest_sha256": manifest["authorization_manifest_sha256"],
        "authorization_document_sha256": manifest["authorization_document_sha256"], "protocol_version": "v1.0",
        "protocol_sha256": PROTOCOL_SHA, "protocol_document_sha256": PROTOCOL_DOC_SHA,
        "scientific_freeze_version": "v1.1", **{k: refs[n]["sha256"] for k, n in aliases.items()},
        "identities": {name: ref["sha256"] for name, ref in refs.items()},
        "formal_implementation_sha256": manifest["formal_implementation_sha256"],
        "source_identity_preflight_sha256": source_sha, "focal_alpha": .5, "focal_gamma": 2.,
        "optimizer_config": protocol["optimizer"], "weight_decay_groups": groups,
        "base_lr": 1e-4, "min_lr": 1e-6, "physical_batch": 2, "effective_batch": 2,
        "validation_batch": 8, "gradient_accumulation": 1, "AMP_mode": "BF16", "seed": 2026,
        "epoch_seed_rule": "2026 + zero_based_epoch_index", "best_checkpoint_metric": "global_val_core_loss",
        "EPOCH_BOUNDARY_RESUME_ONLY": True, "environment": env, "2025_PIXELS_READ": 0,
        "PHASE_B_AUTHORIZED": False, "B1_TO_B8_AUTHORIZED": False}


def loader(dataset, order, batch, epoch):
    return DataLoader(dataset, batch_size=batch, sampler=order, num_workers=2, prefetch_factor=1,
        pin_memory=False, persistent_workers=False, drop_last=False, collate_fn=formal_collate,
        worker_init_fn=formal_worker_init, generator=torch.Generator().manual_seed(2026 + epoch))


def empty_io():
    return {"copy_seconds_sum": 0., "read_seconds_sum": 0., "temporary_bytes_peak_per_worker": 0, "cleanup_success": True, "samples": 0}


def add_io(summary, details):
    for row in details:
        summary["copy_seconds_sum"] += row["copy_seconds"]
        summary["read_seconds_sum"] += row["read_seconds"]
        summary["temporary_bytes_peak_per_worker"] = max(summary["temporary_bytes_peak_per_worker"], row["temporary_bytes_peak"])
        summary["cleanup_success"] &= row["cleanup_success"]
        summary["samples"] += 1


def train_epoch(out, local, model, optimizer, raw, dataset, authorization, epoch, progress):
    model.train()
    order = epoch_permutation(epoch-1).tolist()
    if len(order) != 11720 or sorted(order) != list(range(11720)):
        raise ValueError("Train permutation is not exactly frozen population once")
    torch.cuda.reset_peak_memory_stats()
    started = time.perf_counter()
    previous = started
    s_occ = s_qr = wait = 0.
    denominator = rainy = seen = clipped = 0
    norms, io = [], empty_io()
    iterator = iter(loader(dataset, order, 2, epoch-1))
    update_start = (epoch-1)*5860+1
    with (local / "train_updates.jsonl").open("a", encoding="utf-8", newline="\n") as log:
        for batch_index, (samples, details) in enumerate(iterator):
            loaded = time.perf_counter()
            wait += loaded-previous
            expected_order = order[seen:seen+len(samples)]
            if [d["index"] for d in details] != expected_order or any(s.imerg_window_start.year != 2023 for s in samples):
                raise ValueError("Train sampler/role/identity order mismatch")
            seen += len(samples)
            add_io(io, details)
            u = (epoch-1)*5860 + batch_index+1
            progress.update(epoch=epoch, phase="TRAIN", global_update_completed=u-1,
                current_sample_ids=[s.sample_id for s in samples], current_batch_indices=expected_order)
            batch = formal_batch(samples, details, authorization)
            optimizer.zero_grad(set_to_none=True)
            lr = phase_a_lr_for_update(u)
            for group in optimizer.param_groups:
                group["lr"] = lr
            with torch.autocast("cuda", dtype=torch.bfloat16):
                output = formal_forward(model, batch, authorization)
                loss = formal_loss(output, batch)
            precision_check(model, raw["dtype"], output, loss)
            numerator_occ, numerator_qr, valid, nrain = train_numerators(output, batch)
            s_occ += numerator_occ
            s_qr += numerator_qr
            denominator += valid
            rainy += nrain
            loss.total.backward()
            parameters = list(model.parameters())
            if any(p.grad is None or not bool(torch.isfinite(p.grad).all()) for p in parameters):
                raise FloatingPointError("Nonfinite or missing formal gradient")
            norm = float(torch.nn.utils.clip_grad_norm_(parameters, max_norm=5., norm_type=2., error_if_nonfinite=True, foreach=False))
            norms.append(norm)
            clipped += int(5./(norm+1e-6) < 1.)
            assert_determinism()
            optimizer.step()
            if (any(not bool(torch.isfinite(p).all()) for p in parameters)
                    or any(not bool(torch.isfinite(v).all()) for state in optimizer.state.values() for v in state.values() if isinstance(v, torch.Tensor))):
                raise FloatingPointError("Nonfinite formal parameter/optimizer state")
            torch.cuda.synchronize()
            progress["global_update_completed"] = u
            elapsed = time.perf_counter()-started
            if u % 100 == 0 or batch_index == 0 or batch_index == 5859:
                entry = {"utc": now(), "epoch": epoch, "global_update": u, "LR": lr,
                    "running_L_occ": s_occ/denominator, "running_L_qr": s_qr/denominator,
                    "running_L_total": (s_occ+s_qr)/denominator, "pre_clip_grad_norm": norm,
                    "clipping_fraction": clipped/(batch_index+1), "samples_per_second": seen/elapsed,
                    "GPU_allocated_bytes": torch.cuda.memory_allocated(), "GPU_reserved_bytes": torch.cuda.memory_reserved(),
                    "data_wait_seconds": wait, "training_samples_seen": seen, "scope": SCOPE}
                log.write(json.dumps(entry, allow_nan=False)+"\n")
                log.flush()
                atomic_json(out / "progress.json", {**entry, "updated_utc": now()})
                print("TRAIN " + json.dumps(entry), flush=True)
            del batch, output, loss, samples, details
            previous = time.perf_counter()
    if seen != 11720 or batch_index+1 != 5860 or denominator != sum(int(r["imerg_valid_yunnan_count"]) for r in dataset.identities):
        raise ValueError("Train epoch exact population/denominator mismatch")
    return {"epoch": epoch, "S_occ": s_occ, "S_qr": s_qr, "D_valid": denominator, "N_rain": rainy,
        "global_train_L_occ": s_occ/denominator, "global_train_L_qr": s_qr/denominator,
        "global_train_core_loss": (s_occ+s_qr)/denominator, "samples": seen, "updates": 5860,
        "global_update_start": update_start, "global_update_end": epoch*5860,
        "LR_start": phase_a_lr_for_update(update_start), "LR_end": phase_a_lr_for_update(epoch*5860),
        "wall_seconds": time.perf_counter()-started, "data_wait_seconds": wait,
        "pre_clip_grad_norm_min": min(norms), "pre_clip_grad_norm_max": max(norms),
        "pre_clip_grad_norm_mean": float(np.mean(norms)), "clipping_count": clipped, "clipping_fraction": clipped/5860,
        "peak_GPU_allocated_bytes": torch.cuda.max_memory_allocated(), "peak_GPU_reserved_bytes": torch.cuda.max_memory_reserved(),
        "I_O": io, "aggregation": "Global raw per-cell numerators, promoted before sum; global valid denominator. Production FP32 focal and float64 pinball, not mean batch loss."}


@torch.no_grad()
def validate_epoch(out, model, raw, dataset, authorization, epoch, progress):
    model.eval()
    torch.cuda.reset_peak_memory_stats()
    began = time.perf_counter()
    accumulator = GlobalValidationAccumulator()
    seen, io = 0, empty_io()
    for batch_index, (samples, details) in enumerate(loader(dataset, list(range(11727)), 8, epoch-1)):
        if [d["index"] for d in details] != list(range(seen, seen+len(samples))) or any(s.imerg_window_start.year != 2024 for s in samples):
            raise ValueError("Validation pinned order/role mismatch")
        progress.update(epoch=epoch, phase="VALIDATION", current_sample_ids=[s.sample_id for s in samples],
            validation_samples_completed=seen)
        batch = formal_batch(samples, details, authorization)
        with torch.autocast("cuda", dtype=torch.bfloat16):
            output = formal_forward(model, batch, authorization)
        precision_check(model, raw["dtype"], output)
        accumulator.add(output, batch.y_imerg, batch.imerg_valid_mask, batch.yunnan_eval_mask)
        seen += len(samples)
        add_io(io, details)
        if batch_index % 100 == 0 or seen == 11727:
            entry = {"epoch": epoch, "phase": "VALIDATION", "scenes_completed": seen,
                "scenes_required": 11727, "wall_seconds": time.perf_counter()-began, "updated_utc": now()}
            atomic_json(out / "progress.json", entry)
            print("VALIDATION " + json.dumps(entry), flush=True)
        del samples, details, batch, output
    if seen != 11727 or accumulator.n_valid != sum(int(r["imerg_valid_yunnan_count"]) for r in dataset.identities):
        raise ValueError("Validation exact population/denominator mismatch")
    report = accumulator.report()
    if report["strict_crossing_count"] or report["nonfinite_count"]:
        raise FloatingPointError("Formal Validation numerical failure")
    return {"epoch": epoch, **report, "samples": seen, "wall_seconds": time.perf_counter()-began,
        "peak_GPU_allocated_bytes": torch.cuda.max_memory_allocated(), "peak_GPU_reserved_bytes": torch.cuda.max_memory_reserved(), "I_O": io}


def finalize(out, local, manifest, expected, selection, registry, stop, failure, progress, started):
    epoch_paths = sorted(out.glob("epoch_*.json"))
    epochs = [read(path) for path in epoch_paths]
    training = [{k: v for k, v in e["train"].items() if not isinstance(v, (dict, list))} for e in epochs]
    validation = [{k: v for k, v in e["validation"].items() if not isinstance(v, (dict, list))} for e in epochs]
    table(out / "training_history.csv", training, ("epoch", "global_train_core_loss", "global_train_L_occ", "global_train_L_qr", "D_valid", "N_rain", "samples"))
    table(out / "validation_history.csv", validation, ("epoch", "global_val_core_loss", "global_L_occ", "global_core_L_qr", "N_valid", "N_rain", "samples"))
    atomic_json(out / "early_stopping_summary.json", {**asdict(selection), "patience": 8,
        "min_delta": 1e-4, "stop_reason": stop, "checkpoint_selection_independent": True})
    checkpoint_pass = False
    if registry.get("BEST") and expected:
        try:
            for role in ("BEST", "LAST"):
                payload = load_verified_checkpoint(registry[role], expected)
                del payload
            checkpoint_pass = True
        except Exception:
            failure = (failure or "") + "\n" + traceback.format_exc()
            stop = "FAILURE"
    for role, name in (("BEST", "best_checkpoint_identity.json"), ("LAST", "last_checkpoint_identity.json")):
        if not (out / name).exists():
            atomic_json(out / name, {"status": "NOT_AVAILABLE", "run_id": manifest["run_id"]})
    if not (out / "checkpoint_registry.json").exists():
        atomic_json(out / "checkpoint_registry.json", registry)
    # All 162 execute after actual training/failure; do not apply formal checkpoint states in tests.
    test_pass = False
    before = {r: sha256(Path(i["absolute_local_path"])) for r, i in registry.items() if r in ("BEST", "LAST") and i}
    try:
        run_tests(out, "post_training")
        after = {r: sha256(Path(i["absolute_local_path"])) for r, i in registry.items() if r in ("BEST", "LAST") and i}
        if before != after:
            raise ValueError("Regression tests modified a formal checkpoint")
        test_pass = True
    except Exception:
        failure = (failure or "") + "\n" + traceback.format_exc()
        stop = "FAILURE"
    try:
        preservation_pass = immutable_inventory() == manifest["baseline_files_disk_sha256"]
    except Exception:
        preservation_pass = False
        failure = (failure or "") + "\n" + traceback.format_exc()
    if not preservation_pass:
        failure = (failure or "") + "\nHistorical disk SHA mismatch"
        stop = "FAILURE"
    stage = STAGING_ROOT / ("formal_" + manifest["run_id"])
    residual = [str(p) for p in stage.rglob("*") if p.is_file()] if stage.exists() else []
    if residual:
        failure = (failure or "") + "\nStaging cleanup residual: " + repr(residual)
        stop = "FAILURE"
    atomic_json(out / "runtime_summary.json", {"run_id": manifest["run_id"], "wall_seconds": time.perf_counter()-started,
        "2025_PIXELS_READ": 0, "scope": SCOPE, "progress_at_stop": progress,
        "historical_files_preserved": preservation_pass, "staging_cleanup_residual_files": residual,
        "all_checkpoint_provenance_pass": checkpoint_pass, "post_training_test_checkpoint_hashes_unchanged": test_pass})
    complete = stop in ("MAX_EPOCHS", "EARLY_STOP") and checkpoint_pass and test_pass and preservation_pass and not residual
    final = {"run_id": manifest["run_id"], "FORMAL_TRAINING_AUTHORIZED": True,
        "B0_FORMAL_TRAINING_STARTED": (out / "training_start.json").exists(), "B0_PHASE_A_TRAINING_COMPLETED": complete,
        "TRAIN_SCENES": 11720, "VALIDATION_SCENES": 11727, "PROTOCOL_VERSION": "v1.0", "PRIMARY_SEED": 2026,
        "TOTAL_COMPLETED_EPOCHS": len(epochs), "STOP_REASON": stop,
        "SELECTED_CHECKPOINT_EPOCH": selection.selected_checkpoint_epoch or "NOT_AVAILABLE",
        "SELECTED_CHECKPOINT_VAL_CORE_LOSS": selection.best_checkpoint_value if selection.best_checkpoint_value is not None else "NOT_AVAILABLE",
        "BEST_CHECKPOINT_SHA256": registry.get("BEST", {}).get("sha256", "NOT_AVAILABLE") if registry.get("BEST") else "NOT_AVAILABLE",
        "LAST_CHECKPOINT_SHA256": registry.get("LAST", {}).get("sha256", "NOT_AVAILABLE") if registry.get("LAST") else "NOT_AVAILABLE",
        "POST_TRAINING_162_TESTS_PASS": test_pass, "2025_PIXELS_READ": 0,
        "PHASE_B_EXECUTED": False, "PHASE_B_NORMALIZATION_COMPUTED": False, "PHASE_B_AUTHORIZED": False,
        "B1_STARTED": False, "CHECKPOINT_BINARY_NOT_COMMITTED_TO_GIT": True, "finished_utc": now(),
        "all_checkpoint_provenance_pass": checkpoint_pass, "failure": failure}
    atomic_json(out / "final_status.json", final)
    atomic_json(out / "run_status.json", {**final, "state": "COMPLETED" if complete else "STOPPED_FAILURE"})
    report = ("# B0 Phase-A formal training report\n\n"
        f"Run `{manifest['run_id']}`; baseline `{BASELINE}`; scope `{SCOPE}`. "
        f"Completion: **{complete}**. Stop reason: **{stop}**. Completed epochs: **{len(epochs)}**.\n\n"
        "Researcher authorization is separate from the immutable historical protocol. B0 only, Protocol v1.0, "
        "seed 2026, 11720 frozen 2023 Train identities and 11727 frozen 2024 Validation identities. "
        "No 2025 sources, Phase-B, Phase-B normalization, B1–B8, calibration or threshold selection.\n\n"
        f"Formal training started: {final['B0_FORMAL_TRAINING_STARTED']}. Selected checkpoint epoch: "
        f"{final['SELECTED_CHECKPOINT_EPOCH']}; global Validation core loss: {final['SELECTED_CHECKPOINT_VAL_CORE_LOSS']}.\n\n"
        "Train uses batch 2, accumulation 1, AdamW (.9,.999), eps 1e-8, decay 1e-4 on Conv2d kernels only; "
        "BF16 forward, FP32 parameters/raw quantiles, float64 qlog/qphysical/pinball, no GradScaler. "
        "Every update checks finite outputs/loss/gradients/parameters/optimizer state, strict quantiles and determinism. "
        "LR uses the approved corrected expression base_lr*(u/W), unchanged 50-epoch horizon, no warmup clamp. "
        "Grad norm clips at 5. Train permutation uses independent Generator(2026+zero-based epoch). "
        "Any sample read, identity, QC or numerical failure stops; no sample skipping or automatic tuning.\n\n"
        "Global Train loss accumulates undivided production per-cell focal arithmetic promoted before summation "
        "and float64 pinball over the global valid denominator. Validation uses frozen float64 BCE/focal and "
        "pinball raw numerators with complete fixed-order population. Both avoid averaging batch means. "
        "Exact grouped AUROC/AP, per-tau pinball/coverage and DIAGNOSTIC_PROXY_METRIC are in each completed epoch JSON. "
        "POD/FAR/CSI remain THRESHOLD_NOT_FROZEN. The proxy is not E[R].\n\n"
        "Validation hashes lacking historical full-population pins are explicitly additional run-preflight byte identities; "
        "the frozen identity/order and eligibility manifests remain untouched. Historical spot-check hashes are compared. "
        "All source reads use one-file bounded SHA-verified English staging in independent ASCII worker roots. "
        "Copy/read seconds, temporary bytes and cleanup are in epoch I/O summaries. H and IMERG raw sources remain read-only.\n\n"
        "Only completed Train+Validation epochs can create BEST/LAST. Exact minimum chooses BEST; ties keep earliest. "
        "Early stopping independently requires improvement greater than 1e-4 with patience 8. "
        "Checkpoint write is temporary → fsync/close → round-trip/hash/provenance verification → atomic rename. "
        "New verified registry precedes old owned-file cleanup. Resume validates all provenance before applying states "
        "and starts the next whole epoch from LAST.\n\n"
        f"Checkpoint root: `{local}`. CHECKPOINT_BINARY_NOT_COMMITTED_TO_GIT=true. "
        f"BEST SHA256: `{final['BEST_CHECKPOINT_SHA256']}`; LAST SHA256: `{final['LAST_CHECKPOINT_SHA256']}`. "
        "Absolute paths, filenames, sizes and identities are in checkpoint_registry.json and BEST/LAST identity JSON.\n\n"
        f"Post-run current 162 tests actually executed and PASS: {test_pass}; provenance PASS: {checkpoint_pass}; "
        f"historical files preserved: {preservation_pass}. Additional formal guard tests also execute.\n\n"
        "Artifacts: formal_run_manifest.json, preflight.json, source_identity_preflight.csv, epoch_*.json, "
        "training_history.csv, validation_history.csv, early_stopping_summary.json, runtime_summary.json, "
        "test_results_post_training.txt and final_status.json. No completed epoch means the histories are empty, "
        "not fabricated, and no checkpoint is selected.\n\n"
        + ("Failure evidence:\n\n```text\n" + failure + "\n```\n\n" if failure else "")
        + "PHASE_B_AUTHORIZED=false. This run stops here for researcher review; it does not enter the next stage.\n")
    (out / "B0_PHASE_A_FORMAL_TRAINING_REPORT.md").write_text(report, encoding="utf-8", newline="\n")
    public_hashes = {p.name: sha256(p) for p in out.iterdir() if p.is_file() and p.name != "evidence_sha256.json"}
    atomic_json(out / "evidence_sha256.json", public_hashes)
    print("FINAL " + json.dumps(final, ensure_ascii=False), flush=True)


def execute(run_id, resume=False):
    out = PUBLIC_ROOT / run_id
    manifest = read(out / "formal_run_manifest.json")
    local = Path(manifest["local_checkpoint_directory"])
    started = time.perf_counter()
    selection, registry = ValidationSelection(), {"run_id": run_id, "BEST": None, "LAST": None, "CHECKPOINT_BINARY_NOT_COMMITTED_TO_GIT": True}
    expected = None
    progress = {"epoch": 0, "global_update_completed": 0, "phase": "PREFLIGHT"}
    failure, stop = None, "FAILURE"
    try:
        authorization = FormalAuthorization.load(manifest["authorization_manifest_sha256"])
        if sha256(ROOT / authorization.config["authorization_document"]) != manifest["authorization_document_sha256"]:
            raise ValueError("Authorization document mismatch")
        if immutable_inventory() != manifest["baseline_files_disk_sha256"]:
            raise ValueError("Historical disk provenance mismatch")
        for p, wanted in manifest["formal_implementation_sha256"].items():
            if sha256(ROOT / p) != wanted:
                raise ValueError("Formal implementation changed after run initialization")
        if (out / "final_status.json").exists():
            raise ValueError("Finalized run cannot be resumed or overwritten")
        protocol = load_protocol(expected_sha256=PROTOCOL_SHA)
        protocol_checks = assert_protocol(protocol)
        torch.set_num_threads(2)
        seed_reproducibility()
        assert_determinism()
        env = environment()
        populations, qc_identity = load_populations(protocol)
        mapping = load_sp04()
        mask_path = Path(protocol["identity"]["yunnan_mask"]["path"])
        yunnan = read_frozen_yunnan_mask(mask_path, mapping)
        normalization = read(ROOT / protocol["identity"]["phase_a_normalization_artifact"]["path"])
        if normalization["mean_K"] != MU or normalization["std_K"] != SIGMA or normalization["eligible_scene_count"] != 11720:
            raise ValueError("Frozen normalization values/population mismatch")
        if resume:
            source_check = read(out / "preflight.json")["source_identity"]
            source_rows = rows(out / "source_identity_preflight.csv")
            if sha256(out / "source_identity_preflight.csv") != source_check["source_identity_ledger_sha256"]:
                raise ValueError("Run source identity ledger changed")
            for (_, identities), role in zip(populations, ("Train", "Validation")):
                pinned = [r for r in source_rows if r["role"] == role]
                if len(pinned) != len(identities) or [r["sample_id"] for r in pinned] != [r["sample_id"] for r in identities]:
                    raise ValueError("Resume population order mismatch")
                for identity, old in zip(identities, pinned):
                    identity.update(b13_sha256=old["b13_sha256"], b13_bytes=int(old["b13_bytes"]))
        else:
            if (out / "training_start.json").exists():
                raise ValueError("Use explicit epoch-boundary resume after interruption")
            source_check = identity_preflight(out, populations)
            run_tests(out, "preflight")
            seed_reproducibility()  # Tests use fixtures; restore the exact seed before formal initialization.
        model = B0Model().cuda()
        raw = {}
        def capture_raw(_module, _input, output):
            raw["dtype"] = output.dtype
        model.heads.quantile.register_forward_hook(capture_raw)
        heads = head_pin(model)
        optimizer, group_evidence = adamw(model)
        expected = checkpoint_expected(manifest, protocol, group_evidence, env, source_check["source_identity_ledger_sha256"])
        stage = STAGING_ROOT / ("formal_" + run_id)
        datasets = [FormalDataset(records, identities, mapping, yunnan, mask_path, stage / role, authorization)
            for (records, identities), role in zip(populations, ("train", "validation"))]
        if resume:
            registry = read(out / "checkpoint_registry.json")
            payload = apply_verified_checkpoint(registry["LAST"], expected, model, optimizer)
            selection = ValidationSelection(payload["best_checkpoint_value"], payload["selected_checkpoint_epoch"],
                payload["early_stop_best"], payload["non_improvement_count"], payload["completed_epoch"])
            load_verified_checkpoint(registry["BEST"], expected)
            atomic_json(out / ("resume_" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S") + ".json"),
                {"resumed_utc": now(), "verified_LAST": registry["LAST"], "next_whole_epoch": selection.completed_epoch+1,
                "no_partial_epoch_state_used": True})
            del payload
        else:
            local.mkdir(parents=True, exist_ok=False)
            read_checks = []
            for role, dataset in zip(("Train", "Validation"), datasets):
                for index in (0, len(dataset)-1):
                    sample, detail = dataset[index]
                    batch = formal_batch([sample], [detail], authorization)
                    read_checks.append({"role": role, "index": index, **detail,
                        "normalized_tensor_sha256": state_digest(batch.x_b13), "status": "PASS",
                        "optimizer_updates": 0, "forward_executed": False})
                    del sample, batch
            atomic_json(out / "preflight.json", {"status": "PASS", "checked_utc": now(),
                "protocol": protocol_checks, "heads": heads, "parameter_groups": group_evidence,
                "source_identity": source_check, "QC_identity": qc_identity, "environment": env,
                "initial_model_state_sha256": state_digest(model.state_dict()), "checkpoint_expected": expected,
                "real_read_normalization_batch_checks": read_checks,
                "normalization_SHA": NORMALIZATION_SHA, "normalization_mu": MU, "normalization_sigma": SIGMA,
                "authorization_manifest_sha256": authorization.manifest_sha256,
                "historical_authorization_false_fields_preserved": True})
            atomic_json(out / "training_start.json", {"training_started_utc": now(), "run_id": run_id,
                "FORMAL_TRAINING_AUTHORIZED": True, "B0_FORMAL_TRAINING_STARTED": True, "scope": SCOPE,
                "all_preflight_pass": True})
        atomic_json(out / "run_status.json", {"run_id": run_id, "state": "TRAINING", "updated_utc": now(),
            "FORMAL_TRAINING_AUTHORIZED": True, "B0_FORMAL_TRAINING_STARTED": True, "scope": SCOPE})
        print("FORMAL_TRAINING_STARTED " + run_id, flush=True)
        for epoch in range(selection.completed_epoch+1, 51):
            began = time.perf_counter()
            train = train_epoch(out, local, model, optimizer, raw, datasets[0], authorization, epoch, progress)
            validation = validate_epoch(out, model, raw, datasets[1], authorization, epoch, progress)
            action = selection.update(epoch, validation["global_val_core_loss"])
            payload = make_payload(model, optimizer, expected, selection, epoch, validation)
            registry, checkpoint_action = save_checkpoint(local, out, payload, expected, registry, action["checkpoint_selected"])
            del payload
            evidence = {"epoch": epoch, "run_id": run_id, "scope": SCOPE, "train": train, "validation": validation,
                "wall_seconds": time.perf_counter()-began, "global_update_start": train["global_update_start"],
                "global_update_end": train["global_update_end"], "LR_start": train["LR_start"], "LR_end": train["LR_end"],
                "training_samples": train["samples"], "validation_samples": validation["samples"],
                "checkpoint_action": checkpoint_action, "best_epoch": selection.selected_checkpoint_epoch,
                "selection": asdict(selection), "checkpoint_identity": registry, "identity_SHA": expected,
                "completed_utc": now()}
            atomic_json(out / f"epoch_{epoch:03d}.json", evidence)
            print("EPOCH_COMPLETED " + json.dumps({"epoch": epoch, "global_val_core_loss": validation["global_val_core_loss"],
                "best_epoch": selection.selected_checkpoint_epoch, "early_stop_count": selection.non_improvement_count,
                "wall_seconds": evidence["wall_seconds"]}), flush=True)
            gc.collect()
            if action["stop"]:
                stop = "EARLY_STOP"
                break
        else:
            stop = "MAX_EPOCHS"
    except Exception:
        failure = traceback.format_exc()
        atomic_json(out / "failure_evidence.json", {"utc": now(), "stop_reason": "FAILURE", "traceback": failure,
            "progress": progress, "protocol_automatically_changed": False, "sample_skipped": False,
            "2025_PIXELS_READ": 0, "scope": SCOPE})
        print("STOP_FAILURE " + failure, flush=True)
    finally:
        finalize(out, local, manifest, expected, selection, registry, stop, failure, progress, started)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--initialize", action="store_true")
    parser.add_argument("--run-id")
    parser.add_argument("--resume", action="store_true")
    args = parser.parse_args()
    if args.initialize and not args.run_id and not args.resume:
        initialize()
    elif args.run_id and not args.initialize:
        execute(args.run_id, args.resume)
    else:
        parser.error("Use --initialize OR --run-id run_<UTC> [--resume]")
