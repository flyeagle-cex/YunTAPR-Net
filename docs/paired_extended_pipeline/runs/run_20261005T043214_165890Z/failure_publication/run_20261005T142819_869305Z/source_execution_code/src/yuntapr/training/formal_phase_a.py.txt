"""Run-authorized B0 Phase-A execution; historical engineering guards stay intact."""
from __future__ import annotations

from dataclasses import dataclass, replace, fields
from datetime import timedelta
import hashlib
import json
import math
import os
from pathlib import Path
import random
import uuid

import numpy as np
import torch
import torch.nn.functional as F
import yaml
from torch.utils.data import Dataset, get_worker_info

from yuntapr.contracts.loader import REPO_ROOT, sha256
from yuntapr.data.dataset_b0 import B0Dataset
from yuntapr.data.normalization import PhaseANormalizer
from yuntapr.data.sample_schema import utc
from yuntapr.data.staging import BoundedEnglishStaging, StagedB13Reader, StagedIMERGReader
from yuntapr.losses.total_loss import b0_core_loss
from yuntapr.training.batch_contract import B0Batch
from yuntapr.training.phase_a_protocol import capture_rng, restore_rng, state_digest

SCOPE = "FORMAL_SCIENTIFIC_RUN"
AUTH_PATH = Path("config/training/b0_phase_a_formal_authorization_v1.yaml")
CHECKPOINT_ROOT = Path(r"F:\pytorch\Research\outputs\formal_training\b0_phase_a")
NORMALIZATION_SHA = "4bcfa0520550e343dd154fd4436715a306c015a02d16ec4a12bb2ed3cf606e0e"
MU, SIGMA = 271.7078191073734, 19.896814653342556


def atomic_json(path, value):
    """Replace only a named mutable artifact belonging to this run."""
    path = Path(path)
    temporary = path.with_name(path.name + ".tmp_" + uuid.uuid4().hex)
    with temporary.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(value, stream, indent=2, ensure_ascii=False, allow_nan=False, default=str)
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, path)


@dataclass(frozen=True)
class FormalAuthorization:
    manifest_sha256: str
    config: dict

    @classmethod
    def load(cls, expected_sha256, root=REPO_ROOT):
        path = Path(root) / AUTH_PATH
        if sha256(path) != expected_sha256:
            raise ValueError("Formal authorization SHA mismatch")
        config = yaml.safe_load(path.read_text(encoding="utf-8"))
        for key, value in {"AUTHORIZED_BY": "RESEARCHER", "AUTHORIZED_SCOPE": "B0_PHASE_A_ONLY",
                "FORMAL_TRAINING_AUTHORIZED": True, "B0_FORMAL_TRAINING_STARTED": False,
                "PHASE_B_AUTHORIZED": False, "B1_TO_B8_AUTHORIZED": False,
                "seed": 2026, "protocol_version": "v1.0", "train_count": 11720,
                "validation_count": 11727, "train_year": 2023, "validation_year": 2024,
                "months": list(range(3, 11)), "version": "v1",
                "baseline_commit": "aa65a5b4b33f04d7adddd1ca832963dcb21e4487",
                "FORMAL_CHECKPOINT_ROOT": str(CHECKPOINT_ROOT)}.items():
            if config.get(key) != value:
                raise ValueError("Formal authorization scope mismatch: " + key)
        for name, reference in config["identity"].items():
            source = Path(reference["path"])
            source = source if source.is_absolute() else Path(root) / source
            if sha256(source) != reference["sha256"]:
                raise ValueError("Formal authorization identity mismatch: " + name)
        return cls(expected_sha256, config)


def assert_determinism():
    if (os.environ.get("PYTHONHASHSEED") != "2026"
            or os.environ.get("CUBLAS_WORKSPACE_CONFIG") != ":4096:8"
            or not torch.are_deterministic_algorithms_enabled()
            or torch.is_deterministic_algorithms_warn_only_enabled()
            or not torch.backends.cudnn.deterministic or torch.backends.cudnn.benchmark
            or torch.backends.cuda.matmul.allow_tf32 or torch.backends.cudnn.allow_tf32
            or torch.get_float32_matmul_precision() != "highest"):
        raise RuntimeError("Formal deterministic configuration became invalid")


def guard_record(record):
    start = utc(record.imerg_window_start)
    if start.year not in (2023, 2024) or start.month not in range(3, 11):
        raise ValueError("Unauthorized source year/month; 2025 access prohibited")
    if len(record.frames) != 1 or record.imerg_path is None:
        raise ValueError("Frozen single-frame supervised identity required")
    frame = record.frames[0]
    nominal = utc(frame.nominal_time)
    if nominal != start + timedelta(minutes=20) or utc(frame.obs_end) > start + timedelta(minutes=30):
        raise ValueError("Frozen causal identity mismatch")
    # Validate resolved roots BEFORE any source read; never browse another data role.
    b13_root = Path(r"H:\葵花202303_202510").resolve()
    imerg_root = Path(r"F:\云南极端降水数据\raw\IMERG") / str(start.year)
    if not frame.path.resolve().is_relative_to(b13_root) or not record.imerg_path.resolve().is_relative_to(imerg_root.resolve()):
        raise ValueError("Source path outside authorized read-only roots")
    if frame.path.resolve().relative_to(b13_root).parts[0] != f"{start.year}{start.month:02d}":
        raise ValueError("B13 source month differs from authorized sample role")
    if not record.imerg_provenance_verified or (record.imerg_product, record.imerg_version, record.imerg_run_type) != ("IMERG", "V07", "Final"):
        raise ValueError("Frozen IMERG Final provenance required")


class FormalDataset(Dataset):
    def __init__(self, records, identities, mapping, yunnan, mask_path, stage_root, authorization):
        if not isinstance(authorization, FormalAuthorization):
            raise ValueError("Explicit verified formal authorization required")
        if len(records) != len(identities):
            raise ValueError("Source identity population mismatch")
        for record in records:
            guard_record(record)
        self.records, self.identities = records, identities
        self.mapping, self.yunnan, self.mask_path = mapping, yunnan, mask_path
        self.stage_root, self.authorization = stage_root, authorization
        self.normalizer = PhaseANormalizer.from_pinned()
        self.set_staging("main")

    def set_staging(self, suffix):
        self.staging = BoundedEnglishStaging(self.stage_root / suffix, 734003200, True, True)
        self.dataset = B0Dataset(self.records, self.mapping, self.yunnan,
            StagedB13Reader(self.staging, self.mapping), StagedIMERGReader(self.staging, self.mapping),
            frozen_mask_path=self.mask_path, formal_supervised=True, normalizer=self.normalizer)

    def __len__(self):
        return len(self.records)

    def __getitem__(self, index):
        guard_record(self.records[index])
        before = len(self.staging.records)
        sample = self.dataset[index]
        staged = self.staging.records[before:]
        expected = self.identities[index]
        if len(staged) != 2 or [r.source_sha256 for r in staged] != [expected["b13_sha256"], expected["imerg_sha256"]]:
            raise ValueError("Frozen source SHA mismatch")
        if any(not r.cleanup_success or not r.sha256_match for r in staged) or self.staging._owned:
            raise RuntimeError("Staging integrity or owned-file cleanup failure")
        if (sample.sample_id != expected["sample_id"] or not sample.formal_supervised_qc_pass
                or not sample.b13_full_valid or sample.used_older_causal_frame
                or sample.normalization_artifact_sha256 != NORMALIZATION_SHA
                or sample.normalization_mu != MU or sample.normalization_sigma != SIGMA):
            raise ValueError("Frozen QC or normalization identity mismatch")
        valid = sample.imerg_valid_mask & sample.yunnan_eval_mask
        if (int(valid.sum()) != int(expected["imerg_valid_yunnan_count"])
                or int(((sample.y_imerg > .1) & valid).sum()) != int(expected["imerg_rain_yunnan_count"])):
            raise ValueError("Runtime supervised QC counts changed from frozen identity")
        sample = replace(sample, execution_scope=SCOPE, eligibility_scope=SCOPE)
        detail = {"sample_id": sample.sample_id, "index": index,
            "authorization_manifest_sha256": self.authorization.manifest_sha256,
            "copy_seconds": sum(r.copy_seconds for r in staged),
            "read_seconds": sum(r.read_seconds for r in staged),
            "temporary_bytes_peak": max(r.temporary_bytes for r in staged), "cleanup_success": True,
            "b13_sha256": staged[0].source_sha256, "imerg_sha256": staged[1].source_sha256}
        return sample, detail


def formal_worker_init(worker_id):
    torch.set_num_threads(1)
    seed = torch.initial_seed() % (2 ** 32)
    random.seed(seed)
    np.random.seed(seed)
    get_worker_info().dataset.set_staging(f"worker_{worker_id}")


def formal_collate(items):
    return [item[0] for item in items], [item[1] for item in items]


def formal_batch(samples, details, authorization):
    if (not isinstance(authorization, FormalAuthorization) or not samples or len(samples) != len(details)
            or any(d["authorization_manifest_sha256"] != authorization.manifest_sha256 for d in details)):
        raise ValueError("Unverified formal batch authorization")
    def tensor(name):
        return torch.from_numpy(np.stack([getattr(s, name) for s in samples])[:, None].copy())
    batch = B0Batch(tensor("x_b13_normalized"), tensor("b13_valid_mask"), tensor("y_imerg"),
        tensor("imerg_valid_mask"), tensor("yunnan_eval_mask"), execution_scope=SCOPE, formal_samples=tuple(samples))
    batch.validate()
    if not bool(batch.b13_valid_mask.all()) or not bool(torch.isfinite(batch.x_b13).all()):
        raise ValueError("Formal input must be full-valid finite normalized frame")
    for i, (sample, detail) in enumerate(zip(samples, details)):
        if (sample.execution_scope != SCOPE or sample.eligibility_scope != SCOPE
                or sample.sample_id != detail["sample_id"] or not sample.supervised_eligible
                or not sample.formal_supervised_qc_pass or not sample.b13_full_valid
                or not sample.expected_latest_available or sample.used_older_causal_frame
                or sample.expected_latest_slot != utc(sample.analysis_time) - timedelta(minutes=10)
                or utc(sample.himawari_nominal_time) != sample.expected_latest_slot
                or utc(sample.himawari_obs_end) > utc(sample.analysis_time)
                or utc(sample.imerg_window_start).year not in (2023, 2024)
                or sample.normalization_artifact_sha256 != NORMALIZATION_SHA
                or sample.normalization_mu != MU or sample.normalization_sigma != SIGMA):
            raise ValueError("Formal batch causal/QC/normalization provenance mismatch")
        expected = ((sample.x_b13.astype(np.float64) - MU) / SIGMA).astype(np.float32)
        if not np.isfinite(expected).all() or not torch.equal(batch.x_b13[i, 0], torch.from_numpy(expected)):
            raise ValueError("Formal backbone input normalization differs from pinned artifact")
        if not bool((batch.imerg_valid_mask[i] & batch.yunnan_eval_mask[i]).any()):
            raise ValueError("Formal sample has no valid supervision; sample skipping prohibited")
    for field in fields(batch):
        value = getattr(batch, field.name)
        if isinstance(value, torch.Tensor):
            setattr(batch, field.name, value.cuda())
    return batch


def formal_forward(model, batch, authorization):
    if not isinstance(authorization, FormalAuthorization) or batch.execution_scope != SCOPE:
        raise ValueError("Formal forward requires verified researcher authorization")
    assert_determinism()
    # Reuse the frozen architecture unchanged; the old ENGINEERING_ONLY entry is not relaxed.
    output = model._evaluate(batch.x_b13, batch.b13_valid_mask, batch.b13_valid_mask.flatten(1).sum(-1))
    output.placeholder_policy = "FORMAL_FULL_VALID_NORMALIZED_NO_PLACEHOLDER"
    return output


def precision_check(model, raw_dtype, output, loss=None):
    q, physical = output.conditional_quantiles_log, output.conditional_quantiles_physical
    tensors = [getattr(output, f.name) for f in fields(output) if isinstance(getattr(output, f.name), torch.Tensor)]
    if (any(p.dtype != torch.float32 for p in model.parameters()) or raw_dtype != torch.float32
            or q.dtype != torch.float64 or physical.dtype != torch.float64
            or not all(bool(torch.isfinite(t).all()) for t in tensors)
            or not bool((q[:, 0] > math.log1p(.1)).all())
            or not bool((q[:, 1:] > q[:, :-1]).all())
            or not bool((physical[:, 1:] > physical[:, :-1]).all())):
        raise FloatingPointError("Formal quantile precision/strictness/finite contract failed")
    if loss is not None and (loss.execution_scope != SCOPE or loss.batch_skipped
            or loss.conditional_quantile.dtype != torch.float64
            or not all(bool(torch.isfinite(v)) for v in (loss.total, loss.occurrence, loss.conditional_quantile))):
        raise FloatingPointError("Formal core loss precision/finite contract failed")


def formal_loss(output, batch):
    loss = b0_core_loss(output, batch.y_imerg, batch.imerg_valid_mask, batch.yunnan_eval_mask,
        focal_alpha=.5, focal_gamma=2., quantile_axis_reduction="mean")
    loss.execution_scope = SCOPE
    return loss


@torch.no_grad()
def train_numerators(output, batch):
    """Undivided production per-cell arithmetic promoted BEFORE global accumulation."""
    valid = batch.imerg_valid_mask & batch.yunnan_eval_mask
    rainy = batch.y_imerg > .1
    # Same FP32 focal per-cell arithmetic and autocast policy as the gradient loss.
    with torch.autocast("cuda", dtype=torch.bfloat16):
        bce = F.binary_cross_entropy_with_logits(output.rain_logit, rainy.to(output.rain_logit.dtype), reduction="none")
        focal = .5 * (1 - torch.exp(-bce)).pow(2.) * bce
    with torch.autocast("cuda", enabled=False):
        q = output.conditional_quantiles_log.movedim(1, -1)[valid.squeeze(1)]
        rates = batch.y_imerg[valid].double()
        positive = batch.y_imerg[valid] > .1
        tau = (torch.arange(1, 33, dtype=torch.float64, device=q.device) - .5) / 32
        error = torch.log1p(rates[positive])[:, None] - q[positive]
        pinball = torch.maximum(tau * error, (tau - 1) * error)
        return float(focal[valid].sum(dtype=torch.float64)), float(pinball.mean(-1).sum(dtype=torch.float64)), int(valid.sum()), int(positive.sum())


def validate_payload(payload, expected):
    """Validate all provenance and complete-epoch state BEFORE applying any state."""
    for key, value in expected.items():
        if payload.get(key) != value:
            raise ValueError("Formal checkpoint provenance mismatch: " + key)
    if (payload.get("scope") != SCOPE or payload.get("FORMAL_TRAINING_AUTHORIZED") is not True
            or payload.get("EPOCH_BOUNDARY_RESUME_ONLY") is not True
            or payload.get("validation_completed") is not True
            or not isinstance(payload.get("completed_epoch"), int)
            or not 1 <= payload["completed_epoch"] <= 50
            or payload.get("global_update") != payload["completed_epoch"] * 5860
            or payload.get("training_samples") != 11720 or payload.get("validation_samples") != 11727):
        raise ValueError("Formal checkpoint must represent a completed Train + Validation epoch")
    if not 1 <= payload["selected_checkpoint_epoch"] <= payload["completed_epoch"]:
        raise ValueError("Invalid checkpoint selection state")
    if any(not math.isfinite(payload[k]) for k in ("best_checkpoint_value", "early_stop_best", "global_val_core_loss")):
        raise ValueError("Nonfinite checkpoint metric")
    for name in ("model_state_dict", "optimizer_state_dict"):
        if state_digest(payload[name]) != payload[name + "_sha256"]:
            raise ValueError("Formal checkpoint state checksum mismatch: " + name)
    rng = {"python": payload["python_rng_state"], "numpy": payload["numpy_rng_state"],
        "torch_cpu": payload["torch_cpu_rng_state"], "torch_cuda": payload["torch_cuda_rng_state"]}
    if state_digest(rng) != payload["rng_states_sha256"]:
        raise ValueError("Formal checkpoint RNG checksum mismatch")
    def finite(value):
        if isinstance(value, torch.Tensor) and not bool(torch.isfinite(value).all()):
            raise ValueError("Nonfinite formal checkpoint tensor")
        if isinstance(value, dict):
            for child in value.values():
                finite(child)
        if isinstance(value, (tuple, list)):
            for child in value:
                finite(child)
    finite(payload["model_state_dict"])
    finite(payload["optimizer_state_dict"])
    return rng


def load_verified_checkpoint(identity, expected):
    path = Path(identity["absolute_local_path"]).resolve()
    if not path.is_relative_to(CHECKPOINT_ROOT.resolve()) or path.stat().st_size != identity["bytes"] or sha256(path) != identity["sha256"]:
        raise ValueError("Formal checkpoint file identity mismatch")
    payload = torch.load(path, map_location="cpu", weights_only=False)
    validate_payload(payload, expected)
    return payload


def apply_verified_checkpoint(identity, expected, model, optimizer):
    payload = load_verified_checkpoint(identity, expected)
    # Strict compatibility preflight occurs without mutating the receiving model/optimizer.
    if set(payload["model_state_dict"]) != set(model.state_dict()):
        raise ValueError("Formal checkpoint model keys mismatch")
    for name, tensor in model.state_dict().items():
        candidate = payload["model_state_dict"][name]
        if candidate.shape != tensor.shape or candidate.dtype != tensor.dtype:
            raise ValueError("Formal checkpoint model shape/dtype mismatch")
    if len(payload["optimizer_state_dict"]["param_groups"]) != len(optimizer.param_groups):
        raise ValueError("Formal checkpoint optimizer groups mismatch")
    model.load_state_dict(payload["model_state_dict"], strict=True)
    optimizer.load_state_dict(payload["optimizer_state_dict"])
    restore_rng(validate_payload(payload, expected))
    return payload


def save_checkpoint(local, public, payload, expected, registry, selected):
    local = Path(local).resolve()
    if not local.is_relative_to(CHECKPOINT_ROOT.resolve()):
        raise ValueError("Formal checkpoint directory outside researcher-approved root")
    epoch = payload["completed_epoch"]
    destination = local / f"epoch_{epoch:03d}.pt"
    temporary = local / (destination.name + ".tmp_" + uuid.uuid4().hex)
    if destination.exists():
        raise FileExistsError("Completed checkpoint cannot be silently overwritten")
    with temporary.open("xb") as stream:
        torch.save(payload, stream)
        stream.flush()
        os.fsync(stream.fileno())
    digest = sha256(temporary)
    probe = torch.load(temporary, map_location="cpu", weights_only=False)
    validate_payload(probe, expected)
    if state_digest(probe) != state_digest(payload) or sha256(temporary) != digest:
        raise ValueError("Atomic checkpoint round-trip verification failed")
    del probe
    os.replace(temporary, destination)
    if sha256(destination) != digest:
        raise ValueError("Checkpoint hash changed after atomic rename")
    identity = {"absolute_local_path": str(destination), "filename": destination.name,
        "bytes": destination.stat().st_size, "sha256": digest, "epoch": epoch,
        "global_update": payload["global_update"], "global_val_core_loss": payload["global_val_core_loss"],
        "authorization_manifest_sha256": payload["authorization_manifest_sha256"],
        "CHECKPOINT_BINARY_NOT_COMMITTED_TO_GIT": True}
    new_registry = {"run_id": local.name, "BEST": identity if selected else registry["BEST"],
        "LAST": identity, "CHECKPOINT_BINARY_NOT_COMMITTED_TO_GIT": True}
    # New verified LAST/BEST and registry are durable before any old owned payload is removed.
    atomic_json(public / "checkpoint_registry.json", new_registry)
    atomic_json(public / "best_checkpoint_identity.json", new_registry["BEST"])
    atomic_json(public / "last_checkpoint_identity.json", identity)
    retained = {entry["absolute_local_path"] for entry in (new_registry["BEST"], identity)}
    old = {entry["absolute_local_path"] for entry in (registry.get("BEST"), registry.get("LAST")) if entry}
    deleted = []
    for name in sorted(old - retained):
        target = Path(name).resolve()
        if target.parent != local or target.suffix != ".pt":
            raise ValueError("Checkpoint cleanup target outside this run's owned payloads")
        target.unlink()
        deleted.append(str(target))
    return new_registry, {"LAST": "VERIFIED_ATOMIC_WRITE", "BEST": "SELECTED" if selected else "RETAINED", "deleted_old_owned_payloads": deleted}


def make_payload(model, optimizer, expected, selection, epoch, validation):
    rng = capture_rng()
    return {**expected, "completed_epoch": epoch, "global_update": epoch * 5860,
        "validation_completed": True, "training_samples": 11720, "validation_samples": 11727,
        "global_val_core_loss": validation["global_val_core_loss"],
        "best_checkpoint_value": selection.best_checkpoint_value,
        "selected_checkpoint_epoch": selection.selected_checkpoint_epoch,
        "early_stop_best": selection.early_stop_best, "non_improvement_count": selection.non_improvement_count,
        "model_state_dict": model.state_dict(), "optimizer_state_dict": optimizer.state_dict(),
        "model_state_dict_sha256": state_digest(model.state_dict()),
        "optimizer_state_dict_sha256": state_digest(optimizer.state_dict()),
        "python_rng_state": rng["python"], "numpy_rng_state": rng["numpy"],
        "torch_cpu_rng_state": rng["torch_cpu"], "torch_cuda_rng_state": rng["torch_cuda"],
        "rng_states_sha256": state_digest(rng)}
