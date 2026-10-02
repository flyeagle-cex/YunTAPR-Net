"""Locked B0 FinalFit execution and completed-epoch resume, independent of Phase-A state.

The checked-in release authorizes engineering preflight only. Formal execution requires
a separate researcher authorization with a SHA-pinned runner and implementation.
"""
from __future__ import annotations

import csv
from dataclasses import dataclass, fields
from datetime import timedelta
import json
import math
import os
from pathlib import Path
import random
import time
import uuid

import numpy as np
import torch
from torch.utils.data import Dataset, get_worker_info
import yaml

from yuntapr.contracts.loader import REPO_ROOT, sha256
from yuntapr.data.dataset_b0 import B0Dataset, B0Record
from yuntapr.data.sample_schema import utc
from yuntapr.data.staging import BoundedEnglishStaging, StagedB13Reader, StagedIMERGReader
from yuntapr.losses.total_loss import b0_core_loss
from yuntapr.models.b0 import B0Model
from yuntapr.training.batch_contract import B0Batch
from yuntapr.training.formal_phase_a import atomic_json, assert_determinism, precision_check, train_numerators
from yuntapr.training.phase_a_protocol import (
    adamw, capture_rng, head_pin, load_protocol, restore_rng, seed_reproducibility, state_digest,
)
from yuntapr.training.phase_b_preparation import (
    SCENES, STEPS, EPOCHS, UPDATES, INITIALIZATION, TAIL_POLICY, PhaseBNormalizer,
    batch_plan, finalfit_lr, validate_population,
)

SCOPE = "FORMAL_B0_PHASE_B_FINALFIT"
CONFIG = Path("config/training/b0_phase_b_finalfit_runner_v1.yaml")
PREPARATION_SHA = "9e73e88f33545f052724fdc3673b586d70dad5d3d87d127225e15a00480a3761"
NORMALIZATION_SHA = "c7042beac2412594ca9fc264d7df10981755b393158c539cb48c9b56cd314327"
MANIFEST_SHA = "00e6bd018eae6aeb05be0740b55a92b7a5cc9a44b9ab2b80affbad3e3282ccff"
PROTOCOL_SHA = "dcacbe34050da7e777ad0cb72c53b5b51b48ce57eb9260b09fd283d96de12a4a"
CHECKPOINT_ROOT = Path(r"F:\pytorch\Research\outputs\formal_training\b0_phase_b_finalfit")
HROOT = Path(r"H:\葵花202303_202510")
IROOT = Path(r"F:\云南极端降水数据\raw\IMERG")
STAGING = Path(r"F:\pytorch\Research\stage0_himawari\cache\staging")
LOCKS = {
    "PHASE_B_MODEL_INITIALIZATION": INITIALIZATION, "FINALFIT_SCENES": SCENES,
    "NORMALIZATION_SHA256": NORMALIZATION_SHA, "PHYSICAL_BATCH": 2, "DROP_LAST": False,
    "FINALFIT_TAIL_BATCH_POLICY": TAIL_POLICY, "STEPS_PER_EPOCH": STEPS,
    "FINALFIT_EPOCHS": EPOCHS, "TOTAL_UPDATES": UPDATES, "W": STEPS, "U": 586200,
    "early_stopping": False, "validation_selection": False, "epoch_reselection": False,
    "phase_a_state_allowed": False, "2025_access": False,
}


def implementation_hashes(root=REPO_ROOT):
    # Covers the complete production dependency code, including unchanged architecture,
    # readers, mapping, normalization, numerical heads, loss and scheduler utilities.
    paths = sorted(Path(root).joinpath("src/yuntapr").rglob("*.py"))
    paths.append(Path(root) / "scripts/train_b0_phase_b_finalfit_v1.py")
    return {p.relative_to(root).as_posix(): sha256(p) for p in paths}


@dataclass(frozen=True)
class RunnerContract:
    config_sha256: str
    config: dict
    protocol: dict
    preparation: dict
    normalizer: PhaseBNormalizer
    rows: list

    @classmethod
    def load(cls, root=REPO_ROOT):
        root = Path(root)
        path = root / CONFIG
        config = yaml.safe_load(path.read_text(encoding="utf-8"))
        for key, wanted in LOCKS.items():
            if config.get(key) != wanted or type(config.get(key)) is not type(wanted):
                raise ValueError("FinalFit locked configuration mismatch: " + key)
        if (config.get("PHASE_B_AUTHORIZED") is not False
                or config.get("PHASE_B_FORMAL_TRAINING_STARTED") is not False
                or config.get("checkpoint_root") != str(CHECKPOINT_ROOT)):
            raise ValueError("Runner release scope/root changed")
        prep_path = root / "config/training/phase_b_finalfit_preparation_v1.yaml"
        if sha256(prep_path) != PREPARATION_SHA:
            raise ValueError("Frozen preparation SHA mismatch")
        preparation = yaml.safe_load(prep_path.read_text(encoding="utf-8"))
        protocol = load_protocol(root, expected_sha256=PROTOCOL_SHA)
        for ref in (preparation["scientific_contract"], preparation["acceptance"]):
            if sha256(root / ref["path"]) != ref["sha256"]:
                raise ValueError("Scientific/acceptance identity changed")
        if (preparation["normalization"]["sha256"] != NORMALIZATION_SHA
                or preparation["finalfit_manifest"]["sha256"] != MANIFEST_SHA):
            raise ValueError("Frozen FinalFit identities changed")
        manifest = root / preparation["finalfit_manifest"]["path"]
        if sha256(manifest) != MANIFEST_SHA:
            raise ValueError("FinalFit manifest SHA mismatch")
        with manifest.open(encoding="utf-8", newline="") as stream:
            rows = list(csv.DictReader(stream))
        validate_population(rows)
        for row in rows:
            source_paths(row)  # Pure root/time guard before any raw data access.
        normalizer = PhaseBNormalizer.from_artifact(root / preparation["normalization"]["path"], NORMALIZATION_SHA)
        return cls(sha256(path), config, protocol, preparation, normalizer, rows)


def source_paths(row):
    t = utc(row["window_start"])
    if t.year not in (2023, 2024) or t.month not in range(3, 11):
        raise ValueError("Unauthorized FinalFit source time; 2025 access prohibited")
    h = (HROOT / row["b13_relative_path"]).resolve()
    i = Path(row["imerg_day_path"]).resolve()
    if (not h.is_relative_to(HROOT.resolve())
            or h.relative_to(HROOT.resolve()).parts[0] != t.strftime("%Y%m")
            or not i.is_relative_to((IROOT / str(t.year)).resolve())):
        raise ValueError("Frozen source root changed; no fallback")
    if (utc(row["expected_nominal"]) != t + timedelta(minutes=20)
            or utc(row["analysis_time"]) != t + timedelta(minutes=30)
            or utc(row["selected_obs_end"]) > utc(row["analysis_time"])
            or row["formal_supervised_qc_pass"] != "True"
            or row["used_older_causal_frame"] != "False"
            or int(row["imerg_valid_yunnan_count"]) != 3430
            or int(row["full_valid_native_pixels"]) != 251001
            or (row["imerg_product"], row["imerg_version"], row["imerg_run_type"]) != ("IMERG", "V07", "Final")):
        raise ValueError("Frozen time/QC/product identity changed")
    return h, i


def source_identity_preflight(contract):
    """Full original-source SHA verification before future authorized fit/resume."""
    if not HROOT.is_dir():
        raise FileNotFoundError("BLOCKED_SOURCE_DRIVE_UNAVAILABLE; original H root only")
    unique_imerg = {}
    verified = []
    for row in contract.rows:
        h, i = source_paths(row)
        if not h.is_file() or h.stat().st_size != int(row["b13_bytes"]) or sha256(h) != row["b13_sha256"]:
            raise ValueError("B13 original source identity mismatch: " + row["sample_id"])
        if str(i) not in unique_imerg:
            if not i.is_file() or sha256(i) != row["imerg_sha256"]:
                raise ValueError("IMERG original source SHA mismatch: " + str(i))
            unique_imerg[str(i)] = {"sha256": row["imerg_sha256"], "bytes": i.stat().st_size}
        if unique_imerg[str(i)]["sha256"] != row["imerg_sha256"]:
            raise ValueError("Conflicting IMERG source identity")
        verified.append((row["sample_id"], row["b13_sha256"], int(row["b13_bytes"]), row["imerg_sha256"]))
    return {"finalfit_manifest_sha256": MANIFEST_SHA, "b13_files_verified": len(verified),
        "imerg_days_verified": len(unique_imerg), "verified_source_digest": state_digest(verified),
        "imerg_identities": unique_imerg, "2025_PIXELS_READ": 0}


@dataclass(frozen=True)
class PhaseBAuthorization:
    sha256: str
    config: dict

    @classmethod
    def load(cls, path, expected_sha256, contract):
        if path is None or not expected_sha256:
            raise PermissionError("PHASE_B_AUTHORIZED=false; separate researcher authorization required")
        path = Path(path)
        if sha256(path) != expected_sha256:
            raise ValueError("Phase-B authorization SHA mismatch")
        value = yaml.safe_load(path.read_text(encoding="utf-8"))
        required = {"version": "v1", "AUTHORIZED_BY": "RESEARCHER",
            "AUTHORIZED_SCOPE": "B0_PHASE_B_FINALFIT_ONLY", "PHASE_B_AUTHORIZED": True,
            "PHASE_B_MODEL_INITIALIZATION": INITIALIZATION, "FINALFIT_EPOCHS": EPOCHS,
            "2025_access": False, "runner_config_sha256": contract.config_sha256,
            "NORMALIZATION_SHA256": NORMALIZATION_SHA, "manifest_sha256": MANIFEST_SHA,
            "checkpoint_root": str(CHECKPOINT_ROOT), "implementation_sha256": implementation_hashes()}
        for key, wanted in required.items():
            if value.get(key) != wanted:
                raise PermissionError("Phase-B authorization scope/provenance mismatch: " + key)
        return cls(expected_sha256, value)

    def require(self):
        if (self.config.get("AUTHORIZED_SCOPE") != "B0_PHASE_B_FINALFIT_ONLY"
                or self.config.get("PHASE_B_AUTHORIZED") is not True):
            raise PermissionError("Verified Phase-B authorization required")


class FinalFitDataset(Dataset):
    """Read only the pinned 2023/2024 manifest; no alternate frame/source search."""
    def __init__(self, contract, mapping, yunnan, mask_path, staging_root):
        self.contract, self.mapping, self.yunnan = contract, mapping, yunnan
        self.mask_path, self.staging_root = Path(mask_path), Path(staging_root)
        self.set_staging("main")

    def set_staging(self, suffix):
        self.staging = BoundedEnglishStaging(self.staging_root / suffix, 734003200, True, True)
        self.reader = StagedB13Reader(self.staging, self.mapping)
        self.ireader = StagedIMERGReader(self.staging, self.mapping)

    def __len__(self):
        return len(self.contract.rows)

    def __getitem__(self, index):
        row = self.contract.rows[index]
        h, i = source_paths(row)
        before = len(self.staging.records)
        x, valid, meta = self.reader(h, utc(row["expected_nominal"]))
        if meta.obs_end != utc(row["selected_obs_end"]):
            raise ValueError("Frozen Himawari observation identity changed")
        record = B0Record(row["sample_id"], utc(row["window_start"]), (meta,), i,
            int(row["imerg_index"]), "IMERG", "V07", "Final", True)
        def cached(path, nominal):
            if path != h or nominal != meta.nominal_time:
                raise ValueError("Unexpected cached source")
            return x, valid, meta
        assembler = B0Dataset([record], self.mapping, self.yunnan, cached, self.ireader,
            frozen_mask_path=self.mask_path, formal_supervised=True, normalizer=self.contract.normalizer)
        sample = assembler[0]
        ops = self.staging.records[before:]
        if (len(ops) != 2 or [r.source_sha256 for r in ops] != [row["b13_sha256"], row["imerg_sha256"]]
                or ops[0].temporary_bytes != int(row["b13_bytes"])
                or any(not r.cleanup_success or not r.size_match or not r.sha256_match for r in ops)
                or self.staging._owned or sample.sample_id != row["sample_id"]
                or int((sample.imerg_valid_mask & self.yunnan).sum()) != 3430
                or int(((sample.y_imerg > .1) & sample.imerg_valid_mask & self.yunnan).sum()) != int(row["imerg_rain_yunnan_count"])):
            raise ValueError("FinalFit source SHA/size/QC/cleanup mismatch")
        # Worker histories must stay bounded during eleven complete epochs.
        del self.staging.records[before:]
        return sample, {"index": index, "sample_id": sample.sample_id,
            "operations": [r.__dict__ for r in ops], "cleanup_success": True,
            "copy_seconds": sum(r.copy_seconds for r in ops), "read_seconds": sum(r.read_seconds for r in ops),
            "temporary_bytes_peak": max(r.temporary_bytes for r in ops)}


def worker_init(worker_id):
    torch.set_num_threads(1)
    seed = torch.initial_seed() % 2**32
    random.seed(seed)
    np.random.seed(seed)
    get_worker_info().dataset.set_staging(f"worker_{worker_id}")


def collate(items):
    return [s for s, _ in items], [d for _, d in items]


def fresh_model(device="cpu"):
    seed_reproducibility()
    model = B0Model().to(device)
    head_pin(model)
    if state_digest(model.state_dict()) != "57a4d103a31aa7be1a52af079cdf7fb81bc73c51ba3e0e97d395513d21d9023d":
        raise ValueError("Fresh seed-2026 initialization replay mismatch")
    return model


def prepare_batch(samples, details, authorization=None, *, engineering=False):
    if not engineering:
        if not isinstance(authorization, PhaseBAuthorization):
            raise PermissionError("Phase-B formal batch authorization required")
        authorization.require()
    if len(samples) not in (1, 2) or len(samples) != len(details):
        raise ValueError("Only physical batch2 or singleton tail is allowed")
    for s, d in zip(samples, details):
        t = utc(s.imerg_window_start)
        if (t.year not in (2023, 2024) or t.month not in range(3, 11)
                or s.sample_id != d["sample_id"] or not d["cleanup_success"]
                or s.normalization_artifact_sha256 != NORMALIZATION_SHA
                or s.normalization_mu != 270.5900486586461 or s.normalization_sigma != 20.368583874067266
                or int((s.imerg_valid_mask & s.yunnan_eval_mask).sum()) != 3430):
            raise ValueError("FinalFit batch provenance/denominator mismatch")
    batch = B0Batch.from_formal_samples(samples)
    if not engineering:
        batch.execution_scope = SCOPE
    for field in fields(batch):
        tensor = getattr(batch, field.name)
        if isinstance(tensor, torch.Tensor):
            setattr(batch, field.name, tensor.cuda())
    return batch


def forward_backward_clip(model, optimizer, batch, update, authorization=None, *, engineering=False):
    """Shared numerical preparation; the entrypoint owns the actual optimizer update.

    Preserves the historical no-optimizer-step-in-src contract. Engineering scheduler
    index is stateless and does not imply preceding parameter updates occurred.
    """
    if not engineering:
        if not isinstance(authorization, PhaseBAuthorization) or batch.execution_scope != SCOPE:
            raise PermissionError("Formal update requires verified Phase-B authorization")
        authorization.require()
    elif batch.execution_scope != "ENGINEERING_ONLY":
        raise ValueError("ENGINEERING_ONLY preflight required")
    if isinstance(update, bool) or not isinstance(update, int) or not 1 <= update <= UPDATES:
        raise ValueError("Update outside the locked eleven-epoch execution budget")
    assert_determinism()
    model.train()
    raw = {}
    def capture(_m, _i, output):
        raw["dtype"] = output.dtype
    hook = model.heads.quantile.register_forward_hook(capture)
    optimizer.zero_grad(set_to_none=True)
    lr = finalfit_lr(update)
    for group in optimizer.param_groups:
        group["lr"] = lr
    started = time.perf_counter()
    try:
        with torch.autocast("cuda", dtype=torch.bfloat16):
            output = model._evaluate(batch.x_b13, batch.b13_valid_mask, batch.b13_valid_mask.flatten(1).sum(-1))
            loss = b0_core_loss(output, batch.y_imerg, batch.imerg_valid_mask, batch.yunnan_eval_mask,
                focal_alpha=.5, focal_gamma=2., quantile_axis_reduction="mean")
            output.placeholder_policy = "FULL_VALID_NORMALIZED_NO_PLACEHOLDER"
            loss.execution_scope = "ENGINEERING_ONLY" if engineering else SCOPE
        precision_check(model, raw["dtype"], output)
        n = int((batch.imerg_valid_mask & batch.yunnan_eval_mask).sum())
        if (n != batch.x_b13.shape[0] * 3430 or loss.valid_supervised_count != n or loss.batch_skipped
                or loss.conditional_quantile.dtype != torch.float64
                or not all(bool(torch.isfinite(v)) for v in (loss.total, loss.occurrence, loss.conditional_quantile))):
            raise FloatingPointError("Actual batch denominator/finite loss contract failed")
        # Independently recompute the reduction to prove the real singleton path.
        with torch.no_grad(), torch.autocast("cuda", enabled=False):
            valid = batch.imerg_valid_mask & batch.yunnan_eval_mask
            rainy = batch.y_imerg > .1
            clean = torch.where(valid, batch.y_imerg, torch.zeros_like(batch.y_imerg)).double()
            logits = output.rain_logit.double()
            bce = torch.nn.functional.softplus(logits) - logits * rainy.double()
            occ_ref = (.5 * (1-torch.exp(-bce))**2 * bce * valid).sum() / n
            taus = ((torch.arange(1, 33, device=logits.device, dtype=torch.float64)-.5)/32).reshape(1, 32, 1, 1)
            err = torch.log1p(clean) - output.conditional_quantiles_log
            qr_ref = (torch.maximum(taus*err, (taus-1)*err).mean(1, keepdim=True) * (rainy & valid)).sum() / n
            occ_error = abs(float(loss.occurrence)-float(occ_ref))
            qr_error = abs(float(loss.conditional_quantile)-float(qr_ref))
            if occ_error > 1e-7 or qr_error > 1e-12:
                raise FloatingPointError("Independent actual-denominator reference failed")
        s_occ, s_qr, _, rainy_count = train_numerators(output, batch)
        loss.total.backward()
        parameters = list(model.parameters())
        if any(p.grad is None or not bool(torch.isfinite(p.grad).all()) for p in parameters):
            raise FloatingPointError("Missing/nonfinite FinalFit gradient")
        pre = float(torch.nn.utils.clip_grad_norm_(parameters, 5., norm_type=2., error_if_nonfinite=True, foreach=False))
        post = float(torch.linalg.vector_norm(torch.stack([torch.linalg.vector_norm(p.grad.detach(), 2) for p in parameters]), 2))
        if post > 5.00001:
            raise FloatingPointError("Global norm clip failed")
        return {"scope": "ENGINEERING_ONLY" if engineering else SCOPE, "scheduler_u": update,
            "LR": lr, "LR_hex": lr.hex(), "batch_size": batch.x_b13.shape[0], "valid_denominator": n,
            "loss": float(loss.total.detach()), "S_occ": s_occ, "S_qr": s_qr, "rainy_count": rainy_count,
            "occurrence_reference_abs_error": occ_error, "quantile_reference_abs_error": qr_error,
            "pre_clip_norm": pre, "post_clip_norm": post, "raw_quantile_dtype": str(raw["dtype"]),
            "qlog_dtype": str(output.conditional_quantiles_log.dtype), "pinball_dtype": str(loss.conditional_quantile.dtype),
            "forward_pass": True, "loss_pass": True, "backward_pass": True, "clip_pass": True,
            "wall_seconds": time.perf_counter()-started}
    finally:
        hook.remove()


class EpochCoverage:
    def __init__(self, epoch):
        if type(epoch) is not int or not 1 <= epoch <= EPOCHS:
            raise ValueError("Epoch outside frozen FinalFit budget")
        self.epoch = epoch
        permutation, _ = batch_plan(epoch-1)
        self.order = permutation.tolist()
        self.seen = self.updates = self.denominator = 0

    def add(self, indices, denominator):
        expected = self.order[self.seen:self.seen+2]
        if list(indices) != expected or not expected or denominator != len(expected)*3430:
            raise ValueError("Identity coverage/order/actual batch denominator mismatch")
        self.seen += len(expected)
        self.updates += 1
        self.denominator += denominator

    def complete(self):
        if self.seen != SCENES or self.updates != STEPS or self.denominator != SCENES*3430:
            raise ValueError("Only a fully completed epoch can produce a checkpoint")
        return {"samples": self.seen, "updates": self.updates, "denominator": self.denominator,
            "permutation_sha256": state_digest(torch.tensor(self.order, dtype=torch.int64)),
            "identities_exactly_once": True, "tail_batch_size": 1, "tail_denominator": 3430}


def checkpoint_expected(contract, authorization, run_id, environment, groups, source):
    authorization.require()
    return {"scope": SCOPE, "checkpoint_kind": "FINALFIT_COMPLETED_EPOCH", "run_id": run_id,
        "PHASE_B_AUTHORIZED": True, "EPOCH_BOUNDARY_RESUME_ONLY": True, **LOCKS,
        "runner_config_sha256": contract.config_sha256, "protocol_sha256": PROTOCOL_SHA,
        "finalfit_manifest_sha256": MANIFEST_SHA, "normalization_artifact_sha256": NORMALIZATION_SHA,
        "scientific_contract_sha256": contract.preparation["scientific_contract"]["sha256"],
        "identity_sha256": {k: r["sha256"] for k, r in contract.protocol["identity"].items()
                            if k != "phase_a_normalization_artifact"},
        "authorization_sha256": authorization.sha256, "implementation_sha256": implementation_hashes(),
        "source_identity_preflight_sha256": state_digest(source), "optimizer_config": contract.protocol["optimizer"],
        "parameter_groups": groups, "environment": environment, "seed": 2026, "AMP_mode": "BF16",
        "gradient_accumulation": 1, "gradient_clip_norm": 5., "focal_alpha": .5, "focal_gamma": 2.,
        "base_lr": 1e-4, "min_lr": 1e-6, "2025_PIXELS_READ": 0}


def make_payload(model, optimizer, expected, epoch, coverage, metrics):
    receipt = coverage.complete()
    if coverage.epoch != epoch:
        raise ValueError("Completed epoch coverage mismatch")
    rng = capture_rng()
    payload = {**expected, "completed_epoch": epoch, "global_update": epoch*STEPS,
        "epoch_completed": True, "coverage": receipt, "training_metrics": metrics,
        "last_applied_lr": finalfit_lr(epoch*STEPS), "model_state_dict": model.state_dict(),
        "optimizer_state_dict": optimizer.state_dict(), "rng_states": rng,
        "model_state_dict_sha256": state_digest(model.state_dict()),
        "optimizer_state_dict_sha256": state_digest(optimizer.state_dict()), "rng_states_sha256": state_digest(rng)}
    validate_payload(payload, expected)
    compatible_states(payload, model, optimizer)
    return payload


def validate_payload(payload, expected):
    # No state is applied until ALL provenance and structural checks have completed.
    for key, wanted in expected.items():
        if payload.get(key) != wanted:
            raise ValueError("FinalFit checkpoint provenance mismatch: " + key)
    if (payload.get("scope") != SCOPE or payload.get("checkpoint_kind") != "FINALFIT_COMPLETED_EPOCH"
            or payload.get("PHASE_B_AUTHORIZED") is not True or payload.get("EPOCH_BOUNDARY_RESUME_ONLY") is not True
            or payload.get("epoch_completed") is not True or type(payload.get("completed_epoch")) is not int
            or not 1 <= payload["completed_epoch"] <= EPOCHS
            or payload.get("global_update") != payload["completed_epoch"]*STEPS
            or payload.get("last_applied_lr") != finalfit_lr(payload["global_update"])):
        raise ValueError("FinalFit checkpoint must be a completed epoch boundary")
    if any(k in payload for k in ("BEST", "selected_checkpoint_epoch", "best_checkpoint_value", "early_stop_best", "validation_completed", "scheduler_state_dict")):
        raise ValueError("Phase-A selection/scheduler state prohibited in FinalFit")
    permutation, _ = batch_plan(payload["completed_epoch"]-1)
    coverage = {"samples": SCENES, "updates": STEPS, "denominator": SCENES*3430,
        "permutation_sha256": state_digest(permutation), "identities_exactly_once": True,
        "tail_batch_size": 1, "tail_denominator": 3430}
    if payload.get("coverage") != coverage:
        raise ValueError("Completed epoch identity coverage mismatch")
    for name in ("model_state_dict", "optimizer_state_dict", "rng_states"):
        if name not in payload or state_digest(payload[name]) != payload.get(name+"_sha256"):
            raise ValueError("FinalFit checkpoint state checksum mismatch: " + name)
    def finite(value):
        if isinstance(value, torch.Tensor) and not bool(torch.isfinite(value).all()):
            raise ValueError("Nonfinite checkpoint tensor")
        if isinstance(value, float) and not math.isfinite(value):
            raise ValueError("Nonfinite checkpoint scalar")
        if isinstance(value, dict):
            for child in value.values(): finite(child)
        if isinstance(value, (list, tuple)):
            for child in value: finite(child)
    finite(payload["model_state_dict"])
    finite(payload["optimizer_state_dict"])
    finite(payload["training_metrics"])
    rng = payload["rng_states"]
    # Validate RNG compatibility with independent generators, before global mutation.
    random.Random().setstate(rng["python"])
    np.random.RandomState().set_state(rng["numpy"])
    torch.Generator().set_state(rng["torch_cpu"].cpu())
    if len(rng["torch_cuda"]) != torch.cuda.device_count():
        raise ValueError("Checkpoint CUDA RNG device count mismatch")
    for index, state in enumerate(rng["torch_cuda"]):
        torch.Generator(device=f"cuda:{index}").set_state(state.cpu())
    return rng


def compatible_states(payload, model, optimizer):
    candidate = payload["model_state_dict"]
    if candidate.keys() != model.state_dict().keys():
        raise ValueError("Checkpoint model keys mismatch")
    for name, tensor in model.state_dict().items():
        if candidate[name].shape != tensor.shape or candidate[name].dtype != tensor.dtype:
            raise ValueError("Checkpoint model shape/dtype mismatch")
    incoming = payload["optimizer_state_dict"]
    current = optimizer.state_dict()
    if len(incoming["param_groups"]) != len(current["param_groups"]):
        raise ValueError("Checkpoint optimizer groups mismatch")
    identifiers = []
    for old, new, live in zip(incoming["param_groups"], current["param_groups"], optimizer.param_groups):
        if old.keys() != new.keys() or len(old["params"]) != len(new["params"]):
            raise ValueError("Checkpoint optimizer group schema mismatch")
        for key in new:
            wanted = payload["last_applied_lr"] if key == "lr" else new[key]
            if key != "params" and old[key] != wanted:
                raise ValueError("Checkpoint optimizer hyperparameter mismatch: " + key)
        for identifier, parameter in zip(old["params"], live["params"]):
            identifiers.append(identifier)
            state = incoming["state"].get(identifier)
            if not state or set(state) != {"step", "exp_avg", "exp_avg_sq"}:
                raise ValueError("Incomplete AdamW parameter state")
            if state["step"].numel() != 1 or float(state["step"]) != payload["global_update"]:
                raise ValueError("AdamW step inconsistent with completed epoch")
            for key in ("exp_avg", "exp_avg_sq"):
                if state[key].shape != parameter.shape or state[key].dtype != parameter.dtype:
                    raise ValueError("Checkpoint optimizer moment shape/dtype mismatch")
    if len(set(identifiers)) != len(identifiers) or set(identifiers) != set(incoming["state"]):
        raise ValueError("Checkpoint optimizer parameter coverage mismatch")


def load_verified_checkpoint(identity, expected):
    path = Path(identity["absolute_local_path"]).resolve()
    if (not path.is_relative_to(CHECKPOINT_ROOT.resolve()) or path.parent.name != expected["run_id"]
            or path.name != f'epoch_{identity["epoch"]:03d}.pt'
            or path.stat().st_size != identity["bytes"] or sha256(path) != identity["sha256"]):
        raise ValueError("FinalFit checkpoint file identity mismatch")
    payload = torch.load(path, map_location="cpu", weights_only=False)
    validate_payload(payload, expected)
    if identity["epoch"] != payload["completed_epoch"] or identity["global_update"] != payload["global_update"]:
        raise ValueError("Registry/checkpoint boundary mismatch")
    return payload


def apply_verified_checkpoint(identity, expected, model, optimizer):
    payload = load_verified_checkpoint(identity, expected)
    compatible_states(payload, model, optimizer)
    model.load_state_dict(payload["model_state_dict"], strict=True)
    optimizer.load_state_dict(payload["optimizer_state_dict"])
    restore_rng(payload["rng_states"])
    return payload


def save_checkpoint(local, public, payload, expected, registry):
    local, public = Path(local).resolve(), Path(public).resolve()
    if not local.is_relative_to(CHECKPOINT_ROOT.resolve()) or local.name != expected["run_id"]:
        raise ValueError("Checkpoint directory outside approved Phase-B run root")
    validate_payload(payload, expected)
    epoch = payload["completed_epoch"]
    last = registry.get("LAST")
    if "BEST" in registry or registry.get("FINAL") or epoch != (last["epoch"]+1 if last else 1):
        raise ValueError("Only monotonic completed epochs with LAST/FINAL semantics are allowed")
    destination = local / f"epoch_{epoch:03d}.pt"
    if destination.exists():
        raise FileExistsError("Completed checkpoint cannot be silently overwritten")
    temporary = local / (destination.name+".tmp_"+uuid.uuid4().hex)
    try:
        with temporary.open("xb") as stream:
            torch.save(payload, stream)
            stream.flush()
            os.fsync(stream.fileno())
        digest = sha256(temporary)
        probe = torch.load(temporary, map_location="cpu", weights_only=False)
        validate_payload(probe, expected)
        if state_digest(probe) != state_digest(payload) or sha256(temporary) != digest:
            raise ValueError("Checkpoint atomic round-trip mismatch")
        del probe
        os.replace(temporary, destination)
    finally:
        if temporary.exists(): temporary.unlink()  # This function's own temporary only.
    identity = {"absolute_local_path": str(destination), "filename": destination.name,
        "bytes": destination.stat().st_size, "sha256": digest, "epoch": epoch,
        "global_update": epoch*STEPS, "authorization_sha256": expected["authorization_sha256"],
        "checkpoint_kind": "FINALFIT_COMPLETED_EPOCH", "CHECKPOINT_BINARY_NOT_COMMITTED_TO_GIT": True}
    if sha256(destination) != identity["sha256"]:
        raise ValueError("Checkpoint SHA changed after rename")
    new = {"run_id": local.name, "LAST": identity, "FINAL": identity if epoch == EPOCHS else None,
        "CHECKPOINT_BINARY_NOT_COMMITTED_TO_GIT": True}
    atomic_json(public / "checkpoint_registry.json", new)
    atomic_json(public / "last_checkpoint_identity.json", identity)
    if new["FINAL"]:
        atomic_json(public / "final_checkpoint_identity.json", identity)
    # Older completed checkpoints are retained locally. No deletion of existing payloads.
    return new
