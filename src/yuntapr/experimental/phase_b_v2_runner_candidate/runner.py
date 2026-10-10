"""One synthetic update transaction, fixed evaluation, and synthetic restore.

No paths/batches supplied by the caller, no dataloader, no epoch training loop,
no approval flag. Restoring checkpoints never restores the task step quota.
"""
from __future__ import annotations
from dataclasses import replace
import torch
from yuntapr.training.phase_a_protocol import state_digest
from yuntapr.training.phase_a_validation_v2 import LogDomainValidation
from yuntapr.experimental.phase_b_v2_ablations.config import RunSpec, get_config
from yuntapr.experimental.phase_b_v2_integration.initialization import fresh_paired_models
from yuntapr.experimental.phase_b_v2_integration.synthetic import make_synthetic_pair
from yuntapr.experimental.phase_b_v2_integration.adapter import forward_synthetic
from yuntapr.experimental.phase_b_v2_integration.resources import resource_snapshot, require_resources
from .identity import identity, verify_sources, reject_formal_execution
from .optimizer import new_adamw, PrefixSchedule, clip_and_check, check_finite
from .checkpoint import SCHEMA, SyntheticStore, validate_payload
from .safety import StepLedger, install_guard
from . import rng


class SyntheticRunner:
    def __init__(self, spec: RunSpec, ledger: StepLedger):
        install_guard()
        self.identity = identity(spec)
        if spec.seed != 2026:
            raise ValueError("This engineering campaign executes seed2026 only; other seeds are candidate metadata")
        self.source_count = verify_sources()
        self.admission = resource_snapshot(full_backward=True)
        require_resources(self.admission)  # before constructing either real full-grid architecture
        models, proof = fresh_paired_models(spec.seed)
        self.model = models[spec.model].to("cuda:0")
        self.initial_sha = state_digest(self.model.state_dict())
        if self.initial_sha != proof["state_sha256"][spec.model]:
            raise ValueError("Fresh CPU/CUDA state identity changed")
        self.buffers_sha = state_digest(dict(self.model.named_buffers()))
        self.optimizer, self.groups = new_adamw(self.model)
        self.schedule = PrefixSchedule()
        self.spec, self.ledger = spec, ledger
        self._batch = make_synthetic_pair()[spec.model].to("cuda:0")
        self.store = SyntheticStore()
        self.train_complete = self.validation_complete = False
        self.poisoned = False

    def start_formal(self, *args, **kwargs):
        reject_formal_execution(*args, **kwargs)

    def _healthy(self):
        if self.poisoned:
            raise RuntimeError("Failed synthetic transaction poisoned runner; no retry")
        if self.identity != identity(self.spec):
            raise ValueError("Candidate identity mutated")
        if state_digest(dict(self.model.named_buffers())) != self.buffers_sha:
            raise ValueError("Frozen spatial buffer identity changed")

    def empty_rain_gradient_check(self) -> dict:
        """Backward only; verifies connected zero quantile gradient, no step."""
        self._healthy()
        self.model.train()
        self.optimizer.zero_grad(set_to_none=True)
        empty = replace(self._batch, rate=torch.zeros_like(self._batch.rate))
        _, loss = forward_synthetic(self.model, empty, self.spec.model, self.spec.experiment_id)
        loss.training_objective.backward()
        clipping = clip_and_check(self.model)
        names = [n for n, _ in self.model.named_parameters() if "quantile" in n]
        if not names or loss.n_rain != 0 or float(loss.s_qr.detach()) != 0:
            raise AssertionError("Empty rain semantics changed")
        for name, p in self.model.named_parameters():
            if name in names and (p.grad is None or bool((p.grad != 0).any())):
                raise AssertionError("Empty quantile gradient must be connected zero: " + name)
        self.optimizer.zero_grad(set_to_none=True)
        return {"N_rain": 0, "S_qr": 0., "quantile_gradient_connected_zero": True,
                "quantile_parameter_names": names, "optimizer_steps": 0, **clipping}

    def update_once(self) -> dict:
        self._healthy()
        # Release unused allocator cache before measuring OS-visible free memory;
        # no model, batch, precision or required threshold changes.
        torch.cuda.empty_cache()
        require_resources(resource_snapshot(full_backward=True))
        try:
            if self.schedule.completed and not self.validation_complete:
                raise ValueError("Previous synthetic validation boundary incomplete")
            self.model.train()
            self.optimizer.zero_grad(set_to_none=True)
            lr = self.schedule.prepare(self.optimizer)  # frozen order: pre-step LR assignment
            _, result = forward_synthetic(self.model, self._batch, self.spec.model, self.spec.experiment_id)
            result.training_objective.backward()
            clipping = clip_and_check(self.model)
            config = get_config(self.spec.experiment_id)
            expected = (result.s_occ + config.lambda_q * result.s_qr) / result.n_valid
            if not torch.equal(result.training_objective, expected):
                raise AssertionError("Training objective weighting/denominator mismatch")
            before = {n: state_digest(p) for n, p in self.model.named_parameters()}
            key = self.spec.model + "__" + self.spec.experiment_id
            self.ledger.perform(self.optimizer, key)
            self.schedule.commit()
            self.train_complete, self.validation_complete = True, False
            check_finite(self.model.state_dict())
            check_finite(self.optimizer.state_dict())
            changed = [n for n, p in self.model.named_parameters() if state_digest(p) != before[n]]
            for prefix in ("backbone.", "heads.occurrence.", "heads.quantile."):
                if not any(n.startswith(prefix) for n in changed):
                    raise AssertionError("Backbone/dual head not updated: " + prefix)
            if len(self.optimizer.state) != len(tuple(self.model.parameters())):
                raise AssertionError("Missing AdamW parameter states")
            return {"scope": self.identity["scope"], "synthetic_update": self.schedule.completed,
                    "S_occ_training_unweighted": float(result.s_occ.detach()),
                    "S_qr_unweighted": float(result.s_qr.detach()), "N_valid": result.n_valid, "N_rain": result.n_rain,
                    "training_objective_synthetic": float(result.training_objective.detach()), "lr": lr,
                    "changed_parameters": changed, "optimizer_state_count": len(self.optimizer.state),
                    "all_state_finite": True, "FORMAL_OPTIMIZER_STEPS": 0, **clipping}
        except BaseException:
            self.poisoned = True
            raise

    @torch.inference_mode()
    def evaluate_synthetic(self) -> dict:
        self._healthy()
        if not self.train_complete:
            raise ValueError("Synthetic update required before completion validation")
        try:
            self.model.eval()
            with torch.autocast("cuda", dtype=torch.bfloat16):
                output = self.model(self._batch.x, self._batch.native_valid)
            accumulator = LogDomainValidation()
            accumulator.add(output, self._batch.rate, self._batch.reference_valid, self._batch.region_mask)
            report = accumulator.report()
            # No candidate gamma/lambda enters the frozen FP64 common evaluation.
            report["conditional_pinball_synthetic"] = report["S_qr"] / report["N_rain"] if report["N_rain"] else None
            report["scope"] = self.identity["scope"]
            report["scientific_performance_evidence"] = False
            self.validation_complete = True
            return report
        except BaseException:
            self.poisoned = True
            raise

    def _optimizer_template(self) -> dict:
        template = self.optimizer.state_dict()
        template["_shapes"] = {i: tuple(p.shape) for group, state in
                                zip(self.optimizer.param_groups, template["param_groups"], strict=True)
                                for i, p in zip(state["params"], group["params"], strict=True)}
        return template

    def payload(self) -> dict:
        self._healthy()
        if self.schedule.completed and not (self.train_complete and self.validation_complete):
            raise ValueError("Cannot save incomplete synthetic train/validation boundary")
        return {"schema": SCHEMA, "identity": self.identity, "initial_sha": self.initial_sha,
                "model": self.model.state_dict(), "optimizer": self.optimizer.state_dict(),
                "scheduler": self.schedule.state_dict(), "rng": rng.capture(),
                "progress": {"formal_epoch": 0, "FORMAL_OPTIMIZER_STEPS": 0,
                             "synthetic_updates": self.schedule.completed, "train_complete": self.train_complete,
                             "validation_complete": self.validation_complete}}

    def save(self, name: str):
        payload = self.payload()
        validate_payload(payload, self.identity, self.model.state_dict(), self._optimizer_template())
        return self.store.save(name, payload)

    def restore(self, reference) -> dict:
        self._healthy()
        payload = self.store.read(reference)
        validate_payload(payload, self.identity, self.model.state_dict(), self._optimizer_template())
        if payload["initial_sha"] != self.initial_sha:
            raise ValueError("Checkpoint fresh ancestry identity mismatch")
        try:
            self.model.load_state_dict(payload["model"], strict=True)
            self.optimizer.load_state_dict(payload["optimizer"])
            self.schedule.load_state_dict(payload["scheduler"])
            rng.restore(payload["rng"])
            self.train_complete = payload["progress"]["train_complete"]
            self.validation_complete = payload["progress"]["validation_complete"]
            self.optimizer.zero_grad(set_to_none=True)
            actual = self.state_identity()
            expected = {k: state_digest(payload[k]) for k in ("model", "optimizer", "scheduler", "rng")}
            if actual != expected:
                raise ValueError("Restored synthetic state identity mismatch")
            return actual
        except BaseException:
            self.poisoned = True
            raise

    def state_identity(self) -> dict:
        return {"model": state_digest(self.model.state_dict()), "optimizer": state_digest(self.optimizer.state_dict()),
                "scheduler": state_digest(self.schedule.state_dict()), "rng": state_digest(rng.capture())}
