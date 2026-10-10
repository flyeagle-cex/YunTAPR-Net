"""Artificial batch=1 train and batch=8/5 inference, with unchanged frozen loss."""
from __future__ import annotations
from dataclasses import dataclass, replace
import hashlib
import json
from pathlib import Path
import re
import torch
from yuntapr.models.quantile_v2.models import B0MatchedV2, B1V2
from yuntapr.models.quantile_v2.outputs import LogDomainOutput, validate_log_quantiles
from yuntapr.training.phase_a_validation_v2 import LogDomainValidation
from yuntapr.experimental.phase_b_v2_ablations.config import get_config
from yuntapr.experimental.phase_b_v2_ablations.total import CandidateLossResult, candidate_loss
from . import SCOPE

REPO = Path(__file__).resolve().parents[4]
IDENTITY = REPO / "docs/phase_b_v2_boundary_validation/v1/source_identity.json"
IDENTITY_SHA = "aa8fcf95b00be2573bc93ecbdd3c38f3f45a0e0ba047cf7cfb6164b664db8a7b"
MODES = {1: "TRAIN_TAIL", 8: "VALIDATION_FULL", 5: "VALIDATION_TAIL"}
ARMS = ("E0", "E1", "E2")


def verify_inherited_identity() -> int:
    """Public source/aggregate evidence bytes only; no raw data or checkpoints."""
    raw = IDENTITY.read_bytes()
    if hashlib.sha256(raw).hexdigest() != IDENTITY_SHA:
        raise ValueError("Boundary source identity changed")
    items = json.loads(raw)["inherited_files"]
    for item in items:
        path = (REPO/item["path"]).resolve()
        if not path.is_relative_to(REPO.resolve()):
            raise ValueError("External reference forbidden")
        if hashlib.sha256(path.read_bytes()).hexdigest() != item["sha256"]:
            raise ValueError("Inherited source/evidence mismatch: " + item["path"])
    return len(items)


@dataclass(frozen=True)
class BoundaryBatch:
    x: torch.Tensor
    native_valid: torch.Tensor
    rate: torch.Tensor
    reference_valid: torch.Tensor
    region_mask: torch.Tensor
    sample_ids: tuple[str, ...]
    slot_offsets: tuple[int, ...]
    mode: str
    scope: str = SCOPE
    data_years: tuple[int, ...] = ()
    mask_role: str = "ARTIFICIAL_3430_CELLS_NOT_YUNNAN_GEOGRAPHY"

    def validate(self, kind: str) -> int:
        frames = {"B0_MATCHED_V2": 1, "B1_V2": 6}.get(kind)
        if frames is None or self.scope != SCOPE or self.data_years != () or self.mask_role != "ARTIFICIAL_3430_CELLS_NOT_YUNNAN_GEOGRAPHY":
            raise ValueError("Only declared artificial provenance accepted")
        if not isinstance(self.x, torch.Tensor) or self.x.ndim != 4:
            raise ValueError("Dense four-dimensional input required")
        size = self.x.shape[0]
        if size not in MODES or self.mode != MODES[size] or self.x.shape != (size, frames, 501, 501):
            raise ValueError("Only fixed train1 / validation8 / validation5 boundaries")
        if type(self.sample_ids) is not tuple or len(self.sample_ids) != size or len(set(self.sample_ids)) != size:
            raise ValueError("Exact unique artificial sample identity count required")
        if any(type(s) is not str or re.fullmatch(r"SYNTHETIC_ENGINEERING_ONLY/boundary_scene_[0-9]{4}", s) is None for s in self.sample_ids):
            raise ValueError("Artificial IDs only")
        if self.slot_offsets != ((10,) if frames == 1 else (60, 50, 40, 30, 20, 10)):
            raise ValueError("Frozen causal slots required")
        for name, tensor, shape, dtype in (
            ("x", self.x, (size,frames,501,501), torch.float32),
            ("native_valid", self.native_valid, self.x.shape, torch.bool),
            ("rate", self.rate, (size,1,100,100), torch.float32),
            ("reference_valid", self.reference_valid, (size,1,100,100), torch.bool),
            ("region_mask", self.region_mask, (size,1,100,100), torch.bool)):
            if not isinstance(tensor, torch.Tensor) or tensor.shape != shape or tensor.dtype != dtype:
                raise ValueError(name + ": exact shape and dtype; broadcasting forbidden")
            if tensor.layout != torch.strided or tensor.device != self.x.device or tensor.requires_grad:
                raise ValueError(name + ": dense colocated non-gradient fixture required")
        if self.x.device.type not in ("cpu", "cuda") or not bool(torch.isfinite(self.x).all()):
            raise FloatingPointError("Finite CPU/CUDA artificial inputs required")
        if not bool(torch.isfinite(self.rate).all()) or bool((self.rate < 0).any()):
            raise FloatingPointError("Finite nonnegative FP32 reference required")
        if not bool(self.native_valid.all()):
            raise ValueError("M1 incomplete native frame stops; no replacement")
        if not bool((self.region_mask.flatten(1).sum(1) == 3430).all()):
            raise ValueError("Artificial region count must be 3430 per scene")
        if not bool(((self.reference_valid & self.region_mask).flatten(1).sum(1) == 3430).all()):
            raise ValueError("Q1 incomplete reference stops; no scene skip")
        return size

    def to(self, device: str) -> BoundaryBatch:
        return replace(self, **{name: getattr(self,name).to(device) for name in
                               ("x","native_valid","rate","reference_valid","region_mask")})


def make_boundary_pair(size: int, rain_case: str) -> dict[str, BoundaryBatch]:
    """Finite normalized-coordinate sin pattern; no observed Kelvin or scaler fit."""
    if type(size) is not int or size not in MODES or rain_case not in ("MIXED", "EMPTY_RAIN"):
        raise ValueError("Closed batch sizes and artificial rainfall cases")
    cells = torch.arange(501*501, dtype=torch.float32).reshape(1,1,501,501)
    slots = torch.arange(6, dtype=torch.float32).reshape(1,6,1,1)
    scenes = torch.arange(size, dtype=torch.float32).reshape(size,1,1,1)
    x = .6*torch.sin(cells/173.) + .07*slots + .11*scenes
    threshold = torch.tensor(.1, dtype=torch.float32)
    if rain_case == "MIXED":
        rates = torch.stack((threshold*0, threshold, torch.nextafter(threshold, torch.tensor(float("inf"))),
                             threshold*5, threshold*10, threshold*50, threshold*200))
    else:
        rates = torch.stack((threshold*0, threshold, torch.nextafter(threshold, threshold*0)))
    rate = rates[torch.arange(size*10000) % len(rates)].reshape(size,1,100,100)
    region = (torch.arange(10000).reshape(1,1,100,100) < 3430).expand(size,1,100,100).clone()
    base = BoundaryBatch(x, torch.ones_like(x,dtype=torch.bool), rate,
        torch.ones_like(rate,dtype=torch.bool), region,
        tuple(f"{SCOPE}/boundary_scene_{i:04d}" for i in range(size)), (60,50,40,30,20,10), MODES[size])
    latest = replace(base, x=x[:,-1:].clone(), native_valid=base.native_valid[:,-1:].clone(), slot_offsets=(10,))
    result = {"B0_MATCHED_V2": latest, "B1_V2": base}
    for kind,batch in result.items():
        batch.validate(kind)
    return result


def losses_from_output(output: LogDomainOutput, batch: BoundaryBatch, kind: str) -> dict[str, CandidateLossResult]:
    """One unchanged output, three closed candidate objectives; never a common metric."""
    size = batch.validate(kind)
    if type(output) is not LogDomainOutput:
        raise ValueError("Frozen LogDomainOutput required")
    for name, channels, dtype in (("rain_logit",1,torch.bfloat16), ("rain_prob",1,torch.bfloat16),
                                  ("conditional_quantiles_log",32,torch.float64)):
        tensor = getattr(output,name)
        if not isinstance(tensor,torch.Tensor) or tensor.shape != (size,channels,100,100) or tensor.dtype != dtype:
            raise ValueError(name + ": frozen shape/precision mismatch")
        if tensor.device != batch.x.device or not bool(torch.isfinite(tensor).all()):
            raise FloatingPointError(name + ": device/nonfinite mismatch")
    validate_log_quantiles(output.conditional_quantiles_log)
    if not torch.equal(output.rain_prob, torch.sigmoid(output.rain_logit)):
        raise ValueError("Occurrence probability must be the head sigmoid")
    results = {arm: candidate_loss(output.rain_logit, output.conditional_quantiles_log, batch.rate,
                batch.reference_valid, batch.region_mask, config=get_config(arm)) for arm in ARMS}
    if any(loss.n_valid != size*3430 or loss.execution_authorization for loss in results.values()):
        raise FloatingPointError("Boundary supervision or authorization invariant failed")
    if any(not torch.equal(loss.s_qr, results["E0"].s_qr) for loss in results.values()):
        raise FloatingPointError("Unweighted quantile numerator changed with arm")
    return results


def forward_boundary(model: torch.nn.Module, batch: BoundaryBatch, kind: str) -> tuple[LogDomainOutput, dict[str, CandidateLossResult]]:
    """One full CUDA BF16 forward. Validation uses frozen inference_mode semantics."""
    size = batch.validate(kind)
    expected = {"B0_MATCHED_V2":B0MatchedV2, "B1_V2":B1V2}[kind]
    training = batch.mode == "TRAIN_TAIL"
    if type(model) is not expected or model.training != training or batch.x.device.type != "cuda":
        raise ValueError("Exact model/mode/CUDA boundary required; no precision or device fallback")
    if any(p.device != batch.x.device or p.dtype != torch.float32 for p in model.parameters()):
        raise ValueError("Frozen FP32 parameters required")
    if model.heads.numerics.epsilon_w != 1e-4 or model.heads.numerics.epsilon_span != 1e-4:
        raise ValueError("Frozen epsilon drift")
    with torch.inference_mode(mode=not training), torch.autocast("cuda",dtype=torch.bfloat16):
        output = model(batch.x,batch.native_valid)
        results = losses_from_output(output,batch,kind)
    if output.native_feature_shape != (size,48,501,501) or output.target_feature_shape != (size,48,100,100):
        raise ValueError("Native/SP04 shape mismatch")
    support = output.target_support_fraction
    if support.shape != (size,1,100,100) or not bool((support == 1).all()):
        raise ValueError("SP04 support loss")
    if not bool((output.b13_invalid_count == 0).all()) or not bool((output.b13_valid_fraction == 1).all()):
        raise ValueError("M1 support loss")
    if any(t.requires_grad != training for t in (output.rain_logit,output.conditional_quantiles_log)):
        raise ValueError("Train/validation graph boundary violated")
    return output, results


def evaluation_components(results: dict[str, CandidateLossResult], *, output: LogDomainOutput,
                          batch: BoundaryBatch) -> dict:
    """Frozen FP64 validation recomputation, not any arm's training numerator."""
    if type(results) is not dict or set(results) != set(ARMS):
        raise ValueError("Three explicitly labeled candidate results required")
    base = results["E0"]
    if any(v.experiment_id != k or v.n_valid != base.n_valid or v.n_rain != base.n_rain
           or not torch.equal(v.s_qr,base.s_qr) for k,v in results.items()):
        raise ValueError("Mismatched scientific component identity")
    # The historical accumulator recomputes BCE/Focal in FP64. E0's training
    # S_occ is FP32, so even gamma2 E0 is not the identical common evaluation.
    accumulator = LogDomainValidation()
    accumulator.add(output,batch.rate,batch.reference_valid,batch.region_mask)
    report = accumulator.report()
    if report["N_valid"] != base.n_valid or report["N_rain"] != base.n_rain:
        raise FloatingPointError("Frozen evaluation denominator disagrees with candidate")
    return {"scope":SCOPE,"scientific_performance_evidence":False,
            "occurrence_gamma_for_common_core":2,"S_occ_gamma2_unweighted":report["S_occ"],
            "S_qr_unweighted":report["S_qr"],"N_valid":base.n_valid,"N_rain":base.n_rain}


def aggregate_evaluation(records: list[dict]) -> dict:
    """Sum unweighted numerators and their own denominators before dividing."""
    import math
    required = {"scope","scientific_performance_evidence","occurrence_gamma_for_common_core",
                "S_occ_gamma2_unweighted","S_qr_unweighted","N_valid","N_rain"}
    if not records:
        raise ValueError("No empty aggregate")
    for row in records:
        if set(row) != required or row["scope"] != SCOPE or row["scientific_performance_evidence"] is not False or row["occurrence_gamma_for_common_core"] != 2:
            raise ValueError("No weighted training objective or changed common gamma")
        if type(row["N_valid"]) is not int or type(row["N_rain"]) is not int or not 0 <= row["N_rain"] <= row["N_valid"] or row["N_valid"] <= 0:
            raise ValueError("Invalid denominators")
        if any(type(row[k]) not in (int,float) or not math.isfinite(row[k]) or row[k] < 0
               for k in ("S_occ_gamma2_unweighted","S_qr_unweighted")):
            raise FloatingPointError("Nonfinite or negative evaluation numerator")
    occ, qr = (math.fsum(row[k] for row in records) for k in ("S_occ_gamma2_unweighted","S_qr_unweighted"))
    valid, rainy = (sum(row[k] for row in records) for k in ("N_valid","N_rain"))
    return {"scope":SCOPE,"synthetic_common_core":(occ+qr)/valid,
            "synthetic_conditional_pinball":qr/rainy if rainy else None,
            "N_valid":valid,"N_rain":rainy,"scientific_performance_evidence":False}
