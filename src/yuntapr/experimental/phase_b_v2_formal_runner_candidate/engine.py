"""Production-shaped train → validate → LAST transaction, synthetic only."""
from __future__ import annotations
import json
from pathlib import Path
import torch
from yuntapr.training.phase_a_protocol import state_digest
from yuntapr.experimental.phase_b_v2_ablations.config import RunSpec, get_config
from yuntapr.experimental.phase_b_v2_runner_candidate.optimizer import new_adamw, PrefixSchedule, clip_and_check, check_finite
from yuntapr.experimental.phase_b_v2_runner_candidate import rng
from yuntapr.experimental.phase_b_v2_integration.resources import resource_snapshot, require_resources
from .protocol import run_identity, verify_public_sources, fresh_models_without_observational_artifacts
from .data import Registry, Loader, Coverage, ROLES, to_cuda
from .metrics import StreamingValidation
from .adapter import forward
from .checkpoint import EpochStore, SCHEMA, validate_last, optimizer_template
from .safety import Ledger
from .authorization import start_formal


class EpochSchedule(PrefixSchedule):
    """Same S0 math/order; expand synthetic restore limit from old 2 to 6."""
    def load_state_dict(self, state: dict):
        expected = self.state_dict(); expected["completed"] = state.get("completed")
        if state != expected or type(state["completed"]) is not int or not 0 <= state["completed"] <= 6:
            raise ValueError("Synthetic full-epoch schedule identity/progress mismatch")
        self.completed = state["completed"]


class EpochEngine:
    def __init__(self, spec: RunSpec, registry: Registry, ledger: Ledger):
        if type(registry) is not Registry or type(ledger) is not Ledger or spec.seed != 2026:
            raise ValueError("Fixed synthetic engineering campaign inputs/seed only")
        registry.check()
        self.identity = run_identity(spec, registry.identity_sha)
        self.public_pins = verify_public_sources()
        torch.cuda.empty_cache()
        self.resources = resource_snapshot(full_backward=True); require_resources(self.resources)
        models, self.fresh_proof = fresh_models_without_observational_artifacts(spec.seed)
        self.model = models[spec.model].to("cuda:0")
        self.initial_sha = state_digest(self.model.state_dict())
        if self.initial_sha != self.fresh_proof["state_sha256"][spec.model]:
            raise ValueError("Fresh initialization device identity changed")
        self.buffer_sha = state_digest(dict(self.model.named_buffers()))
        self.optimizer, self.group_evidence = new_adamw(self.model)
        self.schedule, self.store = EpochSchedule(), EpochStore()
        self.spec, self.registry, self.ledger = spec, registry, ledger
        self.completed_epoch, self.phase, self.poisoned = 0, "READY", False
        self.train_receipt = self.epoch_receipt = None
        self.parent_last_sha = None
        self.last_reference = None

    def _healthy(self):
        if self.poisoned:
            raise RuntimeError("Poisoned epoch transaction; no automatic retry")
        if self.identity != run_identity(self.spec, self.registry.identity_sha):
            raise ValueError("Protocol/code/source identity changed")
        self.registry.check()
        self.ledger.read()  # never restore/refund/recreate the consumed quota
        if self.buffer_sha != state_digest(dict(self.model.named_buffers())):
            raise ValueError("Frozen spatial buffer changed")

    def train_epoch(self) -> dict:
        self._healthy()
        if self.phase != "READY" or self.completed_epoch >= 2:
            raise ValueError("No incomplete epoch restart, BEST selection or budget extension")
        epoch = self.completed_epoch + 1
        loader = Loader(self.registry, self.spec.model, ROLES[0], self.spec.seed, epoch - 1)
        coverage = Coverage(self.registry.ids(ROLES[0]))
        config = get_config(self.spec.experiment_id)
        self.phase = "TRAINING"
        batches = []
        try:
            self.model.train()
            for cpu_batch in loader:
                torch.cuda.empty_cache(); require_resources(resource_snapshot(full_backward=True))
                coverage.add(cpu_batch.ids)
                batch = to_cuda(cpu_batch)
                self.optimizer.zero_grad(set_to_none=True)
                lr = self.schedule.prepare(self.optimizer)
                output, loss = forward(self.model, batch, self.spec.model, self.spec.experiment_id)
                loss.training_objective.backward()
                clipping = clip_and_check(self.model)
                if not loss.n_rain:
                    if float(loss.s_qr.detach()) != 0 or any(p.grad is None or bool((p.grad != 0).any())
                            for n, p in self.model.named_parameters() if n.startswith("heads.quantile.")):
                        raise ValueError("Dry batch quantile gradient is not connected zero")
                expected = (loss.s_occ + config.lambda_q * loss.s_qr) / loss.n_valid
                if not torch.equal(loss.training_objective, expected):
                    raise ValueError("Training weighting/denominator contract failed")
                event = {"synthetic_epoch": epoch, "synthetic_update": self.schedule.completed + 1,
                         "scene_ids": list(batch.ids), "lr": lr}
                self.ledger.perform(self.optimizer, self.spec.model + "__" + self.spec.experiment_id, event)
                self.schedule.commit()
                check_finite(self.model.state_dict()); check_finite(self.optimizer.state_dict())
                batches.append({**event, "batch": len(batch.ids), "N_valid": loss.n_valid, "N_rain": loss.n_rain,
                    "S_occ_unweighted_training": float(loss.s_occ.detach()), "S_qr_unweighted": float(loss.s_qr.detach()),
                    "training_objective_synthetic": float(loss.training_objective.detach()),
                    "empty_rain_connected_zero": not bool(loss.n_rain), **clipping})
                del output, loss, expected, batch
            self.train_receipt = {"coverage": coverage.finish(), "batches": len(batches), "batch_records": batches,
                "N_valid": sum(b["N_valid"] for b in batches), "N_rain": sum(b["N_rain"] for b in batches),
                "S_occ_unweighted_training": sum(b["S_occ_unweighted_training"] for b in batches),
                "S_qr_unweighted": sum(b["S_qr_unweighted"] for b in batches)}
            if len(batches) != 3 or [b["batch"] for b in batches] != [2, 2, 1] or self.schedule.completed != epoch * 3:
                raise ValueError("Incomplete synthetic epoch/update budget")
            self.phase = "WAIT_VALIDATION"
            return self.train_receipt
        except BaseException:
            self.poisoned = True
            raise

    @torch.inference_mode()
    def validate_and_commit(self) -> tuple[dict, Path]:
        self._healthy()
        if self.phase != "WAIT_VALIDATION":
            raise ValueError("Full training receipt must precede independent validation")
        epoch = self.completed_epoch + 1
        self.phase = "VALIDATING"
        try:
            self.model.eval()
            streaming = StreamingValidation(self.registry.ids(ROLES[1]))
            for cpu_batch in Loader(self.registry, self.spec.model, ROLES[1], self.spec.seed, epoch - 1):
                batch = to_cuda(cpu_batch)
                output, _ = forward(self.model, batch, self.spec.model, self.spec.experiment_id)
                streaming.add(output, batch)
                del output, batch
            report = streaming.finish()
            receipt = {"epoch": epoch, "update": self.schedule.completed, "train": self.train_receipt,
                       "validation": report, "formal_epoch": 0, "FORMAL_OPTIMIZER_STEPS": 0}
            payload = {"schema": SCHEMA, "identity": self.identity, "initial_sha": self.initial_sha,
                "model": self.model.state_dict(), "optimizer": self.optimizer.state_dict(),
                "scheduler": self.schedule.state_dict(), "rng": rng.capture(), "epoch_receipt": receipt,
                "ancestor": {"campaign": "SYNTHETIC_EPOCH_ENGINE_v1", "parent_last_sha": self.parent_last_sha}}
            self._validate_payload(payload)
            reference = self.store.save(f"LAST_SYNTHETIC_EPOCH{epoch}_{self.spec.experiment_id}", payload)
            # Committed blob+receipt precedes live completion advancement.
            self.completed_epoch, self.epoch_receipt, self.last_reference = epoch, receipt, reference
            self.parent_last_sha = json.loads(reference.read_text())["sha256"]
            self.phase = "READY"
            return receipt, reference
        except BaseException:
            self.poisoned = True
            raise

    def _validate_payload(self, payload):
        validate_last(payload, self.identity, self.model.state_dict(), optimizer_template(self.optimizer),
                      self.registry.ids(ROLES[0]), self.registry.ids(ROLES[1]), self.initial_sha)

    def restore_completed_last(self, source_store: EpochStore, reference: Path, expected_last_sha: str) -> dict:
        self._healthy()
        if self.phase != "READY" or self.completed_epoch != 0 or self.schedule.completed != 0:
            raise ValueError("Restore only into fresh candidate engine; partial live state cannot be resumed")
        if type(source_store) is not EpochStore:
            raise ValueError("Current version synthetic epoch store required")
        from .safety import TEMP_ROOT
        reference = reference.resolve()
        if (not source_store.root.resolve().is_relative_to(TEMP_ROOT.resolve())
                or reference.parent != source_store.root or not reference.name.endswith(".ref.json")):
            raise PermissionError("Synthetic LAST reference outside registered store")
        metadata = json.loads(reference.read_text(encoding="utf-8"))
        if metadata.get("sha256") != expected_last_sha:
            raise ValueError("Exact LAST SHA binding missing/mismatched")
        payload = source_store.read(reference)
        self._validate_payload(payload)
        try:
            self.model.load_state_dict(payload["model"], strict=True)
            self.optimizer.load_state_dict(payload["optimizer"])
            self.schedule.load_state_dict(payload["scheduler"])
            rng.restore(payload["rng"])
            self.completed_epoch = payload["epoch_receipt"]["epoch"]
            self.epoch_receipt = payload["epoch_receipt"]
            self.parent_last_sha = expected_last_sha
            self.optimizer.zero_grad(set_to_none=True)
            actual = self.state_identity()
            expected = {k: state_digest(payload[k]) for k in ("model", "optimizer", "scheduler", "rng")}
            if actual != expected:
                raise ValueError("Synthetic resumed state mismatch")
            return actual
        except BaseException:
            self.poisoned = True
            raise

    def state_identity(self) -> dict:
        return {"model": state_digest(self.model.state_dict()), "optimizer": state_digest(self.optimizer.state_dict()),
                "scheduler": state_digest(self.schedule.state_dict()), "rng": state_digest(rng.capture())}

    def selected_endpoint(self) -> dict:
        return {"synthetic_terminal_epoch": 2, "selected_synthetic_epoch": 2 if self.completed_epoch == 2 else None,
                "scientific_endpoint": "V0_EPOCH9_NOT_EXECUTED", "formal_selected_epoch": None,
                "formal_runs_executed": 0, "BEST_used": False}

    def start_formal(self, *args, **kwargs):
        start_formal(*args, **kwargs)
